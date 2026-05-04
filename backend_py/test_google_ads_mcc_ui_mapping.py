"""
Google Ads MCC UI Mapping Fix — Automated tests (Phase 2A.2).

Verifies that:
  - POST /mcc/hierarchy returns client_accounts and manager_accounts arrays
  - GET /mcc/hierarchy returns client_accounts and manager_accounts arrays
  - GET /accounts returns client_accounts separate from direct_access_accounts
  - selected_manager_customer_id flows through _gads_token_get_meta
  - Live mode: no fallback to direct_access_accounts as client_accounts
  - connectors.html JS contains correct placeholders and no stale mock phrases

Run:
    AUTH_REQUIRED=0 COOLBITS_GATEWAY_ENABLED=false DATABASE=/tmp/camarad_ui_mapping_test.db \
        python3 -m unittest test_google_ads_mcc_ui_mapping -v
"""
import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock

os.environ.setdefault("AUTH_REQUIRED", "0")
os.environ.setdefault("COOLBITS_GATEWAY_ENABLED", "false")
os.environ.setdefault("DATABASE", "/tmp/camarad_ui_mapping_test.db")

for _k in ("GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_DEVELOPER_TOKEN",
           "GOOGLE_ADS_REDIRECT_URI", "GOOGLE_ADS_SCOPES", "GOOGLE_ADS_LOGIN_CUSTOMER_ID"):
    os.environ.pop(_k, None)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as _app_module
from app import (
    app,
    _gads_token_store,
    _gads_token_get_meta,
    _gads_update_metadata,
    _gads_store_accessible_customers,
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


def _build_mock_hierarchy_json_array():
    """Build a JSON-array searchStream response with 1 manager + 2 client accounts."""
    chunks = [
        {
            "results": [{
                "customerClient": {
                    "resourceName": "customers/8924163684/customerClients/8924163684",
                    "clientCustomer": "customers/8924163684",
                    "descriptiveName": "Cool Bits Manager",
                    "manager": True,
                    "status": "ENABLED",
                    "level": "0",
                    "currencyCode": "USD",
                    "timeZone": "America/New_York",
                    "id": "8924163684",
                }
            }]
        },
        {
            "results": [
                {
                    "customerClient": {
                        "resourceName": "customers/8924163684/customerClients/1111111111",
                        "clientCustomer": "customers/1111111111",
                        "descriptiveName": "Client Alpha Ltd",
                        "manager": False,
                        "status": "ENABLED",
                        "level": "1",
                        "currencyCode": "USD",
                        "timeZone": "America/Chicago",
                        "id": "1111111111",
                    }
                },
                {
                    "customerClient": {
                        "resourceName": "customers/8924163684/customerClients/2222222222",
                        "clientCustomer": "customers/2222222222",
                        "descriptiveName": "Client Beta LLC",
                        "manager": False,
                        "status": "ENABLED",
                        "level": "1",
                        "currencyCode": "EUR",
                        "timeZone": "Europe/Bucharest",
                        "id": "2222222222",
                    }
                }
            ]
        },
    ]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = json.dumps(chunks)
    return mock_resp


def _mock_token_refresh():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "access_token": "REFRESHED_ACCESS_NOT_REAL",
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": "https://www.googleapis.com/auth/adwords",
    }
    return mock_resp


# ─── Test 1: POST /mcc/hierarchy response includes client_accounts + manager_accounts ─────

class TestHierarchyPostResponseShape(unittest.TestCase):
    """POST /mcc/hierarchy must return client_accounts and manager_accounts arrays."""

    def setUp(self):
        _set_gads_env()
        self.client = app.test_client()
        _store_mock_token(user_id=1)
        _gads_update_metadata(1, {"api_validated": True, "token_validated": True})

    def tearDown(self):
        _clear_gads_env()

    @patch("app.requests.post")
    def test_post_returns_client_accounts_array(self, mock_post):
        mock_post.side_effect = [_mock_token_refresh(), _build_mock_hierarchy_json_array()]
        resp = self.client.post(
            "/api/connectors/google-ads/mcc/hierarchy",
            json={"manager_customer_id": "8924163684"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))
        self.assertIn("client_accounts", data)
        self.assertIsInstance(data["client_accounts"], list)

    @patch("app.requests.post")
    def test_post_returns_manager_accounts_array(self, mock_post):
        mock_post.side_effect = [_mock_token_refresh(), _build_mock_hierarchy_json_array()]
        resp = self.client.post(
            "/api/connectors/google-ads/mcc/hierarchy",
            json={"manager_customer_id": "8924163684"},
        )
        data = resp.get_json()
        self.assertIn("manager_accounts", data)
        self.assertIsInstance(data["manager_accounts"], list)


# ─── Test 2: client_accounts excludes managers ───────────────────────────────

class TestClientAccountsExcludesManagers(unittest.TestCase):
    """client_accounts in POST response must not include manager accounts."""

    def setUp(self):
        _set_gads_env()
        self.client = app.test_client()
        _store_mock_token(user_id=1)
        _gads_update_metadata(1, {"api_validated": True, "token_validated": True})

    def tearDown(self):
        _clear_gads_env()

    @patch("app.requests.post")
    def test_client_accounts_has_no_managers(self, mock_post):
        mock_post.side_effect = [_mock_token_refresh(), _build_mock_hierarchy_json_array()]
        resp = self.client.post(
            "/api/connectors/google-ads/mcc/hierarchy",
            json={"manager_customer_id": "8924163684"},
        )
        data = resp.get_json()
        for acct in data.get("client_accounts", []):
            self.assertFalse(
                acct.get("is_manager") or acct.get("account_type") == "manager",
                f"Manager account found in client_accounts: {acct}",
            )

    @patch("app.requests.post")
    def test_client_accounts_count_matches_list(self, mock_post):
        mock_post.side_effect = [_mock_token_refresh(), _build_mock_hierarchy_json_array()]
        resp = self.client.post(
            "/api/connectors/google-ads/mcc/hierarchy",
            json={"manager_customer_id": "8924163684"},
        )
        data = resp.get_json()
        self.assertEqual(data.get("client_accounts_count", -1), len(data.get("client_accounts", [])))


# ─── Test 3: manager_accounts excludes client accounts ───────────────────────

class TestManagerAccountsExcludesClients(unittest.TestCase):
    """manager_accounts in POST response must not include client accounts."""

    def setUp(self):
        _set_gads_env()
        self.client = app.test_client()
        _store_mock_token(user_id=1)
        _gads_update_metadata(1, {"api_validated": True, "token_validated": True})

    def tearDown(self):
        _clear_gads_env()

    @patch("app.requests.post")
    def test_manager_accounts_has_no_clients(self, mock_post):
        mock_post.side_effect = [_mock_token_refresh(), _build_mock_hierarchy_json_array()]
        resp = self.client.post(
            "/api/connectors/google-ads/mcc/hierarchy",
            json={"manager_customer_id": "8924163684"},
        )
        data = resp.get_json()
        for acct in data.get("manager_accounts", []):
            self.assertTrue(
                acct.get("is_manager") or acct.get("account_type") == "manager",
                f"Client account found in manager_accounts: {acct}",
            )


# ─── Test 4: GET /accounts returns direct_access_accounts separately ─────────

class TestGetAccountsSeparatesDirectAccess(unittest.TestCase):
    """GET /accounts must return direct_access_accounts as its own array."""

    def setUp(self):
        _set_gads_env()
        self.client = app.test_client()
        _store_mock_token(user_id=1)
        _gads_update_metadata(1, {"api_validated": True, "token_validated": True})
        _gads_store_accessible_customers(1, ["1016047735", "3741586068"])

    def tearDown(self):
        _clear_gads_env()

    def test_get_accounts_has_direct_access_key(self):
        resp = self.client.get("/api/connectors/google-ads/accounts")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("direct_access_accounts", data)
        self.assertIsInstance(data["direct_access_accounts"], list)

    def test_get_accounts_has_mcc_accounts_key(self):
        resp = self.client.get("/api/connectors/google-ads/accounts")
        data = resp.get_json()
        self.assertIn("mcc_accounts", data)
        self.assertIsInstance(data["mcc_accounts"], list)


# ─── Test 5: GET /accounts live mode no fallback ─────────────────────────────

class TestGetAccountsNoFallbackInLiveMode(unittest.TestCase):
    """
    In live mode without hierarchy loaded, client_accounts must be empty —
    must not return direct_access_accounts as client_accounts.
    """

    def setUp(self):
        _set_gads_env()
        self.client = app.test_client()
        _store_mock_token(user_id=1)
        _gads_update_metadata(1, {"api_validated": True, "token_validated": True,
                                  "selected_manager_customer_id": None})
        _gads_store_accessible_customers(1, ["1016047735", "3741586068"])

    def tearDown(self):
        _clear_gads_env()

    def test_no_selected_manager_means_empty_client_accounts(self):
        resp = self.client.get("/api/connectors/google-ads/accounts")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("connected_live"))
        # Without hierarchy loaded there should be no mcc/client accounts
        self.assertEqual(data.get("mcc_accounts"), [])
        client_accounts = data.get("client_accounts", [])
        self.assertEqual(client_accounts, [])

    def test_accounts_compat_field_uses_direct_access_when_no_hierarchy(self):
        """Backward-compat 'accounts' field should be direct_access when no hierarchy."""
        resp = self.client.get("/api/connectors/google-ads/accounts")
        data = resp.get_json()
        # When hierarchy not loaded, compat accounts = direct_access
        direct_ids = {a["id"] for a in data.get("direct_access_accounts", [])}
        compat_ids = {a.get("id") for a in data.get("accounts", [])}
        self.assertEqual(direct_ids, compat_ids)


# ─── Test 6: selected_manager_customer_id flows through _gads_token_get_meta ─

class TestSelectedManagerFlowsThroughMeta(unittest.TestCase):
    """selected_manager_customer_id must be returned by _gads_token_get_meta."""

    def setUp(self):
        _set_gads_env()
        self.client = app.test_client()
        _store_mock_token(user_id=1)
        _gads_update_metadata(1, {"api_validated": True, "token_validated": True,
                                  "selected_manager_customer_id": "8924163684"})

    def tearDown(self):
        _clear_gads_env()

    def test_meta_includes_selected_manager_customer_id(self):
        meta = _gads_token_get_meta(1)
        self.assertIsNotNone(meta)
        self.assertEqual(meta.get("selected_manager_customer_id"), "8924163684")

    def test_get_accounts_uses_stored_manager(self):
        """GET /accounts must load hierarchy when selected_manager_customer_id is set."""
        # Store a hierarchy for this manager
        hierarchy_accounts = [
            {"customer_id": "1111111111", "resource_name": "customers/1111111111",
             "descriptive_name": "Client Alpha", "account_type": "client",
             "is_manager": False, "level": 1, "status": "ENABLED",
             "currency_code": "USD", "time_zone": "UTC"},
        ]
        _gads_store_customer_hierarchy(1, "8924163684", hierarchy_accounts)
        resp = self.client.get("/api/connectors/google-ads/accounts")
        data = resp.get_json()
        self.assertTrue(data.get("mcc_hierarchy_loaded"))
        self.assertTrue(len(data.get("mcc_accounts", [])) > 0)


# ─── Test 7: GET /accounts with hierarchy returns client_accounts ─────────────

class TestGetAccountsWithHierarchyReturnsClientAccounts(unittest.TestCase):
    """After hierarchy stored, GET /accounts returns non-empty client_accounts."""

    def setUp(self):
        _set_gads_env()
        self.client = app.test_client()
        _store_mock_token(user_id=1)
        _gads_update_metadata(1, {"api_validated": True, "token_validated": True,
                                  "selected_manager_customer_id": "8924163684"})
        hierarchy_accounts = [
            {"customer_id": "8924163684", "resource_name": "customers/8924163684",
             "descriptive_name": "Cool Bits Manager", "account_type": "manager",
             "is_manager": True, "level": 0, "status": "ENABLED",
             "currency_code": "USD", "time_zone": "America/New_York"},
            {"customer_id": "1111111111", "resource_name": "customers/1111111111",
             "descriptive_name": "Client Alpha", "account_type": "client",
             "is_manager": False, "level": 1, "status": "ENABLED",
             "currency_code": "USD", "time_zone": "America/Chicago"},
            {"customer_id": "2222222222", "resource_name": "customers/2222222222",
             "descriptive_name": "Client Beta", "account_type": "client",
             "is_manager": False, "level": 1, "status": "ENABLED",
             "currency_code": "EUR", "time_zone": "Europe/Bucharest"},
        ]
        _gads_store_customer_hierarchy(1, "8924163684", hierarchy_accounts)

    def tearDown(self):
        _clear_gads_env()

    def test_client_accounts_non_empty_after_hierarchy(self):
        resp = self.client.get("/api/connectors/google-ads/accounts")
        data = resp.get_json()
        self.assertIn("client_accounts", data)
        self.assertEqual(len(data["client_accounts"]), 2)

    def test_client_accounts_excludes_manager_in_get_accounts(self):
        resp = self.client.get("/api/connectors/google-ads/accounts")
        data = resp.get_json()
        for acct in data.get("client_accounts", []):
            self.assertFalse(acct.get("is_manager"),
                             f"Manager found in client_accounts: {acct}")


# ─── Test 8: connectors.html contains correct placeholder text ────────────────

class TestConnectorsHtmlPlaceholders(unittest.TestCase):
    """connectors.html must contain correct placeholder strings."""

    def setUp(self):
        template_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "templates", "connectors.html",
        )
        with open(template_path, "r", encoding="utf-8") as f:
            self.html = f.read()

    def test_contains_load_mcc_hierarchy_placeholder(self):
        self.assertIn("Load MCC Hierarchy first", self.html)

    def test_does_not_contain_mcc_filter_applied(self):
        self.assertNotIn("MCC filter applied", self.html)

    def test_contains_direct_access_dropdown_id(self):
        self.assertIn("gadsDirectAccessSelect", self.html)

    def test_contains_client_accounts_usage(self):
        self.assertIn("client_accounts", self.html)

    def test_contains_refreshaccounts_function(self):
        self.assertIn("function refreshAccounts", self.html)


# ─── Test 9: GET /accounts returns client_accounts key in live mode ───────────

class TestGetAccountsClientAccountsKeyPresent(unittest.TestCase):
    """GET /accounts in live mode must always return client_accounts key."""

    def setUp(self):
        _set_gads_env()
        self.client = app.test_client()
        _store_mock_token(user_id=1)
        _gads_update_metadata(1, {"api_validated": True, "token_validated": True})

    def tearDown(self):
        _clear_gads_env()

    def test_client_accounts_key_present(self):
        resp = self.client.get("/api/connectors/google-ads/accounts")
        data = resp.get_json()
        self.assertIn("client_accounts", data)

    def test_manager_accounts_key_present(self):
        resp = self.client.get("/api/connectors/google-ads/accounts")
        data = resp.get_json()
        self.assertIn("manager_accounts", data)


# ─── Test 10: GET /mcc/hierarchy returns client_accounts + manager_accounts ───

class TestGetHierarchyResponseShape(unittest.TestCase):
    """GET /mcc/hierarchy must return client_accounts and manager_accounts."""

    def setUp(self):
        _set_gads_env()
        self.client = app.test_client()
        _store_mock_token(user_id=1)
        _gads_update_metadata(1, {"api_validated": True, "token_validated": True,
                                  "selected_manager_customer_id": "8924163684"})
        hierarchy_accounts = [
            {"customer_id": "8924163684", "resource_name": "customers/8924163684",
             "descriptive_name": "Cool Bits Manager", "account_type": "manager",
             "is_manager": True, "level": 0, "status": "ENABLED",
             "currency_code": "USD", "time_zone": "America/New_York"},
            {"customer_id": "1111111111", "resource_name": "customers/1111111111",
             "descriptive_name": "Client Alpha", "account_type": "client",
             "is_manager": False, "level": 1, "status": "ENABLED",
             "currency_code": "USD", "time_zone": "UTC"},
        ]
        _gads_store_customer_hierarchy(1, "8924163684", hierarchy_accounts)

    def tearDown(self):
        _clear_gads_env()

    def test_get_hierarchy_returns_client_accounts(self):
        resp = self.client.get(
            "/api/connectors/google-ads/mcc/hierarchy?manager_customer_id=8924163684"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("client_accounts", data)
        self.assertIsInstance(data["client_accounts"], list)
        self.assertEqual(len(data["client_accounts"]), 1)
        self.assertEqual(data["client_accounts"][0]["customer_id"], "1111111111")

    def test_get_hierarchy_returns_manager_accounts(self):
        resp = self.client.get(
            "/api/connectors/google-ads/mcc/hierarchy?manager_customer_id=8924163684"
        )
        data = resp.get_json()
        self.assertIn("manager_accounts", data)
        self.assertIsInstance(data["manager_accounts"], list)
        self.assertEqual(len(data["manager_accounts"]), 1)
        self.assertEqual(data["manager_accounts"][0]["customer_id"], "8924163684")


if __name__ == "__main__":
    unittest.main(verbosity=2)
