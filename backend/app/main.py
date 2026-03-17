"""
KGKB Backend - FastAPI Application

Main entry point for the KGKB REST API.
"""

from contextlib import asynccontextmanager
from typing import List, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .models.knowledge import (
    Knowledge,
    KnowledgeCreate,
    KnowledgeUpdate,
    Relation,
    RelationCreate,
    SearchResult,
    GraphData,
    GraphNode,
    GraphEdge,
)
from .services.knowledge import KnowledgeService
from .services.embedding import EmbeddingService, create_embedding_service
from .services.vector_store import FAISSVectorStore, VectorStoreManager


# Global services
knowledge_service: Optional[KnowledgeService] = None
embedding_service: Optional[EmbeddingService] = None
vector_manager: Optional[VectorStoreManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup."""
    global knowledge_service, embedding_service, vector_manager

    # Initialize knowledge service (default: ~/.kgkb/data.db)
    db_path = Path.home() / ".kgkb" / "data.db"
    knowledge_service = KnowledgeService(db_path)

    # Initialize embedding service (default: ollama with qwen3-embedding)
    embedding_service = create_embedding_service(
        provider="ollama",
        model="qwen3-embedding:0.6b",
    )

    # Initialize vector store
    vector_path = Path.home() / ".kgkb" / "vectors"
    vector_store = FAISSVectorStore(
        dimension=1024,  # qwen3-embedding:0.6b default
        index_path=vector_path,
    )
    vector_manager = VectorStoreManager(vector_store, embedding_service)

    # Try to load existing index
    try:
        vector_store.load()
        print(f"Loaded vector store with {vector_store.count()} vectors")
    except Exception as e:
        print(f"Starting with empty vector store: {e}")

    yield

    # Cleanup on shutdown
    if vector_store:
        try:
            vector_store.save()
            print("Saved vector store")
        except Exception as e:
            print(f"Error saving vector store: {e}")


app = FastAPI(
    title="KGKB API",
    description="Knowledge Graph Knowledge Base REST API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ Response Models ============

class KnowledgeResponse(BaseModel):
    """Response model for knowledge."""
    id: str
    title: str
    content: str
    content_type: str
    tags: List[str]
    source: Optional[str]
    created_at: str
    updated_at: str


class PaginatedKnowledgeResponse(BaseModel):
    """Paginated list response for knowledge entries."""
    items: List[KnowledgeResponse]
    total: int
    limit: int
    offset: int


class DeleteResponse(BaseModel):
    """Standard response for delete operations."""
    status: str
    id: str


# ============ Helpers ============

def _knowledge_to_response(k) -> KnowledgeResponse:
    """Convert a KnowledgeEntry to a KnowledgeResponse."""
    return KnowledgeResponse(
        id=k.id,
        title=getattr(k, "title", ""),
        content=k.content,
        content_type=getattr(k, "content_type", "text"),
        tags=k.tags,
        source=k.source,
        created_at=k.created_at.isoformat(),
        updated_at=k.updated_at.isoformat(),
    )


@app.post("/api/knowledge", response_model=KnowledgeResponse, status_code=201)
async def create_knowledge(data: KnowledgeCreate):
    """Create a new knowledge entry.

    Accepts title, content, content_type, tags, and source.
    Auto-generates a title from content if not provided.
    Triggers embedding generation if embedding service is available.
    """
    if not knowledge_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        knowledge = knowledge_service.create(
            content=data.content,
            title=data.title,
            content_type=data.content_type,
            tags=data.tags,
            source=data.source,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create knowledge: {e}")

    # Generate embedding asynchronously (best-effort, don't fail the request)
    if vector_manager:
        try:
            await vector_manager.index_knowledge(
                id=knowledge.id,
                content=knowledge.content,
                metadata={"tags": knowledge.tags, "source": knowledge.source},
            )
        except Exception as e:
            print(f"Warning: Failed to index knowledge {knowledge.id}: {e}")

    return _knowledge_to_response(knowledge)


@app.get("/api/knowledge/{kid}", response_model=KnowledgeResponse)
async def get_knowledge(kid: str):
    """Get a knowledge entry by ID.

    Supports both full UUIDs and partial ID prefix matching.
    """
    if not knowledge_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    knowledge = knowledge_service.get(kid)
    if not knowledge:
        raise HTTPException(status_code=404, detail=f"Knowledge not found: {kid}")

    return _knowledge_to_response(knowledge)


@app.get("/api/knowledge", response_model=PaginatedKnowledgeResponse)
async def list_knowledge(
    tag: Optional[str] = Query(None, description="Filter by tag"),
    content_type: Optional[str] = Query(None, description="Filter by content type"),
    limit: int = Query(20, ge=1, le=100, description="Max items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """List knowledge entries with pagination, tag filter, and content type filter."""
    if not knowledge_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    entries = knowledge_service.list(
        tag=tag, content_type=content_type, limit=limit, offset=offset
    )
    total = knowledge_service.count(tag=tag)

    return PaginatedKnowledgeResponse(
        items=[_knowledge_to_response(k) for k in entries],
        total=total,
        limit=limit,
        offset=offset,
    )


@app.put("/api/knowledge/{kid}", response_model=KnowledgeResponse)
async def update_knowledge(kid: str, data: KnowledgeUpdate):
    """Update a knowledge entry.

    Only provided (non-None) fields are updated; omitted fields keep their current values.
    Re-indexes the embedding if content changes.
    """
    if not knowledge_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        knowledge = knowledge_service.update(
            kid,
            title=data.title,
            content=data.content,
            content_type=data.content_type,
            tags=data.tags,
            source=data.source,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update knowledge: {e}")

    if not knowledge:
        raise HTTPException(status_code=404, detail=f"Knowledge not found: {kid}")

    # Re-index embedding if content changed
    if data.content is not None and vector_manager:
        try:
            await vector_manager.index_knowledge(
                id=knowledge.id,
                content=knowledge.content,
                metadata={"tags": knowledge.tags, "source": knowledge.source},
            )
        except Exception as e:
            print(f"Warning: Failed to re-index knowledge {knowledge.id}: {e}")

    return _knowledge_to_response(knowledge)


@app.delete("/api/knowledge/{kid}", response_model=DeleteResponse)
async def delete_knowledge(kid: str):
    """Delete a knowledge entry and its relations/embeddings.

    Also removes the vector from the FAISS index if present.
    """
    if not knowledge_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    if not knowledge_service.delete(kid):
        raise HTTPException(status_code=404, detail=f"Knowledge not found: {kid}")

    # Remove from vector store (best-effort)
    if vector_manager:
        try:
            vector_manager.store.delete_vector(kid)
        except Exception as e:
            print(f"Warning: Failed to remove vector for {kid}: {e}")

    return DeleteResponse(status="deleted", id=kid)


@app.get("/api/tags", response_model=List[str])
async def list_tags():
    """Get all unique tags across all knowledge entries."""
    if not knowledge_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return knowledge_service.get_all_tags()


# ============ Search Endpoints ============

class SearchResponse(BaseModel):
    """Search response model."""
    results: List[dict]
    total: int
    query: str


@app.get("/api/search", response_model=SearchResponse)
async def search_knowledge(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, le=50),
    semantic: bool = Query(False),
):
    """Search knowledge entries."""
    if semantic and vector_manager:
        # Semantic search
        try:
            results = await vector_manager.search_knowledge(q, k=limit)
            return SearchResponse(
                results=[{"id": r.id, "score": r.score, "content": r.content} for r in results],
                total=len(results),
                query=q,
            )
        except Exception as e:
            print(f"Semantic search failed: {e}")
            # Fall back to keyword search

    # Keyword search
    results = knowledge_service.search(q, limit=limit)
    return SearchResponse(
        results=[{"id": r.id, "content": r.content, "tags": r.tags} for r in results],
        total=len(results),
        query=q,
    )


# ============ Graph Endpoints ============

@app.get("/api/graph", response_model=GraphData)
async def get_graph(
    depth: int = Query(2, ge=1, le=5),
    node_id: Optional[str] = Query(None, description="Center node for subgraph (BFS)"),
):
    """Get graph data for visualization.

    Without node_id: returns the full graph (all nodes + edges).
    With node_id: returns a subgraph around that node, expanding via BFS
    up to the specified depth.
    """
    if not knowledge_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    nodes, edges = knowledge_service.get_graph(center_id=node_id, depth=depth)

    return GraphData(
        nodes=[
            GraphNode(
                id=n.id,
                label=n.title if n.title else n.content[:50],
                content=n.content,
                tags=n.tags,
                created_at=n.created_at,
            )
            for n in nodes
        ],
        edges=[
            GraphEdge(
                id=e.id,
                source=e.source_id,
                target=e.target_id,
                type=e.type,
                weight=e.weight,
            )
            for e in edges
        ],
    )


# ============ Relations Endpoints ============

class RelationResponse(BaseModel):
    """Response model for a single relation."""
    id: str
    source_id: str
    target_id: str
    type: str
    weight: float
    created_at: str


class RelationListResponse(BaseModel):
    """Response model for relation list."""
    items: List[RelationResponse]
    total: int
    node_id: Optional[str] = None


def _relation_to_response(r) -> RelationResponse:
    """Convert a RelationEntry to a RelationResponse."""
    return RelationResponse(
        id=r.id,
        source_id=r.source_id,
        target_id=r.target_id,
        type=r.type,
        weight=r.weight,
        created_at=r.created_at.isoformat() if hasattr(r.created_at, "isoformat") else str(r.created_at),
    )


@app.post("/api/relations", response_model=RelationResponse, status_code=201)
async def create_relation(data: RelationCreate):
    """Create a relationship between two knowledge entries.

    Validates that both source and target nodes exist.
    Rejects self-relations and duplicate relations (same source, target, type).
    """
    if not knowledge_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        relation = knowledge_service.create_relation(
            source_id=data.source_id,
            target_id=data.target_id,
            type=data.type,
            weight=data.weight,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return _relation_to_response(relation)


@app.get("/api/relations", response_model=RelationListResponse)
async def list_relations(
    node_id: Optional[str] = Query(None, description="Filter relations by node ID"),
    type: Optional[str] = Query(None, description="Filter by relation type"),
    limit: int = Query(50, ge=1, le=200),
):
    """List relationships, optionally filtered by node ID and/or relation type.

    When node_id is provided, returns all relations where the node appears
    as either source or target.
    """
    if not knowledge_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    if node_id:
        relations = knowledge_service.get_relations_for_node(node_id)
    else:
        relations = knowledge_service.list_relations(limit=limit)

    # Apply optional type filter
    if type:
        relations = [r for r in relations if r.type == type]

    # Apply limit for node-filtered results
    relations = relations[:limit]

    return RelationListResponse(
        items=[_relation_to_response(r) for r in relations],
        total=len(relations),
        node_id=node_id,
    )


@app.get("/api/relations/types", response_model=List[str])
async def list_relation_types():
    """Get all distinct relation types currently in use.

    Useful for populating dropdown/select options when creating new relations.
    """
    if not knowledge_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return knowledge_service.get_relation_types()


@app.get("/api/relations/{rid}", response_model=RelationResponse)
async def get_relation(rid: str):
    """Get a single relation by ID.

    Supports both full UUIDs and partial ID prefix matching.
    """
    if not knowledge_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    relation = knowledge_service.get_relation(rid)
    if not relation:
        raise HTTPException(status_code=404, detail=f"Relation not found: {rid}")

    return _relation_to_response(relation)


@app.delete("/api/relations/{rid}", response_model=DeleteResponse)
async def delete_relation(rid: str):
    """Delete a relationship by its ID.

    Supports both full UUID and partial ID prefix matching.
    """
    if not knowledge_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    if not knowledge_service.delete_relation(rid):
        raise HTTPException(status_code=404, detail=f"Relation not found: {rid}")

    return DeleteResponse(status="deleted", id=rid)


# ============ Health Check ============

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "vector_count": vector_manager.store.count() if vector_manager else 0,
        "knowledge_count": knowledge_service.count() if knowledge_service else 0,
    }


@app.get("/api/stats")
async def get_stats():
    """Get database statistics."""
    if not knowledge_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return knowledge_service.get_stats()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "KGKB API",
        "version": "0.1.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
