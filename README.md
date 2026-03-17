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

### Installation

```bash
# Clone the repository
git clone https://github.com/aAAaqwq/KGKB.git
cd KGKB

# Set up backend
pip install -r requirements.txt

# Set up frontend
cd frontend && npm install && cd ..
```

### Run

```bash
# Start the backend API server
python backend/run.py
# → Runs on http://localhost:8000

# In another terminal, start the frontend dev server
cd frontend && npm run dev
# → Runs on http://localhost:5173
```

### Production Build

```bash
# Build the frontend
cd frontend && npm run build

# The built files go to frontend/dist/
# The backend can serve them as static files
```

---

## Usage

### CLI

```bash
# Add knowledge
kgkb add "OpenAI released GPT-5 with 10x reasoning capability" \
  --tags "AI,GPT,OpenAI" \
  --source "https://openai.com/blog/gpt5"

# Semantic search
kgkb query "latest AI developments" --limit 10

# List by tag
kgkb list --tag "AI"

# Link two entries
kgkb link <id1> <id2> --type "relates_to"

# Export all data
kgkb export --format json

# Start web server
kgkb web
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

Create `~/.kgkb/config.yaml`:

```yaml
# Embedding provider configuration
embedding:
  provider: ollama           # openai | ollama | local
  model: nomic-embed-text    # Model name
  endpoint: http://localhost:11434  # For ollama/local

# Database location
database:
  path: ~/.kgkb/kgkb.db

# Vector store
vector:
  backend: faiss             # faiss | chroma
  dimension: 768             # Must match embedding model
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KGKB_DB_PATH` | `~/.kgkb/kgkb.db` | SQLite database path |
| `KGKB_EMBEDDING_PROVIDER` | `ollama` | Embedding provider |
| `KGKB_EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model |
| `KGKB_EMBEDDING_ENDPOINT` | `http://localhost:11434` | Embedding API endpoint |

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

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
# Run backend in dev mode
python backend/run.py

# Run frontend in dev mode
cd frontend && npm run dev

# Type-check frontend
cd frontend && npx tsc --noEmit

# Build production frontend
cd frontend && npm run build
```

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
