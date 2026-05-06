import json
import os
import re
import sys
import unittest
from unittest.mock import patch


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend_py")
for path in (BACKEND, ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)

os.environ.setdefault("AUTH_REQUIRED", "0")
os.environ.setdefault("COOLBITS_GATEWAY_ENABLED", "false")
os.environ.setdefault("DATABASE", "/tmp/camarad_ui_data_flow.db")

import backend_py.app as app_module
from backend_py.app import app


PATCH = "backend_py.app"
TEMPLATE = os.path.join(BACKEND, "templates", "connectors.html")


def _template():
    with open(TEMPLATE, "r", encoding="utf-8") as fh:
        return fh.read()


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
        labels.append(" ".join(label.split()))
    return labels


class TestGoogleAdsTemplateDataFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = _template()
        cls.gads_panel = _between(cls.html, "GOOGLE ADS RICH PANEL", "END GOOGLE ADS PANEL")
        cls.gads_tabs = _between(cls.gads_panel, 'id="gadsTabs"', "</ul>")

    def test_primary_google_ads_tabs_preserve_intelligence_and_diagnostics(self):
        self.assertEqual(
            _visible_google_ads_tab_labels(self.gads_tabs),
            [
                "Overview",
                "Campaigns",
                "Intelligence",
                "Diagnostics",
                "Reports",
                "AI Brief",
                "Settings",
            ],
        )
        self.assertIn('data-bs-target="#gadsIntelligence"', self.gads_tabs)
        self.assertIn('data-bs-target="#gadsDiagnostics"', self.gads_tabs)
        self.assertIn('data-bs-target="#gadsReports"', self.gads_tabs)
        self.assertNotIn('id="gadsDiagnosticsTab" data-bs-toggle="tab" data-bs-target="#gadsDiagnostics" type="button" title="Diagnostics legacy pane"', self.gads_tabs)

    def test_intelligence_workspace_and_reports_workspace_are_separate(self):
        intelligence = _between(
            self.gads_panel,
            '<div class="tab-pane fade" id="gadsIntelligence">',
            '<div class="tab-pane fade" id="gadsReports">',
        )
        reports = _between(
            self.gads_panel,
            '<div class="tab-pane fade" id="gadsReports">',
            '<div class="tab-pane fade" id="gadsAssets">',
        )
        self.assertIn("Google Ads Intelligence Modules", intelligence)
        self.assertIn('id="gadsModuleCards"', intelligence)
        for label in ("Account Health", "Waste Finder", "ROAS Leaders", "Conv. Efficiency", "Search Terms", "PMax"):
            self.assertIn(label, intelligence)
        self.assertIn("Google Ads Reports", reports)
        self.assertIn("Report presets", reports)
        self.assertIn('id="gadsReportsResult"', reports)
        self.assertNotIn("Google Ads Intelligence Modules", reports)

    def test_advanced_legacy_keeps_dev_tools_not_intelligence_or_diagnostics(self):
        advanced = self.gads_panel[self.gads_panel.index('id="gadsAdvancedLegacy"'):]
        self.assertIn("Advanced / Legacy", advanced)
        for label in ("Test API", "Budget Pacing", "Asset Generator"):
            self.assertIn(label, advanced)
        self.assertNotIn("Intelligence", advanced)
        self.assertNotIn("Diagnostics</button>", advanced)

    def test_central_gads_state_has_date_and_account_context(self):
        self.assertIn("let gadsState = {", self.html)
        for token in (
            "customerId: null",
            "managerCustomerId: null",
            "days: 30",
            'dateRange: "LAST_30_DAYS"',
            'activeTab: "overview"',
            "connectedLive: false",
        ):
            self.assertIn(token, self.html)

    def test_date_and_account_helpers_exist(self):
        self.assertIn("function gadsGetDateParams()", self.html)
        self.assertIn("function gadsGetAccountParams()", self.html)
        self.assertIn("function gadsDaysToDateRange(days)", self.html)
        self.assertIn("function gadsDateRangeToDays(dateRange)", self.html)

    def test_primary_date_selector_lives_in_google_ads_panel(self):
        panel_index = self.html.index('id="googleAdsPanel"')
        selector_index = self.html.index('id="gadsDateRange"')
        tabs_index = self.html.index('id="gadsTabs"')
        self.assertLess(panel_index, selector_index)
        self.assertLess(selector_index, tabs_index)
        self.assertEqual(self.html.count('id="gadsDateRange"'), 1)

    def test_date_change_handler_reloads_active_tab(self):
        self.assertIn("window.gadsOnDateRangeChange = async function(changedId)", self.html)
        handler = re.search(
            r"window\.gadsOnDateRangeChange = async function\(changedId\) \{(?P<body>.*?)\n  \};",
            self.html,
            re.S,
        ).group("body")
        self.assertIn("gadsSyncDateControls(changedId)", handler)
        self.assertIn("gadsClearGoogleAdsOutputs()", handler)
        self.assertIn("gadsReloadActiveTab()", handler)

    def test_overview_loader_uses_customer_mcc_and_days(self):
        body = re.search(r"async function gadsLoadOverview\(\) \{(?P<body>.*?)\n  \}", self.html, re.S).group("body")
        self.assertIn("gadsRequireSelectedAccount('gadsOverviewContent')", body)
        self.assertIn("customer_id=${encodeURIComponent(accountId)}", body)
        self.assertIn("days=${days}", body)
        self.assertIn("date_range=${encodeURIComponent(dateRange)}", body)
        self.assertIn("${mccQs}", body)

    def test_campaigns_loader_uses_customer_mcc_and_days(self):
        body = re.search(r"async function gadsLoadCampaigns\(\) \{(?P<body>.*?)\n  \}", self.html, re.S).group("body")
        self.assertIn("gadsGetAccountParams()", body)
        self.assertIn("customer_id=${encodeURIComponent(accountId)}", body)
        self.assertIn("account_id=${encodeURIComponent(accountId)}", body)
        self.assertIn("days=${days}", body)
        self.assertIn("date_range=${encodeURIComponent(dateRange)}", body)
        self.assertIn("${mccQs}", body)

    def test_intelligence_module_calls_use_context(self):
        body = re.search(r"async function gadsOpenModule\(moduleId\) \{(?P<body>.*?)\n  \}", self.html, re.S).group("body")
        self.assertIn("'account_health': '/api/connectors/google-ads/intelligence/account-health'", body)
        self.assertIn("'waste_finder':   '/api/connectors/google-ads/intelligence/waste-finder'", body)
        self.assertIn("'search_terms':   '/api/connectors/google-ads/intelligence/search-terms'", body)
        self.assertIn("customer_id=${encodeURIComponent(accountId)}", body)
        self.assertIn("days=${days}", body)
        self.assertIn("date_range=${encodeURIComponent(dateRange)}", body)
        self.assertIn("${mccQs}", body)

    def test_report_query_uses_date_range_from_helper(self):
        body = re.search(r"async function gadsRunPreset\([^)]*\) \{(?P<body>.*?)\n  \}", self.html, re.S).group("body")
        self.assertIn("const { accountId, mccId, dateRange } = _gadsQs();", body)
        self.assertIn("date_range: dateRange", body)
        self.assertIn("manager_customer_id: mccId || undefined", body)

    def test_ai_brief_uses_customer_mcc_and_days(self):
        body = re.search(r"async function gadsLoadAiBrief\(\) \{(?P<body>.*?)\n  \}", self.html, re.S).group("body")
        self.assertIn("gadsRequireSelectedAccount('gadsAiBriefContent')", body)
        self.assertIn("customer_id=${encodeURIComponent(accountId)}", body)
        self.assertIn("days=${days}", body)
        self.assertIn("date_range=${encodeURIComponent(dateRange)}", body)
        self.assertIn("${mccQs}", body)

    def test_source_and_meta_renderer_cover_expected_labels(self):
        self.assertIn("function gadsSourceBadge(source)", self.html)
        for label in ("Live", "Cached Google Ads", "API Error / Fallback", "API Error", "Mock"):
            self.assertIn(label, self.html)
        self.assertIn("function gadsRenderDataMeta(container, response)", self.html)
        self.assertIn("date_range", self.html)
        self.assertIn("gadsCurrencyBadge(currency)", self.html)

    def test_loaders_require_selected_account_before_data_calls(self):
        for fn_name, marker in (
            ("gadsLoadOverview", "gadsRequireSelectedAccount('gadsOverviewContent')"),
            ("gadsLoadCampaigns", "gadsGetAccountParams()"),
            ("gadsLoadDiagnostics", "gadsRequireSelectedAccount('gadsDiagnosticsContent')"),
            ("gadsLoadAiBrief", "gadsRequireSelectedAccount('gadsAiBriefContent')"),
            ("gadsOpenModule", "gadsRequireSelectedAccount('gadsReportResult')"),
            ("gadsRunPreset", "gadsRequireSelectedAccount(targetId)"),
        ):
            body = re.search(rf"async function {fn_name}\([^)]*\) \{{(?P<body>.*?)\n  \}}", self.html, re.S).group("body")
            self.assertIn(marker, body)


class TestGoogleAdsBackendDateEcho(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_campaigns_echoes_requested_days_and_date_range(self):
        with patch(f"{PATCH}._gads_token_get_meta", return_value=None), \
             patch(f"{PATCH}._google_ads_gateway_fetch", return_value=(None, {"enabled": False})):
            res = self.client.get(
                "/api/connectors/google-ads/campaigns?customer_id=1325845765&days=7"
            )
        data = json.loads(res.data)
        self.assertEqual(data.get("days"), 7)
        self.assertEqual(data.get("date_range"), "LAST_7_DAYS")

    def test_overview_echoes_requested_days(self):
        with patch(f"{PATCH}._gads_token_get_meta", return_value={}), \
             patch(f"{PATCH}._gads_resolve_live_campaigns", return_value=(
                 [], "LAST_14_DAYS", "mock", None
             )), \
             patch(f"{PATCH}._gads_resolve_currency_context", return_value={}):
            res = self.client.get(
                "/api/connectors/google-ads/overview?customer_id=1325845765&days=14"
            )
        data = json.loads(res.data)
        self.assertEqual(data.get("days"), 14)
        self.assertEqual(data.get("date_range"), "LAST_14_DAYS")

    def test_account_health_echoes_requested_days(self):
        with patch(f"{PATCH}._gads_token_get_meta", return_value={}), \
             patch(f"{PATCH}._gads_resolve_live_campaigns", return_value=(
                 [], "LAST_90_DAYS", "mock", None
             )), \
             patch(f"{PATCH}._gads_resolve_currency_context", return_value={}):
            res = self.client.get(
                "/api/connectors/google-ads/intelligence/account-health"
                "?customer_id=1325845765&days=90"
            )
        data = json.loads(res.data)
        self.assertEqual(data.get("days"), 90)
        self.assertEqual(data.get("date_range"), "LAST_90_DAYS")

    def test_waste_finder_echoes_requested_days(self):
        with patch(f"{PATCH}._gads_token_get_meta", return_value={}), \
             patch(f"{PATCH}._gads_resolve_live_campaigns", return_value=(
                 [], "LAST_7_DAYS", "mock", None
             )), \
             patch(f"{PATCH}._gads_resolve_currency_context", return_value={}):
            res = self.client.get(
                "/api/connectors/google-ads/intelligence/waste-finder"
                "?customer_id=1325845765&days=7"
            )
        data = json.loads(res.data)
        self.assertEqual(data.get("days"), 7)
        self.assertEqual(data.get("date_range"), "LAST_7_DAYS")

    def test_search_terms_echoes_requested_days_and_no_secret_fields(self):
        with patch(f"{PATCH}._gads_token_get_meta", return_value={}), \
             patch(f"{PATCH}._gads_resolve_live_search_terms", return_value=(
                 [], "LAST_14_DAYS", "mock", None
             )), \
             patch(f"{PATCH}._gads_resolve_live_campaigns", return_value=(
                 [], "LAST_14_DAYS", "mock", None
             )), \
             patch(f"{PATCH}._gads_resolve_currency_context", return_value={}):
            res = self.client.get(
                "/api/connectors/google-ads/intelligence/search-terms"
                "?customer_id=1325845765&days=14"
            )
        data = json.loads(res.data)
        self.assertEqual(data.get("days"), 14)
        self.assertEqual(data.get("date_range"), "LAST_14_DAYS")
        text = res.data.decode()
        for forbidden in (
            "access" + "_token",
            "refresh" + "_token",
            "developer" + "_token",
            "client" + "_secret",
        ):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
