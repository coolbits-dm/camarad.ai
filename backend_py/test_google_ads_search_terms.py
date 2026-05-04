"""
test_google_ads_search_terms.py — Phase 2E.2: Search Terms Intelligence

Run from repo root:
    cd backend_py && AUTH_REQUIRED=0 COOLBITS_GATEWAY_ENABLED=false DATABASE=/tmp/test_gads_st.db \
        python3 -m unittest test_google_ads_search_terms -v

All patch targets use _PATCH_PREFIX = "backend_py.app".
No real Google Ads API calls are made.
No negative keyword mutations are tested (none exist).
"""

import sys
import os
import json
import unittest
from unittest.mock import patch, MagicMock

# Allow running from repo root or from backend_py/
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_THIS_DIR)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ.setdefault("AUTH_REQUIRED", "0")
os.environ.setdefault("COOLBITS_GATEWAY_ENABLED", "false")
os.environ.setdefault("DATABASE", "/tmp/test_gads_st.db")

import backend_py.app as app_module

_PATCH_PREFIX = "backend_py.app"

_SAMPLE_ROWS_LIVE = [
    {
        "search_term": "free running shoes",
        "campaign_id": "1001",
        "campaign_name": "Brand Search",
        "campaign_status": "ENABLED",
        "ad_group_id": "2001",
        "ad_group_name": "Brand Keywords",
        "impressions": 320,
        "clicks": 28,
        "cost": 18.50,
        "conversions": 0.0,
        "conversion_value": 0.0,
        "ctr": 8.75,
        "avg_cpc": 0.66,
        "cpa": None,
        "roas": None,
        "conversion_rate": None,
        "currency_code": "RON",
        "targeting_status": "NONE",
        "classification": None,
        "reason": "",
    },
    {
        "search_term": "best running shoes men",
        "campaign_id": "1002",
        "campaign_name": "Performance Search",
        "campaign_status": "ENABLED",
        "ad_group_id": "2002",
        "ad_group_name": "Running Shoes",
        "impressions": 1200,
        "clicks": 95,
        "cost": 67.50,
        "conversions": 8.0,
        "conversion_value": 640.0,
        "ctr": 7.92,
        "avg_cpc": 0.71,
        "cpa": 8.44,
        "roas": 9.48,
        "conversion_rate": 8.42,
        "currency_code": "RON",
        "targeting_status": "NONE",
        "classification": None,
        "reason": "",
    },
    {
        "search_term": "trail running shoes waterproof",
        "campaign_id": "1002",
        "campaign_name": "Performance Search",
        "campaign_status": "ENABLED",
        "ad_group_id": "2003",
        "ad_group_name": "Trail Running",
        "impressions": 450,
        "clicks": 35,
        "cost": 4.20,
        "conversions": 0.0,
        "conversion_value": 0.0,
        "ctr": 7.78,
        "avg_cpc": 0.12,
        "cpa": None,
        "roas": None,
        "conversion_rate": None,
        "currency_code": "RON",
        "targeting_status": "NONE",
        "classification": None,
        "reason": "",
    },
    {
        "search_term": "athletic footwear",
        "campaign_id": "1003",
        "campaign_name": "Generic Search",
        "campaign_status": "ENABLED",
        "ad_group_id": "2004",
        "ad_group_name": "Generic",
        "impressions": 2400,
        "clicks": 9,
        "cost": 3.60,
        "conversions": 0.0,
        "conversion_value": 0.0,
        "ctr": 0.38,
        "avg_cpc": 0.40,
        "cpa": None,
        "roas": None,
        "conversion_rate": None,
        "currency_code": "RON",
        "targeting_status": "NONE",
        "classification": None,
        "reason": "",
    },
]

_SAMPLE_CURRENCY_CTX = {
    "currency_code": "RON",
    "currency_source": "api",
    "conversion_applied": False,
    "warning": None,
}

_EMPTY_CURRENCY_CTX = {
    "currency_code": None,
    "currency_source": "unknown",
    "conversion_applied": False,
    "warning": None,
}


class TestModuleRegistrySearchTerms(unittest.TestCase):
    """1. Registry marks search_terms as partial_live."""

    def test_registry_marks_search_terms_partial_live(self):
        registry = app_module._gads_intelligence_module_registry()
        st = next((m for m in registry if m["id"] == "search_terms"), None)
        self.assertIsNotNone(st, "search_terms not found in registry")
        self.assertEqual(st["status"], "partial_live",
                         f"Expected partial_live, got {st['status']}")

    def test_registry_search_terms_has_endpoint(self):
        registry = app_module._gads_intelligence_module_registry()
        st = next((m for m in registry if m["id"] == "search_terms"), None)
        self.assertIsNotNone(st)
        self.assertIsNotNone(st.get("endpoint"),
                             "search_terms endpoint should not be None for partial_live")
        self.assertIn("search-terms", str(st["endpoint"]))

    def test_registry_pmax_still_planned(self):
        """PMax module remains planned — not promoted yet."""
        registry = app_module._gads_intelligence_module_registry()
        pmax = next((m for m in registry if m["id"] == "performance_max"), None)
        self.assertIsNotNone(pmax)
        self.assertEqual(pmax["status"], "planned")


class TestSearchTermsEndpoint(unittest.TestCase):
    """2–12. Endpoint behavior, source truth, security."""

    def setUp(self):
        app_module.app.config["TESTING"] = True
        self.client = app_module.app.test_client()

    # 2. customer_id required
    def test_endpoint_requires_customer_id(self):
        resp = self.client.get("/api/connectors/google-ads/intelligence/search-terms")
        self.assertEqual(resp.status_code, 400)
        body = resp.get_json()
        self.assertFalse(body.get("success"))
        self.assertEqual(body.get("error"), "customer_id_required")

    # 3. Standard module response contract
    @patch(f"{_PATCH_PREFIX}._gads_resolve_live_search_terms")
    @patch(f"{_PATCH_PREFIX}._gads_resolve_live_campaigns")
    @patch(f"{_PATCH_PREFIX}._gads_resolve_currency_context")
    @patch(f"{_PATCH_PREFIX}.get_current_user_id", return_value=0)
    @patch(f"{_PATCH_PREFIX}._gads_token_get_meta", return_value=None)
    def test_endpoint_returns_standard_module_response(
        self, mock_meta, mock_uid, mock_currency, mock_campaigns, mock_search_terms
    ):
        mock_search_terms.return_value = (
            list(_SAMPLE_ROWS_LIVE), "LAST_30_DAYS", "mock", "RON"
        )
        mock_campaigns.return_value = ([], "LAST_30_DAYS", "mock", None)
        mock_currency.return_value = _SAMPLE_CURRENCY_CTX

        resp = self.client.get(
            "/api/connectors/google-ads/intelligence/search-terms?customer_id=1234567890"
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertTrue(body.get("success"))
        self.assertEqual(body.get("module_id"), "search_terms")
        self.assertEqual(body.get("module_label"), "Search Terms")
        self.assertIn("source", body)
        self.assertIn("live_data", body)
        self.assertIn("customer_id", body)
        self.assertIn("date_range", body)
        self.assertIn("currency", body)
        self.assertIn("summary", body)
        self.assertIn("signals", body)
        self.assertIn("recommendations", body)
        self.assertIn("rows", body)
        self.assertIn("warnings", body)
        # Summary fields
        summary = body["summary"]
        for key in ("terms_count", "waste_terms_count", "winner_terms_count",
                    "opportunity_terms_count", "total_cost", "total_conversions"):
            self.assertIn(key, summary, f"summary missing key: {key}")

    # 4. Row normalization — cost/cpa/roas
    def test_row_normalization_cost_cpa_roas(self):
        """_gads_classify_search_term derives cpa/roas correctly from pre-normalized rows."""
        row = {
            "cost": 50.0, "conversions": 5.0, "conversion_value": 300.0,
            "clicks": 40, "impressions": 500, "ctr": 8.0, "roas": 6.0, "cpa": 10.0,
        }
        cls, reason = app_module._gads_classify_search_term(row)
        self.assertEqual(cls, "winner")
        self.assertIn("ROAS", reason)

    def test_row_normalization_zero_div_safe(self):
        """classify handles zero conversions safely."""
        row = {
            "cost": 100.0, "conversions": 0.0, "conversion_value": 0.0,
            "clicks": 50, "impressions": 400, "ctr": 12.5, "roas": None, "cpa": None,
        }
        cls, _ = app_module._gads_classify_search_term(row)
        self.assertEqual(cls, "waste")

    # 5. waste_search_terms signal
    def test_waste_signal_generated(self):
        rows = [
            {"cost": 20.0, "conversions": 0.0, "conversion_value": 0.0,
             "clicks": 10, "impressions": 100, "ctr": 5.0,
             "search_term": "cheap free stuff", "classification": "waste",
             "roas": None, "cpa": None, "reason": "Spend with zero conversions"},
        ]
        signals = app_module._gads_compute_search_term_signals(rows, _SAMPLE_CURRENCY_CTX)
        ids = [s["id"] for s in signals]
        self.assertIn("waste_search_terms", ids)
        waste_sig = next(s for s in signals if s["id"] == "waste_search_terms")
        self.assertEqual(waste_sig["severity"], "warning")
        self.assertIn("conversions", waste_sig["recommendation"].lower())

    # 6. winner_search_terms signal
    def test_winner_signal_generated(self):
        rows = [
            {"cost": 50.0, "conversions": 5.0, "conversion_value": 400.0,
             "clicks": 40, "impressions": 500, "ctr": 8.0,
             "search_term": "buy running shoes online", "classification": "winner",
             "roas": 8.0, "cpa": 10.0, "reason": "Good ROAS (8.00x)"},
        ]
        signals = app_module._gads_compute_search_term_signals(rows, _SAMPLE_CURRENCY_CTX)
        ids = [s["id"] for s in signals]
        self.assertIn("winner_search_terms", ids)
        winner_sig = next(s for s in signals if s["id"] == "winner_search_terms")
        self.assertEqual(winner_sig["severity"], "info")

    # 7. high_ctr_no_conversion signal
    def test_high_ctr_no_conversion_signal(self):
        rows = [
            {"cost": 2.50, "conversions": 0.0, "conversion_value": 0.0,
             "clicks": 15, "impressions": 150, "ctr": 10.0,
             "search_term": "trail waterproof shoes explore", "classification": "opportunity",
             "roas": None, "cpa": None, "reason": "High CTR, no conversions yet"},
        ]
        signals = app_module._gads_compute_search_term_signals(rows, _SAMPLE_CURRENCY_CTX)
        ids = [s["id"] for s in signals]
        self.assertIn("high_ctr_no_conversion_terms", ids)
        s = next(sig for sig in signals if sig["id"] == "high_ctr_no_conversion_terms")
        self.assertEqual(s["severity"], "warning")

    # 8. low_ctr_high_impression signal
    def test_low_ctr_high_impression_signal(self):
        rows = [
            {"cost": 1.80, "conversions": 0.0, "conversion_value": 0.0,
             "clicks": 5, "impressions": 1500, "ctr": 0.33,
             "search_term": "athletic footwear", "classification": "opportunity",
             "roas": None, "cpa": None, "reason": "High impressions, low CTR"},
        ]
        signals = app_module._gads_compute_search_term_signals(rows, _SAMPLE_CURRENCY_CTX)
        ids = [s["id"] for s in signals]
        self.assertIn("low_ctr_high_impression_terms", ids)
        s = next(sig for sig in signals if sig["id"] == "low_ctr_high_impression_terms")
        self.assertEqual(s["severity"], "warning")

    # 9. Monetary evidence includes currency_code
    def test_monetary_values_include_currency_code(self):
        rows = [
            {"cost": 50.0, "conversions": 0.0, "conversion_value": 0.0,
             "clicks": 30, "impressions": 300, "ctr": 10.0,
             "search_term": "waste term", "classification": "waste",
             "roas": None, "cpa": None, "reason": "Spend with zero conversions"},
        ]
        signals = app_module._gads_compute_search_term_signals(rows, _SAMPLE_CURRENCY_CTX)
        waste_sig = next(
            (s for s in signals if s["id"] == "waste_search_terms"), None
        )
        self.assertIsNotNone(waste_sig)
        ev = waste_sig.get("evidence") or {}
        cost_ev = ev.get("total_waste_cost") or {}
        self.assertEqual(cost_ev.get("currency_code"), "RON")

    # 10. live source → live_data = True
    @patch(f"{_PATCH_PREFIX}._gads_resolve_live_search_terms")
    @patch(f"{_PATCH_PREFIX}._gads_resolve_live_campaigns")
    @patch(f"{_PATCH_PREFIX}._gads_resolve_currency_context")
    @patch(f"{_PATCH_PREFIX}.get_current_user_id", return_value=0)
    @patch(f"{_PATCH_PREFIX}._gads_token_get_meta", return_value=None)
    def test_live_source_gives_live_data_true(
        self, mock_meta, mock_uid, mock_currency, mock_campaigns, mock_search_terms
    ):
        mock_search_terms.return_value = ([], "LAST_30_DAYS", "google_ads_api", "RON")
        mock_campaigns.return_value = ([], "LAST_30_DAYS", "google_ads_api", "RON")
        mock_currency.return_value = _SAMPLE_CURRENCY_CTX

        resp = self.client.get(
            "/api/connectors/google-ads/intelligence/search-terms?customer_id=1234567890"
        )
        body = resp.get_json()
        self.assertTrue(body.get("live_data"))
        self.assertEqual(body.get("source"), "google_ads_api")

    # 11. mock_fallback → live_data = False + warning
    @patch(f"{_PATCH_PREFIX}._gads_resolve_live_search_terms")
    @patch(f"{_PATCH_PREFIX}._gads_resolve_live_campaigns")
    @patch(f"{_PATCH_PREFIX}._gads_resolve_currency_context")
    @patch(f"{_PATCH_PREFIX}.get_current_user_id", return_value=0)
    @patch(f"{_PATCH_PREFIX}._gads_token_get_meta", return_value=None)
    def test_mock_fallback_gives_live_data_false_and_warning(
        self, mock_meta, mock_uid, mock_currency, mock_campaigns, mock_search_terms
    ):
        mock_search_terms.return_value = ([], "LAST_30_DAYS", "mock_fallback", None)
        mock_campaigns.return_value = ([], "LAST_30_DAYS", "mock_fallback", None)
        mock_currency.return_value = _EMPTY_CURRENCY_CTX

        resp = self.client.get(
            "/api/connectors/google-ads/intelligence/search-terms?customer_id=1234567890"
        )
        body = resp.get_json()
        self.assertFalse(body.get("live_data"))
        self.assertEqual(body.get("source"), "mock_fallback")
        warnings = body.get("warnings") or []
        self.assertTrue(any("API call failed" in w or "fallback" in w.lower() for w in warnings),
                        f"Expected fallback warning, got: {warnings}")

    # 12. PMax gap warning present
    @patch(f"{_PATCH_PREFIX}._gads_resolve_live_search_terms")
    @patch(f"{_PATCH_PREFIX}._gads_resolve_live_campaigns")
    @patch(f"{_PATCH_PREFIX}._gads_resolve_currency_context")
    @patch(f"{_PATCH_PREFIX}.get_current_user_id", return_value=0)
    @patch(f"{_PATCH_PREFIX}._gads_token_get_meta", return_value=None)
    def test_pmax_gap_warning_present_when_has_pmax(
        self, mock_meta, mock_uid, mock_currency, mock_campaigns, mock_search_terms
    ):
        mock_search_terms.return_value = ([], "LAST_30_DAYS", "mock", None)
        # Simulate account with a PMax campaign
        mock_campaigns.return_value = (
            [{"name": "PMax - Main", "channel": "Performance Max", "status": "ENABLED",
              "spent": 100, "conversions": 0, "roas": 0, "cpa": 0,
              "impressions": 0, "ctr": 0, "avg_cpc": 0, "campaign_type": "PERFORMANCE_MAX"}],
            "LAST_30_DAYS", "mock", None
        )
        mock_currency.return_value = _EMPTY_CURRENCY_CTX

        resp = self.client.get(
            "/api/connectors/google-ads/intelligence/search-terms?customer_id=1234567890"
        )
        body = resp.get_json()
        warnings = body.get("warnings") or []
        signals = body.get("signals") or []
        signal_ids = [s["id"] for s in signals]
        # Either a pmax_gap_notice signal or a warning about PMax
        has_pmax_signal = "pmax_gap_notice" in signal_ids
        has_pmax_warning = any("Performance Max" in w or "PMax" in w for w in warnings)
        self.assertTrue(has_pmax_signal or has_pmax_warning,
                        f"Expected PMax gap notice. signals={signal_ids}, warnings={warnings}")

    # 13. No secret leak in response
    @patch(f"{_PATCH_PREFIX}._gads_resolve_live_search_terms")
    @patch(f"{_PATCH_PREFIX}._gads_resolve_live_campaigns")
    @patch(f"{_PATCH_PREFIX}._gads_resolve_currency_context")
    @patch(f"{_PATCH_PREFIX}.get_current_user_id", return_value=0)
    @patch(f"{_PATCH_PREFIX}._gads_token_get_meta", return_value=None)
    def test_no_secret_leak(
        self, mock_meta, mock_uid, mock_currency, mock_campaigns, mock_search_terms
    ):
        mock_search_terms.return_value = (
            list(_SAMPLE_ROWS_LIVE), "LAST_30_DAYS", "mock", "RON"
        )
        mock_campaigns.return_value = ([], "LAST_30_DAYS", "mock", None)
        mock_currency.return_value = _SAMPLE_CURRENCY_CTX

        resp = self.client.get(
            "/api/connectors/google-ads/intelligence/search-terms?customer_id=1234567890"
        )
        raw = resp.data.decode("utf-8").lower()
        for secret_key in (
            "access_token", "refresh_token", "client_secret",
            "developer_token", "private_key", "bearer",
        ):
            self.assertNotIn(secret_key, raw,
                             f"Secret key '{secret_key}' found in response body")

    # 14. No mutate/write API called
    @patch(f"{_PATCH_PREFIX}._gads_resolve_live_search_terms")
    @patch(f"{_PATCH_PREFIX}._gads_resolve_live_campaigns")
    @patch(f"{_PATCH_PREFIX}._gads_resolve_currency_context")
    @patch(f"{_PATCH_PREFIX}.get_current_user_id", return_value=0)
    @patch(f"{_PATCH_PREFIX}._gads_token_get_meta", return_value=None)
    @patch(f"{_PATCH_PREFIX}.requests")
    def test_no_mutate_api_called(
        self, mock_requests, mock_meta, mock_uid, mock_currency, mock_campaigns, mock_search_terms
    ):
        mock_search_terms.return_value = ([], "LAST_30_DAYS", "mock", None)
        mock_campaigns.return_value = ([], "LAST_30_DAYS", "mock", None)
        mock_currency.return_value = _EMPTY_CURRENCY_CTX

        self.client.get(
            "/api/connectors/google-ads/intelligence/search-terms?customer_id=1234567890"
        )
        # Verify no call to googleAds:mutate
        for call in mock_requests.post.call_args_list:
            url = str(call[0][0] if call[0] else "")
            self.assertNotIn("mutate", url.lower(),
                             f"Mutate API was called: {url}")


class TestSearchTermRowClassification(unittest.TestCase):
    """Row classification unit tests."""

    def test_classify_waste_high_cost_zero_conv(self):
        row = {"cost": 10.0, "conversions": 0.0, "clicks": 20,
               "impressions": 200, "ctr": 10.0, "roas": None, "cpa": None}
        cls, reason = app_module._gads_classify_search_term(row, waste_cost_threshold=5.0)
        self.assertEqual(cls, "waste")

    def test_classify_winner_good_roas(self):
        row = {"cost": 30.0, "conversions": 3.0, "clicks": 25,
               "impressions": 300, "ctr": 8.3, "roas": 6.5, "cpa": 10.0}
        cls, reason = app_module._gads_classify_search_term(row)
        self.assertEqual(cls, "winner")
        self.assertIn("ROAS", reason)

    def test_classify_opportunity_high_ctr(self):
        row = {"cost": 1.20, "conversions": 0.0, "clicks": 12,
               "impressions": 80, "ctr": 15.0, "roas": None, "cpa": None}
        cls, reason = app_module._gads_classify_search_term(row, waste_cost_threshold=5.0)
        self.assertEqual(cls, "opportunity")
        self.assertIn("CTR", reason)

    def test_classify_opportunity_low_ctr_high_imp(self):
        row = {"cost": 0.80, "conversions": 0.0, "clicks": 3,
               "impressions": 600, "ctr": 0.30, "roas": None, "cpa": None}
        cls, reason = app_module._gads_classify_search_term(row, waste_cost_threshold=5.0)
        self.assertEqual(cls, "opportunity")
        self.assertIn("impressions", reason.lower())

    def test_classify_neutral(self):
        row = {"cost": 2.50, "conversions": 0.0, "clicks": 5,
               "impressions": 50, "ctr": 10.0, "roas": None, "cpa": None}
        cls, _ = app_module._gads_classify_search_term(row, waste_cost_threshold=5.0)
        # cost=2.50 < 5.0 threshold → not waste; clicks=5 < 10 → not opportunity
        self.assertEqual(cls, "neutral")

    def test_classify_winner_multiple_conversions(self):
        row = {"cost": 20.0, "conversions": 2.0, "clicks": 15,
               "impressions": 100, "ctr": 5.0, "roas": 1.5, "cpa": 10.0}
        cls, reason = app_module._gads_classify_search_term(row)
        self.assertEqual(cls, "winner")
        # roas < 3.0 but conversions >= 2 → "Multiple conversions"
        self.assertIn("conversion", reason.lower())


class TestSearchTermSignalDetails(unittest.TestCase):
    """Signal edge-case tests."""

    def test_pmax_gap_signal_when_has_pmax_true(self):
        signals = app_module._gads_compute_search_term_signals([], _SAMPLE_CURRENCY_CTX,
                                                                has_pmax=True)
        ids = [s["id"] for s in signals]
        self.assertIn("pmax_gap_notice", ids)
        pmax_sig = next(s for s in signals if s["id"] == "pmax_gap_notice")
        self.assertEqual(pmax_sig["severity"], "info")
        self.assertIn("Performance Max", pmax_sig["recommendation"])

    def test_pmax_gap_signal_not_present_when_no_pmax(self):
        signals = app_module._gads_compute_search_term_signals([], _SAMPLE_CURRENCY_CTX,
                                                                has_pmax=False)
        ids = [s["id"] for s in signals]
        self.assertNotIn("pmax_gap_notice", ids)

    def test_signals_sorted_warning_before_info(self):
        rows = [
            {"cost": 20.0, "conversions": 0.0, "conversion_value": 0.0,
             "clicks": 12, "impressions": 100, "ctr": 12.0,
             "search_term": "waste", "classification": "waste",
             "roas": None, "cpa": None, "reason": "Spend with zero conversions"},
            {"cost": 30.0, "conversions": 3.0, "conversion_value": 240.0,
             "clicks": 25, "impressions": 200, "ctr": 8.0,
             "search_term": "winner", "classification": "winner",
             "roas": 8.0, "cpa": 10.0, "reason": "Good ROAS (8.00x)"},
        ]
        signals = app_module._gads_compute_search_term_signals(rows, _SAMPLE_CURRENCY_CTX,
                                                                has_pmax=True)
        # warnings must come before info
        severities = [s["severity"] for s in signals]
        warning_indices = [i for i, sv in enumerate(severities) if sv == "warning"]
        info_indices = [i for i, sv in enumerate(severities) if sv == "info"]
        if warning_indices and info_indices:
            self.assertLess(max(warning_indices), min(info_indices),
                            "warnings must appear before info signals")

    def test_high_cost_low_roas_signal(self):
        rows = [
            {"cost": 50.0, "conversions": 2.0, "conversion_value": 60.0,
             "clicks": 30, "impressions": 300, "ctr": 10.0,
             "search_term": "low roas term", "classification": "winner",
             "roas": 1.2, "cpa": 25.0, "reason": "Has conversions"},
        ]
        signals = app_module._gads_compute_search_term_signals(rows, _SAMPLE_CURRENCY_CTX)
        ids = [s["id"] for s in signals]
        # roas=1.2 < 2.0, cost=50 > 10 → high_cost_low_roas_terms
        self.assertIn("high_cost_low_roas_terms", ids)

    def test_no_signals_for_empty_rows(self):
        signals = app_module._gads_compute_search_term_signals([], _SAMPLE_CURRENCY_CTX)
        # Only possibly pmax_gap_notice if has_pmax, but has_pmax=False here
        waste_sigs = [s for s in signals if s["id"] != "pmax_gap_notice"]
        self.assertEqual(len(waste_sigs), 0)

    def test_currency_none_evidence_formats_safely(self):
        rows = [
            {"cost": 20.0, "conversions": 0.0, "conversion_value": 0.0,
             "clicks": 10, "impressions": 100, "ctr": 10.0,
             "search_term": "no currency", "classification": "waste",
             "roas": None, "cpa": None, "reason": "Spend with zero conversions"},
        ]
        signals = app_module._gads_compute_search_term_signals(rows, _EMPTY_CURRENCY_CTX)
        waste_sig = next((s for s in signals if s["id"] == "waste_search_terms"), None)
        self.assertIsNotNone(waste_sig)
        ev = waste_sig.get("evidence") or {}
        cost_ev = ev.get("total_waste_cost") or {}
        # Should format as [?] ... not crash
        self.assertIn("[?]", cost_ev.get("formatted", ""))
        self.assertIsNone(cost_ev.get("currency_code"))


class TestSearchTermsUIAndConstraints(unittest.TestCase):
    """15–16. UI and negative keyword constraints."""

    def _read_template(self):
        template_path = os.path.join(
            os.path.dirname(__file__), "templates", "connectors.html"
        )
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()

    def test_ui_search_terms_is_live_partial_not_disabled(self):
        """Search Terms button must NOT be disabled and must be live/partial."""
        html = self._read_template()
        # Should NOT have disabled attr on the search terms button
        import re
        # Find the search-terms button block
        match = re.search(
            r'<button[^>]*gadsModuleBtn_search_terms[^>]*>.*?</button>',
            html, re.DOTALL
        )
        self.assertIsNotNone(match, "gadsModuleBtn_search_terms button not found in template")
        btn_html = match.group(0)
        self.assertNotIn(' disabled', btn_html,
                         "Search Terms button must not be disabled")
        self.assertIn("gadsOpenModule('search_terms')", btn_html,
                      "Search Terms button must call gadsOpenModule")

    def test_ui_has_gads_render_search_terms_function(self):
        """Template must contain gadsRenderSearchTerms function."""
        html = self._read_template()
        self.assertIn("gadsRenderSearchTerms", html)

    def test_ui_search_terms_in_endpoint_map(self):
        """Template's endpointMap must include search_terms."""
        html = self._read_template()
        self.assertIn("'search_terms'", html)
        self.assertIn("intelligence/search-terms", html)

    def test_negative_keyword_actions_not_implemented(self):
        """There must be no /intelligence/search-terms/apply or mutate route."""
        routes = [rule.rule for rule in app_module.app.url_map.iter_rules()]
        for r in routes:
            self.assertNotIn("negative", r.lower(),
                             f"Negative keyword route found: {r}")
            self.assertNotIn("apply", r.lower() if "search-terms" in r.lower() else "",
                             f"Apply route found: {r}")

    def test_ui_shows_negative_keyword_placeholder(self):
        """Template must show a disabled/planned placeholder for neg kw actions."""
        html = self._read_template()
        self.assertIn("Negative keyword drafts", html)


class TestFetchSearchTermsParsing(unittest.TestCase):
    """Unit tests for _gads_fetch_search_terms response parsing."""

    @patch(f"{_PATCH_PREFIX}.requests")
    def test_fetch_parses_json_array_response(self, mock_requests):
        """Parses searchStream JSON array response format."""
        api_response = [
            {
                "results": [
                    {
                        "searchTermView": {
                            "searchTerm": "buy running shoes",
                            "status": "NONE",
                        },
                        "campaign": {"id": "1001", "name": "Brand", "status": "ENABLED"},
                        "adGroup": {"id": "2001", "name": "Brand KW"},
                        "metrics": {
                            "costMicros": "5000000",
                            "clicks": "50",
                            "impressions": "600",
                            "conversions": "4.0",
                            "conversionsValue": "200.0",
                            "ctr": "0.0833",
                            "averageCpc": "100000",
                        },
                        "customer": {"currencyCode": "RON"},
                    }
                ]
            }
        ]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = json.dumps(api_response)
        mock_requests.post.return_value = mock_resp

        result = app_module._gads_fetch_search_terms(
            "1234567890", "9876543210", "ACCESS_TOKEN", "DEV_TOKEN", days=30, limit=100
        )
        self.assertTrue(result.get("success"))
        rows = result.get("rows") or []
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["search_term"], "buy running shoes")
        self.assertEqual(row["cost"], 5.0)       # 5000000 micros / 1e6
        self.assertEqual(row["clicks"], 50)
        self.assertEqual(row["impressions"], 600)
        self.assertAlmostEqual(row["conversions"], 4.0)
        self.assertAlmostEqual(row["ctr"], 8.33, delta=0.1)  # 0.0833 * 100
        self.assertAlmostEqual(row["avg_cpc"], 0.1, delta=0.01)  # 100000 micros / 1e6
        self.assertEqual(row["currency_code"], "RON")
        self.assertIsNotNone(row.get("roas"))  # 200 / 5 = 40.0

    @patch(f"{_PATCH_PREFIX}.requests")
    def test_fetch_handles_api_error(self, mock_requests):
        """Returns error dict on HTTP non-200 response."""
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {"error": {"status": "INVALID_ARGUMENT"}}
        mock_requests.post.return_value = mock_resp

        result = app_module._gads_fetch_search_terms(
            "1234567890", "9876543210", "AT", "DT", days=30
        )
        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("error"), "google_ads_api_error")

    @patch(f"{_PATCH_PREFIX}.requests")
    def test_fetch_returns_error_on_network_exception(self, mock_requests):
        mock_requests.post.side_effect = Exception("Connection refused")
        result = app_module._gads_fetch_search_terms(
            "1234567890", "9876543210", "AT", "DT", days=30
        )
        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("error"), "api_network_error")

    def test_fetch_rejects_invalid_customer_id(self):
        result = app_module._gads_fetch_search_terms(
            "abc123", "9876543210", "AT", "DT"
        )
        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("error"), "invalid_account_id")

    @patch(f"{_PATCH_PREFIX}.requests")
    def test_fetch_no_token_in_gaql_query(self, mock_requests):
        """Ensures GAQL query does not contain mutation keywords."""
        captured_body = {}

        def capture_post(url, headers=None, json=None, timeout=None):
            captured_body["json"] = json
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = json_module.dumps([{"results": []}])
            return mock_resp

        import json as json_module
        mock_requests.post.side_effect = capture_post

        app_module._gads_fetch_search_terms(
            "1234567890", "9876543210", "AT", "DT", days=30
        )
        query = (captured_body.get("json") or {}).get("query", "").lower()
        self.assertNotIn("mutate", query)
        self.assertNotIn("create", query)
        self.assertNotIn("update", query)
        self.assertNotIn("remove", query)
        self.assertIn("search_term_view", query)


if __name__ == "__main__":
    unittest.main()
