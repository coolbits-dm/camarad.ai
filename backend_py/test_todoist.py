"""Phase 27 – Todoist connector tests (20 tests)."""
import unittest, json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from app import app

BASE = "/api/connectors/todoist"

class TodoistTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    # ── Projects ──
    def test_projects(self):
        r = self.client.get(f"{BASE}/projects")
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(data), 3)
        self.assertTrue(any(p["name"] == "Daily Tasks" for p in data))

    # ── Overview ──
    def test_overview_all(self):
        r = self.client.get(f"{BASE}/overview")
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertIn("kpis", data)
        self.assertEqual(data["kpis"]["tasks_today"], 12)
        self.assertEqual(len(data["daily_completed"]), 7)
        self.assertEqual(len(data["project_stats"]), 3)

    def test_overview_by_project(self):
        r = self.client.get(f"{BASE}/overview?project=Marketing Q1")
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(data["project_stats"]), 1)
        self.assertEqual(data["project_stats"][0]["project"], "Marketing Q1")

    def test_overview_unknown_project(self):
        r = self.client.get(f"{BASE}/overview?project=NonExistent")
        self.assertEqual(r.status_code, 404)

    # ── Tasks ──
    def test_tasks_all(self):
        r = self.client.get(f"{BASE}/tasks")
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(data), 15)

    def test_tasks_filter_status_open(self):
        r = self.client.get(f"{BASE}/tasks?status=open")
        data = r.get_json()
        self.assertTrue(all(not t["is_completed"] for t in data))
        self.assertGreater(len(data), 0)

    def test_tasks_filter_status_completed(self):
        r = self.client.get(f"{BASE}/tasks?status=completed")
        data = r.get_json()
        self.assertTrue(all(t["is_completed"] for t in data))
        self.assertGreater(len(data), 0)

    def test_tasks_filter_priority(self):
        r = self.client.get(f"{BASE}/tasks?priority=1")
        data = r.get_json()
        self.assertTrue(all(t["priority"] == 1 for t in data))
        self.assertGreater(len(data), 0)

    def test_tasks_filter_project(self):
        r = self.client.get(f"{BASE}/tasks?project=Personal Goals")
        data = r.get_json()
        self.assertTrue(all(t["project"] == "Personal Goals" for t in data))
        self.assertGreater(len(data), 0)

    def test_tasks_filter_label(self):
        r = self.client.get(f"{BASE}/tasks?label=urgent")
        data = r.get_json()
        self.assertTrue(all("urgent" in t["labels"] for t in data))
        self.assertGreater(len(data), 0)

    # ── Projects Detail ──
    def test_projects_detail(self):
        r = self.client.get(f"{BASE}/projects-detail")
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(data), 3)
        for p in data:
            self.assertIn("open_tasks", p)
            self.assertIn("completed_tasks", p)
            self.assertIn("overdue_tasks", p)
            self.assertIn("labels_used", p)

    # ── Labels ──
    def test_labels_all(self):
        r = self.client.get(f"{BASE}/labels")
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(data), 10)

    def test_labels_search(self):
        r = self.client.get(f"{BASE}/labels?search=health")
        data = r.get_json()
        self.assertTrue(all("health" in l["name"].lower() for l in data))
        self.assertGreater(len(data), 0)

    # ── Habits ──
    def test_habits_all(self):
        r = self.client.get(f"{BASE}/habits")
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(data), 6)
        for h in data:
            self.assertIn("streak", h)
            self.assertIn("frequency", h)

    def test_habits_filter_frequency(self):
        r = self.client.get(f"{BASE}/habits?frequency=daily")
        data = r.get_json()
        self.assertTrue(all(h["frequency"] == "daily" for h in data))
        self.assertGreater(len(data), 0)

    # ── Reports ──
    def test_reports_unified(self):
        r = self.client.get(f"{BASE}/reports")
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        types = {row["type"] for row in data}
        self.assertIn("Task", types)
        self.assertIn("Project", types)
        self.assertIn("Label", types)
        self.assertIn("Habit", types)
        # 15 tasks + 3 projects + 10 labels + 6 habits = 34
        self.assertGreaterEqual(len(data), 34)

    # ── Test API Call ──
    def test_api_call_tasks(self):
        r = self.client.post(f"{BASE}/test-call",
                             data=json.dumps({"endpoint": "tasks"}),
                             content_type="application/json")
        data = r.get_json()
        self.assertTrue(data["ok"])
        self.assertIn("todoist.com", data["endpoint"])
        self.assertEqual(len(data["response"]["body"]), 3)

    def test_api_call_projects(self):
        r = self.client.post(f"{BASE}/test-call",
                             data=json.dumps({"endpoint": "projects"}),
                             content_type="application/json")
        data = r.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(len(data["response"]["body"]), 3)

    def test_api_call_labels(self):
        r = self.client.post(f"{BASE}/test-call",
                             data=json.dumps({"endpoint": "labels"}),
                             content_type="application/json")
        data = r.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(len(data["response"]["body"]), 5)

    # ── Status ──
    def test_status_save_read(self):
        self.client.post("/api/connectors/todoist",
                         data=json.dumps({"status": "Connected", "config": {"token": "td_test"}}),
                         content_type="application/json")
        r = self.client.get("/api/connectors")
        statuses = r.get_json()
        self.assertEqual(statuses.get("todoist"), "Connected")

if __name__ == "__main__":
    unittest.main()
