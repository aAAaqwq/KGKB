"""
KGKB Knowledge Service - Core business logic for knowledge management

Handles:
- CRUD operations for knowledge entries
- Relationship management between knowledge nodes
- Graph traversal for visualization
- Text search with SQLite FTS5
- Schema migration and versioning

Storage: SQLite at ~/.kgkb/data.db (configurable)
Connection pooling: thread-local connections for safe concurrent access
"""

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from uuid import uuid4
from dataclasses import dataclass, field


# Current schema version — bump when schema changes
SCHEMA_VERSION = 2


@dataclass
class KnowledgeEntry:
    """Knowledge entry data class."""
    id: str
    title: str
    content: str
    content_type: str
    tags: List[str]
    source: Optional[str]
    created_at: datetime
    updated_at: datetime


@dataclass
class RelationEntry:
    """Relation entry data class."""
    id: str
    source_id: str
    target_id: str
    type: str
    weight: float
    created_at: datetime


@dataclass
class EmbeddingEntry:
    """Embedding metadata entry data class."""
    id: str
    knowledge_id: str
    provider: str
    model: str
    dimension: int
    vector_indexed: bool
    created_at: datetime


class ConnectionPool:
    """
    Thread-local SQLite connection pool.

    Each thread gets its own connection, reused for the thread's lifetime.
    Connections are configured with WAL mode for better concurrent read perf.
    """

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._local = threading.local()
        self._lock = threading.Lock()

    def get(self) -> sqlite3.Connection:
        """Get a connection for the current thread."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrent reads
            conn.execute("PRAGMA journal_mode=WAL")
            # Enable foreign key enforcement
            conn.execute("PRAGMA foreign_keys=ON")
            # Reasonable busy timeout (5s)
            conn.execute("PRAGMA busy_timeout=5000")
            self._local.conn = conn
        return conn

    def close_all(self):
        """Close the connection on the current thread."""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            self._local.conn = None


class KnowledgeService:
    """
    Core service for knowledge management.

    Uses SQLite for persistence with thread-local connection pooling.
    Supports schema migrations for forward compatibility.
    Default DB path: ~/.kgkb/data.db
    """

    DEFAULT_DB_PATH = Path.home() / ".kgkb" / "data.db"

    def __init__(self, db_path: Path = None):
        self.db_path = Path(db_path) if db_path else self.DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._pool = ConnectionPool(str(self.db_path))
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection from the pool."""
        return self._pool.get()

    # ============ Schema & Migrations ============

    def _init_db(self):
        """Initialize database tables and run migrations."""
        conn = self._get_conn()

        # Create schema_version table if not exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL,
                description TEXT
            )
        """)
        conn.commit()

        current_version = self._get_schema_version(conn)

        if current_version < 1:
            self._migrate_v1(conn)
        if current_version < 2:
            self._migrate_v2(conn)

    def _get_schema_version(self, conn: sqlite3.Connection) -> int:
        """Get the current schema version."""
        try:
            cursor = conn.execute("SELECT MAX(version) FROM schema_version")
            row = cursor.fetchone()
            return row[0] if row[0] is not None else 0
        except sqlite3.OperationalError:
            return 0

    def _migrate_v1(self, conn: sqlite3.Connection):
        """
        Migration v1: Initial schema.

        Tables: knowledge, relations, embeddings, indexes.
        """
        conn.executescript("""
            -- Knowledge nodes table
            CREATE TABLE IF NOT EXISTS knowledge (
                id TEXT PRIMARY KEY,
                title TEXT DEFAULT '',
                content TEXT NOT NULL,
                content_type TEXT DEFAULT 'text',
                tags TEXT DEFAULT '[]',
                source TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            -- Relations table (edges between knowledge nodes)
            CREATE TABLE IF NOT EXISTS relations (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                type TEXT DEFAULT 'relates_to',
                weight REAL DEFAULT 1.0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (source_id) REFERENCES knowledge(id) ON DELETE CASCADE,
                FOREIGN KEY (target_id) REFERENCES knowledge(id) ON DELETE CASCADE
            );

            -- Embeddings metadata table (tracks which entries have embeddings)
            CREATE TABLE IF NOT EXISTS embeddings (
                id TEXT PRIMARY KEY,
                knowledge_id TEXT NOT NULL UNIQUE,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                dimension INTEGER NOT NULL,
                vector_indexed INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (knowledge_id) REFERENCES knowledge(id) ON DELETE CASCADE
            );

            -- Indexes for performance
            CREATE INDEX IF NOT EXISTS idx_knowledge_created ON knowledge(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_knowledge_content_type ON knowledge(content_type);
            CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_id);
            CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_id);
            CREATE INDEX IF NOT EXISTS idx_relations_type ON relations(type);
            CREATE INDEX IF NOT EXISTS idx_embeddings_knowledge ON embeddings(knowledge_id);
        """)

        # Record migration
        conn.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (1, datetime.utcnow().isoformat(), "Initial schema: knowledge, relations, embeddings"),
        )
        conn.commit()

    def _migrate_v2(self, conn: sqlite3.Connection):
        """
        Migration v2: Add FTS5 virtual table for full-text search.
        """
        # Check if FTS5 is available
        try:
            conn.executescript("""
                -- FTS5 virtual table for fast text search
                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
                    title,
                    content,
                    tags,
                    content=knowledge,
                    content_rowid=rowid
                );

                -- Triggers to keep FTS in sync
                CREATE TRIGGER IF NOT EXISTS knowledge_ai AFTER INSERT ON knowledge BEGIN
                    INSERT INTO knowledge_fts(rowid, title, content, tags)
                    VALUES (new.rowid, new.title, new.content, new.tags);
                END;

                CREATE TRIGGER IF NOT EXISTS knowledge_ad AFTER DELETE ON knowledge BEGIN
                    INSERT INTO knowledge_fts(knowledge_fts, rowid, title, content, tags)
                    VALUES ('delete', old.rowid, old.title, old.content, old.tags);
                END;

                CREATE TRIGGER IF NOT EXISTS knowledge_au AFTER UPDATE ON knowledge BEGIN
                    INSERT INTO knowledge_fts(knowledge_fts, rowid, title, content, tags)
                    VALUES ('delete', old.rowid, old.title, old.content, old.tags);
                    INSERT INTO knowledge_fts(rowid, title, content, tags)
                    VALUES (new.rowid, new.title, new.content, new.tags);
                END;
            """)
        except sqlite3.OperationalError:
            # FTS5 not available — fall back to LIKE-based search (already supported)
            pass

        # Ensure title and content_type columns exist (for DBs migrated from older versions)
        try:
            conn.execute("SELECT title FROM knowledge LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute("ALTER TABLE knowledge ADD COLUMN title TEXT DEFAULT ''")

        try:
            conn.execute("SELECT content_type FROM knowledge LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute("ALTER TABLE knowledge ADD COLUMN content_type TEXT DEFAULT 'text'")

        conn.execute(
            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
            (2, datetime.utcnow().isoformat(), "FTS5 full-text search, title/content_type columns"),
        )
        conn.commit()

    # ============ Knowledge CRUD ============

    def create(
        self,
        content: str,
        title: str = "",
        content_type: str = "text",
        tags: List[str] = None,
        source: str = None,
    ) -> KnowledgeEntry:
        """Create a new knowledge entry."""
        conn = self._get_conn()

        now = datetime.utcnow().isoformat()
        kid = str(uuid4())
        tags_json = json.dumps(tags or [])

        # Auto-generate title from content if not provided
        if not title:
            title = content[:80].split("\n")[0].strip()
            if len(content) > 80:
                title += "..."

        conn.execute(
            """
            INSERT INTO knowledge (id, title, content, content_type, tags, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (kid, title, content, content_type, tags_json, source, now, now),
        )
        conn.commit()

        return KnowledgeEntry(
            id=kid,
            title=title,
            content=content,
            content_type=content_type,
            tags=tags or [],
            source=source,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
        )

    def get(self, kid: str) -> Optional[KnowledgeEntry]:
        """Get a knowledge entry by ID (supports partial ID matching)."""
        conn = self._get_conn()

        if len(kid) < 36:
            cursor = conn.execute("SELECT * FROM knowledge WHERE id LIKE ?", (f"{kid}%",))
        else:
            cursor = conn.execute("SELECT * FROM knowledge WHERE id = ?", (kid,))

        row = cursor.fetchone()
        if not row:
            return None

        return self._row_to_entry(row)

    def list(
        self,
        tag: str = None,
        content_type: str = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[KnowledgeEntry]:
        """List knowledge entries with optional filters."""
        conn = self._get_conn()

        conditions = []
        params: list = []

        if tag:
            conditions.append("tags LIKE ?")
            params.append(f'%"{tag}"%')

        if content_type:
            conditions.append("content_type = ?")
            params.append(content_type)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"""
            SELECT * FROM knowledge
            {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

        return [self._row_to_entry(row) for row in rows]

    def update(
        self,
        kid: str,
        title: str = None,
        content: str = None,
        content_type: str = None,
        tags: List[str] = None,
        source: str = None,
    ) -> Optional[KnowledgeEntry]:
        """Update a knowledge entry. Only non-None fields are updated."""
        conn = self._get_conn()

        # Resolve full ID
        if len(kid) < 36:
            cursor = conn.execute("SELECT * FROM knowledge WHERE id LIKE ?", (f"{kid}%",))
        else:
            cursor = conn.execute("SELECT * FROM knowledge WHERE id = ?", (kid,))

        row = cursor.fetchone()
        if not row:
            return None

        kid = row["id"]
        now = datetime.utcnow().isoformat()

        # Build SET clause dynamically
        updates = {"updated_at": now}
        if title is not None:
            updates["title"] = title
        if content is not None:
            updates["content"] = content
        if content_type is not None:
            updates["content_type"] = content_type
        if tags is not None:
            updates["tags"] = json.dumps(tags)
        if source is not None:
            updates["source"] = source

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [kid]

        conn.execute(f"UPDATE knowledge SET {set_clause} WHERE id = ?", values)
        conn.commit()

        return self.get(kid)

    def delete(self, kid: str) -> bool:
        """Delete a knowledge entry and its relations/embeddings (cascading)."""
        conn = self._get_conn()

        # Resolve full ID if partial
        if len(kid) < 36:
            cursor = conn.execute("SELECT id FROM knowledge WHERE id LIKE ?", (f"{kid}%",))
            row = cursor.fetchone()
            if not row:
                return False
            kid = row["id"]

        # Delete relations first (in case FK cascade isn't working)
        conn.execute("DELETE FROM relations WHERE source_id = ? OR target_id = ?", (kid, kid))
        # Delete embedding metadata
        conn.execute("DELETE FROM embeddings WHERE knowledge_id = ?", (kid,))
        # Delete knowledge
        conn.execute("DELETE FROM knowledge WHERE id = ?", (kid,))

        deleted = conn.total_changes > 0
        conn.commit()
        return deleted

    def count(self, tag: str = None) -> int:
        """Count total knowledge entries, optionally filtered by tag."""
        conn = self._get_conn()
        if tag:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM knowledge WHERE tags LIKE ?",
                (f'%"{tag}"%',),
            )
        else:
            cursor = conn.execute("SELECT COUNT(*) FROM knowledge")
        return cursor.fetchone()[0]

    def get_all_tags(self) -> List[str]:
        """Get all unique tags across all knowledge entries."""
        conn = self._get_conn()
        cursor = conn.execute("SELECT tags FROM knowledge")
        tag_set: set = set()
        for row in cursor.fetchall():
            tags = json.loads(row["tags"]) if row["tags"] else []
            tag_set.update(tags)
        return sorted(tag_set)

    # ============ Text Search ============

    def search(self, query: str, limit: int = 10) -> List[KnowledgeEntry]:
        """
        Full-text search using FTS5 (with LIKE fallback).

        Returns knowledge entries matching the query, ordered by relevance.
        """
        conn = self._get_conn()

        # Try FTS5 first
        try:
            cursor = conn.execute(
                """
                SELECT k.* FROM knowledge k
                JOIN knowledge_fts fts ON k.rowid = fts.rowid
                WHERE knowledge_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit),
            )
            rows = cursor.fetchall()
            if rows:
                return [self._row_to_entry(row) for row in rows]
        except sqlite3.OperationalError:
            pass  # FTS5 not available, fall back to LIKE

        # LIKE fallback
        search_term = f"%{query}%"
        cursor = conn.execute(
            """
            SELECT * FROM knowledge
            WHERE title LIKE ? OR content LIKE ? OR tags LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (search_term, search_term, search_term, limit),
        )
        return [self._row_to_entry(row) for row in cursor.fetchall()]

    # ============ Embeddings Tracking ============

    def record_embedding(
        self,
        knowledge_id: str,
        provider: str,
        model: str,
        dimension: int,
        vector_indexed: bool = False,
    ) -> EmbeddingEntry:
        """Record that a knowledge entry has been embedded."""
        conn = self._get_conn()

        eid = str(uuid4())
        now = datetime.utcnow().isoformat()

        # Upsert: replace if exists for this knowledge_id
        conn.execute(
            """
            INSERT OR REPLACE INTO embeddings
                (id, knowledge_id, provider, model, dimension, vector_indexed, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (eid, knowledge_id, provider, model, dimension, int(vector_indexed), now),
        )
        conn.commit()

        return EmbeddingEntry(
            id=eid,
            knowledge_id=knowledge_id,
            provider=provider,
            model=model,
            dimension=dimension,
            vector_indexed=vector_indexed,
            created_at=datetime.fromisoformat(now),
        )

    def get_embedding_status(self, knowledge_id: str) -> Optional[EmbeddingEntry]:
        """Get embedding status for a knowledge entry."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM embeddings WHERE knowledge_id = ?", (knowledge_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None

        return EmbeddingEntry(
            id=row["id"],
            knowledge_id=row["knowledge_id"],
            provider=row["provider"],
            model=row["model"],
            dimension=row["dimension"],
            vector_indexed=bool(row["vector_indexed"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def list_unembedded(self, limit: int = 100) -> List[KnowledgeEntry]:
        """List knowledge entries that don't have embeddings yet."""
        conn = self._get_conn()
        cursor = conn.execute(
            """
            SELECT k.* FROM knowledge k
            LEFT JOIN embeddings e ON k.id = e.knowledge_id
            WHERE e.id IS NULL
            ORDER BY k.created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [self._row_to_entry(row) for row in cursor.fetchall()]

    def embedding_count(self) -> int:
        """Count knowledge entries with embeddings."""
        conn = self._get_conn()
        cursor = conn.execute("SELECT COUNT(*) FROM embeddings")
        return cursor.fetchone()[0]

    # ============ Relations ============

    def create_relation(
        self,
        source_id: str,
        target_id: str,
        type: str = "relates_to",
        weight: float = 1.0,
    ) -> RelationEntry:
        """
        Create a relationship between two knowledge entries.

        Raises:
            ValueError: If source_id == target_id (self-relation).
            KeyError: If source or target node does not exist.
            FileExistsError: If an identical relation already exists.
            RuntimeError: On database integrity errors.
        """
        conn = self._get_conn()

        # Resolve partial IDs
        resolved_source = self._resolve_id(conn, source_id)
        resolved_target = self._resolve_id(conn, target_id)

        if not resolved_source:
            raise KeyError(f"Source node not found: {source_id}")
        if not resolved_target:
            raise KeyError(f"Target node not found: {target_id}")

        if resolved_source == resolved_target:
            raise ValueError("Cannot create a self-relation (source == target)")

        # Check for duplicate relation (same source, target, and type)
        cursor = conn.execute(
            "SELECT id FROM relations WHERE source_id = ? AND target_id = ? AND type = ?",
            (resolved_source, resolved_target, type),
        )
        if cursor.fetchone():
            raise FileExistsError(
                f"Relation already exists: {resolved_source[:8]}… → {resolved_target[:8]}… ({type})"
            )

        rid = str(uuid4())
        now = datetime.utcnow().isoformat()

        try:
            conn.execute(
                """
                INSERT INTO relations (id, source_id, target_id, type, weight, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (rid, resolved_source, resolved_target, type, weight, now),
            )
            conn.commit()

            return RelationEntry(
                id=rid,
                source_id=resolved_source,
                target_id=resolved_target,
                type=type,
                weight=weight,
                created_at=datetime.fromisoformat(now),
            )
        except sqlite3.IntegrityError as e:
            raise RuntimeError(f"Database integrity error creating relation: {e}")

    def get_relation(self, rid: str) -> Optional[RelationEntry]:
        """Get a single relation by ID (supports partial ID matching)."""
        conn = self._get_conn()

        if len(rid) < 36:
            cursor = conn.execute("SELECT * FROM relations WHERE id LIKE ?", (f"{rid}%",))
        else:
            cursor = conn.execute("SELECT * FROM relations WHERE id = ?", (rid,))

        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_relation(row)

    def get_relations_for_node(self, node_id: str) -> List[RelationEntry]:
        """Get all relations connected to a specific node."""
        conn = self._get_conn()
        node_id = self._resolve_id(conn, node_id) or node_id

        cursor = conn.execute(
            """
            SELECT * FROM relations
            WHERE source_id = ? OR target_id = ?
            ORDER BY created_at DESC
            """,
            (node_id, node_id),
        )
        return [self._row_to_relation(row) for row in cursor.fetchall()]

    def list_relations(self, limit: int = 50) -> List[RelationEntry]:
        """List all relationships."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM relations ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [self._row_to_relation(row) for row in cursor.fetchall()]

    def delete_relation(self, rid: str) -> bool:
        """Delete a relationship."""
        conn = self._get_conn()
        conn.execute("DELETE FROM relations WHERE id = ? OR id LIKE ?", (rid, f"{rid}%"))
        deleted = conn.total_changes > 0
        conn.commit()
        return deleted

    def relation_count(self) -> int:
        """Count total relations."""
        conn = self._get_conn()
        cursor = conn.execute("SELECT COUNT(*) FROM relations")
        return cursor.fetchone()[0]

    def get_relation_types(self) -> List[str]:
        """Get all distinct relation types currently in use."""
        conn = self._get_conn()
        cursor = conn.execute("SELECT DISTINCT type FROM relations ORDER BY type")
        return [row["type"] for row in cursor.fetchall()]

    # ============ Graph ============

    def get_graph(
        self,
        center_id: str = None,
        depth: int = 2,
    ) -> Tuple[List[KnowledgeEntry], List[RelationEntry]]:
        """
        Get graph data for visualization.

        If center_id is provided, returns subgraph around that node (BFS to given depth).
        Otherwise returns full graph (all nodes + edges).
        """
        conn = self._get_conn()

        if center_id:
            center_id = self._resolve_id(conn, center_id)
            if not center_id:
                return [], []

            # BFS from center node
            node_ids = {center_id}
            frontier = {center_id}

            for _ in range(depth):
                if not frontier:
                    break
                new_frontier = set()
                for nid in frontier:
                    cursor = conn.execute(
                        "SELECT source_id, target_id FROM relations WHERE source_id = ? OR target_id = ?",
                        (nid, nid),
                    )
                    for row in cursor.fetchall():
                        new_frontier.add(row["source_id"])
                        new_frontier.add(row["target_id"])

                frontier = new_frontier - node_ids
                node_ids.update(frontier)
        else:
            cursor = conn.execute("SELECT id FROM knowledge")
            node_ids = {row["id"] for row in cursor.fetchall()}

        if not node_ids:
            return [], []

        # Fetch nodes
        placeholders = ",".join("?" * len(node_ids))
        id_list = list(node_ids)

        cursor = conn.execute(
            f"SELECT * FROM knowledge WHERE id IN ({placeholders})",
            id_list,
        )
        nodes = [self._row_to_entry(row) for row in cursor.fetchall()]

        # Fetch edges between these nodes
        cursor = conn.execute(
            f"""
            SELECT * FROM relations
            WHERE source_id IN ({placeholders}) AND target_id IN ({placeholders})
            """,
            id_list + id_list,
        )
        edges = [self._row_to_relation(row) for row in cursor.fetchall()]

        return nodes, edges

    # ============ Stats ============

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        conn = self._get_conn()

        knowledge_count = conn.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0]
        relation_count = conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0]

        try:
            embedding_count = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        except sqlite3.OperationalError:
            embedding_count = 0

        schema_version = self._get_schema_version(conn)

        return {
            "knowledge_count": knowledge_count,
            "relation_count": relation_count,
            "embedding_count": embedding_count,
            "schema_version": schema_version,
            "db_path": str(self.db_path),
        }

    # ============ Helpers ============

    def _row_to_entry(self, row: sqlite3.Row) -> KnowledgeEntry:
        """Convert database row to KnowledgeEntry."""
        return KnowledgeEntry(
            id=row["id"],
            title=row["title"] if "title" in row.keys() else "",
            content=row["content"],
            content_type=row["content_type"] if "content_type" in row.keys() else "text",
            tags=json.loads(row["tags"]) if row["tags"] else [],
            source=row["source"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _row_to_relation(self, row: sqlite3.Row) -> RelationEntry:
        """Convert database row to RelationEntry."""
        return RelationEntry(
            id=row["id"],
            source_id=row["source_id"],
            target_id=row["target_id"],
            type=row["type"],
            weight=row["weight"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def _resolve_id(self, conn: sqlite3.Connection, partial_id: str) -> Optional[str]:
        """Resolve partial ID to full UUID."""
        if not partial_id:
            return None
        if len(partial_id) >= 36:
            return partial_id

        cursor = conn.execute("SELECT id FROM knowledge WHERE id LIKE ?", (f"{partial_id}%",))
        row = cursor.fetchone()
        return row["id"] if row else None

    def close(self):
        """Close all connections in the pool."""
        self._pool.close_all()
