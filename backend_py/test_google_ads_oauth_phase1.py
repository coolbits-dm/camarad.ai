"""
Google Ads OAuth Phase 1 — Automated tests.
Run:
    AUTH_REQUIRED=0 COOLBITS_GATEWAY_ENABLED=false DATABASE=/tmp/camarad_gads_oauth_test.db \
        python3 -m unittest test_google_ads_oauth_phase1 -v
"""
import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock

os.environ.setdefault("AUTH_REQUIRED", "0")
os.environ.setdefault("COOLBITS_GATEWAY_ENABLED", "false")
os.environ.setdefault("DATABASE", "/tmp/camarad_gads_oauth_test.db")
# Ensure Google Ads env vars NOT set for most tests
for _k in ("GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_DEVELOPER_TOKEN",
           "GOOGLE_ADS_REDIRECT_URI", "GOOGLE_ADS_SCOPES"):
    os.environ.pop(_k, None)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as _app_module
from app import app, _gads_oauth_configured, _gads_oauth_config_internal, \
    _gads_store_oauth_state, _gads_validate_oauth_state, _gads_mark_oauth_state_used, \
    _gads_token_store, _gads_token_get_meta, _gads_token_revoke


def _set_gads_env(**kwargs):
    defaults = {
        "GOOGLE_ADS_CLIENT_ID": "test_client_id",
        "GOOGLE_ADS_CLIENT_SECRET": "test_client_secret",
        "GOOGLE_ADS_DEVELOPER_TOKEN": "test_dev_token",
    }
    defaults.update(kwargs)
    return defaults


class TestGadsOAuthConfigDetection(unittest.TestCase):
    def test_config_missing_when_no_env_vars(self):
        for k in ("GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_DEVELOPER_TOKEN"):
            os.environ.pop(k, None)
        self.assertFalse(_gads_oauth_configured())

    def test_config_present_when_all_vars_set(self):
        with patch.dict(os.environ, _set_gads_env()):
            self.assertTrue(_gads_oauth_configured())

    def test_config_missing_when_partial(self):
        with patch.dict(os.environ, {"GOOGLE_ADS_CLIENT_ID": "x"}, clear=False):
            for k in ("GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_DEVELOPER_TOKEN"):
                os.environ.pop(k, None)
            self.assertFalse(_gads_oauth_configured())


class TestGadsOAuthStartRoute(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_start_returns_400_when_config_missing(self):
        for k in ("GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_DEVELOPER_TOKEN"):
            os.environ.pop(k, None)
        resp = self.client.get("/api/connectors/google-ads/oauth/start")
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "config_missing")

    def test_start_returns_authorize_url_when_configured(self):
        with patch.dict(os.environ, _set_gads_env()):
            resp = self.client.get("/api/connectors/google-ads/oauth/start")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertIn("authorize_url", data)
        self.assertIn("accounts.google.com", data["authorize_url"])
        self.assertTrue(data["state_created"])

    def test_authorize_url_does_not_contain_client_secret(self):
        env = _set_gads_env(GOOGLE_ADS_CLIENT_SECRET="SUPERSECRET_DO_NOT_LEAK")
        with patch.dict(os.environ, env):
            resp = self.client.get("/api/connectors/google-ads/oauth/start")
        data = resp.get_json()
        url = data.get("authorize_url", "")
        self.assertNotIn("SUPERSECRET_DO_NOT_LEAK", url)
        self.assertNotIn("client_secret", url)

    def test_authorize_url_contains_required_params(self):
        with patch.dict(os.environ, _set_gads_env()):
            resp = self.client.get("/api/connectors/google-ads/oauth/start")
        data = resp.get_json()
        url = data["authorize_url"]
        self.assertIn("response_type=code", url)
        self.assertIn("access_type=offline", url)
        self.assertIn("prompt=consent", url)
        self.assertIn("state=", url)
        self.assertIn("redirect_uri=", url)

    def test_start_response_never_contains_developer_token(self):
        env = _set_gads_env(GOOGLE_ADS_DEVELOPER_TOKEN="DEV_TOKEN_SECRET")
        with patch.dict(os.environ, env):
            resp = self.client.get("/api/connectors/google-ads/oauth/start")
        data = resp.get_json()
        resp_text = json.dumps(data)
        self.assertNotIn("DEV_TOKEN_SECRET", resp_text)


class TestGadsOAuthStateHelpers(unittest.TestCase):
    def test_store_and_validate_state(self):
        with patch.dict(os.environ, _set_gads_env()):
            import secrets as _sec
            state = _sec.token_urlsafe(16)
            stored = _gads_store_oauth_state(state, user_id=1)
            self.assertTrue(stored)
            ok, reason, row = _gads_validate_oauth_state(state)
            self.assertTrue(ok, msg=f"Expected ok=True, got reason={reason}")
            self.assertEqual(reason, "ok")

    def test_missing_state_fails(self):
        ok, reason, row = _gads_validate_oauth_state("")
        self.assertFalse(ok)
        self.assertEqual(reason, "missing_state")

    def test_unknown_state_fails(self):
        ok, reason, row = _gads_validate_oauth_state("nonexistent_state_xyz_12345")
        self.assertFalse(ok)
        self.assertEqual(reason, "state_not_found")

    def test_consumed_state_fails(self):
        with patch.dict(os.environ, _set_gads_env()):
            import secrets as _sec
            state = _sec.token_urlsafe(16)
            _gads_store_oauth_state(state, user_id=1)
            _gads_mark_oauth_state_used(state)
            ok, reason, row = _gads_validate_oauth_state(state)
            self.assertFalse(ok)
            self.assertEqual(reason, "state_already_used")


class TestGadsTokenStorage(unittest.TestCase):
    def test_token_stored_and_retrieved(self):
        token_data = {
            "access_token": "ya29.test_access",
            "refresh_token": "1//test_refresh",
            "token_type": "Bearer",
            "expires_in": 3599,
            "scope": "https://www.googleapis.com/auth/adwords",
        }
        stored = _gads_token_store(user_id=9991, token_data=token_data)
        self.assertTrue(stored)
        meta = _gads_token_get_meta(user_id=9991)
        self.assertIsNotNone(meta)
        self.assertEqual(meta["status"], "active")
        self.assertTrue(meta["token_validated"])
        self.assertFalse(meta["api_validated"])

    def test_token_meta_never_contains_refresh_token(self):
        token_data = {
            "refresh_token": "REFRESH_TOKEN_SHOULD_NOT_APPEAR",
            "access_token": "ACCESS_TOKEN_SHOULD_NOT_APPEAR",
        }
        _gads_token_store(user_id=9992, token_data=token_data)
        meta = _gads_token_get_meta(user_id=9992)
        meta_str = json.dumps(meta)
        self.assertNotIn("REFRESH_TOKEN_SHOULD_NOT_APPEAR", meta_str)
        self.assertNotIn("ACCESS_TOKEN_SHOULD_NOT_APPEAR", meta_str)

    def test_token_revoke_marks_revoked(self):
        _gads_token_store(user_id=9993, token_data={"refresh_token": "r", "access_token": "a"})
        _gads_token_revoke(user_id=9993)
        meta = _gads_token_get_meta(user_id=9993)
        self.assertIsNotNone(meta)
        self.assertEqual(meta["status"], "revoked")

    def test_no_token_returns_none(self):
        meta = _gads_token_get_meta(user_id=99999)
        self.assertIsNone(meta)


class TestGadsRealityStatus(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_reality_status_config_missing(self):
        for k in ("GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_DEVELOPER_TOKEN"):
            os.environ.pop(k, None)
        resp = self.client.get("/api/connectors/google-ads/reality/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["mode"], "config_missing")
        self.assertFalse(data["connected_live"])
        self.assertFalse(data["oauth_configured"])
        self.assertNotIn("client_secret", json.dumps(data))

    def test_reality_status_oauth_required_when_configured_no_token(self):
        with patch.dict(os.environ, _set_gads_env()):
            resp = self.client.get("/api/connectors/google-ads/reality/status")
        data = resp.get_json()
        self.assertEqual(data["mode"], "oauth_required")
        self.assertFalse(data["connected_live"])
        self.assertTrue(data["oauth_configured"])

    def test_reality_status_token_stored_after_storing_token(self):
        _gads_token_store(user_id=1, token_data={"refresh_token": "r", "access_token": "a"})
        with patch.dict(os.environ, _set_gads_env()):
            resp = self.client.get("/api/connectors/google-ads/reality/status")
        data = resp.get_json()
        self.assertEqual(data["mode"], "token_stored")
        self.assertTrue(data["has_token"])
        self.assertFalse(data["connected_live"])
        # Clean up
        _gads_token_revoke(user_id=1)

    def test_reality_status_never_exposes_secrets(self):
        with patch.dict(os.environ, _set_gads_env(
            GOOGLE_ADS_CLIENT_SECRET="SHOULD_NOT_APPEAR",
            GOOGLE_ADS_DEVELOPER_TOKEN="ALSO_SECRET"
        )):
            resp = self.client.get("/api/connectors/google-ads/reality/status")
        resp_text = resp.get_data(as_text=True)
        self.assertNotIn("SHOULD_NOT_APPEAR", resp_text)
        self.assertNotIn("ALSO_SECRET", resp_text)


class TestGadsOAuthDisconnect(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_disconnect_revokes_token(self):
        _gads_token_store(user_id=1, token_data={"refresh_token": "r2", "access_token": "a2"})
        resp = self.client.post("/api/connectors/google-ads/oauth/disconnect")
        data = resp.get_json()
        self.assertTrue(data["success"])
        meta = _gads_token_get_meta(user_id=1)
        self.assertEqual(meta["status"], "revoked")


class TestGadsValidateRoute(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_validate_without_config_returns_400(self):
        for k in ("GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_DEVELOPER_TOKEN"):
            os.environ.pop(k, None)
        resp = self.client.post("/api/connectors/google-ads/validate")
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["status"], "config_missing")

    def test_validate_without_token_returns_400(self):
        _gads_token_revoke(user_id=1)
        with patch.dict(os.environ, _set_gads_env()):
            resp = self.client.post("/api/connectors/google-ads/validate")
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertEqual(data["status"], "oauth_required")

    def test_validate_with_token_returns_token_stored(self):
        _gads_token_store(user_id=1, token_data={"refresh_token": "r3", "access_token": "a3"})
        with patch.dict(os.environ, _set_gads_env()):
            resp = self.client.post("/api/connectors/google-ads/validate")
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "token_stored")
        self.assertFalse(data["api_validated"])
        self.assertFalse(data["connected_live"])
        # Clean up
        _gads_token_revoke(user_id=1)

    def test_validate_does_not_leak_secrets(self):
        _gads_token_store(user_id=1, token_data={"refresh_token": "REFRESH_LEAK_CHECK", "access_token": "ACCESS_LEAK_CHECK"})
        with patch.dict(os.environ, _set_gads_env()):
            resp = self.client.post("/api/connectors/google-ads/validate")
        resp_text = resp.get_data(as_text=True)
        self.assertNotIn("REFRESH_LEAK_CHECK", resp_text)
        self.assertNotIn("ACCESS_LEAK_CHECK", resp_text)
        # Clean up
        _gads_token_revoke(user_id=1)


class TestGadsOAuthStatusRoute(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_status_oauth_required_when_no_token(self):
        _gads_token_revoke(user_id=1)
        with patch.dict(os.environ, _set_gads_env()):
            resp = self.client.get("/api/connectors/google-ads/oauth/status")
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "oauth_required")
        self.assertFalse(data["has_token"])

    def test_status_token_stored_when_token_exists(self):
        _gads_token_store(user_id=1, token_data={"refresh_token": "r4", "access_token": "a4"})
        with patch.dict(os.environ, _set_gads_env()):
            resp = self.client.get("/api/connectors/google-ads/oauth/status")
        data = resp.get_json()
        self.assertTrue(data["has_token"])
        self.assertEqual(data["status"], "token_stored")
        self.assertNotIn("refresh_token", json.dumps(data))
        self.assertNotIn("access_token", json.dumps(data))
        # Clean up
        _gads_token_revoke(user_id=1)


class TestGadsCallbackRoute(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_callback_user_denied_redirects_with_error(self):
        resp = self.client.get("/api/connectors/google-ads/oauth/callback?error=access_denied&state=x")
        self.assertEqual(resp.status_code, 302)
        location = resp.headers.get("Location", "")
        self.assertIn("oauth=error", location)
        self.assertIn("access_denied", location)

    def test_callback_invalid_state_redirects_with_error(self):
        resp = self.client.get("/api/connectors/google-ads/oauth/callback?code=somecode&state=INVALID_STATE_XYZ")
        self.assertEqual(resp.status_code, 302)
        location = resp.headers.get("Location", "")
        self.assertIn("oauth=error", location)
        self.assertIn("invalid_state", location)

    def test_callback_missing_code_redirects_with_error(self):
        with patch.dict(os.environ, _set_gads_env()):
            import secrets as _sec
            state = _sec.token_urlsafe(16)
            _gads_store_oauth_state(state, user_id=1)
            resp = self.client.get(f"/api/connectors/google-ads/oauth/callback?state={state}")
        self.assertEqual(resp.status_code, 302)
        location = resp.headers.get("Location", "")
        self.assertIn("oauth=error", location)
        self.assertIn("missing_code", location)


if __name__ == "__main__":
    unittest.main(verbosity=2)
