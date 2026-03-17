"""
KGKB Backend - FastAPI Application

Main entry point for the KGKB REST API.
"""

import os
from contextlib import asynccontextmanager
from typing import Dict, List, Optional
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
from .services.embedding import (
    EmbeddingService,
    create_embedding_service,
    create_embedding_service_from_config,
    load_config,
)
from .services.vector_store import FAISSVectorStore, VectorStoreManager


# Global services
knowledge_service: Optional[KnowledgeService] = None
embedding_service: Optional[EmbeddingService] = None
vector_manager: Optional[VectorStoreManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup."""
    global knowledge_service, embedding_service, vector_manager

    # Load configuration from config.json (check KGKB_DATA_DIR, then ~/.kgkb)
    app_config = load_config()

    # Initialize knowledge service — respect KGKB_DATA_DIR for Docker
    data_dir_env = os.environ.get("KGKB_DATA_DIR")
    if data_dir_env:
        db_path = Path(data_dir_env) / "data.db"
    else:
        db_path_str = app_config.database.get("path", "~/.kgkb/data.db")
        db_path = Path(db_path_str).expanduser()
    knowledge_service = KnowledgeService(db_path)

    # Initialize embedding service from config file (graceful if unavailable)
    embedding_service = create_embedding_service_from_config()

    # Check if embedding service is reachable
    embedding_ok = await embedding_service.is_available()
    if embedding_ok:
        print(f"Embedding service ready: {embedding_service.config.provider} / {embedding_service.config.model}")
    else:
        print(
            f"Warning: Embedding service not reachable ({embedding_service.config.provider} "
            f"at {embedding_service.config.endpoint}). Semantic search disabled until available."
        )

    # Initialize vector store — respect KGKB_DATA_DIR for Docker
    vector_dim = app_config.vector.get("dimension", app_config.embedding.dimension)
    if data_dir_env:
        vector_path = Path(data_dir_env) / "vectors"
    else:
        vector_path = Path.home() / ".kgkb" / "vectors"
    vector_store = FAISSVectorStore(
        dimension=vector_dim,
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

# CORS configuration
# Default: allow common frontend dev ports + configurable via KGKB_CORS_ORIGINS env var
_default_origins = [
    "http://localhost:3000",    # Vite dev server (configured port)
    "http://localhost:5173",    # Vite default port
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://localhost:8080",    # Alternative dev port
    "http://127.0.0.1:8080",
]
_env_origins = os.environ.get("KGKB_CORS_ORIGINS", "")
if _env_origins == "*":
    _allowed_origins = ["*"]
elif _env_origins:
    _allowed_origins = [o.strip() for o in _env_origins.split(",") if o.strip()]
else:
    _allowed_origins = _default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
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

    # Auto-embed: generate embedding asynchronously (best-effort, don't fail the request)
    if vector_manager and embedding_service:
        try:
            embedding_vec = await embedding_service.embed_knowledge(
                knowledge.content,
                metadata={"tags": knowledge.tags, "source": knowledge.source, "title": knowledge.title},
            )
            if embedding_vec is not None:
                vector_manager.store.add(
                    knowledge.id,
                    embedding_vec,
                    {"content": knowledge.content, "tags": knowledge.tags},
                )
                # Record embedding in SQLite for tracking
                knowledge_service.record_embedding(
                    knowledge_id=knowledge.id,
                    provider=embedding_service.config.provider,
                    model=embedding_service.config.model,
                    dimension=len(embedding_vec),
                    vector_indexed=True,
                )
        except Exception as e:
            print(f"Warning: Failed to auto-embed knowledge {knowledge.id}: {e}")

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

    # Re-index embedding if content changed (best-effort)
    if data.content is not None and vector_manager and embedding_service:
        try:
            embedding_vec = await embedding_service.embed_knowledge(
                knowledge.content,
                metadata={"tags": knowledge.tags, "source": knowledge.source, "title": knowledge.title},
            )
            if embedding_vec is not None:
                # Remove old vector, add new one
                vector_manager.store.remove(knowledge.id)
                vector_manager.store.add(
                    knowledge.id,
                    embedding_vec,
                    {"content": knowledge.content, "tags": knowledge.tags},
                )
                knowledge_service.record_embedding(
                    knowledge_id=knowledge.id,
                    provider=embedding_service.config.provider,
                    model=embedding_service.config.model,
                    dimension=len(embedding_vec),
                    vector_indexed=True,
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

class SearchResultResponse(BaseModel):
    """A single search result with relevance score."""
    id: str
    title: str
    content: str
    tags: List[str]
    source: Optional[str]
    score: float
    created_at: str


class KnowledgeSearchResponse(BaseModel):
    """Response model for /api/knowledge/search."""
    results: List[SearchResultResponse]
    total: int
    query: str
    mode: str


class SearchResponse(BaseModel):
    """Legacy search response model (for /api/search)."""
    results: List[dict]
    total: int
    query: str


@app.get("/api/knowledge/search", response_model=KnowledgeSearchResponse)
async def search_knowledge_advanced(
    q: str = Query(..., min_length=1, description="Search query text"),
    mode: str = Query("text", pattern="^(text|semantic|hybrid)$", description="Search mode: text, semantic, or hybrid"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of results"),
    min_score: float = Query(0.0, ge=0.0, le=1.0, description="Minimum relevance score (0-1) for filtering results"),
):
    """Search knowledge entries with text, semantic, or hybrid mode.

    Modes:
    - **text**: Full-text search using SQLite FTS5 (with LIKE fallback).
      Fast, exact keyword matching. Results scored by rank position.
    - **semantic**: Vector similarity search using FAISS.
      Requires embedding service. Finds conceptually similar content
      even when exact keywords don't match.
    - **hybrid**: Combines text and semantic results. Runs both searches,
      normalizes scores to [0, 1], and merges with weighted combination
      (0.4 text + 0.6 semantic). Deduplicates by knowledge ID.

    Returns results sorted by descending relevance score.
    Falls back to text search if semantic service is unavailable.
    """
    if not knowledge_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    results_map: Dict[str, SearchResultResponse] = {}  # keyed by knowledge ID

    # --- Text search ---
    if mode in ("text", "hybrid"):
        text_entries = knowledge_service.search(q, limit=limit)
        for rank, entry in enumerate(text_entries):
            # Score by rank: top result = 1.0, decays linearly
            text_score = max(0.0, 1.0 - (rank / max(len(text_entries), 1)))
            results_map[entry.id] = SearchResultResponse(
                id=entry.id,
                title=entry.title,
                content=entry.content,
                tags=entry.tags,
                source=entry.source,
                score=text_score if mode == "text" else text_score * 0.4,
                created_at=entry.created_at.isoformat(),
            )

    # --- Semantic search ---
    if mode in ("semantic", "hybrid") and vector_manager and embedding_service:
        try:
            semantic_results = await vector_manager.search_knowledge(q, k=limit)

            if semantic_results:
                # Normalize semantic scores to [0, 1]
                max_sem_score = max(r.score for r in semantic_results) if semantic_results else 1.0
                min_sem_score = min(r.score for r in semantic_results) if len(semantic_results) > 1 else 0.0
                score_range = max_sem_score - min_sem_score if max_sem_score != min_sem_score else 1.0

                for r in semantic_results:
                    normalized_score = (r.score - min_sem_score) / score_range if score_range > 0 else r.score

                    if mode == "semantic":
                        # Pure semantic mode: use normalized score directly
                        # Fetch full knowledge entry for complete metadata
                        full_entry = knowledge_service.get(r.id)
                        if full_entry:
                            results_map[r.id] = SearchResultResponse(
                                id=r.id,
                                title=full_entry.title,
                                content=full_entry.content,
                                tags=full_entry.tags,
                                source=full_entry.source,
                                score=round(normalized_score, 4),
                                created_at=full_entry.created_at.isoformat(),
                            )
                    else:
                        # Hybrid mode: combine with text score
                        semantic_weighted = normalized_score * 0.6
                        if r.id in results_map:
                            # Already found by text search — add semantic weight
                            existing = results_map[r.id]
                            combined = existing.score + semantic_weighted
                            results_map[r.id] = existing.model_copy(update={"score": round(combined, 4)})
                        else:
                            # Only found by semantic search — use semantic score only
                            full_entry = knowledge_service.get(r.id)
                            if full_entry:
                                results_map[r.id] = SearchResultResponse(
                                    id=r.id,
                                    title=full_entry.title,
                                    content=full_entry.content,
                                    tags=full_entry.tags,
                                    source=full_entry.source,
                                    score=round(semantic_weighted, 4),
                                    created_at=full_entry.created_at.isoformat(),
                                )
        except Exception as e:
            print(f"Semantic search failed, falling back to text results: {e}")
            # If pure semantic mode failed and we have no results, try text fallback
            if mode == "semantic" and not results_map:
                text_entries = knowledge_service.search(q, limit=limit)
                for rank, entry in enumerate(text_entries):
                    text_score = max(0.0, 1.0 - (rank / max(len(text_entries), 1)))
                    results_map[entry.id] = SearchResultResponse(
                        id=entry.id,
                        title=entry.title,
                        content=entry.content,
                        tags=entry.tags,
                        source=entry.source,
                        score=text_score,
                        created_at=entry.created_at.isoformat(),
                    )

    # If semantic mode requested but no embedding service, fall back to text
    if mode == "semantic" and not results_map and (not vector_manager or not embedding_service):
        text_entries = knowledge_service.search(q, limit=limit)
        for rank, entry in enumerate(text_entries):
            text_score = max(0.0, 1.0 - (rank / max(len(text_entries), 1)))
            results_map[entry.id] = SearchResultResponse(
                id=entry.id,
                title=entry.title,
                content=entry.content,
                tags=entry.tags,
                source=entry.source,
                score=text_score,
                created_at=entry.created_at.isoformat(),
            )

    # Sort by score descending, apply min_score filter, limit
    sorted_results = sorted(results_map.values(), key=lambda r: r.score, reverse=True)
    filtered_results = [r for r in sorted_results if r.score >= min_score][:limit]

    return KnowledgeSearchResponse(
        results=filtered_results,
        total=len(filtered_results),
        query=q,
        mode=mode,
    )


@app.get("/api/search", response_model=SearchResponse)
async def search_knowledge_legacy(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, le=50),
    semantic: bool = Query(False),
):
    """Legacy search endpoint (use /api/knowledge/search for full features)."""
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
    if not knowledge_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
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

import time as _time

_startup_time: float = _time.time()


@app.get("/api/health")
async def health_check():
    """Health check endpoint.

    Returns service status including database connectivity, embedding
    service availability, vector store count, and uptime.
    Used by monitoring, load balancers, and frontend connection checks.
    """
    embedding_available = False
    if embedding_service:
        try:
            embedding_available = await embedding_service.is_available()
        except Exception:
            embedding_available = False

    uptime_seconds = round(_time.time() - _startup_time, 1) if _startup_time > 0 else 0

    return {
        "status": "healthy",
        "version": "0.1.0",
        "uptime_seconds": uptime_seconds,
        "services": {
            "database": knowledge_service is not None,
            "embedding": embedding_available,
            "vector_store": vector_manager is not None and vector_manager.store is not None,
        },
        "counts": {
            "knowledge": knowledge_service.count() if knowledge_service else 0,
            "vectors": vector_manager.store.count() if vector_manager else 0,
        },
    }


@app.get("/api/embedding/status")
async def embedding_status():
    """Get embedding service status and configuration.

    Returns provider info, availability, and dimension/model details.
    Useful for diagnostics and frontend config display.
    """
    if not embedding_service:
        return {"available": False, "reason": "Embedding service not configured"}

    available = await embedding_service.is_available(force_check=True)
    info = embedding_service.get_provider_info()
    info["available"] = available

    if knowledge_service:
        info["embedded_count"] = knowledge_service.embedding_count()
        info["unembedded_count"] = len(knowledge_service.list_unembedded(limit=1000))

    return info


@app.get("/api/stats")
async def get_stats():
    """Get database statistics."""
    if not knowledge_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return knowledge_service.get_stats()


# ============ Import / Export Endpoints ============

class ImportItem(BaseModel):
    """A single item in an import payload."""
    title: Optional[str] = ""
    content: str
    content_type: Optional[str] = "text"
    tags: Optional[List[str]] = []
    source: Optional[str] = None


class ImportResponse(BaseModel):
    """Response from import operation."""
    imported: int
    skipped: int
    errors: List[str]


class ExportData(BaseModel):
    """Full export payload."""
    knowledge: List[dict]
    relations: List[dict]
    exported_at: str
    stats: dict


@app.post("/api/import", response_model=ImportResponse, status_code=201)
async def import_knowledge(items: List[ImportItem]):
    """Import knowledge entries from a JSON array.

    Accepts a list of knowledge items and creates them in the database.
    Skips items with empty content. Returns count of imported, skipped,
    and any errors encountered.
    """
    if not knowledge_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    imported = 0
    skipped = 0
    errors: List[str] = []

    for i, item in enumerate(items):
        # Skip empty content
        if not item.content or not item.content.strip():
            skipped += 1
            continue

        try:
            knowledge = knowledge_service.create(
                content=item.content,
                title=item.title or "",
                content_type=item.content_type or "text",
                tags=item.tags or [],
                source=item.source,
            )

            # Auto-embed (best-effort, don't block import on embedding failures)
            if vector_manager and embedding_service:
                try:
                    embedding_vec = await embedding_service.embed_knowledge(
                        knowledge.content,
                        metadata={"tags": knowledge.tags, "source": knowledge.source, "title": knowledge.title},
                    )
                    if embedding_vec is not None:
                        vector_manager.store.add(
                            knowledge.id,
                            embedding_vec,
                            {"content": knowledge.content, "tags": knowledge.tags},
                        )
                        knowledge_service.record_embedding(
                            knowledge_id=knowledge.id,
                            provider=embedding_service.config.provider,
                            model=embedding_service.config.model,
                            dimension=len(embedding_vec),
                            vector_indexed=True,
                        )
                except Exception as e:
                    print(f"Warning: Failed to embed imported item {knowledge.id[:8]}: {e}")

            imported += 1
        except Exception as e:
            errors.append(f"Item {i}: {str(e)}")

    return ImportResponse(imported=imported, skipped=skipped, errors=errors)


@app.get("/api/export")
async def export_knowledge(
    format: str = Query("json", pattern="^(json|markdown)$", description="Export format: json or markdown"),
):
    """Export all knowledge entries and relations.

    Formats:
    - **json**: Complete JSON with knowledge entries, relations, and metadata.
    - **markdown**: Human-readable markdown document with all entries and relations.

    Returns the export data directly as JSON (for json format) or as a text
    response (for markdown format).
    """
    if not knowledge_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    from datetime import datetime as dt
    from fastapi.responses import PlainTextResponse

    # Collect all knowledge entries (paginated internally)
    all_entries = []
    offset = 0
    page_size = 100
    while True:
        batch = knowledge_service.list(limit=page_size, offset=offset)
        if not batch:
            break
        all_entries.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size

    # Collect all relations
    all_relations = knowledge_service.list_relations(limit=10000)

    now_str = dt.utcnow().isoformat()

    if format == "json":
        knowledge_data = [
            {
                "id": k.id,
                "title": k.title,
                "content": k.content,
                "content_type": k.content_type,
                "tags": k.tags,
                "source": k.source,
                "created_at": k.created_at.isoformat(),
                "updated_at": k.updated_at.isoformat(),
            }
            for k in all_entries
        ]
        relation_data = [
            {
                "id": r.id,
                "source_id": r.source_id,
                "target_id": r.target_id,
                "type": r.type,
                "weight": r.weight,
                "created_at": r.created_at.isoformat() if hasattr(r.created_at, "isoformat") else str(r.created_at),
            }
            for r in all_relations
        ]
        return {
            "knowledge": knowledge_data,
            "relations": relation_data,
            "exported_at": now_str,
            "stats": {
                "knowledge_count": len(knowledge_data),
                "relation_count": len(relation_data),
            },
        }

    elif format == "markdown":
        # Build markdown document
        lines = [
            "# KGKB Knowledge Export",
            "",
            f"Exported: {now_str}",
            f"Entries: {len(all_entries)} | Relations: {len(all_relations)}",
            "",
            "---",
            "",
        ]

        # Build relation lookup
        relations_by_node: Dict[str, list] = {}
        for r in all_relations:
            relations_by_node.setdefault(r.source_id, []).append(r)
            relations_by_node.setdefault(r.target_id, []).append(r)

        for entry in all_entries:
            title = entry.title or "(untitled)"
            lines.append(f"## {title}")
            lines.append("")
            lines.append(f"- **ID**: `{entry.id[:8]}`")
            lines.append(f"- **Type**: {entry.content_type}")
            if entry.tags:
                lines.append(f"- **Tags**: {', '.join(entry.tags)}")
            if entry.source:
                lines.append(f"- **Source**: {entry.source}")
            lines.append(f"- **Created**: {entry.created_at.isoformat()[:10]}")
            lines.append("")
            lines.append(entry.content)
            lines.append("")

            # Relations
            node_rels = relations_by_node.get(entry.id, [])
            if node_rels:
                lines.append("### Relations")
                lines.append("")
                for r in node_rels:
                    if r.source_id == entry.id:
                        lines.append(f"- → **{r.type}** → `{r.target_id[:8]}`")
                    else:
                        lines.append(f"- ← **{r.type}** ← `{r.source_id[:8]}`")
                lines.append("")

            lines.append("---")
            lines.append("")

        return PlainTextResponse(content="\n".join(lines), media_type="text/markdown")


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
