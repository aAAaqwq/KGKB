"""
KGKB API Tests

Tests for all REST API endpoints using FastAPI's TestClient.
Covers: Knowledge CRUD, Relations CRUD, Search, Graph, Tags,
Health, Stats, Import/Export.
"""

import pytest


# ============ Health & Root ============


class TestHealthAndRoot:
    """Test health check and root endpoint."""

    def test_root_returns_api_info(self, test_client):
        """GET / should return API name and version."""
        resp = test_client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "KGKB API"
        assert "version" in data

    def test_health_check(self, test_client):
        """GET /api/health should return healthy status."""
        resp = test_client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "services" in data
        assert "counts" in data
        assert data["services"]["database"] is True

    def test_stats_endpoint(self, test_client):
        """GET /api/stats should return database statistics."""
        resp = test_client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "knowledge_count" in data

    def test_embedding_status(self, test_client):
        """GET /api/embedding/status should return embedding info."""
        resp = test_client.get("/api/embedding/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "available" in data


# ============ Knowledge CRUD ============


class TestKnowledgeCRUD:
    """Test knowledge entry create, read, update, delete."""

    def test_create_knowledge(self, test_client):
        """POST /api/knowledge should create a new entry."""
        payload = {
            "title": "Test Entry",
            "content": "This is a test knowledge entry for unit testing.",
            "content_type": "text",
            "tags": ["test", "api"],
            "source": "https://example.com/test",
        }
        resp = test_client.post("/api/knowledge", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test Entry"
        assert data["content"] == payload["content"]
        assert data["tags"] == ["test", "api"]
        assert data["source"] == payload["source"]
        assert "id" in data
        assert "created_at" in data

    def test_create_knowledge_minimal(self, test_client):
        """POST /api/knowledge with only content should work."""
        payload = {"content": "Minimal entry with just content."}
        resp = test_client.post("/api/knowledge", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["content"] == payload["content"]
        # Title should default to empty or auto-generated
        assert isinstance(data["title"], str)

    def test_create_knowledge_empty_content_fails(self, test_client):
        """POST /api/knowledge with empty content should fail validation."""
        payload = {"content": ""}
        resp = test_client.post("/api/knowledge", json=payload)
        assert resp.status_code == 422  # Pydantic validation error

    def test_get_knowledge(self, test_client):
        """GET /api/knowledge/:id should return the entry."""
        # Create first
        create_resp = test_client.post("/api/knowledge", json={
            "title": "Get Test",
            "content": "Content for get test.",
            "tags": ["get-test"],
        })
        assert create_resp.status_code == 201
        kid = create_resp.json()["id"]

        # Get by full ID
        resp = test_client.get(f"/api/knowledge/{kid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == kid
        assert data["title"] == "Get Test"

    def test_get_knowledge_not_found(self, test_client):
        """GET /api/knowledge/:id with unknown ID should return 404."""
        resp = test_client.get("/api/knowledge/nonexistent-id-12345")
        assert resp.status_code == 404

    def test_list_knowledge(self, test_client):
        """GET /api/knowledge should return a paginated list."""
        resp = test_client.get("/api/knowledge", params={"limit": 5, "offset": 0})
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert isinstance(data["items"], list)

    def test_list_knowledge_filter_by_tag(self, test_client):
        """GET /api/knowledge?tag=X should filter by tag."""
        # Create entries with specific tags
        test_client.post("/api/knowledge", json={
            "content": "Tagged entry for filter test.",
            "tags": ["filter-tag-unique"],
        })

        resp = test_client.get("/api/knowledge", params={"tag": "filter-tag-unique"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert "filter-tag-unique" in item["tags"]

    def test_update_knowledge(self, test_client):
        """PUT /api/knowledge/:id should update fields."""
        # Create
        create_resp = test_client.post("/api/knowledge", json={
            "title": "Before Update",
            "content": "Original content.",
        })
        kid = create_resp.json()["id"]

        # Update
        resp = test_client.put(f"/api/knowledge/{kid}", json={
            "title": "After Update",
            "content": "Updated content.",
            "tags": ["updated"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "After Update"
        assert data["content"] == "Updated content."
        assert "updated" in data["tags"]

    def test_update_knowledge_partial(self, test_client):
        """PUT /api/knowledge/:id with partial data should only update provided fields."""
        create_resp = test_client.post("/api/knowledge", json={
            "title": "Partial Update",
            "content": "Will stay the same.",
            "tags": ["original"],
        })
        kid = create_resp.json()["id"]

        # Only update title
        resp = test_client.put(f"/api/knowledge/{kid}", json={"title": "New Title Only"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "New Title Only"
        assert data["content"] == "Will stay the same."

    def test_delete_knowledge(self, test_client):
        """DELETE /api/knowledge/:id should remove the entry."""
        create_resp = test_client.post("/api/knowledge", json={
            "content": "This will be deleted.",
        })
        kid = create_resp.json()["id"]

        # Delete
        resp = test_client.delete(f"/api/knowledge/{kid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "deleted"
        assert data["id"] == kid

        # Verify it's gone
        get_resp = test_client.get(f"/api/knowledge/{kid}")
        assert get_resp.status_code == 404

    def test_delete_knowledge_not_found(self, test_client):
        """DELETE /api/knowledge/:id with unknown ID should return 404."""
        resp = test_client.delete("/api/knowledge/nonexistent-id-99999")
        assert resp.status_code == 404


# ============ Tags ============


class TestTags:
    """Test tag endpoints."""

    def test_list_tags(self, test_client):
        """GET /api/tags should return list of strings."""
        # Ensure at least one tagged entry exists
        test_client.post("/api/knowledge", json={
            "content": "Tagged for tag list test.",
            "tags": ["tag-list-test"],
        })

        resp = test_client.get("/api/tags")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert "tag-list-test" in data


# ============ Search ============


class TestSearch:
    """Test search endpoints."""

    def test_text_search(self, test_client):
        """GET /api/knowledge/search with text mode should find entries."""
        # Create a searchable entry
        test_client.post("/api/knowledge", json={
            "title": "Quantum Computing",
            "content": "Quantum computing uses qubits for parallel computation.",
            "tags": ["science", "computing"],
        })

        resp = test_client.get("/api/knowledge/search", params={
            "q": "quantum",
            "mode": "text",
            "limit": 10,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert data["query"] == "quantum"
        assert data["mode"] == "text"
        # Should find at least 1 result
        assert data["total"] >= 1
        assert any("quantum" in r["content"].lower() or "quantum" in r["title"].lower()
                    for r in data["results"])

    def test_search_no_results(self, test_client):
        """GET /api/knowledge/search with gibberish should return empty."""
        resp = test_client.get("/api/knowledge/search", params={
            "q": "xyzzy_impossible_query_12345",
            "mode": "text",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["results"] == []

    def test_search_validation(self, test_client):
        """GET /api/knowledge/search without q should fail."""
        resp = test_client.get("/api/knowledge/search")
        assert resp.status_code == 422

    def test_legacy_search(self, test_client):
        """GET /api/search should work (legacy endpoint)."""
        resp = test_client.get("/api/search", params={"q": "test", "limit": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "total" in data
        assert "query" in data


# ============ Relations ============


class TestRelations:
    """Test relation endpoints."""

    def _create_two_entries(self, test_client):
        """Helper: create two knowledge entries and return their IDs."""
        r1 = test_client.post("/api/knowledge", json={
            "title": "Node A",
            "content": "First node for relation test.",
        })
        r2 = test_client.post("/api/knowledge", json={
            "title": "Node B",
            "content": "Second node for relation test.",
        })
        return r1.json()["id"], r2.json()["id"]

    def test_create_relation(self, test_client):
        """POST /api/relations should create a relation between two entries."""
        id_a, id_b = self._create_two_entries(test_client)

        resp = test_client.post("/api/relations", json={
            "source_id": id_a,
            "target_id": id_b,
            "type": "relates_to",
            "weight": 0.8,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["source_id"] == id_a
        assert data["target_id"] == id_b
        assert data["type"] == "relates_to"
        assert data["weight"] == 0.8
        assert "id" in data

    def test_create_relation_invalid_node(self, test_client):
        """POST /api/relations with nonexistent node should fail."""
        resp = test_client.post("/api/relations", json={
            "source_id": "nonexistent-1",
            "target_id": "nonexistent-2",
            "type": "relates_to",
        })
        assert resp.status_code in (400, 404)

    def test_list_relations(self, test_client):
        """GET /api/relations should return a list."""
        resp = test_client.get("/api/relations")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    def test_list_relations_by_node(self, test_client):
        """GET /api/relations?node_id=X should filter by node."""
        id_a, id_b = self._create_two_entries(test_client)
        test_client.post("/api/relations", json={
            "source_id": id_a,
            "target_id": id_b,
            "type": "node_filter_test",
        })

        resp = test_client.get("/api/relations", params={"node_id": id_a})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        # All returned relations should involve node_id
        for item in data["items"]:
            assert id_a in (item["source_id"], item["target_id"])

    def test_get_relation(self, test_client):
        """GET /api/relations/:id should return the relation."""
        id_a, id_b = self._create_two_entries(test_client)
        create_resp = test_client.post("/api/relations", json={
            "source_id": id_a,
            "target_id": id_b,
            "type": "get_test",
        })
        rid = create_resp.json()["id"]

        resp = test_client.get(f"/api/relations/{rid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == rid
        assert data["type"] == "get_test"

    def test_delete_relation(self, test_client):
        """DELETE /api/relations/:id should remove the relation."""
        id_a, id_b = self._create_two_entries(test_client)
        create_resp = test_client.post("/api/relations", json={
            "source_id": id_a,
            "target_id": id_b,
            "type": "delete_test",
        })
        rid = create_resp.json()["id"]

        resp = test_client.delete(f"/api/relations/{rid}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

        # Verify it's gone
        get_resp = test_client.get(f"/api/relations/{rid}")
        assert get_resp.status_code == 404

    def test_relation_types(self, test_client):
        """GET /api/relations/types should return list of type strings."""
        resp = test_client.get("/api/relations/types")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


# ============ Graph ============


class TestGraph:
    """Test graph endpoint."""

    def test_get_graph(self, test_client):
        """GET /api/graph should return nodes and edges."""
        resp = test_client.get("/api/graph")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)

    def test_get_graph_with_depth(self, test_client):
        """GET /api/graph?depth=1 should work."""
        resp = test_client.get("/api/graph", params={"depth": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data

    def test_graph_node_structure(self, test_client):
        """Graph nodes should have expected fields."""
        # Ensure at least one entry exists
        test_client.post("/api/knowledge", json={
            "title": "Graph Node Test",
            "content": "Entry for graph node structure test.",
            "tags": ["graph-test"],
        })

        resp = test_client.get("/api/graph")
        data = resp.json()
        if data["nodes"]:
            node = data["nodes"][0]
            assert "id" in node
            assert "label" in node
            assert "content" in node
            assert "tags" in node


# ============ Import / Export ============


class TestImportExport:
    """Test import and export endpoints."""

    def test_export_json(self, test_client):
        """GET /api/export should return JSON with knowledge and relations."""
        resp = test_client.get("/api/export", params={"format": "json"})
        assert resp.status_code == 200
        data = resp.json()
        assert "knowledge" in data
        assert "relations" in data
        assert "exported_at" in data
        assert "stats" in data
        assert isinstance(data["knowledge"], list)
        assert isinstance(data["relations"], list)

    def test_export_markdown(self, test_client):
        """GET /api/export?format=markdown should return markdown text."""
        resp = test_client.get("/api/export", params={"format": "markdown"})
        assert resp.status_code == 200
        assert "KGKB Knowledge Export" in resp.text

    def test_import_knowledge(self, test_client):
        """POST /api/import should import entries."""
        items = [
            {"content": "Import test entry 1", "tags": ["import"]},
            {"content": "Import test entry 2", "tags": ["import"]},
            {"content": ""},  # This should be skipped (empty content)
        ]
        resp = test_client.post("/api/import", json=items)
        assert resp.status_code == 201
        data = resp.json()
        assert data["imported"] == 2
        assert data["skipped"] == 1
        assert isinstance(data["errors"], list)

    def test_import_empty_list(self, test_client):
        """POST /api/import with empty list should succeed with 0 imports."""
        resp = test_client.post("/api/import", json=[])
        assert resp.status_code == 201
        data = resp.json()
        assert data["imported"] == 0
