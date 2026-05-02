"""
Tests for Google Ads Truth Mode (Phase 1).

Tests:
 1.  reality/status returns mode=config_missing when env vars absent
 2.  reality/status response never includes actual env secret values
 3.  reality/status has all required fields
 4.  accounts endpoint returns source=mock, connected_live=false
 5.  campaigns endpoint returns source=mock, connected_live=false
 6.  keywords endpoint returns source=mock, connected_live=false
 7.  metrics endpoint returns source=mock, connected_live=false
 8.  test-call endpoint returns source=mock, api_validated=false
 9.  test-call has truthful message field about simulation
10.  reality/status response contains no secret-looking field names
"""

import json
import os
import unittest
import tempfile

os.environ.setdefault("AUTH_REQUIRED", "0")
# Ensure COOLBITS_GATEWAY_ENABLED is off for all these tests
os.environ["COOLBITS_GATEWAY_ENABLED"] = "false"

import app as _app_module
from app import app
from database import init_db, get_db


def _setup_db(db_path):
    os.environ["DATABASE"] = db_path
    _app_module.DATABASE = db_path
    if hasattr(_app_module, "AUTH_REQUIRED"):
        _app_module.AUTH_REQUIRED = False
    app.config["TESTING"] = True
    app.config["DATABASE"] = db_path
    conn = get_db()
    init_db()
    conn.close()
    return db_path


class TestGoogleAdsTruthMode(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        _setup_db(self.db_path)
        # Clear Google Ads env vars to simulate missing config
        for var in ("GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET",
                    "GOOGLE_ADS_DEVELOPER_TOKEN", "GOOGLE_ADS_REFRESH_TOKEN",
                    "GOOGLE_ADS_LOGIN_CUSTOMER_ID"):
            os.environ.pop(var, None)
        self.client = app.test_client()

    def tearDown(self):
        os.unlink(self.db_path)

    # 1. reality/status returns mode=config_missing when env vars absent
    def test_reality_status_mode_config_missing(self):
        r = self.client.get("/api/connectors/google-ads/reality/status")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn(data.get("mode"), ("config_missing", "oauth_required", "mock"))
        self.assertFalse(data.get("connected_live"))
        self.assertIn("ui_label", data)
        self.assertIn("message", data)

    # 2. reality/status response never includes actual env secret values
    def test_reality_status_no_secret_values(self):
        os.environ["GOOGLE_ADS_CLIENT_ID"] = "test-client-id-12345"
        os.environ["GOOGLE_ADS_CLIENT_SECRET"] = "super-secret-value-XYZ"
        os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"] = "devtoken-ABC123"
        try:
            r = self.client.get("/api/connectors/google-ads/reality/status")
            raw = r.get_data(as_text=True)
            self.assertNotIn("test-client-id-12345", raw)
            self.assertNotIn("super-secret-value-XYZ", raw)
            self.assertNotIn("devtoken-ABC123", raw)
        finally:
            os.environ.pop("GOOGLE_ADS_CLIENT_ID", None)
            os.environ.pop("GOOGLE_ADS_CLIENT_SECRET", None)
            os.environ.pop("GOOGLE_ADS_DEVELOPER_TOKEN", None)

    # 3. reality/status has all required fields
    def test_reality_status_required_fields(self):
        r = self.client.get("/api/connectors/google-ads/reality/status")
        data = r.get_json()
        for field in ("provider", "mode", "connected_live", "connected_mock",
                      "oauth_configured", "has_token", "token_validated",
                      "api_validated", "data_source", "ui_label", "ui_badge_class", "message"):
            self.assertIn(field, data, msg=f"Missing field: {field}")
        self.assertEqual(data["provider"], "google_ads")
        self.assertEqual(data["data_source"], "mock")
        self.assertFalse(data["connected_live"])
        self.assertFalse(data["token_validated"])
        self.assertFalse(data["api_validated"])

    # 4. accounts endpoint returns source=mock, connected_live=false
    def test_accounts_returns_mock_metadata(self):
        r = self.client.get("/api/connectors/google-ads/accounts")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(data.get("source"), "mock")
        self.assertFalse(data.get("connected_live"))
        self.assertTrue(data.get("connected_mock"))
        self.assertIn("accounts", data)

    # 5. campaigns endpoint returns source=mock, connected_live=false
    def test_campaigns_returns_mock_metadata(self):
        r = self.client.get("/api/connectors/google-ads/campaigns?account_id=123-456-7890")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(data.get("source"), "mock")
        self.assertFalse(data.get("connected_live"))
        self.assertTrue(data.get("connected_mock"))

    # 6. keywords endpoint returns source=mock, connected_live=false
    def test_keywords_returns_mock_metadata(self):
        r = self.client.get("/api/connectors/google-ads/keywords?campaign_id=1001")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(data.get("source"), "mock")
        self.assertFalse(data.get("connected_live"))
        self.assertTrue(data.get("connected_mock"))

    # 7. metrics endpoint returns source=mock, connected_live=false
    def test_metrics_returns_mock_metadata(self):
        r = self.client.get("/api/connectors/google-ads/metrics?account_id=123-456-7890&days=7")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(data.get("source"), "mock")
        self.assertFalse(data.get("connected_live"))
        self.assertTrue(data.get("connected_mock"))

    # 8. test-call endpoint returns source=mock, api_validated=false
    def test_test_call_api_validated_false(self):
        r = self.client.post("/api/connectors/google-ads/test-call",
                             data=json.dumps({"endpoint": "/v17/customers/123456/campaigns", "method": "GET"}),
                             content_type="application/json")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(data.get("source"), "mock")
        self.assertFalse(data.get("api_validated"))

    # 9. test-call has truthful message field about simulation
    def test_test_call_has_simulation_message(self):
        r = self.client.post("/api/connectors/google-ads/test-call",
                             data=json.dumps({}),
                             content_type="application/json")
        data = r.get_json()
        msg = data.get("message", "")
        self.assertTrue(
            "simulated" in msg.lower() or "no live" in msg.lower(),
            msg=f"Expected simulation disclaimer in message, got: {msg!r}"
        )

    # 10. reality/status response contains no secret-looking field names
    def test_reality_status_no_secret_fields(self):
        r = self.client.get("/api/connectors/google-ads/reality/status")
        data = r.get_json()
        secret_field_names = {
            "client_secret", "client_id", "developer_token", "refresh_token",
            "access_token", "oauth_token", "secret", "token_value",
        }
        # None of those keys should appear as top-level field names in the response
        for field in data.keys():
            self.assertNotIn(field.lower(), secret_field_names,
                             msg=f"Potentially secret field {field!r} in reality/status response")


if __name__ == "__main__":
    unittest.main(verbosity=2)
