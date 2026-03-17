#!/usr/bin/env python3
"""
KGKB Task #30 — End-to-End Verification Script

Runs the full E2E pipeline against a live backend:
  1. Health check
  2. Create knowledge nodes
  3. Add relations
  4. Search (text, semantic fallback)
  5. Graph visualization data
  6. Import / Export round-trip
  7. Update / Delete
  8. Stats verification

Output: structured JSON report → docs/E2E-VERIFICATION.md
"""

import json
import sys
import time
import requests
from datetime import datetime, timezone

BASE = "http://localhost:8000"
report = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "version": "0.1.0",
    "results": [],
    "errors": [],
    "summary": {"passed": 0, "failed": 0, "skipped": 0},
}

def step(name, func):
    """Run a test step and record result."""
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    try:
        result = func()
        report["summary"]["passed"] += 1
        report["results"].append({"step": name, "status": "✅ PASS", "detail": str(result)})
        print(f"  ✅ PASS: {result}")
        return result
    except Exception as e:
        report["summary"]["failed"] += 1
        report["results"].append({"step": name, "status": "❌ FAIL", "detail": str(e)})
        report["errors"].append({"step": name, "error": str(e)})
        print(f"  ❌ FAIL: {e}")
        return None


def test_health():
    """Step 1: Health check."""
    r = requests.get(f"{BASE}/api/health", timeout=5)
    assert r.status_code == 200, f"HTTP {r.status_code}"
    data = r.json()
    assert data["status"] == "healthy"
    assert data["services"]["database"] is True
    return f"healthy | db={data['services']['database']} | embed={data['services']['embedding']} | vectors={data['counts']['vectors']}"


def test_create_nodes():
    """Step 2: Create 5 knowledge nodes."""
    nodes = [
        {"title": "OpenClaw", "content": "OpenClaw is an open-source AI agent framework that runs locally with persistent memory, multi-channel messaging, and browser automation.", "content_type": "concept", "tags": ["ai", "agent", "framework", "open-source"]},
        {"title": "FastAPI", "content": "FastAPI is a modern Python web framework for building APIs with automatic validation and documentation.", "content_type": "technology", "tags": ["python", "web", "api"]},
        {"title": "FAISS", "content": "Facebook AI Similarity Search (FAISS) is a library for efficient similarity search and clustering of dense vectors.", "content_type": "technology", "tags": ["vector", "search", "ai"]},
        {"title": "Knowledge Graph", "content": "A knowledge graph represents entities as nodes and relationships as edges, enabling semantic reasoning and discovery.", "content_type": "concept", "tags": ["graph", "data", "ai"]},
        {"title": "Daniel Li & AI Team", "content": "Daniel Li leads an AI Super Team of 13 specialized agents that handle development, content creation, trading, and operations 24/7.", "content_type": "team", "tags": ["team", "agi", "agent"]},
    ]
    created = []
    for n in nodes:
        r = requests.post(f"{BASE}/api/knowledge", json=n, timeout=5)
        assert r.status_code == 201, f"Create failed: {r.status_code} {r.text}"
        created.append(r.json())
    report["_node_ids"] = [n["id"] for n in created]
    return f"Created {len(created)} nodes: {[n['title'] for n in created]}"


def test_add_relations():
    """Step 3: Add relations between nodes."""
    ids = report["_node_ids"]
    relations = [
        {"source_id": ids[0], "target_id": ids[1], "type": "uses", "weight": 1.0},  # OpenClaw uses FastAPI
        {"source_id": ids[0], "target_id": ids[2], "type": "uses", "weight": 0.8},  # OpenClaw uses FAISS
        {"source_id": ids[3], "target_id": ids[0], "type": "related_to", "weight": 0.7},  # KG related to OpenClaw
        {"source_id": ids[4], "target_id": ids[0], "type": "develops", "weight": 1.0},  # Team develops OpenClaw
        {"source_id": ids[1], "target_id": ids[2], "type": "integrates_with", "weight": 0.5},  # FastAPI + FAISS
    ]
    created = []
    for rel in relations:
        r = requests.post(f"{BASE}/api/relations", json=rel, timeout=5)
        assert r.status_code == 201, f"Relation failed: {r.status_code} {r.text}"
        created.append(r.json())
    return f"Created {len(created)} relations"


def test_text_search():
    """Step 4a: Text search."""
    r = requests.get(f"{BASE}/api/knowledge/search", params={"q": "AI agent", "mode": "text", "limit": 5}, timeout=5)
    assert r.status_code == 200, f"Search failed: {r.status_code}"
    data = r.json()
    assert data["total"] >= 1, "Should find at least 1 result"
    return f"Found {data['total']} results for 'AI agent' (top: {data['results'][0]['title'] if data['results'] else 'N/A'})"


def test_semantic_search_fallback():
    """Step 4b: Semantic search (fallback to text if no embedding service)."""
    r = requests.get(f"{BASE}/api/knowledge/search", params={"q": "vector similarity library", "mode": "semantic", "limit": 5}, timeout=5)
    assert r.status_code == 200, f"Semantic search failed: {r.status_code}"
    data = r.json()
    return f"Semantic search: {data['total']} results, mode={data['mode']}"


def test_hybrid_search():
    """Step 4c: Hybrid search."""
    r = requests.get(f"{BASE}/api/knowledge/search", params={"q": "python web framework", "mode": "hybrid", "limit": 5}, timeout=5)
    assert r.status_code == 200, f"Hybrid search failed: {r.status_code}"
    data = r.json()
    return f"Hybrid search: {data['total']} results"


def test_no_results():
    """Step 4d: Search with no results."""
    r = requests.get(f"{BASE}/api/knowledge/search", params={"q": "xyznonexistent12345", "mode": "text"}, timeout=5)
    assert r.status_code == 200
    assert r.json()["total"] == 0
    return "Correctly returns 0 results for gibberish"


def test_graph_data():
    """Step 5: Graph visualization."""
    r = requests.get(f"{BASE}/api/graph", params={"depth": 2}, timeout=5)
    assert r.status_code == 200
    data = r.json()
    assert len(data["nodes"]) >= 5, f"Expected >=5 nodes, got {len(data['nodes'])}"
    assert len(data["edges"]) >= 4, f"Expected >=4 edges, got {len(data['edges'])}"
    return f"Graph: {len(data['nodes'])} nodes, {len(data['edges'])} edges"

def test_graph_subgraph():
    """Step 5b: Subgraph around a node."""
    node_id = report["_node_ids"][0]  # OpenClaw
    r = requests.get(f"{BASE}/api/graph", params={"node_id": node_id, "depth": 1}, timeout=5)
    assert r.status_code == 200
    data = r.json()
    return f"Subgraph: {len(data['nodes'])} nodes, {len(data['edges'])} edges (centered on OpenClaw)"


def test_export_json():
    """Step 6a: Export JSON."""
    r = requests.get(f"{BASE}/api/export", params={"format": "json"}, timeout=5)
    assert r.status_code == 200
    data = r.json()
    assert data["stats"]["knowledge_count"] >= 5
    report["_export_data"] = data
    return f"Exported: {data['stats']['knowledge_count']} entries, {data['stats']['relation_count']} relations"


def test_export_markdown():
    """Step 6b: Export Markdown."""
    r = requests.get(f"{BASE}/api/export", params={"format": "markdown"}, timeout=5)
    assert r.status_code == 200
    assert "KGKB Knowledge Export" in r.text
    return f"Markdown export: {len(r.text)} chars"


def test_import():
    """Step 6c: Import round-trip."""
    items = [
        {"title": "Imported Node 1", "content": "This was imported via the API.", "tags": ["import-test"]},
        {"title": "Imported Node 2", "content": "Another imported node.", "tags": ["import-test"]},
        {"content": ""},  # Should be skipped
    ]
    r = requests.post(f"{BASE}/api/import", json=items, timeout=5)
    assert r.status_code == 201
    data = r.json()
    assert data["imported"] == 2
    assert data["skipped"] == 1
    report["_imported_ids"] = []  # IDs tracked via tags
    return f"Imported {data['imported']}, skipped {data['skipped']}, errors: {len(data['errors'])}"


def test_update():
    """Step 7a: Update a node."""
    kid = report["_node_ids"][0]
    r = requests.put(f"{BASE}/api/knowledge/{kid}", json={"title": "OpenClaw (Updated)", "tags": ["ai", "agent", "framework", "updated"]}, timeout=5)
    assert r.status_code == 200
    assert r.json()["title"] == "OpenClaw (Updated)"
    return "Updated node title and tags"


def test_tag_filter():
    """Step 7b: Filter by tag."""
    r = requests.get(f"{BASE}/api/knowledge", params={"tag": "import-test"}, timeout=5)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 2, f"Expected >=2 import-test entries, got {data['total']}"
    return f"Tag filter 'import-test': {data['total']} entries"


def test_tags_list():
    """Step 7c: List all tags."""
    r = requests.get(f"{BASE}/api/tags", timeout=5)
    assert r.status_code == 200
    tags = r.json()
    assert "ai" in tags
    assert "import-test" in tags
    return f"{len(tags)} tags: {', '.join(sorted(tags)[:10])}..."


def test_relation_types():
    """Step 7d: List relation types."""
    r = requests.get(f"{BASE}/api/relations/types", timeout=5)
    assert r.status_code == 200
    types = r.json()
    assert "uses" in types
    return f"Relation types: {types}"


def test_delete_node():
    """Step 8a: Delete a node."""
    # First create one to delete
    r = requests.post(f"{BASE}/api/knowledge", json={"content": "This will be deleted.", "tags": ["delete-me"]}, timeout=5)
    assert r.status_code == 201
    kid = r.json()["id"]
    
    # Delete it
    r = requests.delete(f"{BASE}/api/knowledge/{kid}", timeout=5)
    assert r.status_code == 200
    assert r.json()["status"] == "deleted"
    
    # Verify gone
    r = requests.get(f"{BASE}/api/knowledge/{kid}", timeout=5)
    assert r.status_code == 404
    return "Created → Deleted → Verified 404"


def test_delete_relation():
    """Step 8b: Delete a relation."""
    # Get list of relations
    r = requests.get(f"{BASE}/api/relations", params={"type": "integrates_with"}, timeout=5)
    assert r.status_code == 200
    data = r.json()
    if data["items"]:
        rid = data["items"][0]["id"]
        r = requests.delete(f"{BASE}/api/relations/{rid}", timeout=5)
        assert r.status_code == 200
        return f"Deleted relation {rid[:8]}"
    return "No relations of type 'integrates_with' to delete (skipped)"


def test_stats():
    """Step 9: Final stats."""
    r = requests.get(f"{BASE}/api/stats", timeout=5)
    assert r.status_code == 200
    data = r.json()
    report["_final_stats"] = data
    return f"Knowledge: {data.get('knowledge_count', '?')} | Relations: {data.get('relation_count', '?')} | Tags: {data.get('tag_count', '?')}"


def test_embedding_status():
    """Step 10: Embedding service status."""
    r = requests.get(f"{BASE}/api/embedding/status", timeout=5)
    assert r.status_code == 200
    data = r.json()
    return f"Provider: {data.get('provider', 'N/A')} | Available: {data.get('available', False)}"


# ===== Run all steps =====
def main():
    print("=" * 60)
    print("  KGKB Task #30 — End-to-End Verification")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Check backend is up
    try:
        requests.get(f"{BASE}/", timeout=3)
    except Exception as e:
        print(f"\n❌ Backend not reachable at {BASE}: {e}")
        print("Start with: cd ~/clawd/projects/knowledge-graph-kb && source .venv/bin/activate && python -m uvicorn backend.app.main:app --port 8000")
        sys.exit(1)

    steps = [
        ("1. Health Check", test_health),
        ("2. Create Knowledge Nodes (5)", test_create_nodes),
        ("3. Add Relations (5)", test_add_relations),
        ("4a. Text Search", test_text_search),
        ("4b. Semantic Search (fallback)", test_semantic_search_fallback),
        ("4c. Hybrid Search", test_hybrid_search),
        ("4d. No-Results Search", test_no_results),
        ("5a. Graph Data (full)", test_graph_data),
        ("5b. Graph Subgraph (centered)", test_graph_subgraph),
        ("6a. Export JSON", test_export_json),
        ("6b. Export Markdown", test_export_markdown),
        ("6c. Import (round-trip)", test_import),
        ("7a. Update Node", test_update),
        ("7b. Tag Filter", test_tag_filter),
        ("7c. List Tags", test_tags_list),
        ("7d. Relation Types", test_relation_types),
        ("8a. Delete Node", test_delete_node),
        ("8b. Delete Relation", test_delete_relation),
        ("9. Final Stats", test_stats),
        ("10. Embedding Status", test_embedding_status),
    ]

    for name, func in steps:
        step(name, func)
        time.sleep(0.2)

    # Print summary
    print(f"\n{'='*60}")
    print(f"  SUMMARY: {report['summary']['passed']} passed, {report['summary']['failed']} failed")
    print(f"{'='*60}")

    if report["errors"]:
        print("\nErrors:")
        for e in report["errors"]:
            print(f"  ❌ {e['step']}: {e['error']}")

    # Clean up internal keys
    report.pop("_node_ids", None)
    report.pop("_export_data", None)
    report.pop("_imported_ids", None)
    report.pop("_final_stats", None)

    # Write report
    report_path = "docs/E2E-VERIFICATION.md"
    with open(report_path, "w") as f:
        f.write("# E2E Verification Report\n\n")
        f.write(f"**Date:** {report['timestamp']}\n\n")
        f.write(f"**Result:** {'✅ ALL PASSED' if report['summary']['failed'] == 0 else '❌ SOME FAILED'}\n\n")
        f.write(f"| Step | Status | Detail |\n")
        f.write(f"|------|--------|--------|\n")
        for r in report["results"]:
            detail = r["detail"].replace("|", "\\|")[:80]
            f.write(f"| {r['step']} | {r['status']} | {detail} |\n")
        f.write(f"\n## Summary\n\n")
        f.write(f"- **Passed:** {report['summary']['passed']}\n")
        f.write(f"- **Failed:** {report['summary']['failed']}\n\n")
        if report["errors"]:
            f.write("## Errors\n\n")
            for e in report["errors"]:
                f.write(f"- **{e['step']}:** {e['error']}\n")

    # Also write raw JSON
    with open("docs/e2e-report.json", "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n📄 Report: {report_path}")
    print(f"📄 JSON: docs/e2e-report.json")

    sys.exit(0 if report['summary']['failed'] == 0 else 1)


if __name__ == "__main__":
    main()
