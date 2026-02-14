"""Billing Phase 3 flag/idempotency/caps smoke tests."""
import json
import os
import time
import uuid

import app as m


m.AUTH_REQUIRED = False
client = m.app.test_client()
RUN_ID = int(time.time())


def hdr(uid=1, cid=None):
    h = {"X-User-ID": str(uid)}
    if cid is not None:
        h["X-Client-ID"] = str(cid)
    return h


def _seed_shadow_row(request_id, shadow_ct=7, workspace_id="agency", user_id=1):
    conn = m.get_db()
    m._ensure_usage_ledger_table(conn)
    conn.execute(
        """
        INSERT OR REPLACE INTO usage_ledger (
          user_id, client_id, event_type, amount, description, created_at,
          request_id, workspace_id, provider, model, status,
          ct_shadow_debit, ct_debit_shadow, minimum_ct_debit, billable_usd
        ) VALUES (?, NULL, 'chat_message', 0, ?, datetime('now'), ?, ?, 'vertex', 'gemini-1.5-flash-002', 'ok', ?, ?, 1, 0.01)
        """,
        (int(user_id), f"phase3 seed {request_id}", str(request_id), str(workspace_id), int(shadow_ct), int(shadow_ct)),
    )
    conn.commit()
    conn.close()


def _snapshot(uid=1):
    r = client.get("/api/user/snapshot", headers=hdr(uid))
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json() or {}


def run():
    prev = {
        "BILLING_PHASE3_ENABLED": os.environ.get("BILLING_PHASE3_ENABLED"),
        "MAX_CT_PER_REQUEST": os.environ.get("MAX_CT_PER_REQUEST"),
        "MAX_DAILY_CT_PER_WORKSPACE": os.environ.get("MAX_DAILY_CT_PER_WORKSPACE"),
    }

    try:
        # Ensure large enough budget for tests.
        r = client.patch(
            "/api/settings/user",
            data=json.dumps({"economy": {"daily_limit": 999999, "cost_multiplier": 1.0}}),
            content_type="application/json",
            headers=hdr(1),
        )
        assert r.status_code == 200, r.get_data(as_text=True)

        # Seed balance directly for deterministic debit checks.
        conn = m.get_db()
        m._ensure_usage_ledger_table(conn)
        conn.execute(
            "INSERT INTO usage_ledger (user_id, client_id, event_type, amount, description, created_at) VALUES (?, NULL, 'topup', ?, ?, datetime('now'))",
            (1, 50000, f"phase3 topup seed {RUN_ID}"),
        )
        conn.commit()
        conn.close()

        # 1) Flag OFF keeps legacy path (no phase3_applied).
        os.environ["BILLING_PHASE3_ENABLED"] = "0"
        req_off = f"phase3-off-{uuid.uuid4()}"
        r = client.post(
            "/api/user/spend",
            data=json.dumps({"amount": 5, "event_type": "chat_message", "request_id": req_off}),
            content_type="application/json",
            headers=hdr(1),
        )
        assert r.status_code == 200, r.get_data(as_text=True)
        body = r.get_json() or {}
        assert body.get("success") is True, body
        assert body.get("phase3_applied") is False, body

        # 2) Flag ON uses ct_shadow_debit and is idempotent by request_id.
        os.environ["BILLING_PHASE3_ENABLED"] = "1"
        os.environ["MAX_CT_PER_REQUEST"] = "200"
        os.environ["MAX_DAILY_CT_PER_WORKSPACE"] = "5000"

        req_on = f"phase3-on-{uuid.uuid4()}"
        _seed_shadow_row(req_on, shadow_ct=7, workspace_id="agency", user_id=1)

        snap_before = _snapshot(1)
        bal_before = int(snap_before.get("ct_balance") or 0)

        r1 = client.post(
            "/api/user/spend",
            data=json.dumps({"amount": 2, "event_type": "chat_message", "request_id": req_on}),
            content_type="application/json",
            headers=hdr(1),
        )
        assert r1.status_code == 200, r1.get_data(as_text=True)
        b1 = r1.get_json() or {}
        assert b1.get("success") is True, b1
        assert b1.get("phase3_applied") is True, b1
        assert int(b1.get("spent") or 0) == 7, b1
        assert b1.get("idempotent") is False, b1

        snap_after_first = _snapshot(1)
        bal_after_first = int(snap_after_first.get("ct_balance") or 0)
        assert bal_after_first == bal_before - 7, (bal_before, bal_after_first)

        # same request_id again => no second debit
        r2 = client.post(
            "/api/user/spend",
            data=json.dumps({"amount": 2, "event_type": "chat_message", "request_id": req_on}),
            content_type="application/json",
            headers=hdr(1),
        )
        assert r2.status_code == 200, r2.get_data(as_text=True)
        b2 = r2.get_json() or {}
        assert b2.get("success") is True, b2
        assert b2.get("phase3_applied") is True, b2
        assert b2.get("idempotent") is True, b2

        snap_after_second = _snapshot(1)
        bal_after_second = int(snap_after_second.get("ct_balance") or 0)
        assert bal_after_second == bal_after_first, (bal_after_first, bal_after_second)

        # 3) Per-request cap reject (no debit).
        os.environ["MAX_CT_PER_REQUEST"] = "3"
        req_cap = f"phase3-cap-{uuid.uuid4()}"
        _seed_shadow_row(req_cap, shadow_ct=9, workspace_id="agency", user_id=1)

        snap_cap_before = _snapshot(1)
        bal_cap_before = int(snap_cap_before.get("ct_balance") or 0)

        rc = client.post(
            "/api/user/spend",
            data=json.dumps({"amount": 2, "event_type": "chat_message", "request_id": req_cap}),
            content_type="application/json",
            headers=hdr(1),
        )
        assert rc.status_code == 429, rc.get_data(as_text=True)
        bc = rc.get_json() or {}
        assert bc.get("success") is False, bc
        assert str(bc.get("code") or "") == "max_ct_per_request", bc

        snap_cap_after = _snapshot(1)
        bal_cap_after = int(snap_cap_after.get("ct_balance") or 0)
        assert bal_cap_after == bal_cap_before, (bal_cap_before, bal_cap_after)

        print("Billing Phase3 tests: OK")

    finally:
        for k, v in prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


if __name__ == "__main__":
    run()
