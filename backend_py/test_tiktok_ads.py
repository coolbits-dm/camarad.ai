"""
TikTok Ads Connector – Test Suite
13 tests covering all 8 endpoints + status persistence
"""
import pytest
import requests
import json

BASE = "http://127.0.0.1:5051"


# ── Accounts ───────────────────────────────────────────────────────────
def test_tiktok_accounts():
    r = requests.get(f"{BASE}/api/connectors/tiktok-ads/accounts")
    assert r.status_code == 200
    data = r.json()
    assert "accounts" in data
    assert len(data["accounts"]) == 3
    names = [a["name"] for a in data["accounts"]]
    assert "TechStart TikTok" in names
    assert all("advertiser_id" in a for a in data["accounts"])


# ── Overview ───────────────────────────────────────────────────────────
def test_tiktok_overview():
    r = requests.get(f"{BASE}/api/connectors/tiktok-ads/overview?advertiser_id=adv_987654321")
    assert r.status_code == 200
    ov = r.json()["overview"]
    assert ov["spend"] == 2890.45
    assert ov["video_views"] == 1234567
    assert ov["completion_rate"] == 68.4
    assert ov["engagement_rate"] == 12.1
    assert ov["roas"] == 3.9
    assert len(ov["daily_spend"]) == 7
    assert len(ov["placement_breakdown"]) == 4


def test_tiktok_overview_unknown_account():
    r = requests.get(f"{BASE}/api/connectors/tiktok-ads/overview?advertiser_id=adv_000")
    assert r.status_code == 200
    ov = r.json()["overview"]
    assert ov["spend"] == 0
    assert ov["video_views"] == 0


# ── Campaigns ──────────────────────────────────────────────────────────
def test_tiktok_campaigns():
    r = requests.get(f"{BASE}/api/connectors/tiktok-ads/campaigns")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 8
    camps = data["campaigns"]
    assert any(c["name"] == "Viral Dance Challenge" for c in camps)
    assert any(c["objective"] == "VIDEO_VIEWS" for c in camps)
    assert any(c["status"] == "PAUSED" for c in camps)


# ── Ad Groups ──────────────────────────────────────────────────────────
def test_tiktok_adgroups():
    r = requests.get(f"{BASE}/api/connectors/tiktok-ads/adgroups?campaign_id=camp_tt_001")
    assert r.status_code == 200
    data = r.json()
    assert data["campaign_id"] == "camp_tt_001"
    assert data["total"] == 3
    groups = data["ad_groups"]
    assert any(g["name"] == "Women 18-24 Dance" for g in groups)
    # Check targeting structure
    t = groups[0]["targeting"]
    assert "interests" in t
    assert "age" in t


def test_tiktok_adgroups_retargeting():
    r = requests.get(f"{BASE}/api/connectors/tiktok-ads/adgroups?campaign_id=camp_tt_002")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    # Check audience targeting
    groups = data["ad_groups"]
    has_audience = any("audiences" in g["targeting"] for g in groups)
    assert has_audience


# ── Ads ────────────────────────────────────────────────────────────────
def test_tiktok_ads():
    r = requests.get(f"{BASE}/api/connectors/tiktok-ads/ads?adgroup_id=ag_tt_001")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    ads = data["ads"]
    assert any(a["format"] == "In-Feed Video" for a in ads)
    assert any(a["format"] == "Spark Ad" for a in ads)
    assert all("video_duration" in a for a in ads)
    assert all("completion_rate" in a for a in ads)


def test_tiktok_ads_ootd():
    r = requests.get(f"{BASE}/api/connectors/tiktok-ads/ads?adgroup_id=ag_tt_006")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    ads = data["ads"]
    assert any("Transition" in a["name"] for a in ads)


# ── Budget Pacing ──────────────────────────────────────────────────────
def test_tiktok_budget_pacing():
    r = requests.get(f"{BASE}/api/connectors/tiktok-ads/budget-pacing?advertiser_id=adv_987654321")
    assert r.status_code == 200
    p = r.json()["pacing"]
    assert p["overall_budget"] == 6000
    assert p["overall_spent"] == 4320.45
    assert p["pacing_status"] == "ON_TRACK"
    assert len(p["campaigns"]) == 8
    pacings = [c["pacing"] for c in p["campaigns"]]
    assert "OVERPACING" in pacings
    assert "UNDERPACING" in pacings


# ── Reports ────────────────────────────────────────────────────────────
def test_tiktok_reports():
    r = requests.get(f"{BASE}/api/connectors/tiktok-ads/reports?advertiser_id=adv_987654321")
    assert r.status_code == 200
    data = r.json()
    assert data["total_rows"] == 56  # 7 days x 8 campaigns
    row = data["rows"][0]
    assert "date" in row
    assert "campaign" in row
    assert "video_views" in row
    assert "completion_rate" in row


# ── Test API Call ──────────────────────────────────────────────────────
def test_tiktok_test_call_campaigns():
    r = requests.post(f"{BASE}/api/connectors/tiktok-ads/test-call",
                      json={"endpoint": "campaign/get", "method": "GET"})
    assert r.status_code == 200
    data = r.json()
    assert data["endpoint"] == "campaign/get"
    body = data["response"]["body"]
    assert body["code"] == 0
    assert len(body["data"]["list"]) == 3


def test_tiktok_test_call_report():
    r = requests.post(f"{BASE}/api/connectors/tiktok-ads/test-call",
                      json={"endpoint": "report/integrated/get", "method": "GET"})
    assert r.status_code == 200
    body = r.json()["response"]["body"]
    assert body["code"] == 0
    assert "metrics" in body["data"]["list"][0]


# ── Status persistence ────────────────────────────────────────────────
def test_tiktok_status_save_read():
    # Save
    r = requests.post(f"{BASE}/api/connectors/tiktok-ads",
                      json={"status": "Connected", "config": {"account": "adv_987654321"}})
    assert r.status_code == 200
    # Read back
    r2 = requests.get(f"{BASE}/api/connectors/tiktok-ads")
    assert r2.status_code == 200
    assert r2.json()["status"] == "Connected"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
