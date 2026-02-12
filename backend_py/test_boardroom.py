"""Boardroom + Maturity Index + Active Context — Full Test Suite"""
import requests, sys, json

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

print("\n🏛️  Boardroom + Maturity + Context Tests")
print("=" * 55)

# ── Boardroom ──────────────────────────────────────────────

print("\n📋 Boardroom API:")

def t_templates():
    r = requests.get(f"{BASE}/api/boardroom/templates")
    assert r.status_code == 200
    d = r.json()
    assert len(d["templates"]) == 10
    names = [t["id"] for t in d["templates"]]
    assert "strategy-review" in names
    assert "crisis-war-room" in names
    assert "custom-sandbox" in names
test("GET /templates → 10 meeting types", t_templates)

def t_agents():
    r = requests.get(f"{BASE}/api/boardroom/agents")
    assert r.status_code == 200
    d = r.json()
    assert len(d["agents"]) == 20
    slugs = [a["slug"] for a in d["agents"]]
    assert "ceo-strategy" in slugs
    assert "creative-muse" in slugs
test("GET /agents → 20 agents with colors", t_agents)

def t_meetings_list():
    r = requests.get(f"{BASE}/api/boardroom/meetings")
    assert r.status_code == 200
    d = r.json()
    assert len(d["meetings"]) >= 3  # 3 mock meetings
    assert d["meetings"][0]["status"] == "completed"
test("GET /meetings → ≥3 mock meetings", t_meetings_list)

def t_meeting_detail():
    r = requests.get(f"{BASE}/api/boardroom/meetings/mtg-001")
    assert r.status_code == 200
    d = r.json()
    assert d["title"] == "Q1 2026 Strategy Alignment"
    assert len(d["transcript"]) >= 8
    assert len(d["action_items"]) >= 3
    assert d["summary"] != ""
test("GET /meetings/mtg-001 → full transcript + actions", t_meeting_detail)

def t_meeting_detail_2():
    r = requests.get(f"{BASE}/api/boardroom/meetings/mtg-002")
    d = r.json()
    assert d["template_id"] == "tech-architecture"
    assert "backend-architect" in d["agents"]
test("GET /meetings/mtg-002 → tech architecture meeting", t_meeting_detail_2)

def t_create_meeting():
    r = requests.post(f"{BASE}/api/boardroom/meetings", json={
        "template_id": "creative-brainstorm",
        "title": "Test Brainstorm Session",
        "agents": ["creative-director", "creative-muse", "social-media"],
        "topic": "Generate ideas for the Q2 product rebrand.",
        "rounds": 2,
        "config": {"complexity": "medium"},
    })
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "completed"
    assert len(d["transcript"]) == 6  # 3 agents × 2 rounds
    assert len(d["action_items"]) >= 2
    assert d["summary"] != ""
    assert d["title"] == "Test Brainstorm Session"
test("POST /meetings → create + run meeting (3 agents, 2 rounds)", t_create_meeting)

def t_create_too_few():
    r = requests.post(f"{BASE}/api/boardroom/meetings", json={
        "agents": ["ceo-strategy"],
        "topic": "Solo",
    })
    assert r.status_code == 400
    d = r.json()
    assert "error" in d
test("POST /meetings → rejects <2 agents", t_create_too_few)

def t_create_war_room():
    r = requests.post(f"{BASE}/api/boardroom/meetings", json={
        "template_id": "crisis-war-room",
        "title": "Production Incident P1",
        "agents": ["cto-innovation", "devops-infra", "security-quality", "ceo-strategy", "coo-operations"],
        "topic": "Production database failure — 500 errors across all services.",
        "rounds": 3,
    })
    d = r.json()
    assert d["status"] == "completed"
    assert len(d["transcript"]) == 15  # 5 agents × 3 rounds
    assert len(d["agents"]) == 5
test("POST /meetings → war room (5 agents, 3 rounds, 15 msgs)", t_create_war_room)

# ── Maturity Index ─────────────────────────────────────────

print("\n📊 Maturity Index API:")

def t_maturity():
    r = requests.get(f"{BASE}/api/maturity")
    assert r.status_code == 200
    d = r.json()
    # Check structure
    for key in ("cmi", "pmi", "ami", "dmi", "factors", "accounting", "recommendations"):
        assert key in d, f"Missing: {key}"
    # CMI structure
    assert "score" in d["cmi"]
    assert "level" in d["cmi"]
    assert d["cmi"]["level"]["label"] in ("Starter", "Growing", "Intermediate", "Advanced", "Expert")
    # Sub-indices
    for sub in ("pmi", "ami", "dmi"):
        assert "score" in d[sub]
        assert "pct" in d[sub]
        assert "level" in d[sub]
test("GET /maturity → CMI + PMI + AMI + DMI structure", t_maturity)

def t_maturity_factors():
    r = requests.get(f"{BASE}/api/maturity")
    d = r.json()
    factors = d["factors"]
    assert len(factors) >= 10
    for key in ("connectors_active", "agents_configured", "meetings_held", "monthly_budget"):
        assert key in factors
        assert "raw" in factors[key]
        assert "normalized" in factors[key]
        assert "weighted_score" in factors[key]
test("GET /maturity → 13+ factors with weights", t_maturity_factors)

def t_maturity_accounting():
    r = requests.get(f"{BASE}/api/maturity")
    d = r.json()
    acc = d["accounting"]
    for key in ("monthly_revenue", "burn_rate", "arr", "profit_margin", "runway_months"):
        assert key in acc
    assert acc["monthly_revenue"] > 0
test("GET /maturity → accounting snapshot", t_maturity_accounting)

def t_maturity_recommendations():
    r = requests.get(f"{BASE}/api/maturity")
    d = r.json()
    recs = d["recommendations"]
    assert len(recs) >= 1
    assert "title" in recs[0]
    assert "icon" in recs[0]
test("GET /maturity → recommendations", t_maturity_recommendations)

# ── Active Context ─────────────────────────────────────────

print("\n🔴 Active Context API:")

def t_context():
    r = requests.get(f"{BASE}/api/active-context")
    assert r.status_code == 200
    d = r.json()
    for key in ("session", "maturity_snapshot", "active_connectors", "active_agents", "business_context", "contextual_signals", "next_actions"):
        assert key in d, f"Missing: {key}"
test("GET /active-context → all sections present", t_context)

def t_context_business():
    r = requests.get(f"{BASE}/api/active-context")
    d = r.json()
    biz = d["business_context"]
    assert biz["businesses"] >= 1
    assert biz["total_budget"] > 0
    assert "accounting_summary" in biz
    assert biz["accounting_summary"]["health"] in ("healthy", "at-risk")
test("GET /active-context → business + accounting", t_context_business)

def t_context_signals():
    r = requests.get(f"{BASE}/api/active-context")
    d = r.json()
    signals = d["contextual_signals"]
    assert len(signals) >= 2
    types = set(s["type"] for s in signals)
    assert "insight" in types or "alert" in types
test("GET /active-context → contextual signals", t_context_signals)

# ── Page Rendering ─────────────────────────────────────────

print("\n🌐 Page Rendering:")

def t_boardroom_page():
    r = requests.get(f"{BASE}/boardroom")
    assert r.status_code == 200
    assert "Boardroom" in r.text
    assert "brInit" in r.text
    assert "brRunMeeting" in r.text
    assert "Maturity Index" in r.text
    assert "Active Context" in r.text
test("GET /boardroom → page renders with all panels", t_boardroom_page)

def t_sidebar():
    r = requests.get(f"{BASE}/boardroom")
    assert "bi-people-fill" in r.text
    assert 'href="/boardroom"' in r.text
test("Sidebar → Boardroom link present", t_sidebar)

print(f"\n{'=' * 55}")
print(f"Results: {passed} passed, {failed} failed out of {passed + failed}")
sys.exit(1 if failed else 0)
