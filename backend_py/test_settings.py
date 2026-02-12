"""Global settings API smoke tests (script-style)."""
import json
import time
from app import app, get_db

client = app.test_client()
RUN_ID = int(time.time())
TAG = f"settings-{RUN_ID}"


def hdr(uid=1, cid=None):
    h = {"X-User-ID": str(uid)}
    if cid is not None:
        h["X-Client-ID"] = str(cid)
    return h


print("=" * 64)
print("SETTINGS TESTS")
print("=" * 64)

# 1) Settings page route
print("[1] GET /settings")
r = client.get("/settings", headers=hdr(1))
assert r.status_code == 200, r.get_data(as_text=True)
html = r.get_data(as_text=True)
assert "Settings" in html
print("    OK: settings page renders")

# 2) GET user settings defaults/current
print("[2] GET /api/settings/user")
r = client.get("/api/settings/user", headers=hdr(1))
assert r.status_code == 200, r.get_data(as_text=True)
data = r.get_json()
assert data.get("success") is True
assert isinstance(data.get("settings"), dict)
for key in ["profile", "preferences", "notifications", "orchestrator", "privacy", "integrations", "appearance", "economy"]:
    assert key in data["settings"], f"missing key {key}"
print("    OK: user settings payload shape")

# 3) PATCH user settings
print("[3] PATCH /api/settings/user")
patch_payload = {
    "profile": {
        "display_name": TAG,
        "email": f"{TAG}@example.com",
        "timezone": "America/New_York",
        "language": "en",
    },
    "preferences": {
        "default_workspace": "business",
        "compact_sidebar": True,
        "reduce_motion": True,
    },
    "orchestrator": {
        "grid_style": "lines",
        "default_zoom": 125,
    },
    "integrations": {
        "preferred_llm": "OpenAI",
        "byok_enabled": True,
    },
    "privacy": {
        "retain_days": 365,
    },
}
r = client.patch("/api/settings/user", data=json.dumps(patch_payload), content_type="application/json", headers=hdr(1))
assert r.status_code == 200, r.get_data(as_text=True)
out = r.get_json()
assert out.get("success") is True
assert out["settings"]["profile"]["display_name"] == TAG
assert out["settings"]["preferences"]["default_workspace"] == "business"
assert out["settings"]["orchestrator"]["grid_style"] == "lines"
assert out["settings"]["integrations"]["preferred_llm"] == "OpenAI"
print("    OK: patch persisted")

# 4) GET verifies persistence
print("[4] GET /api/settings/user persists")
r = client.get("/api/settings/user", headers=hdr(1))
assert r.status_code == 200
s = r.get_json()["settings"]
assert s["profile"]["display_name"] == TAG
assert s["preferences"]["compact_sidebar"] is True
assert s["preferences"]["reduce_motion"] is True
assert s["privacy"]["retain_days"] == 365
print("    OK: persisted across requests")

# 5) Partial PATCH keeps prior values
print("[5] PATCH partial merge")
r = client.patch(
    "/api/settings/user",
    data=json.dumps({"preferences": {"show_tips": False}}),
    content_type="application/json",
    headers=hdr(1),
)
assert r.status_code == 200
s = r.get_json()["settings"]
assert s["preferences"]["show_tips"] is False
assert s["preferences"]["default_workspace"] == "business"
print("    OK: deep merge works")

# 6) Invalid values are sanitized
print("[6] PATCH invalid values sanitize")
r = client.patch(
    "/api/settings/user",
    data=json.dumps({
        "preferences": {"default_workspace": "invalid-ws"},
        "orchestrator": {"grid_style": "wild", "default_zoom": 9999},
        "privacy": {"retain_days": -10},
        "integrations": {"preferred_llm": "Unknown"},
        "economy": {"monthly_reset_day": 99, "monthly_reset_hour": 99, "monthly_reset_minute": 99},
    }),
    content_type="application/json",
    headers=hdr(1),
)
assert r.status_code == 200
s = r.get_json()["settings"]
assert s["preferences"]["default_workspace"] == "agency"
assert s["orchestrator"]["grid_style"] == "dots"
assert s["orchestrator"]["default_zoom"] == 200
assert s["privacy"]["retain_days"] == 7
assert s["integrations"]["preferred_llm"] == "Grok"
assert int(s["economy"]["monthly_reset_day"]) == 28
assert int(s["economy"].get("monthly_reset_hour") or 0) == 23
assert int(s["economy"].get("monthly_reset_minute") or 0) == 45
print("    OK: sanitization and clamping work")

# 7) Isolation per user
print("[7] User isolation")
r = client.get("/api/settings/user", headers=hdr(2))
assert r.status_code == 200
s2 = r.get_json()["settings"]
assert s2["profile"].get("display_name", "") != TAG
print("    OK: user settings isolated")

# 8) Summary endpoint
print("[8] GET /api/settings/summary")
r = client.get("/api/settings/summary", headers=hdr(1))
assert r.status_code == 200
summary = r.get_json()
assert summary.get("success") is True
for key in ["agents", "connectors", "connected_connectors", "flows", "templates", "chats", "clients", "client_accounts"]:
    assert key in summary.get("counts", {}), f"missing count {key}"
print("    OK: summary includes expected counters")

# 9) Reset endpoint
print("[9] POST /api/settings/user/reset")
r = client.post("/api/settings/user/reset", headers=hdr(1))
assert r.status_code == 200
s = r.get_json()["settings"]
assert s["preferences"]["default_workspace"] == "agency"
assert s["profile"]["display_name"] == ""
print("    OK: reset to defaults")

# 10) Export contains user_settings
print("[10] GET /api/export includes user_settings")
r = client.get("/api/export", headers=hdr(1))
assert r.status_code == 200
exp = r.get_json()
assert "user_settings" in exp
assert isinstance(exp["user_settings"], dict)
print("    OK: export includes settings")

# 11) Import can restore settings
print("[11] POST /api/import restores user_settings")
import_payload = {
    "version": "1.3",
    "user_settings": {
        "profile": {"display_name": f"{TAG}-imported", "language": "ro"},
        "preferences": {"default_workspace": "development", "compact_sidebar": True},
        "orchestrator": {"grid_style": "off", "default_zoom": 90},
    },
}
r = client.post("/api/import", data=json.dumps(import_payload), content_type="application/json", headers=hdr(1))
assert r.status_code == 200, r.get_data(as_text=True)
imp = r.get_json()
assert imp.get("success") is True
assert int(imp.get("counts", {}).get("user_settings", 0)) == 1

r = client.get("/api/settings/user", headers=hdr(1))
assert r.status_code == 200
s = r.get_json()["settings"]
assert s["profile"]["display_name"] == f"{TAG}-imported"
assert s["preferences"]["default_workspace"] == "development"
assert s["orchestrator"]["grid_style"] == "off"
print("    OK: import updates settings row")

# 12) Client header does not break settings endpoint
print("[12] GET /api/settings/user with X-Client-ID")
r = client.get("/api/settings/user", headers=hdr(1, 999999))
assert r.status_code == 200
assert r.get_json().get("success") is True
print("    OK: settings endpoint is client-safe")

# 13) Default landing preference redirects from /
print("[13] GET / follows default_landing preference")
r = client.patch(
    "/api/settings/user",
    data=json.dumps({"preferences": {"default_landing": "orchestrator", "default_workspace": "development"}}),
    content_type="application/json",
    headers=hdr(1),
)
assert r.status_code == 200
r = client.get("/", headers=hdr(1), follow_redirects=False)
assert r.status_code in (301, 302, 307, 308)
location = r.headers.get("Location", "")
assert location.endswith("/orchestrator"), location
print("    OK: / redirects to preferred landing")

# 14) New conversation falls back to default_workspace when omitted
print("[14] POST /api/conversations/new uses default_workspace fallback")
r = client.post(
    "/api/conversations/new",
    data=json.dumps({}),
    content_type="application/json",
    headers=hdr(1),
)
assert r.status_code == 200, r.get_data(as_text=True)
conv_resp = r.get_json()
assert conv_resp.get("success") is True
redirect_url = str(conv_resp.get("redirect") or conv_resp.get("url") or "")
assert redirect_url.startswith("/chat/development/"), redirect_url
print("    OK: conversation fallback workspace honored")

# 15) /?home=1 bypasses default landing redirect
print("[15] GET /?home=1 bypasses redirect")
r = client.get("/?home=1", headers=hdr(1))
assert r.status_code == 200
assert "Workspaces" in r.get_data(as_text=True)
print("    OK: explicit home bypass works")
# 16) always_open_home bypasses landing redirect on /
print("[16] always_open_home bypass")
r = client.patch(
    "/api/settings/user",
    data=json.dumps({"preferences": {"default_landing": "orchestrator", "always_open_home": True}}),
    content_type="application/json",
    headers=hdr(1),
)
assert r.status_code == 200
r = client.get("/", headers=hdr(1), follow_redirects=False)
assert r.status_code == 200
assert "Workspaces" in r.get_data(as_text=True)
print("    OK: always_open_home bypasses landing redirect")

# 17) User snapshot + CT ledger smoke
print("[17] GET /api/user/snapshot ledger payload")
r = client.get("/api/user/snapshot", headers=hdr(1))
assert r.status_code == 200, r.get_data(as_text=True)
snap = r.get_json()
assert snap.get("success") is True
for key in ["ct_balance", "ct_used_month", "ct_usage_pct", "requests_today", "tier", "monthly_reset_hour", "monthly_reset_minute"]:
    assert key in snap, f"missing snapshot key {key}"
print("    OK: snapshot returns CT ledger fields")

# 18) Top-up then spend updates balance deterministically
print("[18] POST /api/user/topup + /api/user/spend")
r = client.patch(
    "/api/settings/user",
    data=json.dumps({"economy": {"daily_limit": 500000, "cost_multiplier": 1.0}}),
    content_type="application/json",
    headers=hdr(1),
)
assert r.status_code == 200, r.get_data(as_text=True)
before = int(snap.get("ct_balance") or 0)
r = client.post("/api/user/topup", data=json.dumps({"amount": 250, "description": "test topup"}), content_type="application/json", headers=hdr(1))
assert r.status_code == 200, r.get_data(as_text=True)
top = r.get_json()
assert top.get("success") is True
after_top = int(top.get("new_balance") or 0)
assert after_top >= before + 250
r = client.post("/api/user/spend", data=json.dumps({"amount": 40, "event_type": "qa_test", "description": "test spend"}), content_type="application/json", headers=hdr(1))
assert r.status_code == 200, r.get_data(as_text=True)
sp = r.get_json()
assert sp.get("success") is True
after_spend = int(sp.get("new_balance") or 0)
assert after_spend <= after_top - 40
print("    OK: top-up and spend mutate ledger balance")

# 19) Pricing preset applies economy defaults
print("[19] PATCH /api/settings/user preset=pro")
r = client.patch(
    "/api/settings/user",
    data=json.dumps({"preset": "pro"}),
    content_type="application/json",
    headers=hdr(1),
)
assert r.status_code == 200, r.get_data(as_text=True)
out = r.get_json()
assert out.get("success") is True
se = out.get("settings", {}).get("economy", {})
assert se.get("preset") == "pro"
assert float(se.get("cost_multiplier")) == 0.7
assert int(se.get("monthly_grant")) == 10000
assert int(se.get("max_per_message")) == 150
assert int(se.get("daily_limit")) == 1000
assert int(se.get("monthly_reset_day")) == 1
assert int(se.get("monthly_reset_hour") or 0) == 0
assert int(se.get("monthly_reset_minute") or 0) == 0
print("    OK: preset pro applied with expected defaults")

# 20) Manual top-level overrides apply on top of preset
print("[20] PATCH /api/settings/user top-level overrides")
r = client.patch(
    "/api/settings/user",
    data=json.dumps({"cost_multiplier": 0.55, "max_per_message": 210, "daily_limit": 4321, "monthly_grant": 23456, "monthly_reset_day": 15, "monthly_reset_hour": 8, "monthly_reset_minute": 30}),
    content_type="application/json",
    headers=hdr(1),
)
assert r.status_code == 200, r.get_data(as_text=True)
out = r.get_json() or {}
assert out.get("success") is True
se = out.get("settings", {}).get("economy", {})
assert se.get("preset") == "pro"
assert abs(float(se.get("cost_multiplier")) - 0.55) < 1e-9
assert int(se.get("max_per_message")) == 210
assert int(se.get("daily_limit")) == 4321
assert int(se.get("monthly_grant")) == 23456
assert int(se.get("monthly_reset_day")) == 15
assert int(se.get("monthly_reset_hour") or 0) == 8
assert int(se.get("monthly_reset_minute") or 0) == 30
r = client.get("/api/user/snapshot", headers=hdr(1))
assert r.status_code == 200
snap2 = r.get_json() or {}
assert abs(float(snap2.get("cost_multiplier") or 0) - 0.55) < 1e-9
assert int(snap2.get("max_per_message") or 0) == 210
assert int(snap2.get("daily_limit") or 0) == 4321
assert int(snap2.get("monthly_grant") or 0) == 23456
assert int(snap2.get("monthly_reset_day") or 0) == 15
assert int(snap2.get("monthly_reset_hour") or 0) == 8
assert int(snap2.get("monthly_reset_minute") or 0) == 30
print("    OK: top-level overrides persisted and surfaced in snapshot")

# 21) Daily CT limit is enforced (429)
print("[21] Daily limit enforcement on /api/user/spend")
r = client.patch(
    "/api/settings/user",
    data=json.dumps({"economy": {"daily_limit": 1, "cost_multiplier": 1.0}}),
    content_type="application/json",
    headers=hdr(1),
)
assert r.status_code == 200, r.get_data(as_text=True)
r = client.post(
    "/api/user/spend",
    data=json.dumps({"amount": 100, "event_type": "daily_limit_test", "description": "daily limit smoke"}),
    content_type="application/json",
    headers=hdr(1),
)
assert r.status_code == 429, r.get_data(as_text=True)
err = r.get_json() or {}
assert err.get("success") is False
assert "daily" in str(err.get("error", "")).lower()
print("    OK: daily CT limit blocks spend with 429")

# 22) Shadow usage ledger insert exists for request_id (no CT debit assertion)
print("[22] Shadow usage ledger insert by request_id")
shadow_request_id = f"shadow-{RUN_ID}"
r = client.post(
    "/api/user/spend",
    data=json.dumps({
        "amount": 1,
        "event_type": "run_flow",
        "description": "shadow ledger test",
        "request_id": shadow_request_id,
    }),
    content_type="application/json",
    headers=hdr(1),
)
# May be blocked by configured limits, but row should still be written in shadow preflight.
assert r.status_code in (200, 402, 429), r.get_data(as_text=True)
conn = get_db()
row = conn.execute(
    """
    SELECT request_id, event_type, provider, model, cost_final_usd
    FROM usage_ledger
    WHERE request_id = ?
    ORDER BY id DESC
    LIMIT 1
    """,
    (shadow_request_id,),
).fetchone()
conn.close()
assert row is not None, "usage_ledger missing shadow row"
assert str(row["request_id"]) == shadow_request_id
assert str(row["event_type"]) == "run_flow"
assert float(row["cost_final_usd"] or 0.0) == 0.0
print("    OK: shadow row written with request_id and zero final cost")

# restore default for deterministic local behavior
client.post("/api/settings/user/reset", headers=hdr(1))

print("\n" + "=" * 64)
print("ALL SETTINGS TESTS PASSED")
print("=" * 64)



