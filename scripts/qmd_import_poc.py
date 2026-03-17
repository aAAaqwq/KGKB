#!/usr/bin/env python3
"""
QMD → KGKB Import POC

Reads recent daily-memory documents from QMD's SQLite index,
converts them to KGKB Knowledge format, generates embeddings,
and imports them into KGKB's storage.

Usage:
    python scripts/qmd_import_poc.py [--limit 10] [--collection daily-memory] [--dry-run]

Requirements:
    pip install httpx rich  (minimal deps for POC)
"""

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    RICH = True
except ImportError:
    RICH = False

try:
    import httpx
    HTTPX = True
except ImportError:
    HTTPX = False

try:
    import numpy as np
    NUMPY = True
except ImportError:
    NUMPY = False

# ============ Config ============

QMD_DB = Path.home() / ".cache" / "qmd" / "index.sqlite"
KGKB_DB = Path.home() / ".kgkb" / "kgkb.db"
KGKB_VECTORS = Path.home() / ".kgkb" / "vectors"
SYNC_STATE = Path.home() / ".kgkb" / "qmd_sync_state.json"
OLLAMA_URL = "http://localhost:11434"
OLLAMA_REMOTE_URL = "http://100.65.110.126:11434"
EMBED_MODEL = "qwen3-embedding:0.6b"
EMBED_DIM = 1024

# Collection → tag mapping
COLLECTION_TAGS = {
    "clawd-memory": ["memory", "clawd"],
    "daily-memory": ["daily", "memory"],
    "team": ["team", "config"],
    "openclaw-config": ["openclaw", "config"],
    "projects": ["project"],
    "skills": ["skill"],
    "reports": ["report"],
}

console = Console() if RICH else None


def log(msg: str, style: str = ""):
    if console:
        console.print(msg, style=style)
    else:
        print(msg)


# ============ QMD Reader ============

def read_qmd_documents(collection: str, limit: int) -> list[dict]:
    """Read documents from QMD's SQLite index."""
    if not QMD_DB.exists():
        log(f"[red]QMD database not found: {QMD_DB}[/red]")
        sys.exit(1)

    conn = sqlite3.connect(str(QMD_DB))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute(
        """
        SELECT d.id, d.collection, d.path, d.title, d.hash,
               d.created_at, d.modified_at, c.doc
        FROM documents d
        JOIN content c ON d.hash = c.hash
        WHERE d.collection = ? AND d.active = 1
        ORDER BY d.modified_at DESC
        LIMIT ?
        """,
        (collection, limit),
    )

    docs = []
    for row in cur.fetchall():
        docs.append({
            "qmd_id": row["id"],
            "collection": row["collection"],
            "path": row["path"],
            "title": row["title"] or row["path"],
            "hash": row["hash"],
            "created_at": row["created_at"],
            "modified_at": row["modified_at"],
            "content": row["doc"],
        })

    conn.close()
    log(f"Read {len(docs)} documents from QMD collection '{collection}'")
    return docs


# ============ Embedding ============

def check_ollama(url: str) -> bool:
    """Check if Ollama is reachable."""
    if not HTTPX:
        return False
    try:
        r = httpx.get(f"{url}/api/tags", timeout=5.0)
        return r.status_code == 200
    except Exception:
        return False


def embed_text(text: str, url: str) -> Optional[list[float]]:
    """Generate embedding via Ollama API."""
    if not HTTPX:
        return None
    try:
        r = httpx.post(
            f"{url}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text[:4000]},
            timeout=30.0,
        )
        r.raise_for_status()
        return r.json()["embedding"]
    except Exception as e:
        log(f"[yellow]Embedding failed: {e}[/yellow]")
        return None


def mock_embedding(text: str, dim: int = EMBED_DIM) -> list[float]:
    """Generate deterministic mock embedding for testing."""
    h = hashlib.sha256(text.encode()).digest()
    if NUMPY:
        rng = np.random.RandomState(int.from_bytes(h[:4], "big"))
        vec = rng.randn(dim).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        return vec.tolist()
    else:
        import random
        rng = random.Random(int.from_bytes(h[:4], "big"))
        vec = [rng.gauss(0, 1) for _ in range(dim)]
        norm = sum(x * x for x in vec) ** 0.5
        return [x / norm for x in vec]


# ============ KGKB Writer ============

def init_kgkb_db():
    """Initialize KGKB database."""
    KGKB_DB.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(KGKB_DB))
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
    log("KGKB database initialized")


def insert_knowledge(kid: str, title: str, content: str, tags: list, source: str,
                     created_at: str, updated_at: str) -> bool:
    """Insert a knowledge entry into KGKB."""
    conn = sqlite3.connect(str(KGKB_DB))
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT OR REPLACE INTO knowledge (id, content, tags, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (kid, f"# {title}\n\n{content}" if title else content,
             json.dumps(tags), source, created_at, updated_at),
        )
        conn.commit()
        return True
    except Exception as e:
        log(f"[red]Insert failed: {e}[/red]")
        return False
    finally:
        conn.close()


def insert_relation(source_id: str, target_id: str, rel_type: str, weight: float):
    """Insert a relation between two knowledge entries."""
    conn = sqlite3.connect(str(KGKB_DB))
    cur = conn.cursor()
    rid = str(uuid4())
    now = datetime.utcnow().isoformat()
    try:
        cur.execute(
            "INSERT INTO relations (id, source_id, target_id, type, weight, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (rid, source_id, target_id, rel_type, weight, now),
        )
        conn.commit()
    except Exception as e:
        log(f"[yellow]Relation insert failed: {e}[/yellow]")
    finally:
        conn.close()


# ============ FAISS Vector Store ============

def save_to_faiss(vectors: dict[str, list[float]]):
    """Save vectors to FAISS index."""
    try:
        import faiss
    except ImportError:
        log("[yellow]FAISS not available, skipping vector store[/yellow]")
        return False

    if not vectors:
        return False

    KGKB_VECTORS.parent.mkdir(parents=True, exist_ok=True)

    ids = list(vectors.keys())
    vecs = np.array(list(vectors.values()), dtype=np.float32)

    # Normalize for cosine similarity
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1
    vecs = vecs / norms

    dim = vecs.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vecs)

    # Save FAISS index
    faiss_path = KGKB_VECTORS.with_suffix(".faiss")
    faiss.write_index(index, str(faiss_path))

    # Save ID mapping
    import pickle
    meta = {
        "id_map": {i: kid for i, kid in enumerate(ids)},
        "metadata_store": {},
        "dimension": dim,
        "metric": "cosine",
    }
    with open(KGKB_VECTORS.with_suffix(".meta"), "wb") as f:
        pickle.dump(meta, f)

    log(f"Saved {len(ids)} vectors to FAISS (dim={dim})")
    return True


# ============ Sync State ============

def load_sync_state() -> dict:
    """Load QMD→KGKB sync state."""
    if SYNC_STATE.exists():
        return json.loads(SYNC_STATE.read_text())
    return {"hash_to_uuid": {}, "last_sync": None}


def save_sync_state(state: dict):
    """Save sync state."""
    SYNC_STATE.parent.mkdir(parents=True, exist_ok=True)
    SYNC_STATE.write_text(json.dumps(state, indent=2))


# ============ Verification ============

def verify_import():
    """Verify imported data is searchable."""
    conn = sqlite3.connect(str(KGKB_DB))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) as cnt FROM knowledge")
    total = cur.fetchone()["cnt"]

    cur.execute("SELECT COUNT(*) as cnt FROM relations")
    rels = cur.fetchone()["cnt"]

    cur.execute("SELECT id, substr(content, 1, 80) as preview, tags FROM knowledge ORDER BY created_at DESC LIMIT 5")
    rows = cur.fetchall()
    conn.close()

    log(f"\n[bold green]✅ Verification[/bold green]")
    log(f"  Knowledge entries: {total}")
    log(f"  Relations: {rels}")

    if rows and RICH:
        table = Table(title="Recent Entries")
        table.add_column("ID", style="dim", width=8)
        table.add_column("Preview", width=60)
        table.add_column("Tags")
        for r in rows:
            table.add_row(r["id"][:8], r["preview"], r["tags"])
        console.print(table)

    # Test keyword search
    cur2 = sqlite3.connect(str(KGKB_DB))
    cur2.row_factory = sqlite3.Row
    c = cur2.cursor()
    c.execute("SELECT id, substr(content, 1, 60) as preview FROM knowledge WHERE content LIKE '%memory%' LIMIT 3")
    search_results = c.fetchall()
    cur2.close()

    if search_results:
        log(f"\n  Search 'memory': {len(search_results)} results ✅")
        for r in search_results:
            log(f"    {r['id'][:8]}  {r['preview']}")
    else:
        log(f"\n  Search 'memory': 0 results ⚠️")

    return total > 0


# ============ Main ============

def main():
    parser = argparse.ArgumentParser(description="QMD → KGKB Import POC")
    parser.add_argument("--limit", type=int, default=10, help="Number of docs to import")
    parser.add_argument("--collection", default="daily-memory", help="QMD collection to import")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be imported")
    parser.add_argument("--mock-embed", action="store_true", help="Use mock embeddings (no Ollama needed)")
    args = parser.parse_args()

    log("[bold]🔄 QMD → KGKB Import POC[/bold]\n")

    # Step 1: Read QMD documents
    log("[bold]Step 1: Reading QMD documents[/bold]")
    docs = read_qmd_documents(args.collection, args.limit)
    if not docs:
        log("[red]No documents found[/red]")
        return

    # Step 2: Check embedding availability
    log("\n[bold]Step 2: Checking embedding service[/bold]")
    use_mock = args.mock_embed
    ollama_url = None

    if not use_mock:
        if check_ollama(OLLAMA_URL):
            ollama_url = OLLAMA_URL
            log(f"  Using local Ollama: {OLLAMA_URL} ✅")
        elif check_ollama(OLLAMA_REMOTE_URL):
            ollama_url = OLLAMA_REMOTE_URL
            log(f"  Using remote Ollama: {OLLAMA_REMOTE_URL} ✅")
        else:
            log("  [yellow]Ollama unreachable, falling back to mock embeddings[/yellow]")
            use_mock = True

    if use_mock:
        log(f"  Using mock embeddings (dim={EMBED_DIM}) — search quality will be random")

    if args.dry_run:
        log(f"\n[bold yellow]DRY RUN — would import {len(docs)} documents:[/bold yellow]")
        for d in docs:
            tags = COLLECTION_TAGS.get(d["collection"], [d["collection"]])
            log(f"  {d['path']} → tags={tags}, {len(d['content'])} chars")
        return

    # Step 3: Initialize KGKB
    log("\n[bold]Step 3: Initializing KGKB database[/bold]")
    init_kgkb_db()

    # Step 4: Import documents
    log("\n[bold]Step 4: Importing documents[/bold]")
    sync_state = load_sync_state()
    vectors: dict[str, list[float]] = {}
    imported_ids: list[str] = []
    skipped = 0

    for i, doc in enumerate(docs):
        # Check if already imported
        if doc["hash"] in sync_state["hash_to_uuid"]:
            skipped += 1
            continue

        kid = str(uuid4())
        tags = COLLECTION_TAGS.get(doc["collection"], [doc["collection"]])
        source = f"qmd://{doc['collection']}/{doc['path']}"

        # Generate embedding
        if use_mock:
            embedding = mock_embedding(doc["content"])
        else:
            embedding = embed_text(doc["content"], ollama_url)
            if embedding is None:
                embedding = mock_embedding(doc["content"])
                log(f"  [yellow]Fallback to mock for: {doc['path']}[/yellow]")

        # Insert into KGKB
        success = insert_knowledge(
            kid=kid,
            title=doc["title"],
            content=doc["content"],
            tags=tags,
            source=source,
            created_at=doc["created_at"] or datetime.utcnow().isoformat(),
            updated_at=doc["modified_at"] or datetime.utcnow().isoformat(),
        )

        if success:
            vectors[kid] = embedding
            imported_ids.append(kid)
            sync_state["hash_to_uuid"][doc["hash"]] = kid
            log(f"  [{i+1}/{len(docs)}] ✅ {doc['path']} → {kid[:8]}")
        else:
            log(f"  [{i+1}/{len(docs)}] ❌ {doc['path']}")

    log(f"\nImported: {len(imported_ids)}, Skipped (already synced): {skipped}")

    # Step 5: Create co-temporal relations
    log("\n[bold]Step 5: Inferring relations[/bold]")
    rel_count = 0
    if len(imported_ids) > 1:
        # Link sequential daily entries
        for i in range(len(imported_ids) - 1):
            insert_relation(imported_ids[i], imported_ids[i + 1], "co_temporal", 0.5)
            rel_count += 1
        log(f"  Created {rel_count} co-temporal relations")

    # Step 6: Save vectors
    log("\n[bold]Step 6: Saving vectors to FAISS[/bold]")
    if vectors:
        save_to_faiss(vectors)

    # Step 7: Save sync state
    sync_state["last_sync"] = datetime.utcnow().isoformat()
    save_sync_state(sync_state)
    log(f"Sync state saved: {len(sync_state['hash_to_uuid'])} mappings")

    # Step 8: Verify
    log("\n[bold]Step 8: Verification[/bold]")
    verify_import()

    log(f"\n[bold green]🎉 POC Complete![/bold green]")
    log(f"  Imported: {len(imported_ids)} documents")
    log(f"  Vectors: {len(vectors)} embeddings ({EMBED_DIM}d)")
    log(f"  Relations: {rel_count}")
    log(f"  Mode: {'mock' if use_mock else 'ollama'}")


if __name__ == "__main__":
    main()
