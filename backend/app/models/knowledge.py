"""
KGKB Data Models - Pydantic models for API and storage
"""

from datetime import datetime
from typing import Optional, List
from uuid import uuid4
from pydantic import BaseModel, Field


# ============ Knowledge Models ============

class KnowledgeBase(BaseModel):
    """Base model for knowledge entries."""
    title: str = Field(default="", max_length=500, description="Short title for the knowledge entry")
    content: str = Field(..., min_length=1, max_length=50000)
    content_type: str = Field(default="text", description="Content type: text, url, markdown")
    tags: List[str] = Field(default_factory=list)
    source: Optional[str] = None


class KnowledgeCreate(KnowledgeBase):
    """Model for creating a new knowledge entry."""
    pass


class KnowledgeUpdate(BaseModel):
    """Model for updating a knowledge entry."""
    title: Optional[str] = Field(None, max_length=500)
    content: Optional[str] = Field(None, min_length=1, max_length=50000)
    content_type: Optional[str] = None
    tags: Optional[List[str]] = None
    source: Optional[str] = None


class Knowledge(KnowledgeBase):
    """Full knowledge entry with metadata."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


# ============ Relation Models ============

class RelationBase(BaseModel):
    """Base model for relationships."""
    source_id: str
    target_id: str
    type: str = "relates_to"
    weight: float = 1.0


class RelationCreate(RelationBase):
    """Model for creating a relationship."""
    pass


class Relation(RelationBase):
    """Full relationship with metadata."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


# ============ Search Models ============

class SearchResult(BaseModel):
    """Search result model."""
    id: str
    title: str
    content: str
    tags: List[str]
    source: Optional[str]
    score: float
    created_at: datetime


# ============ Graph Models ============

class GraphNode(BaseModel):
    """Graph node for visualization."""
    id: str
    label: str
    content: str
    tags: List[str]
    created_at: datetime


class GraphEdge(BaseModel):
    """Graph edge for visualization."""
    id: str
    source: str
    target: str
    type: str
    weight: float


class GraphData(BaseModel):
    """Full graph data for visualization."""
    nodes: List[GraphNode]
    edges: List[GraphEdge]


# ============ Embedding Models ============

class EmbeddingRecord(BaseModel):
    """Record of an embedding stored in the database."""
    id: str
    knowledge_id: str
    provider: str
    model: str
    dimension: int
    created_at: datetime


class EmbeddingConfig(BaseModel):
    """Embedding configuration."""
    provider: str = "ollama"  # openai, ollama, custom
    model: str = "qwen3-embedding:0.6b"
    endpoint: str = "http://localhost:11434"
    dimension: int = 1024
    api_key: Optional[str] = None


class ConfigModel(BaseModel):
    """Full KGKB configuration."""
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    database: dict = Field(default_factory=lambda: {"path": "~/.kgkb/data.db"})
    vector: dict = Field(default_factory=lambda: {"backend": "faiss", "dimension": 1024})
