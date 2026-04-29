import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app


class TestMwrLanding(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_mwr_landing_renders_expected_sections_and_links(self):
        response = self.client.get("/mwr")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Calatoreste mai bine, cu mai multa claritate si mai putin efort", html)
        self.assertIn("Creezi cont", html)
        self.assertIn("Acceseaza platforma", html)
        self.assertIn("Descopera platforma", html)
        self.assertIn('href="https://example.com/mwr"', html)
        self.assertIn('target="_blank"', html)
        self.assertIn('href="/mwr/privacy"', html)
        self.assertIn('href="/mwr/terms"', html)
        self.assertIn("Rezultatele pot varia in functie de utilizare.", html)

    def test_mwr_support_pages_and_sitemap_are_live(self):
        self.assertEqual(self.client.get("/mwr/privacy").status_code, 200)
        self.assertEqual(self.client.get("/mwr/terms").status_code, 200)
        sitemap = self.client.get("/sitemap.xml")
        self.assertEqual(sitemap.status_code, 200)
        self.assertIn("/mwr</loc>", sitemap.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
