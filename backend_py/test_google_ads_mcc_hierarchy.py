"""
Google Ads MCC Hierarchy Phase 2A.1 — Automated tests.

Tests the customer_client hierarchy loading endpoints, account grouping,
and removal of misleading mock behavior. Read-only only; no mutations.

Run:
    AUTH_REQUIRED=0 COOLBITS_GATEWAY_ENABLED=false DATABASE=/tmp/camarad_mcc_hierarchy_test.db \
        python3 -m unittest test_google_ads_mcc_hierarchy -v
"""
import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock

os.environ.setdefault("AUTH_REQUIRED", "0")
os.environ.setdefault("COOLBITS_GATEWAY_ENABLED", "false")
os.environ.setdefault("DATABASE", "/tmp/camarad_mcc_hierarchy_test.db")

for _k in ("GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_DEVELOPER_TOKEN",
           "GOOGLE_ADS_REDIRECT_URI", "GOOGLE_ADS_SCOPES", "GOOGLE_ADS_LOGIN_CUSTOMER_ID"):
    os.environ.pop(_k, None)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as _app_module
from app import (
    app,
    _gads_token_store,
    _gads_token_get_meta,
    _gads_token_revoke,
    _gads_update_metadata,
    _gads_store_accessible_customers,
    _gads_fetch_customer_hierarchy,
    _gads_store_customer_hierarchy,
    _gads_get_customer_hierarchy,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

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
    return _gads_token_store(user_id=user_id, token_data={
        "refresh_token": "FAKE_REFRESH_NOT_REAL",
        "access_token": "FAKE_ACCESS_NOT_REAL",
        "token_type": "Bearer",
        "scope": "https://www.googleapis.com/auth/adwords",
    })


def _build_mock_hierarchy_ndjson(include_manager=True, include_client=True):
    """Build a NDJSON searchStream response with one manager and one client account."""
    rows = []
    if include_manager:
        rows.append({
            "results": [{
                "customerClient": {
                    "resourceName": "customers/1234567890/customerClients/9876543210",
                    "clientCustomer": "customers/9876543210",
                    "descriptiveName": "Manager Sub-Account",
                    "manager": True,
                    "status": "ENABLED",
                    "level": "1",
                    "currencyCode": "USD",
                    "timeZone": "America/New_York",
                    "id": "9876543210",
                }
            }]
        })
    if include_client:
        rows.append({
            "results": [{
                "customerClient": {
                    "resourceName": "customers/1234567890/customerClients/5551234567",
                    "clientCustomer": "customers/5551234567",
                    "descriptiveName": "Test Client Account",
                    "manager": False,
                    "status": "ENABLED",
                    "level": "2",
                    "currencyCode": "EUR",
                    "timeZone": "Europe/Bucharest",
                    "id": "5551234567",
                }
            }]
        })
    return "\n".join(json.dumps(r) for r in rows)


def _mock_token_refresh():
    """Return a mock requests.Response for a successful token refresh."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "access_token": "REFRESHED_ACCESS_NOT_REAL",
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": "https://www.googleapis.com/auth/adwords",
    }
    return mock_resp


def _mock_searchstream_response(ndjson_body):
    """Build a mock response matching the real searchStream JSON array format."""
    # ndjson_body may be NDJSON lines — convert to JSON array for realism
    chunks = []
    for line in ndjson_body.strip().splitlines():
        line = line.strip()
        if line:
            try:
                chunks.append(json.loads(line))
            except Exception:
                pass
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = json.dumps(chunks) if chunks else "[]"
    return mock_resp


# ─── Test Classes ─────────────────────────────────────────────────────────────


class TestHierarchyEndpointNoToken(unittest.TestCase):
    """Test 1: POST /mcc/hierarchy without any OAuth token → oauth_required."""

    def setUp(self):
        _set_gads_env()
        _gads_token_revoke(user_id=1)

    def tearDown(self):
        _clear_gads_env()

    def test_no_token_returns_oauth_required(self):
        with app.test_client() as c:
            c.set_cookie("camarad_user_id", "1")
            resp = c.post(
                "/api/connectors/google-ads/mcc/hierarchy",
                json={"manager_customer_id": "123456789012"},
            )
        data = resp.get_json()
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("status"), "oauth_required")


class TestHierarchyEndpointNotValidated(unittest.TestCase):
    """Test 2: POST /mcc/hierarchy with token but api_validated=False → validation_required."""

    def setUp(self):
        _set_gads_env()
        _store_mock_token(user_id=1)
        # Token stored but not validated
        _gads_update_metadata(1, {"api_validated": False})

    def tearDown(self):
        _clear_gads_env()
        _gads_token_revoke(user_id=1)

    def test_not_validated_returns_validation_required(self):
        with app.test_client() as c:
            c.set_cookie("camarad_user_id", "1")
            resp = c.post(
                "/api/connectors/google-ads/mcc/hierarchy",
                json={"manager_customer_id": "123456789012"},
            )
        data = resp.get_json()
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("status"), "validation_required")


class TestHierarchyEndpointInvalidManagerId(unittest.TestCase):
    """Test 3: POST /mcc/hierarchy with invalid manager_customer_id → 400."""

    def setUp(self):
        _set_gads_env()
        _store_mock_token(user_id=1)
        _gads_update_metadata(1, {"api_validated": True})

    def tearDown(self):
        _clear_gads_env()
        _gads_token_revoke(user_id=1)

    def test_empty_id_is_rejected(self):
        with app.test_client() as c:
            c.set_cookie("camarad_user_id", "1")
            resp = c.post(
                "/api/connectors/google-ads/mcc/hierarchy",
                json={"manager_customer_id": ""},
            )
        data = resp.get_json()
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(data.get("status"), "invalid_manager_customer_id")

    def test_alphabetic_id_is_rejected(self):
        with app.test_client() as c:
            c.set_cookie("camarad_user_id", "1")
            resp = c.post(
                "/api/connectors/google-ads/mcc/hierarchy",
                json={"manager_customer_id": "abc-def-ghij"},
            )
        data = resp.get_json()
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(data.get("status"), "invalid_manager_customer_id")

    def test_too_short_id_is_rejected(self):
        with app.test_client() as c:
            c.set_cookie("camarad_user_id", "1")
            resp = c.post(
                "/api/connectors/google-ads/mcc/hierarchy",
                json={"manager_customer_id": "12345"},
            )
        data = resp.get_json()
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(data.get("status"), "invalid_manager_customer_id")


class TestHierarchyStoresRows(unittest.TestCase):
    """Test 4: Successful hierarchy response stores rows in DB."""

    def setUp(self):
        _set_gads_env()
        _store_mock_token(user_id=1)
        _gads_update_metadata(1, {"api_validated": True})

    def tearDown(self):
        _clear_gads_env()
        _gads_token_revoke(user_id=1)

    @patch("app.requests.post")
    def test_stores_hierarchy_rows(self, mock_post):
        ndjson = _build_mock_hierarchy_ndjson(include_manager=True, include_client=True)
        mock_post.side_effect = [
            _mock_token_refresh(),
            _mock_searchstream_response(ndjson),
        ]
        with app.test_client() as c:
            c.set_cookie("camarad_user_id", "1")
            resp = c.post(
                "/api/connectors/google-ads/mcc/hierarchy",
                json={"manager_customer_id": "1234567890"},
            )
        data = resp.get_json()
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(data.get("success"))
        self.assertGreater(data.get("accounts_count", 0), 0)

        # Verify stored in DB
        stored = _gads_get_customer_hierarchy(1, "1234567890")
        self.assertGreater(len(stored), 0)


class TestHierarchyClassifiesManagerAccounts(unittest.TestCase):
    """Test 5: Accounts with manager=True are classified as account_type='manager'."""

    def setUp(self):
        _set_gads_env()

    def tearDown(self):
        _clear_gads_env()

    @patch("app.requests.post")
    def test_manager_true_classified_as_manager(self, mock_post):
        ndjson = _build_mock_hierarchy_ndjson(include_manager=True, include_client=False)
        mock_post.return_value = _mock_searchstream_response(ndjson)

        result = _gads_fetch_customer_hierarchy(
            manager_customer_id="1234567890",
            access_token="FAKE_ACCESS_NOT_REAL",
            developer_token="test_dev_token_NOT_REAL",
            login_customer_id="1234567890",
        )

        self.assertTrue(result.get("success"))
        accounts = result.get("accounts", [])
        self.assertGreater(len(accounts), 0)
        manager_accounts = [a for a in accounts if a["account_type"] == "manager"]
        self.assertGreater(len(manager_accounts), 0)
        self.assertEqual(manager_accounts[0]["customer_id"], "9876543210")


class TestHierarchyClassifiesClientAccounts(unittest.TestCase):
    """Test 6: Accounts with manager=False are classified as account_type='client'."""

    def setUp(self):
        _set_gads_env()

    def tearDown(self):
        _clear_gads_env()

    @patch("app.requests.post")
    def test_manager_false_classified_as_client(self, mock_post):
        ndjson = _build_mock_hierarchy_ndjson(include_manager=False, include_client=True)
        mock_post.return_value = _mock_searchstream_response(ndjson)

        result = _gads_fetch_customer_hierarchy(
            manager_customer_id="1234567890",
            access_token="FAKE_ACCESS_NOT_REAL",
            developer_token="test_dev_token_NOT_REAL",
            login_customer_id="1234567890",
        )

        self.assertTrue(result.get("success"))
        accounts = result.get("accounts", [])
        client_accounts = [a for a in accounts if a["account_type"] == "client"]
        self.assertGreater(len(client_accounts), 0)
        self.assertEqual(client_accounts[0]["customer_id"], "5551234567")


class TestHierarchyResponseCountFields(unittest.TestCase):
    """Test 7: POST response includes manager_accounts_count and client_accounts_count."""

    def setUp(self):
        _set_gads_env()
        _store_mock_token(user_id=1)
        _gads_update_metadata(1, {"api_validated": True})

    def tearDown(self):
        _clear_gads_env()
        _gads_token_revoke(user_id=1)

    @patch("app.requests.post")
    def test_response_has_count_fields(self, mock_post):
        ndjson = _build_mock_hierarchy_ndjson(include_manager=True, include_client=True)
        mock_post.side_effect = [
            _mock_token_refresh(),
            _mock_searchstream_response(ndjson),
        ]
        with app.test_client() as c:
            c.set_cookie("camarad_user_id", "1")
            resp = c.post(
                "/api/connectors/google-ads/mcc/hierarchy",
                json={"manager_customer_id": "1234567890"},
            )
        data = resp.get_json()
        self.assertEqual(resp.status_code, 200)
        self.assertIn("manager_accounts_count", data)
        self.assertIn("client_accounts_count", data)
        self.assertIsInstance(data["manager_accounts_count"], int)
        self.assertIsInstance(data["client_accounts_count"], int)
        self.assertGreaterEqual(data["manager_accounts_count"], 0)
        self.assertGreaterEqual(data["client_accounts_count"], 0)


class TestAccountsEndpointGrouped(unittest.TestCase):
    """Test 8: GET /accounts in live mode returns direct_access_accounts and mcc_accounts separately."""

    def setUp(self):
        _set_gads_env()
        _store_mock_token(user_id=1)
        _gads_update_metadata(1, {"api_validated": True})
        # Seed some accessible customers
        _gads_store_accessible_customers(1, ["1111111111", "2222222222"])

    def tearDown(self):
        _clear_gads_env()
        _gads_token_revoke(user_id=1)

    def test_accounts_response_has_grouped_keys(self):
        with app.test_client() as c:
            c.set_cookie("camarad_user_id", "1")
            resp = c.get("/api/connectors/google-ads/accounts")
        data = resp.get_json()
        self.assertEqual(resp.status_code, 200)
        self.assertIn("direct_access_accounts", data)
        self.assertIn("mcc_accounts", data)
        self.assertIn("mcc_hierarchy_loaded", data)
        self.assertTrue(data.get("connected_live"))
        self.assertIsInstance(data["direct_access_accounts"], list)
        self.assertIsInstance(data["mcc_accounts"], list)


class TestAccountsEndpointNoMockInLiveMode(unittest.TestCase):
    """Test 9: Live mode does NOT return E-Shop/TechStart/Global Reach mock accounts."""

    MOCK_NAMES = {"E-Shop Plus GmbH", "TechStart Berlin", "Global Reach Inc."}

    def setUp(self):
        _set_gads_env()
        _store_mock_token(user_id=1)
        _gads_update_metadata(1, {"api_validated": True})
        _gads_store_accessible_customers(1, ["1234567890"])

    def tearDown(self):
        _clear_gads_env()
        _gads_token_revoke(user_id=1)

    def test_no_mock_account_names_in_live_mode(self):
        with app.test_client() as c:
            c.set_cookie("camarad_user_id", "1")
            resp = c.get("/api/connectors/google-ads/accounts")
        data = resp.get_json()
        self.assertTrue(data.get("connected_live"))
        all_names = {a.get("name", "") for a in (data.get("accounts") or [])}
        all_names |= {a.get("name", "") for a in (data.get("direct_access_accounts") or [])}
        for mock_name in self.MOCK_NAMES:
            self.assertNotIn(mock_name, all_names, f"Mock account '{mock_name}' found in live mode response")

    def test_source_is_cached_google_ads_api_in_live_mode(self):
        with app.test_client() as c:
            c.set_cookie("camarad_user_id", "1")
            resp = c.get("/api/connectors/google-ads/accounts")
        data = resp.get_json()
        self.assertEqual(data.get("source"), "cached_google_ads_api")
        self.assertFalse(data.get("live_data"))
        self.assertTrue(data.get("cache"))
        self.assertFalse(data.get("fresh"))


class TestNoMccFilterAppliedString(unittest.TestCase):
    """Test 10: 'MCC filter applied' string removed from template."""

    def test_mcc_filter_applied_not_in_template(self):
        template_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "templates", "connectors.html",
        )
        with open(template_path, "r", encoding="utf-8") as fh:
            content = fh.read()
        self.assertNotIn(
            "MCC filter applied",
            content,
            "Template still contains 'MCC filter applied' — remove it.",
        )

    def test_gads_apply_mcc_id_function_removed(self):
        template_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "templates", "connectors.html",
        )
        with open(template_path, "r", encoding="utf-8") as fh:
            content = fh.read()
        self.assertNotIn(
            "function gadsApplyMccId",
            content,
            "Template still contains 'gadsApplyMccId' function.",
        )


class TestTemplateHasLoadMccHierarchyButton(unittest.TestCase):
    """Test 11: Template includes 'Load MCC Hierarchy' button."""

    def test_template_has_load_mcc_hierarchy(self):
        template_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "templates", "connectors.html",
        )
        with open(template_path, "r", encoding="utf-8") as fh:
            content = fh.read()
        self.assertIn(
            "Load MCC Hierarchy",
            content,
            "Template is missing 'Load MCC Hierarchy' button text.",
        )
        self.assertIn(
            "gadsLoadMccHierarchy",
            content,
            "Template is missing 'gadsLoadMccHierarchy' JS function.",
        )


class TestTemplateHasDirectAndClientSections(unittest.TestCase):
    """Test 12: Template includes 'Directly Accessible Accounts' and 'Client Account' sections."""

    def test_template_has_directly_accessible_accounts(self):
        template_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "templates", "connectors.html",
        )
        with open(template_path, "r", encoding="utf-8") as fh:
            content = fh.read()
        self.assertIn(
            "Directly Accessible Accounts",
            content,
            "Template missing 'Directly Accessible Accounts' section.",
        )
        self.assertIn(
            "Client Account",
            content,
            "Template missing 'Client Account' section.",
        )


class TestApiErrorsAreSafe(unittest.TestCase):
    """Test 13: API error responses do not expose tokens, keys, or secrets."""

    def setUp(self):
        _set_gads_env()
        _store_mock_token(user_id=1)
        _gads_update_metadata(1, {"api_validated": True})

    def tearDown(self):
        _clear_gads_env()
        _gads_token_revoke(user_id=1)

    @patch("app.requests.post")
    def test_403_response_does_not_expose_token(self, mock_post):
        # Token refresh succeeds, but searchStream returns 403
        mock_refresh = _mock_token_refresh()
        mock_403 = MagicMock()
        mock_403.status_code = 403
        mock_403.text = json.dumps({"error": {"code": 403, "message": "The caller does not have permission."}})
        mock_post.side_effect = [mock_refresh, mock_403]

        with app.test_client() as c:
            c.set_cookie("camarad_user_id", "1")
            resp = c.post(
                "/api/connectors/google-ads/mcc/hierarchy",
                json={"manager_customer_id": "1234567890"},
            )
        data = resp.get_json()
        raw_body = resp.get_data(as_text=True)

        # Status must be error
        self.assertFalse(data.get("success"))
        # No real access token, refresh token, or client secret should appear in body
        self.assertNotIn("FAKE_ACCESS_NOT_REAL", raw_body)
        self.assertNotIn("FAKE_REFRESH_NOT_REAL", raw_body)
        self.assertNotIn("test_client_secret_NOT_REAL", raw_body)
        self.assertNotIn("test_dev_token_NOT_REAL", raw_body)


class TestNoWriteMutationCalls(unittest.TestCase):
    """Test 14: Hierarchy loading never calls a write/mutation Google Ads API endpoint."""

    FORBIDDEN_MUTATE_PATHS = [
        "/googleAds:mutate",
        "/campaigns:mutate",
        "/adGroups:mutate",
        "/ads:mutate",
        "/batchJobs",
        "/customerExtensionSettings",
    ]

    def setUp(self):
        _set_gads_env()
        _store_mock_token(user_id=1)
        _gads_update_metadata(1, {"api_validated": True})

    def tearDown(self):
        _clear_gads_env()
        _gads_token_revoke(user_id=1)

    @patch("app.requests.post")
    def test_no_mutate_call_during_hierarchy_load(self, mock_post):
        ndjson = _build_mock_hierarchy_ndjson()
        mock_post.side_effect = [
            _mock_token_refresh(),
            _mock_searchstream_response(ndjson),
        ]
        with app.test_client() as c:
            c.set_cookie("camarad_user_id", "1")
            c.post(
                "/api/connectors/google-ads/mcc/hierarchy",
                json={"manager_customer_id": "1234567890"},
            )

        for call in mock_post.call_args_list:
            url = str(call[0][0]) if call[0] else str(call[1].get("url", ""))
            for forbidden in self.FORBIDDEN_MUTATE_PATHS:
                self.assertNotIn(forbidden, url, f"Forbidden mutate path '{forbidden}' was called: {url}")


class TestValidateFlowStillWorks(unittest.TestCase):
    """Test 15: Existing validate flow still sets connected_live=True after ListAccessibleCustomers."""

    def setUp(self):
        _set_gads_env()
        _store_mock_token(user_id=1)
        _gads_update_metadata(1, {"api_validated": False})

    def tearDown(self):
        _clear_gads_env()
        _gads_token_revoke(user_id=1)

    @patch("app.requests.get")
    @patch("app.requests.post")
    def test_validate_sets_connected_live(self, mock_post, mock_get):
        # Token refresh
        mock_post.return_value = _mock_token_refresh()
        # ListAccessibleCustomers
        mock_accessible = MagicMock()
        mock_accessible.status_code = 200
        mock_accessible.json.return_value = {
            "resourceNames": ["customers/1234567890", "customers/9876543210"]
        }
        mock_get.return_value = mock_accessible

        with app.test_client() as c:
            c.set_cookie("camarad_user_id", "1")
            resp = c.post("/api/connectors/google-ads/validate")
        data = resp.get_json()

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(data.get("success"))
        self.assertTrue(data.get("connected_live"))
        self.assertTrue(data.get("api_validated"))
        self.assertGreater(data.get("accessible_customers_count", 0), 0)

        # Verify metadata persisted
        meta = _gads_token_get_meta(1)
        self.assertTrue(meta.get("api_validated"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
