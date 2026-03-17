#!/usr/bin/env python3
"""
KGKB Backend Startup Script

Initializes the database, validates configuration, and starts the
FastAPI application via uvicorn.

Usage:
    python backend/run.py              # Default: host=0.0.0.0, port=8000
    python backend/run.py --port 9000  # Custom port
    python backend/run.py --reload     # Dev mode with auto-reload
    python -m backend.run              # As module
"""

import argparse
import os
import sys
from pathlib import Path


def ensure_data_dir() -> Path:
    """Create ~/.kgkb directory structure if it doesn't exist.

    Returns the data directory path.
    """
    data_dir = Path.home() / ".kgkb"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def init_config(data_dir: Path) -> None:
    """Create default config.json if it doesn't exist.

    Writes a sensible default configuration with Ollama embedding
    provider and SQLite database path.
    """
    config_path = data_dir / "config.json"
    if config_path.exists():
        return

    import json

    default_config = {
        "embedding": {
            "provider": "ollama",
            "model": "qwen3-embedding:0.6b",
            "endpoint": "http://localhost:11434",
            "dimension": 1024,
            "api_key": None,
        },
        "database": {
            "path": str(data_dir / "data.db"),
        },
        "vector": {
            "backend": "faiss",
            "dimension": 1024,
        },
    }

    config_path.write_text(json.dumps(default_config, indent=2, ensure_ascii=False))
    print(f"Created default config at {config_path}")


def init_database(data_dir: Path) -> None:
    """Initialize the SQLite database with the required schema.

    Uses KnowledgeService's built-in schema initialization and migration.
    Ensures the database file exists and tables are created.
    """
    # Add project root to path so we can import the app
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from backend.app.services.knowledge import KnowledgeService

    db_path = data_dir / "data.db"
    service = KnowledgeService(db_path)

    # Verify tables exist by running a count query
    count = service.count()
    print(f"Database ready at {db_path} ({count} knowledge entries)")


def print_banner(host: str, port: int, reload: bool) -> None:
    """Print startup banner with useful info."""
    data_dir = Path.home() / ".kgkb"
    print()
    print("=" * 55)
    print("  KGKB - Knowledge Graph Knowledge Base")
    print("=" * 55)
    print(f"  API:     http://{host}:{port}")
    print(f"  Docs:    http://{host}:{port}/docs")
    print(f"  Health:  http://{host}:{port}/api/health")
    print(f"  Data:    {data_dir}")
    print(f"  Mode:    {'development (auto-reload)' if reload else 'production'}")
    print("=" * 55)
    print()


def main():
    """Parse arguments, initialize everything, and start the server."""
    parser = argparse.ArgumentParser(
        description="Start the KGKB backend server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python backend/run.py                  # Start on 0.0.0.0:8000
  python backend/run.py --port 9000      # Custom port
  python backend/run.py --reload         # Dev mode with auto-reload
  python backend/run.py --host 127.0.0.1 # Localhost only
        """,
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("KGKB_HOST", "0.0.0.0"),
        help="Bind host (default: 0.0.0.0, env: KGKB_HOST)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("KGKB_PORT", "8000")),
        help="Bind port (default: 8000, env: KGKB_PORT)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=os.environ.get("KGKB_RELOAD", "").lower() in ("1", "true", "yes"),
        help="Enable auto-reload for development (env: KGKB_RELOAD)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=int(os.environ.get("KGKB_WORKERS", "1")),
        help="Number of worker processes (default: 1, env: KGKB_WORKERS)",
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("KGKB_LOG_LEVEL", "info"),
        choices=["debug", "info", "warning", "error", "critical"],
        help="Log level (default: info, env: KGKB_LOG_LEVEL)",
    )

    args = parser.parse_args()

    # Step 1: Ensure data directory exists
    data_dir = ensure_data_dir()

    # Step 2: Initialize config if needed
    init_config(data_dir)

    # Step 3: Initialize database
    try:
        init_database(data_dir)
    except Exception as e:
        print(f"Warning: Database pre-init failed ({e}). Will initialize on first request.")

    # Step 4: Print banner and start server
    print_banner(args.host, args.port, args.reload)

    import uvicorn

    uvicorn.run(
        "backend.app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1,  # reload mode only works with 1 worker
        log_level=args.log_level,
        access_log=True,
    )


if __name__ == "__main__":
    main()
