import html
import re
import unittest
from pathlib import Path


TEMPLATE = Path(__file__).with_name("templates") / "connectors.html"


def _read_template():
    return TEMPLATE.read_text(encoding="utf-8")


def _between(text, start, end):
    start_idx = text.index(start)
    end_idx = text.index(end, start_idx)
    return text[start_idx:end_idx]


def _visible_google_ads_tab_labels(tab_html):
    labels = []
    for item in re.findall(r'<li class="nav-item">(.*?)</li>', tab_html, flags=re.S):
        match = re.search(r"<button\b[^>]*>(.*?)</button>", item, flags=re.S)
        if not match:
            continue
        label = re.sub(r"<[^>]+>", " ", match.group(1))
        labels.append(" ".join(html.unescape(label).split()))
    return labels


class GoogleAdsUiSimplificationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read_template()
        cls.gads_panel = _between(cls.text, "GOOGLE ADS RICH PANEL", "END GOOGLE ADS PANEL")
        cls.gads_tabs = _between(cls.gads_panel, 'id="gadsTabs"', "</ul>")
        cls.gads_js = _between(cls.text, "  // GOOGLE ADS: Full Mock Connector Engine", "  // GA4:")

    def test_primary_tabs_preserve_google_ads_workspaces(self):
        self.assertEqual(
            _visible_google_ads_tab_labels(self.gads_tabs),
            ["Overview", "Campaigns", "Intelligence", "Diagnostics", "Reports", "AI Brief", "Settings"],
        )

    def test_diagnostics_and_intelligence_are_primary_tabs(self):
        visible_labels = _visible_google_ads_tab_labels(self.gads_tabs)
        self.assertIn("Intelligence", visible_labels)
        self.assertIn("Diagnostics", visible_labels)
        self.assertIn('data-bs-target="#gadsIntelligence"', self.gads_tabs)
        self.assertIn('data-bs-target="#gadsDiagnostics"', self.gads_tabs)
        self.assertIn('id="gadsDiagnosticsTab"', self.gads_tabs)
        self.assertNotIn('title="Diagnostics legacy pane"', self.gads_tabs)

    def test_advanced_legacy_section_contains_dev_tools(self):
        self.assertIn('id="gadsAdvancedLegacy"', self.gads_panel)
        self.assertIn("Advanced / Legacy", self.gads_panel)
        for label in ("Test API", "Budget Pacing", "Asset Generator"):
            self.assertIn(label, self.gads_panel)
        advanced = self.gads_panel[self.gads_panel.index('id="gadsAdvancedLegacy"'):]
        self.assertNotIn("Diagnostics</button>", advanced)
        self.assertNotIn("Intelligence</button>", advanced)

    def test_source_badge_labels_are_normalized(self):
        self.assertIn("function gadsSourceBadge(source)", self.gads_js)
        for label in ("Live", "API Error / Fallback", "Mock", "Planned"):
            self.assertIn(label, self.gads_js)

    def test_currency_badge_and_money_formatting_do_not_default_to_usd(self):
        self.assertIn("function gadsCurrencyBadge(currency)", self.gads_js)
        for label in ("Native:", "Currency unknown", "Conversion unavailable"):
            self.assertIn(label, self.gads_js)
        old_usd_patterns = [
            "fmtNum(ps.spend, '$')",
            "fmtNum(ps.cpa, '$')",
            "fmtNum(ps.avg_cpc, '$')",
            "fmtNum(t.spend, '$')",
            "fmtNum(t.cpa, '$')",
            "fmtNum(t.avg_cpc, '$')",
            "$${",
            "'$' +",
            '"$" +',
            "+ '$'",
            '+ "$"',
        ]
        for pattern in old_usd_patterns:
            self.assertNotIn(pattern, self.gads_js)

    def test_planned_modules_are_compact_and_disabled(self):
        self.assertIn("Coming next", self.gads_panel)
        planned_labels = ("PMax", "Budget", "Assets", "Audiences")
        for label in planned_labels:
            pattern = re.compile(rf"<button[^>]*disabled[^>]*>.*?{re.escape(label)}.*?</button>", re.S)
            self.assertRegex(self.gads_panel, pattern)
        self.assertGreaterEqual(self.gads_panel.count("Planned"), 3)

    def test_report_module_cards_are_still_available(self):
        for label in ("Account Health", "Waste Finder", "ROAS Leaders", "Conv. Efficiency", "Search Terms"):
            self.assertIn(label, self.gads_panel)
        self.assertIn("Google Ads Intelligence Modules", self.gads_panel)
        self.assertIn("Google Ads Reports", self.gads_panel)

    def test_test_api_is_not_primary_tab(self):
        visible_labels = _visible_google_ads_tab_labels(self.gads_tabs)
        self.assertNotIn("Test API", visible_labels)
        self.assertIn("gadsOpenAdvancedPane('gadsApiTestTab')", self.gads_panel)

    def test_account_selector_copy_is_compact_but_preserved(self):
        expected_copy = (
            "Direct Access",
            "OAuth-visible accounts",
            "Manager/MCC",
            "Manager context",
            "Client Account",
            "Reporting account",
        )
        for text in expected_copy:
            self.assertIn(text, self.gads_panel)

    def test_no_google_ads_mutation_ui_was_introduced(self):
        lowered = (self.gads_panel + self.gads_js).lower()
        forbidden = (
            "googleads:mutate",
            "/mutate",
            "apply negative",
            "publish negative",
            "create negative keyword",
        )
        for pattern in forbidden:
            self.assertNotIn(pattern, lowered)
        self.assertIn("no automatic changes applied", lowered)


if __name__ == "__main__":
    unittest.main()
