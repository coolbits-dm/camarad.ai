"""Flows Draft Mode tests.

Covers:
1.  POST /api/flows/drafts/generate - empty prompt returns 400
2.  POST /api/flows/drafts/generate - generic prompt creates draft with trigger/agent/output
3.  POST /api/flows/drafts/generate - PPC prompt includes PPC agent + Google Ads placeholder
4.  Draft response includes orchestrator_url
5.  GET /api/flows/drafts - lists only current user's drafts
6.  GET /api/flows/drafts/<id> - returns flow_json safely
7.  Generated draft has safety.mode=draft_only and requires_human_approval=True
8.  POST /api/orchestrator/execute - rejects draft flow with draft_not_executable
9.  POST /api/flows/drafts/<id>/promote - creates saved flow, does NOT execute
10. No external connector call occurs during generation

No real OpenAI calls. No external actions. No real connector mutations.
"""

import json
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("AUTH_REQUIRED", "0")
os.environ["AUTH_REQUIRED"] = "0"


class FlowsDraftModeTests(unittest.TestCase):
    """Test the /api/flows/drafts/* endpoints and draft mode safety."""

    def setUp(self):
        import app as _app_module
        _app_module.AUTH_REQUIRED = False
        from app import app
        from database import init_db, ensure_flow_drafts_table, get_db
        app.config["TESTING"] = True
        self.client = app.test_client()
        # Ensure all tables exist for a fresh-DB run
        with app.app_context():
            init_db()
            conn = get_db()
            ensure_flow_drafts_table(conn)
            conn.close()
        self._hdr = {
            "Content-Type": "application/json",
            "X-User-ID": "900",
        }
        # Ensure onboarding is complete for test user
        self.client.patch(
            "/api/settings/user",
            data=json.dumps({"preferences": {"onboarding_completed": True}}),
            content_type="application/json",
            headers={"X-User-ID": "900"},
        )

    # ------------------------------------------------------------------
    # 1. Empty prompt returns 400
    # ------------------------------------------------------------------
    def test_generate_empty_prompt_returns_400(self):
        """Empty prompt → 400 with prompt_required error."""
        resp = self.client.post(
            "/api/flows/drafts/generate",
            data=json.dumps({"prompt": ""}),
            content_type="application/json",
            headers=self._hdr,
        )
        self.assertEqual(resp.status_code, 400, resp.get_data(as_text=True))
        body = resp.get_json()
        self.assertIsNotNone(body)
        self.assertEqual(body.get("error"), "prompt_required")

    def test_generate_missing_prompt_returns_400(self):
        """Missing prompt key → 400."""
        resp = self.client.post(
            "/api/flows/drafts/generate",
            data=json.dumps({}),
            content_type="application/json",
            headers=self._hdr,
        )
        self.assertEqual(resp.status_code, 400)

    # ------------------------------------------------------------------
    # 2. Generic prompt creates draft with trigger / agent / output
    # ------------------------------------------------------------------
    def test_generate_generic_prompt_creates_draft(self):
        """Generic prompt → 200 with draft containing trigger, agent, output nodes."""
        resp = self.client.post(
            "/api/flows/drafts/generate",
            data=json.dumps({"prompt": "help me plan my next quarter"}),
            content_type="application/json",
            headers=self._hdr,
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        body = resp.get_json()
        self.assertTrue(body.get("success"))
        self.assertIn("draft_id", body)
        self.assertEqual(body.get("status"), "draft")

        flow = body.get("flow", {})
        self.assertIsInstance(flow, dict)
        nodes = flow.get("nodes", [])
        node_types = [n.get("type") for n in nodes]
        self.assertIn("trigger", node_types, "Must have at least one trigger node")
        self.assertIn("agent", node_types, "Must have at least one agent node")
        self.assertIn("output", node_types, "Must have at least one output node")

    # ------------------------------------------------------------------
    # 3. PPC prompt includes PPC agent + Google Ads placeholder
    # ------------------------------------------------------------------
    def test_generate_ppc_prompt_includes_ppc_nodes(self):
        """PPC prompt → includes ppc-specialist agent + Google Ads connector placeholder."""
        resp = self.client.post(
            "/api/flows/drafts/generate",
            data=json.dumps({"prompt": "make a weekly PPC report for current client"}),
            content_type="application/json",
            headers=self._hdr,
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        flow = body.get("flow", {})
        nodes = flow.get("nodes", [])

        agent_slugs = [n.get("slug") for n in nodes if n.get("type") == "agent"]
        self.assertIn("ppc-specialist", agent_slugs, "PPC prompt should assign ppc-specialist agent")

        connector_slugs = [n.get("slug") for n in nodes if n.get("type") == "connector"]
        self.assertIn("google-ads", connector_slugs, "PPC prompt should include Google Ads placeholder")

    # ------------------------------------------------------------------
    # 4. Draft response includes orchestrator_url
    # ------------------------------------------------------------------
    def test_generate_response_has_orchestrator_url(self):
        """Draft response must include orchestrator_url pointing to draft_id."""
        resp = self.client.post(
            "/api/flows/drafts/generate",
            data=json.dumps({"prompt": "summarize recent performance"}),
            content_type="application/json",
            headers=self._hdr,
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        draft_id = body.get("draft_id")
        self.assertIsNotNone(draft_id)
        url = body.get("orchestrator_url", "")
        self.assertIn("draft_id", url, "orchestrator_url must contain draft_id")
        self.assertIn(str(draft_id), url, "orchestrator_url must match the returned draft_id")

    # ------------------------------------------------------------------
    # 5. GET /api/flows/drafts lists only current user's drafts
    # ------------------------------------------------------------------
    def test_list_drafts_scoped_to_user(self):
        """List drafts returns only this user's drafts, not other users'."""
        # Create a draft for user 900
        self.client.post(
            "/api/flows/drafts/generate",
            data=json.dumps({"prompt": "test draft for user 900"}),
            content_type="application/json",
            headers=self._hdr,
        )
        resp = self.client.get(
            "/api/flows/drafts",
            headers={"X-User-ID": "900"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertTrue(body.get("success"))
        drafts = body.get("drafts", [])
        self.assertIsInstance(drafts, list)
        # All returned drafts must belong to user 900
        for d in drafts:
            self.assertEqual(d.get("user_id"), 900, f"Got draft owned by user {d.get('user_id')}, expected 900")

        # Another user (901) should NOT see user 900's drafts
        resp2 = self.client.get(
            "/api/flows/drafts",
            headers={"X-User-ID": "901"},
        )
        body2 = resp2.get_json() or {}
        drafts2 = body2.get("drafts", [])
        user_900_in_901 = [d for d in drafts2 if d.get("user_id") == 900]
        self.assertEqual(len(user_900_in_901), 0, "User 901 should not see user 900's drafts")

    # ------------------------------------------------------------------
    # 6. GET /api/flows/drafts/<id> returns flow_json safely
    # ------------------------------------------------------------------
    def test_get_draft_by_id(self):
        """GET /api/flows/drafts/<id> returns full draft with flow object."""
        # Create draft first
        create_resp = self.client.post(
            "/api/flows/drafts/generate",
            data=json.dumps({"prompt": "create monthly analytics report"}),
            content_type="application/json",
            headers=self._hdr,
        )
        self.assertEqual(create_resp.status_code, 200)
        draft_id = create_resp.get_json().get("draft_id")
        self.assertIsNotNone(draft_id)

        # Fetch by id
        resp = self.client.get(
            f"/api/flows/drafts/{draft_id}",
            headers={"X-User-ID": "900"},
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        body = resp.get_json()
        self.assertTrue(body.get("success"))
        draft = body.get("draft", {})
        self.assertEqual(draft.get("id"), draft_id)
        self.assertIn("flow", draft)
        self.assertIn("nodes", draft.get("flow", {}))

        # Must not expose secrets
        raw = json.dumps(body)
        self.assertNotIn("sk-", raw)
        self.assertNotIn("OPENAI_API_KEY", raw)

    def test_get_draft_other_user_returns_404(self):
        """Another user cannot fetch a draft they don't own."""
        # Create draft as user 900
        create_resp = self.client.post(
            "/api/flows/drafts/generate",
            data=json.dumps({"prompt": "secret plan"}),
            content_type="application/json",
            headers=self._hdr,
        )
        draft_id = create_resp.get_json().get("draft_id")

        # Fetch as user 902
        resp = self.client.get(
            f"/api/flows/drafts/{draft_id}",
            headers={"X-User-ID": "902"},
        )
        self.assertEqual(resp.status_code, 404)

    # ------------------------------------------------------------------
    # 7. Generated draft has safety.mode=draft_only and requires_human_approval=True
    # ------------------------------------------------------------------
    def test_draft_has_safety_metadata(self):
        """Generated draft flow must have draft=True, safety.mode=draft_only, requires_human_approval=True."""
        resp = self.client.post(
            "/api/flows/drafts/generate",
            data=json.dumps({"prompt": "prepare quarterly review"}),
            content_type="application/json",
            headers=self._hdr,
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        flow = body.get("flow", {})

        self.assertTrue(flow.get("draft"), "flow.draft must be True")
        safety = flow.get("safety", {})
        self.assertEqual(safety.get("mode"), "draft_only", "safety.mode must be 'draft_only'")
        self.assertTrue(safety.get("requires_human_approval"), "safety.requires_human_approval must be True")
        self.assertFalse(safety.get("external_actions_enabled"), "safety.external_actions_enabled must be False")
        self.assertEqual(flow.get("version"), "draft_v1")

    # ------------------------------------------------------------------
    # 8. /api/orchestrator/execute rejects draft flow with draft_not_executable
    # ------------------------------------------------------------------
    def test_execute_rejects_draft_only_flow(self):
        """Posting a draft_only flow to /api/orchestrator/execute must return 400 draft_not_executable."""
        # Create a client for user 900 so client scope requirement is satisfied
        cr = self.client.post(
            "/api/clients",
            data=json.dumps({"name": "Draft Test Client"}),
            content_type="application/json",
            headers=self._hdr,
        )
        client_id = (cr.get_json() or {}).get("client", {}).get("id") or (cr.get_json() or {}).get("id")

        draft_flow = {
            "version": "draft_v1",
            "draft": True,
            "safety": {
                "mode": "draft_only",
                "requires_human_approval": True,
                "external_actions_enabled": False,
            },
            "nodes": [
                {"id": "trigger_1", "type": "trigger", "x": 80, "y": 140, "label": "Start"},
                {"id": "agent_1", "type": "agent", "x": 320, "y": 140, "label": "Assistant", "slug": "assistant"},
                {"id": "output_1", "type": "output", "x": 560, "y": 140, "label": "Output"},
            ],
            "connections": [
                {"from": "trigger_1", "to": "agent_1"},
                {"from": "agent_1", "to": "output_1"},
            ],
        }
        exec_hdr = dict(self._hdr)
        if client_id:
            exec_hdr["X-Client-ID"] = str(client_id)
        resp = self.client.post(
            "/api/orchestrator/execute",
            data=json.dumps({"flow": draft_flow}),
            content_type="application/json",
            headers=exec_hdr,
        )
        self.assertEqual(resp.status_code, 400, resp.get_data(as_text=True))
        body = resp.get_json()
        self.assertIsNotNone(body)
        self.assertEqual(body.get("error"), "draft_not_executable")
        self.assertIn("message", body)

    def test_execute_non_draft_flow_not_blocked(self):
        """A non-draft flow must NOT be blocked by the draft guard (existing behavior preserved)."""
        normal_flow = {
            "version": "1.0",
            "nodes": [
                {"id": "trigger_1", "type": "trigger", "x": 80, "y": 140, "label": "Start"},
                {"id": "output_1", "type": "output", "x": 320, "y": 140, "label": "Output"},
            ],
            "connections": [{"from": "trigger_1", "to": "output_1"}],
        }
        resp = self.client.post(
            "/api/orchestrator/execute",
            data=json.dumps({"flow": normal_flow}),
            content_type="application/json",
            headers=self._hdr,
        )
        # Must not be blocked by draft guard — it may fail for other reasons (CT spend etc)
        # but must not return error=draft_not_executable
        body = resp.get_json() or {}
        self.assertNotEqual(body.get("error"), "draft_not_executable",
                            "Non-draft flow must not be blocked by draft guard")

    # ------------------------------------------------------------------
    # 9. Promote endpoint creates saved flow, does NOT execute
    # ------------------------------------------------------------------
    def test_promote_creates_flow_and_does_not_execute(self):
        """Promote endpoint saves draft to flows table; returned flow_id is not None."""
        # Create draft
        create_resp = self.client.post(
            "/api/flows/drafts/generate",
            data=json.dumps({"prompt": "create strategy outline"}),
            content_type="application/json",
            headers=self._hdr,
        )
        self.assertEqual(create_resp.status_code, 200)
        draft_id = create_resp.get_json().get("draft_id")

        # Promote
        promo_resp = self.client.post(
            f"/api/flows/drafts/{draft_id}/promote",
            content_type="application/json",
            headers=self._hdr,
        )
        self.assertEqual(promo_resp.status_code, 200, promo_resp.get_data(as_text=True))
        promo = promo_resp.get_json()
        self.assertTrue(promo.get("success"))
        flow_id = promo.get("flow_id")
        self.assertIsNotNone(flow_id, "Promote must return a flow_id")

        # Verify the saved flow exists and is NOT marked as executed
        flow_resp = self.client.get(
            f"/api/flows/{flow_id}",
            headers={"X-User-ID": "900"},
        )
        self.assertEqual(flow_resp.status_code, 200)
        flow_data = flow_resp.get_json()
        self.assertIsNotNone(flow_data)
        # Must not have execution metadata
        self.assertNotIn("executed_at", json.dumps(flow_data))
        self.assertNotIn("execution_result", json.dumps(flow_data))

    # ------------------------------------------------------------------
    # 10. No external connector call occurs during generation
    # ------------------------------------------------------------------
    def test_generate_makes_no_external_calls(self):
        """Draft generation must never call external APIs or LLM."""
        external_calls = []

        def _mock_get_llm(*a, **kw):
            external_calls.append(("get_llm_response", a))
            return "{}"

        def _mock_requests(*a, **kw):
            external_calls.append(("requests", a))
            raise AssertionError("External HTTP request made during draft generation!")

        with patch("app.get_llm_response", side_effect=_mock_get_llm), \
             patch("requests.get", side_effect=_mock_requests), \
             patch("requests.post", side_effect=_mock_requests):
            resp = self.client.post(
                "/api/flows/drafts/generate",
                data=json.dumps({"prompt": "analyze google ads performance and create report"}),
                content_type="application/json",
                headers=self._hdr,
            )

        self.assertEqual(resp.status_code, 200)
        llm_calls = [c for c in external_calls if c[0] == "get_llm_response"]
        self.assertEqual(len(llm_calls), 0, "Draft generator must not call get_llm_response")

    # ------------------------------------------------------------------
    # Connector placeholder nodes must not have external_action=True
    # ------------------------------------------------------------------
    def test_connector_nodes_are_draft_placeholders(self):
        """Connector nodes in generated drafts must have external_action=False."""
        resp = self.client.post(
            "/api/flows/drafts/generate",
            data=json.dumps({"prompt": "pull Google Analytics data and send weekly summary"}),
            content_type="application/json",
            headers=self._hdr,
        )
        self.assertEqual(resp.status_code, 200)
        flow = resp.get_json().get("flow", {})
        for node in flow.get("nodes", []):
            if node.get("type") == "connector":
                config = node.get("config", {})
                self.assertFalse(
                    config.get("external_action"),
                    f"Connector node {node.get('id')} must have external_action=False in draft"
                )


if __name__ == "__main__":
    unittest.main()
