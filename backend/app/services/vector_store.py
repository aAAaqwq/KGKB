"""
KGKB Vector Store - FAISS-based vector storage and search

Provides:
- Vector indexing with FAISS (IndexIDMap2 for proper add/remove)
- Semantic similarity search with cosine or L2 distance
- Persistence to disk (~/.kgkb/vectors.faiss + .meta sidecar)
- VectorStoreManager for coordinated embedding + indexing

Default dimension: 1024 (qwen3-embedding:0.6b)
Default index path: ~/.kgkb/vectors
"""

import hashlib
import logging
import pickle
import struct
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

logger = logging.getLogger("kgkb.vector_store")

# Default paths
DEFAULT_INDEX_PATH = Path.home() / ".kgkb" / "vectors"
DEFAULT_DIMENSION = 1024  # qwen3-embedding:0.6b output dimension


def _string_id_to_int64(string_id: str) -> int:
    """Convert a string UUID to a stable int64 for FAISS IDMap.

    Uses the first 8 bytes of SHA-256 hash, interpreted as a signed int64.
    Collision probability is negligible for reasonable dataset sizes.
    """
    digest = hashlib.sha256(string_id.encode()).digest()[:8]
    return struct.unpack("<q", digest)[0]


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

    Uses IndexIDMap2 wrapping a flat index so that vectors can be
    added and **removed** by numeric ID.  String knowledge IDs are
    mapped to deterministic int64 keys via SHA-256.

    Args:
        dimension: Embedding vector dimension (default 1024).
        index_path: Base path for persistence files (.faiss + .meta).
                    Defaults to ~/.kgkb/vectors.
        metric: Distance metric — "cosine" (default) or "l2".
        auto_save: If True, persist to disk after every mutation.
    """

    def __init__(
        self,
        dimension: int = DEFAULT_DIMENSION,
        index_path: Optional[Path] = None,
        metric: str = "cosine",
        auto_save: bool = False,
    ):
        if not FAISS_AVAILABLE:
            raise ImportError(
                "FAISS not installed. Run: pip install faiss-cpu"
            )

        self.dimension = dimension
        self.index_path = Path(index_path) if index_path else DEFAULT_INDEX_PATH
        self.metric = metric
        self.auto_save = auto_save

        # String ID ↔ int64 ID mapping
        self._str_to_int: Dict[str, int] = {}
        self._int_to_str: Dict[int, str] = {}

        # Metadata keyed by string ID
        self.metadata_store: Dict[str, Dict[str, Any]] = {}

        # Build FAISS index wrapped with IDMap2 for removal support
        self._index = self._create_index()

        # Load existing index from disk if present
        if self.index_path:
            faiss_file = self.index_path.with_suffix(".faiss")
            if faiss_file.exists():
                try:
                    self.load()
                except Exception as exc:
                    logger.warning("Could not load existing index at %s: %s", faiss_file, exc)

    # ------------------------------------------------------------------ #
    #  Index creation
    # ------------------------------------------------------------------ #

    def _create_index(self) -> "faiss.IndexIDMap2":
        """Create a fresh IndexIDMap2 wrapping a flat base index."""
        if self.metric == "cosine":
            base = faiss.IndexFlatIP(self.dimension)
        else:
            base = faiss.IndexFlatL2(self.dimension)
        return faiss.IndexIDMap2(base)

    # ------------------------------------------------------------------ #
    #  Normalization
    # ------------------------------------------------------------------ #

    @staticmethod
    def _normalize(vectors: np.ndarray) -> np.ndarray:
        """L2-normalize vectors (required for cosine via inner-product)."""
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        return vectors / norms

    # ------------------------------------------------------------------ #
    #  Add vectors
    # ------------------------------------------------------------------ #

    def add(
        self,
        id: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a single vector to the index.

        If the ID already exists, the old vector is replaced (remove + add).
        """
        # Replace if exists
        if id in self._str_to_int:
            self._remove_internal(id)

        vector = np.array([embedding], dtype=np.float32)
        if self.metric == "cosine":
            vector = self._normalize(vector)

        int_id = _string_id_to_int64(id)
        ids = np.array([int_id], dtype=np.int64)

        self._index.add_with_ids(vector, ids)

        # Update maps
        self._str_to_int[id] = int_id
        self._int_to_str[int_id] = id
        if metadata:
            self.metadata_store[id] = metadata

        if self.auto_save:
            self.save()

    # Alias used by main.py's create endpoint
    add_vector = add

    def add_batch(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        metadata_list: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Add multiple vectors at once.

        Existing IDs are replaced.
        """
        if not ids:
            return

        # Remove any that already exist
        for sid in ids:
            if sid in self._str_to_int:
                self._remove_internal(sid)

        vectors = np.array(embeddings, dtype=np.float32)
        if self.metric == "cosine":
            vectors = self._normalize(vectors)

        int_ids = np.array(
            [_string_id_to_int64(sid) for sid in ids], dtype=np.int64
        )
        self._index.add_with_ids(vectors, int_ids)

        for i, sid in enumerate(ids):
            iid = int(int_ids[i])
            self._str_to_int[sid] = iid
            self._int_to_str[iid] = sid
            if metadata_list and i < len(metadata_list) and metadata_list[i]:
                self.metadata_store[sid] = metadata_list[i]

        if self.auto_save:
            self.save()

    # ------------------------------------------------------------------ #
    #  Search
    # ------------------------------------------------------------------ #

    def search(
        self,
        query_embedding: List[float],
        k: int = 10,
        min_score: float = 0.0,
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """Search for the k most similar vectors.

        Returns list of (string_id, score, metadata) tuples sorted by
        descending similarity (cosine) or ascending distance (L2).
        """
        if self._index.ntotal == 0:
            return []

        query = np.array([query_embedding], dtype=np.float32)
        if self.metric == "cosine":
            query = self._normalize(query)

        effective_k = min(k, self._index.ntotal)
        scores, int_ids = self._index.search(query, effective_k)

        results: List[Tuple[str, float, Dict[str, Any]]] = []
        for score, iid in zip(scores[0], int_ids[0]):
            if iid < 0:
                continue  # FAISS sentinel for "not enough results"

            sid = self._int_to_str.get(int(iid))
            if sid is None:
                continue  # stale entry (shouldn't happen with IDMap2)

            if score < min_score:
                continue

            metadata = self.metadata_store.get(sid, {})
            results.append((sid, float(score), metadata))

        return results

    # Alias expected by VectorStoreManager
    search_similar = search

    # ------------------------------------------------------------------ #
    #  Remove
    # ------------------------------------------------------------------ #

    def _remove_internal(self, id: str) -> bool:
        """Remove a vector without auto-saving (internal helper)."""
        iid = self._str_to_int.get(id)
        if iid is None:
            return False

        # Remove from FAISS via IDMap2
        id_selector = faiss.IDSelectorArray(
            1, faiss.swig_ptr(np.array([iid], dtype=np.int64))
        )
        self._index.remove_ids(id_selector)

        # Clean up maps
        del self._str_to_int[id]
        self._int_to_str.pop(iid, None)
        self.metadata_store.pop(id, None)

        return True

    def remove(self, id: str) -> bool:
        """Remove a vector from the index by string ID.

        Returns True if the vector was found and removed, False otherwise.
        """
        removed = self._remove_internal(id)
        if removed and self.auto_save:
            self.save()
        return removed

    # Alias used by main.py's delete endpoint
    delete_vector = remove

    def remove_batch(self, ids: List[str]) -> int:
        """Remove multiple vectors. Returns count of actually removed."""
        removed = 0
        for sid in ids:
            if self._remove_internal(sid):
                removed += 1
        if removed > 0 and self.auto_save:
            self.save()
        return removed

    # ------------------------------------------------------------------ #
    #  Rebuild / compact
    # ------------------------------------------------------------------ #

    def rebuild(self) -> None:
        """Rebuild the FAISS index from scratch.

        Useful if many vectors were removed and you want to reclaim memory
        and ensure optimal search performance.
        """
        if self._index.ntotal == 0:
            self._index = self._create_index()
            return

        # Reconstruct all vectors currently in the index
        all_int_ids = []
        all_vectors = []

        for sid, iid in self._str_to_int.items():
            try:
                vec = self._index.reconstruct(iid)
                all_int_ids.append(iid)
                all_vectors.append(vec)
            except RuntimeError:
                logger.warning("Could not reconstruct vector for %s — skipping", sid)
                # Clean up dangling reference
                self._int_to_str.pop(iid, None)

        # Create fresh index and re-add
        self._index = self._create_index()

        if all_vectors:
            vectors = np.array(all_vectors, dtype=np.float32)
            ids_arr = np.array(all_int_ids, dtype=np.int64)
            self._index.add_with_ids(vectors, ids_arr)

        logger.info("Rebuilt index with %d vectors", self._index.ntotal)

    # ------------------------------------------------------------------ #
    #  Persistence
    # ------------------------------------------------------------------ #

    def save(self, path: Optional[Path] = None) -> None:
        """Save FAISS index + metadata to disk.

        Files written:
            <path>.faiss  — binary FAISS index
            <path>.meta   — pickle sidecar (ID maps + metadata)
        """
        path = Path(path) if path else self.index_path
        if not path:
            raise ValueError("No path specified for saving")

        path.parent.mkdir(parents=True, exist_ok=True)

        faiss.write_index(self._index, str(path.with_suffix(".faiss")))

        sidecar = {
            "str_to_int": self._str_to_int,
            "int_to_str": self._int_to_str,
            "metadata_store": self.metadata_store,
            "dimension": self.dimension,
            "metric": self.metric,
        }
        with open(path.with_suffix(".meta"), "wb") as f:
            pickle.dump(sidecar, f, protocol=pickle.HIGHEST_PROTOCOL)

        logger.debug("Saved vector store (%d vectors) to %s", self._index.ntotal, path)

    def load(self, path: Optional[Path] = None) -> None:
        """Load FAISS index + metadata from disk.

        Silently skips if the files don't exist.
        """
        path = Path(path) if path else self.index_path
        if not path:
            raise ValueError("No path specified for loading")

        faiss_file = path.with_suffix(".faiss")
        meta_file = path.with_suffix(".meta")

        if faiss_file.exists():
            self._index = faiss.read_index(str(faiss_file))
        else:
            logger.debug("No FAISS index file at %s — starting empty", faiss_file)
            return

        if meta_file.exists():
            with open(meta_file, "rb") as f:
                sidecar = pickle.load(f)
            self._str_to_int = sidecar.get("str_to_int", {})
            self._int_to_str = sidecar.get("int_to_str", {})
            self.metadata_store = sidecar.get("metadata_store", {})
            self.dimension = sidecar.get("dimension", self.dimension)
            self.metric = sidecar.get("metric", self.metric)

            # Backwards compatibility: migrate old id_map format
            if not self._str_to_int and "id_map" in sidecar:
                old_map = sidecar["id_map"]  # {faiss_idx: str_id}
                logger.info("Migrating legacy id_map (%d entries)", len(old_map))
                for _faiss_idx, sid in old_map.items():
                    iid = _string_id_to_int64(sid)
                    self._str_to_int[sid] = iid
                    self._int_to_str[iid] = sid
                # Rebuild index with new int64 IDs
                self.rebuild()
        else:
            logger.warning("FAISS index found but no .meta sidecar — index has no ID mapping")

        logger.info(
            "Loaded vector store: %d vectors, %d mapped IDs",
            self._index.ntotal,
            len(self._str_to_int),
        )

    # ------------------------------------------------------------------ #
    #  Utilities
    # ------------------------------------------------------------------ #

    def count(self) -> int:
        """Return number of vectors in the index."""
        return len(self._str_to_int)

    def has(self, id: str) -> bool:
        """Check if a vector exists for the given string ID."""
        return id in self._str_to_int

    def clear(self) -> None:
        """Remove all vectors and metadata."""
        self._index = self._create_index()
        self._str_to_int.clear()
        self._int_to_str.clear()
        self.metadata_store.clear()

        if self.auto_save:
            self.save()

    def get_ids(self) -> List[str]:
        """Return all stored string IDs."""
        return list(self._str_to_int.keys())

    def get_stats(self) -> Dict[str, Any]:
        """Return index statistics."""
        return {
            "total_vectors": self._index.ntotal,
            "mapped_ids": len(self._str_to_int),
            "dimension": self.dimension,
            "metric": self.metric,
            "index_path": str(self.index_path) if self.index_path else None,
            "has_metadata": len(self.metadata_store),
        }


class VectorStoreManager:
    """
    High-level manager that coordinates embedding generation and vector storage.

    Typical usage:
        manager = VectorStoreManager(store, embedding_service)
        await manager.index_knowledge(id, content, metadata)
        results = await manager.search_knowledge("query text")
    """

    def __init__(
        self,
        store: FAISSVectorStore,
        embedding_service,  # EmbeddingService (import avoided for circular dep)
    ):
        self.store = store
        self.embedding_service = embedding_service

    async def index_knowledge(
        self,
        id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Generate embedding and add to vector store.

        Returns True if the vector was successfully indexed, False if the
        embedding service was unavailable or returned an error.
        """
        embedding = await self.embedding_service.embed_knowledge(content, metadata)
        if embedding is None:
            logger.warning("Embedding unavailable for knowledge %s — skipping indexing", id)
            return False

        self.store.add(id, embedding, metadata)
        return True

    async def search_knowledge(
        self,
        query: str,
        k: int = 10,
        min_score: float = 0.0,
    ) -> List[SearchResult]:
        """Search for knowledge using semantic similarity.

        Embeds the query, searches the vector store, and returns
        SearchResult objects sorted by descending relevance.

        Returns an empty list if the embedding service is unavailable.
        """
        result = await self.embedding_service.embed(query)
        if result is None:
            logger.warning("Cannot perform semantic search — embedding service unavailable")
            return []

        matches = self.store.search(result.embedding, k=k, min_score=min_score)

        return [
            SearchResult(
                id=kid,
                score=score,
                content=meta.get("content", ""),
                metadata=meta,
            )
            for kid, score, meta in matches
        ]

    async def reindex_all(
        self,
        knowledge_entries: List[Any],
        batch_size: int = 10,
    ) -> int:
        """Re-embed and re-index a list of knowledge entries.

        Useful after changing embedding provider/model.
        Returns count of successfully indexed entries.
        """
        indexed = 0
        for i in range(0, len(knowledge_entries), batch_size):
            batch = knowledge_entries[i : i + batch_size]
            texts = [entry.content for entry in batch]

            results = await self.embedding_service.embed_batch(texts)
            for entry, emb_result in zip(batch, results):
                if emb_result is not None:
                    meta = {
                        "content": entry.content,
                        "tags": getattr(entry, "tags", []),
                        "title": getattr(entry, "title", ""),
                    }
                    self.store.add(entry.id, emb_result.embedding, meta)
                    indexed += 1

        return indexed

    def save(self) -> None:
        """Persist vector store to disk."""
        self.store.save()

    def load(self) -> None:
        """Load vector store from disk."""
        self.store.load()
