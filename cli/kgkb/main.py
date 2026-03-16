#!/usr/bin/env python3
"""
KGKB CLI - Knowledge Graph Knowledge Base Command Line Interface

Usage:
    kgkb init                    # Initialize database
    kgkb add <content>           # Add knowledge entry
    kgkb query <text>            # Semantic search
    kgkb list [--tag <tag>]      # List entries
    kgkb link <id1> <id2> [--type <rel_type>]  # Create relationship
    kgkb export [--format json]  # Export data
    kgkb web                     # Start web server
    kgkb config                  # Show configuration
"""

import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List
from uuid import uuid4

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

app = typer.Typer(
    name="kgkb",
    help="Knowledge Graph Knowledge Base - Store, visualize, connect and predict knowledge.",
    add_completion=False,
)
console = Console()

# Default paths
DEFAULT_KB_PATH = Path.home() / ".kgkb"
DEFAULT_DB_PATH = DEFAULT_KB_PATH / "kgkb.db"
DEFAULT_CONFIG_PATH = DEFAULT_KB_PATH / "config.yaml"


def get_db_path() -> Path:
    """Get database path from config or default."""
    config_path = DEFAULT_CONFIG_PATH
    if config_path.exists():
        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f)
        if config and "database" in config and "path" in config["database"]:
            return Path(config["database"]["path"]).expanduser()
    return DEFAULT_DB_PATH


def init_db(db_path: Path = None) -> sqlite3.Connection:
    """Initialize database connection and create tables if needed."""
    if db_path is None:
        db_path = get_db_path()

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Create tables
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
    return conn


@app.command()
def init():
    """Initialize KGKB database and configuration."""
    console.print(Panel.fit("🧠 Initializing KGKB", style="bold blue"))

    # Create directories
    DEFAULT_KB_PATH.mkdir(parents=True, exist_ok=True)

    # Initialize database
    conn = init_db()
    conn.close()

    # Create default config if not exists
    if not DEFAULT_CONFIG_PATH.exists():
        import yaml
        config = {
            "embedding": {
                "provider": "ollama",
                "model": "nomic-embed-text",
                "endpoint": "http://localhost:11434",
                "dimension": 768,
            },
            "database": {
                "path": str(DEFAULT_DB_PATH),
            },
            "vector": {
                "backend": "faiss",
                "dimension": 768,
            },
        }
        with open(DEFAULT_CONFIG_PATH, "w") as f:
            yaml.dump(config, f, default_flow_style=False)
        console.print(f"✅ Created config at {DEFAULT_CONFIG_PATH}")

    console.print(f"✅ Database initialized at {get_db_path()}", style="green")
    console.print("\n🎉 KGKB is ready! Try: kgkb add 'Your first knowledge'")


@app.command()
def add(
    content: str = typer.Argument(..., help="Knowledge content to add"),
    tags: str = typer.Option(None, "--tags", "-t", help="Comma-separated tags"),
    source: str = typer.Option(None, "--source", "-s", help="Source URL or reference"),
):
    """Add a new knowledge entry."""
    conn = init_db()
    cursor = conn.cursor()

    # Generate ID and timestamps
    kid = str(uuid4())
    now = datetime.utcnow().isoformat()

    # Parse tags
    tag_list = []
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    tags_json = json.dumps(tag_list)

    # Insert entry
    cursor.execute(
        """
        INSERT INTO knowledge (id, content, tags, source, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (kid, content, tags_json, source, now, now),
    )
    conn.commit()
    conn.close()

    console.print(f"✅ Added knowledge [bold]{kid[:8]}...[/bold]")
    console.print(f"   Content: {content[:60]}{'...' if len(content) > 60 else ''}")
    if tag_list:
        console.print(f"   Tags: {', '.join(tag_list)}")


@app.command()
def query(
    text: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum results"),
    semantic: bool = typer.Option(False, "--semantic", "-s", help="Use semantic search"),
):
    """Search knowledge entries."""
    conn = init_db()
    cursor = conn.cursor()

    if semantic:
        # TODO: Implement semantic search with embeddings
        console.print("⚠️ Semantic search not yet implemented, using keyword search", style="yellow")

    # Simple keyword search
    search_term = f"%{text}%"
    cursor.execute(
        """
        SELECT id, content, tags, source, created_at
        FROM knowledge
        WHERE content LIKE ? OR tags LIKE ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (search_term, search_term, limit),
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        console.print("🔍 No results found", style="yellow")
        return

    table = Table(title=f"🔍 Search Results ({len(rows)} found)")
    table.add_column("ID", style="cyan", width=10)
    table.add_column("Content", width=50)
    table.add_column("Tags", width=20)
    table.add_column("Created", width=12)

    for row in rows:
        tags = json.loads(row["tags"])
        tag_str = ", ".join(tags[:3]) + ("..." if len(tags) > 3 else "")
        content = row["content"][:47] + "..." if len(row["content"]) > 50 else row["content"]
        created = row["created_at"][:10]

        table.add_row(row["id"][:8], content, tag_str, created)

    console.print(table)


@app.command("list")
def list_entries(
    tag: str = typer.Option(None, "--tag", "-t", help="Filter by tag"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum results"),
    all: bool = typer.Option(False, "--all", "-a", help="Show all entries"),
):
    """List knowledge entries."""
    conn = init_db()
    cursor = conn.cursor()

    if all:
        limit = 1000

    if tag:
        search_term = f'%"{tag}"%'
        cursor.execute(
            """
            SELECT id, content, tags, created_at
            FROM knowledge
            WHERE tags LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (search_term, limit),
        )
    else:
        cursor.execute(
            """
            SELECT id, content, tags, created_at
            FROM knowledge
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        console.print("📭 No entries found", style="yellow")
        return

    table = Table(title=f"📋 Knowledge Entries ({len(rows)} total)")
    table.add_column("ID", style="cyan", width=10)
    table.add_column("Content", width=50)
    table.add_column("Tags", width=20)
    table.add_column("Created", width=12)

    for row in rows:
        tags = json.loads(row["tags"])
        tag_str = ", ".join(tags[:3]) + ("..." if len(tags) > 3 else "")
        content = row["content"][:47] + "..." if len(row["content"]) > 50 else row["content"]
        created = row["created_at"][:10]

        table.add_row(row["id"][:8], content, tag_str, created)

    console.print(table)


@app.command()
def link(
    source_id: str = typer.Argument(..., help="Source knowledge ID"),
    target_id: str = typer.Argument(..., help="Target knowledge ID"),
    type: str = typer.Option("relates_to", "--type", "-t", help="Relationship type"),
    weight: float = typer.Option(1.0, "--weight", "-w", help="Relationship weight"),
):
    """Create a relationship between two knowledge entries."""
    conn = init_db()
    cursor = conn.cursor()

    # Verify both entries exist
    cursor.execute("SELECT id FROM knowledge WHERE id LIKE ?", (f"{source_id}%",))
    source = cursor.fetchone()
    cursor.execute("SELECT id FROM knowledge WHERE id LIKE ?", (f"{target_id}%",))
    target = cursor.fetchone()

    if not source:
        console.print(f"❌ Source ID not found: {source_id}", style="red")
        conn.close()
        raise typer.Exit(1)
    if not target:
        console.print(f"❌ Target ID not found: {target_id}", style="red")
        conn.close()
        raise typer.Exit(1)

    # Use full IDs
    source_id = source["id"]
    target_id = target["id"]

    # Create relationship
    rid = str(uuid4())
    now = datetime.utcnow().isoformat()

    cursor.execute(
        """
        INSERT INTO relations (id, source_id, target_id, type, weight, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (rid, source_id, target_id, type, weight, now),
    )
    conn.commit()
    conn.close()

    console.print(f"✅ Created relationship: [cyan]{source_id[:8]}[/cyan] --[{type}]--> [cyan]{target_id[:8]}[/cyan]")


@app.command()
def export(
    format: str = typer.Option("json", "--format", "-f", help="Export format (json, csv)"),
    output: str = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Export knowledge base data."""
    conn = init_db()
    cursor = conn.cursor()

    # Get all knowledge
    cursor.execute("SELECT * FROM knowledge ORDER BY created_at DESC")
    knowledge = [dict(row) for row in cursor.fetchall()]

    # Get all relations
    cursor.execute("SELECT * FROM relations ORDER BY created_at DESC")
    relations = [dict(row) for row in cursor.fetchall()]

    conn.close()

    # Parse JSON fields
    for k in knowledge:
        k["tags"] = json.loads(k["tags"]) if k["tags"] else []

    data = {
        "knowledge": knowledge,
        "relations": relations,
        "exported_at": datetime.utcnow().isoformat(),
        "stats": {
            "knowledge_count": len(knowledge),
            "relation_count": len(relations),
        },
    }

    if format == "json":
        output_data = json.dumps(data, indent=2, ensure_ascii=False)
        if output:
            Path(output).write_text(output_data)
            console.print(f"✅ Exported to {output}")
        else:
            rprint(output_data)
    else:
        console.print(f"❌ Format '{format}' not supported yet", style="red")


@app.command()
def web(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind"),
):
    """Start the web server."""
    console.print("🚀 Starting KGKB web server...", style="blue")
    console.print(f"   Backend: http://{host}:{port}")
    console.print(f"   Frontend: http://{host}:{port + 1}")
    console.print("\n⚠️ Web server implementation coming soon!", style="yellow")
    console.print("   For now, use the CLI commands.")


@app.command()
def config():
    """Show current configuration."""
    if not DEFAULT_CONFIG_PATH.exists():
        console.print("⚠️ No config file found. Run 'kgkb init' first.", style="yellow")
        return

    import yaml
    with open(DEFAULT_CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)

    console.print(Panel.fit("⚙️ KGKB Configuration", style="bold blue"))

    table = Table(show_header=False)
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="green")

    def flatten(d, prefix=""):
        for k, v in d.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                flatten(v, key)
            else:
                table.add_row(key, str(v))

    flatten(cfg)
    console.print(table)


@app.command()
def stats():
    """Show knowledge base statistics."""
    conn = init_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM knowledge")
    knowledge_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM relations")
    relation_count = cursor.fetchone()[0]

    cursor.execute("SELECT tags FROM knowledge WHERE tags != '[]'")
    all_tags = []
    for row in cursor.fetchall():
        tags = json.loads(row[0])
        all_tags.extend(tags)

    from collections import Counter
    tag_counts = Counter(all_tags)
    top_tags = tag_counts.most_common(5)

    conn.close()

    console.print(Panel.fit("📊 KGKB Statistics", style="bold blue"))

    console.print(f"📝 Total knowledge entries: [bold]{knowledge_count}[/bold]")
    console.print(f"🔗 Total relationships: [bold]{relation_count}[/bold]")

    if top_tags:
        console.print("\n🏷️ Top tags:")
        for tag, count in top_tags:
            console.print(f"   {tag}: {count}")


if __name__ == "__main__":
    app()
