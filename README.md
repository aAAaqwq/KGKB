# KGKB - Knowledge Graph Knowledge Base

<div align="center">

[![GitHub Stars](https://img.shields.io/github/stars/aAAaqwq/KGKB?style=flat-square&color=yellow)](https://github.com/aAAaqwq/KGKB/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/aAAaqwq/KGKB?style=flat-square)](https://github.com/aAAaqwq/KGKB/network)
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-green?style=flat-square&logo=python)](https://python.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-blue?style=flat-square&logo=typescript)](https://www.typescriptlang.org/)

**A graph-visualized, AI-predictive knowledge base that connects everything.**

*Store • Visualize • Connect • Predict*

[English](#overview) | [中文文档](docs/README-CN.md)

</div>

---

## Overview

KGKB is a next-generation knowledge management system that combines:
- **📍 Local-first storage** — Your data stays on your machine
- **🕸️ Graph visualization** — See knowledge connections at a glance
- **🔮 AI prediction** — Discover hidden patterns and predict trends
- **🔌 AI Agent integration** — Works with OpenClaw and other AI frameworks

Inspired by [GitNexus](https://github.com/abhigyanpatwari/GitNexus) (code graph) and [MiroFish](https://github.com/666ghj/MiroFish) (swarm intelligence), KGKB fuses knowledge graphs with predictive AI.

## Features

| Feature | Status | Description |
|---------|:------:|-------------|
| CLI Interface | ✅ | `kgkb add/query/list` commands |
| Vector Search | ✅ | Semantic search with FAISS/ChromaDB |
| Graph Visualization | ✅ | Interactive D3.js/Cytoscape.js web UI |
| Knowledge Linking | ✅ | Manual + AI-suggested connections |
| AI Prediction | 🚧 | Trend prediction based on graph patterns |
| OpenClaw Integration | 🚧 | Native knowledge provider for AI agents |
| Multi-Agent Simulation | 📅 | Swarm intelligence prediction |

## Screenshots

<div align="center">
<table>
<tr>
<td><img src="docs/screenshots/graph-view.png" alt="Graph View" width="100%"/></td>
<td><img src="docs/screenshots/search.png" alt="Semantic Search" width="100%"/></td>
</tr>
<tr>
<td align="center"><em>Knowledge Graph View</em></td>
<td align="center"><em>Semantic Search Results</em></td>
</tr>
</table>
</div>

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- SQLite3

### Installation

```bash
# Clone the repo
git clone https://github.com/aAAaqwq/KGKB.git
cd KGKB

# Install backend
pip install -r requirements.txt

# Install frontend
cd frontend && npm install && cd ..

# Initialize database
kgkb init
```

### Basic Usage

```bash
# Add knowledge
kgkb add "OpenAI released GPT-5 with 10x reasoning capability" \
  --tags "AI,GPT,OpenAI" \
  --source "https://openai.com/blog/gpt5"

# Query knowledge
kgkb query "latest AI developments" --limit 10

# List by tag
kgkb list --tag "AI"

# Start web UI
kgkb web
```

### Configuration

Create `~/.kgkb/config.yaml`:

```yaml
embedding:
  provider: ollama  # openai, ollama, local
  model: nomic-embed-text
  endpoint: http://localhost:11434

database:
  path: ~/.kgkb/kgkb.db

vector:
  backend: faiss  # faiss or chroma
  dimension: 768
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend (React)                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
│  │ Graph UI │  │ Search   │  │ Knowledge Editor     │  │
│  │ (D3.js)  │  │ Results  │  │                      │  │
│  └────┬─────┘  └────┬─────┘  └──────────┬───────────┘  │
└───────┼─────────────┼───────────────────┼──────────────┘
        │             │                   │
        └─────────────┼───────────────────┘
                      │ REST API
┌─────────────────────▼─────────────────────────────────┐
│                   Backend (FastAPI)                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐ │
│  │ Knowledge│  │ Vector   │  │ Graph Engine         │ │
│  │ Service  │  │ Search   │  │                      │ │
│  └────┬─────┘  └────┬─────┘  └──────────┬───────────┘ │
└───────┼─────────────┼───────────────────┼─────────────┘
        │             │                   │
┌───────▼─────────────▼───────────────────▼─────────────┐
│                    Storage Layer                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐ │
│  │ SQLite   │  │ FAISS/   │  │ Graph Store          │ │
│  │ (Meta)   │  │ Chroma   │  │ (Nodes + Edges)      │ │
│  └──────────┘  └──────────┘  └──────────────────────┘ │
└────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| **CLI** | Python Typer + Rich |
| **Backend** | FastAPI + SQLAlchemy |
| **Frontend** | React + TypeScript + Tailwind |
| **Visualization** | D3.js / Cytoscape.js |
| **Vector DB** | FAISS / ChromaDB |
| **Graph DB** | SQLite (adjacency list) |
| **Embedding** | OpenAI / Ollama / Local |

## API Reference

### REST API

```bash
# Add knowledge
POST /api/knowledge
{
  "content": "string",
  "tags": ["tag1", "tag2"],
  "source": "optional url"
}

# Search knowledge
GET /api/search?q={query}&limit={n}

# Get graph data
GET /api/graph?depth={n}

# Create relationship
POST /api/relations
{
  "source_id": "uuid",
  "target_id": "uuid",
  "type": "relates_to"
}
```

### CLI Commands

```bash
kgkb init                    # Initialize database
kgkb add <content>           # Add knowledge entry
kgkb query <text>            # Semantic search
kgkb list [--tag <tag>]      # List entries
kgkb link <id1> <id2>        # Create relationship
kgkb export [--format json]  # Export data
kgkb web                     # Start web server
kgkb config                  # Show configuration
```

## Roadmap

- [x] CLI interface (add/query/list)
- [x] Vector embedding with multiple providers
- [x] Graph visualization web UI
- [x] Manual knowledge linking
- [ ] AI-suggested relationships
- [ ] Basic trend prediction
- [ ] OpenClaw integration
- [ ] Multi-agent swarm simulation
- [ ] Plugin system

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [GitNexus](https://github.com/abhigyanpatwari/GitNexus) - Code graph inspiration
- [MiroFish](https://github.com/666ghj/MiroFish) - Swarm intelligence concepts
- [Obsidian](https://obsidian.md) - Knowledge management UX patterns

---

<div align="center">

**[⬆ Back to Top](#kgkb---knowledge-graph-knowledge-base)**

Made with ❤️ by the AGI Super Team

</div>
