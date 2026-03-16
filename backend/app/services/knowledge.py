"""
KGKB Knowledge Service - Core business logic for knowledge management

Handles:
- CRUD operations for knowledge entries
- Relationship management
- Graph traversal
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple
from uuid import uuid4
from dataclasses import dataclass


@dataclass
class KnowledgeEntry:
    """Knowledge entry data class."""
    id: str
    content: str
    tags: List[str]
    source: Optional[str]
    embedding: Optional[bytes]
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


class KnowledgeService:
    """
    Core service for knowledge management.
    Uses SQLite for persistence.
    """

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize database tables."""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS knowledge (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                tags TEXT DEFAULT '[]',
                source TEXT,
                embedding BLOB,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS relations (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                type TEXT DEFAULT 'relates_to',
                weight REAL DEFAULT 1.0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (source_id) REFERENCES knowledge(id),
                FOREIGN KEY (target_id) REFERENCES knowledge(id)
            );

            CREATE INDEX IF NOT EXISTS idx_knowledge_tags ON knowledge(tags);
            CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_id);
            CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_id);
        """)
        conn.commit()
        conn.close()

    def create(
        self,
        content: str,
        tags: List[str] = None,
        source: str = None,
    ) -> KnowledgeEntry:
        """Create a new knowledge entry."""
        conn = self._get_conn()
        cursor = conn.cursor()

        now = datetime.utcnow().isoformat()
        kid = str(uuid4())
        tags_json = json.dumps(tags or [])

        cursor.execute(
            """
            INSERT INTO knowledge (id, content, tags, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (kid, content, tags_json, source, now, now),
        )
        conn.commit()
        conn.close()

        return KnowledgeEntry(
            id=kid,
            content=content,
            tags=tags or [],
            source=source,
            embedding=None,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
        )

    def get(self, kid: str) -> Optional[KnowledgeEntry]:
        """Get a knowledge entry by ID."""
        conn = self._get_conn()
        cursor = conn.cursor()

        # Support partial ID matching
        if len(kid) < 36:
            cursor.execute("SELECT * FROM knowledge WHERE id LIKE ?", (f"{kid}%",))
        else:
            cursor.execute("SELECT * FROM knowledge WHERE id = ?", (kid,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return self._row_to_entry(row)

    def list(
        self,
        tag: str = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[KnowledgeEntry]:
        """List knowledge entries."""
        conn = self._get_conn()
        cursor = conn.cursor()

        if tag:
            search_term = f'%"{tag}"%'
            cursor.execute(
                """
                SELECT * FROM knowledge
                WHERE tags LIKE ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (search_term, limit, offset),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM knowledge
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )

        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_entry(row) for row in rows]

    def update(
        self,
        kid: str,
        content: str = None,
        tags: List[str] = None,
        source: str = None,
    ) -> Optional[KnowledgeEntry]:
        """Update a knowledge entry."""
        conn = self._get_conn()
        cursor = conn.cursor()

        # Get existing entry
        if len(kid) < 36:
            cursor.execute("SELECT * FROM knowledge WHERE id LIKE ?", (f"{kid}%",))
        else:
            cursor.execute("SELECT * FROM knowledge WHERE id = ?", (kid,))

        row = cursor.fetchone()
        if not row:
            conn.close()
            return None

        kid = row["id"]  # Use full ID
        now = datetime.utcnow().isoformat()

        # Update fields
        new_content = content if content is not None else row["content"]
        new_tags = json.dumps(tags) if tags is not None else row["tags"]
        new_source = source if source is not None else row["source"]

        cursor.execute(
            """
            UPDATE knowledge
            SET content = ?, tags = ?, source = ?, updated_at = ?
            WHERE id = ?
            """,
            (new_content, new_tags, new_source, now, kid),
        )
        conn.commit()
        conn.close()

        return self.get(kid)

    def delete(self, kid: str) -> bool:
        """Delete a knowledge entry."""
        conn = self._get_conn()
        cursor = conn.cursor()

        # Get full ID if partial
        if len(kid) < 36:
            cursor.execute("SELECT id FROM knowledge WHERE id LIKE ?", (f"{kid}%",))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return False
            kid = row["id"]

        # Delete related relations first
        cursor.execute("DELETE FROM relations WHERE source_id = ? OR target_id = ?", (kid, kid))

        # Delete knowledge
        cursor.execute("DELETE FROM knowledge WHERE id = ?", (kid,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()

        return deleted

    def search(self, query: str, limit: int = 10) -> List[KnowledgeEntry]:
        """Simple keyword search."""
        conn = self._get_conn()
        cursor = conn.cursor()

        search_term = f"%{query}%"
        cursor.execute(
            """
            SELECT * FROM knowledge
            WHERE content LIKE ? OR tags LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (search_term, search_term, limit),
        )

        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_entry(row) for row in rows]

    def count(self) -> int:
        """Count total knowledge entries."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM knowledge")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    # ============ Relations ============

    def create_relation(
        self,
        source_id: str,
        target_id: str,
        type: str = "relates_to",
        weight: float = 1.0,
    ) -> Optional[RelationEntry]:
        """Create a relationship between two knowledge entries."""
        conn = self._get_conn()
        cursor = conn.cursor()

        # Resolve partial IDs
        source_id = self._resolve_id(cursor, source_id)
        target_id = self._resolve_id(cursor, target_id)

        if not source_id or not target_id:
            conn.close()
            return None

        rid = str(uuid4())
        now = datetime.utcnow().isoformat()

        try:
            cursor.execute(
                """
                INSERT INTO relations (id, source_id, target_id, type, weight, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (rid, source_id, target_id, type, weight, now),
            )
            conn.commit()
            conn.close()

            return RelationEntry(
                id=rid,
                source_id=source_id,
                target_id=target_id,
                type=type,
                weight=weight,
                created_at=datetime.fromisoformat(now),
            )
        except sqlite3.IntegrityError:
            conn.close()
            return None

    def list_relations(self, limit: int = 50) -> List[RelationEntry]:
        """List all relationships."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM relations ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )

        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_relation(row) for row in rows]

    def delete_relation(self, rid: str) -> bool:
        """Delete a relationship."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM relations WHERE id = ? OR id LIKE ?", (rid, f"{rid}%"))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()

        return deleted

    # ============ Graph ============

    def get_graph(
        self,
        center_id: str = None,
        depth: int = 2,
    ) -> Tuple[List[KnowledgeEntry], List[RelationEntry]]:
        """
        Get graph data for visualization.

        If center_id is provided, returns subgraph around that node.
        Otherwise returns full graph.
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        if center_id:
            # BFS from center node
            center_id = self._resolve_id(cursor, center_id)
            if not center_id:
                conn.close()
                return [], []

            node_ids = {center_id}
            frontier = {center_id}

            for _ in range(depth):
                new_frontier = set()
                for nid in frontier:
                    # Get connected nodes
                    cursor.execute(
                        """
                        SELECT source_id, target_id FROM relations
                        WHERE source_id = ? OR target_id = ?
                        """,
                        (nid, nid),
                    )
                    for row in cursor.fetchall():
                        new_frontier.add(row["source_id"])
                        new_frontier.add(row["target_id"])

                frontier = new_frontier - node_ids
                node_ids.update(frontier)
                if not frontier:
                    break
        else:
            # Get all nodes
            cursor.execute("SELECT id FROM knowledge")
            node_ids = {row["id"] for row in cursor.fetchall()}

        # Get nodes
        placeholders = ",".join("?" * len(node_ids))
        cursor.execute(
            f"SELECT * FROM knowledge WHERE id IN ({placeholders})",
            list(node_ids),
        )
        nodes = [self._row_to_entry(row) for row in cursor.fetchall()]

        # Get edges
        cursor.execute(
            f"""
            SELECT * FROM relations
            WHERE source_id IN ({placeholders}) AND target_id IN ({placeholders})
            """,
            list(node_ids) * 2,
        )
        edges = [self._row_to_relation(row) for row in cursor.fetchall()]

        conn.close()
        return nodes, edges

    # ============ Helpers ============

    def _row_to_entry(self, row: sqlite3.Row) -> KnowledgeEntry:
        """Convert database row to KnowledgeEntry."""
        return KnowledgeEntry(
            id=row["id"],
            content=row["content"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            source=row["source"],
            embedding=row["embedding"],
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

    def _resolve_id(self, cursor: sqlite3.Cursor, partial_id: str) -> Optional[str]:
        """Resolve partial ID to full ID."""
        if len(partial_id) >= 36:
            return partial_id

        cursor.execute("SELECT id FROM knowledge WHERE id LIKE ?", (f"{partial_id}%",))
        row = cursor.fetchone()
        return row["id"] if row else None
