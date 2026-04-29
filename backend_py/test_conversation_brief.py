"""Conversation brief smoke tests."""
import os
import json
import time

os.environ.setdefault("AUTH_REQUIRED", "0")

from app import app

client = app.test_client()
RUN_ID = int(time.time())
TAG = f"brief-{RUN_ID}"
USER_ID = 901
OTHER_USER_ID = 902


def hdr(uid=USER_ID, cid=None):
    headers = {"X-User-ID": str(uid)}
    if cid is not None:
        headers["X-Client-ID"] = str(cid)
    return headers


print("=" * 64)
print("CONVERSATION BRIEF TESTS")
print("=" * 64)

print("[1] Mark onboarding complete for test user")
r = client.patch(
    "/api/settings/user",
    data=json.dumps({"preferences": {"onboarding_completed": True}}),
    content_type="application/json",
    headers=hdr(USER_ID),
)
assert r.status_code == 200, r.get_data(as_text=True)
print("    OK: onboarding bypass ready")

print("[2] Create a scoped client")
r = client.post(
    "/api/clients",
    data=json.dumps({"type": "person", "name": f"{TAG}-client"}),
    content_type="application/json",
    headers=hdr(USER_ID),
)
assert r.status_code == 200, r.get_data(as_text=True)
client_data = r.get_json() or {}
client_id = int(((client_data.get("client") or {}).get("id")) or 0)
assert client_id > 0
print(f"    OK: created client_id={client_id}")

print("[3] Create a new conversation")
r = client.post(
    "/api/conversations/new",
    data=json.dumps({
        "workspace_slug": "personal",
        "agent_slug": "life-coach",
        "title": f"{TAG}-chat",
    }),
    content_type="application/json",
    headers=hdr(USER_ID, client_id),
)
assert r.status_code == 200, r.get_data(as_text=True)
data = r.get_json()
assert data.get("success") is True
conv_id = int(data["conv_id"])
print(f"    OK: created conv_id={conv_id}")

payload = {
    "objective": f"{TAG} objective",
    "current_status": f"{TAG} status",
    "next_step": f"{TAG} next",
    "blocked_by": f"{TAG} blocker",
}

print("[4] PATCH /api/conversations/<id>/brief")
r = client.patch(
    f"/api/conversations/{conv_id}/brief",
    data=json.dumps(payload),
    content_type="application/json",
    headers=hdr(USER_ID, client_id),
)
assert r.status_code == 200, r.get_data(as_text=True)
brief_resp = r.get_json()
assert brief_resp.get("success") is True
brief = brief_resp.get("brief") or {}
for key, value in payload.items():
    assert brief.get(key) == value, f"expected {key}={value!r}, got {brief.get(key)!r}"
assert brief.get("updated_at"), "updated_at should be set after save"
print("    OK: brief saved and timestamped")

print("[5] GET /api/conversations/<id>/brief persists")
r = client.get(f"/api/conversations/{conv_id}/brief", headers=hdr(USER_ID, client_id))
assert r.status_code == 200, r.get_data(as_text=True)
brief = (r.get_json() or {}).get("brief") or {}
for key, value in payload.items():
    assert brief.get(key) == value, f"persisted {key} mismatch"
print("    OK: brief persists across requests")

print("[6] GET /api/conversations includes brief signal for re-entry")
r = client.get("/api/conversations", headers=hdr(USER_ID, client_id))
assert r.status_code == 200, r.get_data(as_text=True)
convs = r.get_json() or []
conv = next((item for item in convs if int(item.get("id") or 0) == conv_id), None)
assert conv, f"conversation {conv_id} missing from list payload"
assert conv.get("has_brief") is True
brief = conv.get("brief") or {}
for key, value in payload.items():
    assert brief.get(key) == value, f"list brief {key} mismatch"
signal = conv.get("brief_signal") or {}
assert signal.get("field") == "blocked_by", signal
assert signal.get("label") == "Blocked", signal
assert payload["blocked_by"] in str(signal.get("text") or ""), signal
print("    OK: conversation list exposes brief signal for fast re-entry")

print("[7] GET /chat/... renders conversation brief")
r = client.get(f"/chat/personal/life-coach?conv_id={conv_id}&client_id={client_id}", headers=hdr(USER_ID, client_id))
assert r.status_code == 200, r.get_data(as_text=True)
html = r.get_data(as_text=True)
assert "Conversation Brief" in html
assert "Resume this thread in under 30 seconds." in html
for value in payload.values():
    assert value in html, f"missing rendered value {value!r}"
print("    OK: chat page renders brief card with saved values")

print("[8] GET /chat home shows brief signal for fast re-entry")
r = client.get(f"/chat?client_id={client_id}", headers=hdr(USER_ID, client_id))
assert r.status_code == 200, r.get_data(as_text=True)
html = r.get_data(as_text=True)
assert "Brief" in html
assert "Blocked:" in html
assert payload["blocked_by"] in html, "chat home should surface brief signal text"
print("    OK: chat home surfaces brief signal on agent card")

print("[9] Isolation: other user cannot read or write brief")
r = client.get(f"/api/conversations/{conv_id}/brief", headers=hdr(OTHER_USER_ID, client_id))
assert r.status_code == 404, r.get_data(as_text=True)
r = client.patch(
    f"/api/conversations/{conv_id}/brief",
    data=json.dumps({"objective": "should-not-work"}),
    content_type="application/json",
    headers=hdr(OTHER_USER_ID, client_id),
)
assert r.status_code == 404, r.get_data(as_text=True)
print("    OK: brief is user-isolated")

print("[10] Cleanup conversation")
r = client.delete(f"/api/conversations/{conv_id}", headers=hdr(USER_ID, client_id))
assert r.status_code == 200, r.get_data(as_text=True)
r = client.delete(f"/api/clients/{client_id}", headers=hdr(USER_ID))
assert r.status_code == 200, r.get_data(as_text=True)
print("    OK: cleanup complete")

print("\nOK: CONVERSATION BRIEF TESTS PASSED")
