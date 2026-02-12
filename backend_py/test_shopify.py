"""
test_shopify.py – Phase 19 Shopify Connector Tests
Covers: stores, overview, products, orders, abandoned carts,
        customers, reports, test-call, status save/read
"""
import requests, sys

BASE = "http://127.0.0.1:5051"
PASS = 0
FAIL = 0


def ok(label):
    global PASS
    PASS += 1
    print(f"  ✅ {label}")


def fail(label, reason=""):
    global FAIL
    FAIL += 1
    print(f"  ❌ {label} — {reason}")


def t(label, fn):
    try:
        fn()
        ok(label)
    except AssertionError as e:
        fail(label, str(e))
    except Exception as e:
        fail(label, repr(e))


# ── Tests ──────────────────────────────────────────────────────────────────

def test_stores():
    r = requests.get(f"{BASE}/api/connectors/shopify/stores")
    d = r.json()
    assert r.status_code == 200
    assert len(d["stores"]) == 3
    ids = [s["store_id"] for s in d["stores"]]
    assert "techstart-store.myshopify.com" in ids

t("1. GET /shopify/stores → 3 stores", test_stores)


def test_overview():
    r = requests.get(f"{BASE}/api/connectors/shopify/overview?store_id=techstart-store.myshopify.com")
    d = r.json()
    assert r.status_code == 200
    ov = d["overview"]
    assert ov["revenue_this_month"] == 28472
    assert ov["orders_this_month"] == 312
    assert ov["aov"] == 91.26
    assert len(ov["top_products"]) == 5
    assert len(ov["daily_revenue"]) == 7
    assert len(ov["sales_by_channel"]) == 4

t("2. GET /shopify/overview → KPIs + daily + channel", test_overview)


def test_overview_unknown():
    r = requests.get(f"{BASE}/api/connectors/shopify/overview?store_id=nonexistent")
    d = r.json()
    assert r.status_code == 200
    ov = d["overview"]
    assert ov["revenue_this_month"] == 0
    assert ov["orders_this_month"] == 0

t("3. GET /shopify/overview unknown → zeros", test_overview_unknown)


def test_products():
    r = requests.get(f"{BASE}/api/connectors/shopify/products")
    d = r.json()
    assert r.status_code == 200
    assert d["total"] == 12
    assert len(d["products"]) == 12

t("4. GET /shopify/products → 12 products", test_products)


def test_products_filter():
    r = requests.get(f"{BASE}/api/connectors/shopify/products?status=draft")
    d = r.json()
    assert r.status_code == 200
    assert all(p["status"] == "draft" for p in d["products"])
    assert d["total"] >= 1

t("5. GET /shopify/products?status=draft → filter", test_products_filter)


def test_orders():
    r = requests.get(f"{BASE}/api/connectors/shopify/orders")
    d = r.json()
    assert r.status_code == 200
    assert d["total"] == 10
    assert len(d["orders"]) == 10
    assert d["orders"][0]["order_id"] == "#1001"

t("6. GET /shopify/orders → 10 orders", test_orders)


def test_orders_filter():
    r = requests.get(f"{BASE}/api/connectors/shopify/orders?status=cancelled")
    d = r.json()
    assert r.status_code == 200
    assert all(o["status"] == "cancelled" for o in d["orders"])

t("7. GET /shopify/orders?status=cancelled → filter", test_orders_filter)


def test_abandoned_carts():
    r = requests.get(f"{BASE}/api/connectors/shopify/abandoned-carts")
    d = r.json()
    assert r.status_code == 200
    assert d["total"] == 8
    assert len(d["carts"]) == 8
    assert "recovery_rate" in d
    assert d["recovered"] >= 1

t("8. GET /shopify/abandoned-carts → 8 carts + recovery", test_abandoned_carts)


def test_customers():
    r = requests.get(f"{BASE}/api/connectors/shopify/customers")
    d = r.json()
    assert r.status_code == 200
    assert d["total"] == 10
    assert len(d["customers"]) == 10
    assert "tags" in d["customers"][0]

t("9. GET /shopify/customers → 10 customers + tags", test_customers)


def test_reports():
    r = requests.get(f"{BASE}/api/connectors/shopify/reports?store_id=techstart-store")
    d = r.json()
    assert r.status_code == 200
    assert len(d["rows"]) == 31
    row = d["rows"][0]
    for k in ["date", "revenue", "orders", "aov", "new_customers", "returning_customers", "abandoned_carts", "sessions"]:
        assert k in row, f"missing key {k}"

t("10. GET /shopify/reports → 31 rows", test_reports)


def test_call_products():
    r = requests.post(f"{BASE}/api/connectors/shopify/test-call",
                      json={"endpoint": "products", "method": "GET"})
    d = r.json()
    assert r.status_code == 200
    assert "response" in d
    assert "products" in d["response"]["body"]

t("11. POST /shopify/test-call products → mock data", test_call_products)


def test_call_orders():
    r = requests.post(f"{BASE}/api/connectors/shopify/test-call",
                      json={"endpoint": "orders", "method": "GET"})
    d = r.json()
    assert r.status_code == 200
    assert "orders" in d["response"]["body"]

t("12. POST /shopify/test-call orders → mock data", test_call_orders)


def test_status_save_read():
    # Save
    r = requests.post(f"{BASE}/api/connectors/shopify",
                      json={"status": "Connected", "config": {"store": "techstart-store"}})
    assert r.status_code == 200
    # Read
    r2 = requests.get(f"{BASE}/api/connectors/shopify")
    d2 = r2.json()
    assert d2["status"] == "Connected"

t("13. Status save + read → Connected", test_status_save_read)


# ── Summary ────────────────────────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"Shopify Tests: {PASS} passed, {FAIL} failed out of {PASS+FAIL}")
print(f"{'='*50}")
if FAIL:
    sys.exit(1)
