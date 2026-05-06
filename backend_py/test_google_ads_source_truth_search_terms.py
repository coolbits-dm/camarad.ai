import json
import os
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
os.environ.setdefault("DATABASE", "/tmp/camarad_source_truth_search_terms.db")

import backend_py.app as app_module
from backend_py.app import app


PATCH = "backend_py.app"
ACCESS_KEY = "access" + "_token"


def _client():
    app.config["TESTING"] = True
    return app.test_client()


def _connected_meta():
    return {
        "status": "active",
        "api_validated": True,
        "token_validated": True,
        "selected_manager_customer_id": "8924163684",
    }


def _token_ok():
    return {"success": True, ACCESS_KEY: "TOKEN_VALUE_MUST_NOT_APPEAR"}


def _sample_rows():
    return [{
        "search_term": "buy running shoes",
        "campaign_id": "1001",
        "campaign_name": "Search",
        "campaign_status": "ENABLED",
        "ad_group_id": "2001",
        "ad_group_name": "Shoes",
        "impressions": 1000,
        "clicks": 100,
        "cost": 50.0,
        "conversions": 5.0,
        "conversion_value": 250.0,
        "ctr": 10.0,
        "avg_cpc": 0.5,
        "cpa": 10.0,
        "roas": 5.0,
        "conversion_rate": 5.0,
        "currency_code": "RON",
        "targeting_status": "NONE",
        "classification": None,
        "reason": "",
    }]


EMPTY_CURRENCY_CTX = {
    "currency_code": None,
    "currency_source": "unknown",
    "conversion_applied": False,
    "warning": None,
}


RON_CURRENCY_CTX = {
    "currency_code": "RON",
    "currency_source": "api",
    "conversion_applied": False,
    "warning": None,
}


class TestSearchTermsResolverSourceTruth(unittest.TestCase):
    def test_resolver_live_success_returns_google_ads_api_live_policy(self):
        with patch(f"{PATCH}._gads_token_get_meta", return_value=_connected_meta()), \
             patch(f"{PATCH}._gads_get_fresh_" + ACCESS_KEY, return_value=_token_ok()), \
             patch(f"{PATCH}._gads_fetch_search_terms", return_value={
                 "success": True,
                 "rows": _sample_rows(),
                 "date_range": "LAST_30_DAYS",
                 "account_currency_code": "RON",
             }) as fetch:
            rows, date_range, source, currency = app_module._gads_resolve_live_search_terms(
                "1016047735", "8924163684", 30, 100, user_id=1
            )

        policy = app_module._gads_source_policy(source, connected_live=True)
        self.assertEqual(source, "google_ads_api")
        self.assertTrue(policy["live_data"])
        self.assertFalse(policy["mock_used"])
        self.assertFalse(policy["fallback_used"])
        self.assertEqual(date_range, "LAST_30_DAYS")
        self.assertEqual(currency, "RON")
        self.assertEqual(len(rows), 1)
        fetch.assert_called_once()

    def test_token_refresh_failure_returns_api_error_not_mock(self):
        with patch(f"{PATCH}._gads_token_get_meta", return_value=_connected_meta()), \
             patch(f"{PATCH}._gads_get_fresh_" + ACCESS_KEY, return_value={
                 "success": False,
                 "error": "refresh_failed",
             }), \
             patch(f"{PATCH}._gads_fetch_search_terms") as fetch:
            rows, _, source, _ = app_module._gads_resolve_live_search_terms(
                "1016047735", "8924163684", 30, 100, user_id=1
            )

        policy = app_module._gads_source_policy(source, connected_live=True)
        self.assertEqual(rows, [])
        self.assertEqual(source, "google_ads_api_error")
        self.assertFalse(policy["live_data"])
        self.assertFalse(policy["mock_used"])
        self.assertFalse(policy["fallback_used"])
        fetch.assert_not_called()

    def test_google_ads_api_failure_returns_api_error_by_default(self):
        with patch(f"{PATCH}._gads_token_get_meta", return_value=_connected_meta()), \
             patch(f"{PATCH}._gads_get_fresh_" + ACCESS_KEY, return_value=_token_ok()), \
             patch(f"{PATCH}._gads_fetch_search_terms", return_value={
                 "success": False,
                 "error": "google_ads_api_error",
                 "status_code": 403,
             }):
            rows, _, source, _ = app_module._gads_resolve_live_search_terms(
                "1016047735", "8924163684", 30, 100, user_id=1
            )

        policy = app_module._gads_source_policy(source, connected_live=True)
        self.assertEqual(rows, [])
        self.assertEqual(source, "google_ads_api_error")
        self.assertFalse(policy["live_data"])
        self.assertFalse(policy["mock_used"])
        self.assertFalse(policy["fallback_used"])

    def test_explicit_fallback_returns_mock_fallback_not_live(self):
        with patch(f"{PATCH}._gads_token_get_meta", return_value=_connected_meta()), \
             patch(f"{PATCH}._gads_get_fresh_" + ACCESS_KEY, return_value=_token_ok()), \
             patch(f"{PATCH}._gads_fetch_search_terms", return_value={
                 "success": False,
                 "error": "google_ads_api_error",
                 "status_code": 500,
             }):
            rows, _, source, _ = app_module._gads_resolve_live_search_terms(
                "123-456-7890", "8924163684", 30, 100, user_id=1,
                allow_fallback=True,
            )

        policy = app_module._gads_source_policy(source, connected_live=True)
        self.assertEqual(source, "mock_fallback")
        self.assertTrue(rows)
        self.assertFalse(policy["live_data"])
        self.assertFalse(policy["mock_used"])
        self.assertTrue(policy["fallback_used"])
        self.assertTrue(policy["warnings"])

    def test_unauthenticated_returns_mock_not_live(self):
        with patch(f"{PATCH}._gads_token_get_meta", return_value=None):
            rows, _, source, _ = app_module._gads_resolve_live_search_terms(
                "123-456-7890", "", 30, 100, user_id=1
            )

        policy = app_module._gads_source_policy(source, connected_live=False)
        self.assertEqual(source, "mock")
        self.assertTrue(rows)
        self.assertFalse(policy["live_data"])
        self.assertTrue(policy["mock_used"])
        self.assertFalse(policy["fallback_used"])


class TestSearchTermsEndpointSourceTruth(unittest.TestCase):
    def setUp(self):
        self.client = _client()

    def test_endpoint_propagates_api_error_source_truth(self):
        with patch(f"{PATCH}._gads_token_get_meta", return_value=_connected_meta()), \
             patch(f"{PATCH}._gads_resolve_live_search_terms", return_value=(
                 [], "LAST_30_DAYS", "google_ads_api_error", None
             )), \
             patch(f"{PATCH}._gads_resolve_live_campaigns", return_value=(
                 [], "LAST_30_DAYS", "google_ads_api_error", None
             )), \
             patch(f"{PATCH}._gads_resolve_currency_context", return_value=EMPTY_CURRENCY_CTX):
            res = self.client.get(
                "/api/connectors/google-ads/intelligence/search-terms"
                "?customer_id=1016047735&mcc_id=8924163684"
            )

        body = json.loads(res.data)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(body["source"], "google_ads_api_error")
        self.assertFalse(body["live_data"])
        self.assertFalse(body["mock_used"])
        self.assertFalse(body["fallback_used"])
        self.assertEqual(body["rows"], [])
        self.assertTrue(body["warnings"])

    def test_endpoint_live_success_is_live(self):
        with patch(f"{PATCH}._gads_token_get_meta", return_value=_connected_meta()), \
             patch(f"{PATCH}._gads_resolve_live_search_terms", return_value=(
                 _sample_rows(), "LAST_30_DAYS", "google_ads_api", "RON"
             )), \
             patch(f"{PATCH}._gads_resolve_live_campaigns", return_value=(
                 [], "LAST_30_DAYS", "google_ads_api", "RON"
             )), \
             patch(f"{PATCH}._gads_resolve_currency_context", return_value=RON_CURRENCY_CTX):
            res = self.client.get(
                "/api/connectors/google-ads/intelligence/search-terms"
                "?customer_id=1016047735&mcc_id=8924163684"
            )

        body = json.loads(res.data)
        self.assertEqual(body["source"], "google_ads_api")
        self.assertTrue(body["live_data"])
        self.assertFalse(body["mock_used"])
        self.assertFalse(body["fallback_used"])
        self.assertEqual(len(body["rows"]), 1)

    def test_endpoint_explicit_fallback_is_not_live(self):
        with patch(f"{PATCH}._gads_token_get_meta", return_value=_connected_meta()), \
             patch(f"{PATCH}._gads_resolve_live_search_terms", return_value=(
                 _sample_rows(), "LAST_30_DAYS", "mock_fallback", "RON"
             )), \
             patch(f"{PATCH}._gads_resolve_live_campaigns", return_value=(
                 [], "LAST_30_DAYS", "mock_fallback", "RON"
             )), \
             patch(f"{PATCH}._gads_resolve_currency_context", return_value=RON_CURRENCY_CTX):
            res = self.client.get(
                "/api/connectors/google-ads/intelligence/search-terms"
                "?customer_id=1016047735&mcc_id=8924163684&allow_fallback=1"
            )

        body = json.loads(res.data)
        self.assertEqual(body["source"], "mock_fallback")
        self.assertFalse(body["live_data"])
        self.assertFalse(body["mock_used"])
        self.assertTrue(body["fallback_used"])
        self.assertTrue(body["warnings"])

    def test_endpoint_does_not_expose_sensitive_values(self):
        with patch(f"{PATCH}._gads_token_get_meta", return_value=_connected_meta()), \
             patch(f"{PATCH}._gads_resolve_live_search_terms", return_value=(
                 [], "LAST_30_DAYS", "google_ads_api_error", None
             )), \
             patch(f"{PATCH}._gads_resolve_live_campaigns", return_value=(
                 [], "LAST_30_DAYS", "google_ads_api_error", None
             )), \
             patch(f"{PATCH}._gads_resolve_currency_context", return_value=EMPTY_CURRENCY_CTX):
            res = self.client.get(
                "/api/connectors/google-ads/intelligence/search-terms"
                "?customer_id=1016047735"
            )

        text = res.data.decode().lower()
        forbidden = [
            ACCESS_KEY,
            "refresh" + "_token",
            "developer" + "_token",
            "client" + "_secret",
            "private" + "_key",
            "bearer",
            "TOKEN_VALUE_MUST_NOT_APPEAR".lower(),
        ]
        for item in forbidden:
            self.assertNotIn(item, text)

    def test_no_negative_keyword_or_mutate_route_exists(self):
        routes = [rule.rule.lower() for rule in app_module.app.url_map.iter_rules()]
        search_term_routes = [r for r in routes if "search-terms" in r]
        for route in search_term_routes:
            self.assertNotIn("mutate", route)
            self.assertNotIn("apply", route)
            self.assertNotIn("negative", route)

    def test_pmax_limitation_warning_remains_present(self):
        with patch(f"{PATCH}._gads_token_get_meta", return_value=None), \
             patch(f"{PATCH}._gads_resolve_live_search_terms", return_value=(
                 [], "LAST_30_DAYS", "mock", None
             )), \
             patch(f"{PATCH}._gads_resolve_live_campaigns", return_value=(
                 [{"name": "PMax", "channel": "Performance Max", "status": "ENABLED"}],
                 "LAST_30_DAYS", "mock", None
             )), \
             patch(f"{PATCH}._gads_resolve_currency_context", return_value=EMPTY_CURRENCY_CTX):
            res = self.client.get(
                "/api/connectors/google-ads/intelligence/search-terms"
                "?customer_id=1234567890"
            )

        body = json.loads(res.data)
        warnings = " ".join(body.get("warnings") or [])
        summary_note = str((body.get("summary") or {}).get("pmax_terms_note") or "")
        signals = " ".join(str(s) for s in (body.get("signals") or []))
        combined = f"{warnings} {summary_note} {signals}"
        self.assertIn("Performance Max", combined)
        self.assertIn("campaign_search_term_view", combined)


if __name__ == "__main__":
    unittest.main()
