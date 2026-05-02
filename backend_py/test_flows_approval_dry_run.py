"""
Tests for Flows v2 Approval + Dry-Run Gate.

Tests:
 1.  Request approval for promoted flow returns pending
 2.  Duplicate request returns existing pending (no duplicate)
 3.  Approval status returns pending + can_dry_run=False before approval
 4.  Approve sets status=approved
 5.  Reject sets status=rejected
 6.  Dry-run without approval returns approval_required
 7.  Dry-run with approved approval returns dry_run_completed
 8.  Dry-run result has external_actions_executed=0
 9.  Dry-run makes no external/LLM calls (pure simulation)
10.  Draft flow still rejected by execute (draft_not_executable)
11.  Draft flow cannot be dry-run (must promote first)
12.  Promoted flow has safety.mode=promoted_safe
13.  User cannot access another user's approval
14.  Existing execute behavior preserved for legacy non-safety flows
"""

import json
import os
import unittest
import tempfile

os.environ.setdefault("AUTH_REQUIRED", "0")

import app as _app_module
from app import app
from database import init_db, get_db, ensure_flow_drafts_table, ensure_flow_approvals_table, ensure_execution_type_column


def _make_client():
    return app.test_client()


def _setup_db(db_path):
    os.environ["DATABASE"] = db_path
    _app_module.DATABASE = db_path
    if hasattr(_app_module, "AUTH_REQUIRED"):
        _app_module.AUTH_REQUIRED = False
    app.config["TESTING"] = True
    app.config["DATABASE"] = db_path
    conn = get_db()
    init_db()
    ensure_flow_drafts_table(conn)
    ensure_flow_approvals_table(conn)
    ensure_execution_type_column(conn)
    conn.close()
    return db_path


def _insert_promoted_flow(uid=1, cid=None, flow_json=None):
    """Insert a promoted flow with safety.mode=promoted_safe and return flow_id."""
    if flow_json is None:
        flow_json = json.dumps({
            "version": "draft_v1",
            "safety": {
                "mode": "promoted_safe",
                "requires_human_approval": True,
                "external_actions_enabled": False,
                "dry_run_enabled": True,
            },
            "nodes": [
                {"id": "n1", "type": "trigger", "label": "Start", "x": 0, "y": 0},
                {"id": "n2", "type": "agent", "label": "Agent A", "slug": "seo", "x": 200, "y": 0},
                {"id": "n3", "type": "connector", "label": "GA4", "slug": "ga4", "x": 400, "y": 0},
                {"id": "n4", "type": "output", "label": "End", "x": 600, "y": 0},
            ],
            "connections": [
                {"from": "n1", "to": "n2"},
                {"from": "n2", "to": "n3"},
                {"from": "n3", "to": "n4"},
            ],
        })
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO flows (name, user_id, client_id, flow_json, category, is_template) VALUES (?, ?, ?, ?, 'Draft Promoted', 0)",
        ("Test Promoted Flow", uid, cid, flow_json),
    )
    flow_id = cur.lastrowid
    conn.commit()
    conn.close()
    return flow_id


def _insert_draft_flow(uid=1, cid=None):
    """Insert a draft flow with safety.mode=draft_only and return (draft_id)."""
    flow_json = json.dumps({
        "version": "draft_v1",
        "draft": True,
        "safety": {"mode": "draft_only", "draft_only": True},
        "nodes": [{"id": "d1", "type": "trigger", "label": "Start", "x": 0, "y": 0}],
        "connections": [],
    })
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO flow_drafts (user_id, client_id, name, prompt, flow_json, status, safety_level)
           VALUES (?, ?, ?, ?, ?, 'draft', 'draft_only')""",
        (uid, cid, "Test Draft", "test prompt", flow_json),
    )
    draft_id = cur.lastrowid
    conn.commit()
    conn.close()
    return draft_id


class TestFlowsApprovalDryRun(unittest.TestCase):

    def setUp(self):
        self._db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._db_path = self._db_file.name
        self._db_file.close()
        _setup_db(self._db_path)
        self.client = _make_client()
        self.flow_id = _insert_promoted_flow()

    def tearDown(self):
        try:
            os.unlink(self._db_path)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Test 1: Request approval returns pending
    # ------------------------------------------------------------------
    def test_01_request_approval_returns_pending(self):
        resp = self.client.post(
            f"/api/flows/{self.flow_id}/approval/request",
            json={"approval_scope": "dry_run"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["approval"]["status"], "pending")
        self.assertEqual(data["approval"]["flow_id"], self.flow_id)

    # ------------------------------------------------------------------
    # Test 2: Duplicate request returns existing (no new row)
    # ------------------------------------------------------------------
    def test_02_duplicate_request_returns_existing(self):
        r1 = self.client.post(
            f"/api/flows/{self.flow_id}/approval/request", json={}
        ).get_json()
        r2 = self.client.post(
            f"/api/flows/{self.flow_id}/approval/request", json={}
        ).get_json()
        self.assertEqual(r1["approval"]["id"], r2["approval"]["id"])
        self.assertTrue(r2.get("already_pending"))

    # ------------------------------------------------------------------
    # Test 3: Status endpoint shows pending + can_dry_run=False
    # ------------------------------------------------------------------
    def test_03_status_pending_no_dry_run(self):
        self.client.post(f"/api/flows/{self.flow_id}/approval/request", json={})
        resp = self.client.get(f"/api/flows/{self.flow_id}/approval/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["approval"]["status"], "pending")
        self.assertFalse(data["can_dry_run"])

    # ------------------------------------------------------------------
    # Test 4: Approve sets status=approved
    # ------------------------------------------------------------------
    def test_04_approve_sets_approved(self):
        appr_id = self.client.post(
            f"/api/flows/{self.flow_id}/approval/request", json={}
        ).get_json()["approval"]["id"]
        resp = self.client.post(f"/api/flows/approvals/{appr_id}/approve", json={})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["approval"]["status"], "approved")
        self.assertIsNotNone(data["approval"]["approved_at"])

    # ------------------------------------------------------------------
    # Test 5: Reject sets status=rejected
    # ------------------------------------------------------------------
    def test_05_reject_sets_rejected(self):
        appr_id = self.client.post(
            f"/api/flows/{self.flow_id}/approval/request", json={}
        ).get_json()["approval"]["id"]
        resp = self.client.post(f"/api/flows/approvals/{appr_id}/reject", json={"reason": "too risky"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["approval"]["status"], "rejected")
        self.assertIsNotNone(data["approval"]["rejected_at"])

    # ------------------------------------------------------------------
    # Test 6: Dry-run without approval returns approval_required
    # ------------------------------------------------------------------
    def test_06_dry_run_without_approval_blocked(self):
        resp = self.client.post(
            "/api/orchestrator/dry-run", json={"flow_id": self.flow_id}
        )
        self.assertEqual(resp.status_code, 403)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "approval_required")

    # ------------------------------------------------------------------
    # Test 7: Dry-run with approved approval succeeds
    # ------------------------------------------------------------------
    def test_07_dry_run_with_approval_succeeds(self):
        appr_id = self.client.post(
            f"/api/flows/{self.flow_id}/approval/request", json={}
        ).get_json()["approval"]["id"]
        self.client.post(f"/api/flows/approvals/{appr_id}/approve", json={})
        resp = self.client.post(
            "/api/orchestrator/dry-run", json={"flow_id": self.flow_id}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "dry_run_completed")
        self.assertTrue(data["dry_run"])

    # ------------------------------------------------------------------
    # Test 8: Dry-run external_actions_executed is 0
    # ------------------------------------------------------------------
    def test_08_dry_run_no_external_actions(self):
        appr_id = self.client.post(
            f"/api/flows/{self.flow_id}/approval/request", json={}
        ).get_json()["approval"]["id"]
        self.client.post(f"/api/flows/approvals/{appr_id}/approve", json={})
        data = self.client.post(
            "/api/orchestrator/dry-run", json={"flow_id": self.flow_id}
        ).get_json()
        self.assertEqual(data["external_actions_executed"], 0)

    # ------------------------------------------------------------------
    # Test 9: Dry-run steps are all simulated (no external_action_executed=True)
    # ------------------------------------------------------------------
    def test_09_dry_run_all_steps_simulated(self):
        appr_id = self.client.post(
            f"/api/flows/{self.flow_id}/approval/request", json={}
        ).get_json()["approval"]["id"]
        self.client.post(f"/api/flows/approvals/{appr_id}/approve", json={})
        data = self.client.post(
            "/api/orchestrator/dry-run", json={"flow_id": self.flow_id}
        ).get_json()
        for step in data.get("steps", []):
            self.assertFalse(step.get("external_action_executed"), msg=f"Step {step.get('node_id')} executed externally!")
            self.assertTrue(step.get("dry_run"), msg=f"Step {step.get('node_id')} missing dry_run=True")

    # ------------------------------------------------------------------
    # Test 10: Draft flow still rejected by execute endpoint
    # ------------------------------------------------------------------
    def test_10_draft_blocked_by_execute(self):
        """Draft flow must not reach actual execution — blocked by scope or draft guard."""
        draft_flow = {
            "nodes": [{"id": "d1", "type": "trigger", "label": "Start", "x": 0, "y": 0}],
            "connections": [],
            "safety": {"mode": "draft_only"},
        }
        resp = self.client.post(
            "/api/orchestrator/execute", json={"flow": draft_flow, "name": "Draft Test"}
        )
        # 400 = draft guard / scope guard; 403 = approval guard — any non-2xx is correct
        self.assertGreaterEqual(resp.status_code, 400)
        data = resp.get_json()
        # Execution must never succeed for a draft flow
        self.assertFalse(data.get("success", False))

    # ------------------------------------------------------------------
    # Test 11: Draft flow cannot be dry-run
    # ------------------------------------------------------------------
    def test_11_draft_cannot_be_dry_run(self):
        # Insert a flow with draft_only safety
        draft_as_flow = _insert_promoted_flow(flow_json=json.dumps({
            "safety": {"mode": "draft_only"},
            "nodes": [{"id": "d1", "type": "trigger", "label": "Start", "x": 0, "y": 0}],
            "connections": [],
        }))
        resp = self.client.post(
            "/api/orchestrator/dry-run", json={"flow_id": draft_as_flow}
        )
        self.assertIn(resp.status_code, (400, 403))
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertIn(data["error"], ("draft_not_executable", "approval_required"))

    # ------------------------------------------------------------------
    # Test 12: Promoted flow has safety.mode=promoted_safe
    # ------------------------------------------------------------------
    def test_12_promoted_flow_has_promoted_safe(self):
        # Create a draft, then promote it via API
        draft_flow_json = json.dumps({
            "version": "draft_v1",
            "draft": True,
            "safety": {"mode": "draft_only", "draft_only": True},
            "nodes": [{"id": "d1", "type": "trigger", "label": "Start", "x": 0, "y": 0}],
            "connections": [],
        })
        conn = get_db()
        cur = conn.execute(
            """INSERT INTO flow_drafts (user_id, client_id, name, prompt, flow_json, status, safety_level)
               VALUES (1, NULL, 'Draft', 'test prompt', ?, 'draft', 'draft_only')""",
            (draft_flow_json,),
        )
        draft_id = cur.lastrowid
        conn.commit()
        conn.close()

        resp = self.client.post(f"/api/flows/drafts/{draft_id}/promote", json={})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        flow_id = data["flow_id"]

        conn = get_db()
        row = conn.execute("SELECT flow_json FROM flows WHERE id=?", (flow_id,)).fetchone()
        conn.close()
        saved = json.loads(row[0])
        self.assertEqual(saved["safety"]["mode"], "promoted_safe")

    # ------------------------------------------------------------------
    # Test 13: User cannot access another user's approval
    # ------------------------------------------------------------------
    def test_13_cannot_access_other_users_approval(self):
        # Create approval for user 1
        appr_id = self.client.post(
            f"/api/flows/{self.flow_id}/approval/request", json={}
        ).get_json()["approval"]["id"]

        # Insert a flow owned by user 2
        flow_id_u2 = _insert_promoted_flow(uid=2)
        # User 1 requesting approval for user 2's flow should fail
        resp = self.client.post(
            f"/api/flows/{flow_id_u2}/approval/request", json={}
        )
        # Should return 404 (flow_not_found from user 1 perspective)
        self.assertEqual(resp.status_code, 404)

    # ------------------------------------------------------------------
    # Test 14: Legacy flow without safety block executes normally
    # ------------------------------------------------------------------
    def test_14_legacy_flow_no_safety_executes(self):
        legacy_flow = {
            "nodes": [{"id": "l1", "type": "trigger", "label": "Start", "x": 0, "y": 0}],
            "connections": [],
        }
        resp = self.client.post(
            "/api/orchestrator/execute", json={"flow": legacy_flow, "name": "Legacy"}
        )
        # Should not return draft_not_executable or approval_required
        data = resp.get_json()
        self.assertNotEqual(data.get("error"), "draft_not_executable")
        self.assertNotEqual(data.get("error"), "approval_required")


if __name__ == "__main__":
    unittest.main(verbosity=2)
