"""M3 anti-leak scoping smoke tests for sensitive API prefixes."""
import json
import os
import time

import app as m


m.AUTH_REQUIRED = False
client = m.app.test_client()
RUN_ID = int(time.time())
PREFIX = f"m3-{RUN_ID}"


def hdr(uid=1, cid=None):
    h = {"X-User-ID": str(uid)}
    if cid is not None:
        h["X-Client-ID"] = str(cid)
    return h


def _create_client(uid, name):
    payload = {"type": "company", "company_name": name, "email": f"{name}@example.com"}
    r = client.post("/api/clients", data=json.dumps(payload), content_type="application/json", headers=hdr(uid))
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json() or {}
    assert body.get("success") is True, body
    return int(body["client"]["id"])


def _minimal_flow_payload():
    return {
        "flow": {
            "nodes": [
                {"id": "n1", "type": "trigger", "label": "Manual Trigger", "config": {"trigger_type": "manual"}}
            ],
            "connections": [],
        }
    }


def run():
    client_a = _create_client(1, f"{PREFIX}-a")
    client_b = _create_client(1, f"{PREFIX}-b")
    invalid_client_id = client_a + 999999

    ok_paths = [
        "/api/agents/list",
        "/api/connectors/list",
        "/api/flows",
        "/api/conversations",
        "/api/orchestrator/history",
        "/api/connectors/ga4/status",
    ]
    for p in ok_paths:
        r = client.get(p, headers=hdr(1, client_a))
        assert r.status_code == 200, (p, r.status_code, r.get_data(as_text=True)[:240])

    leak_paths = [
        "/api/agents/list",
        "/api/connectors/list",
        "/api/flows",
        "/api/conversations",
        "/api/orchestrator/history",
        "/api/connectors/ga4/status",
    ]
    for p in leak_paths:
        r = client.get(p, headers=hdr(1, invalid_client_id))
        assert r.status_code == 404, (p, r.status_code, r.get_data(as_text=True)[:240])

    # Orchestrator execute: valid client ok/validation, invalid 404, missing client 400
    r = client.post(
        "/api/orchestrator/execute",
        data=json.dumps(_minimal_flow_payload()),
        content_type="application/json",
        headers=hdr(1, client_a),
    )
    assert r.status_code in (200, 400), (r.status_code, r.get_data(as_text=True)[:240])
    exec_payload = r.get_json(silent=True) or {}
    exec_id = int(exec_payload.get("execution_id") or 0)

    r = client.post(
        "/api/orchestrator/execute",
        data=json.dumps(_minimal_flow_payload()),
        content_type="application/json",
        headers=hdr(1, invalid_client_id),
    )
    assert r.status_code == 404, (r.status_code, r.get_data(as_text=True)[:240])

    r = client.post(
        "/api/orchestrator/execute",
        data=json.dumps(_minimal_flow_payload()),
        content_type="application/json",
        headers=hdr(1, None),
    )
    assert r.status_code == 400, (r.status_code, r.get_data(as_text=True)[:240])

    # History detail: require client and isolate cross-client
    if exec_id > 0:
        r = client.get(f"/api/orchestrator/history/{exec_id}", headers=hdr(1, client_a))
        assert r.status_code == 200, (r.status_code, r.get_data(as_text=True)[:240])

        r = client.get(f"/api/orchestrator/history/{exec_id}", headers=hdr(1, invalid_client_id))
        assert r.status_code == 404, (r.status_code, r.get_data(as_text=True)[:240])

        r = client.get(f"/api/orchestrator/history/{exec_id}", headers=hdr(1, None))
        assert r.status_code == 400, (r.status_code, r.get_data(as_text=True)[:240])

    # Conversation detail: create scoped conversation, enforce scoping on message detail
    r = client.post(
        "/api/conversations/new",
        data=json.dumps({"workspace_slug": "personal", "agent_slug": "life-coach"}),
        content_type="application/json",
        headers=hdr(1, client_a),
    )
    assert r.status_code == 200, (r.status_code, r.get_data(as_text=True)[:240])
    conv_id = int((r.get_json() or {}).get("conv_id") or 0)
    assert conv_id > 0

    r = client.get(f"/api/conversations/{conv_id}/messages", headers=hdr(1, client_a))
    assert r.status_code == 200, (r.status_code, r.get_data(as_text=True)[:240])

    r = client.get(f"/api/conversations/{conv_id}/messages", headers=hdr(1, invalid_client_id))
    assert r.status_code == 404, (r.status_code, r.get_data(as_text=True)[:240])

    r = client.get(f"/api/conversations/{conv_id}/messages", headers=hdr(1, client_b))
    assert r.status_code == 404, (r.status_code, r.get_data(as_text=True)[:240])

    r = client.get(f"/api/conversations/{conv_id}/messages", headers=hdr(1, None))
    assert r.status_code == 400, (r.status_code, r.get_data(as_text=True)[:240])

    # Connector write path: GA4 property select requires client scope
    payload = {"propertyId": "properties/123456"}
    r = client.post("/api/connectors/ga4/property", data=json.dumps(payload), content_type="application/json", headers=hdr(1, client_a))
    assert r.status_code in (200, 400, 502), (r.status_code, r.get_data(as_text=True)[:240])

    r = client.post("/api/connectors/ga4/property", data=json.dumps(payload), content_type="application/json", headers=hdr(1, invalid_client_id))
    assert r.status_code == 404, (r.status_code, r.get_data(as_text=True)[:240])

    r = client.post("/api/connectors/ga4/property", data=json.dumps(payload), content_type="application/json", headers=hdr(1, None))
    assert r.status_code == 400, (r.status_code, r.get_data(as_text=True)[:240])

    # Cross-client owned isolation on client-scoped connector links
    r = client.post(
        "/api/client_connectors",
        data=json.dumps({
            "client_id": client_a,
            "connector_slug": "ga4",
            "account_id": "prop-A",
            "account_name": "Property A",
            "status": "connected",
            "config": {"property_id": "properties/111"},
        }),
        content_type="application/json",
        headers=hdr(1, client_a),
    )
    assert r.status_code == 200, (r.status_code, r.get_data(as_text=True)[:240])

    r = client.post(
        "/api/client_connectors",
        data=json.dumps({
            "client_id": client_b,
            "connector_slug": "ga4",
            "account_id": "prop-B",
            "account_name": "Property B",
            "status": "connected",
            "config": {"property_id": "properties/222"},
        }),
        content_type="application/json",
        headers=hdr(1, client_b),
    )
    assert r.status_code == 200, (r.status_code, r.get_data(as_text=True)[:240])

    ra = client.get(f"/api/client_connectors?client_id={client_a}", headers=hdr(1, client_a))
    rb = client.get(f"/api/client_connectors?client_id={client_b}", headers=hdr(1, client_b))
    assert ra.status_code == 200 and rb.status_code == 200
    rows_a = ra.get_json() or []
    rows_b = rb.get_json() or []
    assert any(str(x.get("account_id")) == "prop-A" for x in rows_a), rows_a
    assert not any(str(x.get("account_id")) == "prop-B" for x in rows_a), rows_a
    assert any(str(x.get("account_id")) == "prop-B" for x in rows_b), rows_b
    assert not any(str(x.get("account_id")) == "prop-A" for x in rows_b), rows_b

    # Orchestrator history list should not leak executions between valid owned clients
    r = client.get("/api/orchestrator/history", headers=hdr(1, client_b))
    assert r.status_code == 200
    history_b = r.get_json() or []
    if exec_id > 0:
        assert all(int(x.get("id") or 0) != exec_id for x in history_b), history_b[:3]

    # Spoof guard: in production mode, X-User-ID fallback must not grant scoped access
    old_auth_required = m.AUTH_REQUIRED
    old_app_env = os.environ.get("APP_ENV")
    old_flask_env = os.environ.get("FLASK_ENV")
    try:
        m.AUTH_REQUIRED = True
        os.environ["APP_ENV"] = "production"
        os.environ["FLASK_ENV"] = "production"
        r = client.get("/api/connectors/list", headers=hdr(1, client_a))
        assert r.status_code == 401, (r.status_code, r.get_data(as_text=True)[:240])
    finally:
        m.AUTH_REQUIRED = old_auth_required
        if old_app_env is None:
            os.environ.pop("APP_ENV", None)
        else:
            os.environ["APP_ENV"] = old_app_env
        if old_flask_env is None:
            os.environ.pop("FLASK_ENV", None)
        else:
            os.environ["FLASK_ENV"] = old_flask_env

    print("M3 scoping tests: OK")


if __name__ == "__main__":
    run()
