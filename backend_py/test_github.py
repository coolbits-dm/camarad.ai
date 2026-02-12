"""
GitHub Connector – 20 tests
Phase 26: Accounts, Repos, Commits, Issues/PRs, Actions, Reports, Test API, Settings
"""
import unittest
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from app import app


class GitHubTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()
        app.config["TESTING"] = True

    # ── Accounts ──
    def test_accounts(self):
        r = self.client.get("/api/connectors/github/accounts")
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(data), 3)
        types = [a["type"] for a in data]
        self.assertIn("User", types)
        self.assertIn("Organization", types)

    # ── Overview ──
    def test_overview_all(self):
        r = self.client.get("/api/connectors/github/overview?account=all")
        d = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(d["total_repos"], 185)
        self.assertEqual(d["total_stars"], 8734)
        self.assertIn("weekly_commits", d)
        self.assertEqual(len(d["weekly_commits"]), 5)

    def test_overview_by_account(self):
        r = self.client.get("/api/connectors/github/overview?account=org-gh-001")
        d = r.get_json()
        self.assertEqual(d["total_repos"], 45)
        self.assertEqual(d["total_stars"], 3278)

    def test_overview_unknown_account(self):
        r = self.client.get("/api/connectors/github/overview?account=unknown-999")
        d = r.get_json()
        self.assertEqual(d["total_repos"], 0)
        self.assertEqual(d["total_stars"], 0)

    # ── Repositories ──
    def test_repos_all(self):
        r = self.client.get("/api/connectors/github/repos")
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(data), 12)

    def test_repos_filter_visibility(self):
        r = self.client.get("/api/connectors/github/repos?visibility=private")
        data = r.get_json()
        self.assertTrue(all(repo["visibility"] == "private" for repo in data))
        self.assertGreater(len(data), 0)

    def test_repos_filter_language(self):
        r = self.client.get("/api/connectors/github/repos?language=Python")
        data = r.get_json()
        self.assertTrue(all(repo["language"] == "Python" for repo in data))
        self.assertGreater(len(data), 0)

    # ── Commits ──
    def test_commits_all(self):
        r = self.client.get("/api/connectors/github/commits")
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(data), 15)

    def test_commits_filter_repo(self):
        r = self.client.get("/api/connectors/github/commits?repo=camarad-ai")
        data = r.get_json()
        self.assertTrue(all(c["repo"] == "camarad-ai" for c in data))
        self.assertGreater(len(data), 0)

    def test_commits_filter_author(self):
        r = self.client.get("/api/connectors/github/commits?author=Alice+Chen")
        data = r.get_json()
        self.assertTrue(all(c["author"] == "Alice Chen" for c in data))
        self.assertGreater(len(data), 0)

    # ── Issues & PRs ──
    def test_issues_all(self):
        r = self.client.get("/api/connectors/github/issues")
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(data), 12)

    def test_issues_filter_state(self):
        r = self.client.get("/api/connectors/github/issues?state=open")
        data = r.get_json()
        self.assertTrue(all(i["state"] == "open" for i in data))
        self.assertGreater(len(data), 0)

    def test_issues_filter_kind(self):
        r = self.client.get("/api/connectors/github/issues?kind=pr")
        data = r.get_json()
        self.assertTrue(all(i["kind"] == "pr" for i in data))
        self.assertGreater(len(data), 0)

    # ── Actions ──
    def test_actions_all(self):
        r = self.client.get("/api/connectors/github/actions")
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(data), 10)

    def test_actions_filter_conclusion(self):
        r = self.client.get("/api/connectors/github/actions?conclusion=success")
        data = r.get_json()
        self.assertTrue(all(a["conclusion"] == "success" for a in data))
        self.assertGreater(len(data), 0)

    # ── Reports ──
    def test_reports_unified(self):
        r = self.client.get("/api/connectors/github/reports")
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        # 12 repos + 15 commits + 12 issues + 10 actions = 49 rows
        self.assertGreaterEqual(len(data), 49)
        types = set(row["type"] for row in data)
        self.assertIn("Repository", types)
        self.assertIn("Commit", types)
        self.assertIn("Action", types)

    # ── Test API ──
    def test_api_call_repos(self):
        r = self.client.post("/api/connectors/github/test-call",
                             data=json.dumps({"endpoint": "repos"}),
                             content_type="application/json")
        d = r.get_json()
        self.assertEqual(d["endpoint"], "repos")
        self.assertEqual(d["response"]["status_code"], 200)
        self.assertIsInstance(d["response"]["body"], list)

    def test_api_call_commits(self):
        r = self.client.post("/api/connectors/github/test-call",
                             data=json.dumps({"endpoint": "commits"}),
                             content_type="application/json")
        d = r.get_json()
        self.assertEqual(d["endpoint"], "commits")
        self.assertIn("body", d["response"])

    def test_api_call_issues(self):
        r = self.client.post("/api/connectors/github/test-call",
                             data=json.dumps({"endpoint": "issues"}),
                             content_type="application/json")
        d = r.get_json()
        self.assertEqual(d["endpoint"], "issues")
        self.assertIn("body", d["response"])

    # ── Status save + read ──
    def test_status_save_read(self):
        self.client.post("/api/connectors/github",
                         data=json.dumps({"status": "Connected", "config": {"token": "ghp_test"}}),
                         content_type="application/json")
        r = self.client.get("/api/connectors")
        statuses = r.get_json()
        self.assertEqual(statuses.get("github"), "Connected")


if __name__ == "__main__":
    unittest.main()
