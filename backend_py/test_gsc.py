"""Google Search Console Mock Connector — Endpoint Tests"""
import requests, sys

BASE = "http://localhost:5051"
passed = failed = 0

def test(name, fn):
    global passed, failed
    try:
        fn()
        print(f"  ✅ {name}")
        passed += 1
    except Exception as e:
        print(f"  ❌ {name}: {e}")
        failed += 1

print("\n🔬 Google Search Console Mock Connector Tests\n" + "=" * 55)

# 1 — Properties
def t_properties():
    r = requests.get(f"{BASE}/api/connectors/google-search-console/properties")
    assert r.status_code == 200
    d = r.json()
    assert len(d["properties"]) == 3
    types = [p["type"] for p in d["properties"]]
    assert "Domain" in types
    assert "URL prefix" in types
    assert all("verified" in p for p in d["properties"])
test("GET /properties → 3 properties (Domain + URL prefix)", t_properties)

# 2 — Overview
def t_overview():
    r = requests.get(f"{BASE}/api/connectors/google-search-console/overview?property_id=sc-domain:camarad.ai")
    assert r.status_code == 200
    d = r.json()
    for k in ("total_clicks", "total_impressions", "avg_ctr", "avg_position",
              "clicks_change", "impressions_change", "ctr_change", "position_change",
              "top_query", "top_page", "crawl_errors", "indexed_pages"):
        assert k in d, f"Missing key: {k}"
    assert d["total_clicks"] > 0
    assert d["indexed_pages"] > 0
test("GET /overview → 12 KPI fields + change deltas", t_overview)

# 3 — Queries
def t_queries():
    r = requests.get(f"{BASE}/api/connectors/google-search-console/queries?property_id=sc-domain:camarad.ai")
    d = r.json()
    assert len(d["queries"]) >= 10
    q = d["queries"][0]
    for k in ("query", "clicks", "impressions", "ctr", "position"):
        assert k in q, f"Missing key: {k}"
    assert d["queries"][0]["clicks"] >= d["queries"][1]["clicks"]  # sorted desc
test("GET /queries → ≥10 queries with all search fields", t_queries)

# 4 — Pages
def t_pages():
    r = requests.get(f"{BASE}/api/connectors/google-search-console/pages?property_id=sc-domain:camarad.ai")
    d = r.json()
    assert len(d["pages"]) >= 8
    p = d["pages"][0]
    for k in ("page", "clicks", "impressions", "ctr", "position"):
        assert k in p, f"Missing key: {k}"
test("GET /pages → ≥8 pages with performance data", t_pages)

# 5 — Countries
def t_countries():
    r = requests.get(f"{BASE}/api/connectors/google-search-console/countries?property_id=sc-domain:camarad.ai")
    d = r.json()
    assert len(d["countries"]) >= 5
    c = d["countries"][0]
    for k in ("country", "code", "clicks", "impressions", "ctr", "position"):
        assert k in c, f"Missing key: {k}"
    codes = [x["code"] for x in d["countries"]]
    assert "RO" in codes  # Romania should be present
test("GET /countries → ≥5 countries, includes RO", t_countries)

# 6 — Devices
def t_devices():
    r = requests.get(f"{BASE}/api/connectors/google-search-console/devices?property_id=sc-domain:camarad.ai")
    d = r.json()
    assert len(d["devices"]) == 3
    device_names = [x["device"] for x in d["devices"]]
    assert "Mobile" in device_names
    assert "Desktop" in device_names
    assert "Tablet" in device_names
    for dev in d["devices"]:
        assert "share" in dev
        assert dev["clicks"] > 0
test("GET /devices → Mobile + Desktop + Tablet with share %", t_devices)

# 7 — Index Coverage
def t_index_coverage():
    r = requests.get(f"{BASE}/api/connectors/google-search-console/index-coverage?property_id=sc-domain:camarad.ai")
    assert r.status_code == 200
    d = r.json()
    assert "summary" in d
    s = d["summary"]
    for k in ("valid", "warning", "error", "excluded"):
        assert k in s, f"Missing summary key: {k}"
    assert s["valid"] > 1000
    assert "errors" in d
    assert "warnings" in d
    assert "excluded" in d
    assert len(d["errors"]) >= 2
    assert len(d["warnings"]) >= 2
    assert len(d["excluded"]) >= 3
test("GET /index-coverage → summary + errors + warnings + excluded", t_index_coverage)

# 8 — Sitemaps
def t_sitemaps():
    r = requests.get(f"{BASE}/api/connectors/google-search-console/sitemaps?property_id=sc-domain:camarad.ai")
    d = r.json()
    assert len(d["sitemaps"]) >= 3
    s = d["sitemaps"][0]
    for k in ("url", "type", "status", "submitted", "last_read", "discovered_urls", "indexed_urls"):
        assert k in s, f"Missing key: {k}"
    assert any(x["status"] == "Success" for x in d["sitemaps"])
test("GET /sitemaps → ≥3 sitemaps with full status", t_sitemaps)

# 9 — Timeseries
def t_timeseries():
    r = requests.get(f"{BASE}/api/connectors/google-search-console/timeseries?property_id=sc-domain:camarad.ai&days=14")
    d = r.json()
    assert d["days"] == 14
    assert len(d["daily"]) == 14
    day = d["daily"][0]
    for k in ("date", "clicks", "impressions", "ctr", "position"):
        assert k in day, f"Missing key: {k}"
test("GET /timeseries → 14 days of daily search data", t_timeseries)

# 10 — Test API Call (searchAnalytics)
def t_test_api_search():
    r = requests.post(f"{BASE}/api/connectors/google-search-console/test-call", json={
        "method": "POST",
        "endpoint": "/webmasters/v3/sites/sc-domain:camarad.ai/searchAnalytics/query"
    })
    d = r.json()
    assert "request" in d
    assert "response" in d
    assert d["response"]["status_code"] == 200
    assert "rows" in d["response"]["body"]
    assert "quota" in d
test("POST /test-call (searchAnalytics) → mock response + quota", t_test_api_search)

# 11 — Test API Call (urlInspection)
def t_test_api_inspection():
    r = requests.post(f"{BASE}/api/connectors/google-search-console/test-call", json={
        "method": "POST",
        "endpoint": "/webmasters/v3/urlInspection/index:inspect"
    })
    d = r.json()
    assert d["response"]["status_code"] == 200
    body = d["response"]["body"]
    assert "inspectionResult" in body
    assert "indexStatusResult" in body["inspectionResult"]
    assert "mobileUsabilityResult" in body["inspectionResult"]
test("POST /test-call (urlInspection) → index status + mobile usability", t_test_api_inspection)

# 12 — Save/Read connector status
def t_save_read():
    r = requests.post(f"{BASE}/api/connectors/google-search-console", json={
        "status": "Connected", "config": {"account": "webmaster@camarad.ai"}
    })
    assert r.status_code == 200
    r2 = requests.get(f"{BASE}/api/connectors/google-search-console")
    d = r2.json()
    assert d["status"] == "Connected"
test("POST+GET /connectors/google-search-console → save & read status", t_save_read)

# ── Summary ────────────────────────────────────────────────────────────
print(f"\n{'=' * 55}")
print(f"  Results: {passed} passed, {failed} failed out of {passed + failed}")
print(f"{'=' * 55}")
sys.exit(1 if failed else 0)
