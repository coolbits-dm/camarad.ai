"""Tests for Phase 2D: Google Ads Report Query, Metric Catalog, and Currency Normalization.

Run:
    cd /opt/camarad-repo/backend_py
    AUTH_REQUIRED=0 COOLBITS_GATEWAY_ENABLED=false DATABASE=/tmp/camarad_rq.db \
        python3 -m unittest test_google_ads_report_query -v
"""

import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure the package is importable when run as `python3 -m unittest`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_PATCH_PREFIX = "backend_py.app"

import backend_py.app as app_module
from backend_py.app import app


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _post_query(client, body):
    return client.post(
        "/api/connectors/google-ads/report/query",
        data=json.dumps(body),
        content_type="application/json",
    )


# ─── Metric Catalog ──────────────────────────────────────────────────────────

class TestMetricCatalog(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_catalog_returns_metrics(self):
        res = self.client.get("/api/connectors/google-ads/report/catalog")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIsInstance(data["metrics"], list)
        self.assertGreater(len(data["metrics"]), 0)

    def test_catalog_has_all_expected_metrics(self):
        res = self.client.get("/api/connectors/google-ads/report/catalog")
        data = res.get_json()
        keys = {m["key"] for m in data["metrics"]}
        required = {"cost", "impressions", "clicks", "ctr", "avg_cpc",
                    "conversions", "conversions_value", "roas", "cpa",
                    "conversion_rate", "all_conversions"}
        self.assertTrue(required.issubset(keys), f"Missing: {required - keys}")

    def test_catalog_has_dimensions(self):
        res = self.client.get("/api/connectors/google-ads/report/catalog")
        data = res.get_json()
        keys = {d["key"] for d in data["dimensions"]}
        self.assertIn("campaign", keys)
        self.assertIn("campaign_status", keys)
        self.assertIn("currency_code", keys)

    def test_catalog_has_date_ranges(self):
        res = self.client.get("/api/connectors/google-ads/report/catalog")
        data = res.get_json()
        self.assertIn("LAST_30_DAYS", data["date_ranges"])
        self.assertIn("LAST_7_DAYS", data["date_ranges"])

    def test_catalog_has_presets(self):
        res = self.client.get("/api/connectors/google-ads/report/catalog")
        data = res.get_json()
        preset_names = {p["name"] for p in data["presets"]}
        self.assertIn("Account Health", preset_names)
        self.assertIn("ROAS Leaders", preset_names)

    def test_catalog_currency_no_conversion(self):
        res = self.client.get("/api/connectors/google-ads/report/catalog")
        data = res.get_json()
        self.assertFalse(data["currency"]["conversion_supported"])

    def test_catalog_currency_sensitive_flagged(self):
        res = self.client.get("/api/connectors/google-ads/report/catalog")
        data = res.get_json()
        cost_metric = next(m for m in data["metrics"] if m["key"] == "cost")
        impressions_metric = next(m for m in data["metrics"] if m["key"] == "impressions")
        self.assertTrue(cost_metric["currency_sensitive"])
        self.assertFalse(impressions_metric["currency_sensitive"])


# ─── Safe Query Builder ───────────────────────────────────────────────────────

class TestSafeQueryBuilder(unittest.TestCase):
    def test_valid_query_returns_gaql(self):
        gaql, err = app_module._gads_build_safe_report_query(
            level="campaign",
            metrics=["cost", "clicks"],
            dimensions=["campaign", "campaign_status"],
            filters={},
            date_range="LAST_30_DAYS",
            sort="-cost",
            limit=50,
        )
        self.assertIsNone(err)
        self.assertIn("FROM campaign", gaql)
        self.assertIn("LAST_30_DAYS", gaql)
        self.assertIn("metrics.cost_micros", gaql)

    def test_invalid_metric_rejected(self):
        gaql, err = app_module._gads_build_safe_report_query(
            level="campaign",
            metrics=["malicious_field"],
            dimensions=[],
            filters={},
            date_range="LAST_30_DAYS",
            sort="-cost",
            limit=50,
        )
        self.assertIsNone(gaql)
        self.assertIn("malicious_field", err)

    def test_invalid_dimension_rejected(self):
        gaql, err = app_module._gads_build_safe_report_query(
            level="campaign",
            metrics=["cost"],
            dimensions=["DROP TABLE users"],
            filters={},
            date_range="LAST_30_DAYS",
            sort="-cost",
            limit=50,
        )
        self.assertIsNone(gaql)
        self.assertIsNotNone(err)

    def test_invalid_date_range_rejected(self):
        gaql, err = app_module._gads_build_safe_report_query(
            level="campaign",
            metrics=["cost"],
            dimensions=["campaign"],
            filters={},
            date_range="LAST_365_DAYS",
            sort="-cost",
            limit=50,
        )
        self.assertIsNone(gaql)
        self.assertIn("date_range", err)

    def test_limit_capped_at_200(self):
        gaql, err = app_module._gads_build_safe_report_query(
            level="campaign",
            metrics=["cost"],
            dimensions=[],
            filters={},
            date_range="LAST_7_DAYS",
            sort="-cost",
            limit=9999,
        )
        self.assertIsNone(err)
        self.assertIn("LIMIT 200", gaql)

    def test_status_filter_injected_safely(self):
        gaql, err = app_module._gads_build_safe_report_query(
            level="campaign",
            metrics=["cost"],
            dimensions=[],
            filters={"campaign_status": "ENABLED"},
            date_range="LAST_30_DAYS",
            sort="-cost",
            limit=50,
        )
        self.assertIsNone(err)
        self.assertIn("campaign.status", gaql)

    def test_invalid_filter_key_rejected(self):
        gaql, err = app_module._gads_build_safe_report_query(
            level="campaign",
            metrics=["cost"],
            dimensions=[],
            filters={"__proto__": "exploit"},
            date_range="LAST_30_DAYS",
            sort="-cost",
            limit=50,
        )
        self.assertIsNone(gaql)
        self.assertIsNotNone(err)

    def test_invalid_level_rejected(self):
        gaql, err = app_module._gads_build_safe_report_query(
            level="keyword",
            metrics=["cost"],
            dimensions=[],
            filters={},
            date_range="LAST_30_DAYS",
            sort="-cost",
            limit=50,
        )
        self.assertIsNone(gaql)
        self.assertIn("level", err)

    def test_currency_code_always_in_select(self):
        gaql, err = app_module._gads_build_safe_report_query(
            level="campaign",
            metrics=["impressions"],
            dimensions=[],
            filters={},
            date_range="LAST_7_DAYS",
            sort="-impressions",
            limit=10,
        )
        self.assertIsNone(err)
        self.assertIn("customer.currency_code", gaql)


# ─── Report Query Endpoint ────────────────────────────────────────────────────

class TestReportQueryEndpoint(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    @patch(f"{_PATCH_PREFIX}.get_current_user_id", return_value=1)
    @patch(f"{_PATCH_PREFIX}._gads_token_get_meta", return_value=None)
    def test_mock_fallback_returns_rows(self, mock_meta, mock_uid):
        res = _post_query(self.client, {
            "customer_id": "123-456-7890",
            "date_range": "LAST_30_DAYS",
            "metrics": ["cost", "clicks", "conversions"],
            "dimensions": ["campaign", "campaign_status"],
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["source"], "mock")
        self.assertIsInstance(data["rows"], list)
        self.assertGreater(len(data["rows"]), 0)

    @patch(f"{_PATCH_PREFIX}.get_current_user_id", return_value=1)
    @patch(f"{_PATCH_PREFIX}._gads_token_get_meta", return_value=None)
    def test_response_has_currency_context(self, mock_meta, mock_uid):
        res = _post_query(self.client, {
            "customer_id": "123-456-7890",
            "metrics": ["cost"],
            "dimensions": ["campaign"],
        })
        data = res.get_json()
        self.assertIn("currency", data)
        self.assertIn("currency_code", data["currency"])
        self.assertIn("conversion_applied", data["currency"])
        self.assertFalse(data["currency"]["conversion_applied"])

    @patch(f"{_PATCH_PREFIX}.get_current_user_id", return_value=1)
    @patch(f"{_PATCH_PREFIX}._gads_token_get_meta", return_value=None)
    def test_mock_ron_account_has_ron_currency(self, mock_meta, mock_uid):
        res = _post_query(self.client, {
            "customer_id": "123-456-7890",  # RON mock account
            "metrics": ["cost"],
            "dimensions": ["campaign"],
        })
        data = res.get_json()
        # Currency must be RON from mock account (not USD)
        self.assertEqual(data["currency"]["currency_code"], "RON")

    @patch(f"{_PATCH_PREFIX}.get_current_user_id", return_value=1)
    @patch(f"{_PATCH_PREFIX}._gads_token_get_meta", return_value=None)
    def test_mock_eur_account_has_eur_currency(self, mock_meta, mock_uid):
        res = _post_query(self.client, {
            "customer_id": "234-567-8901",  # EUR mock account
            "metrics": ["cost"],
            "dimensions": ["campaign"],
        })
        data = res.get_json()
        self.assertEqual(data["currency"]["currency_code"], "EUR")

    @patch(f"{_PATCH_PREFIX}.get_current_user_id", return_value=1)
    @patch(f"{_PATCH_PREFIX}._gads_token_get_meta", return_value=None)
    def test_response_has_totals(self, mock_meta, mock_uid):
        res = _post_query(self.client, {
            "customer_id": "123-456-7890",
            "metrics": ["cost", "clicks", "conversions", "roas", "cpa"],
            "dimensions": ["campaign"],
        })
        data = res.get_json()
        self.assertIn("totals", data)
        self.assertIn("cost", data["totals"])
        self.assertIn("roas", data["totals"])

    @patch(f"{_PATCH_PREFIX}.get_current_user_id", return_value=1)
    @patch(f"{_PATCH_PREFIX}._gads_token_get_meta", return_value=None)
    def test_raw_gaql_rejected(self, mock_meta, mock_uid):
        res = _post_query(self.client, {
            "customer_id": "123-456-7890",
            "gaql": "SELECT campaign.id FROM campaign",
        })
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "raw_gaql_not_allowed")

    @patch(f"{_PATCH_PREFIX}.get_current_user_id", return_value=1)
    @patch(f"{_PATCH_PREFIX}._gads_token_get_meta", return_value=None)
    def test_raw_query_param_rejected(self, mock_meta, mock_uid):
        res = _post_query(self.client, {
            "customer_id": "123-456-7890",
            "query": "SELECT campaign.id FROM campaign",
        })
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data["success"])

    @patch(f"{_PATCH_PREFIX}.get_current_user_id", return_value=1)
    @patch(f"{_PATCH_PREFIX}._gads_token_get_meta", return_value=None)
    def test_invalid_metric_returns_400(self, mock_meta, mock_uid):
        res = _post_query(self.client, {
            "customer_id": "123-456-7890",
            "metrics": ["evil_metric"],
            "dimensions": ["campaign"],
        })
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertIn("evil_metric", data["message"])

    @patch(f"{_PATCH_PREFIX}.get_current_user_id", return_value=1)
    @patch(f"{_PATCH_PREFIX}._gads_token_get_meta", return_value=None)
    def test_missing_customer_id_returns_400(self, mock_meta, mock_uid):
        res = _post_query(self.client, {
            "metrics": ["cost"],
        })
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "customer_id_required")

    @patch(f"{_PATCH_PREFIX}.get_current_user_id", return_value=1)
    @patch(f"{_PATCH_PREFIX}._gads_token_get_meta", return_value=None)
    def test_response_has_query_plan(self, mock_meta, mock_uid):
        res = _post_query(self.client, {
            "customer_id": "123-456-7890",
            "metrics": ["cost", "clicks"],
            "dimensions": ["campaign"],
            "date_range": "LAST_7_DAYS",
            "sort": "-cost",
            "limit": 10,
        })
        data = res.get_json()
        self.assertIn("query_plan", data)
        self.assertEqual(data["query_plan"]["date_range"], "LAST_7_DAYS")

    @patch(f"{_PATCH_PREFIX}.get_current_user_id", return_value=1)
    @patch(f"{_PATCH_PREFIX}._gads_token_get_meta", return_value=None)
    def test_source_is_mock_when_not_connected(self, mock_meta, mock_uid):
        res = _post_query(self.client, {
            "customer_id": "123-456-7890",
            "metrics": ["cost"],
            "dimensions": ["campaign"],
        })
        data = res.get_json()
        self.assertEqual(data["source"], "mock")

    @patch(f"{_PATCH_PREFIX}.get_current_user_id", return_value=1)
    @patch(f"{_PATCH_PREFIX}._gads_token_get_meta", return_value=None)
    def test_warnings_list_present(self, mock_meta, mock_uid):
        res = _post_query(self.client, {
            "customer_id": "123-456-7890",
            "metrics": ["cost"],
            "dimensions": ["campaign"],
        })
        data = res.get_json()
        self.assertIn("warnings", data)
        self.assertIsInstance(data["warnings"], list)


# ─── Currency Helpers ─────────────────────────────────────────────────────────

class TestCurrencyHelpers(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True

    def test_resolve_currency_from_api_code(self):
        with app.test_request_context("/"):
            ctx = app_module._gads_resolve_currency_context(
                customer_id="1234567890",
                api_currency_code="EUR",
            )
        self.assertEqual(ctx["currency_code"], "EUR")
        self.assertEqual(ctx["currency_source"], "google_ads_api_query")
        self.assertFalse(ctx["conversion_applied"])

    def test_resolve_currency_from_rows(self):
        rows = [
            {"currency_code": "RON", "cost": 100},
            {"currency_code": "RON", "cost": 200},
        ]
        with app.test_request_context("/"):
            ctx = app_module._gads_resolve_currency_context(
                customer_id="1234567890",
                rows=rows,
            )
        self.assertEqual(ctx["currency_code"], "RON")
        self.assertFalse(ctx["mixed_currency"])

    def test_mixed_currency_detected(self):
        rows = [
            {"currency_code": "USD", "cost": 100},
            {"currency_code": "EUR", "cost": 200},
        ]
        with app.test_request_context("/"):
            ctx = app_module._gads_resolve_currency_context(
                customer_id="1234567890",
                rows=rows,
            )
        self.assertTrue(ctx["mixed_currency"])
        self.assertIsNotNone(ctx["warning"])

    def test_unknown_currency_is_null_not_usd(self):
        with app.test_request_context("/"):
            ctx = app_module._gads_resolve_currency_context(
                customer_id="9999999999",
            )
        # currency_code must be None, never "USD"
        self.assertIsNone(ctx["currency_code"])
        self.assertIsNotNone(ctx["warning"])

    def test_api_code_takes_priority_over_rows(self):
        rows = [{"currency_code": "EUR", "cost": 100}]
        with app.test_request_context("/"):
            ctx = app_module._gads_resolve_currency_context(
                customer_id="1234567890",
                api_currency_code="GBP",
                rows=rows,
            )
        self.assertEqual(ctx["currency_code"], "GBP")
        self.assertEqual(ctx["currency_source"], "google_ads_api_query")


# ─── Report Totals ────────────────────────────────────────────────────────────

class TestReportTotals(unittest.TestCase):
    def _rows(self):
        return [
            {"cost": 100, "impressions": 1000, "clicks": 50, "conversions": 5,
             "conversions_value": 500, "all_conversions": 5,
             "campaign_status": "ENABLED"},
            {"cost": 50, "impressions": 500, "clicks": 20, "conversions": 2,
             "conversions_value": 200, "all_conversions": 2,
             "campaign_status": "PAUSED"},
        ]

    def test_sum_cost(self):
        totals = app_module._gads_compute_report_totals(self._rows(), ["cost"])
        self.assertAlmostEqual(totals["cost"], 150.0)

    def test_sum_conversions(self):
        totals = app_module._gads_compute_report_totals(self._rows(), ["conversions"])
        self.assertAlmostEqual(totals["conversions"], 7.0)

    def test_derived_roas(self):
        totals = app_module._gads_compute_report_totals(
            self._rows(), ["cost", "conversions_value", "roas"]
        )
        # roas = 700 / 150 = 4.67
        self.assertAlmostEqual(totals["roas"], round(700 / 150, 2))

    def test_derived_cpa(self):
        totals = app_module._gads_compute_report_totals(
            self._rows(), ["cost", "conversions", "cpa"]
        )
        self.assertAlmostEqual(totals["cpa"], round(150 / 7, 2))

    def test_active_campaigns_count(self):
        totals = app_module._gads_compute_report_totals(
            self._rows(), ["active_campaigns", "total_campaigns"]
        )
        self.assertEqual(totals["active_campaigns"], 1)
        self.assertEqual(totals["total_campaigns"], 2)


# ─── Existing Endpoints: Currency Field Added ─────────────────────────────────

class TestExistingEndpointsCurrencyField(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    @patch(f"{_PATCH_PREFIX}.get_current_user_id", return_value=1)
    @patch(f"{_PATCH_PREFIX}._gads_token_get_meta", return_value=None)
    def test_overview_has_currency(self, mock_meta, mock_uid):
        res = self.client.get(
            "/api/connectors/google-ads/overview?customer_id=123-456-7890"
        )
        data = res.get_json()
        self.assertIn("currency", data)
        self.assertIn("currency_code", data["currency"])

    @patch(f"{_PATCH_PREFIX}.get_current_user_id", return_value=1)
    @patch(f"{_PATCH_PREFIX}._gads_token_get_meta", return_value=None)
    def test_diagnostics_has_currency(self, mock_meta, mock_uid):
        res = self.client.get(
            "/api/connectors/google-ads/diagnostics?customer_id=123-456-7890"
        )
        data = res.get_json()
        self.assertIn("currency", data)

    @patch(f"{_PATCH_PREFIX}.get_current_user_id", return_value=1)
    @patch(f"{_PATCH_PREFIX}._gads_token_get_meta", return_value=None)
    def test_ai_brief_has_currency(self, mock_meta, mock_uid):
        res = self.client.get(
            "/api/connectors/google-ads/ai-brief?customer_id=123-456-7890"
        )
        data = res.get_json()
        self.assertIn("currency", data)

    @patch(f"{_PATCH_PREFIX}.get_current_user_id", return_value=1)
    @patch(f"{_PATCH_PREFIX}._gads_token_get_meta", return_value=None)
    def test_overview_ron_account_currency(self, mock_meta, mock_uid):
        res = self.client.get(
            "/api/connectors/google-ads/overview?customer_id=123-456-7890"
        )
        data = res.get_json()
        self.assertEqual(data["currency"]["currency_code"], "RON")

    @patch(f"{_PATCH_PREFIX}.get_current_user_id", return_value=1)
    @patch(f"{_PATCH_PREFIX}._gads_token_get_meta", return_value=None)
    def test_overview_currency_no_conversion(self, mock_meta, mock_uid):
        res = self.client.get(
            "/api/connectors/google-ads/overview?customer_id=123-456-7890"
        )
        data = res.get_json()
        self.assertFalse(data["currency"]["conversion_applied"])


if __name__ == "__main__":
    unittest.main()
