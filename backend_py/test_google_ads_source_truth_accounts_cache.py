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
os.environ.setdefault("DATABASE", "/tmp/camarad_source_truth_accounts_cache.db")

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


def _cached_accessible_customers():
    return [{
        "customer_id": "8924163684",
        "resource_name": "customers/8924163684",
        "display_name": "Google Ads Customer 892-416-3684",
    }]


def _cached_hierarchy():
    return [
        {
            "customer_id": "8924163684",
            "resource_name": "customers/8924163684",
            "descriptive_name": "Manager Account",
            "account_type": "manager",
            "is_manager": True,
            "level": 0,
            "status": "ENABLED",
            "currency_code": "RON",
            "time_zone": "Europe/Bucharest",
        },
        {
            "customer_id": "1325845765",
            "resource_name": "customers/1325845765",
            "descriptive_name": "MATCA",
            "account_type": "client",
            "is_manager": False,
            "level": 1,
            "status": "ENABLED",
            "currency_code": "RON",
            "time_zone": "Europe/Bucharest",
        },
    ]


class TestGoogleAdsAccountsCacheSourceTruth(unittest.TestCase):
    def setUp(self):
        self.client = _client()

    def test_accounts_cached_accessible_customers_use_cached_source(self):
        with patch(f"{PATCH}._gads_token_get_meta", return_value=_connected_meta()), \
             patch(f"{PATCH}._gads_get_accessible_customers", return_value=_cached_accessible_customers()), \
             patch(f"{PATCH}._gads_get_customer_hierarchy", return_value=[]), \
             patch(f"{PATCH}._google_ads_gateway_fetch") as gateway:
            res = self.client.get("/api/connectors/google-ads/accounts")

        body = json.loads(res.data)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(body["source"], "cached_google_ads_api")
        self.assertEqual(body["source_label"], "Cached Google Ads")
        self.assertFalse(body["live_data"])
        self.assertTrue(body["cache"])
        self.assertFalse(body["fresh"])
        self.assertTrue(body["connected_live"])
        self.assertTrue(body["warnings"])
        gateway.assert_not_called()

    def test_accounts_mock_response_is_non_live_mock(self):
        with patch(f"{PATCH}._gads_token_get_meta", return_value=None), \
             patch(f"{PATCH}._google_ads_gateway_fetch", return_value=(None, {"enabled": False})):
            res = self.client.get("/api/connectors/google-ads/accounts")

        body = json.loads(res.data)
        self.assertEqual(body["source"], "mock")
        self.assertFalse(body["live_data"])
        self.assertTrue(body["mock_used"])
        self.assertFalse(body["fallback_used"])
        self.assertFalse(body["cache"])
        self.assertFalse(body["fresh"])

    def test_connected_accounts_do_not_return_legacy_demo_names(self):
        with patch(f"{PATCH}._gads_token_get_meta", return_value=_connected_meta()), \
             patch(f"{PATCH}._gads_get_accessible_customers", return_value=_cached_accessible_customers()), \
             patch(f"{PATCH}._gads_get_customer_hierarchy", return_value=_cached_hierarchy()):
            res = self.client.get("/api/connectors/google-ads/accounts")

        text = res.data.decode()
        self.assertEqual(res.status_code, 200)
        for demo_name in ("E-Shop", "TechStart", "Global Reach"):
            self.assertNotIn(demo_name, text)

    def test_get_mcc_hierarchy_cached_source(self):
        with patch(f"{PATCH}._gads_token_get_meta", return_value=_connected_meta()), \
             patch(f"{PATCH}._gads_get_customer_hierarchy", return_value=_cached_hierarchy()):
            res = self.client.get(
                "/api/connectors/google-ads/mcc/hierarchy?manager_customer_id=8924163684"
            )

        body = json.loads(res.data)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(body["source"], "cached_google_ads_api")
        self.assertFalse(body["live_data"])
        self.assertTrue(body["cache"])
        self.assertFalse(body["fresh"])
        self.assertTrue(body["connected_live"])
        self.assertTrue(body["warnings"])
        self.assertEqual(body["accounts_count"], 2)

    def test_get_mcc_hierarchy_without_manager_still_marks_cached_read(self):
        meta = dict(_connected_meta(), selected_manager_customer_id=None)
        with patch(f"{PATCH}._gads_token_get_meta", return_value=meta):
            res = self.client.get("/api/connectors/google-ads/mcc/hierarchy")

        body = json.loads(res.data)
        self.assertEqual(body["source"], "cached_google_ads_api")
        self.assertFalse(body["live_data"])
        self.assertTrue(body["cache"])
        self.assertFalse(body["fresh"])

    def test_post_mcc_hierarchy_success_is_fresh_api(self):
        with patch(f"{PATCH}._gads_oauth_configured", return_value=True), \
             patch(f"{PATCH}._gads_token_get_meta", return_value=_connected_meta()), \
             patch(f"{PATCH}._gads_get_fresh_" + ACCESS_KEY, return_value={
                 "success": True,
                 ACCESS_KEY: "VALUE_MUST_NOT_APPEAR",
             }), \
             patch(f"{PATCH}._gads_oauth_config_internal", return_value={}), \
             patch(f"{PATCH}._gads_fetch_customer_hierarchy", return_value={
                 "success": True,
                 "accounts": _cached_hierarchy(),
             }) as fetch, \
             patch(f"{PATCH}._gads_store_customer_hierarchy", return_value=2), \
             patch(f"{PATCH}._gads_update_metadata"):
            res = self.client.post(
                "/api/connectors/google-ads/mcc/hierarchy",
                json={"manager_customer_id": "8924163684"},
            )

        body = json.loads(res.data)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(body["source"], "google_ads_api")
        self.assertTrue(body["live_data"])
        self.assertFalse(body["cache"])
        self.assertTrue(body["fresh"])
        self.assertFalse(body["mock_used"])
        self.assertFalse(body["fallback_used"])
        fetch.assert_called_once()

    def test_post_mcc_hierarchy_api_failure_is_api_error(self):
        with patch(f"{PATCH}._gads_oauth_configured", return_value=True), \
             patch(f"{PATCH}._gads_token_get_meta", return_value=_connected_meta()), \
             patch(f"{PATCH}._gads_get_fresh_" + ACCESS_KEY, return_value={
                 "success": True,
                 ACCESS_KEY: "VALUE_MUST_NOT_APPEAR",
             }), \
             patch(f"{PATCH}._gads_oauth_config_internal", return_value={}), \
             patch(f"{PATCH}._gads_fetch_customer_hierarchy", return_value={
                 "success": False,
                 "error": "google_ads_api_error",
                 "status_code": 403,
                 "message": "Google Ads API denied hierarchy access.",
             }):
            res = self.client.post(
                "/api/connectors/google-ads/mcc/hierarchy",
                json={"manager_customer_id": "8924163684"},
            )

        body = json.loads(res.data)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(body["source"], "google_ads_api_error")
        self.assertFalse(body["live_data"])
        self.assertFalse(body["cache"])
        self.assertFalse(body["fresh"])
        self.assertFalse(body["mock_used"])
        self.assertFalse(body["fallback_used"])
        self.assertTrue(body["warnings"])

    def test_post_mcc_hierarchy_token_failure_is_api_error(self):
        with patch(f"{PATCH}._gads_oauth_configured", return_value=True), \
             patch(f"{PATCH}._gads_token_get_meta", return_value=_connected_meta()), \
             patch(f"{PATCH}._gads_get_fresh_" + ACCESS_KEY, return_value={
                 "success": False,
                 "error": "refresh_failed",
                 "message": "Refresh failed.",
             }), \
             patch(f"{PATCH}._gads_fetch_customer_hierarchy") as fetch:
            res = self.client.post(
                "/api/connectors/google-ads/mcc/hierarchy",
                json={"manager_customer_id": "8924163684"},
            )

        body = json.loads(res.data)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(body["source"], "google_ads_api_error")
        self.assertFalse(body["live_data"])
        self.assertFalse(body["mock_used"])
        self.assertFalse(body["fallback_used"])
        fetch.assert_not_called()

    def test_responses_do_not_expose_sensitive_values(self):
        with patch(f"{PATCH}._gads_oauth_configured", return_value=True), \
             patch(f"{PATCH}._gads_token_get_meta", return_value=_connected_meta()), \
             patch(f"{PATCH}._gads_get_fresh_" + ACCESS_KEY, return_value={
                 "success": True,
                 ACCESS_KEY: "VALUE_MUST_NOT_APPEAR",
             }), \
             patch(f"{PATCH}._gads_oauth_config_internal", return_value={}), \
             patch(f"{PATCH}._gads_fetch_customer_hierarchy", return_value={
                 "success": False,
                 "error": "google_ads_api_error",
             }):
            res = self.client.post(
                "/api/connectors/google-ads/mcc/hierarchy",
                json={"manager_customer_id": "8924163684"},
            )

        text = res.data.decode()
        forbidden = [
            "VALUE_MUST_NOT_APPEAR",
            ACCESS_KEY,
            "refresh" + "_token",
            "developer" + "_token",
            "client" + "_secret",
            "Bearer",
        ]
        for item in forbidden:
            self.assertNotIn(item, text)

    def test_cached_account_reads_do_not_call_google_ads_write_api(self):
        with patch(f"{PATCH}._gads_token_get_meta", return_value=_connected_meta()), \
             patch(f"{PATCH}._gads_get_accessible_customers", return_value=_cached_accessible_customers()), \
             patch(f"{PATCH}._gads_get_customer_hierarchy", return_value=[]), \
             patch(f"{PATCH}.requests.post") as post:
            res = self.client.get("/api/connectors/google-ads/accounts")

        self.assertEqual(res.status_code, 200)
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
