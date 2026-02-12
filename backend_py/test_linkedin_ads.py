"""
LinkedIn Ads Connector – Test Suite
13 tests covering all 8 endpoints + status persistence
"""
import pytest
import requests
import json

BASE = "http://127.0.0.1:5051"


# ── Accounts ───────────────────────────────────────────────────────────
def test_linkedin_accounts():
    r = requests.get(f"{BASE}/api/connectors/linkedin-ads/accounts")
    assert r.status_code == 200
    data = r.json()
    assert "accounts" in data
    assert len(data["accounts"]) == 3
    names = [a["name"] for a in data["accounts"]]
    assert "TechStart B2B" in names
    assert all("account_id" in a for a in data["accounts"])
    assert all(a["type"] == "BUSINESS" for a in data["accounts"])


# ── Overview ───────────────────────────────────────────────────────────
def test_linkedin_overview():
    r = requests.get(f"{BASE}/api/connectors/linkedin-ads/overview?account_id=li_acc_987654321")
    assert r.status_code == 200
    ov = r.json()["overview"]
    assert ov["spend"] == 3195.40
    assert ov["leads"] == 89
    assert ov["cost_per_lead"] == 35.90
    assert ov["roas"] == 3.2
    assert ov["engagement_rate"] == 2.8
    assert len(ov["daily_spend"]) == 7
    assert len(ov["audience_breakdown"]) == 4


def test_linkedin_overview_unknown_account():
    r = requests.get(f"{BASE}/api/connectors/linkedin-ads/overview?account_id=li_acc_000")
    assert r.status_code == 200
    ov = r.json()["overview"]
    assert ov["spend"] == 0
    assert ov["leads"] == 0


# ── Campaigns ──────────────────────────────────────────────────────────
def test_linkedin_campaigns():
    r = requests.get(f"{BASE}/api/connectors/linkedin-ads/campaigns")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 8
    camps = data["campaigns"]
    assert any(c["name"] == "B2B Lead Gen Q1" for c in camps)
    assert any(c["objective"] == "LEAD_GENERATION" for c in camps)
    assert any(c["status"] == "PAUSED" for c in camps)
    assert any(c["format"] == "MESSAGE_AD" for c in camps)


# ── Ad Sets ────────────────────────────────────────────────────────────
def test_linkedin_adsets():
    r = requests.get(f"{BASE}/api/connectors/linkedin-ads/adsets?campaign_id=li_camp_001")
    assert r.status_code == 200
    data = r.json()
    assert data["campaign_id"] == "li_camp_001"
    assert data["total"] == 3
    sets = data["ad_sets"]
    assert any(s["name"] == "Marketing Managers 50-500 emp" for s in sets)
    # Check B2B targeting structure
    t = sets[0]["targeting"]
    assert "job_titles" in t
    assert "company_size" in t
    assert "industries" in t
    assert "seniority" in t


def test_linkedin_adsets_retargeting():
    r = requests.get(f"{BASE}/api/connectors/linkedin-ads/adsets?campaign_id=li_camp_007")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    sets = data["ad_sets"]
    # Retargeting ad sets should have matched_audiences
    has_matched = any(s["targeting"].get("matched_audiences") for s in sets)
    assert has_matched
    has_audiences = any("audiences" in s["targeting"] for s in sets)
    assert has_audiences


# ── Ads ────────────────────────────────────────────────────────────────
def test_linkedin_ads():
    r = requests.get(f"{BASE}/api/connectors/linkedin-ads/ads?adset_id=li_as_001")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    ads = data["ads"]
    assert any(a["format"] == "Single Image" for a in ads)
    assert all("headline" in a for a in ads)
    assert all("cta" in a for a in ads)


def test_linkedin_ads_creative():
    r = requests.get(f"{BASE}/api/connectors/linkedin-ads/ads?adset_id=li_as_006")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    ads = data["ads"]
    assert any(a["format"] == "Message Ad" for a in ads)
    assert any("leads" in a and a["leads"] > 0 for a in ads)
    assert any(a["cost_per_lead"] > 0 for a in ads)


# ── Budget Pacing ──────────────────────────────────────────────────────
def test_linkedin_budget_pacing():
    r = requests.get(f"{BASE}/api/connectors/linkedin-ads/budget-pacing?account_id=li_acc_987654321")
    assert r.status_code == 200
    p = r.json()["pacing"]
    assert p["overall_budget"] == 4500
    assert p["overall_spent"] == 3195.40
    assert p["pacing_status"] == "ON_TRACK"
    assert len(p["campaigns"]) == 8
    pacings = [c["pacing"] for c in p["campaigns"]]
    assert "OVERPACING" in pacings
    assert "UNDERPACING" in pacings


# ── Reports ────────────────────────────────────────────────────────────
def test_linkedin_reports():
    r = requests.get(f"{BASE}/api/connectors/linkedin-ads/reports?account_id=li_acc_987654321")
    assert r.status_code == 200
    data = r.json()
    assert data["total_rows"] == 56  # 7 days × 8 campaigns
    row = data["rows"][0]
    assert "date" in row
    assert "campaign" in row
    assert "objective" in row
    assert "format" in row
    assert "leads" in row
    assert "cost_per_lead" in row


# ── Test API Call ──────────────────────────────────────────────────────
def test_linkedin_test_call_campaigns():
    r = requests.post(f"{BASE}/api/connectors/linkedin-ads/test-call",
                      json={"endpoint": "adCampaignsV2", "method": "GET"})
    assert r.status_code == 200
    data = r.json()
    assert data["endpoint"] == "adCampaignsV2"
    body = data["response"]["body"]
    assert len(body["elements"]) == 3
    assert "quota" in data
    assert data["quota"]["daily_limit"] == 5000


def test_linkedin_test_call_analytics():
    r = requests.post(f"{BASE}/api/connectors/linkedin-ads/test-call",
                      json={"endpoint": "adAnalyticsV2", "method": "GET"})
    assert r.status_code == 200
    body = r.json()["response"]["body"]
    assert len(body["elements"]) == 1
    elem = body["elements"][0]
    assert "impressions" in elem
    assert "leads" in elem
    assert "totalEngagements" in elem


# ── Status persistence ────────────────────────────────────────────────
def test_linkedin_status_save_read():
    # Save
    r = requests.post(f"{BASE}/api/connectors/linkedin-ads",
                      json={"status": "Connected", "config": {"account": "li_acc_987654321"}})
    assert r.status_code == 200
    # Read back
    r2 = requests.get(f"{BASE}/api/connectors/linkedin-ads")
    assert r2.status_code == 200
    assert r2.json()["status"] == "Connected"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
