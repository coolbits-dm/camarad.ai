"""
Phase 30 – Vercel connector tests  (20 tests)
Deployments, Domains, Logs, Analytics, Overview, Reports, Test API, Status
"""
import unittest, requests

BASE = "http://127.0.0.1:5051"


class TestVercel(unittest.TestCase):

    # ── Deployments ────────────────────────────────────────────────────
    def test_deployments_all(self):
        r = requests.get(f"{BASE}/api/connectors/vercel/deployments")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data), 15)
        self.assertTrue(all("uid" in d for d in data))

    def test_deployments_filter_ready(self):
        r = requests.get(f"{BASE}/api/connectors/vercel/deployments?state=READY")
        data = r.json()
        self.assertTrue(len(data) >= 10)
        self.assertTrue(all(d["state"] == "READY" for d in data))

    def test_deployments_filter_error(self):
        r = requests.get(f"{BASE}/api/connectors/vercel/deployments?state=ERROR")
        data = r.json()
        self.assertEqual(len(data), 2)
        self.assertTrue(all(d["state"] == "ERROR" for d in data))

    def test_deployments_filter_production(self):
        r = requests.get(f"{BASE}/api/connectors/vercel/deployments?target=production")
        data = r.json()
        self.assertTrue(len(data) >= 7)
        self.assertTrue(all(d["target"] == "production" for d in data))

    def test_deployments_filter_project(self):
        r = requests.get(f"{BASE}/api/connectors/vercel/deployments?project=camarad-docs")
        data = r.json()
        self.assertTrue(len(data) >= 3)
        self.assertTrue(all("docs" in d["name"] for d in data))

    # ── Domains ────────────────────────────────────────────────────────
    def test_domains_all(self):
        r = requests.get(f"{BASE}/api/connectors/vercel/domains")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data), 10)
        self.assertTrue(all("ssl" in d for d in data))

    def test_domains_filter_valid(self):
        r = requests.get(f"{BASE}/api/connectors/vercel/domains?status=valid")
        data = r.json()
        self.assertTrue(len(data) >= 7)
        self.assertTrue(all(d["status"] == "valid" for d in data))

    def test_domains_filter_expired(self):
        r = requests.get(f"{BASE}/api/connectors/vercel/domains?status=expired")
        data = r.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "old-site.techstart.com")

    # ── Logs ───────────────────────────────────────────────────────────
    def test_logs_all(self):
        r = requests.get(f"{BASE}/api/connectors/vercel/logs")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data), 18)

    def test_logs_filter_deployment(self):
        r = requests.get(f"{BASE}/api/connectors/vercel/logs?deployment=dpl_abc005")
        data = r.json()
        self.assertEqual(len(data), 5)
        self.assertTrue(all(l["deployment"] == "dpl_abc005" for l in data))

    def test_logs_filter_error(self):
        r = requests.get(f"{BASE}/api/connectors/vercel/logs?level=error")
        data = r.json()
        self.assertTrue(len(data) >= 3)
        self.assertTrue(all(l["level"] == "error" for l in data))

    def test_logs_search(self):
        r = requests.get(f"{BASE}/api/connectors/vercel/logs?search=memory")
        data = r.json()
        self.assertTrue(len(data) >= 1)
        self.assertTrue(all("memory" in l["message"].lower() for l in data))

    # ── Analytics ──────────────────────────────────────────────────────
    def test_analytics(self):
        r = requests.get(f"{BASE}/api/connectors/vercel/analytics")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn("total_visitors", d)
        self.assertIn("top_pages", d)
        self.assertIn("daily_visitors", d)
        self.assertIn("top_referrers", d)
        self.assertTrue(len(d["top_pages"]) >= 8)
        self.assertTrue(len(d["daily_visitors"]) >= 7)

    # ── Overview ───────────────────────────────────────────────────────
    def test_overview(self):
        r = requests.get(f"{BASE}/api/connectors/vercel/overview")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["total_deployments"], 156)
        self.assertEqual(d["domains"], 10)
        self.assertIn("deploy_trend", d)
        self.assertTrue(len(d["deploy_trend"]) >= 7)

    # ── Reports ────────────────────────────────────────────────────────
    def test_reports_unified(self):
        r = requests.get(f"{BASE}/api/connectors/vercel/reports")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        # 15 Deployments + 10 Domains + 8 Pages = 33
        self.assertTrue(len(data) >= 33)
        types = set(row["type"] for row in data)
        self.assertIn("Deployment", types)
        self.assertIn("Domain", types)
        self.assertIn("Page", types)

    # ── Test API ───────────────────────────────────────────────────────
    def test_api_call_list_deployments(self):
        r = requests.post(f"{BASE}/api/connectors/vercel/test-call",
                          json={"endpoint": "list-deployments"})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn("deployments", d["response"]["body"])

    def test_api_call_list_domains(self):
        r = requests.post(f"{BASE}/api/connectors/vercel/test-call",
                          json={"endpoint": "list-domains"})
        d = r.json()
        self.assertIn("domains", d["response"]["body"])

    def test_api_call_get_project(self):
        r = requests.post(f"{BASE}/api/connectors/vercel/test-call",
                          json={"endpoint": "get-project"})
        d = r.json()
        self.assertEqual(d["response"]["body"]["name"], "camarad-app")

    def test_api_call_create_deployment(self):
        r = requests.post(f"{BASE}/api/connectors/vercel/test-call",
                          json={"endpoint": "create-deployment"})
        d = r.json()
        self.assertEqual(d["response"]["body"]["state"], "BUILDING")

    # ── Status ─────────────────────────────────────────────────────────
    def test_status_save_read(self):
        requests.post(f"{BASE}/api/connectors/vercel",
                      json={"status": "Connected", "config": {"team": "team_abc123"}})
        r = requests.get(f"{BASE}/api/connectors")
        statuses = r.json()
        self.assertEqual(statuses.get("vercel"), "Connected")


if __name__ == "__main__":
    unittest.main()
