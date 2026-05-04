"""
Google Ads API Validation Phase 2A — Automated tests.
Run:
    AUTH_REQUIRED=0 COOLBITS_GATEWAY_ENABLED=false DATABASE=/tmp/camarad_gads_api_validation_test.db \
        python3 -m unittest test_google_ads_api_validation -v
"""
import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock

os.environ.setdefault("AUTH_REQUIRED", "0")
os.environ.setdefault("COOLBITS_GATEWAY_ENABLED", "false")
os.environ.setdefault("DATABASE", "/tmp/camarad_gads_api_validation_test.db")
# Ensure Google Ads env vars NOT set by default
for _k in ("GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_DEVELOPER_TOKEN",
           "GOOGLE_ADS_REDIRECT_URI", "GOOGLE_ADS_SCOPES", "GOOGLE_ADS_LOGIN_CUSTOMER_ID"):
    os.environ.pop(_k, None)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as _app_module
from app import (
    app,
    _gads_oauth_configured,
    _gads_token_store,
    _gads_token_get_meta,
    _gads_token_revoke,
    _gads_update_metadata,
    _gads_get_fresh_access_token,
    _gads_list_accessible_customers,
    _gads_store_accessible_customers,
    _gads_get_accessible_customers,
)


def _set_gads_env(**kwargs):
    defaults = {
        "GOOGLE_ADS_CLIENT_ID": "test_client_id",
        "GOOGLE_ADS_CLIENT_SECRET": "test_client_secret_NOT_REAL",
        "GOOGLE_ADS_DEVELOPER_TOKEN": "test_dev_token_NOT_REAL",
        "GOOGLE_ADS_REDIRECT_URI": "https://camarad.ai/api/connectors/google-ads/oauth/callback",
    }
    defaults.update(kwargs)
    for k, v in defaults.items():
        os.environ[k] = v
    return defaults


def _clear_gads_env():
    for _k in ("GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_DEVELOPER_TOKEN",
               "GOOGLE_ADS_REDIRECT_URI", "GOOGLE_ADS_SCOPES", "GOOGLE_ADS_LOGIN_CUSTOMER_ID"):
        os.environ.pop(_k, None)


def _store_mock_token(user_id=1):
    """Store a fake encrypted refresh_token for a test user."""
    return _gads_token_store(user_id=user_id, token_data={
        "refresh_token": "FAKE_REFRESH_TOKEN_NOT_REAL",
        "access_token": "FAKE_ACCESS_TOKEN_NOT_REAL",
        "token_type": "Bearer",
        "scope": "https://www.googleapis.com/auth/adwords",
    })


_MOCK_LIST_ACCESSIBLE_RESPONSE = {
    "resourceNames": [
        "customers/1234567890",
        "customers/9876543210",
    ]
}


class TestValidateWithoutToken(unittest.TestCase):
    """Test 1: validate without token returns oauth_required."""

    def setUp(self):
        _set_gads_env()
        _gads_token_revoke(user_id=1)

    def tearDown(self):
        _clear_gads_env()

    def test_validate_without_token_returns_oauth_required(self):
        with app.test_client() as c:
            r = c.post("/api/connectors/google-ads/validate")
        self.assertEqual(r.status_code, 400)
        data = json.loads(r.data)
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("status"), "oauth_required")
        self.assertNotEqual(data.get("connected_live"), True)


class TestValidateMissingConfig(unittest.TestCase):
    """Test 2: validate with missing developer_token/config returns config_missing."""

    def setUp(self):
        _clear_gads_env()

    def tearDown(self):
        _clear_gads_env()

    def test_validate_missing_config_returns_config_missing(self):
        with app.test_client() as c:
            r = c.post("/api/connectors/google-ads/validate")
        self.assertEqual(r.status_code, 400)
        data = json.loads(r.data)
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("status"), "config_missing")


class TestTokenRefresh(unittest.TestCase):
    """Test 3: validate refreshes expired token using refresh_token without exposing token."""

    def setUp(self):
        _set_gads_env()
        _store_mock_token(user_id=1)

    def tearDown(self):
        _clear_gads_env()
        _gads_token_revoke(user_id=1)

    @patch("app.requests.post")
    @patch("app.requests.get")
    def test_validate_calls_token_refresh(self, mock_get, mock_post):
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {"access_token": "FRESH_TOKEN_NOT_REAL", "token_type": "Bearer"}
        mock_post.return_value = mock_post_resp

        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = _MOCK_LIST_ACCESSIBLE_RESPONSE
        mock_get.return_value = mock_get_resp

        with app.test_client() as c:
            r = c.post("/api/connectors/google-ads/validate")
        data = json.loads(r.data)
        # Verify token refresh was attempted
        self.assertTrue(mock_post.called)
        # Verify access_token NOT in response
        resp_str = json.dumps(data)
        self.assertNotIn("FRESH_TOKEN_NOT_REAL", resp_str)
        self.assertNotIn("FAKE_REFRESH_TOKEN", resp_str)

    @patch("app.requests.post")
    def test_validate_token_refresh_failure_returns_error(self, mock_post):
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 401
        mock_post.return_value = mock_post_resp

        with app.test_client() as c:
            r = c.post("/api/connectors/google-ads/validate")
        self.assertEqual(r.status_code, 400)
        data = json.loads(r.data)
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("status"), "token_refresh_failed")
        self.assertFalse(data.get("connected_live", True))


class TestListAccessibleCustomersHeaders(unittest.TestCase):
    """Test 4: validate calls ListAccessibleCustomers with correct headers, values not exposed."""

    def setUp(self):
        _set_gads_env()
        _store_mock_token(user_id=1)

    def tearDown(self):
        _clear_gads_env()
        _gads_token_revoke(user_id=1)

    @patch("app.requests.post")
    @patch("app.requests.get")
    def test_validate_calls_list_accessible_customers(self, mock_get, mock_post):
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {"access_token": "FRESH_HEADER_TOKEN_NOT_REAL", "token_type": "Bearer"}
        mock_post.return_value = mock_post_resp

        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = _MOCK_LIST_ACCESSIBLE_RESPONSE
        mock_get.return_value = mock_get_resp

        with app.test_client() as c:
            c.post("/api/connectors/google-ads/validate")

        # Verify GET was called (ListAccessibleCustomers)
        self.assertTrue(mock_get.called)
        call_args = mock_get.call_args
        url = call_args[0][0] if call_args[0] else call_args.kwargs.get("url", "")
        # URL should be Google Ads API
        self.assertIn("googleads.googleapis.com", url)
        self.assertIn("listAccessibleCustomers", url)
        # Headers should have Authorization and developer-token
        headers = call_args[1].get("headers", {}) if call_args[1] else {}
        self.assertIn("Authorization", headers)
        self.assertIn("developer-token", headers)
        # Values must not be printed in test output — only check presence
        self.assertTrue(headers["Authorization"].startswith("Bearer "))
        self.assertTrue(len(headers["developer-token"]) > 0)


class TestAccessibleCustomersStorage(unittest.TestCase):
    """Test 5: successful ListAccessibleCustomers stores accessible customers."""

    def setUp(self):
        _set_gads_env()
        _store_mock_token(user_id=1)

    def tearDown(self):
        _clear_gads_env()
        _gads_token_revoke(user_id=1)

    @patch("app.requests.post")
    @patch("app.requests.get")
    def test_accessible_customers_stored_after_validation(self, mock_get, mock_post):
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {"access_token": "FRESH_STORE_TOKEN_NOT_REAL", "token_type": "Bearer"}
        mock_post.return_value = mock_post_resp

        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = _MOCK_LIST_ACCESSIBLE_RESPONSE
        mock_get.return_value = mock_get_resp

        with app.test_client() as c:
            c.post("/api/connectors/google-ads/validate")

        customers = _gads_get_accessible_customers(user_id=1)
        self.assertGreater(len(customers), 0)
        ids = [c["customer_id"] for c in customers]
        self.assertIn("1234567890", ids)
        self.assertIn("9876543210", ids)


class TestValidationSetsConnectedLive(unittest.TestCase):
    """Test 6: successful validation sets api_validated=true and connected_live=true."""

    def setUp(self):
        _set_gads_env()
        _store_mock_token(user_id=1)

    def tearDown(self):
        _clear_gads_env()
        _gads_token_revoke(user_id=1)

    @patch("app.requests.post")
    @patch("app.requests.get")
    def test_successful_validation_connected_live(self, mock_get, mock_post):
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {"access_token": "FRESH_VALIDATE_TOKEN_NOT_REAL", "token_type": "Bearer"}
        mock_post.return_value = mock_post_resp

        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = _MOCK_LIST_ACCESSIBLE_RESPONSE
        mock_get.return_value = mock_get_resp

        with app.test_client() as c:
            r = c.post("/api/connectors/google-ads/validate")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertTrue(data.get("success"))
        self.assertTrue(data.get("api_validated"))
        self.assertTrue(data.get("connected_live"))
        self.assertGreater(data.get("accessible_customers_count", 0), 0)
        self.assertIsInstance(data.get("customers"), list)
        self.assertGreater(len(data["customers"]), 0)


class TestRealityStatusConnectedLive(unittest.TestCase):
    """Test 7: reality/status returns connected_live only after api_validated."""

    def setUp(self):
        _set_gads_env()
        _store_mock_token(user_id=1)

    def tearDown(self):
        _clear_gads_env()
        _gads_token_revoke(user_id=1)

    def test_reality_status_token_stored_before_validation(self):
        with app.test_client() as c:
            r = c.get("/api/connectors/google-ads/reality/status")
        data = json.loads(r.data)
        self.assertEqual(data.get("mode"), "token_stored")
        self.assertFalse(data.get("connected_live"))
        self.assertFalse(data.get("api_validated"))

    @patch("app.requests.post")
    @patch("app.requests.get")
    def test_reality_status_connected_live_after_validation(self, mock_get, mock_post):
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {"access_token": "FRESH_REALITY_TOKEN_NOT_REAL", "token_type": "Bearer"}
        mock_post.return_value = mock_post_resp

        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = _MOCK_LIST_ACCESSIBLE_RESPONSE
        mock_get.return_value = mock_get_resp

        with app.test_client() as c:
            c.post("/api/connectors/google-ads/validate")
            r = c.get("/api/connectors/google-ads/reality/status")
        data = json.loads(r.data)
        self.assertEqual(data.get("mode"), "connected_live")
        self.assertTrue(data.get("connected_live"))
        self.assertTrue(data.get("api_validated"))
        self.assertFalse(data.get("connected_mock"))
        self.assertEqual(data.get("data_source"), "google_ads_api")
        self.assertGreaterEqual(data.get("accessible_customers_count", 0), 1)


class TestAccountsEndpoint(unittest.TestCase):
    """Test 8: accounts endpoint returns source=google_ads_api after validation."""

    def setUp(self):
        _set_gads_env()
        _store_mock_token(user_id=1)

    def tearDown(self):
        _clear_gads_env()
        _gads_token_revoke(user_id=1)

    @patch("app.requests.post")
    @patch("app.requests.get")
    def test_accounts_returns_live_source_after_validation(self, mock_get, mock_post):
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {"access_token": "FRESH_ACCT_TOKEN_NOT_REAL", "token_type": "Bearer"}
        mock_post.return_value = mock_post_resp

        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = _MOCK_LIST_ACCESSIBLE_RESPONSE
        mock_get.return_value = mock_get_resp

        with app.test_client() as c:
            c.post("/api/connectors/google-ads/validate")
            r = c.get("/api/connectors/google-ads/accounts")
        data = json.loads(r.data)
        self.assertEqual(data.get("source"), "google_ads_api")
        self.assertTrue(data.get("connected_live"))
        self.assertFalse(data.get("connected_mock"))
        ids = [a["id"] for a in data.get("accounts", [])]
        self.assertIn("1234567890", ids)


class TestTokenStoredNoMockEShop(unittest.TestCase):
    """Test 9: token_stored mode does not expose mock E-Shop account as live."""

    def setUp(self):
        _set_gads_env()
        _store_mock_token(user_id=1)

    def tearDown(self):
        _clear_gads_env()
        _gads_token_revoke(user_id=1)

    def test_token_stored_accounts_returns_empty_not_mock(self):
        with app.test_client() as c:
            r = c.get("/api/connectors/google-ads/accounts")
        data = json.loads(r.data)
        # Must NOT return E-Shop or mock accounts as live
        self.assertEqual(data.get("source"), "none")
        self.assertFalse(data.get("connected_live"))
        self.assertEqual(data.get("accounts"), [])
        # Check no E-Shop account present
        account_names = [a.get("name", "") for a in data.get("accounts", [])]
        self.assertFalse(any("E-Shop" in n for n in account_names))


class TestFailedApiResponseError(unittest.TestCase):
    """Test 10: failed Google Ads API response returns api_error, connected_live=false."""

    def setUp(self):
        _set_gads_env()
        _store_mock_token(user_id=1)

    def tearDown(self):
        _clear_gads_env()
        _gads_token_revoke(user_id=1)

    @patch("app.requests.post")
    @patch("app.requests.get")
    def test_failed_api_call_returns_api_error(self, mock_get, mock_post):
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {"access_token": "FRESH_FAIL_TOKEN_NOT_REAL", "token_type": "Bearer"}
        mock_post.return_value = mock_post_resp

        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 403
        mock_get_resp.json.return_value = {
            "error": {
                "message": "DEVELOPER_TOKEN_NOT_APPROVED",
                "status": "PERMISSION_DENIED",
            }
        }
        mock_get.return_value = mock_get_resp

        with app.test_client() as c:
            r = c.post("/api/connectors/google-ads/validate")
        self.assertEqual(r.status_code, 400)
        data = json.loads(r.data)
        self.assertFalse(data.get("success"))
        self.assertFalse(data.get("connected_live", True))
        self.assertFalse(data.get("api_validated", True))
        # Safe error message present
        self.assertIn("message", data)
        # No secret values in response
        resp_str = json.dumps(data)
        self.assertNotIn("FRESH_FAIL_TOKEN_NOT_REAL", resp_str)
        self.assertNotIn("FAKE_REFRESH_TOKEN", resp_str)


class TestUiTemplateMessages(unittest.TestCase):
    """Test 11: UI template contains correct token_stored/pending validation message."""

    def test_template_contains_token_stored_pending_message(self):
        import os
        tpl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "connectors.html")
        with open(tpl_path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("API validation pending", content)
        self.assertIn("Validate Access", content)
        self.assertIn("token_stored", content)

    def test_template_contains_connected_live_mode(self):
        import os
        tpl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "connectors.html")
        with open(tpl_path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("connected_live", content)


class TestNoSecretsInResponses(unittest.TestCase):
    """Test 12: no response includes access_token, refresh_token, developer_token, client_secret."""

    def setUp(self):
        _set_gads_env()
        _store_mock_token(user_id=1)

    def tearDown(self):
        _clear_gads_env()
        _gads_token_revoke(user_id=1)

    @patch("app.requests.post")
    @patch("app.requests.get")
    def test_no_secrets_in_validate_response(self, mock_get, mock_post):
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {"access_token": "NOSECRET_ACCESS_TOKEN_LEAK_CHECK", "token_type": "Bearer"}
        mock_post.return_value = mock_post_resp

        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = _MOCK_LIST_ACCESSIBLE_RESPONSE
        mock_get.return_value = mock_get_resp

        with app.test_client() as c:
            r = c.post("/api/connectors/google-ads/validate")
        resp_str = r.data.decode("utf-8")
        self.assertNotIn("NOSECRET_ACCESS_TOKEN_LEAK_CHECK", resp_str)
        self.assertNotIn("FAKE_REFRESH_TOKEN", resp_str)
        self.assertNotIn("test_client_secret_NOT_REAL", resp_str)
        self.assertNotIn("test_dev_token_NOT_REAL", resp_str)

    @patch("app.requests.post")
    @patch("app.requests.get")
    def test_no_secrets_in_reality_status_response(self, mock_get, mock_post):
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {"access_token": "STATUS_ACCESS_TOKEN_SHOULD_NOT_APPEAR", "token_type": "Bearer"}
        mock_post.return_value = mock_post_resp

        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = _MOCK_LIST_ACCESSIBLE_RESPONSE
        mock_get.return_value = mock_get_resp

        with app.test_client() as c:
            c.post("/api/connectors/google-ads/validate")
            r = c.get("/api/connectors/google-ads/reality/status")
        resp_str = r.data.decode("utf-8")
        self.assertNotIn("STATUS_ACCESS_TOKEN_SHOULD_NOT_APPEAR", resp_str)
        self.assertNotIn("FAKE_REFRESH_TOKEN", resp_str)
        self.assertNotIn("test_client_secret_NOT_REAL", resp_str)

    @patch("app.requests.post")
    @patch("app.requests.get")
    def test_no_secrets_in_accounts_response(self, mock_get, mock_post):
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {"access_token": "ACCOUNTS_ACCESS_TOKEN_SHOULD_NOT_APPEAR", "token_type": "Bearer"}
        mock_post.return_value = mock_post_resp

        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = _MOCK_LIST_ACCESSIBLE_RESPONSE
        mock_get.return_value = mock_get_resp

        with app.test_client() as c:
            c.post("/api/connectors/google-ads/validate")
            r = c.get("/api/connectors/google-ads/accounts")
        resp_str = r.data.decode("utf-8")
        self.assertNotIn("ACCOUNTS_ACCESS_TOKEN_SHOULD_NOT_APPEAR", resp_str)
        self.assertNotIn("FAKE_REFRESH_TOKEN", resp_str)


class TestTestCallSimulated(unittest.TestCase):
    """Test 13: test-call in token_stored mode says validation pending, not live."""

    def setUp(self):
        _set_gads_env()
        _store_mock_token(user_id=1)

    def tearDown(self):
        _clear_gads_env()
        _gads_token_revoke(user_id=1)

    def test_test_call_token_stored_says_validation_pending(self):
        with app.test_client() as c:
            r = c.post("/api/connectors/google-ads/test-call", json={"endpoint": "/v17/customers/123/campaigns"})
        data = json.loads(r.data)
        self.assertFalse(data.get("api_validated"))
        self.assertIn("source", data)
        self.assertIn(data["source"], ("mock", "simulated"))
        self.assertIn("validation pending", data.get("message", "").lower())

    @patch("app.requests.post")
    @patch("app.requests.get")
    def test_test_call_after_validation_is_simulated_not_live(self, mock_get, mock_post):
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {"access_token": "TESTCALL_TOKEN_NOT_REAL", "token_type": "Bearer"}
        mock_post.return_value = mock_post_resp

        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = _MOCK_LIST_ACCESSIBLE_RESPONSE
        mock_get.return_value = mock_get_resp

        with app.test_client() as c:
            c.post("/api/connectors/google-ads/validate")
            r = c.post("/api/connectors/google-ads/test-call", json={"endpoint": "/v17/customers/123/campaigns"})
        data = json.loads(r.data)
        self.assertTrue(data.get("api_validated"))
        self.assertEqual(data.get("source"), "simulated")
        self.assertIn("Phase 2B", data.get("message", ""))


class TestNoMutationEndpointCalled(unittest.TestCase):
    """Test 14: no mutation endpoint is called during validation."""

    def setUp(self):
        _set_gads_env()
        _store_mock_token(user_id=1)

    def tearDown(self):
        _clear_gads_env()
        _gads_token_revoke(user_id=1)

    @patch("app.requests.post")
    @patch("app.requests.get")
    def test_no_mutation_endpoints_called(self, mock_get, mock_post):
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {"access_token": "MUTATION_CHECK_TOKEN_NOT_REAL", "token_type": "Bearer"}
        mock_post.return_value = mock_post_resp

        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = _MOCK_LIST_ACCESSIBLE_RESPONSE
        mock_get.return_value = mock_get_resp

        with app.test_client() as c:
            c.post("/api/connectors/google-ads/validate")

        # Only one GET should have been called (ListAccessibleCustomers)
        self.assertEqual(mock_get.call_count, 1)
        get_url = mock_get.call_args[0][0] if mock_get.call_args[0] else ""
        self.assertIn("listAccessibleCustomers", get_url)

        # POST should only have been called for token refresh (oauth2.googleapis.com)
        for call in mock_post.call_args_list:
            call_url = call[0][0] if call[0] else ""
            self.assertIn("oauth2.googleapis.com", call_url)
            # Must NOT include any Google Ads API mutation paths
            self.assertNotIn("googleads.googleapis.com", call_url)
            self.assertNotIn("mutate", call_url.lower())
            self.assertNotIn("create", call_url.lower())


# ── Unit tests for helpers ──────────────────────────────────────────────────

class TestGadsListAccessibleCustomersHelper(unittest.TestCase):
    """Unit tests for _gads_list_accessible_customers helper."""

    def test_success_returns_customer_ids(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"resourceNames": ["customers/1234567890", "customers/0987654321"]}
        with patch("app.requests.get", return_value=mock_resp):
            result = _gads_list_accessible_customers("FAKE_ACCESS", "FAKE_DEV")
        self.assertTrue(result["success"])
        self.assertIn("1234567890", result["customer_ids"])
        self.assertIn("0987654321", result["customer_ids"])
        self.assertEqual(result["count"], 2)

    def test_api_error_returns_safe_message(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.json.return_value = {"error": {"message": "Token not approved.", "status": "PERMISSION_DENIED"}}
        with patch("app.requests.get", return_value=mock_resp):
            result = _gads_list_accessible_customers("FAKE_ACCESS", "FAKE_DEV")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "google_ads_api_error")
        self.assertEqual(result["status_code"], 403)
        # Result must not contain the fake access token
        resp_str = json.dumps(result)
        self.assertNotIn("FAKE_ACCESS", resp_str)
        self.assertNotIn("FAKE_DEV", resp_str)

    def test_network_error_returns_safe_message(self):
        with patch("app.requests.get", side_effect=Exception("Connection refused")):
            result = _gads_list_accessible_customers("FAKE_ACCESS", "FAKE_DEV")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "api_network_error")


class TestGadsStoreAccessibleCustomers(unittest.TestCase):
    """Unit tests for _gads_store_accessible_customers helper."""

    def test_store_and_retrieve(self):
        _gads_store_accessible_customers(user_id=8881, customer_ids=["1112223334", "5556667778"])
        customers = _gads_get_accessible_customers(user_id=8881)
        ids = [c["customer_id"] for c in customers]
        self.assertIn("1112223334", ids)
        self.assertIn("5556667778", ids)

    def test_store_marks_old_as_not_seen(self):
        _gads_store_accessible_customers(user_id=8882, customer_ids=["1111111111"])
        _gads_store_accessible_customers(user_id=8882, customer_ids=["2222222222"])
        customers = _gads_get_accessible_customers(user_id=8882)
        ids = [c["customer_id"] for c in customers]
        # Only the new batch should be active
        self.assertIn("2222222222", ids)
        self.assertNotIn("1111111111", ids)

    def test_store_empty_list_returns_zero(self):
        count = _gads_store_accessible_customers(user_id=8883, customer_ids=[])
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
