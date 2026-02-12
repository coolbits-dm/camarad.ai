"""
Phase 24 – PayPal connector test-suite
Target: 16 tests (accounts, overview, transactions, payouts, disputes, reports, test-call, status)
"""
import unittest, json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from app import app

class PayPalTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    # ── Accounts ───────────────────────────────────────────────────────────
    def test_accounts(self):
        r = self.client.get("/api/connectors/paypal/accounts")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 3)
        self.assertIn("balance", data[0])
        self.assertIn("currency", data[0])

    # ── Overview ───────────────────────────────────────────────────────────
    def test_overview_all(self):
        r = self.client.get("/api/connectors/paypal/overview")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("kpis", data)
        self.assertGreaterEqual(len(data["kpis"]), 8)
        self.assertIn("monthly_trend", data)

    def test_overview_by_account(self):
        r = self.client.get("/api/connectors/paypal/overview?account=business@techstart.com")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("kpis", data)
        self.assertEqual(data["kpis"][0]["label"], "Balance")

    def test_overview_unknown_account(self):
        r = self.client.get("/api/connectors/paypal/overview?account=nobody@nowhere.com")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("kpis", data)

    # ── Transactions ───────────────────────────────────────────────────────
    def test_transactions_all(self):
        r = self.client.get("/api/connectors/paypal/transactions")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 12)

    def test_transactions_filter_status(self):
        r = self.client.get("/api/connectors/paypal/transactions?status=pending")
        data = r.get_json()
        self.assertTrue(all(t["status"] == "pending" for t in data))
        self.assertGreaterEqual(len(data), 1)

    def test_transactions_filter_type(self):
        r = self.client.get("/api/connectors/paypal/transactions?type=refund")
        data = r.get_json()
        self.assertTrue(all(t["type"] == "refund" for t in data))
        self.assertGreaterEqual(len(data), 2)

    # ── Payouts ────────────────────────────────────────────────────────────
    def test_payouts_all(self):
        r = self.client.get("/api/connectors/paypal/payouts")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertGreaterEqual(len(data), 7)

    def test_payouts_filter_status(self):
        r = self.client.get("/api/connectors/paypal/payouts?status=pending")
        data = r.get_json()
        self.assertTrue(all(p["status"] == "pending" for p in data))
        self.assertGreaterEqual(len(data), 1)

    # ── Disputes ───────────────────────────────────────────────────────────
    def test_disputes_all(self):
        r = self.client.get("/api/connectors/paypal/disputes")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertGreaterEqual(len(data), 6)

    def test_disputes_filter_status(self):
        r = self.client.get("/api/connectors/paypal/disputes?status=open")
        data = r.get_json()
        self.assertTrue(all(d["status"] == "open" for d in data))

    def test_disputes_filter_reason(self):
        r = self.client.get("/api/connectors/paypal/disputes?reason=ITEM_NOT_RECEIVED")
        data = r.get_json()
        self.assertTrue(all(d["reason"] == "ITEM_NOT_RECEIVED" for d in data))

    # ── Reports ────────────────────────────────────────────────────────────
    def test_reports_unified(self):
        r = self.client.get("/api/connectors/paypal/reports")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        # 12 transactions + 7 payouts + 6 disputes = 25 rows
        self.assertGreaterEqual(len(data), 25)
        types = {row["type"] for row in data}
        self.assertIn("Transaction", types)
        self.assertIn("Payout", types)
        self.assertIn("Dispute", types)

    # ── Test API Call ──────────────────────────────────────────────────────
    def test_api_call_payments(self):
        r = self.client.post("/api/connectors/paypal/test-call",
                             json={"endpoint": "payments", "method": "GET"})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(data["endpoint"], "payments")
        self.assertIn("transactions", data["response"]["body"])

    def test_api_call_disputes(self):
        r = self.client.post("/api/connectors/paypal/test-call",
                             json={"endpoint": "disputes", "method": "GET"})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("items", data["response"]["body"])

    # ── Status save / read ─────────────────────────────────────────────────
    def test_status_save_read(self):
        self.client.post("/api/connectors/paypal",
                         json={"status": "Connected", "config": {"currency": "USD"}})
        r = self.client.get("/api/connectors/paypal")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(data["status"], "Connected")


if __name__ == "__main__":
    unittest.main(verbosity=2)
