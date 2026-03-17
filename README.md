# KGKB — Knowledge Graph Knowledge Base

<div align="center">

[![GitHub Stars](https://img.shields.io/github/stars/aAAaqwq/KGKB?style=flat-square&color=yellow)](https://github.com/aAAaqwq/KGKB/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/aAAaqwq/KGKB?style=flat-square)](https://github.com/aAAaqwq/KGKB/network)
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-green?style=flat-square&logo=python)](https://python.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-blue?style=flat-square&logo=typescript)](https://www.typescriptlang.org/)

**A graph-visualized, AI-predictive knowledge base that connects everything.**

*Store · Visualize · Connect · Predict*

[English](#overview) · [中文文档](docs/README-CN.md) · [API Reference](docs/API.md)

</div>

---

## Overview

KGKB is a **local-first** knowledge management system that stores your knowledge as a graph. Instead of flat notes or folders, every piece of knowledge becomes a **node** and every connection becomes an **edge** — creating a living network of ideas you can explore, search, and visualize.

### Why KGKB?

| Feature | KGKB | Notion | Obsidian |
|---------|:----:|:------:|:--------:|
| **Local-first** | ✅ | ❌ | ✅ |
| **Graph visualization** | ✅ Interactive D3.js | ❌ | ⚠️ Plugin |
| **Semantic search** | ✅ FAISS/Ollama | ❌ | ❌ |
| **CLI interface** | ✅ | ❌ | ❌ |
| **REST API** | ✅ | ❌ | ❌ |
| **AI Agent integration** | ✅ OpenClaw | ❌ | ❌ |
| **Open source** | ✅ MIT | ❌ | ⚠️ Partial |

### Core Features

- 🧠 **Smart Storage** — SQLite-backed with full-text search and tagging
- 🕸️ **Interactive Graph** — D3.js force-directed visualization with zoom, filter, and link mode
- 🔍 **Triple Search** — Text, semantic (vector), and hybrid search modes
- 🔗 **Knowledge Linking** — Create typed, weighted relationships between entries
- 📥 **Import/Export** — JSON import/export for portability
- 🖥️ **CLI + Web** — Full CLI for power users, polished React web UI for everyone else
- 🌙 **Dark Theme** — Carefully designed dark UI with responsive mobile layout

---

## Quick Start

### Prerequisites

- **Python 3.11+** — Backend and CLI
- **Node.js 18+** — Frontend build
- **SQLite3** — Included with Python

### Quick Start (One Command)

```bash
git clone https://github.com/aAAaqwq/KGKB.git
cd KGKB
./start.sh
```

That's it. The script creates a Python venv, installs all dependencies, and starts both servers:

| Service | URL |
|---------|-----|
| **Web UI** | http://localhost:5173 |
| **API** | http://localhost:8000 |
| **API Docs** | http://localhost:8000/docs |

Press `Ctrl+C` to stop everything.

### Manual Installation

```bash
# Clone
git clone https://github.com/aAAaqwq/KGKB.git
cd KGKB

# Backend (use a virtualenv)
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend && npm install && cd ..
```

### Manual Run

```bash
# Terminal 1: Backend
source venv/bin/activate
python backend/run.py --reload
# → http://localhost:8000

# Terminal 2: Frontend
cd frontend && npm run dev
# → http://localhost:5173
```

### Production (Docker)

```bash
# Start with Docker Compose
./start-prod.sh

# Or with custom ports
KGKB_FRONTEND_PORT=80 KGKB_BACKEND_PORT=9000 ./start-prod.sh

# Force rebuild after code changes
./start-prod.sh --build

# View logs / status / stop
./start-prod.sh --logs
./start-prod.sh --status
./start-prod.sh --stop
```

### Build Frontend for Production

```bash
cd frontend && npm run build
# Output: frontend/dist/ (serve with any static file server)
```

---

## Usage

### CLI

The CLI works directly against the SQLite database (no server needed).

```bash
# ── Add Knowledge ──────────────────────────────────
# From text
kgkb add "Transformers use self-attention for sequence modeling" \
  --tags "ML,NLP,architecture" \
  --source "https://arxiv.org/abs/1706.03762"

# From a file
kgkb add --file notes/paper-summary.md --tags "research,summary"

# Specify content type
kgkb add "https://example.com/tutorial" --type url --tags "tutorial"

# ── Search ─────────────────────────────────────────
# Semantic search (requires embedding service)
kgkb query "how do neural networks learn representations" --limit 5

# Text search (works without embeddings)
kgkb search "transformer" --json   # JSON output for scripting

# ── Browse ─────────────────────────────────────────
kgkb list                          # All entries (paginated)
kgkb list --tag "ML" --limit 20   # Filter by tag

# ── Link Knowledge ─────────────────────────────────
kgkb link abc123 def456 --type "builds_on"
kgkb relations abc123             # Show all connections
kgkb unlink abc123 def456        # Remove a link

# ── Manage ─────────────────────────────────────────
kgkb delete abc123               # Delete (with confirmation)

# ── Import / Export ────────────────────────────────
kgkb export --format json > backup.json
kgkb import backup.json

# ── Configuration ──────────────────────────────────
kgkb config                       # Show current config
kgkb config --embedding-provider ollama
kgkb config --embedding-model "qwen3-embedding:0.6b"
kgkb config --embedding-endpoint "http://localhost:11434"

# ── Web Server ─────────────────────────────────────
kgkb web                          # Starts backend on :8000
```

### Web UI

The web interface provides four main views:

| View | Path | Description |
|------|------|-------------|
| **Graph** | `/` | Interactive force-directed knowledge graph |
| **List** | `/list` | Browse, filter, and manage all entries |
| **Search** | `/search` | Text, semantic, and hybrid search |
| **Add** | `/add` | Create new knowledge entries |

**Keyboard shortcuts:**
- `Ctrl/⌘ + K` — Focus search
- `Ctrl/⌘ + N` — Add new knowledge
- `+` / `-` / `0` / `F` — Zoom controls (graph view)
- `Esc` — Close panels

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend (React)                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
│  │ Graph UI │  │ Search   │  │ Knowledge CRUD       │  │
│  │ (D3.js)  │  │ View     │  │ (List/Add/Detail)    │  │
│  └────┬─────┘  └────┬─────┘  └──────────┬───────────┘  │
│       └──────────────┼───────────────────┘              │
│                      │ Axios HTTP Client                │
└──────────────────────┼──────────────────────────────────┘
                       │ REST API (JSON)
┌──────────────────────▼──────────────────────────────────┐
│                   Backend (FastAPI)                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
│  │ Knowledge│  │ Vector   │  │ Graph Engine         │  │
│  │ Service  │  │ Store    │  │ (Nodes + Relations)  │  │
│  └────┬─────┘  └────┬─────┘  └──────────┬───────────┘  │
└───────┼─────────────┼───────────────────┼───────────────┘
        │             │                   │
┌───────▼─────────────▼───────────────────▼───────────────┐
│                    Storage Layer                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
│  │ SQLite   │  │ FAISS    │  │ Adjacency List       │  │
│  │ (Data)   │  │ (Vectors)│  │ (Relations)          │  │
│  └──────────┘  └──────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Tech Stack

| Layer | Technology |
|-------|------------|
| **CLI** | Python + Typer + Rich |
| **Backend** | FastAPI + SQLAlchemy + Pydantic |
| **Frontend** | React 18 + TypeScript + Tailwind CSS |
| **Visualization** | D3.js (force-directed graph) |
| **Vector DB** | FAISS (with Ollama/OpenAI embeddings) |
| **Database** | SQLite |
| **Build** | Vite |

### Project Structure

```
knowledge-graph-kb/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app + routes
│   │   ├── models/           # SQLAlchemy models
│   │   └── services/         # Business logic
│   │       ├── knowledge.py  # Knowledge CRUD
│   │       ├── embedding.py  # Embedding provider
│   │       └── vector_store.py # FAISS vector store
│   └── run.py                # Entry point
├── frontend/
│   ├── src/
│   │   ├── api/client.ts     # Typed API client
│   │   ├── components/       # Reusable UI components
│   │   │   ├── ConfirmDialog.tsx
│   │   │   ├── EmptyState.tsx
│   │   │   ├── GraphFilters.tsx
│   │   │   ├── LinkModeDialog.tsx
│   │   │   ├── LoadingSpinner.tsx
│   │   │   ├── NodeDetailPanel.tsx
│   │   │   └── Toast.tsx
│   │   ├── hooks/            # Custom React hooks
│   │   │   └── useKeyboard.ts
│   │   ├── views/            # Page-level components
│   │   │   ├── KnowledgeGraph.tsx
│   │   │   ├── KnowledgeList.tsx
│   │   │   ├── KnowledgeDetail.tsx
│   │   │   ├── SearchView.tsx
│   │   │   └── AddKnowledge.tsx
│   │   ├── App.tsx           # Root layout + routing
│   │   └── main.tsx          # Entry point
│   ├── tailwind.config.js
│   └── vite.config.ts
├── cli/                      # CLI tool
├── docs/                     # Documentation
│   ├── PRD.md
│   └── API.md
├── tests/
├── requirements.txt
└── README.md
```

---

## API Reference

Full API documentation: **[docs/API.md](docs/API.md)**

### Quick Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/knowledge` | Create knowledge entry |
| `GET` | `/api/knowledge` | List entries (paginated) |
| `GET` | `/api/knowledge/:id` | Get single entry |
| `PUT` | `/api/knowledge/:id` | Update entry |
| `DELETE` | `/api/knowledge/:id` | Delete entry |
| `GET` | `/api/knowledge/search` | Search (text/semantic/hybrid) |
| `GET` | `/api/tags` | List all tags |
| `POST` | `/api/relations` | Create relation |
| `GET` | `/api/relations` | List relations |
| `DELETE` | `/api/relations/:id` | Delete relation |
| `GET` | `/api/graph` | Get graph data |
| `POST` | `/api/import` | Bulk import |
| `GET` | `/api/export` | Export all data |
| `GET` | `/api/health` | Health check |
| `GET` | `/api/stats` | Database statistics |

---

## Configuration

KGKB stores its data and config in `~/.kgkb/`:

```
~/.kgkb/
├── config.json       # Main configuration (auto-created on first run)
├── data.db           # SQLite database
└── vectors.faiss     # FAISS vector index
```

### Config File (`~/.kgkb/config.json`)

Auto-created on first run. Edit directly or use `kgkb config`:

```json
{
  "embedding": {
    "provider": "ollama",
    "model": "qwen3-embedding:0.6b",
    "endpoint": "http://localhost:11434",
    "dimension": 1024,
    "api_key": null
  },
  "database": {
    "path": "~/.kgkb/data.db"
  },
  "vector": {
    "backend": "faiss",
    "dimension": 1024
  }
}
```

### Embedding Providers

| Provider | Config | Notes |
|----------|--------|-------|
| **Ollama** (default) | `provider: "ollama"` | Free, local. Install [Ollama](https://ollama.ai), then `ollama pull qwen3-embedding:0.6b` |
| **OpenAI** | `provider: "openai"`, set `api_key` | Requires API key. Uses `text-embedding-3-small` by default |
| **Custom** | `provider: "custom"`, set `endpoint` | Any OpenAI-compatible embedding API |

> **Note**: Semantic search requires a running embedding service. Text search and all other features work without one.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KGKB_DATA_DIR` | `~/.kgkb` | Data directory (useful for Docker) |
| `KGKB_DB_PATH` | `~/.kgkb/data.db` | SQLite database path |
| `KGKB_HOST` | `0.0.0.0` | Backend bind host |
| `KGKB_PORT` | `8000` | Backend bind port |
| `KGKB_LOG_LEVEL` | `info` | Log level (`debug`/`info`/`warning`/`error`) |
| `KGKB_EMBEDDING_PROVIDER` | `ollama` | Embedding provider |
| `KGKB_EMBEDDING_MODEL` | `qwen3-embedding:0.6b` | Embedding model |
| `KGKB_EMBEDDING_ENDPOINT` | `http://localhost:11434` | Embedding API endpoint |
| `KGKB_BACKEND_PORT` | `8000` | Docker: backend exposed port |
| `KGKB_FRONTEND_PORT` | `3000` | Docker: frontend exposed port |

---

## Roadmap

- [x] Knowledge CRUD with SQLite storage
- [x] CLI interface (`kgkb add/query/list`)
- [x] Vector embedding with FAISS
- [x] RESTful API (FastAPI)
- [x] Interactive graph visualization (D3.js)
- [x] Knowledge linking (manual + Link Mode)
- [x] Text, semantic, and hybrid search
- [x] Tag filtering and search-in-graph
- [x] Import/export (JSON)
- [x] Dark theme + responsive layout
- [x] Keyboard shortcuts
- [ ] AI-suggested relationships
- [ ] Trend prediction (graph pattern analysis)
- [ ] OpenClaw native integration
- [ ] Plugin system

---

## Development

```bash
# Quick start (installs deps + starts servers with hot reload)
./start.sh

# Or start individually:
./start.sh --backend    # Backend only (with auto-reload)
./start.sh --frontend   # Frontend only
./start.sh --install    # Install deps without starting

# Type-check frontend
cd frontend && npx tsc --noEmit

# Lint Python
ruff check backend/ cli/

# Run tests
python -m pytest tests/

# Build production frontend
cd frontend && npm run build
```

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) for details.

## Acknowledgments

- [D3.js](https://d3js.org/) — Force-directed graph engine
- [FastAPI](https://fastapi.tiangolo.com/) — Modern Python API framework
- [FAISS](https://github.com/facebookresearch/faiss) — Vector similarity search
- [Tailwind CSS](https://tailwindcss.com/) — Utility-first CSS

---

<div align="center">

Made with 🧠 by the AGI Super Team

</div>
