#!/usr/bin/env python3
"""
KGKB CLI - Knowledge Graph Knowledge Base Command Line Interface

Usage:
    kgkb init                    # Initialize database
    kgkb add <content>           # Add knowledge entry
    kgkb add --file note.md      # Add from file
    kgkb query <text>            # Semantic search
    kgkb search <text>           # Text search
    kgkb list [--tag <tag>]      # List entries
    kgkb link <id1> <id2>        # Create relationship
    kgkb unlink <id1> <id2>      # Remove relationship
    kgkb relations <id>          # Show node's relations
    kgkb delete <id>             # Delete entry
    kgkb export [--format json]  # Export data
    kgkb import <file>           # Import data
    kgkb web                     # Start web server
    kgkb config                  # Show/set configuration
"""

import os
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List
from uuid import uuid4

import typer
import httpx
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
DEFAULT_JSON_CONFIG_PATH = DEFAULT_KB_PATH / "config.json"

# Default API base URL
DEFAULT_API_URL = "http://127.0.0.1:8000"


def get_api_url() -> str:
    """Get the backend API base URL from config or environment."""
    # 1. Check environment variable
    env_url = os.environ.get("KGKB_API_URL")
    if env_url:
        return env_url.rstrip("/")

    # 2. Check JSON config (used by backend)
    if DEFAULT_JSON_CONFIG_PATH.exists():
        try:
            with open(DEFAULT_JSON_CONFIG_PATH) as f:
                config = json.load(f)
            api_url = config.get("api", {}).get("url")
            if api_url:
                return api_url.rstrip("/")
        except (json.JSONDecodeError, OSError):
            pass

    # 3. Check YAML config
    if DEFAULT_CONFIG_PATH.exists():
        try:
            import yaml
            with open(DEFAULT_CONFIG_PATH) as f:
                config = yaml.safe_load(f)
            if config:
                api_url = config.get("api", {}).get("url")
                if api_url:
                    return api_url.rstrip("/")
        except Exception:
            pass

    return DEFAULT_API_URL


def api_client() -> httpx.Client:
    """Create an httpx client configured for the KGKB API."""
    return httpx.Client(
        base_url=get_api_url(),
        timeout=30.0,
        headers={"Content-Type": "application/json"},
    )


def handle_api_error(response: httpx.Response, action: str = "request") -> None:
    """Handle API error responses with user-friendly messages."""
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except Exception:
            detail = response.text
        console.print(f"❌ API {action} failed (HTTP {response.status_code}): {detail}", style="red")
        raise typer.Exit(1)


def check_api_available(client: httpx.Client) -> bool:
    """Check if the backend API is reachable."""
    try:
        resp = client.get("/api/health", timeout=5.0)
        return resp.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


def get_db_path() -> Path:
    """Get database path from config or default (used by init/offline commands)."""
    config_path = DEFAULT_CONFIG_PATH
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                config = yaml.safe_load(f)
            if config and "database" in config and "path" in config["database"]:
                return Path(config["database"]["path"]).expanduser()
        except Exception:
            pass
    return DEFAULT_DB_PATH


def init_db(db_path: Path = None) -> sqlite3.Connection:
    """Initialize database connection and create tables if needed.

    Used for offline/init commands when the backend is not running.
    """
    if db_path is None:
        db_path = get_db_path()

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

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
    content: Optional[str] = typer.Argument(None, help="Knowledge content to add (or use --file)"),
    file: Optional[Path] = typer.Option(
        None, "--file", "-f",
        help="Read content from a file instead of positional argument",
        exists=True,
        readable=True,
    ),
    tags: Optional[str] = typer.Option(None, "--tags", "-t", help="Comma-separated tags"),
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Source URL or reference"),
    content_type: str = typer.Option(
        "text", "--type", help="Content type: text, url, or markdown"
    ),
    title: Optional[str] = typer.Option(None, "--title", help="Short title for the entry"),
    output_json: bool = typer.Option(False, "--json", "-j", help="Output result as JSON"),
):
    """Add a new knowledge entry via the backend API.

    Provide content as a positional argument, or use --file to read from a file.
    Auto-triggers embedding generation if the backend embedding service is configured.

    Examples:
        kgkb add "Python is a programming language" --tags python,programming
        kgkb add --file notes.md --type markdown --tags notes --source https://example.com
        kgkb add "https://example.com/article" --type url --tags reference
    """
    # --- Input validation ---
    if content is None and file is None:
        console.print("❌ Please provide content as an argument or use --file <path>", style="red")
        raise typer.Exit(1)

    if content is not None and file is not None:
        console.print("❌ Provide either content argument or --file, not both", style="red")
        raise typer.Exit(1)

    # Read content from file if specified
    if file is not None:
        try:
            content = file.read_text(encoding="utf-8")
            # Auto-detect content type from file extension
            suffix = file.suffix.lower()
            if suffix in (".md", ".markdown") and content_type == "text":
                content_type = "markdown"
            # Use filename as default title if none provided
            if title is None:
                title = file.stem.replace("-", " ").replace("_", " ").title()
            # Use file path as default source if none provided
            if source is None:
                source = f"file://{file.resolve()}"
        except Exception as e:
            console.print(f"❌ Failed to read file: {e}", style="red")
            raise typer.Exit(1)

    # Validate content type
    valid_types = ("text", "url", "markdown")
    if content_type not in valid_types:
        console.print(
            f"❌ Invalid content type '{content_type}'. Must be one of: {', '.join(valid_types)}",
            style="red",
        )
        raise typer.Exit(1)

    # Validate content is not empty
    if not content or not content.strip():
        console.print("❌ Content cannot be empty", style="red")
        raise typer.Exit(1)

    # Validate content length
    if len(content) > 50000:
        console.print(
            f"❌ Content too long ({len(content)} chars). Maximum is 50,000 characters.",
            style="red",
        )
        raise typer.Exit(1)

    # Parse tags
    tag_list: List[str] = []
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    # Auto-generate title from content if not provided
    if not title:
        # Use first line or first 80 chars as title
        first_line = content.strip().split("\n")[0].strip()
        # Strip markdown heading prefix
        if first_line.startswith("#"):
            first_line = first_line.lstrip("#").strip()
        title = first_line[:80] + ("..." if len(first_line) > 80 else "")

    # --- Call backend API ---
    with api_client() as client:
        if not check_api_available(client):
            console.print(
                f"❌ Backend API not reachable at {get_api_url()}\n"
                "   Start the backend with: python -m uvicorn backend.app.main:app",
                style="red",
            )
            raise typer.Exit(1)

        payload = {
            "title": title,
            "content": content,
            "content_type": content_type,
            "tags": tag_list,
            "source": source,
        }

        try:
            response = client.post("/api/knowledge", json=payload)
        except httpx.RequestError as e:
            console.print(f"❌ API request failed: {e}", style="red")
            raise typer.Exit(1)

        handle_api_error(response, "create knowledge")
        result = response.json()

    # --- Output ---
    if output_json:
        rprint(json.dumps(result, indent=2, ensure_ascii=False))
        return

    kid = result["id"]
    result_title = result.get("title", "")
    result_tags = result.get("tags", [])
    result_content = result.get("content", "")

    console.print(f"\n✅ Added knowledge [bold cyan]{kid[:8]}...[/bold cyan]")
    console.print(f"   📌 Title:   {result_title}")
    content_preview = result_content[:80].replace("\n", " ")
    if len(result_content) > 80:
        content_preview += "..."
    console.print(f"   📝 Content: {content_preview}")
    console.print(f"   📄 Type:    {result.get('content_type', content_type)}")
    if result_tags:
        tag_display = ", ".join(f"[yellow]{t}[/yellow]" for t in result_tags)
        console.print(f"   🏷️  Tags:    {tag_display}")
    if source:
        console.print(f"   🔗 Source:  {source}")
    console.print(f"   🆔 Full ID: {kid}")
    console.print()

    # Check embedding status via health endpoint (best-effort)
    try:
        with api_client() as client:
            health = client.get("/api/health", timeout=3.0)
            if health.status_code == 200:
                health_data = health.json()
                if health_data.get("embedding_available"):
                    console.print("   ✨ Embedding auto-generated", style="dim green")
                else:
                    console.print("   ⚠️  Embedding skipped (service not available)", style="dim yellow")
    except Exception:
        pass  # Don't fail for status check


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
