"""
Stripe Connector – Test Suite
13 tests covering all 8 endpoints + status persistence
"""
import pytest
import requests

BASE = "http://127.0.0.1:5051"


# ── Accounts ───────────────────────────────────────────────────────────
def test_stripe_accounts():
    r = requests.get(f"{BASE}/api/connectors/stripe/accounts")
    assert r.status_code == 200
    data = r.json()
    assert "accounts" in data
    assert len(data["accounts"]) == 2
    names = [a["name"] for a in data["accounts"]]
    assert "TechStart Live" in names
    assert "TechStart Test" in names
    assert all(a["business_type"] == "company" for a in data["accounts"])


# ── Overview ───────────────────────────────────────────────────────────
def test_stripe_overview():
    r = requests.get(f"{BASE}/api/connectors/stripe/overview?account_id=acct_1J7xQR2eZvKYlo2C")
    assert r.status_code == 200
    ov = r.json()["overview"]
    assert ov["mrr"] == 4812
    assert ov["arr"] == 57744
    assert ov["active_subscriptions"] == 231
    assert ov["churn_rate"] == 4.2
    assert ov["ltv_cac_ratio"] == 3.46
    assert ov["runway_months"] == 18
    assert len(ov["mrr_trend"]) == 6
    assert len(ov["revenue_by_product"]) == 4


def test_stripe_overview_unknown_account():
    r = requests.get(f"{BASE}/api/connectors/stripe/overview?account_id=acct_000")
    assert r.status_code == 200
    ov = r.json()["overview"]
    assert ov["mrr"] == 0
    assert ov["active_subscriptions"] == 0


# ── Subscriptions ──────────────────────────────────────────────────────
def test_stripe_subscriptions():
    r = requests.get(f"{BASE}/api/connectors/stripe/subscriptions")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 12
    subs = data["subscriptions"]
    assert any(s["plan"] == "Enterprise" for s in subs)
    assert any(s["status"] == "trialing" for s in subs)
    assert any(s["status"] == "canceled" for s in subs)
    assert any(s["status"] == "past_due" for s in subs)


def test_stripe_subscriptions_filter():
    r = requests.get(f"{BASE}/api/connectors/stripe/subscriptions?status=active")
    assert r.status_code == 200
    data = r.json()
    assert all(s["status"] == "active" for s in data["subscriptions"])
    assert data["total"] > 0
    assert data["total"] < 12  # Not all subs are active


# ── Payments ───────────────────────────────────────────────────────────
def test_stripe_payments():
    r = requests.get(f"{BASE}/api/connectors/stripe/payments")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 10
    payments = data["payments"]
    assert any(p["status"] == "succeeded" for p in payments)
    assert any(p["status"] == "refunded" for p in payments)
    assert any(p["status"] == "failed" for p in payments)
    assert all("card_last4" in p for p in payments)


# ── Customers ──────────────────────────────────────────────────────────
def test_stripe_customers():
    r = requests.get(f"{BASE}/api/connectors/stripe/customers")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 12
    customers = data["customers"]
    assert any(c["name"] == "John Mitchell" for c in customers)
    assert any(c["status"] == "canceled" for c in customers)
    assert all("ltv" in c for c in customers)
    assert all("email" in c for c in customers)


# ── Budget Pacing ──────────────────────────────────────────────────────
def test_stripe_budget_pacing():
    r = requests.get(f"{BASE}/api/connectors/stripe/budget-pacing?account_id=acct_1J7xQR2eZvKYlo2C")
    assert r.status_code == 200
    p = r.json()["pacing"]
    assert p["monthly_revenue_goal"] == 18000
    assert p["current_revenue"] == 14236
    assert p["pacing_status"] == "AHEAD"
    assert p["cash_runway_months"] == 18
    assert len(p["products"]) == 4
    pacings = [pr["pacing"] for pr in p["products"]]
    assert "AHEAD" in pacings
    assert "UNDERPACING" in pacings


# ── Reports ────────────────────────────────────────────────────────────
def test_stripe_reports():
    r = requests.get(f"{BASE}/api/connectors/stripe/reports?account_id=acct_1J7xQR2eZvKYlo2C")
    assert r.status_code == 200
    data = r.json()
    assert data["total_rows"] == 124  # 31 days × 4 plans
    row = data["rows"][0]
    assert "date" in row
    assert "plan" in row
    assert "revenue" in row
    assert "new_subscriptions" in row
    assert "net_revenue" in row


# ── Test API Call ──────────────────────────────────────────────────────
def test_stripe_test_call_customers():
    r = requests.post(f"{BASE}/api/connectors/stripe/test-call",
                      json={"endpoint": "customers", "method": "GET"})
    assert r.status_code == 200
    data = r.json()
    assert data["endpoint"] == "customers"
    body = data["response"]["body"]
    assert body["object"] == "list"
    assert len(body["data"]) == 3
    assert all("email" in c for c in body["data"])
    assert "quota" in data


def test_stripe_test_call_subscriptions():
    r = requests.post(f"{BASE}/api/connectors/stripe/test-call",
                      json={"endpoint": "subscriptions", "method": "GET"})
    assert r.status_code == 200
    body = r.json()["response"]["body"]
    assert body["object"] == "list"
    assert len(body["data"]) == 3
    assert all("items" in s for s in body["data"])


# ── Status persistence ────────────────────────────────────────────────
def test_stripe_status_save_read():
    # Save
    r = requests.post(f"{BASE}/api/connectors/stripe",
                      json={"status": "Connected", "config": {"account": "acct_1J7xQR2eZvKYlo2C"}})
    assert r.status_code == 200
    # Read back
    r2 = requests.get(f"{BASE}/api/connectors/stripe")
    assert r2.status_code == 200
    assert r2.json()["status"] == "Connected"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
