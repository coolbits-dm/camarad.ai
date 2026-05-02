"""AI provider policy smoke tests."""

import json
import os
import unittest
from unittest.mock import patch

from ai.provider_policy import get_ai_provider_policy, safe_provider_status


SECRET = "test-secret-value-that-must-not-leak"


class AIProviderPolicyTests(unittest.TestCase):
    def test_hosted_platform_default_configured(self):
        policy = get_ai_provider_policy(
            {
                "CAMARAD_DISTRIBUTION": "hosted",
                "CAMARAD_PROVIDER_MODE": "platform_default",
                "ALLOW_PLATFORM_DEFAULT_PROVIDER": "true",
                "OPENAI_API_KEY": SECRET,
                "OPENAI_DEFAULT_MODEL": "gpt-test",
            }
        )

        self.assertTrue(policy.configured)
        self.assertEqual(policy.status, "configured")
        self.assertEqual(policy.provider, "openai")
        self.assertEqual(policy.credential_source, "platform_default")
        self.assertEqual(policy.default_model, "gpt-test")

    def test_hosted_disabled(self):
        status = safe_provider_status(
            {
                "CAMARAD_DISTRIBUTION": "hosted",
                "CAMARAD_PROVIDER_MODE": "disabled",
                "OPENAI_API_KEY": SECRET,
            }
        )

        self.assertFalse(status["configured"])
        self.assertEqual(status["status"], "disabled")
        self.assertIsNone(status["provider"])
        self.assertEqual(status["credential_source"], "none")

    def test_self_hosted_byok_configured(self):
        policy = get_ai_provider_policy(
            {
                "CAMARAD_DISTRIBUTION": "self_hosted",
                "CAMARAD_PROVIDER_MODE": "byok",
                "OPENAI_API_KEY": SECRET,
            }
        )

        self.assertTrue(policy.configured)
        self.assertEqual(policy.status, "configured")
        self.assertEqual(policy.provider, "openai")
        self.assertEqual(policy.credential_source, "instance_env")

    def test_self_hosted_byok_missing_key(self):
        status = safe_provider_status(
            {
                "CAMARAD_DISTRIBUTION": "self_hosted",
                "CAMARAD_PROVIDER_MODE": "byok",
            }
        )

        self.assertFalse(status["configured"])
        self.assertEqual(status["status"], "setup_required")
        self.assertEqual(status["provider"], "openai")
        self.assertEqual(status["credential_source"], "none")

    def test_self_hosted_platform_default_is_invalid(self):
        status = safe_provider_status(
            {
                "CAMARAD_DISTRIBUTION": "self_hosted",
                "CAMARAD_PROVIDER_MODE": "platform_default",
                "ALLOW_PLATFORM_DEFAULT_PROVIDER": "true",
                "OPENAI_API_KEY": SECRET,
            }
        )

        self.assertFalse(status["configured"])
        self.assertEqual(status["status"], "invalid_config")
        self.assertIsNone(status["provider"])
        self.assertEqual(status["credential_source"], "none")

    def test_safe_status_never_leaks_secret_values(self):
        status = safe_provider_status(
            {
                "CAMARAD_DISTRIBUTION": "hosted",
                "CAMARAD_PROVIDER_MODE": "platform_default",
                "ALLOW_PLATFORM_DEFAULT_PROVIDER": "true",
                "OPENAI_API_KEY": SECRET,
                "OPENAI_PROJECT_ID": "proj-secret-123",
            }
        )
        rendered = json.dumps(status, sort_keys=True)

        self.assertNotIn(SECRET, rendered)
        self.assertNotIn("test-secret", rendered)
        self.assertNotIn("proj-secret-123", rendered)

    def test_status_endpoint_returns_safe_metadata(self):
        env = {
            "CAMARAD_DISTRIBUTION": "hosted",
            "CAMARAD_PROVIDER_MODE": "platform_default",
            "ALLOW_PLATFORM_DEFAULT_PROVIDER": "true",
            "OPENAI_API_KEY": SECRET,
            "OPENAI_PROJECT_ID": "proj-secret-123",
        }
        with patch.dict(os.environ, env, clear=True):
            from app import app

            response = app.test_client().get("/api/ai/provider/status")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json() or {}
        self.assertTrue(payload.get("configured"))
        self.assertEqual(payload.get("credential_source"), "platform_default")
        rendered = json.dumps(payload, sort_keys=True)
        self.assertNotIn(SECRET, rendered)
        self.assertNotIn("test-secret", rendered)
        self.assertNotIn("proj-secret-123", rendered)


if __name__ == "__main__":
    unittest.main()
