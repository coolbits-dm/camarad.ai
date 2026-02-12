"""Billing plan recommendations (read-only) smoke test."""
import time
import uuid

import app as m


def run():
    token = f"tok-{int(time.time())}"
    m.BILLING_INTERNAL_TOKEN = token
    c = m.app.test_client()

    # 1) Forbidden without internal token.
    r = c.get("/api/billing/plan-recommendations?window_days=7")
    assert r.status_code == 403, r.get_data(as_text=True)

    # 2) Seed enough shadow rows to pass guardrails.
    conn = m.get_db()
    m._ensure_usage_ledger_table(conn)
    rows = []
    workspaces = ["personal", "agency", "business"]
    for i in range(600):
        ws = workspaces[i % len(workspaces)]
        inp = 300 + (i % 40) * 10
        out = 120 + (i % 30) * 7
        cost = 0.001 + ((i % 20) * 0.0001)
        bill = cost * 1.65
        ct_actual = 10 + (i % 15)
        rows.append((
            1, None, "chat_message", -1, "plan-reco test",
            m.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            f"plan-reco-{uuid.uuid4()}",
            ws,
            "vertex",
            "gemini-1.5-flash-002",
            inp,
            out,
            0,
            0,
            350 + (i % 100),
            "ok",
            cost,
            bill,
            ct_actual,
        ))
    conn.executemany(
        """
        INSERT INTO usage_ledger (
            user_id, client_id, event_type, amount, description, created_at,
            request_id, workspace_id, provider, model,
            input_tokens, output_tokens, tool_calls, connector_calls, latency_ms,
            status, cost_final_usd, billable_usd, ct_actual_debit
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()

    # 3) Endpoint returns recommendations when guardrails are met.
    r2 = c.get(
        "/api/billing/plan-recommendations?window_days=7",
        headers={"X-Internal-Token": token},
    )
    assert r2.status_code == 200, r2.get_data(as_text=True)
    data = r2.get_json() or {}
    assert data.get("insufficient_data") is False, data
    assert isinstance(data.get("recommendations"), dict), data
    assert all(k in data["recommendations"] for k in ("free", "standard", "pro")), data
    assert int((data.get("coverage") or {}).get("rows_with_tokens") or 0) >= 500, data
    assert int((data.get("coverage") or {}).get("distinct_workspaces") or 0) >= 3, data
    print("Plan recommendations tests: OK")


if __name__ == "__main__":
    run()
