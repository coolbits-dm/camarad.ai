"""
Notion Connector – 17 tests
Phase 25: Pages, Databases, Blocks, Collaborators, Reports, Test API, Settings
"""
import unittest
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from app import app

class NotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()
        app.config["TESTING"] = True

    # ── Workspaces ──
    def test_workspaces(self):
        r = self.client.get("/api/connectors/notion/workspaces")
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(data), 3)
        names = [w["name"] for w in data]
        self.assertIn("TechStart Team", names)
        self.assertIn("Personal Journal", names)
        self.assertIn("Project Wiki", names)

    # ── Overview ──
    def test_overview_all(self):
        r = self.client.get("/api/connectors/notion/overview?workspace=all")
        d = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(d["total_pages"], 2113)
        self.assertEqual(d["total_databases"], 75)
        self.assertEqual(d["total_blocks"], 189234)
        self.assertIn("monthly_trend", d)
        self.assertEqual(len(d["monthly_trend"]), 5)

    def test_overview_by_workspace(self):
        r = self.client.get("/api/connectors/notion/overview?workspace=ws-abc123-def456")
        d = r.get_json()
        self.assertEqual(d["total_pages"], 1234)
        self.assertEqual(d["collaborators"], 12)

    def test_overview_unknown_workspace(self):
        r = self.client.get("/api/connectors/notion/overview?workspace=ws-unknown")
        d = r.get_json()
        self.assertEqual(d["total_pages"], 0)
        self.assertEqual(d["total_databases"], 0)

    # ── Pages ──
    def test_pages_all(self):
        r = self.client.get("/api/connectors/notion/pages")
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(data), 15)

    def test_pages_filter_status(self):
        r = self.client.get("/api/connectors/notion/pages?status=private")
        data = r.get_json()
        self.assertTrue(all(p["status"] == "private" for p in data))
        self.assertGreater(len(data), 0)

    def test_pages_filter_workspace(self):
        r = self.client.get("/api/connectors/notion/pages?workspace=Project+Wiki")
        data = r.get_json()
        self.assertTrue(all(p["workspace"] == "Project Wiki" for p in data))
        self.assertGreater(len(data), 0)

    # ── Databases ──
    def test_databases_all(self):
        r = self.client.get("/api/connectors/notion/databases")
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(data), 10)

    def test_databases_filter_type(self):
        r = self.client.get("/api/connectors/notion/databases?type=kanban")
        data = r.get_json()
        self.assertTrue(all(d["type"] == "kanban" for d in data))
        self.assertGreater(len(data), 0)

    # ── Blocks ──
    def test_blocks_all(self):
        r = self.client.get("/api/connectors/notion/blocks")
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(data), 12)

    def test_blocks_filter_type(self):
        r = self.client.get("/api/connectors/notion/blocks?type=to_do")
        data = r.get_json()
        self.assertTrue(all(b["type"] == "to_do" for b in data))
        self.assertGreater(len(data), 0)

    def test_blocks_search(self):
        r = self.client.get("/api/connectors/notion/blocks?q=MRR")
        data = r.get_json()
        self.assertGreater(len(data), 0)
        self.assertTrue(any("MRR" in b["content"] for b in data))

    # ── Collaborators ──
    def test_collaborators_all(self):
        r = self.client.get("/api/connectors/notion/collaborators")
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(data), 10)

    def test_collaborators_filter_role(self):
        r = self.client.get("/api/connectors/notion/collaborators?role=Admin")
        data = r.get_json()
        self.assertTrue(all(c["role"] == "Admin" for c in data))
        self.assertGreater(len(data), 0)

    # ── Reports ──
    def test_reports_unified(self):
        r = self.client.get("/api/connectors/notion/reports")
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        # 15 pages + 10 databases + 8 blocks = 33 rows
        self.assertGreaterEqual(len(data), 33)
        types = set(row["type"] for row in data)
        self.assertIn("Page", types)
        self.assertIn("Database", types)
        self.assertIn("Block", types)

    # ── Test API ──
    def test_api_call_pages(self):
        r = self.client.post("/api/connectors/notion/test-call",
                             data=json.dumps({"endpoint": "pages"}),
                             content_type="application/json")
        d = r.get_json()
        self.assertEqual(d["endpoint"], "pages")
        self.assertEqual(d["response"]["status_code"], 200)
        self.assertIn("results", d["response"]["body"])

    def test_api_call_databases(self):
        r = self.client.post("/api/connectors/notion/test-call",
                             data=json.dumps({"endpoint": "databases"}),
                             content_type="application/json")
        d = r.get_json()
        self.assertEqual(d["endpoint"], "databases")
        self.assertIn("results", d["response"]["body"])

    # ── Status save + read ──
    def test_status_save_read(self):
        self.client.post("/api/connectors/notion",
                         data=json.dumps({"status": "Connected", "config": {"token": "secret_test"}}),
                         content_type="application/json")
        r = self.client.get("/api/connectors")
        statuses = r.get_json()
        self.assertEqual(statuses.get("notion"), "Connected")


if __name__ == "__main__":
    unittest.main()
