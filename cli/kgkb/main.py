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


def _format_search_results(results: list, query_text: str, mode: str, total: int, output_json: bool) -> None:
    """Format and display search results as a rich table or JSON.

    Args:
        results: List of search result dicts from the API.
        query_text: The original query string.
        mode: Search mode used (text, semantic, hybrid).
        total: Total number of results returned.
        output_json: If True, output raw JSON instead of a table.
    """
    if output_json:
        rprint(json.dumps({"results": results, "total": total, "query": query_text, "mode": mode}, indent=2, ensure_ascii=False))
        return

    if not results:
        console.print(f"🔍 No results found for '{query_text}' (mode: {mode})", style="yellow")
        return

    table = Table(title=f"🔍 Search Results — '{query_text}' ({total} found, mode: {mode})")
    table.add_column("ID", style="cyan", width=10)
    table.add_column("Title", width=30)
    table.add_column("Content", width=40)
    table.add_column("Tags", style="yellow", width=18)
    table.add_column("Score", style="green", width=7, justify="right")
    table.add_column("Created", style="dim", width=12)

    for r in results:
        rid = r.get("id", "")[:8]
        title = r.get("title", "")
        if len(title) > 30:
            title = title[:27] + "..."
        content = r.get("content", "").replace("\n", " ")
        if len(content) > 40:
            content = content[:37] + "..."
        tags = r.get("tags", [])
        tag_str = ", ".join(tags[:3]) + ("..." if len(tags) > 3 else "")
        score = f"{r.get('score', 0):.2f}"
        created = r.get("created_at", "")[:10]
        table.add_row(rid, title, content, tag_str, score, created)

    console.print(table)


@app.command()
def query(
    text: str = typer.Argument(..., help="Semantic search query text"),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum number of results"),
    min_score: float = typer.Option(0.0, "--min-score", help="Minimum relevance score (0-1)"),
    output_json: bool = typer.Option(False, "--json", "-j", help="Output results as JSON"),
):
    """Semantic search — find knowledge by meaning, not just keywords.

    Uses the backend embedding service (e.g. Ollama qwen3-embedding) to find
    conceptually similar entries. Falls back to text search if embeddings are
    unavailable.

    Examples:
        kgkb query "machine learning basics"
        kgkb query "how to deploy docker" --limit 5
        kgkb query "database optimization" --json
    """
    with api_client() as client:
        if not check_api_available(client):
            console.print(
                f"❌ Backend API not reachable at {get_api_url()}\n"
                "   Start the backend with: python -m uvicorn backend.app.main:app",
                style="red",
            )
            raise typer.Exit(1)

        try:
            response = client.get(
                "/api/knowledge/search",
                params={"q": text, "mode": "semantic", "limit": limit, "min_score": min_score},
            )
        except httpx.RequestError as e:
            console.print(f"❌ API request failed: {e}", style="red")
            raise typer.Exit(1)

        handle_api_error(response, "semantic search")
        data = response.json()

    _format_search_results(data.get("results", []), text, data.get("mode", "semantic"), data.get("total", 0), output_json)


@app.command()
def search(
    text: str = typer.Argument(..., help="Text search query"),
    mode: str = typer.Option(
        "text", "--mode", "-m",
        help="Search mode: text (keyword), semantic (meaning), or hybrid (both)",
    ),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum number of results"),
    min_score: float = typer.Option(0.0, "--min-score", help="Minimum relevance score (0-1)"),
    output_json: bool = typer.Option(False, "--json", "-j", help="Output results as JSON"),
):
    """Search knowledge entries with configurable mode.

    Modes:
      - text:     Keyword/full-text search (fast, exact matching)
      - semantic: Vector similarity search (meaning-based)
      - hybrid:   Combines text + semantic scores

    Examples:
        kgkb search "python tutorial"
        kgkb search "deploy to cloud" --mode hybrid
        kgkb search "API design" --mode semantic --limit 20
        kgkb search "docker" --json
    """
    valid_modes = ("text", "semantic", "hybrid")
    if mode not in valid_modes:
        console.print(f"❌ Invalid mode '{mode}'. Must be one of: {', '.join(valid_modes)}", style="red")
        raise typer.Exit(1)

    with api_client() as client:
        if not check_api_available(client):
            console.print(
                f"❌ Backend API not reachable at {get_api_url()}\n"
                "   Start the backend with: python -m uvicorn backend.app.main:app",
                style="red",
            )
            raise typer.Exit(1)

        try:
            response = client.get(
                "/api/knowledge/search",
                params={"q": text, "mode": mode, "limit": limit, "min_score": min_score},
            )
        except httpx.RequestError as e:
            console.print(f"❌ API request failed: {e}", style="red")
            raise typer.Exit(1)

        handle_api_error(response, "search")
        data = response.json()

    _format_search_results(data.get("results", []), text, data.get("mode", mode), data.get("total", 0), output_json)


@app.command("list")
def list_entries(
    tag: Optional[str] = typer.Option(None, "--tag", "-t", help="Filter by tag"),
    content_type: Optional[str] = typer.Option(None, "--type", help="Filter by content type (text/url/markdown)"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum results per page"),
    offset: int = typer.Option(0, "--offset", "-o", help="Pagination offset (skip N entries)"),
    output_json: bool = typer.Option(False, "--json", "-j", help="Output results as JSON"),
):
    """List knowledge entries with pagination and filtering.

    Displays knowledge in a formatted table with ID, title, content preview,
    tags, and creation date. Supports filtering by tag and content type,
    and pagination via --limit / --offset.

    Examples:
        kgkb list
        kgkb list --tag python --limit 5
        kgkb list --offset 20 --limit 10
        kgkb list --type markdown --json
    """
    with api_client() as client:
        if not check_api_available(client):
            console.print(
                f"❌ Backend API not reachable at {get_api_url()}\n"
                "   Start the backend with: python -m uvicorn backend.app.main:app",
                style="red",
            )
            raise typer.Exit(1)

        params: dict = {"limit": limit, "offset": offset}
        if tag:
            params["tag"] = tag
        if content_type:
            params["content_type"] = content_type

        try:
            response = client.get("/api/knowledge", params=params)
        except httpx.RequestError as e:
            console.print(f"❌ API request failed: {e}", style="red")
            raise typer.Exit(1)

        handle_api_error(response, "list knowledge")
        data = response.json()

    items = data.get("items", [])
    total = data.get("total", 0)
    current_offset = data.get("offset", offset)
    current_limit = data.get("limit", limit)

    if output_json:
        rprint(json.dumps(data, indent=2, ensure_ascii=False))
        return

    if not items:
        filter_desc = ""
        if tag:
            filter_desc += f" with tag '{tag}'"
        if content_type:
            filter_desc += f" of type '{content_type}'"
        console.print(f"📭 No entries found{filter_desc}", style="yellow")
        return

    # Build title with pagination info
    page_start = current_offset + 1
    page_end = current_offset + len(items)
    title = f"📋 Knowledge Entries — showing {page_start}-{page_end} of {total}"
    if tag:
        title += f" [tag: {tag}]"
    if content_type:
        title += f" [type: {content_type}]"

    table = Table(title=title)
    table.add_column("ID", style="cyan", width=10)
    table.add_column("Title", width=28)
    table.add_column("Content", width=36)
    table.add_column("Type", style="magenta", width=8)
    table.add_column("Tags", style="yellow", width=18)
    table.add_column("Created", style="dim", width=12)

    for item in items:
        kid = item.get("id", "")[:8]
        title_text = item.get("title", "")
        if len(title_text) > 28:
            title_text = title_text[:25] + "..."
        content = item.get("content", "").replace("\n", " ")
        if len(content) > 36:
            content = content[:33] + "..."
        ctype = item.get("content_type", "text")
        tags = item.get("tags", [])
        tag_str = ", ".join(tags[:3]) + ("..." if len(tags) > 3 else "")
        created = item.get("created_at", "")[:10]

        table.add_row(kid, title_text, content, ctype, tag_str, created)

    console.print(table)

    # Pagination hint
    if page_end < total:
        next_offset = current_offset + current_limit
        console.print(
            f"\n💡 More entries available. Use [bold]--offset {next_offset}[/bold] to see the next page.",
            style="dim",
        )


@app.command()
def link(
    source_id: str = typer.Argument(..., help="Source knowledge ID (or prefix)"),
    target_id: str = typer.Argument(..., help="Target knowledge ID (or prefix)"),
    type: str = typer.Option("relates_to", "--type", "-t", help="Relationship type (e.g. relates_to, depends_on, contradicts)"),
    weight: float = typer.Option(1.0, "--weight", "-w", help="Relationship weight (0.0–1.0)"),
    output_json: bool = typer.Option(False, "--json", "-j", help="Output result as JSON"),
):
    """Create a relationship between two knowledge entries via the backend API.

    Supports partial ID prefixes — the backend resolves them to full UUIDs.
    Common relation types: relates_to, depends_on, extends, contradicts,
    references, part_of, derived_from.

    Examples:
        kgkb link abc123 def456
        kgkb link abc123 def456 --type depends_on
        kgkb link abc123 def456 --type references --weight 0.8
    """
    with api_client() as client:
        if not check_api_available(client):
            console.print(
                f"❌ Backend API not reachable at {get_api_url()}\n"
                "   Start the backend with: python -m uvicorn backend.app.main:app",
                style="red",
            )
            raise typer.Exit(1)

        payload = {
            "source_id": source_id,
            "target_id": target_id,
            "type": type,
            "weight": weight,
        }

        try:
            response = client.post("/api/relations", json=payload)
        except httpx.RequestError as e:
            console.print(f"❌ API request failed: {e}", style="red")
            raise typer.Exit(1)

        handle_api_error(response, "create relation")
        result = response.json()

    if output_json:
        rprint(json.dumps(result, indent=2, ensure_ascii=False))
        return

    sid = result.get("source_id", source_id)[:8]
    tid = result.get("target_id", target_id)[:8]
    rtype = result.get("type", type)
    console.print(f"\n✅ Created relation [bold cyan]{result['id'][:8]}...[/bold cyan]")
    console.print(f"   🔗 [cyan]{sid}...[/cyan] --[{rtype}]--> [cyan]{tid}...[/cyan]")
    console.print(f"   ⚖️  Weight: {result.get('weight', weight)}")
    console.print()


@app.command()
def unlink(
    source_id: str = typer.Argument(..., help="Source knowledge ID (or prefix)"),
    target_id: str = typer.Argument(..., help="Target knowledge ID (or prefix)"),
    type: Optional[str] = typer.Option(None, "--type", "-t", help="Only unlink relations of this type"),
    force: bool = typer.Option(False, "--force", "-y", help="Skip confirmation prompt"),
):
    """Remove a relationship between two knowledge entries.

    Finds and deletes relations where source matches source_id and target
    matches target_id. If --type is given, only removes relations of that type.
    By default asks for confirmation (use --force / -y to skip).

    Examples:
        kgkb unlink abc123 def456
        kgkb unlink abc123 def456 --type depends_on
        kgkb unlink abc123 def456 --force
    """
    with api_client() as client:
        if not check_api_available(client):
            console.print(
                f"❌ Backend API not reachable at {get_api_url()}\n"
                "   Start the backend with: python -m uvicorn backend.app.main:app",
                style="red",
            )
            raise typer.Exit(1)

        # Find matching relations by querying the source node's relations
        try:
            response = client.get("/api/relations", params={"node_id": source_id, "limit": 200})
        except httpx.RequestError as e:
            console.print(f"❌ API request failed: {e}", style="red")
            raise typer.Exit(1)
        handle_api_error(response, "list relations")
        data = response.json()

        # Filter: find relations matching source→target (prefix match on target)
        matching = []
        for r in data.get("items", []):
            src_match = r["source_id"].startswith(source_id) or source_id.startswith(r["source_id"][:8])
            tgt_match = r["target_id"].startswith(target_id) or target_id.startswith(r["target_id"][:8])
            if src_match and tgt_match:
                if type is None or r["type"] == type:
                    matching.append(r)

        if not matching:
            console.print(
                f"❌ No relations found from [cyan]{source_id[:8]}[/cyan] to [cyan]{target_id[:8]}[/cyan]"
                + (f" with type '{type}'" if type else ""),
                style="yellow",
            )
            raise typer.Exit(1)

        # Show what will be removed
        console.print(f"\n🔗 Found {len(matching)} relation(s) to remove:")
        for r in matching:
            console.print(
                f"   {r['id'][:8]}... [cyan]{r['source_id'][:8]}[/cyan] "
                f"--[{r['type']}]--> [cyan]{r['target_id'][:8]}[/cyan]"
            )

        # Confirm unless --force
        if not force:
            confirm = typer.confirm(f"\nDelete {len(matching)} relation(s)?", default=False)
            if not confirm:
                console.print("Cancelled.", style="dim")
                raise typer.Exit(0)

        # Delete each matching relation
        deleted = 0
        for r in matching:
            try:
                del_resp = client.delete(f"/api/relations/{r['id']}")
                if del_resp.status_code < 400:
                    deleted += 1
                else:
                    console.print(f"⚠️  Failed to delete {r['id'][:8]}: HTTP {del_resp.status_code}", style="yellow")
            except httpx.RequestError as e:
                console.print(f"⚠️  Failed to delete {r['id'][:8]}: {e}", style="yellow")

        console.print(f"\n✅ Deleted {deleted}/{len(matching)} relation(s)", style="green")


@app.command()
def relations(
    node_id: str = typer.Argument(..., help="Knowledge node ID (or prefix) to show relations for"),
    type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by relation type"),
    output_json: bool = typer.Option(False, "--json", "-j", help="Output results as JSON"),
):
    """Show all relations for a knowledge entry.

    Lists both incoming and outgoing relations for the specified node.
    Shows relation type, direction, and the connected node's title.

    Examples:
        kgkb relations abc123
        kgkb relations abc123 --type depends_on
        kgkb relations abc123 --json
    """
    with api_client() as client:
        if not check_api_available(client):
            console.print(
                f"❌ Backend API not reachable at {get_api_url()}\n"
                "   Start the backend with: python -m uvicorn backend.app.main:app",
                style="red",
            )
            raise typer.Exit(1)

        # Fetch relations for the node
        try:
            params = {"node_id": node_id, "limit": 200}
            if type:
                params["type"] = type
            response = client.get("/api/relations", params=params)
        except httpx.RequestError as e:
            console.print(f"❌ API request failed: {e}", style="red")
            raise typer.Exit(1)
        handle_api_error(response, "list relations")
        data = response.json()

        items = data.get("items", [])

        if output_json:
            rprint(json.dumps(data, indent=2, ensure_ascii=False))
            return

        if not items:
            console.print(
                f"📭 No relations found for node [cyan]{node_id[:8]}[/cyan]"
                + (f" with type '{type}'" if type else ""),
                style="yellow",
            )
            return

        # Resolve node titles for better display (best-effort, cache per ID)
        node_titles: dict = {}

        def get_title(nid: str) -> str:
            if nid not in node_titles:
                try:
                    resp = client.get(f"/api/knowledge/{nid}")
                    if resp.status_code == 200:
                        node_titles[nid] = resp.json().get("title", "")[:30]
                    else:
                        node_titles[nid] = ""
                except Exception:
                    node_titles[nid] = ""
            return node_titles[nid]

        # Separate into outgoing and incoming
        outgoing = [r for r in items if r["source_id"].startswith(node_id) or node_id.startswith(r["source_id"][:8])]
        incoming = [r for r in items if r not in outgoing]

        table = Table(title=f"🔗 Relations for [cyan]{node_id[:8]}...[/cyan] ({len(items)} total)")
        table.add_column("Dir", width=3, justify="center")
        table.add_column("Relation ID", style="dim", width=10)
        table.add_column("Type", style="magenta", width=14)
        table.add_column("Connected Node", style="cyan", width=10)
        table.add_column("Title", width=30)
        table.add_column("Weight", style="green", width=7, justify="right")
        table.add_column("Created", style="dim", width=12)

        for r in outgoing:
            connected = r["target_id"]
            title_text = get_title(connected)
            table.add_row(
                "→",
                r["id"][:8],
                r["type"],
                connected[:8],
                title_text or "(untitled)",
                f"{r['weight']:.1f}",
                r["created_at"][:10],
            )

        for r in incoming:
            connected = r["source_id"]
            title_text = get_title(connected)
            table.add_row(
                "←",
                r["id"][:8],
                r["type"],
                connected[:8],
                title_text or "(untitled)",
                f"{r['weight']:.1f}",
                r["created_at"][:10],
            )

        console.print(table)
        console.print(f"\n   → = outgoing ({len(outgoing)}),  ← = incoming ({len(incoming)})", style="dim")


@app.command()
def delete(
    kid: str = typer.Argument(..., help="Knowledge ID (or prefix) to delete"),
    force: bool = typer.Option(False, "--force", "-y", help="Skip confirmation prompt"),
    output_json: bool = typer.Option(False, "--json", "-j", help="Output result as JSON"),
):
    """Delete a knowledge entry and all its relations.

    Removes the entry from the database, deletes associated embeddings and
    vector index entries, and removes any relations involving this node.
    Asks for confirmation unless --force is used.

    Examples:
        kgkb delete abc12345
        kgkb delete abc12345 --force
    """
    with api_client() as client:
        if not check_api_available(client):
            console.print(
                f"❌ Backend API not reachable at {get_api_url()}\n"
                "   Start the backend with: python -m uvicorn backend.app.main:app",
                style="red",
            )
            raise typer.Exit(1)

        # First, fetch the entry to show details before deletion
        try:
            resp = client.get(f"/api/knowledge/{kid}")
        except httpx.RequestError as e:
            console.print(f"❌ API request failed: {e}", style="red")
            raise typer.Exit(1)

        if resp.status_code == 404:
            console.print(f"❌ Knowledge not found: {kid}", style="red")
            raise typer.Exit(1)
        handle_api_error(resp, "get knowledge")
        entry = resp.json()

        # Show what will be deleted
        console.print(f"\n🗑️  About to delete:")
        console.print(f"   🆔 ID:      [cyan]{entry['id'][:8]}...[/cyan]")
        console.print(f"   📌 Title:   {entry.get('title', '(untitled)')}")
        content_preview = entry.get("content", "")[:60].replace("\n", " ")
        console.print(f"   📝 Content: {content_preview}...")
        tags = entry.get("tags", [])
        if tags:
            console.print(f"   🏷️  Tags:    {', '.join(tags)}")

        # Check for relations
        try:
            rel_resp = client.get("/api/relations", params={"node_id": entry["id"], "limit": 100})
            if rel_resp.status_code == 200:
                rel_data = rel_resp.json()
                rel_count = rel_data.get("total", 0)
                if rel_count > 0:
                    console.print(f"   🔗 Relations: {rel_count} (will also be removed)", style="yellow")
        except Exception:
            pass

        # Confirm deletion
        if not force:
            confirm = typer.confirm("\nAre you sure you want to delete this entry?", default=False)
            if not confirm:
                console.print("Cancelled.", style="dim")
                raise typer.Exit(0)

        # Perform deletion
        try:
            del_resp = client.delete(f"/api/knowledge/{entry['id']}")
        except httpx.RequestError as e:
            console.print(f"❌ API request failed: {e}", style="red")
            raise typer.Exit(1)
        handle_api_error(del_resp, "delete knowledge")
        result = del_resp.json()

    if output_json:
        rprint(json.dumps(result, indent=2, ensure_ascii=False))
        return

    console.print(f"\n✅ Deleted knowledge [bold cyan]{entry['id'][:8]}...[/bold cyan]", style="green")


@app.command()
def export(
    format: str = typer.Option("json", "--format", "-f", help="Export format: json or md (markdown)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path (prints to stdout if omitted)"),
):
    """Export all knowledge base data via the backend API.

    Formats:
      - json: Complete JSON export with knowledge entries, relations, and metadata.
      - md:   Markdown document with each entry as a section, including tags and relations.

    Examples:
        kgkb export                          # JSON to stdout
        kgkb export --format json -o backup.json
        kgkb export --format md -o knowledge.md
    """
    valid_formats = ("json", "md")
    if format not in valid_formats:
        console.print(f"❌ Invalid format '{format}'. Must be one of: {', '.join(valid_formats)}", style="red")
        raise typer.Exit(1)

    with api_client() as client:
        if not check_api_available(client):
            console.print(
                f"❌ Backend API not reachable at {get_api_url()}\n"
                "   Start the backend with: python -m uvicorn backend.app.main:app",
                style="red",
            )
            raise typer.Exit(1)

        # Fetch all knowledge entries (paginated, collect all)
        all_entries = []
        offset = 0
        page_size = 100
        while True:
            try:
                resp = client.get("/api/knowledge", params={"limit": page_size, "offset": offset})
            except httpx.RequestError as e:
                console.print(f"❌ API request failed: {e}", style="red")
                raise typer.Exit(1)
            handle_api_error(resp, "list knowledge")
            page = resp.json()
            items = page.get("items", [])
            all_entries.extend(items)
            if len(items) < page_size:
                break
            offset += page_size

        # Fetch all relations
        all_relations = []
        try:
            resp = client.get("/api/relations", params={"limit": 200})
            if resp.status_code == 200:
                all_relations = resp.json().get("items", [])
        except Exception:
            pass

    now_str = datetime.utcnow().isoformat()

    if format == "json":
        data = {
            "knowledge": all_entries,
            "relations": all_relations,
            "exported_at": now_str,
            "stats": {
                "knowledge_count": len(all_entries),
                "relation_count": len(all_relations),
            },
        }
        output_data = json.dumps(data, indent=2, ensure_ascii=False)

    elif format == "md":
        # Build a markdown document
        lines = []
        lines.append(f"# KGKB Knowledge Export")
        lines.append(f"")
        lines.append(f"Exported: {now_str}")
        lines.append(f"Entries: {len(all_entries)} | Relations: {len(all_relations)}")
        lines.append(f"")
        lines.append(f"---")
        lines.append(f"")

        # Build a relation lookup for enriching entries
        relations_by_node: dict = {}
        for r in all_relations:
            sid, tid = r["source_id"], r["target_id"]
            relations_by_node.setdefault(sid, []).append(r)
            relations_by_node.setdefault(tid, []).append(r)

        for entry in all_entries:
            eid = entry["id"]
            title = entry.get("title", "(untitled)")
            lines.append(f"## {title}")
            lines.append(f"")
            lines.append(f"- **ID**: `{eid[:8]}`")
            lines.append(f"- **Type**: {entry.get('content_type', 'text')}")
            tags = entry.get("tags", [])
            if tags:
                lines.append(f"- **Tags**: {', '.join(tags)}")
            source = entry.get("source")
            if source:
                lines.append(f"- **Source**: {source}")
            lines.append(f"- **Created**: {entry.get('created_at', '')[:10]}")
            lines.append(f"")
            lines.append(entry.get("content", ""))
            lines.append(f"")

            # Relations for this entry
            node_rels = relations_by_node.get(eid, [])
            if node_rels:
                lines.append(f"### Relations")
                lines.append(f"")
                for r in node_rels:
                    if r["source_id"] == eid:
                        lines.append(f"- → **{r['type']}** → `{r['target_id'][:8]}`")
                    else:
                        lines.append(f"- ← **{r['type']}** ← `{r['source_id'][:8]}`")
                lines.append(f"")

            lines.append(f"---")
            lines.append(f"")

        output_data = "\n".join(lines)

    if output:
        Path(output).write_text(output_data, encoding="utf-8")
        console.print(f"✅ Exported {len(all_entries)} entries to [bold]{output}[/bold]", style="green")
    else:
        rprint(output_data)


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
def config(
    key: Optional[str] = typer.Argument(None, help="Config key to set (e.g. embedding.provider, embedding.endpoint)"),
    value: Optional[str] = typer.Argument(None, help="Value to set for the key"),
    output_json: bool = typer.Option(False, "--json", "-j", help="Output current config as JSON"),
):
    """Show or update KGKB configuration.

    Without arguments: displays the current configuration in a table.
    With key + value: updates a specific config key and saves.

    Supported config keys:
        embedding.provider   — ollama, openai, or custom
        embedding.model      — embedding model name (e.g. qwen3-embedding:0.6b)
        embedding.endpoint   — embedding service URL (e.g. http://localhost:11434)
        embedding.dimension  — embedding dimension (e.g. 1024)
        embedding.api_key    — API key for OpenAI/custom providers
        database.path        — SQLite database path
        api.url              — Backend API URL for CLI

    Examples:
        kgkb config                                  # Show all config
        kgkb config embedding.provider ollama        # Set provider
        kgkb config embedding.endpoint http://localhost:11434
        kgkb config embedding.model qwen3-embedding:0.6b
        kgkb config --json                           # Output as JSON
    """
    # Use JSON config as primary (what the backend uses)
    config_path = DEFAULT_JSON_CONFIG_PATH
    yaml_path = DEFAULT_CONFIG_PATH

    # Load existing config
    cfg: dict = {}
    if config_path.exists():
        try:
            with open(config_path) as f:
                cfg = json.load(f)
        except (json.JSONDecodeError, OSError):
            cfg = {}
    elif yaml_path.exists():
        try:
            import yaml
            with open(yaml_path) as f:
                cfg = yaml.safe_load(f) or {}
        except Exception:
            cfg = {}

    # If no key given, display current config
    if key is None:
        if not cfg:
            console.print("⚠️  No config file found. Run 'kgkb init' first.", style="yellow")
            return

        if output_json:
            rprint(json.dumps(cfg, indent=2, ensure_ascii=False))
            return

        console.print(Panel.fit("⚙️  KGKB Configuration", style="bold blue"))

        table = Table(show_header=True)
        table.add_column("Key", style="cyan", width=25)
        table.add_column("Value", style="green")

        def flatten(d: dict, prefix: str = "") -> None:
            for k, v in sorted(d.items()):
                full_key = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    flatten(v, full_key)
                else:
                    # Mask API keys for display
                    display_val = str(v)
                    if "key" in k.lower() and v and len(str(v)) > 8:
                        display_val = str(v)[:4] + "****" + str(v)[-4:]
                    table.add_row(full_key, display_val)

        flatten(cfg)
        console.print(table)

        console.print(f"\n   📁 Config file: {config_path if config_path.exists() else yaml_path}", style="dim")
        return

    # Setting a config value
    if value is None:
        # Show just this key's value
        parts = key.split(".")
        val = cfg
        for p in parts:
            if isinstance(val, dict) and p in val:
                val = val[p]
            else:
                console.print(f"❌ Key not found: {key}", style="red")
                raise typer.Exit(1)
        console.print(f"[cyan]{key}[/cyan] = [green]{val}[/green]")
        return

    # Parse the value (try int, float, bool, else string)
    parsed_value: object = value
    if value.lower() in ("true", "false"):
        parsed_value = value.lower() == "true"
    else:
        try:
            parsed_value = int(value)
        except ValueError:
            try:
                parsed_value = float(value)
            except ValueError:
                parsed_value = value

    # Set the nested key
    parts = key.split(".")
    current = cfg
    for i, p in enumerate(parts[:-1]):
        if p not in current or not isinstance(current[p], dict):
            current[p] = {}
        current = current[p]
    old_value = current.get(parts[-1])
    current[parts[-1]] = parsed_value

    # Save to JSON config
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

    console.print(f"✅ Updated [cyan]{key}[/cyan]: ", end="")
    if old_value is not None:
        console.print(f"[dim]{old_value}[/dim] → [green]{parsed_value}[/green]")
    else:
        console.print(f"[green]{parsed_value}[/green] (new)")
    console.print(f"   📁 Saved to {config_path}", style="dim")


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
