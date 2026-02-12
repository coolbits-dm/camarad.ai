"""
Phase 23 – Mailchimp connector test-suite
Target: 15 tests (audiences, overview, campaigns, automations, segments, reports, test-call, status)
"""
import unittest, json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from app import app

class MailchimpTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    # ── Audiences ──────────────────────────────────────────────────────────
    def test_audiences(self):
        r = self.client.get("/api/connectors/mailchimp/audiences")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 4)
        self.assertIn("member_count", data[0])

    # ── Overview ───────────────────────────────────────────────────────────
    def test_overview_all(self):
        r = self.client.get("/api/connectors/mailchimp/overview")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("kpis", data)
        self.assertGreaterEqual(len(data["kpis"]), 5)
        self.assertIn("monthly_trend", data)

    def test_overview_by_audience(self):
        r = self.client.get("/api/connectors/mailchimp/overview?audience=VIP+Customers")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("kpis", data)
        self.assertEqual(data["kpis"][0]["label"], "Subscribers")

    def test_overview_unknown_audience(self):
        r = self.client.get("/api/connectors/mailchimp/overview?audience=NOPE")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        # Falls back to global overview
        self.assertIn("kpis", data)

    # ── Campaigns ──────────────────────────────────────────────────────────
    def test_campaigns_all(self):
        r = self.client.get("/api/connectors/mailchimp/campaigns")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 10)

    def test_campaigns_filter_status(self):
        r = self.client.get("/api/connectors/mailchimp/campaigns?status=draft")
        data = r.get_json()
        self.assertTrue(all(c["status"] == "draft" for c in data))
        self.assertGreaterEqual(len(data), 1)

    def test_campaigns_filter_audience(self):
        r = self.client.get("/api/connectors/mailchimp/campaigns?audience=VIP+Customers")
        data = r.get_json()
        self.assertTrue(all(c["audience"] == "VIP Customers" for c in data))

    def test_campaigns_filter_type(self):
        r = self.client.get("/api/connectors/mailchimp/campaigns?type=plaintext")
        data = r.get_json()
        self.assertTrue(all(c["type"] == "plaintext" for c in data))

    # ── Automations ────────────────────────────────────────────────────────
    def test_automations_all(self):
        r = self.client.get("/api/connectors/mailchimp/automations")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertGreaterEqual(len(data), 8)

    def test_automations_filter_status(self):
        r = self.client.get("/api/connectors/mailchimp/automations?status=paused")
        data = r.get_json()
        self.assertTrue(all(a["status"] == "paused" for a in data))
        self.assertGreaterEqual(len(data), 2)

    # ── Segments ───────────────────────────────────────────────────────────
    def test_segments_all(self):
        r = self.client.get("/api/connectors/mailchimp/segments")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertGreaterEqual(len(data), 8)

    def test_segments_filter_audience(self):
        r = self.client.get("/api/connectors/mailchimp/segments?audience=VIP+Customers")
        data = r.get_json()
        self.assertTrue(all(s["audience"] == "VIP Customers" for s in data))

    # ── Reports ────────────────────────────────────────────────────────────
    def test_reports_unified(self):
        r = self.client.get("/api/connectors/mailchimp/reports")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        # 11 campaigns + 8 automations + 8 segments = 27 rows
        self.assertGreaterEqual(len(data), 27)
        types = {row["type"] for row in data}
        self.assertIn("Campaign", types)
        self.assertIn("Automation", types)
        self.assertIn("Segment", types)

    # ── Test API Call ──────────────────────────────────────────────────────
    def test_api_call_campaigns(self):
        r = self.client.post("/api/connectors/mailchimp/test-call",
                             json={"endpoint": "campaigns", "method": "GET"})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(data["endpoint"], "campaigns")
        self.assertIn("campaigns", data["response"]["body"])

    def test_api_call_lists(self):
        r = self.client.post("/api/connectors/mailchimp/test-call",
                             json={"endpoint": "lists", "method": "GET"})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("lists", data["response"]["body"])

    # ── Status save / read ─────────────────────────────────────────────────
    def test_status_save_read(self):
        self.client.post("/api/connectors/mailchimp",
                         json={"status": "Connected", "config": {"api_key": "xxx-us1"}})
        r = self.client.get("/api/connectors/mailchimp")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(data["status"], "Connected")


if __name__ == "__main__":
    unittest.main(verbosity=2)
