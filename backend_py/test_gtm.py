"""
Tests for Google Tag Manager (GTM) connector — Phase 14
Covers: containers, overview, tags, triggers, variables, versions, preview, test-call, status save/read
"""
import pytest, json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from app import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c

# ─── 1. Containers ─────────────────────────────────────────────────────
def test_gtm_containers(client):
    r = client.get("/api/connectors/google-tag-manager/containers")
    assert r.status_code == 200
    data = r.get_json()
    assert "containers" in data
    assert len(data["containers"]) >= 3
    ids = [c["id"] for c in data["containers"]]
    assert "GTM-WX4R7N2" in ids

# ─── 2. Overview ───────────────────────────────────────────────────────
def test_gtm_overview(client):
    r = client.get("/api/connectors/google-tag-manager/overview?container_id=GTM-WX4R7N2")
    assert r.status_code == 200
    data = r.get_json()
    assert data["tags_total"] >= 15
    assert "daily_fires" in data
    assert len(data["daily_fires"]) == 7

# ─── 3. Tags ──────────────────────────────────────────────────────────
def test_gtm_tags(client):
    r = client.get("/api/connectors/google-tag-manager/tags?container_id=GTM-WX4R7N2")
    assert r.status_code == 200
    data = r.get_json()
    assert "tags" in data
    assert len(data["tags"]) >= 15
    names = [t["name"] for t in data["tags"]]
    assert "GA4 — Page View" in names
    # Check each tag has required fields
    for t in data["tags"]:
        assert "type" in t
        assert "status" in t
        assert "fire_count_7d" in t

# ─── 4. Triggers ──────────────────────────────────────────────────────
def test_gtm_triggers(client):
    r = client.get("/api/connectors/google-tag-manager/triggers?container_id=GTM-WX4R7N2")
    assert r.status_code == 200
    data = r.get_json()
    assert "triggers" in data
    assert len(data["triggers"]) >= 10
    for tr in data["triggers"]:
        assert "name" in tr
        assert "type" in tr
        assert "filters" in tr
        assert "used_by_tags" in tr

# ─── 5. Variables ─────────────────────────────────────────────────────
def test_gtm_variables(client):
    r = client.get("/api/connectors/google-tag-manager/variables?container_id=GTM-WX4R7N2")
    assert r.status_code == 200
    data = r.get_json()
    assert "variables" in data
    assert len(data["variables"]) >= 20
    scopes = set(v["scope"] for v in data["variables"])
    assert "Built-in" in scopes
    assert "User-Defined" in scopes

# ─── 6. Versions ─────────────────────────────────────────────────────
def test_gtm_versions(client):
    r = client.get("/api/connectors/google-tag-manager/versions?container_id=GTM-WX4R7N2")
    assert r.status_code == 200
    data = r.get_json()
    assert "versions" in data
    assert len(data["versions"]) >= 8
    latest = data["versions"][0]
    assert "name" in latest
    assert "published" in latest
    assert "tags_added" in latest

# ─── 7. Preview ──────────────────────────────────────────────────────
def test_gtm_preview(client):
    r = client.get("/api/connectors/google-tag-manager/preview")
    assert r.status_code == 200
    data = r.get_json()
    assert "events" in data
    assert "container" in data
    assert len(data["events"]) >= 5
    for evt in data["events"]:
        assert "event" in evt
        assert "tags_fired" in evt
        assert "data_layer" in evt

# ─── 8. Test API Call ────────────────────────────────────────────────
def test_gtm_test_call_tags(client):
    r = client.post("/api/connectors/google-tag-manager/test-call",
                     json={"method": "GET", "endpoint": "tags"})
    assert r.status_code == 200
    data = r.get_json()
    assert "request" in data
    assert "response" in data
    assert data["response"]["status_code"] == 200
    assert "quota" in data

def test_gtm_test_call_triggers(client):
    r = client.post("/api/connectors/google-tag-manager/test-call",
                     json={"method": "GET", "endpoint": "triggers"})
    assert r.status_code == 200
    data = r.get_json()
    assert data["response"]["status_code"] == 200

# ─── 9. Status Save/Read ────────────────────────────────────────────
def test_gtm_status_save_read(client):
    # Save
    r = client.post("/api/connectors/google-tag-manager",
                     json={"status": "Connected", "config": {"account": "gtm@camarad.ai"}})
    assert r.status_code == 200
    # Read
    r = client.get("/api/connectors/google-tag-manager")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "Connected"

# ─── 10. Overview Fallback Container ─────────────────────────────────
def test_gtm_overview_fallback_container(client):
    """Unknown container_id falls back to default container data"""
    r = client.get("/api/connectors/google-tag-manager/overview?container_id=GTM-UNKNOWN")
    assert r.status_code == 200
    data = r.get_json()
    assert data["container_id"] == "GTM-UNKNOWN"
    # Falls back to default container data
    assert data["tags_total"] >= 15

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
