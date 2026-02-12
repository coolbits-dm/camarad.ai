"""GA4 Mock Connector — Endpoint Tests"""
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

print("\n🔬 GA4 Mock Connector Tests\n" + "=" * 50)

# 1 — Properties
def t_properties():
    r = requests.get(f"{BASE}/api/connectors/ga4/properties")
    assert r.status_code == 200
    d = r.json()
    assert len(d["properties"]) == 3
    assert d["properties"][0]["stream"] in ("Web", "iOS", "Android")
test("GET /properties → 3 properties", t_properties)

# 2 — Overview
def t_overview():
    r = requests.get(f"{BASE}/api/connectors/ga4/overview?property_id=GA4-001")
    assert r.status_code == 200
    d = r.json()
    for k in ("sessions", "users", "conversions", "revenue", "bounce_rate", "engagement_rate"):
        assert k in d, f"Missing key: {k}"
    assert "comparison" in d
test("GET /overview → KPIs + comparison", t_overview)

# 3 — Pages
def t_pages():
    r = requests.get(f"{BASE}/api/connectors/ga4/pages?property_id=G-ABC123DEF4")
    d = r.json()
    assert len(d["pages"]) >= 5
    p = d["pages"][0]
    for k in ("path", "title", "views", "sessions", "users", "avg_time", "bounce_rate", "conversions"):
        assert k in p, f"Missing key: {k}"
test("GET /pages → ≥5 pages with all fields", t_pages)

# 4 — Sources
def t_sources():
    r = requests.get(f"{BASE}/api/connectors/ga4/sources?property_id=GA4-001")
    d = r.json()
    assert len(d["sources"]) >= 5
    s = d["sources"][0]
    for k in ("source", "medium", "sessions", "users", "conversions", "revenue", "bounce_rate"):
        assert k in s
test("GET /sources → ≥5 sources", t_sources)

# 5 — Events
def t_events():
    r = requests.get(f"{BASE}/api/connectors/ga4/events?property_id=GA4-001")
    d = r.json()
    assert len(d["events"]) >= 10
    cats = set(e["category"] for e in d["events"])
    assert "Auto" in cats and "Ecommerce" in cats
test("GET /events → ≥10 events, Auto+Ecommerce", t_events)

# 6 — Devices
def t_devices():
    r = requests.get(f"{BASE}/api/connectors/ga4/devices?property_id=GA4-001")
    d = r.json()
    assert len(d["devices"]) == 3
    names = [dev["category"] for dev in d["devices"]]
    assert "desktop" in names and "mobile" in names
test("GET /devices → 3 categories", t_devices)

# 7 — Countries
def t_countries():
    r = requests.get(f"{BASE}/api/connectors/ga4/countries?property_id=GA4-001")
    d = r.json()
    assert len(d["countries"]) >= 5
test("GET /countries → ≥5 countries", t_countries)

# 8 — Funnel
def t_funnel():
    r = requests.get(f"{BASE}/api/connectors/ga4/funnel?type=ecommerce")
    d = r.json()
    assert "steps" in d and len(d["steps"]) >= 3
    assert "overall_conversion" in d
    # Check drop-off
    assert "drop_off" in d["steps"][1]
test("GET /funnel?type=ecommerce → steps + drop-off", t_funnel)

# 9 — Timeseries
def t_timeseries():
    r = requests.get(f"{BASE}/api/connectors/ga4/timeseries?property_id=G-ABC123DEF4")
    d = r.json()
    assert len(d["daily"]) >= 7
    ts = d["daily"][0]
    for k in ("date", "sessions", "users", "conversions"):
        assert k in ts
test("GET /timeseries → ≥7 days", t_timeseries)

# 10 — Test API call
def t_test_call():
    r = requests.post(f"{BASE}/api/connectors/ga4/test-call", json={
        "method": "POST", "endpoint": "runReport"
    })
    d = r.json()
    assert d["response"]["status_code"] == 200
    assert "latency_ms" in d
    assert "quota" in d
test("POST /test-call → 200 + quota", t_test_call)

# 11 — Page renders
def t_page():
    r = requests.get(f"{BASE}/connectors")
    assert r.status_code == 200
    assert "ga4Panel" in r.text
    assert "ga4Init" in r.text
    assert "ga4Connect" in r.text
test("GET /connectors page → GA4 panel + JS", t_page)

print(f"\n{'=' * 50}")
print(f"Results: {passed} passed, {failed} failed out of {passed + failed}")
sys.exit(1 if failed else 0)
