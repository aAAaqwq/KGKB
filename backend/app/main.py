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


# ============ Knowledge Endpoints ============

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


@app.post("/api/knowledge", response_model=KnowledgeResponse)
async def create_knowledge(data: KnowledgeCreate):
    """Create a new knowledge entry."""
    knowledge = knowledge_service.create(
        content=data.content,
        title=data.title,
        content_type=data.content_type,
        tags=data.tags,
        source=data.source,
    )

    # Generate embedding asynchronously
    if vector_manager:
        try:
            await vector_manager.index_knowledge(
                id=knowledge.id,
                content=knowledge.content,
                metadata={"tags": knowledge.tags, "source": knowledge.source},
            )
        except Exception as e:
            print(f"Warning: Failed to index knowledge: {e}")

    return _knowledge_to_response(knowledge)


@app.get("/api/knowledge/{kid}", response_model=KnowledgeResponse)
async def get_knowledge(kid: str):
    """Get a knowledge entry by ID."""
    knowledge = knowledge_service.get(kid)
    if not knowledge:
        raise HTTPException(status_code=404, detail="Knowledge not found")

    return _knowledge_to_response(knowledge)


@app.get("/api/knowledge", response_model=List[KnowledgeResponse])
async def list_knowledge(
    tag: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0),
):
    """List knowledge entries."""
    entries = knowledge_service.list(tag=tag, limit=limit, offset=offset)
    return [_knowledge_to_response(k) for k in entries]


@app.put("/api/knowledge/{kid}", response_model=KnowledgeResponse)
async def update_knowledge(kid: str, data: KnowledgeUpdate):
    """Update a knowledge entry."""
    knowledge = knowledge_service.update(
        kid,
        title=data.title,
        content=data.content,
        content_type=data.content_type,
        tags=data.tags,
        source=data.source,
    )
    if not knowledge:
        raise HTTPException(status_code=404, detail="Knowledge not found")

    return _knowledge_to_response(knowledge)


@app.delete("/api/knowledge/{kid}")
async def delete_knowledge(kid: str):
    """Delete a knowledge entry."""
    if not knowledge_service.delete(kid):
        raise HTTPException(status_code=404, detail="Knowledge not found")
    return {"status": "deleted"}


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
    depth: int = Query(2, le=5),
    node_id: Optional[str] = Query(None),
):
    """Get graph data for visualization."""
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

@app.post("/api/relations", response_model=Relation)
async def create_relation(data: RelationCreate):
    """Create a relationship between knowledge entries."""
    relation = knowledge_service.create_relation(
        source_id=data.source_id,
        target_id=data.target_id,
        type=data.type,
        weight=data.weight,
    )
    if not relation:
        raise HTTPException(status_code=400, detail="Failed to create relation")

    return relation


@app.get("/api/relations")
async def list_relations(limit: int = Query(50)):
    """List all relationships."""
    return knowledge_service.list_relations(limit=limit)


@app.delete("/api/relations/{rid}")
async def delete_relation(rid: str):
    """Delete a relationship."""
    if not knowledge_service.delete_relation(rid):
        raise HTTPException(status_code=404, detail="Relation not found")
    return {"status": "deleted"}


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
