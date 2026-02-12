"""Client context integration smoke tests (script-style)."""
import json
import time
from app import app

client = app.test_client()
RUN_ID = int(time.time())
PREFIX = f"client-{RUN_ID}"


def hdr(uid=1, cid=None):
    headers = {"X-User-ID": str(uid)}
    if cid is not None:
        headers["X-Client-ID"] = str(cid)
    return headers


created_flows = []
created_chats = []
created_clients = []


def cleanup():
    for flow_id, cid in created_flows:
        try:
            client.delete(f"/api/flows/{flow_id}", headers=hdr(1, cid))
        except Exception:
            try:
                client.delete(f"/api/flows/{flow_id}", headers=hdr(1))
            except Exception:
                pass

    for conv_id, cid in created_chats:
        try:
            client.delete(f"/api/conversations/{conv_id}", headers=hdr(1, cid))
        except Exception:
            try:
                client.delete(f"/api/conversations/{conv_id}", headers=hdr(1))
            except Exception:
                pass

    for client_id in reversed(created_clients):
        try:
            client.delete(f"/api/clients/{client_id}", headers=hdr(1))
        except Exception:
            pass


print("=" * 64)
print("CLIENT CONTEXT TESTS")
print("=" * 64)

try:
    # 1) GET /api/clients
    print("[1] GET /api/clients")
    r = client.get("/api/clients", headers=hdr(1))
    assert r.status_code == 200, r.get_data(as_text=True)
    base_clients = r.get_json()
    assert isinstance(base_clients, list)
    print(f"    OK: existing clients for user1 = {len(base_clients)}")

    # 2) POST person client
    print("[2] POST /api/clients (person)")
    person_payload = {
        "type": "person",
        "name": f"{PREFIX}-person",
        "email": f"{PREFIX}-person@example.com",
        "website": "https://person.example.com",
        "notes": "script test person client"
    }
    r = client.post("/api/clients", data=json.dumps(person_payload), content_type="application/json", headers=hdr(1))
    assert r.status_code == 200, r.get_data(as_text=True)
    person_resp = r.get_json()
    assert person_resp.get("success") is True
    person_client_id = int(person_resp["client"]["id"])
    created_clients.append(person_client_id)
    print(f"    OK: created person client id={person_client_id}")

    # 3) POST company client
    print("[3] POST /api/clients (company)")
    company_payload = {
        "type": "company",
        "company_name": f"{PREFIX}-company",
        "email": f"{PREFIX}-company@example.com",
        "website": "https://company.example.com",
        "notes": "script test company client"
    }
    r = client.post("/api/clients", data=json.dumps(company_payload), content_type="application/json", headers=hdr(1))
    assert r.status_code == 200, r.get_data(as_text=True)
    company_resp = r.get_json()
    assert company_resp.get("success") is True
    company_client_id = int(company_resp["client"]["id"])
    created_clients.append(company_client_id)
    print(f"    OK: created company client id={company_client_id}")

    # 4) Ensure list contains both new clients
    print("[4] GET /api/clients includes new ids")
    r = client.get("/api/clients", headers=hdr(1))
    assert r.status_code == 200
    clients = r.get_json()
    ids = {int(c["id"]) for c in clients}
    assert person_client_id in ids
    assert company_client_id in ids
    print("    OK: both clients are listed")

    # 4b) GET single client by id
    print("[4b] GET /api/clients/<id>")
    r = client.get(f"/api/clients/{person_client_id}", headers=hdr(1))
    assert r.status_code == 200, r.get_data(as_text=True)
    client_one = r.get_json()
    assert int(client_one.get("id")) == person_client_id
    assert str(client_one.get("type")) == "person"
    print("    OK: single client endpoint returns owned client")

    # 4c) PATCH client details
    print("[4c] PATCH /api/clients/<id> updates owned client")
    patch_client_payload = {
        "email": f"{PREFIX}-person+updated@example.com",
        "website": "https://person-updated.example.com",
        "phone": "+1 555 000 111",
        "notes": "updated from test_client.py"
    }
    r = client.patch(
        f"/api/clients/{person_client_id}",
        data=json.dumps(patch_client_payload),
        content_type="application/json",
        headers=hdr(1),
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    patched_client = r.get_json()
    assert patched_client.get("success") is True
    assert patched_client["client"]["email"] == patch_client_payload["email"]
    assert patched_client["client"]["website"] == patch_client_payload["website"]
    assert patched_client["client"]["phone"] == patch_client_payload["phone"]
    assert patched_client["client"]["notes"] == patch_client_payload["notes"]
    print("    OK: patch persisted and returned updated client")

    # 4d) PATCH ownership check
    print("[4d] PATCH /api/clients/<id> ownership enforced")
    r = client.patch(
        f"/api/clients/{person_client_id}",
        data=json.dumps({"notes": "forbidden"}),
        content_type="application/json",
        headers=hdr(2),
    )
    assert r.status_code == 404, r.get_data(as_text=True)
    print("    OK: foreign user cannot patch another user's client")

    # 5) Add account link to person client
    print("[5] POST /api/client_connectors")
    link_payload = {
        "client_id": person_client_id,
        "connector_slug": "google-ads",
        "account_id": f"{PREFIX}-acc-001",
        "account_name": f"{PREFIX} Ads Main",
        "status": "pending",
        "config": {"region": "US", "currency": "USD"}
    }
    r = client.post("/api/client_connectors", data=json.dumps(link_payload), content_type="application/json", headers=hdr(1))
    assert r.status_code == 200, r.get_data(as_text=True)
    link_resp = r.get_json()
    assert link_resp.get("success") is True
    link_id = int(link_resp["client_connector"]["id"])
    print(f"    OK: created client connector link id={link_id}")

    # 6) GET linked accounts by query client_id
    print("[6] GET /api/client_connectors?client_id=...")
    r = client.get(f"/api/client_connectors?client_id={person_client_id}", headers=hdr(1))
    assert r.status_code == 200
    accounts = r.get_json()
    assert any(int(a["id"]) == link_id for a in accounts), "Linked account not found"
    print(f"    OK: accounts returned={len(accounts)}")

    # 7) PATCH status/config
    print("[7] PATCH /api/client_connectors/<id>")
    patch_payload = {"status": "connected", "config": {"region": "US", "synced": True}}
    r = client.patch(f"/api/client_connectors/{link_id}", data=json.dumps(patch_payload), content_type="application/json", headers=hdr(1))
    assert r.status_code == 200, r.get_data(as_text=True)
    patched = r.get_json()["client_connector"]
    assert patched["status"] == "connected"
    assert isinstance(patched.get("config"), dict)
    assert patched["config"].get("synced") is True
    print("    OK: link patched to connected")

    # 8) GET linked accounts by active client header
    print("[8] GET /api/client_connectors with X-Client-ID")
    r = client.get("/api/client_connectors", headers=hdr(1, person_client_id))
    assert r.status_code == 200
    accounts_hdr = r.get_json()
    assert any(int(a["id"]) == link_id for a in accounts_hdr)
    print("    OK: header-based client scoping works")

    # 8b) Strict agents filtering with active client
    print("[8b] GET /api/agents/list strict client scope")
    r = client.post(
        "/api/agents/ceo-strategy",
        data=json.dumps({"custom_name": f"{PREFIX}-ceo-a", "status": "Active", "rag_enabled": True}),
        content_type="application/json",
        headers=hdr(1, person_client_id),
    )
    assert r.status_code == 200, r.get_data(as_text=True)

    r = client.post(
        "/api/agents/social-media-manager",
        data=json.dumps({"custom_name": f"{PREFIX}-social-b", "status": "Active", "rag_enabled": True}),
        content_type="application/json",
        headers=hdr(1, company_client_id),
    )
    assert r.status_code == 200, r.get_data(as_text=True)

    r = client.get("/api/agents/list", headers=hdr(1, person_client_id))
    assert r.status_code == 200
    person_agent_slugs = {a.get("slug") for a in r.get_json()}
    assert "ceo-strategy" in person_agent_slugs
    assert "social-media-manager" not in person_agent_slugs

    r = client.get("/api/agents/list", headers=hdr(1, company_client_id))
    assert r.status_code == 200
    company_agent_slugs = {a.get("slug") for a in r.get_json()}
    assert "social-media-manager" in company_agent_slugs
    assert "ceo-strategy" not in company_agent_slugs
    print("    OK: /api/agents/list is strictly filtered per client")

    # 8c) Strict connectors filtering with active client
    print("[8c] GET /api/connectors/list strict client scope")
    r = client.get("/api/connectors/list", headers=hdr(1, person_client_id))
    assert r.status_code == 200
    person_connectors = {c.get("slug") for c in r.get_json()}
    assert "google-ads" in person_connectors

    r = client.get("/api/connectors/list", headers=hdr(1, company_client_id))
    assert r.status_code == 200
    company_connectors = {c.get("slug") for c in r.get_json()}
    assert "google-ads" not in company_connectors

    # all=1 bypass is used by Add Account modal and must still return full catalog
    r = client.get("/api/connectors/list?all=1", headers=hdr(1, company_client_id))
    assert r.status_code == 200
    assert isinstance(r.get_json(), list)
    assert len(r.get_json()) >= 1
    print("    OK: /api/connectors/list strict scope + all=1 bypass work")

    # 9) Save flow for person client
    print("[9] POST /api/flows for person client")
    flow_a_name = f"{PREFIX}-flow-a"
    flow_a = {
        "name": flow_a_name,
        "flow": {
            "nodes": [{"id": "n1", "type": "trigger", "label": "Start A"}],
            "connections": []
        },
        "thumbnail": None,
        "category": "QA",
        "description": "Client A scoped flow"
    }
    r = client.post("/api/flows", data=json.dumps(flow_a), content_type="application/json", headers=hdr(1, person_client_id))
    assert r.status_code == 200, r.get_data(as_text=True)
    flow_a_id = int(r.get_json()["flow_id"])
    created_flows.append((flow_a_id, person_client_id))
    print(f"    OK: flow a id={flow_a_id}")

    # 10) Save flow for company client
    print("[10] POST /api/flows for company client")
    flow_b_name = f"{PREFIX}-flow-b"
    flow_b = {
        "name": flow_b_name,
        "flow": {
            "nodes": [{"id": "n1", "type": "trigger", "label": "Start B"}],
            "connections": []
        },
        "thumbnail": None,
        "category": "QA",
        "description": "Client B scoped flow"
    }
    r = client.post("/api/flows", data=json.dumps(flow_b), content_type="application/json", headers=hdr(1, company_client_id))
    assert r.status_code == 200, r.get_data(as_text=True)
    flow_b_id = int(r.get_json()["flow_id"])
    created_flows.append((flow_b_id, company_client_id))
    print(f"    OK: flow b id={flow_b_id}")

    # 11) List flows for person client only
    print("[11] GET /api/flows filtered for person client")
    r = client.get("/api/flows", headers=hdr(1, person_client_id))
    assert r.status_code == 200
    names = [f.get("name") for f in r.get_json()]
    assert flow_a_name in names
    assert flow_b_name not in names
    print("    OK: person flow visible, company flow hidden")

    # 12) List flows for company client only
    print("[12] GET /api/flows filtered for company client")
    r = client.get("/api/flows", headers=hdr(1, company_client_id))
    assert r.status_code == 200
    names = [f.get("name") for f in r.get_json()]
    assert flow_b_name in names
    assert flow_a_name not in names
    print("    OK: company flow visible, person flow hidden")

    # 13) Chats are client-scoped
    print("[13] POST/GET /api/chats client scoping")
    chat_a_title = f"{PREFIX}-chat-a"
    chat_b_title = f"{PREFIX}-chat-b"

    r = client.post(
        "/api/chats",
        data=json.dumps({"workspace": "business", "agent_slug": "ceo-strategy", "title": chat_a_title}),
        content_type="application/json",
        headers=hdr(1, person_client_id),
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    chat_a_id = int(r.get_json()["chat_id"])
    created_chats.append((chat_a_id, person_client_id))

    r = client.post(
        "/api/chats",
        data=json.dumps({"workspace": "business", "agent_slug": "ceo-strategy", "title": chat_b_title}),
        content_type="application/json",
        headers=hdr(1, company_client_id),
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    chat_b_id = int(r.get_json()["chat_id"])
    created_chats.append((chat_b_id, company_client_id))

    r = client.get("/api/chats", headers=hdr(1, person_client_id))
    assert r.status_code == 200
    titles_a = [c.get("title") for c in r.get_json()]
    assert chat_a_title in titles_a
    assert chat_b_title not in titles_a

    r = client.get("/api/chats", headers=hdr(1, company_client_id))
    assert r.status_code == 200
    titles_b = [c.get("title") for c in r.get_json()]
    assert chat_b_title in titles_b
    assert chat_a_title not in titles_b
    print("    OK: chats are isolated per client")

    # 14) User isolation for clients/client_connectors
    print("[14] User isolation checks")
    r = client.get("/api/clients", headers=hdr(2))
    assert r.status_code == 200
    user2_ids = {int(c["id"]) for c in r.get_json()}
    assert person_client_id not in user2_ids
    assert company_client_id not in user2_ids

    r = client.get(f"/api/client_connectors?client_id={person_client_id}", headers=hdr(2))
    assert r.status_code == 200
    assert r.get_json() == []

    r = client.get(f"/api/clients/{person_client_id}", headers=hdr(2))
    assert r.status_code == 404

    r = client.post(
        "/api/client_connectors",
        data=json.dumps({
            "client_id": person_client_id,
            "connector_slug": "ga4",
            "account_id": f"{PREFIX}-forbidden"
        }),
        content_type="application/json",
        headers=hdr(2),
    )
    assert r.status_code == 404
    print("    OK: user-level isolation enforced")

    # 15) DELETE client + linked accounts cleanup
    print("[15] DELETE /api/clients/<id> removes client and linked accounts")
    r = client.post(
        "/api/clients",
        data=json.dumps({
            "type": "company",
            "company_name": f"{PREFIX}-delete-me",
            "email": f"{PREFIX}-delete@example.com",
        }),
        content_type="application/json",
        headers=hdr(1),
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    delete_client_id = int(r.get_json()["client"]["id"])
    created_clients.append(delete_client_id)

    r = client.post(
        "/api/client_connectors",
        data=json.dumps({
            "client_id": delete_client_id,
            "connector_slug": "ga4",
            "account_id": f"{PREFIX}-delete-link-1",
            "account_name": f"{PREFIX} Delete Link",
            "status": "connected",
        }),
        content_type="application/json",
        headers=hdr(1),
    )
    assert r.status_code == 200, r.get_data(as_text=True)

    r = client.delete(f"/api/clients/{delete_client_id}", headers=hdr(1))
    assert r.status_code == 200, r.get_data(as_text=True)
    delete_payload = r.get_json()
    assert delete_payload.get("success") is True
    assert int(delete_payload.get("removed_links", 0)) >= 1

    created_clients[:] = [cid for cid in created_clients if cid != delete_client_id]

    r = client.get(f"/api/clients/{delete_client_id}", headers=hdr(1))
    assert r.status_code == 404

    r = client.patch(
        f"/api/clients/{delete_client_id}",
        data=json.dumps({"notes": "should fail"}),
        content_type="application/json",
        headers=hdr(1),
    )
    assert r.status_code == 404

    r = client.get(f"/api/client_connectors?client_id={delete_client_id}", headers=hdr(1))
    assert r.status_code == 200
    assert r.get_json() == []
    print("    OK: delete endpoint works and linked accounts are cleared")

    print("\nALL CLIENT CONTEXT TESTS PASSED (extended checks)")

finally:
    cleanup()

