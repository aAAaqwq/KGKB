"""
KGKB Vector Store - FAISS-based vector storage and search

Provides:
- Vector indexing with FAISS
- Semantic similarity search
- Persistence to disk
"""

import json
import pickle
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass

import numpy as np

# FAISS import with fallback
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False


@dataclass
class SearchResult:
    """Vector search result."""
    id: str
    score: float
    content: str
    metadata: Dict[str, Any]


class FAISSVectorStore:
    """
    FAISS-based vector store for semantic search.

    Stores embeddings and provides fast similarity search.
    """

    def __init__(
        self,
        dimension: int = 768,
        index_path: Optional[Path] = None,
        metric: str = "cosine",  # cosine or l2
    ):
        if not FAISS_AVAILABLE:
            raise ImportError("FAISS not installed. Run: pip install faiss-cpu")

        self.dimension = dimension
        self.index_path = index_path
        self.metric = metric

        # Mapping from FAISS index to knowledge IDs
        self.id_map: Dict[int, str] = {}
        self.metadata_store: Dict[str, Dict[str, Any]] = {}

        # Initialize FAISS index
        if metric == "cosine":
            # For cosine similarity, we normalize vectors
            self.index = faiss.IndexFlatIP(dimension)  # Inner product for normalized vectors
        else:
            self.index = faiss.IndexFlatL2(dimension)

        # Load existing index if path provided
        if index_path and index_path.exists():
            self.load()

    def _normalize(self, vectors: np.ndarray) -> np.ndarray:
        """Normalize vectors for cosine similarity."""
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1  # Avoid division by zero
        return vectors / norms

    def add(
        self,
        id: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a single vector to the index."""
        vector = np.array([embedding], dtype=np.float32)

        if self.metric == "cosine":
            vector = self._normalize(vector)

        # Add to FAISS index
        idx = self.index.ntotal
        self.index.add(vector)

        # Store mapping
        self.id_map[idx] = id
        if metadata:
            self.metadata_store[id] = metadata

    def add_batch(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Add multiple vectors to the index."""
        vectors = np.array(embeddings, dtype=np.float32)

        if self.metric == "cosine":
            vectors = self._normalize(vectors)

        start_idx = self.index.ntotal
        self.index.add(vectors)

        # Store mappings
        for i, kid in enumerate(ids):
            self.id_map[start_idx + i] = kid
            if metadata and i < len(metadata):
                self.metadata_store[kid] = metadata[i]

    def search(
        self,
        query_embedding: List[float],
        k: int = 10,
        min_score: float = 0.0,
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """
        Search for similar vectors.

        Returns list of (id, score, metadata) tuples.
        """
        query = np.array([query_embedding], dtype=np.float32)

        if self.metric == "cosine":
            query = self._normalize(query)

        # Search
        k = min(k, self.index.ntotal)
        if k == 0:
            return []

        scores, indices = self.index.search(query, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:  # FAISS returns -1 for not enough results
                continue

            kid = self.id_map.get(idx)
            if kid and score >= min_score:
                metadata = self.metadata_store.get(kid, {})
                results.append((kid, float(score), metadata))

        return results

    def remove(self, id: str) -> bool:
        """
        Remove a vector from the index.

        Note: FAISS doesn't support direct removal, so we mark it as removed.
        For full removal, need to rebuild the index.
        """
        # Find index
        idx = None
        for i, kid in self.id_map.items():
            if kid == id:
                idx = i
                break

        if idx is None:
            return False

        # Remove from mappings
        del self.id_map[idx]
        if id in self.metadata_store:
            del self.metadata_store[id]

        # Note: FAISS index still contains the vector
        # For production, consider rebuild() or use IndexIDMap
        return True

    def save(self, path: Optional[Path] = None) -> None:
        """Save index and metadata to disk."""
        path = path or self.index_path
        if not path:
            raise ValueError("No path specified for saving")

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Save FAISS index
        faiss.write_index(self.index, str(path.with_suffix(".faiss")))

        # Save metadata
        metadata = {
            "id_map": self.id_map,
            "metadata_store": self.metadata_store,
            "dimension": self.dimension,
            "metric": self.metric,
        }
        with open(path.with_suffix(".meta"), "wb") as f:
            pickle.dump(metadata, f)

    def load(self, path: Optional[Path] = None) -> None:
        """Load index and metadata from disk."""
        path = path or self.index_path
        if not path:
            raise ValueError("No path specified for loading")

        path = Path(path)

        # Load FAISS index
        index_file = path.with_suffix(".faiss")
        if index_file.exists():
            self.index = faiss.read_index(str(index_file))

        # Load metadata
        meta_file = path.with_suffix(".meta")
        if meta_file.exists():
            with open(meta_file, "rb") as f:
                metadata = pickle.load(f)
            self.id_map = metadata.get("id_map", {})
            self.metadata_store = metadata.get("metadata_store", {})
            self.dimension = metadata.get("dimension", self.dimension)
            self.metric = metadata.get("metric", self.metric)

    def count(self) -> int:
        """Return number of vectors in the index."""
        return len(self.id_map)

    def clear(self) -> None:
        """Clear all vectors from the index."""
        if self.metric == "cosine":
            self.index = faiss.IndexFlatIP(self.dimension)
        else:
            self.index = faiss.IndexFlatL2(self.dimension)
        self.id_map.clear()
        self.metadata_store.clear()


class VectorStoreManager:
    """
    Manager for vector store operations.
    Handles embedding generation and storage.
    """

    def __init__(
        self,
        store: FAISSVectorStore,
        embedding_service,  # EmbeddingService type
    ):
        self.store = store
        self.embedding_service = embedding_service

    async def index_knowledge(
        self,
        id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Generate embedding and add to vector store."""
        embedding = await self.embedding_service.embed_knowledge(content, metadata)
        self.store.add(id, embedding, metadata)

    async def search_knowledge(
        self,
        query: str,
        k: int = 10,
        min_score: float = 0.5,
    ) -> List[SearchResult]:
        """Search for knowledge using semantic similarity."""
        # Generate query embedding
        result = await self.embedding_service.embed(query)

        # Search vector store
        matches = self.store.search(result.embedding, k=k, min_score=min_score)

        # Convert to SearchResult objects
        results = []
        for kid, score, metadata in matches:
            results.append(SearchResult(
                id=kid,
                score=score,
                content=metadata.get("content", ""),
                metadata=metadata,
            ))

        return results

    def save(self) -> None:
        """Save vector store to disk."""
        self.store.save()

    def load(self) -> None:
        """Load vector store from disk."""
        self.store.load()
