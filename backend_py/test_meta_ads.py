"""
Tests for Meta Ads (Facebook + Instagram) connector — Phase 15
Covers: accounts, overview, campaigns, adsets, ads, budget-pacing, reports, test-call, status save/read
"""
import pytest, json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from app import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c

# ─── 1. Ad Accounts ───────────────────────────────────────────────────
def test_meta_accounts(client):
    r = client.get("/api/connectors/meta-ads/accounts")
    assert r.status_code == 200
    data = r.get_json()
    assert "accounts" in data
    assert len(data["accounts"]) >= 3
    ids = [a["id"] for a in data["accounts"]]
    assert "act_123456789" in ids
    for a in data["accounts"]:
        assert "name" in a
        assert "currency" in a
        assert "status" in a

# ─── 2. Overview ──────────────────────────────────────────────────────
def test_meta_overview(client):
    r = client.get("/api/connectors/meta-ads/overview?account_id=act_123456789")
    assert r.status_code == 200
    data = r.get_json()
    assert data["spend"] > 0
    assert data["reach"] > 0
    assert data["roas"] > 0
    assert "daily_spend" in data
    assert len(data["daily_spend"]) == 7
    assert "platform_breakdown" in data
    assert len(data["platform_breakdown"]) == 2

# ─── 3. Campaigns ────────────────────────────────────────────────────
def test_meta_campaigns(client):
    r = client.get("/api/connectors/meta-ads/campaigns?account_id=act_123456789")
    assert r.status_code == 200
    data = r.get_json()
    assert "campaigns" in data
    assert len(data["campaigns"]) >= 5
    for c in data["campaigns"]:
        assert "name" in c
        assert "objective" in c
        assert "status" in c
        assert "spend" in c
        assert "roas" in c

# ─── 4. Ad Sets ──────────────────────────────────────────────────────
def test_meta_adsets(client):
    r = client.get("/api/connectors/meta-ads/adsets?campaign_id=camp_001")
    assert r.status_code == 200
    data = r.get_json()
    assert "adsets" in data
    assert len(data["adsets"]) >= 3
    for a in data["adsets"]:
        assert "targeting" in a
        assert "age_min" in a["targeting"]
        assert "interests" in a["targeting"]

def test_meta_adsets_retargeting(client):
    r = client.get("/api/connectors/meta-ads/adsets?campaign_id=camp_003")
    assert r.status_code == 200
    data = r.get_json()
    assert len(data["adsets"]) >= 2

# ─── 5. Ads ──────────────────────────────────────────────────────────
def test_meta_ads(client):
    r = client.get("/api/connectors/meta-ads/ads?adset_id=as_001")
    assert r.status_code == 200
    data = r.get_json()
    assert "ads" in data
    assert len(data["ads"]) >= 3
    formats = [a["format"] for a in data["ads"]]
    assert "CAROUSEL" in formats or "VIDEO" in formats
    for a in data["ads"]:
        assert "headline" in a
        assert "cta" in a
        assert "impressions" in a

def test_meta_ads_dynamic(client):
    r = client.get("/api/connectors/meta-ads/ads?adset_id=as_004")
    assert r.status_code == 200
    data = r.get_json()
    assert len(data["ads"]) >= 2
    assert any(a["format"] == "DYNAMIC" for a in data["ads"])

# ─── 6. Budget & Pacing ─────────────────────────────────────────────
def test_meta_budget_pacing(client):
    r = client.get("/api/connectors/meta-ads/budget-pacing?account_id=act_123456789")
    assert r.status_code == 200
    data = r.get_json()
    assert data["total_budget"] > 0
    assert data["spent"] > 0
    assert "pacing_status" in data
    assert "campaigns" in data
    assert len(data["campaigns"]) >= 3
    for c in data["campaigns"]:
        assert "pacing" in c
        assert "pct" in c

# ─── 7. Reports ──────────────────────────────────────────────────────
def test_meta_reports(client):
    r = client.get("/api/connectors/meta-ads/reports?account_id=act_123456789")
    assert r.status_code == 200
    data = r.get_json()
    assert "rows" in data
    assert len(data["rows"]) >= 20
    assert "generated_at" in data
    for row in data["rows"][:5]:
        assert "date" in row
        assert "campaign" in row
        assert "spend" in row

# ─── 8. Test API Call ────────────────────────────────────────────────
def test_meta_test_call_campaigns(client):
    r = client.post("/api/connectors/meta-ads/test-call",
                     json={"method": "GET", "endpoint": "campaigns"})
    assert r.status_code == 200
    data = r.get_json()
    assert "request" in data
    assert "response" in data
    assert data["response"]["status_code"] == 200
    assert "data" in data["response"]["body"]
    assert "quota" in data

def test_meta_test_call_insights(client):
    r = client.post("/api/connectors/meta-ads/test-call",
                     json={"method": "GET", "endpoint": "insights"})
    assert r.status_code == 200
    data = r.get_json()
    assert data["response"]["status_code"] == 200
    assert "actions" in data["response"]["body"]["data"][0]

# ─── 9. Status Save/Read ────────────────────────────────────────────
def test_meta_status_save_read(client):
    r = client.post("/api/connectors/meta-ads",
                     json={"status": "Connected", "config": {"account": "business@meta.com"}})
    assert r.status_code == 200
    r = client.get("/api/connectors/meta-ads")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "Connected"

# ─── 10. Unknown Account Fallback ───────────────────────────────────
def test_meta_overview_unknown_account(client):
    r = client.get("/api/connectors/meta-ads/overview?account_id=act_unknown")
    assert r.status_code == 200
    data = r.get_json()
    assert data["spend"] == 0

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
