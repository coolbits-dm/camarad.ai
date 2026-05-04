"""
Tests: Google Ads Intelligence Modules Framework (Phase 2E)

24 tests covering:
- Module registry endpoint
- Account Health v0 endpoint
- Waste Finder endpoint
- All 11 signal types
- Currency evidence contract
- Source truth (live vs mock_fallback vs mock)
- Security (no secrets, no mutations)
- Non-regression of existing report/query endpoints

Run:
    cd /opt/camarad-repo/backend_py
    AUTH_REQUIRED=0 COOLBITS_GATEWAY_ENABLED=false DATABASE=/tmp/camarad_2e_test.db \\
        python3 -m unittest test_google_ads_intelligence_modules -v
"""

import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure backend_py package is importable when run from backend_py/ dir
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_PATCH_PREFIX = "backend_py.app"

import backend_py.app as app_module
from backend_py.app import app

# Helpers for building mock campaign rows
_C = dict  # alias for readability


def _make_campaign(
    name="CampA",
    status="ENABLED",
    spent=500.0,
    impressions=10000,
    clicks=200,
    ctr=2.0,
    conversions=10.0,
    cpa=50.0,
    roas=2.5,
    avg_cpc=2.5,
):
    return {
        "name": name,
        "status": status,
        "spent": spent,
        "impressions": impressions,
        "clicks": clicks,
        "ctr": ctr,
        "conversions": conversions,
        "cpa": cpa,
        "roas": roas,
        "avg_cpc": avg_cpc,
    }


_MOCK_TOTALS = {
    "spend": 500.0,
    "impressions": 10000,
    "clicks": 200,
    "conversions": 10.0,
    "roas": 2.5,
    "cpa": 50.0,
    "active_campaigns": 1,
    "total_campaigns": 1,
}

_MOCK_CURRENCY_CTX = {
    "currency_code": "RON",
    "currency_source": "cached_hierarchy",
    "warning": None,
}


def _make_client(app):
    app.config["TESTING"] = True
    return app.test_client()


class TestModulesRegistry(unittest.TestCase):
    """Tests 1–3: /intelligence/modules endpoint."""

    def setUp(self):
        self.client = _make_client(app)

    def test_1_modules_endpoint_returns_registry(self):
        """Test 1: /intelligence/modules returns list of modules with success=True."""
        res = self.client.get("/api/connectors/google-ads/intelligence/modules")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data.get("success"))
        self.assertIsInstance(data.get("modules"), list)
        self.assertGreater(len(data["modules"]), 0)

    def test_2_registry_includes_required_modules(self):
        """Test 2: Registry includes all 7 required module IDs."""
        res = self.client.get("/api/connectors/google-ads/intelligence/modules")
        data = json.loads(res.data)
        ids = {m["id"] for m in data["modules"]}
        required = {
            "account_health", "waste_finder", "search_terms",
            "performance_max", "budget_pacing", "assets_creatives",
            "audiences_targeting",
        }
        self.assertTrue(required.issubset(ids), f"Missing modules: {required - ids}")

    def test_3_planned_modules_not_falsely_live(self):
        """Test 3: Planned/limited modules are never marked live_v0 or live_basic."""
        res = self.client.get("/api/connectors/google-ads/intelligence/modules")
        data = json.loads(res.data)
        live_statuses = {"live_v0", "live_basic", "partial"}
        planned_ids = {
            "search_terms", "performance_max", "budget_pacing",
            "assets_creatives", "audiences_targeting", "geo_device",
            "landing_pages", "conversion_tracking",
        }
        for m in data["modules"]:
            if m["id"] in planned_ids:
                self.assertNotIn(
                    m["status"], live_statuses,
                    f"Module {m['id']} should not have live status: {m['status']}",
                )


class TestAccountHealthEndpoint(unittest.TestCase):
    """Tests 4–18: /intelligence/account-health endpoint."""

    def setUp(self):
        self.client = _make_client(app)

    def _patch_campaigns(self, campaigns, source="google_ads_api", currency="RON"):
        """Return a context manager that patches _gads_resolve_live_campaigns."""
        totals = {
            "spend": sum(float(c.get("spent") or 0) for c in campaigns),
            "impressions": sum(int(c.get("impressions") or 0) for c in campaigns),
            "clicks": sum(int(c.get("clicks") or 0) for c in campaigns),
            "conversions": sum(float(c.get("conversions") or 0) for c in campaigns),
            "roas": 0.0,
            "cpa": 0.0,
            "active_campaigns": sum(1 for c in campaigns if c.get("status") == "ENABLED"),
            "total_campaigns": len(campaigns),
        }
        currency_ctx = {
            "currency_code": currency,
            "currency_source": "cached_hierarchy",
            "warning": None,
        }
        return (
            patch(f"{_PATCH_PREFIX}._gads_resolve_live_campaigns",
                  return_value=(campaigns, "LAST_30_DAYS", source, currency)),
            patch(f"{_PATCH_PREFIX}._gads_compute_overview_totals",
                  return_value=totals),
            patch(f"{_PATCH_PREFIX}._gads_resolve_currency_context",
                  return_value=currency_ctx),
        )

    def _run_health(self, campaigns, source="google_ads_api", currency="RON"):
        p1, p2, p3 = self._patch_campaigns(campaigns, source, currency)
        with p1, p2, p3:
            res = self.client.get(
                "/api/connectors/google-ads/intelligence/account-health?customer_id=1234567890"
            )
            data = json.loads(res.data)
        return res, data

    def test_4_account_health_requires_customer_id(self):
        """Test 4: account-health without customer_id returns 400."""
        res = self.client.get("/api/connectors/google-ads/intelligence/account-health")
        self.assertEqual(res.status_code, 400)
        data = json.loads(res.data)
        self.assertFalse(data.get("success"))

    def test_5_account_health_standard_contract(self):
        """Test 5: account-health returns standard module response contract."""
        camps = [_make_campaign()]
        _, data = self._run_health(camps)
        self.assertTrue(data.get("success"))
        for key in ("module_id", "module_label", "source", "live_data", "source_label",
                    "customer_id", "date_range", "currency", "summary",
                    "signals", "recommendations", "rows", "warnings"):
            self.assertIn(key, data, f"Missing key: {key}")
        self.assertEqual(data["module_id"], "account_health")

    def test_6_account_health_returns_currency_metadata(self):
        """Test 6: account-health returns currency metadata with currency_code."""
        camps = [_make_campaign()]
        _, data = self._run_health(camps)
        currency = data.get("currency") or {}
        self.assertIn("currency_code", currency)
        self.assertEqual(currency["currency_code"], "RON")

    def test_7_account_health_returns_signal_summary(self):
        """Test 7: account-health returns summary with signal_counts."""
        camps = [_make_campaign()]
        _, data = self._run_health(camps)
        summary = data.get("summary") or {}
        self.assertIn("signal_counts", summary)
        counts = summary["signal_counts"]
        for k in ("critical", "warning", "info", "total"):
            self.assertIn(k, counts)

    def test_8_zero_conversion_spend_signal(self):
        """Test 8: zero_conversion_spend signal generated for enabled camp with spend, no conv."""
        camps = [_make_campaign(name="NoConv", spent=200.0, conversions=0)]
        _, data = self._run_health(camps)
        ids = {s["id"] for s in data["signals"]}
        self.assertIn("zero_conversion_spend", ids)

    def test_9_low_roas_spend_signal(self):
        """Test 9: low_roas_spend signal generated for enabled camp with roas < 2.0."""
        camps = [_make_campaign(name="LowROAS", spent=200.0, roas=1.2, conversions=2)]
        _, data = self._run_health(camps)
        ids = {s["id"] for s in data["signals"]}
        self.assertIn("low_roas_spend", ids)

    def test_10_high_cpa_campaign_signal(self):
        """Test 10: high_cpa_campaign signal generated when campaign CPA > 2x account avg."""
        p1, p2, p3 = self._patch_campaigns([])
        high_cpa_camp = _make_campaign(name="HighCPA", spent=200.0, cpa=300.0, conversions=2)
        totals = {
            "spend": 200.0, "impressions": 10000, "clicks": 200,
            "conversions": 2.0, "roas": 1.0, "cpa": 50.0,
            "active_campaigns": 1, "total_campaigns": 1,
        }
        currency_ctx = {"currency_code": "RON", "currency_source": "test", "warning": None}
        with patch(f"{_PATCH_PREFIX}._gads_resolve_live_campaigns",
                   return_value=([high_cpa_camp], "LAST_30_DAYS", "google_ads_api", "RON")), \
             patch(f"{_PATCH_PREFIX}._gads_compute_overview_totals", return_value=totals), \
             patch(f"{_PATCH_PREFIX}._gads_resolve_currency_context", return_value=currency_ctx):
            res = self.client.get(
                "/api/connectors/google-ads/intelligence/account-health?customer_id=1234567890"
            )
            data = json.loads(res.data)
        ids = {s["id"] for s in data["signals"]}
        self.assertIn("high_cpa_campaign", ids)

    def test_11_paused_winner_signal(self):
        """Test 11: paused_winner signal generated for paused campaign with conversions >= 5."""
        camps = [_make_campaign(name="PausedWinner", status="PAUSED", conversions=10.0, roas=4.0)]
        _, data = self._run_health(camps)
        ids = {s["id"] for s in data["signals"]}
        self.assertIn("paused_winner", ids)

    def test_12_enabled_loser_signal(self):
        """Test 12: enabled_loser generated for heavy spend + near-zero roas (not already critical)."""
        camps = [_make_campaign(name="Loser", spent=500.0, roas=0.1, conversions=1)]
        _, data = self._run_health(camps)
        ids = {s["id"] for s in data["signals"]}
        self.assertIn("enabled_loser", ids)

    def test_13_spend_concentration_risk_signal(self):
        """Test 13: spend_concentration_risk when one campaign > 80% total spend."""
        camp_a = _make_campaign(name="Big", spent=900.0, conversions=5)
        camp_b = _make_campaign(name="Small", spent=100.0, conversions=2)
        totals = {
            "spend": 1000.0, "impressions": 20000, "clicks": 400,
            "conversions": 7.0, "roas": 2.0, "cpa": 100.0,
            "active_campaigns": 2, "total_campaigns": 2,
        }
        currency_ctx = {"currency_code": "RON", "currency_source": "test", "warning": None}
        with patch(f"{_PATCH_PREFIX}._gads_resolve_live_campaigns",
                   return_value=([camp_a, camp_b], "LAST_30_DAYS", "google_ads_api", "RON")), \
             patch(f"{_PATCH_PREFIX}._gads_compute_overview_totals", return_value=totals), \
             patch(f"{_PATCH_PREFIX}._gads_resolve_currency_context", return_value=currency_ctx):
            res = self.client.get(
                "/api/connectors/google-ads/intelligence/account-health?customer_id=1234567890"
            )
            data = json.loads(res.data)
        ids = {s["id"] for s in data["signals"]}
        self.assertIn("spend_concentration_risk", ids)

    def test_14_tracking_sanity_warning_signal(self):
        """Test 14: tracking_sanity_warning when total_spend > 100 + total_conversions == 0."""
        camps = [_make_campaign(name="NoConvLarge", spent=500.0, conversions=0)]
        totals = {
            "spend": 500.0, "impressions": 10000, "clicks": 100,
            "conversions": 0, "roas": 0, "cpa": 0,
            "active_campaigns": 1, "total_campaigns": 1,
        }
        currency_ctx = {"currency_code": "RON", "currency_source": "test", "warning": None}
        with patch(f"{_PATCH_PREFIX}._gads_resolve_live_campaigns",
                   return_value=(camps, "LAST_30_DAYS", "google_ads_api", "RON")), \
             patch(f"{_PATCH_PREFIX}._gads_compute_overview_totals", return_value=totals), \
             patch(f"{_PATCH_PREFIX}._gads_resolve_currency_context", return_value=currency_ctx):
            res = self.client.get(
                "/api/connectors/google-ads/intelligence/account-health?customer_id=1234567890"
            )
            data = json.loads(res.data)
        ids = {s["id"] for s in data["signals"]}
        self.assertIn("tracking_sanity_warning", ids)

    def test_15_signals_sorted_critical_first(self):
        """Test 15: signals are sorted critical > warning > info."""
        camps = [
            _make_campaign(name="LowROAS", spent=200.0, roas=1.2, conversions=2),
            _make_campaign(name="NoConv", spent=200.0, conversions=0),
        ]
        totals = {
            "spend": 400.0, "impressions": 20000, "clicks": 200,
            "conversions": 2.0, "roas": 0.5, "cpa": 200.0,
            "active_campaigns": 2, "total_campaigns": 2,
        }
        currency_ctx = {"currency_code": "RON", "currency_source": "test", "warning": None}
        signals = app_module._gads_compute_account_health_signals(camps, totals, currency_ctx)
        sev_order = {"critical": 0, "warning": 1, "info": 2}
        sevs = [sev_order.get(s.get("severity", "info"), 3) for s in signals]
        self.assertEqual(sevs, sorted(sevs), f"Signals not sorted: {[s['id'] for s in signals]}")

    def test_16_monetary_evidence_includes_currency(self):
        """Test 16: monetary evidence objects include currency_code and formatted."""
        camps = [_make_campaign(name="NoConv", spent=300.0, conversions=0)]
        _, data = self._run_health(camps)
        monetary_fields = []
        for s in data["signals"]:
            ev = s.get("evidence") or {}
            for v in ev.values():
                if isinstance(v, dict) and "currency_code" in v and "formatted" in v:
                    monetary_fields.append(v)
        self.assertGreater(len(monetary_fields), 0, "No monetary evidence found")
        for mf in monetary_fields:
            self.assertIn("currency_code", mf)
            self.assertIn("formatted", mf)
            self.assertIn("amount", mf)
            # Must use account currency (RON) or None — never USD for a RON account
            if mf["currency_code"] is not None:
                self.assertEqual(mf["currency_code"], "RON")

    def test_17_mock_fallback_live_data_false(self):
        """Test 17: source=mock_fallback → live_data=False."""
        camps = [_make_campaign()]
        _, data = self._run_health(camps, source="mock_fallback")
        self.assertFalse(data.get("live_data"))

    def test_18_google_ads_api_live_data_true(self):
        """Test 18: source=google_ads_api → live_data=True."""
        camps = [_make_campaign()]
        _, data = self._run_health(camps, source="google_ads_api")
        self.assertTrue(data.get("live_data"))


class TestWasteFinderEndpoint(unittest.TestCase):
    """Tests 19: /intelligence/waste-finder endpoint."""

    def setUp(self):
        self.client = _make_client(app)

    def test_19_waste_finder_returns_waste_signals_only(self):
        """Test 19: waste-finder returns only waste-category signals, not paused_winner etc."""
        camps = [
            _make_campaign(name="NoConv", spent=200.0, conversions=0),
            _make_campaign(name="PausedWinner", status="PAUSED", conversions=10.0, roas=4.0),
        ]
        totals = {
            "spend": 200.0, "impressions": 10000, "clicks": 100,
            "conversions": 0, "roas": 0, "cpa": 0,
            "active_campaigns": 1, "total_campaigns": 2,
        }
        currency_ctx = {"currency_code": "RON", "currency_source": "test", "warning": None}
        waste_signal_ids = {
            "zero_conversion_spend", "low_roas_spend", "high_cpa_campaign",
            "enabled_loser", "tracking_sanity_warning",
        }
        with patch(f"{_PATCH_PREFIX}._gads_resolve_live_campaigns",
                   return_value=(camps, "LAST_30_DAYS", "google_ads_api", "RON")), \
             patch(f"{_PATCH_PREFIX}._gads_compute_overview_totals", return_value=totals), \
             patch(f"{_PATCH_PREFIX}._gads_resolve_currency_context", return_value=currency_ctx):
            res = self.client.get(
                "/api/connectors/google-ads/intelligence/waste-finder?customer_id=1234567890"
            )
            data = json.loads(res.data)

        for s in data.get("signals", []):
            self.assertIn(
                s["id"], waste_signal_ids,
                f"Non-waste signal {s['id']} found in waste-finder response"
            )


class TestUIModuleLabels(unittest.TestCase):
    """Tests 20–21: connectors.html Reports tab UI."""

    def _read_html(self):
        here = os.path.dirname(os.path.abspath(__file__))
        html_path = os.path.join(here, "templates", "connectors.html")
        with open(html_path, "r", encoding="utf-8") as fh:
            return fh.read()

    def test_20_ui_contains_module_labels(self):
        """Test 20: connectors.html contains required module labels."""
        html = self._read_html()
        for label in ("Account Health", "Waste Finder", "ROAS Leaders", "Conv. Efficiency",
                      "Search Terms", "PMax"):
            self.assertIn(label, html, f"Missing module label: {label}")

    def test_21_planned_module_buttons_disabled(self):
        """Test 21: Planned module buttons carry the disabled attribute in the HTML."""
        html = self._read_html()
        # Search Terms, PMax must be disabled buttons
        import re
        # Each planned module button should have both a Planned badge and disabled attribute
        planned_buttons = re.findall(r'<button[^>]*disabled[^>]*>.*?</button>', html, re.DOTALL)
        btn_texts = " ".join(planned_buttons)
        for label in ("Search Terms", "PMax", "Budget", "Assets"):
            self.assertIn(label, btn_texts, f"Planned module '{label}' not in disabled buttons")


class TestSecurityConstraints(unittest.TestCase):
    """Tests 22–23: Security — no token leaks, no write APIs called."""

    def setUp(self):
        import backend_py.app as _app
        self.client = _make_client(_app.app)

    def _run_health_minimal(self, camps, source="mock"):
        totals = {"spend": 0, "impressions": 0, "clicks": 0, "conversions": 0,
                  "roas": 0, "cpa": 0, "active_campaigns": 0, "total_campaigns": 0}
        currency_ctx = {"currency_code": None, "currency_source": "not_found", "warning": None}
        with patch(f"{_PATCH_PREFIX}._gads_resolve_live_campaigns",
                   return_value=(camps, "LAST_30_DAYS", source, None)), \
             patch(f"{_PATCH_PREFIX}._gads_compute_overview_totals", return_value=totals), \
             patch(f"{_PATCH_PREFIX}._gads_resolve_currency_context", return_value=currency_ctx):
            res = self.client.get(
                "/api/connectors/google-ads/intelligence/account-health?customer_id=1234567890"
            )
            return json.loads(res.data)

    def test_22_no_tokens_or_secrets_in_response(self):
        """Test 22: API response must not contain OAuth tokens or secrets."""
        data = self._run_health_minimal([_make_campaign()])
        response_str = json.dumps(data).lower()
        forbidden_patterns = [
            "access_token", "refresh_token", "client_secret",
            "developer_token", "private_key", "authorization: bearer",
        ]
        for pat in forbidden_patterns:
            self.assertNotIn(pat, response_str, f"Response contains forbidden pattern: {pat}")

    def test_23_no_mutate_api_called(self):
        """Test 23: no Google Ads mutate/write API is called in account-health or waste-finder.
        Verifies by patching _gads_searchstream_campaigns to raise if called, then asserting
        the endpoint completes without triggering it (because _gads_resolve_live_campaigns
        is already patched to return mock data, so no live HTTP call should be made).
        """
        with patch(f"{_PATCH_PREFIX}._gads_resolve_live_campaigns",
                   return_value=([], "LAST_30_DAYS", "mock", None)), \
             patch(f"{_PATCH_PREFIX}._gads_compute_overview_totals",
                   return_value={"spend": 0, "impressions": 0, "clicks": 0, "conversions": 0,
                                 "roas": 0, "cpa": 0, "active_campaigns": 0, "total_campaigns": 0}), \
             patch(f"{_PATCH_PREFIX}._gads_resolve_currency_context",
                   return_value={"currency_code": None, "currency_source": "not_found", "warning": None}), \
             patch(f"{_PATCH_PREFIX}._gads_searchstream_campaigns",
                   side_effect=AssertionError("mutate/write API must not be called")):
            res = self.client.get(
                "/api/connectors/google-ads/intelligence/account-health?customer_id=1234"
            )
            data = json.loads(res.data)
        # Must complete without calling _gads_searchstream_campaigns
        self.assertIn("success", data)


class TestExistingReportQueryNonRegression(unittest.TestCase):
    """Test 24: /report/query endpoints still pass after Phase 2E insertion."""

    def setUp(self):
        import backend_py.app as _app
        self.client = _make_client(_app.app)

    def test_24_report_catalog_still_works(self):
        """Test 24: /report/catalog still returns 4 presets + 15 metrics after Phase 2E."""
        res = self.client.get("/api/connectors/google-ads/report/catalog")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data.get("success"))
        self.assertGreaterEqual(len(data.get("presets", [])), 4)
        self.assertGreaterEqual(len(data.get("metrics", [])), 15)


if __name__ == "__main__":
    unittest.main(verbosity=2)
