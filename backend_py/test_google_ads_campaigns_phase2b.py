"""
Phase 2B: Google Ads Campaigns Read-Only via searchStream.

Tests:
1. _gads_searchstream_campaigns parses valid JSON-array searchStream response
2. _gads_searchstream_campaigns correctly converts cost_micros to cost dollars
3. _gads_searchstream_campaigns computes CTR, avg_cpc, cost_per_conv, ROAS
4. _gads_searchstream_campaigns maps channel type to friendly name
5. _gads_searchstream_campaigns handles LAST_7_DAYS and LAST_30_DAYS date range
6. _gads_searchstream_campaigns returns error on non-200 (no leak)
7. _gads_searchstream_campaigns rejects invalid account_id
8. GET /campaigns uses live API when api_validated (source=google_ads_api)
9. GET /campaigns returns mcc_id as login-customer-id when provided
10. GET /campaigns falls back to mock when no OAuth token
11. GET /campaigns falls back to mock on API error (no crash)
12. Response always contains campaigns list + summary keys
"""

import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# ── env bootstrap ──────────────────────────────────────────────────────────
os.environ.setdefault("AUTH_REQUIRED", "0")
os.environ.setdefault("COOLBITS_GATEWAY_ENABLED", "false")
os.environ.setdefault("DATABASE", "/tmp/camarad_gads_phase2b_test.db")
os.environ.setdefault("GOOGLE_ADS_CLIENT_ID", "FAKE_CLIENT_ID")
os.environ.setdefault("GOOGLE_ADS_CLIENT_SECRET", "FAKE_SECRET")
os.environ.setdefault("GOOGLE_ADS_DEVELOPER_TOKEN", "FAKE_DEV_TOKEN")

sys.path.insert(0, os.path.dirname(__file__))
import app as _app
from app import (
    _gads_searchstream_campaigns,
    _gads_token_store,
    _gads_update_metadata,
    _gads_store_customer_hierarchy,
    _gads_store_accessible_customers,
)


# ── helpers ────────────────────────────────────────────────────────────────

def _set_env():
    os.environ["AUTH_REQUIRED"] = "0"
    os.environ["COOLBITS_GATEWAY_ENABLED"] = "false"
    os.environ["GOOGLE_ADS_CLIENT_ID"] = "FAKE_CLIENT_ID"
    os.environ["GOOGLE_ADS_CLIENT_SECRET"] = "FAKE_SECRET"
    os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"] = "FAKE_DEV_TOKEN"


def _store_mock_token(user_id=1):
    token_data = {
        "refresh_token": "FAKE_REFRESH_NOT_REAL",
        "token_type": "Bearer",
    }
    _gads_token_store(user_id, token_data)
    _gads_update_metadata(user_id, {
        "token_validated": True,
        "api_validated": True,
        "accessible_customers": ["1016047735", "3741586068", "8924163684"],
        "selected_manager_customer_id": "8924163684",
    })


def _mock_token_refresh():
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {"access_token": "REFRESHED_ACCESS_NOT_REAL"}
    return m


def _build_mock_campaigns_json_array(num_campaigns=3):
    results = []
    for i in range(num_campaigns):
        cid = str(1000000 + i)
        results.append({
            "campaign": {
                "id": cid,
                "name": f"Test Campaign {i + 1}",
                "advertisingChannelType": "SEARCH",
                "status": "ENABLED",
                "biddingStrategyType": "TARGET_CPA",
                "resourceName": f"customers/8924163684/campaigns/{cid}",
            },
            "metrics": {
                "impressions": str(10000 * (i + 1)),
                "clicks": str(500 * (i + 1)),
                "costMicros": str(250_000_000 * (i + 1)),  # $250 * (i+1)
                "conversions": float(25 * (i + 1)),
                "conversionsValue": float(1000 * (i + 1)),
            },
        })
    return json.dumps([{"results": results}])


# ── Test 1: Parse valid JSON-array searchStream response ───────────────────
class TestSearchStreamParsing(unittest.TestCase):

    def test_parses_json_array_format(self):
        """_gads_searchstream_campaigns must parse JSON-array searchStream response."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = _build_mock_campaigns_json_array(3)

        with patch("requests.post", return_value=mock_resp):
            result = _gads_searchstream_campaigns(
                "8924163684", "FAKE_TOKEN", "FAKE_DEV", "8924163684", days=30
            )

        self.assertTrue(result.get("success"), f"Expected success, got: {result}")
        campaigns = result["campaigns"]
        self.assertEqual(len(campaigns), 3)

    def test_returns_empty_list_on_empty_results(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = json.dumps([{"results": []}])

        with patch("requests.post", return_value=mock_resp):
            result = _gads_searchstream_campaigns(
                "8924163684", "FAKE_TOKEN", "FAKE_DEV", "8924163684", days=30
            )

        self.assertTrue(result.get("success"))
        self.assertEqual(result["campaigns"], [])


# ── Test 2: cost_micros → dollars ─────────────────────────────────────────
class TestCostConversion(unittest.TestCase):

    def test_cost_micros_converted_to_dollars(self):
        """250_000_000 micros = $250.00"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = json.dumps([{"results": [{
            "campaign": {"id": "111", "name": "C1", "advertisingChannelType": "SEARCH", "status": "ENABLED"},
            "metrics": {"impressions": "1000", "clicks": "100",
                        "costMicros": "250000000", "conversions": 10.0, "conversionsValue": 500.0},
        }]}])

        with patch("requests.post", return_value=mock_resp):
            result = _gads_searchstream_campaigns(
                "1234567890", "FAKE_TOKEN", "FAKE_DEV", "8924163684", days=30
            )

        self.assertTrue(result.get("success"))
        c = result["campaigns"][0]
        self.assertAlmostEqual(c["spent"], 250.0, places=2)


# ── Test 3: Derived metrics ────────────────────────────────────────────────
class TestDerivedMetrics(unittest.TestCase):

    def _get_campaign(self, impressions=10000, clicks=500, cost_micros=250_000_000,
                      conversions=25.0, conv_value=1000.0):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = json.dumps([{"results": [{
            "campaign": {"id": "222", "name": "C2", "advertisingChannelType": "SEARCH", "status": "ENABLED"},
            "metrics": {
                "impressions": str(impressions), "clicks": str(clicks),
                "costMicros": str(cost_micros), "conversions": conversions,
                "conversionsValue": conv_value,
            },
        }]}])
        with patch("requests.post", return_value=mock_resp):
            result = _gads_searchstream_campaigns(
                "1234567890", "FAKE_TOKEN", "FAKE_DEV", "8924163684", days=30
            )
        self.assertTrue(result.get("success"))
        return result["campaigns"][0]

    def test_ctr_computed(self):
        c = self._get_campaign(impressions=10000, clicks=500)
        # 500/10000*100 = 5.0
        self.assertAlmostEqual(c["ctr"], 5.0, places=1)

    def test_avg_cpc_computed(self):
        c = self._get_campaign(clicks=500, cost_micros=250_000_000)  # $250 / 500 = $0.50
        self.assertAlmostEqual(c["avg_cpc"], 0.5, places=2)

    def test_cost_per_conv_computed(self):
        c = self._get_campaign(cost_micros=250_000_000, conversions=25.0)  # $250 / 25 = $10
        self.assertAlmostEqual(c["cost_per_conv"], 10.0, places=2)

    def test_roas_computed(self):
        c = self._get_campaign(cost_micros=250_000_000, conv_value=1000.0)  # 1000/250 = 4.0
        self.assertAlmostEqual(c["roas"], 4.0, places=2)

    def test_zero_cost_roas_is_zero(self):
        c = self._get_campaign(cost_micros=0, conv_value=0.0)
        self.assertEqual(c["roas"], 0.0)


# ── Test 4: Channel type mapping ──────────────────────────────────────────
class TestChannelTypeMapping(unittest.TestCase):

    def _get_campaign_channel(self, channel_type):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = json.dumps([{"results": [{
            "campaign": {"id": "333", "name": "C3", "advertisingChannelType": channel_type, "status": "ENABLED"},
            "metrics": {"impressions": "100", "clicks": "10", "costMicros": "1000000",
                        "conversions": 0.0, "conversionsValue": 0.0},
        }]}])
        with patch("requests.post", return_value=mock_resp):
            result = _gads_searchstream_campaigns(
                "1234567890", "FAKE_TOKEN", "FAKE_DEV", "8924163684", days=30
            )
        return result["campaigns"][0]["type"]

    def test_search_maps_to_search(self):
        self.assertEqual(self._get_campaign_channel("SEARCH"), "Search")

    def test_display_maps_to_display(self):
        self.assertEqual(self._get_campaign_channel("DISPLAY"), "Display")

    def test_performance_max_maps_correctly(self):
        t = self._get_campaign_channel("PERFORMANCE_MAX")
        self.assertIn("Performance", t)

    def test_video_maps_to_video(self):
        self.assertEqual(self._get_campaign_channel("VIDEO"), "Video")


# ── Test 5: Date range mapping ────────────────────────────────────────────
class TestDateRangeMapping(unittest.TestCase):

    def _get_called_gaql(self, days):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = json.dumps([{"results": []}])
        with patch("requests.post", return_value=mock_resp) as mp:
            _gads_searchstream_campaigns("1234567890", "T", "D", "8924163684", days=days)
            call_body = mp.call_args[1]["json"] if mp.call_args[1] else mp.call_args[0][2]
            return call_body.get("query", "")

    def test_7_days_uses_last_7_days(self):
        gaql = self._get_called_gaql(7)
        self.assertIn("LAST_7_DAYS", gaql)

    def test_30_days_uses_last_30_days(self):
        gaql = self._get_called_gaql(30)
        self.assertIn("LAST_30_DAYS", gaql)

    def test_90_days_uses_last_90_days(self):
        gaql = self._get_called_gaql(90)
        self.assertIn("LAST_90_DAYS", gaql)

    def test_unknown_days_defaults_to_last_30(self):
        gaql = self._get_called_gaql(45)
        self.assertIn("LAST_30_DAYS", gaql)


# ── Test 6: API error — no secret leak ────────────────────────────────────
class TestApiError(unittest.TestCase):

    def test_403_returns_error_no_token_in_response(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.json.return_value = {"error": {"status": "PERMISSION_DENIED", "message": "Denied"}}

        with patch("requests.post", return_value=mock_resp):
            result = _gads_searchstream_campaigns(
                "1234567890", "FAKE_TOKEN_SHOULD_NOT_APPEAR", "FAKE_DEV", "8924163684", days=30
            )

        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("status_code"), 403)
        result_str = json.dumps(result)
        self.assertNotIn("FAKE_TOKEN_SHOULD_NOT_APPEAR", result_str)
        self.assertNotIn("FAKE_DEV", result_str)

    def test_network_error_returns_error_dict(self):
        with patch("requests.post", side_effect=Exception("connection refused")):
            result = _gads_searchstream_campaigns(
                "1234567890", "T", "D", "8924163684", days=30
            )
        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("error"), "api_network_error")


# ── Test 7: Invalid account_id ────────────────────────────────────────────
class TestInvalidAccountId(unittest.TestCase):

    def test_rejects_empty_account_id(self):
        result = _gads_searchstream_campaigns("", "T", "D", "8924163684", days=30)
        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("error"), "invalid_account_id")

    def test_rejects_short_account_id(self):
        result = _gads_searchstream_campaigns("12345", "T", "D", "8924163684", days=30)
        self.assertFalse(result.get("success"))


# ── Test 8: GET /campaigns uses live API when api_validated ───────────────
class TestCampaignsRouteUsesLiveApi(unittest.TestCase):

    def setUp(self):
        _set_env()
        self.app = _app.app.test_client()
        self.app.testing = True
        _store_mock_token(user_id=1)

    def test_source_is_google_ads_api_when_validated(self):
        mock_token_resp = _mock_token_refresh()
        mock_search_resp = MagicMock()
        mock_search_resp.status_code = 200
        mock_search_resp.text = _build_mock_campaigns_json_array(2)

        with patch("requests.post", side_effect=[mock_token_resp, mock_search_resp]):
            resp = self.app.get("/api/connectors/google-ads/campaigns?account_id=1016047735&mcc_id=8924163684")

        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data.get("source"), "google_ads_api")
        self.assertTrue(data.get("connected_live"))
        self.assertFalse(data.get("connected_mock"))
        self.assertIsInstance(data.get("campaigns"), list)
        self.assertEqual(len(data["campaigns"]), 2)

    def test_summary_is_computed_from_live_campaigns(self):
        mock_token_resp = _mock_token_refresh()
        mock_search_resp = MagicMock()
        mock_search_resp.status_code = 200
        mock_search_resp.text = _build_mock_campaigns_json_array(2)

        with patch("requests.post", side_effect=[mock_token_resp, mock_search_resp]):
            resp = self.app.get("/api/connectors/google-ads/campaigns?account_id=1016047735&mcc_id=8924163684")

        data = json.loads(resp.data)
        summary = data.get("summary", {})
        self.assertIn("total_campaigns", summary)
        self.assertEqual(summary["total_campaigns"], 2)


# ── Test 9: login-customer-id uses mcc_id param ───────────────────────────
class TestLoginCustomerIdHeader(unittest.TestCase):

    def test_login_customer_id_is_mcc_id_when_provided(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = json.dumps([{"results": []}])

        with patch("requests.post", return_value=mock_resp) as mp:
            _gads_searchstream_campaigns(
                "1016047735", "FAKE_ACCESS", "FAKE_DEV", "8924163684", days=30
            )
            call_kwargs = mp.call_args[1]
            headers = call_kwargs.get("headers", {})
            self.assertEqual(headers.get("login-customer-id"), "8924163684")


# ── Test 10: Falls back to mock when no OAuth ─────────────────────────────
class TestCampaignsRouteNoAuth(unittest.TestCase):

    def setUp(self):
        _set_env()
        # Use fresh DB without any token
        os.environ["DATABASE"] = "/tmp/camarad_gads_phase2b_noauth.db"
        self.app = _app.app.test_client()
        self.app.testing = True

    def test_falls_back_to_mock_when_no_token(self):
        resp = self.app.get("/api/connectors/google-ads/campaigns?account_id=123-456-7890")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data.get("source"), "mock")
        self.assertFalse(data.get("connected_live"))

    def tearDown(self):
        os.environ["DATABASE"] = "/tmp/camarad_gads_phase2b_test.db"


# ── Test 11: Falls back to mock on API error ──────────────────────────────
class TestCampaignsRouteFallbackOnError(unittest.TestCase):

    def setUp(self):
        _set_env()
        self.app = _app.app.test_client()
        self.app.testing = True
        _store_mock_token(user_id=1)

    def test_falls_back_to_mock_on_403(self):
        mock_token_resp = _mock_token_refresh()
        mock_403 = MagicMock()
        mock_403.status_code = 403
        mock_403.json.return_value = {"error": {"status": "PERMISSION_DENIED"}}

        with patch("requests.post", side_effect=[mock_token_resp, mock_403]):
            resp = self.app.get("/api/connectors/google-ads/campaigns?account_id=123-456-7890")

        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        # Falls back to mock for '123-456-7890' (mock account)
        self.assertEqual(data.get("source"), "mock")


# ── Test 12: Response always has campaigns + summary ─────────────────────
class TestResponseShape(unittest.TestCase):

    def setUp(self):
        _set_env()
        self.app = _app.app.test_client()
        self.app.testing = True

    def test_mock_response_has_campaigns_and_summary(self):
        resp = self.app.get("/api/connectors/google-ads/campaigns?account_id=123-456-7890")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertIn("campaigns", data)
        self.assertIn("summary", data)
        self.assertIsInstance(data["campaigns"], list)
        self.assertIsInstance(data["summary"], dict)


if __name__ == "__main__":
    unittest.main(verbosity=2)
