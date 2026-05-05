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
os.environ.setdefault("DATABASE", "/tmp/camarad_source_truth_campaigns.db")

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


def _live_campaigns():
    return [{
        "id": "1001",
        "name": "Live Campaign",
        "status": "ENABLED",
        "type": "Search",
        "channel": "SEARCH",
        "spent": 123.45,
        "impressions": 1000,
        "clicks": 100,
        "conversions": 10.0,
        "conversion_value": 400.0,
        "cost_per_conv": 12.35,
        "roas": 3.24,
        "ctr": 10.0,
        "avg_cpc": 1.23,
        "currency_code": "RON",
    }]


class TestGoogleAdsSourcePolicy(unittest.TestCase):
    def test_google_ads_api_connected_is_live(self):
        p = app_module._gads_source_policy("google_ads_api", connected_live=True)
        self.assertTrue(p["live_data"])
        self.assertFalse(p["mock_used"])
        self.assertFalse(p["fallback_used"])

    def test_mock_is_non_live_and_mock_used(self):
        p = app_module._gads_source_policy("mock")
        self.assertFalse(p["live_data"])
        self.assertTrue(p["mock_used"])
        self.assertFalse(p["fallback_used"])

    def test_mock_fallback_is_non_live_with_warning(self):
        p = app_module._gads_source_policy("mock_fallback", connected_live=True)
        self.assertFalse(p["live_data"])
        self.assertFalse(p["mock_used"])
        self.assertTrue(p["fallback_used"])
        self.assertTrue(any("fallback" in w.lower() for w in p["warnings"]))

    def test_google_ads_api_error_is_non_live_without_mock(self):
        p = app_module._gads_source_policy("google_ads_api_error", connected_live=True)
        self.assertFalse(p["live_data"])
        self.assertFalse(p["mock_used"])
        self.assertFalse(p["fallback_used"])
        self.assertTrue(p["warnings"])


class TestCampaignResolverSourceTruth(unittest.TestCase):
    def test_connected_live_resolver_never_returns_plain_mock_on_raise(self):
        with patch(f"{PATCH}._gads_token_get_meta", return_value=_connected_meta()), \
             patch(f"{PATCH}._gads_get_fresh_" + ACCESS_KEY, return_value=_token_ok()), \
             patch(f"{PATCH}._gads_searchstream_campaigns", side_effect=RuntimeError("boom")):
            campaigns, _, source, _ = app_module._gads_resolve_live_campaigns(
                "1016047735", "8924163684", 30, user_id=1
            )
        self.assertEqual(campaigns, [])
        self.assertNotEqual(source, "mock")
        self.assertIn(source, ("google_ads_api_error", "mock_fallback"))


class TestCampaignsRouteSourceTruth(unittest.TestCase):
    def setUp(self):
        self.client = _client()

    def test_campaigns_returns_google_ads_api_on_success(self):
        live = _live_campaigns()
        with patch(f"{PATCH}._gads_token_get_meta", return_value=_connected_meta()), \
             patch(f"{PATCH}._gads_get_fresh_" + ACCESS_KEY, return_value=_token_ok()), \
             patch(f"{PATCH}._gads_searchstream_campaigns", return_value={
                 "success": True,
                 "campaigns": live,
                 "date_range": "LAST_30_DAYS",
                 "account_currency_code": "RON",
             }), \
             patch(f"{PATCH}._google_ads_gateway_fetch") as gateway, \
             patch(f"{PATCH}._google_ads_set_active_customer") as set_active:
            res = self.client.get(
                "/api/connectors/google-ads/campaigns"
                "?account_id=1016047735&mcc_id=8924163684"
            )
        self.assertEqual(res.status_code, 200)
        body = json.loads(res.data)
        self.assertEqual(body["source"], "google_ads_api")
        self.assertTrue(body["live_data"])
        self.assertFalse(body["mock_used"])
        self.assertFalse(body["fallback_used"])
        self.assertEqual(len(body["campaigns"]), 1)
        gateway.assert_not_called()
        set_active.assert_not_called()

    def test_campaigns_live_failure_returns_error_or_fallback_warning(self):
        with patch(f"{PATCH}._gads_token_get_meta", return_value=_connected_meta()), \
             patch(f"{PATCH}._gads_get_fresh_" + ACCESS_KEY, return_value=_token_ok()), \
             patch(f"{PATCH}._gads_searchstream_campaigns", return_value={
                 "success": False,
                 "error": "google_ads_api_error",
                 "status_code": 403,
                 "message": "Google Ads API failed.",
             }), \
             patch(f"{PATCH}._google_ads_gateway_fetch") as gateway:
            res = self.client.get(
                "/api/connectors/google-ads/campaigns"
                "?account_id=1016047735&mcc_id=8924163684"
            )
        self.assertEqual(res.status_code, 200)
        body = json.loads(res.data)
        self.assertIn(body["source"], ("google_ads_api_error", "mock_fallback"))
        self.assertNotEqual(body["source"], "mock")
        self.assertTrue(body["warnings"])
        self.assertFalse(body["live_data"])
        gateway.assert_not_called()

    def test_campaigns_fallback_is_not_live(self):
        with patch(f"{PATCH}._gads_token_get_meta", return_value=_connected_meta()), \
             patch(f"{PATCH}._gads_get_fresh_" + ACCESS_KEY, return_value=_token_ok()), \
             patch(f"{PATCH}._gads_searchstream_campaigns", return_value={
                 "success": False,
                 "error": "google_ads_api_error",
                 "status_code": 500,
             }):
            res = self.client.get(
                "/api/connectors/google-ads/campaigns"
                "?account_id=123-456-7890&allow_fallback=1"
            )
        body = json.loads(res.data)
        self.assertEqual(body["source"], "mock_fallback")
        self.assertFalse(body["live_data"])
        self.assertTrue(body["fallback_used"])
        self.assertFalse(body["mock_used"])

    def test_campaigns_unauthenticated_mock_is_not_live(self):
        with patch(f"{PATCH}._gads_token_get_meta", return_value=None), \
             patch(f"{PATCH}._google_ads_gateway_fetch", return_value=(None, {"enabled": False})):
            res = self.client.get(
                "/api/connectors/google-ads/campaigns?account_id=123-456-7890"
            )
        body = json.loads(res.data)
        self.assertEqual(body["source"], "mock")
        self.assertFalse(body["live_data"])
        self.assertTrue(body["mock_used"])
        self.assertFalse(body["fallback_used"])

    def test_campaign_response_does_not_expose_sensitive_values(self):
        with patch(f"{PATCH}._gads_token_get_meta", return_value=_connected_meta()), \
             patch(f"{PATCH}._gads_get_fresh_" + ACCESS_KEY, return_value=_token_ok()), \
             patch(f"{PATCH}._gads_searchstream_campaigns", return_value={
                 "success": False,
                 "error": "google_ads_api_error",
                 "status_code": 403,
             }):
            res = self.client.get(
                "/api/connectors/google-ads/campaigns?account_id=1016047735"
            )
        text = res.data.decode()
        forbidden = [
            "TOKEN_VALUE_MUST_NOT_APPEAR",
            ACCESS_KEY,
            "refresh" + "_token",
            "developer" + "_token",
            "client" + "_secret",
        ]
        for item in forbidden:
            self.assertNotIn(item, text)

    def test_campaigns_live_path_does_not_call_fallback_gateway(self):
        with patch(f"{PATCH}._gads_token_get_meta", return_value=_connected_meta()), \
             patch(f"{PATCH}._gads_get_fresh_" + ACCESS_KEY, return_value=_token_ok()), \
             patch(f"{PATCH}._gads_searchstream_campaigns", return_value={
                 "success": False,
                 "error": "google_ads_api_error",
                 "status_code": 403,
             }) as stream, \
             patch(f"{PATCH}._google_ads_gateway_fetch") as gateway, \
             patch(f"{PATCH}._google_ads_set_active_customer") as set_active:
            self.client.get(
                "/api/connectors/google-ads/campaigns?account_id=1016047735"
            )
        stream.assert_called_once()
        gateway.assert_not_called()
        set_active.assert_not_called()


class TestDerivedCampaignConsumers(unittest.TestCase):
    def setUp(self):
        self.client = _client()

    def test_overview_propagates_non_live_source_and_warnings(self):
        with patch(f"{PATCH}._gads_token_get_meta", return_value=_connected_meta()), \
             patch(f"{PATCH}._gads_resolve_live_campaigns", return_value=(
                 [], "LAST_30_DAYS", "google_ads_api_error", None
             )):
            res = self.client.get(
                "/api/connectors/google-ads/overview?customer_id=1016047735"
            )
        body = json.loads(res.data)
        self.assertEqual(body["source"], "google_ads_api_error")
        self.assertFalse(body["live_data"])
        self.assertFalse(body["mock_used"])
        self.assertTrue(body["warnings"])

    def test_account_health_and_waste_finder_do_not_mark_fallback_live(self):
        campaign = _live_campaigns()[0]
        with patch(f"{PATCH}._gads_token_get_meta", return_value=_connected_meta()), \
             patch(f"{PATCH}._gads_resolve_live_campaigns", return_value=(
                 [campaign], "LAST_30_DAYS", "mock_fallback", "RON"
             )):
            health = json.loads(self.client.get(
                "/api/connectors/google-ads/intelligence/account-health"
                "?customer_id=1016047735"
            ).data)
            waste = json.loads(self.client.get(
                "/api/connectors/google-ads/intelligence/waste-finder"
                "?customer_id=1016047735"
            ).data)
        for body in (health, waste):
            self.assertEqual(body["source"], "mock_fallback")
            self.assertFalse(body["live_data"])
            self.assertTrue(body["fallback_used"])
            self.assertFalse(body["mock_used"])


if __name__ == "__main__":
    unittest.main()
