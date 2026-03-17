# QMD → KGKB Integration Plan

> **Author**: 小code  
> **Date**: 2026-03-17  
> **Status**: Draft  
> **Depends on**: QMD v0.1.7+, KGKB v0.1.0

---

## 1. Current State Analysis

### 1.1 QMD Data Model

| Component | Details |
|-----------|---------|
| **Storage** | SQLite (`~/.cache/qmd/index.sqlite`, 649 MB) |
| **Documents** | 9,870 rows — `{id, collection, path, title, hash, created_at, modified_at, active}` |
| **Content** | 6,477 unique content hashes — `{hash, doc (full text), created_at}` |
| **Vectors** | 49,675 embeddings — `{hash, seq, pos, model, embedded_at}` stored via `sqlite-vec` |
| **Embedding model** | `embeddinggemma` (EmbeddingGemma-300M, estimated 256 dimensions, local GGUF) |
| **Collections** | 7: clawd-memory (6107), openclaw-config (1332), team (1308), skills (892), daily-memory (59), projects (47), reports (21) |
| **Chunking** | Long documents split into sequential chunks (`seq=0,1,2...`) with byte `pos` offset |
| **FTS** | SQLite FTS5 on documents (title, path, content) |
| **Unembedded** | 138 documents (Ollama remote unreachable) |

**Key design**: QMD is a **flat document index** — no relationships between documents. Content is addressed by hash (deduplication). Vectors are stored in `sqlite-vec` extension chunks. One document → many vector chunks.

### 1.2 KGKB Data Model

| Component | Details |
|-----------|---------|
| **Storage** | SQLite (`~/.kgkb/data.db`) + FAISS (`.kgkb/vectors.faiss`) |
| **Knowledge** | `{id (uuid), content, title, content_type, tags[], source, embedding, created_at, updated_at}` |
| **Relations** | `{id (uuid), source_id, target_id, type, weight, created_at}` |
| **Vectors** | FAISS IndexFlatIP (cosine via normalized vectors), dimension configurable (default 1024) |
| **Embedding model** | `qwen3-embedding:0.6b` via Ollama (1024d) or OpenAI compatible |
| **Graph** | BFS traversal from any node, edges typed (`relates_to`, `contains`, `references`, etc.) |

**Key design**: KGKB is a **knowledge graph** — nodes (Knowledge) connected by typed, weighted edges (Relations). Each node has exactly one embedding vector. Supports semantic search via FAISS.

### 1.3 Core Differences

| Dimension | QMD | KGKB |
|-----------|-----|------|
| **Unit** | File/document (path-based) | Knowledge entry (content-based) |
| **Identity** | Content hash | UUID |
| **Relationships** | None (flat) | Typed, weighted graph edges |
| **Embeddings** | embeddinggemma 256d (local) | qwen3-embedding 1024d (configurable) |
| **Vector store** | sqlite-vec (in SQLite) | FAISS (separate file) |
| **Chunking** | Multi-chunk per doc | One embedding per entry |
| **Metadata** | collection, path, title | tags, source, content_type |
| **Search** | BM25 + vector + reranking + query expansion | BM25 keyword + FAISS cosine |

---

## 2. Integration Architecture

```
┌─────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│   QMD       │     │  Integration Layer   │     │     KGKB        │
│             │     │                      │     │                 │
│ documents ──┼────▶│ 1. Extract & Map     │────▶│ knowledge       │
│ content   ──┼────▶│ 2. Re-embed (1024d)  │────▶│ FAISS vectors   │
│ collections─┼────▶│ 3. Infer relations   │────▶│ relations       │
│             │     │ 4. Sync state        │     │                 │
└─────────────┘     └──────────────────────┘     └─────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │  sync_state.json  │
                    │  (hash→uuid map)  │
                    └───────────────────┘
```

### Data Flow

1. **Extract**: Read QMD documents via `qmd get` or direct SQLite access
2. **Map**: Convert QMD document → KGKB Knowledge entry
3. **Re-embed**: Generate new embeddings with KGKB's model (dimension mismatch requires re-embedding)
4. **Infer Relations**: Use collection hierarchy, co-tags, and semantic similarity to create graph edges
5. **Track State**: Maintain hash→uuid mapping for incremental sync

---

## 3. Data Mapping

### 3.1 Document → Knowledge Entry

```python
# QMD document fields → KGKB knowledge fields
{
    # QMD                        # KGKB
    "id": doc_id,                # → (ignored, new uuid generated)
    "path": "2026-03-17.md",     # → source = f"qmd://{collection}/{path}"
    "title": "Daily Memory",     # → title
    "collection": "daily-memory",# → tags = [collection, ...extracted_tags]
    "doc": "# Full content...",  # → content
    "hash": "abc123...",         # → (stored in sync_state for tracking)
    "modified_at": "...",        # → updated_at
    "created_at": "...",         # → created_at
}
```

### 3.2 Collection → Tag Mapping

| QMD Collection | KGKB Tags |
|----------------|-----------|
| `clawd-memory` | `["memory", "clawd"]` |
| `daily-memory` | `["daily", "memory"]` |
| `team` | `["team", "config"]` |
| `openclaw-config` | `["openclaw", "config"]` |
| `projects` | `["project"]` |
| `skills` | `["skill"]` |
| `reports` | `["report"]` |

### 3.3 Relation Inference Strategies

Since QMD has no explicit relationships, we infer them:

| Strategy | Type | Weight | Description |
|----------|------|--------|-------------|
| **Same collection** | `belongs_to` | 0.3 | Docs in same collection share a weak link |
| **Same date** | `co-temporal` | 0.5 | Daily memory entries from same date |
| **Path hierarchy** | `contains` | 0.7 | Parent/child paths (e.g. `docs/` contains `docs/prd.md`) |
| **Semantic similarity** | `similar_to` | cosine score | FAISS top-k neighbors above threshold (>0.8) |
| **Cross-reference** | `references` | 0.9 | Markdown links or mentions of other document paths |

---

## 4. Implementation Phases

### Phase 1: Basic Import (MVP — 2 days)

- [ ] `qmd_import.py` — Read QMD SQLite directly, convert documents to KGKB format
- [ ] Generate new embeddings via KGKB's embedding service
- [ ] Insert into KGKB SQLite + FAISS
- [ ] Track sync state (`sync_state.json`: QMD hash → KGKB uuid)
- [ ] Scope: `daily-memory` collection only (~59 docs)

### Phase 2: Relation Inference (3 days)

- [ ] Implement path-based `contains` relations
- [ ] Implement collection-based `belongs_to` relations
- [ ] Implement semantic `similar_to` (FAISS k-NN post-import)
- [ ] Implement cross-reference detection (markdown link parsing)

### Phase 3: Full Sync Pipeline (3 days)

- [ ] Extend to all 7 collections
- [ ] Incremental sync (only new/updated hashes)
- [ ] `kgkb sync qmd` CLI command
- [ ] Configurable sync: collection whitelist, tag overrides, relation thresholds

### Phase 4: Live Integration (future)

- [ ] QMD webhook/watcher → auto-import on `qmd update`
- [ ] Bidirectional: KGKB edits propagate back to markdown files
- [ ] Shared embedding model alignment

---

## 5. Technical Challenges & Solutions

### 5.1 Embedding Dimension Mismatch ⚠️ Critical

**Problem**: QMD uses `embeddinggemma` (256d), KGKB uses `qwen3-embedding:0.6b` (1024d). Vectors are incompatible — cannot directly migrate.

**Solution**: Re-embed all imported documents using KGKB's model. This means:
- Extra compute cost (~10K docs × embedding API call)
- But ensures consistent search quality within KGKB
- QMD vectors remain untouched (QMD continues working independently)

**Optimization**: Batch embedding (10 docs/request for OpenAI, sequential for Ollama) with progress tracking.

### 5.2 Chunking Strategy Difference

**Problem**: QMD chunks long documents into multiple vectors (`seq=0,1,2...`). KGKB stores one embedding per knowledge entry.

**Solution**: Two options:
- **Option A (simple)**: Import full document as single entry, embed the whole content. Loses granularity for long docs but simplest.
- **Option B (preserve)**: Split QMD chunks into separate KGKB entries linked by `chunk_of` relations. More complex but preserves search precision.

**Recommendation**: Start with **Option A** for MVP. Long documents (>2000 chars) get truncated for embedding but stored in full. Add Option B in Phase 3.

### 5.3 Ollama Availability

**Problem**: Remote Ollama at `100.65.110.126:11434` is currently unreachable. Both QMD embed and KGKB embedding fail without it.

**Solution**:
- POC uses a mock/fallback embedding (random vectors for testing pipeline)
- Production requires Ollama to be running on Daniel's Studio or local machine
- Add health check before sync: skip embedding if Ollama is down, queue for later

### 5.4 Scale Concerns

**Problem**: Importing all 9,870 QMD docs with re-embedding + relation inference is compute-heavy.

**Solution**:
- Phase 1 imports only `daily-memory` (59 docs) as proof of concept
- Batch processing with progress bars
- Estimate: ~5 min for 59 docs, ~2 hours for full 9,870 (Ollama on GPU)

---

## 6. Work Estimate

| Phase | Effort | Dependencies |
|-------|--------|--------------|
| Phase 1: Basic Import | 2 days | Ollama running (or mock for testing) |
| Phase 2: Relations | 3 days | Phase 1 complete |
| Phase 3: Full Sync | 3 days | Phase 2 complete |
| Phase 4: Live | TBD | Phase 3 stable |
| **Total MVP (P1+P2)** | **5 days** | |

---

## 7. POC Scope

The accompanying `scripts/qmd_import_poc.py` demonstrates Phase 1:

1. Read 10 most recent `daily-memory` documents from QMD SQLite
2. Map to KGKB Knowledge format
3. Generate embeddings (with fallback to mock if Ollama unavailable)
4. Insert into KGKB SQLite + FAISS
5. Verify search works via KGKB API

Success criteria: Can `kgkb query "daily memory"` and find imported QMD documents.
