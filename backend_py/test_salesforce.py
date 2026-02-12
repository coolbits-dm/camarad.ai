"""
test_salesforce.py — Salesforce connector tests (Phase 21)
Covers: orgs, overview, leads (with filters), opportunities (with filters),
        accounts (with filters), campaigns (with filters), reports,
        test-call (leads + opportunities), status save/read.
"""

import unittest, requests

BASE = "http://127.0.0.1:5051"


class TestSalesforce(unittest.TestCase):

    # ── Orgs ──────────────────────────────────────────────────────────────
    def test_orgs(self):
        r = requests.get(f"{BASE}/api/connectors/salesforce/orgs")
        self.assertEqual(r.status_code, 200)
        orgs = r.json()["orgs"]
        self.assertGreaterEqual(len(orgs), 3)
        names = [o["name"] for o in orgs]
        self.assertIn("TechStart Production", names)

    # ── Overview ──────────────────────────────────────────────────────────
    def test_overview(self):
        r = requests.get(f"{BASE}/api/connectors/salesforce/overview",
                         params={"org_id": "00D5g000008XYZABC"})
        self.assertEqual(r.status_code, 200)
        ov = r.json()["overview"]
        self.assertGreater(ov["total_leads"], 0)
        self.assertGreater(ov["pipeline_value"], 0)
        self.assertIn("monthly_pipeline", ov)
        self.assertIn("opportunity_stage_distribution", ov)

    def test_overview_unknown_org(self):
        r = requests.get(f"{BASE}/api/connectors/salesforce/overview",
                         params={"org_id": "UNKNOWN"})
        self.assertEqual(r.status_code, 200)
        ov = r.json()["overview"]
        self.assertEqual(ov["total_leads"], 0)

    # ── Leads ─────────────────────────────────────────────────────────────
    def test_leads_all(self):
        r = requests.get(f"{BASE}/api/connectors/salesforce/leads")
        self.assertEqual(r.status_code, 200)
        leads = r.json()["leads"]
        self.assertGreaterEqual(len(leads), 10)

    def test_leads_filter_status(self):
        r = requests.get(f"{BASE}/api/connectors/salesforce/leads",
                         params={"status": "Working"})
        self.assertEqual(r.status_code, 200)
        leads = r.json()["leads"]
        self.assertGreater(len(leads), 0)
        for l in leads:
            self.assertIn("Working", l["status"])

    def test_leads_filter_rating(self):
        r = requests.get(f"{BASE}/api/connectors/salesforce/leads",
                         params={"rating": "Hot"})
        self.assertEqual(r.status_code, 200)
        leads = r.json()["leads"]
        self.assertGreater(len(leads), 0)
        for l in leads:
            self.assertEqual(l["rating"], "Hot")

    # ── Opportunities ─────────────────────────────────────────────────────
    def test_opportunities_all(self):
        r = requests.get(f"{BASE}/api/connectors/salesforce/opportunities")
        self.assertEqual(r.status_code, 200)
        opps = r.json()["opportunities"]
        self.assertGreaterEqual(len(opps), 8)

    def test_opportunities_filter_stage(self):
        r = requests.get(f"{BASE}/api/connectors/salesforce/opportunities",
                         params={"stage": "Closed Won"})
        self.assertEqual(r.status_code, 200)
        opps = r.json()["opportunities"]
        self.assertGreater(len(opps), 0)
        for o in opps:
            self.assertIn("Closed Won", o["stage"])

    # ── Accounts ──────────────────────────────────────────────────────────
    def test_accounts_all(self):
        r = requests.get(f"{BASE}/api/connectors/salesforce/accounts")
        self.assertEqual(r.status_code, 200)
        accts = r.json()["accounts"]
        self.assertGreaterEqual(len(accts), 8)

    def test_accounts_filter_type(self):
        r = requests.get(f"{BASE}/api/connectors/salesforce/accounts",
                         params={"type": "Customer"})
        self.assertEqual(r.status_code, 200)
        accts = r.json()["accounts"]
        self.assertGreater(len(accts), 0)
        for a in accts:
            self.assertEqual(a["type"], "Customer")

    # ── Campaigns ─────────────────────────────────────────────────────────
    def test_campaigns_all(self):
        r = requests.get(f"{BASE}/api/connectors/salesforce/campaigns")
        self.assertEqual(r.status_code, 200)
        camps = r.json()["campaigns"]
        self.assertGreaterEqual(len(camps), 5)

    def test_campaigns_filter_status(self):
        r = requests.get(f"{BASE}/api/connectors/salesforce/campaigns",
                         params={"status": "Active"})
        self.assertEqual(r.status_code, 200)
        camps = r.json()["campaigns"]
        self.assertGreater(len(camps), 0)
        for c in camps:
            self.assertEqual(c["status"], "Active")

    # ── Reports ───────────────────────────────────────────────────────────
    def test_reports(self):
        r = requests.get(f"{BASE}/api/connectors/salesforce/reports")
        self.assertEqual(r.status_code, 200)
        rows = r.json()["rows"]
        self.assertEqual(len(rows), 31)
        self.assertIn("new_leads", rows[0])
        self.assertIn("revenue", rows[0])

    # ── Test Call ─────────────────────────────────────────────────────────
    def test_call_leads(self):
        r = requests.post(f"{BASE}/api/connectors/salesforce/test-call",
                          json={"endpoint": "leads", "method": "GET"})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["response"]["status_code"], 200)
        self.assertEqual(d["response"]["body"]["totalSize"], 3)
        self.assertIn("latency_ms", d)

    def test_call_opportunities(self):
        r = requests.post(f"{BASE}/api/connectors/salesforce/test-call",
                          json={"endpoint": "opportunities", "method": "GET"})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["response"]["body"]["totalSize"], 2)

    # ── Status Save / Read ────────────────────────────────────────────────
    def test_status_save_read(self):
        # Save
        r = requests.post(f"{BASE}/api/connectors/salesforce",
                          json={"status": "Connected",
                                "config": {"org": "TechStart Production"}})
        self.assertEqual(r.status_code, 200)
        # Read
        r2 = requests.get(f"{BASE}/api/connectors/salesforce")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["status"], "Connected")


if __name__ == "__main__":
    unittest.main()
