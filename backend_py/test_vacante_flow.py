import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app as app_module
from app import app


class TestVacanteFlow(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "vacante-test.db"
        self.previous_database = app.config.get("DATABASE")
        app.config["DATABASE"] = str(self.db_path)

    def tearDown(self):
        if self.previous_database is None:
            app.config.pop("DATABASE", None)
        else:
            app.config["DATABASE"] = self.previous_database
        self.tmpdir.cleanup()

    def test_afla_page_renders_live_contact_form(self):
        response = self.client.get("/afla-mai-mult")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('action="/api/contact"', html)
        self.assertIn('name="website"', html)
        self.assertIn('name="phone"', html)
        self.assertIn('id="contact-form-status"', html)
        self.assertIn('"@type": "FAQPage"', html)
        self.assertIn('id="vac-cookie-banner"', html)

    def test_homepage_renders_cookie_banner_and_org_schema(self):
        response = self.client.get("/", base_url="https://vacanteinteligente.com")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('"@type": "Organization"', html)
        self.assertIn('vacante_cookie_consent_default', html)
        self.assertIn('id="vac-cookie-banner"', html)
        self.assertIn('vacante-social-og.jpg', html)

    def test_faq_page_renders_details_schema_and_contact_paths(self):
        response = self.client.get("/intrebari-frecvente")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('"@type": "FAQPage"', html)
        self.assertIn("Raspunsuri clare, inainte sa deschizi platforma.", html)
        self.assertIn('<details class="faq-item">', html)
        self.assertIn('/afla-mai-mult#contact', html)

    def test_vacante_sitemap_contains_faq_page(self):
        response = self.client.get("/sitemap.xml", base_url="https://vacanteinteligente.com")
        self.assertEqual(response.status_code, 200)
        xml = response.get_data(as_text=True)
        self.assertIn("https://vacanteinteligente.com/afla-mai-mult", xml)
        self.assertIn("https://vacanteinteligente.com/intrebari-frecvente", xml)
        self.assertNotIn("https://vacanteinteligente.com/pricing", xml)

    def test_contact_api_persists_message_and_returns_redirect(self):
        response = self.client.post(
            "/api/contact",
            data={
                "name": "Ana Popescu",
                "email": "ana@example.com",
                "phone": "0712 345 678",
                "message": "Buna, vreau sa inteleg mai bine cum functioneaza membershipul.",
                "source_path": "/afla-mai-mult",
                "website": "",
            },
            headers={"Accept": "application/json", "CF-Connecting-IP": "198.51.100.10"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload, {"ok": True, "redirect": "/multumesc?contact=1"})

        conn = sqlite3.connect(str(self.db_path))
        row = conn.execute(
            "SELECT name, email, phone, source_path FROM vacante_contact_messages"
        ).fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], "Ana Popescu")
        self.assertEqual(row[1], "ana@example.com")
        self.assertEqual(row[2], "0712 345 678")
        self.assertEqual(row[3], "/afla-mai-mult")

    def test_contact_api_rate_limits_after_five_messages_per_hour(self):
        payload = {
            "name": "Mihai Ionescu",
            "email": "mihai@example.com",
            "message": "Salut, as vrea mai multe detalii despre ofertele disponibile.",
            "source_path": "/afla-mai-mult",
            "website": "",
        }
        headers = {"Accept": "application/json", "CF-Connecting-IP": "203.0.113.20"}

        for _ in range(5):
            response = self.client.post("/api/contact", data=payload, headers=headers)
            self.assertEqual(response.status_code, 200)

        response = self.client.post("/api/contact", data=payload, headers=headers)
        self.assertEqual(response.status_code, 429)
        self.assertIn("Ai trimis deja cateva mesaje recent", response.get_json()["error"])

    def test_contact_api_marks_message_notified_when_notification_succeeds(self):
        with patch.object(
            app_module,
            "_vacante_send_contact_notification",
            return_value={"status": "notified", "provider": "mock"},
        ):
            response = self.client.post(
                "/api/contact",
                data={
                    "name": "Ioana Matei",
                    "email": "ioana@example.com",
                    "message": "As vrea mai multe detalii despre varianta aceasta.",
                    "source_path": "/afla-mai-mult",
                    "website": "",
                },
                headers={"Accept": "application/json", "CF-Connecting-IP": "198.51.100.11"},
            )
        self.assertEqual(response.status_code, 200)

        conn = sqlite3.connect(str(self.db_path))
        status = conn.execute(
            "SELECT status FROM vacante_contact_messages ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
        conn.close()

        self.assertEqual(status, "notified")

    def test_contact_api_keeps_submission_when_notification_fails(self):
        with patch.object(
            app_module,
            "_vacante_send_contact_notification",
            side_effect=RuntimeError("smtp unavailable"),
        ):
            response = self.client.post(
                "/api/contact",
                data={
                    "name": "Radu Enache",
                    "email": "radu@example.com",
                    "message": "Vreau sa aflu cum functioneaza inainte sa intru pe platforma.",
                    "source_path": "/afla-mai-mult",
                    "website": "",
                },
                headers={"Accept": "application/json", "CF-Connecting-IP": "198.51.100.12"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"ok": True, "redirect": "/multumesc?contact=1"})

        conn = sqlite3.connect(str(self.db_path))
        status = conn.execute(
            "SELECT status FROM vacante_contact_messages ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
        conn.close()

        self.assertEqual(status, "notify_failed")

    def test_multumesc_page_renders_success_state(self):
        response = self.client.get("/multumesc?contact=1")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Mesajul a plecat.", html)
        self.assertIn("Deschide platforma MWR", html)


if __name__ == "__main__":
    unittest.main()
