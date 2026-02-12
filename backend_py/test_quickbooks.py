"""
test_quickbooks.py — QuickBooks connector tests (Phase 22)
Covers: companies, overview, invoices (with filters), expenses (with filters),
        banking (with filters), reports, test-call (invoices + expenses + pnl),
        status save/read.
"""

import unittest, requests

BASE = "http://127.0.0.1:5051"


class TestQuickBooks(unittest.TestCase):

    # ── Companies ─────────────────────────────────────────────────────────
    def test_companies(self):
        r = requests.get(f"{BASE}/api/connectors/quickbooks/companies")
        self.assertEqual(r.status_code, 200)
        companies = r.json()["companies"]
        self.assertGreaterEqual(len(companies), 3)
        names = [c["name"] for c in companies]
        self.assertIn("TechStart Agency", names)

    # ── Overview ──────────────────────────────────────────────────────────
    def test_overview(self):
        r = requests.get(f"{BASE}/api/connectors/quickbooks/overview",
                         params={"company_id": "123456789"})
        self.assertEqual(r.status_code, 200)
        ov = r.json()["overview"]
        self.assertGreater(ov["total_revenue"], 0)
        self.assertGreater(ov["net_profit"], 0)
        self.assertIn("monthly_pnl", ov)
        self.assertIn("expense_by_category", ov)

    def test_overview_unknown_company(self):
        r = requests.get(f"{BASE}/api/connectors/quickbooks/overview",
                         params={"company_id": "UNKNOWN"})
        self.assertEqual(r.status_code, 200)
        ov = r.json()["overview"]
        self.assertEqual(ov["total_revenue"], 0)

    # ── Invoices ──────────────────────────────────────────────────────────
    def test_invoices_all(self):
        r = requests.get(f"{BASE}/api/connectors/quickbooks/invoices")
        self.assertEqual(r.status_code, 200)
        invoices = r.json()["invoices"]
        self.assertGreaterEqual(len(invoices), 10)

    def test_invoices_filter_paid(self):
        r = requests.get(f"{BASE}/api/connectors/quickbooks/invoices",
                         params={"status": "Paid"})
        self.assertEqual(r.status_code, 200)
        invoices = r.json()["invoices"]
        self.assertGreater(len(invoices), 0)
        for inv in invoices:
            self.assertEqual(inv["status"], "Paid")

    def test_invoices_filter_overdue(self):
        r = requests.get(f"{BASE}/api/connectors/quickbooks/invoices",
                         params={"status": "Overdue"})
        self.assertEqual(r.status_code, 200)
        invoices = r.json()["invoices"]
        self.assertGreater(len(invoices), 0)
        for inv in invoices:
            self.assertEqual(inv["status"], "Overdue")

    # ── Expenses ──────────────────────────────────────────────────────────
    def test_expenses_all(self):
        r = requests.get(f"{BASE}/api/connectors/quickbooks/expenses")
        self.assertEqual(r.status_code, 200)
        expenses = r.json()["expenses"]
        self.assertGreaterEqual(len(expenses), 10)

    def test_expenses_filter_category(self):
        r = requests.get(f"{BASE}/api/connectors/quickbooks/expenses",
                         params={"category": "Cloud"})
        self.assertEqual(r.status_code, 200)
        expenses = r.json()["expenses"]
        self.assertGreater(len(expenses), 0)
        for e in expenses:
            self.assertIn("Cloud", e["category"])

    # ── Banking ───────────────────────────────────────────────────────────
    def test_banking_all(self):
        r = requests.get(f"{BASE}/api/connectors/quickbooks/banking")
        self.assertEqual(r.status_code, 200)
        txns = r.json()["transactions"]
        self.assertGreaterEqual(len(txns), 10)

    def test_banking_filter_credit(self):
        r = requests.get(f"{BASE}/api/connectors/quickbooks/banking",
                         params={"type": "Credit"})
        self.assertEqual(r.status_code, 200)
        txns = r.json()["transactions"]
        self.assertGreater(len(txns), 0)
        for t in txns:
            self.assertEqual(t["type"], "Credit")

    # ── Reports ───────────────────────────────────────────────────────────
    def test_reports(self):
        r = requests.get(f"{BASE}/api/connectors/quickbooks/reports")
        self.assertEqual(r.status_code, 200)
        rows = r.json()["rows"]
        self.assertEqual(len(rows), 31)
        self.assertIn("revenue", rows[0])
        self.assertIn("net_income", rows[0])

    # ── Test Call ─────────────────────────────────────────────────────────
    def test_call_invoices(self):
        r = requests.post(f"{BASE}/api/connectors/quickbooks/test-call",
                          json={"endpoint": "invoices", "method": "GET"})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["response"]["status_code"], 200)
        self.assertIn("QueryResponse", d["response"]["body"])
        self.assertEqual(d["response"]["body"]["QueryResponse"]["totalCount"], 12)
        self.assertIn("latency_ms", d)

    def test_call_expenses(self):
        r = requests.post(f"{BASE}/api/connectors/quickbooks/test-call",
                          json={"endpoint": "expenses", "method": "GET"})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn("QueryResponse", d["response"]["body"])

    def test_call_pnl(self):
        r = requests.post(f"{BASE}/api/connectors/quickbooks/test-call",
                          json={"endpoint": "pnl", "method": "GET"})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn("Header", d["response"]["body"])
        self.assertEqual(d["response"]["body"]["Header"]["ReportName"], "ProfitAndLoss")

    # ── Status Save / Read ────────────────────────────────────────────────
    def test_status_save_read(self):
        r = requests.post(f"{BASE}/api/connectors/quickbooks",
                          json={"status": "Connected",
                                "config": {"company": "TechStart Agency"}})
        self.assertEqual(r.status_code, 200)
        r2 = requests.get(f"{BASE}/api/connectors/quickbooks")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["status"], "Connected")


if __name__ == "__main__":
    unittest.main()
