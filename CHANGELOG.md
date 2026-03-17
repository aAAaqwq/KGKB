# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] — 2026-03-17

### Added

#### Backend Foundation
- **SQLite storage layer** with proper schema for `knowledge_nodes`, `knowledge_relations`, and `embeddings` tables. Auto-creates `~/.kgkb/data.db` with migration support.
- **Knowledge CRUD API** — `POST/GET/PUT/DELETE /api/knowledge` with pagination, tag filtering, and consistent JSON responses.
- **Relation CRUD API** — `POST/DELETE /api/relations`, `GET /api/graph` for graph rendering data.
- **Embedding service** — Ollama integration (default: `qwen3-embedding:0.6b`) with OpenAI API and custom endpoint fallback. Configurable via `~/.kgkb/config.json`.
- **FAISS vector store** — `add_vector`, `search_similar`, `delete_vector` with persistent index at `~/.kgkb/vectors.faiss`. Configurable dimension (default 1024).
- **Semantic search** — `GET /api/knowledge/search?q=&mode=semantic|text|hybrid` combining SQLite FTS and FAISS similarity.
- **Backend startup** — `backend/run.py` with CLI args, CORS middleware, `/api/health` and `/api/stats` endpoints.
- **Import/export** — `POST /api/import` for bulk JSON import, `GET /api/export?format=json|markdown`.

#### CLI
- **`kgkb add`** — Add knowledge with `--tags`, `--source`, `--type`, `--file` support. Auto-triggers embedding.
- **`kgkb query`** — Semantic search with formatted Rich table output.
- **`kgkb search`** — Text search with `--json` output option.
- **`kgkb list`** — List entries with `--tag`, `--limit`, `--offset` filters.
- **`kgkb link/unlink`** — Create and remove typed relations between nodes.
- **`kgkb relations`** — Show a node's connections.
- **`kgkb delete`** — Delete with confirmation prompt.
- **`kgkb export/import`** — JSON export and file import.
- **`kgkb config`** — View and set embedding provider/URL.

#### Frontend (React + TypeScript + Tailwind)
- **Knowledge list view** — Search bar, tag filter chips, pagination, expandable cards, delete with confirmation.
- **Add knowledge form** — Title, content (Markdown), tag chips, source URL, content type selector with validation.
- **Search view** — Mode toggle (text/semantic/hybrid), relevance score badges, loading states.
- **Knowledge detail page** — Full entry view with inline edit mode, relations display, navigation.
- **Knowledge graph** — D3.js force-directed layout with:
  - Zoom, pan, drag interactions
  - Node coloring by tag, sizing by connection count
  - Side panel with full node details on click
  - Tag filtering with legend and node/edge counts
  - Search-in-graph to highlight matching nodes
  - **Link Mode** — Click two nodes to create a relation
  - Minimap, edge labels, smooth animations
- **Dark theme** — Consistent palette (`gray-900` bg, `gray-800` cards, `blue-400` accent), responsive mobile layout.
- **UX polish** — Loading spinners, skeleton loaders, empty states, toast notifications, confirm dialogs, keyboard shortcuts (`Ctrl+K` search, `Ctrl+N` new), breadcrumbs, debounced search, tag autocomplete.
- **Vite proxy** configured for seamless frontend↔backend development.

#### DevOps
- **Dockerfile.backend** — Multi-stage Python 3.11 slim build with non-root user.
- **Dockerfile.frontend** — Node 20 build stage + Nginx static serve.
- **docker-compose.yml** — Backend + frontend services, health checks, persistent volume, configurable ports via env vars.
- **`start.sh`** — One-command dev startup (venv setup, pip install, npm install, start both servers).
- **`start-prod.sh`** — Docker Compose production startup with build, stop, logs, status, and cleanup commands.

### Technical Details

- **Backend**: Python 3.11 / FastAPI / SQLAlchemy / Pydantic v2
- **Frontend**: React 18 / TypeScript 5 / Tailwind CSS / Vite
- **Visualization**: D3.js force-directed graph
- **Vector search**: FAISS with Ollama/OpenAI embeddings
- **Database**: SQLite (zero-config, local-first)
- **CLI**: Typer + Rich for polished terminal output
