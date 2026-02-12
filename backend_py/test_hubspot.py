"""
test_hubspot.py – Phase 20 HubSpot CRM Connector Tests
Covers: portals, overview, contacts, companies, deals, campaigns,
        reports, test-call, status save/read
"""
import requests, sys

BASE = "http://127.0.0.1:5051"
PASS = 0
FAIL = 0


def ok(label):
    global PASS
    PASS += 1
    print(f"  ✅ {label}")


def fail(label, reason=""):
    global FAIL
    FAIL += 1
    print(f"  ❌ {label} — {reason}")


def t(label, fn):
    try:
        fn()
        ok(label)
    except AssertionError as e:
        fail(label, str(e))
    except Exception as e:
        fail(label, repr(e))


# ── Tests ──────────────────────────────────────────────────────────────────

def test_portals():
    r = requests.get(f"{BASE}/api/connectors/hubspot/portals")
    d = r.json()
    assert r.status_code == 200
    assert len(d["portals"]) == 3
    ids = [p["portal_id"] for p in d["portals"]]
    assert "techstart-crm" in ids

t("1. GET /hubspot/portals → 3 portals", test_portals)


def test_overview():
    r = requests.get(f"{BASE}/api/connectors/hubspot/overview?portal_id=techstart-crm")
    d = r.json()
    assert r.status_code == 200
    ov = d["overview"]
    assert ov["total_contacts"] == 1234
    assert ov["total_deals"] == 89
    assert ov["won_revenue_this_month"] == 42350
    assert len(ov["monthly_deals"]) == 6
    assert len(ov["deal_stage_distribution"]) == 7

t("2. GET /hubspot/overview → KPIs + deals + stages", test_overview)


def test_overview_unknown():
    r = requests.get(f"{BASE}/api/connectors/hubspot/overview?portal_id=nonexistent")
    d = r.json()
    assert r.status_code == 200
    ov = d["overview"]
    assert ov["total_contacts"] == 0
    assert ov["total_deals"] == 0

t("3. GET /hubspot/overview unknown → zeros", test_overview_unknown)


def test_contacts():
    r = requests.get(f"{BASE}/api/connectors/hubspot/contacts")
    d = r.json()
    assert r.status_code == 200
    assert d["total"] == 15
    assert len(d["contacts"]) == 15
    c = d["contacts"][0]
    for k in ["name", "email", "company", "lifecycle_stage", "lead_status", "owner"]:
        assert k in c, f"missing key {k}"

t("4. GET /hubspot/contacts → 15 contacts", test_contacts)


def test_contacts_filter_stage():
    r = requests.get(f"{BASE}/api/connectors/hubspot/contacts?lifecycle_stage=Customer")
    d = r.json()
    assert r.status_code == 200
    assert all(c["lifecycle_stage"] == "Customer" for c in d["contacts"])
    assert d["total"] >= 3

t("5. GET /hubspot/contacts?stage=Customer → filter", test_contacts_filter_stage)


def test_contacts_filter_owner():
    r = requests.get(f"{BASE}/api/connectors/hubspot/contacts?owner=Sarah+Chen")
    d = r.json()
    assert r.status_code == 200
    assert all("Sarah Chen" in c["owner"] for c in d["contacts"])

t("6. GET /hubspot/contacts?owner=Sarah → filter", test_contacts_filter_owner)


def test_companies():
    r = requests.get(f"{BASE}/api/connectors/hubspot/companies")
    d = r.json()
    assert r.status_code == 200
    assert d["total"] == 10
    assert len(d["companies"]) == 10
    c = d["companies"][0]
    for k in ["name", "domain", "industry", "annual_revenue", "employees", "deals_count"]:
        assert k in c, f"missing key {k}"

t("7. GET /hubspot/companies → 10 companies", test_companies)


def test_companies_filter():
    r = requests.get(f"{BASE}/api/connectors/hubspot/companies?industry=SaaS")
    d = r.json()
    assert r.status_code == 200
    assert all("SaaS" in c["industry"] for c in d["companies"])
    assert d["total"] >= 2

t("8. GET /hubspot/companies?industry=SaaS → filter", test_companies_filter)


def test_deals():
    r = requests.get(f"{BASE}/api/connectors/hubspot/deals")
    d = r.json()
    assert r.status_code == 200
    assert d["total"] == 10
    assert len(d["deals"]) == 10
    deal = d["deals"][0]
    for k in ["name", "amount", "stage", "probability", "company", "contact", "close_date"]:
        assert k in deal, f"missing key {k}"

t("9. GET /hubspot/deals → 10 deals", test_deals)


def test_deals_filter():
    r = requests.get(f"{BASE}/api/connectors/hubspot/deals?stage=Closed+Won")
    d = r.json()
    assert r.status_code == 200
    assert all("Closed Won" in dl["stage"] for dl in d["deals"])
    assert d["total"] >= 3

t("10. GET /hubspot/deals?stage=Closed Won → filter", test_deals_filter)


def test_campaigns():
    r = requests.get(f"{BASE}/api/connectors/hubspot/campaigns")
    d = r.json()
    assert r.status_code == 200
    assert d["total"] == 8
    assert len(d["campaigns"]) == 8
    c = d["campaigns"][0]
    for k in ["name", "subject", "sent", "opens", "clicks", "open_rate", "click_rate", "status"]:
        assert k in c, f"missing key {k}"

t("11. GET /hubspot/campaigns → 8 campaigns", test_campaigns)


def test_campaigns_filter():
    r = requests.get(f"{BASE}/api/connectors/hubspot/campaigns?status=draft")
    d = r.json()
    assert r.status_code == 200
    assert all(c["status"] == "draft" for c in d["campaigns"])
    assert d["total"] >= 1

t("12. GET /hubspot/campaigns?status=draft → filter", test_campaigns_filter)


def test_reports():
    r = requests.get(f"{BASE}/api/connectors/hubspot/reports?portal_id=techstart-crm")
    d = r.json()
    assert r.status_code == 200
    assert len(d["rows"]) == 31
    row = d["rows"][0]
    for k in ["date", "contacts_added", "deals_created", "deals_closed", "revenue", "emails_sent", "email_opens", "form_submissions", "meetings_booked"]:
        assert k in row, f"missing key {k}"

t("13. GET /hubspot/reports → 31 rows", test_reports)


def test_call_contacts():
    r = requests.post(f"{BASE}/api/connectors/hubspot/test-call",
                      json={"endpoint": "contacts", "method": "GET"})
    d = r.json()
    assert r.status_code == 200
    assert "response" in d
    assert "results" in d["response"]["body"]
    assert len(d["response"]["body"]["results"]) >= 2

t("14. POST /hubspot/test-call contacts → mock data", test_call_contacts)


def test_call_deals():
    r = requests.post(f"{BASE}/api/connectors/hubspot/test-call",
                      json={"endpoint": "deals", "method": "GET"})
    d = r.json()
    assert r.status_code == 200
    assert "results" in d["response"]["body"]

t("15. POST /hubspot/test-call deals → mock data", test_call_deals)


def test_status_save_read():
    # Save
    r = requests.post(f"{BASE}/api/connectors/hubspot",
                      json={"status": "Connected", "config": {"portal": "techstart-crm"}})
    assert r.status_code == 200
    # Read
    r2 = requests.get(f"{BASE}/api/connectors/hubspot")
    d2 = r2.json()
    assert d2["status"] == "Connected"

t("16. Status save + read → Connected", test_status_save_read)


# ── Summary ────────────────────────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"HubSpot Tests: {PASS} passed, {FAIL} failed out of {PASS+FAIL}")
print(f"{'='*50}")
if FAIL:
    sys.exit(1)
