"""
KGKB Data Models - Pydantic models for API and storage
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class KnowledgeBase(BaseModel):
    """Base model for knowledge entries."""
    content: str = Field(..., min_length=1, max_length=10000)
    tags: List[str] = Field(default_factory=list)
    source: Optional[str] = None


class KnowledgeCreate(KnowledgeBase):
    """Model for creating a new knowledge entry."""
    pass


class KnowledgeUpdate(BaseModel):
    """Model for updating a knowledge entry."""
    content: Optional[str] = Field(None, min_length=1, max_length=10000)
    tags: Optional[List[str]] = None
    source: Optional[str] = None


class Knowledge(KnowledgeBase):
    """Full knowledge entry with metadata."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    embedding: Optional[List[float]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


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


class SearchResult(BaseModel):
    """Search result model."""
    id: str
    content: str
    tags: List[str]
    source: Optional[str]
    score: float
    created_at: datetime


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


class EmbeddingConfig(BaseModel):
    """Embedding configuration."""
    provider: str = "ollama"  # openai, ollama, local
    model: str = "nomic-embed-text"
    endpoint: str = "http://localhost:11434"
    dimension: int = 768
    api_key: Optional[str] = None


class ConfigModel(BaseModel):
    """Full KGKB configuration."""
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    database: dict = Field(default_factory=lambda: {"path": "~/.kgkb/kgkb.db"})
    vector: dict = Field(default_factory=lambda: {"backend": "faiss", "dimension": 768})
