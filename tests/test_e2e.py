"""
KGKB End-to-End Tests

Tests the full application flow through the REST API using FastAPI's TestClient.
Simulates a real user workflow:
  1. Health check — verify backend is alive
  2. Add knowledge entries (like CLI `kgkb add`)
  3. Search entries via text mode
  4. Create relations between entries
  5. Verify graph data has correct nodes and edges
  6. Import/export round-trip
  7. Update and delete entries
  8. Final stats verification

These tests run in order within the class using a session-scoped client
and a temporary database, so they form a single coherent E2E scenario.
"""

import pytest


class TestE2EFullFlow:
    """End-to-end test: full lifecycle of knowledge entries, relations, search, graph, and export."""

    # Store IDs across tests within this class
    _node_ids: list = []
    _relation_ids: list = []

    # ── Step 1: Health & Root ──

    def test_01_health_check(self, test_client):
        """E2E Step 1: Verify the backend is healthy and all services are up."""
        resp = test_client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["services"]["database"] is True
        assert "version" in data

    def test_02_root_endpoint(self, test_client):
        """E2E Step 1b: Root should return API info."""
        resp = test_client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "KGKB API"
        assert data["version"] == "0.1.0"

    # ── Step 2: Create Knowledge (simulates CLI `kgkb add`) ──

    def test_03_add_knowledge_entries(self, test_client):
        """E2E Step 2: Create 5 knowledge entries covering different content types."""
        entries = [
            {
                "title": "OpenClaw Framework",
                "content": "OpenClaw is an open-source AI agent framework that runs locally "
                           "with persistent memory, multi-channel messaging, and browser automation.",
                "content_type": "concept",
                "tags": ["ai", "agent", "framework", "open-source"],
                "source": "https://github.com/nicepkg/openclaw",
            },
            {
                "title": "FastAPI Web Framework",
                "content": "FastAPI is a modern, high-performance Python web framework for building "
                           "APIs with automatic validation, serialization, and interactive documentation.",
                "content_type": "technology",
                "tags": ["python", "web", "api", "backend"],
            },
            {
                "title": "FAISS Vector Search",
                "content": "Facebook AI Similarity Search (FAISS) is a library for efficient "
                           "similarity search and clustering of dense vectors at scale.",
                "content_type": "technology",
                "tags": ["vector", "search", "ai", "facebook"],
            },
            {
                "title": "Knowledge Graphs",
                "content": "A knowledge graph represents entities as nodes and relationships as edges, "
                           "enabling semantic reasoning, discovery, and structured data navigation.",
                "content_type": "concept",
                "tags": ["graph", "data", "ai", "semantic"],
            },
            {
                "title": "KGKB Project",
                "content": "KGKB (Knowledge Graph Knowledge Base) combines a graph database with "
                           "vector embeddings for intelligent knowledge management and retrieval.",
                "content_type": "text",
                "tags": ["kgkb", "project", "ai"],
                "source": "https://github.com/example/kgkb",
            },
        ]

        TestE2EFullFlow._node_ids = []
        for entry in entries:
            resp = test_client.post("/api/knowledge", json=entry)
            assert resp.status_code == 201, f"Failed to create '{entry['title']}': {resp.text}"
            data = resp.json()
            assert data["title"] == entry["title"]
            assert data["content"] == entry["content"]
            assert data["tags"] == entry["tags"]
            assert "id" in data
            assert "created_at" in data
            TestE2EFullFlow._node_ids.append(data["id"])

        assert len(TestE2EFullFlow._node_ids) == 5

    # ── Step 3: Search via API ──

    def test_04_text_search_finds_entries(self, test_client):
        """E2E Step 3a: Text search should find relevant entries."""
        resp = test_client.get("/api/knowledge/search", params={
            "q": "AI agent framework",
            "mode": "text",
            "limit": 10,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "text"
        assert data["total"] >= 1
        # Should find OpenClaw (contains "AI", "agent", "framework")
        titles = [r["title"] for r in data["results"]]
        assert any("OpenClaw" in t for t in titles), f"Expected OpenClaw in results, got: {titles}"

    def test_05_text_search_vector(self, test_client):
        """E2E Step 3b: Text search for 'vector' should find FAISS entry."""
        resp = test_client.get("/api/knowledge/search", params={
            "q": "vector",
            "mode": "text",
            "limit": 5,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        found_faiss = any("FAISS" in r["title"] or "vector" in r["content"].lower()
                          for r in data["results"])
        assert found_faiss, "Should find FAISS entry when searching for 'vector'"

    def test_06_search_no_results(self, test_client):
        """E2E Step 3c: Search for gibberish returns empty results."""
        resp = test_client.get("/api/knowledge/search", params={
            "q": "xyzzy_nonexistent_12345",
            "mode": "text",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["results"] == []

    def test_07_legacy_search(self, test_client):
        """E2E Step 3d: Legacy /api/search endpoint should work."""
        resp = test_client.get("/api/search", params={"q": "knowledge", "limit": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "total" in data
        assert data["total"] >= 1

    # ── Step 4: Create Relations ──

    def test_08_create_relations(self, test_client):
        """E2E Step 4: Create relations between knowledge entries."""
        ids = TestE2EFullFlow._node_ids
        assert len(ids) == 5, "Need 5 node IDs from step 2"

        relations = [
            # OpenClaw uses FastAPI
            {"source_id": ids[0], "target_id": ids[1], "type": "uses", "weight": 1.0},
            # OpenClaw uses FAISS
            {"source_id": ids[0], "target_id": ids[2], "type": "uses", "weight": 0.8},
            # Knowledge Graphs related to OpenClaw
            {"source_id": ids[3], "target_id": ids[0], "type": "related_to", "weight": 0.7},
            # KGKB extends OpenClaw
            {"source_id": ids[4], "target_id": ids[0], "type": "extends", "weight": 0.9},
            # KGKB uses FAISS
            {"source_id": ids[4], "target_id": ids[2], "type": "uses", "weight": 0.8},
        ]

        TestE2EFullFlow._relation_ids = []
        for rel in relations:
            resp = test_client.post("/api/relations", json=rel)
            assert resp.status_code == 201, f"Failed to create relation: {resp.text}"
            data = resp.json()
            assert data["source_id"] == rel["source_id"]
            assert data["target_id"] == rel["target_id"]
            assert data["type"] == rel["type"]
            assert data["weight"] == rel["weight"]
            assert "id" in data
            TestE2EFullFlow._relation_ids.append(data["id"])

        assert len(TestE2EFullFlow._relation_ids) == 5

    def test_09_list_relations(self, test_client):
        """E2E Step 4b: List all relations."""
        resp = test_client.get("/api/relations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 5
        assert len(data["items"]) >= 5

    def test_10_list_relations_by_node(self, test_client):
        """E2E Step 4c: Filter relations by node ID (OpenClaw should have 4 relations)."""
        openclaw_id = TestE2EFullFlow._node_ids[0]
        resp = test_client.get("/api/relations", params={"node_id": openclaw_id})
        assert resp.status_code == 200
        data = resp.json()
        # OpenClaw: 2 outgoing (uses FastAPI, uses FAISS) + 2 incoming (related_to, extends)
        assert data["total"] >= 4, f"Expected >= 4 relations for OpenClaw, got {data['total']}"

    def test_11_get_single_relation(self, test_client):
        """E2E Step 4d: Get a single relation by ID."""
        rid = TestE2EFullFlow._relation_ids[0]
        resp = test_client.get(f"/api/relations/{rid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == rid
        assert data["type"] == "uses"

    def test_12_relation_types(self, test_client):
        """E2E Step 4e: List distinct relation types."""
        resp = test_client.get("/api/relations/types")
        assert resp.status_code == 200
        types = resp.json()
        assert isinstance(types, list)
        assert "uses" in types
        assert "related_to" in types
        assert "extends" in types

    # ── Step 5: Verify Graph Data ──

    def test_13_graph_full(self, test_client):
        """E2E Step 5a: Full graph should contain all 5 nodes and 5 edges."""
        resp = test_client.get("/api/graph", params={"depth": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) >= 5, f"Expected >= 5 nodes, got {len(data['nodes'])}"
        assert len(data["edges"]) >= 5, f"Expected >= 5 edges, got {len(data['edges'])}"

        # Verify node structure
        node = data["nodes"][0]
        assert "id" in node
        assert "label" in node
        assert "content" in node
        assert "tags" in node

        # Verify edge structure
        edge = data["edges"][0]
        assert "id" in edge
        assert "source" in edge
        assert "target" in edge
        assert "type" in edge
        assert "weight" in edge

    def test_14_graph_subgraph(self, test_client):
        """E2E Step 5b: Subgraph centered on OpenClaw should show its neighbors."""
        openclaw_id = TestE2EFullFlow._node_ids[0]
        resp = test_client.get("/api/graph", params={"node_id": openclaw_id, "depth": 1})
        assert resp.status_code == 200
        data = resp.json()
        # OpenClaw + its direct neighbors (FastAPI, FAISS, KG, KGKB) = 5 nodes
        assert len(data["nodes"]) >= 3, f"Expected >= 3 nodes in subgraph, got {len(data['nodes'])}"
        assert len(data["edges"]) >= 2, f"Expected >= 2 edges in subgraph, got {len(data['edges'])}"

        # OpenClaw node should be in the subgraph
        node_ids = [n["id"] for n in data["nodes"]]
        assert openclaw_id in node_ids

    # ── Step 6: Tags ──

    def test_15_list_tags(self, test_client):
        """E2E Step 6: All tags should be retrievable."""
        resp = test_client.get("/api/tags")
        assert resp.status_code == 200
        tags = resp.json()
        assert isinstance(tags, list)
        assert "ai" in tags
        assert "python" in tags
        assert "kgkb" in tags

    def test_16_filter_by_tag(self, test_client):
        """E2E Step 6b: Filter knowledge entries by tag."""
        resp = test_client.get("/api/knowledge", params={"tag": "ai"})
        assert resp.status_code == 200
        data = resp.json()
        # OpenClaw, FAISS, KG, KGKB all have 'ai' tag
        assert data["total"] >= 4, f"Expected >= 4 entries with 'ai' tag, got {data['total']}"
        for item in data["items"]:
            assert "ai" in item["tags"]

    # ── Step 7: Update ──

    def test_17_update_knowledge(self, test_client):
        """E2E Step 7: Update a knowledge entry's title and tags."""
        kid = TestE2EFullFlow._node_ids[0]  # OpenClaw
        resp = test_client.put(f"/api/knowledge/{kid}", json={
            "title": "OpenClaw Framework (Updated)",
            "tags": ["ai", "agent", "framework", "open-source", "updated"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "OpenClaw Framework (Updated)"
        assert "updated" in data["tags"]
        # Content should remain unchanged
        assert "OpenClaw" in data["content"]

    # ── Step 8: Export ──

    def test_18_export_json(self, test_client):
        """E2E Step 8a: JSON export should include all entries and relations."""
        resp = test_client.get("/api/export", params={"format": "json"})
        assert resp.status_code == 200
        data = resp.json()
        assert "knowledge" in data
        assert "relations" in data
        assert "exported_at" in data
        assert "stats" in data
        assert data["stats"]["knowledge_count"] >= 5
        assert data["stats"]["relation_count"] >= 5

        # Verify the updated title is in the export
        titles = [k["title"] for k in data["knowledge"]]
        assert "OpenClaw Framework (Updated)" in titles

    def test_19_export_markdown(self, test_client):
        """E2E Step 8b: Markdown export should be a readable document."""
        resp = test_client.get("/api/export", params={"format": "markdown"})
        assert resp.status_code == 200
        text = resp.text
        assert "KGKB Knowledge Export" in text
        assert "OpenClaw Framework (Updated)" in text

    # ── Step 9: Import round-trip ──

    def test_20_import_entries(self, test_client):
        """E2E Step 9: Import new entries and verify they appear in the DB."""
        import_items = [
            {
                "title": "Imported: Docker Containers",
                "content": "Docker uses OS-level virtualization to deliver software in containers.",
                "tags": ["docker", "devops", "import-test"],
            },
            {
                "title": "Imported: Kubernetes",
                "content": "Kubernetes automates deployment, scaling, and management of containerized apps.",
                "tags": ["k8s", "devops", "import-test"],
            },
            {"content": ""},  # Empty — should be skipped
        ]
        resp = test_client.post("/api/import", json=import_items)
        assert resp.status_code == 201
        data = resp.json()
        assert data["imported"] == 2
        assert data["skipped"] == 1

        # Verify via tag filter
        list_resp = test_client.get("/api/knowledge", params={"tag": "import-test"})
        assert list_resp.status_code == 200
        list_data = list_resp.json()
        assert list_data["total"] == 2

    # ── Step 10: Delete ──

    def test_21_delete_relation(self, test_client):
        """E2E Step 10a: Delete a relation and verify it's gone."""
        rid = TestE2EFullFlow._relation_ids[-1]  # last relation (KGKB uses FAISS)
        resp = test_client.delete(f"/api/relations/{rid}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

        # Verify 404
        get_resp = test_client.get(f"/api/relations/{rid}")
        assert get_resp.status_code == 404

    def test_22_delete_knowledge(self, test_client):
        """E2E Step 10b: Delete a knowledge entry and verify cascade."""
        # Create a temporary entry to delete
        create_resp = test_client.post("/api/knowledge", json={
            "title": "Temporary Entry",
            "content": "This entry will be deleted in the E2E test.",
            "tags": ["temp", "delete-me"],
        })
        assert create_resp.status_code == 201
        temp_id = create_resp.json()["id"]

        # Delete it
        del_resp = test_client.delete(f"/api/knowledge/{temp_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "deleted"

        # Verify 404
        get_resp = test_client.get(f"/api/knowledge/{temp_id}")
        assert get_resp.status_code == 404

    # ── Step 11: Stats ──

    def test_23_stats_reflect_operations(self, test_client):
        """E2E Step 11a: Stats should reflect all our create/import/delete operations."""
        resp = test_client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "knowledge_count" in data
        # 5 original + 2 imported = 7 (temp entry was deleted)
        assert data["knowledge_count"] >= 7, f"Expected >= 7 entries, got {data['knowledge_count']}"

    def test_24_embedding_status(self, test_client):
        """E2E Step 11b: Embedding status endpoint should respond."""
        resp = test_client.get("/api/embedding/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "available" in data

    # ── Step 12: Edge cases ──

    def test_25_get_nonexistent_returns_404(self, test_client):
        """E2E Step 12a: Getting a nonexistent entry should return 404."""
        resp = test_client.get("/api/knowledge/nonexistent-id-99999")
        assert resp.status_code == 404

    def test_26_create_relation_invalid_nodes(self, test_client):
        """E2E Step 12b: Creating a relation with invalid node IDs should fail."""
        resp = test_client.post("/api/relations", json={
            "source_id": "nonexistent-1",
            "target_id": "nonexistent-2",
            "type": "relates_to",
        })
        assert resp.status_code in (400, 404)

    def test_27_create_empty_content_fails(self, test_client):
        """E2E Step 12c: Creating knowledge with empty content should fail validation."""
        resp = test_client.post("/api/knowledge", json={"content": ""})
        assert resp.status_code == 422

    def test_28_pagination(self, test_client):
        """E2E Step 12d: Pagination should work correctly."""
        # Get first page
        resp1 = test_client.get("/api/knowledge", params={"limit": 3, "offset": 0})
        assert resp1.status_code == 200
        page1 = resp1.json()
        assert len(page1["items"]) == 3
        assert page1["total"] >= 7

        # Get second page
        resp2 = test_client.get("/api/knowledge", params={"limit": 3, "offset": 3})
        assert resp2.status_code == 200
        page2 = resp2.json()
        assert len(page2["items"]) >= 1

        # Pages should not overlap
        ids_page1 = {item["id"] for item in page1["items"]}
        ids_page2 = {item["id"] for item in page2["items"]}
        assert ids_page1.isdisjoint(ids_page2), "Pagination pages should not overlap"

    def test_29_search_modes(self, test_client):
        """E2E Step 12e: All search modes should return valid responses."""
        for mode in ("text", "semantic", "hybrid"):
            resp = test_client.get("/api/knowledge/search", params={
                "q": "knowledge",
                "mode": mode,
                "limit": 5,
            })
            assert resp.status_code == 200, f"Search mode '{mode}' failed"
            data = resp.json()
            assert "results" in data
            assert "total" in data
            assert "query" in data
            assert "mode" in data

    def test_30_final_graph_integrity(self, test_client):
        """E2E Step 13: Final graph should be consistent after all operations."""
        resp = test_client.get("/api/graph", params={"depth": 3})
        assert resp.status_code == 200
        data = resp.json()

        # Build lookup
        node_ids = {n["id"] for n in data["nodes"]}
        edge_node_ids = set()
        for e in data["edges"]:
            edge_node_ids.add(e["source"])
            edge_node_ids.add(e["target"])

        # All edge endpoints should reference existing nodes
        for eid in edge_node_ids:
            assert eid in node_ids, f"Edge references node {eid[:8]} which is not in the graph"

        # We should still have our 5 original + 2 imported nodes
        assert len(data["nodes"]) >= 7, f"Expected >= 7 nodes, got {len(data['nodes'])}"
        # We deleted 1 relation, so should have >= 4 edges
        assert len(data["edges"]) >= 4, f"Expected >= 4 edges, got {len(data['edges'])}"
