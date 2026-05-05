"""
Tests: PPC Specialist Agent — /api/agents/ppc/run

Covers:
  1. Valid payload returns valid schema
  2. Missing GA4 context still works (Google Ads-only analysis)
  3. Empty context returns safe no-data response (200, not error)
  4. Malformed payload returns 400
  5. Missing account_id returns 400
  6. Invalid policy coerces to "deep"
  7. LLM failure returns fallback JSON (not HTML/error text)
  8. Fallback plan uses waste_finder signals when available
  9. Fallback plan uses account_health signals when available
 10. Fallback plan handles waste search terms count
 11. Validated LLM output strips markdown fences
 12. Validated LLM output rejects bad action types
 13. Policy limit enforced in fallback (auto=3, eco=8, deep=20)
 14. Context validation warns on missing sections
 15. Content-Type: non-JSON returns 400

Run:
    cd /opt/camarad-repo/backend_py
    AUTH_REQUIRED=0 COOLBITS_GATEWAY_ENABLED=false DATABASE=/tmp/ppc_agent_test.db \\
        python3 -m unittest test_ppc_agent -v
"""

import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend_py.app as app_module
from backend_py.app import app

# ─── Shared fixtures ──────────────────────────────────────────────────────────

_ACCOUNT_ID = "1325845765"

_HEALTH = {
    "success": True, "module_id": "account_health", "source": "mock",
    "live_data": False,
    "summary": {
        "active_campaigns": 3,
        "total_spend": 1500.0,
        "account_roas": 2.8,
        "account_cpa": 45.0,
        "signal_counts": {"critical": 1, "warning": 2, "info": 1, "total": 4},
        "score_status": "planned",
        "top_signal": "high_spend_zero_conversions",
    },
    "signals": [
        {
            "id": "high_spend_zero_conversions",
            "severity": "critical",
            "message": "Campaign 'Demand Gen - Prospecting' spent 53.19 RON with 0 conversions.",
            "evidence": {"spend": 53.19, "conversions": 0, "campaign": "Demand Gen - Prospecting"},
        },
        {
            "id": "low_roas_campaigns",
            "severity": "warning",
            "message": "2 campaigns have ROAS below 1.0.",
            "evidence": {"count": 2},
        },
    ],
    "warnings": [],
}

_CAMPAIGNS = {
    "campaigns": [
        {"name": "Search - Brand", "status": "ENABLED", "spent": 800.0,
         "roas": 4.2, "conversions": 18.0, "impressions": 12000, "clicks": 320},
        {"name": "Demand Gen - Prospecting", "status": "ENABLED", "spent": 53.19,
         "roas": 0.0, "conversions": 0.0, "impressions": 5000, "clicks": 90},
    ],
    "summary": {
        "total_campaigns": 2, "active_campaigns": 2,
        "total_spent": 853.19, "avg_roas": 2.1,
    },
    "source": "mock",
}

_WASTE = {
    "success": True, "module_id": "waste_finder", "source": "mock",
    "live_data": False,
    "summary": {
        "waste_campaigns_count": 1,
        "total_waste_spend": {"amount": 53.19, "currency_code": "RON", "formatted": "53.19 RON"},
        "total_account_spend": {"amount": 853.19, "currency_code": "RON", "formatted": "853.19 RON"},
        "signal_counts": {"critical": 1, "warning": 0, "info": 0, "total": 1},
    },
    "signals": [
        {
            "id": "waste_search_terms",
            "severity": "critical",
            "message": "Campaign 'Demand Gen - Prospecting': 53.19 RON spent with 0 conversions.",
            "evidence": {"campaign": "Demand Gen - Prospecting", "spend": 53.19, "conversions": 0},
        },
    ],
    "warnings": [],
}

_SEARCH_TERMS = {
    "success": True, "module_id": "search_terms", "source": "mock",
    "live_data": False,
    "summary": {
        "terms_count": 48,
        "waste_terms_count": 12,
        "winner_terms_count": 6,
        "opportunity_terms_count": 8,
        "total_cost": 420.0,
        "total_conversions": 9,
        "pmax_gap": True,
        "pmax_terms_note": "PMax terms detected but not analyzed in this version.",
    },
    "signals": [],
    "warnings": [],
}

_GA4 = {
    "sessions": 4200, "users": 3100,
    "bounce_rate": 38.2, "avg_session_duration": 142,
    "source": "google/cpc",
}

_FULL_CONTEXT = {
    "account_health": _HEALTH,
    "campaigns": _CAMPAIGNS,
    "waste_finder": _WASTE,
    "search_terms": _SEARCH_TERMS,
    "ga4_overview": _GA4,
}

_GADS_ONLY_CONTEXT = {
    "account_health": _HEALTH,
    "campaigns": _CAMPAIGNS,
    "waste_finder": _WASTE,
    "search_terms": _SEARCH_TERMS,
    # ga4_overview intentionally omitted
}

_VALID_PPC_OUTPUT = json.dumps({
    "agent": "ppc",
    "policy_used": "deep",
    "account_id": _ACCOUNT_ID,
    "summary": "Account has 1 critical waste signal. Demand Gen campaign spending with zero conversions.",
    "actions": [
        {
            "priority": "critical",
            "type": "pause_campaign",
            "entity": "Demand Gen - Prospecting",
            "reason": "53.19 RON spent with 0 conversions over 30 days.",
            "evidence": {"spend": 53.19, "conversions": 0},
            "expected_impact": "Save 53.19 RON/month in wasted spend",
            "risk": "May reduce upper-funnel reach",
            "recommended_next_step": "Pause campaign and review audience targeting",
        }
    ],
    "next_questions": [],
    "warnings": [],
})

# ─── Helper ───────────────────────────────────────────────────────────────────

def _post(client, payload, content_type="application/json"):
    return client.post(
        "/api/agents/ppc/run",
        data=json.dumps(payload) if content_type == "application/json" else payload,
        content_type=content_type,
    )


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestPpcAgentEndpoint(unittest.TestCase):

    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    # 1. Valid payload + gateway disabled → fallback JSON with correct schema
    def test_valid_payload_returns_valid_schema(self):
        payload = {
            "account_id": _ACCOUNT_ID,
            "policy": "deep",
            "context": _FULL_CONTEXT,
        }
        resp = _post(self.client, payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["agent"], "ppc")
        self.assertIn(data["policy_used"], {"auto", "eco", "deep"})
        self.assertEqual(data["account_id"], _ACCOUNT_ID)
        self.assertIsInstance(data["summary"], str)
        self.assertGreater(len(data["summary"]), 0)
        self.assertIsInstance(data["actions"], list)
        self.assertIsInstance(data["next_questions"], list)
        self.assertIsInstance(data["warnings"], list)
        # Each action must have required fields
        for action in data["actions"]:
            self.assertIn(action["priority"], {"critical", "high", "medium", "low"})
            self.assertIn("type", action)
            self.assertIn("reason", action)
            self.assertIn("evidence", action)

    # 2. Missing GA4 — should still work with Google Ads-only context
    def test_missing_ga4_still_works(self):
        payload = {
            "account_id": _ACCOUNT_ID,
            "policy": "eco",
            "context": _GADS_ONLY_CONTEXT,
        }
        resp = _post(self.client, payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["agent"], "ppc")
        # Should warn about missing GA4
        warnings_text = " ".join(data["warnings"])
        self.assertIn("ga4_overview", warnings_text)
        # Should still produce actions
        self.assertIsInstance(data["actions"], list)

    # 3. Empty context → safe no-data 200 response (not 400)
    def test_empty_context_returns_no_data_response(self):
        payload = {
            "account_id": _ACCOUNT_ID,
            "policy": "deep",
            "context": {},
        }
        resp = _post(self.client, payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["agent"], "ppc")
        self.assertEqual(data["actions"], [])
        self.assertGreater(len(data["summary"]), 0)
        self.assertIsInstance(data["warnings"], list)

    # 4. Malformed JSON body → 400
    def test_malformed_payload_returns_400(self):
        resp = self.client.post(
            "/api/agents/ppc/run",
            data="this is not json",
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    # 5. Missing account_id → 400
    def test_missing_account_id_returns_400(self):
        payload = {"policy": "deep", "context": _FULL_CONTEXT}
        resp = _post(self.client, payload)
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertEqual(data["error"], "account_id_required")

    # 6. Invalid policy coerces to "deep"
    def test_invalid_policy_coerces_to_deep(self):
        payload = {
            "account_id": _ACCOUNT_ID,
            "policy": "ultra",
            "context": _GADS_ONLY_CONTEXT,
        }
        resp = _post(self.client, payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["policy_used"], "deep")

    # 7. LLM failure (gateway raises) → fallback JSON, not HTML or exception
    def test_llm_failure_returns_fallback_json(self):
        with patch.object(app_module, "COOLBITS_GATEWAY_ENABLED", True):
            with patch.object(app_module, "_coolbits_request", side_effect=Exception("gateway_down")):
                payload = {
                    "account_id": _ACCOUNT_ID,
                    "policy": "deep",
                    "context": _FULL_CONTEXT,
                }
                resp = _post(self.client, payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        # Must be valid JSON with correct agent field, not HTML
        self.assertEqual(data["agent"], "ppc")
        self.assertIsInstance(data["actions"], list)
        # Must warn about LLM failure
        warnings_text = " ".join(data["warnings"])
        self.assertIn("gateway_exception", warnings_text)

    # 8. Fallback uses waste_finder signals
    def test_fallback_uses_waste_finder_signals(self):
        payload = {
            "account_id": _ACCOUNT_ID,
            "policy": "deep",
            "context": {"waste_finder": _WASTE},
        }
        resp = _post(self.client, payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIsInstance(data["actions"], list)
        self.assertGreater(len(data["actions"]), 0)
        # At least one action should come from waste signal
        reasons = [a["reason"] for a in data["actions"]]
        self.assertTrue(any("Demand Gen" in r or "53.19" in r or "0 conversions" in r for r in reasons))

    # 9. Fallback uses account_health signals when waste_finder absent
    def test_fallback_uses_account_health_signals(self):
        payload = {
            "account_id": _ACCOUNT_ID,
            "policy": "deep",
            "context": {"account_health": _HEALTH},
        }
        resp = _post(self.client, payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIsInstance(data["actions"], list)
        self.assertGreater(len(data["actions"]), 0)

    # 10. Fallback adds search terms action when waste_terms_count > 0
    def test_fallback_search_terms_action(self):
        payload = {
            "account_id": _ACCOUNT_ID,
            "policy": "deep",
            "context": {"search_terms": _SEARCH_TERMS},
        }
        resp = _post(self.client, payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        types = [a["type"] for a in data["actions"]]
        self.assertIn("add_negative_keyword", types)

    # 11. _ppc_validate_llm_output strips markdown fences
    def test_validate_output_strips_markdown_fences(self):
        raw = f"```json\n{_VALID_PPC_OUTPUT}\n```"
        cleaned, valid = app_module._ppc_validate_llm_output(raw, _ACCOUNT_ID, "deep")
        self.assertTrue(valid)
        self.assertEqual(cleaned["agent"], "ppc")
        self.assertIsInstance(cleaned["actions"], list)

    # 12. _ppc_validate_llm_output rejects bad action type → coerced to reporting_action
    def test_validate_output_coerces_invalid_action_type(self):
        bad_output = json.loads(_VALID_PPC_OUTPUT)
        bad_output["actions"][0]["type"] = "delete_account"  # not in allowed types
        raw = json.dumps(bad_output)
        cleaned, valid = app_module._ppc_validate_llm_output(raw, _ACCOUNT_ID, "deep")
        self.assertTrue(valid)
        self.assertEqual(cleaned["actions"][0]["type"], "reporting_action")

    # 13. Policy action limit: auto=3
    def test_policy_limit_auto(self):
        payload = {
            "account_id": _ACCOUNT_ID,
            "policy": "auto",
            "context": _FULL_CONTEXT,
        }
        resp = _post(self.client, payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertLessEqual(len(data["actions"]), 3)

    # 14. Context validation warns on missing sections
    def test_context_validation_warns_missing_sections(self):
        ctx, warnings = app_module._ppc_validate_context({"account_health": _HEALTH})
        self.assertIn("campaigns", " ".join(warnings))
        self.assertIn("waste_finder", " ".join(warnings))
        self.assertIn("ga4_overview", " ".join(warnings))

    # 15. Non-JSON Content-Type → 400
    def test_non_json_content_type_returns_400(self):
        resp = self.client.post(
            "/api/agents/ppc/run",
            data="account_id=test",
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertEqual(data["error"], "invalid_content_type")


if __name__ == "__main__":
    unittest.main()
