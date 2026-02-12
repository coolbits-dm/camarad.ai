"""Phase 28 – Telegram connector tests (20 tests)."""
import unittest, json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from app import app

BASE = "/api/connectors/telegram"

class TelegramTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    # ── Chats ──
    def test_chats_all(self):
        r = self.client.get(f"{BASE}/chats")
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(data), 10)

    def test_chats_filter_private(self):
        r = self.client.get(f"{BASE}/chats?type=private")
        data = r.get_json()
        self.assertTrue(all(c["type"] == "private" for c in data))
        self.assertGreater(len(data), 0)

    def test_chats_filter_group(self):
        r = self.client.get(f"{BASE}/chats?type=group")
        data = r.get_json()
        self.assertTrue(all(c["type"] == "group" for c in data))
        self.assertGreater(len(data), 0)

    # ── Overview ──
    def test_overview(self):
        r = self.client.get(f"{BASE}/overview")
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertIn("kpis", data)
        self.assertEqual(data["kpis"]["messages_sent"], 1234)
        self.assertEqual(data["kpis"]["messages_received"], 987)
        self.assertEqual(len(data["daily_messages"]), 7)
        self.assertIn("chat_type_breakdown", data)

    # ── Channels ──
    def test_channels_all(self):
        r = self.client.get(f"{BASE}/channels")
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(data), 6)

    def test_channels_filter_public(self):
        r = self.client.get(f"{BASE}/channels?type=public")
        data = r.get_json()
        self.assertTrue(all(ch["type"] == "public" for ch in data))
        self.assertGreater(len(data), 0)

    def test_channels_filter_private(self):
        r = self.client.get(f"{BASE}/channels?type=private")
        data = r.get_json()
        self.assertTrue(all(ch["type"] == "private" for ch in data))
        self.assertGreater(len(data), 0)

    # ── Bots ──
    def test_bots_all(self):
        r = self.client.get(f"{BASE}/bots")
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(data), 5)
        for b in data:
            self.assertIn("username", b)
            self.assertIn("commands", b)

    def test_bots_filter_active(self):
        r = self.client.get(f"{BASE}/bots?status=active")
        data = r.get_json()
        self.assertTrue(all(b["status"] == "active" for b in data))
        self.assertGreater(len(data), 0)

    def test_bots_filter_paused(self):
        r = self.client.get(f"{BASE}/bots?status=paused")
        data = r.get_json()
        self.assertTrue(all(b["status"] == "paused" for b in data))
        self.assertGreater(len(data), 0)

    # ── Messages ──
    def test_messages_all(self):
        r = self.client.get(f"{BASE}/messages")
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(data), 15)

    def test_messages_filter_chat(self):
        r = self.client.get(f"{BASE}/messages?chat=Alice")
        data = r.get_json()
        self.assertTrue(all(m["chat"] == "Alice" for m in data))
        self.assertGreater(len(data), 0)

    def test_messages_filter_from(self):
        r = self.client.get(f"{BASE}/messages?from=Maria")
        data = r.get_json()
        self.assertTrue(all("maria" in m["from"].lower() for m in data))
        self.assertGreater(len(data), 0)

    def test_messages_search(self):
        r = self.client.get(f"{BASE}/messages?search=deploy")
        data = r.get_json()
        self.assertTrue(all("deploy" in m["text"].lower() for m in data))
        self.assertGreater(len(data), 0)

    # ── Reports ──
    def test_reports_unified(self):
        r = self.client.get(f"{BASE}/reports")
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        types = {row["type"] for row in data}
        self.assertIn("Chat", types)
        self.assertIn("Channel", types)
        self.assertIn("Bot", types)
        self.assertIn("Message", types)
        # 10 chats + 6 channels + 5 bots + 15 messages = 36
        self.assertGreaterEqual(len(data), 36)

    # ── Test API Call ──
    def test_api_call_get_updates(self):
        r = self.client.post(f"{BASE}/test-call",
                             data=json.dumps({"endpoint": "getUpdates"}),
                             content_type="application/json")
        data = r.get_json()
        self.assertTrue(data["ok"])
        self.assertIn("telegram.org", data["endpoint"])
        self.assertTrue(data["response"]["body"]["ok"])

    def test_api_call_send_message(self):
        r = self.client.post(f"{BASE}/test-call",
                             data=json.dumps({"endpoint": "sendMessage"}),
                             content_type="application/json")
        data = r.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["method"], "POST")
        self.assertIn("message_id", data["response"]["body"]["result"])

    def test_api_call_get_me(self):
        r = self.client.post(f"{BASE}/test-call",
                             data=json.dumps({"endpoint": "getMe"}),
                             content_type="application/json")
        data = r.get_json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["response"]["body"]["result"]["is_bot"])

    # ── Status ──
    def test_status_save_read(self):
        self.client.post("/api/connectors/telegram",
                         data=json.dumps({"status": "Connected", "config": {"token": "tg_test"}}),
                         content_type="application/json")
        r = self.client.get("/api/connectors")
        statuses = r.get_json()
        self.assertEqual(statuses.get("telegram"), "Connected")

if __name__ == "__main__":
    unittest.main()
