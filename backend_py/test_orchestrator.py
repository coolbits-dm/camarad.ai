"""
test_orchestrator.py — Orchestrator Engine Tests (45 tests)
Tests: templates, smart routing, agent briefs, flow execution, execution history
"""
import unittest, json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from app import app, get_db

class OrchestratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()

    @staticmethod
    def _hdr(uid=1, cid=None):
        h = {"X-User-ID": str(uid)}
        if cid is not None:
            h["X-Client-ID"] = str(cid)
        return h

    def _create_client(self, name):
        r = self.client.post(
            "/api/clients",
            json={"type": "company", "company_name": name, "email": f"{name.lower().replace(' ', '-')[:24]}@example.com"},
            headers=self._hdr(1),
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertTrue(data.get("success"))
        return int(data["client"]["id"])

    def _delete_client(self, client_id):
        self.client.delete(f"/api/clients/{client_id}", headers=self._hdr(1))

    def _delete_flow_by_name(self, flow_name):
        with app.app_context():
            conn = get_db()
            conn.execute("DELETE FROM flows WHERE user_id = ? AND name = ?", (1, flow_name))
            conn.commit()
            conn.close()

    def _delete_connector_scope(self, slug, client_id):
        with app.app_context():
            conn = get_db()
            conn.execute(
                "DELETE FROM connectors_config WHERE user_id = ? AND connector_slug = ? AND COALESCE(client_id, 0) = ?",
                (1, slug, int(client_id) if client_id else 0),
            )
            conn.commit()
            conn.close()

    def _delete_executions_by_flow_name(self, flow_name):
        with app.app_context():
            conn = get_db()
            conn.execute("DELETE FROM flow_executions WHERE user_id = ? AND flow_name = ?", (1, flow_name))
            conn.commit()
            conn.close()
    # ── Templates ──────────────────────────────────────────────────

    def test_templates_all(self):
        r = self.client.get("/api/flows/templates")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 10)
        for t in data:
            self.assertIn("id", t)
            self.assertIn("name", t)
            self.assertIn("nodes", t)
            self.assertIn("connections", t)
            self.assertIn("category", t)

    def test_templates_filter_category(self):
        r = self.client.get("/api/flows/templates?category=Marketing")
        data = r.get_json()
        self.assertGreaterEqual(len(data), 2)  # Marketing Report + SEO Audit + Social Review
        for t in data:
            self.assertEqual(t["category"], "Marketing")

    def test_templates_filter_engineering(self):
        r = self.client.get("/api/flows/templates?category=Engineering")
        data = r.get_json()
        self.assertGreaterEqual(len(data), 1)
        self.assertTrue(any("devops" in str(t.get("name", "")).lower() for t in data))
        for t in data:
            self.assertEqual(t.get("category"), "Engineering")

    def test_templates_structure(self):
        r = self.client.get("/api/flows/templates")
        tpl = r.get_json()[0]
        # Check nodes have required fields
        for n in tpl["nodes"]:
            self.assertIn("id", n)
            self.assertIn("type", n)
            self.assertIn("x", n)
            self.assertIn("y", n)
            self.assertIn("label", n)
        # Check connections reference valid node IDs
        node_ids = {n["id"] for n in tpl["nodes"]}
        for c in tpl["connections"]:
            self.assertIn(c["from"], node_ids)
            self.assertIn(c["to"], node_ids)

    def test_fallback_templates_scoped_per_client(self):
        tag = f"scope-{os.getpid()}-{self._testMethodName}"
        c1 = self._create_client(f"{tag}-a")
        c2 = self._create_client(f"{tag}-b")
        tpl_a = f"{tag}-fallback-a"
        tpl_b = f"{tag}-fallback-b"
        try:
            body_a = {
                "name": tpl_a,
                "flow": {"nodes": [{"id": "n1", "type": "trigger", "label": "A"}], "connections": []},
                "is_template": True,
                "category": "QA",
                "description": "fallback-a"
            }
            body_b = {
                "name": tpl_b,
                "flow": {"nodes": [{"id": "n1", "type": "trigger", "label": "B"}], "connections": []},
                "is_template": True,
                "category": "QA",
                "description": "fallback-b"
            }
            self.assertEqual(self.client.post("/api/flows", json=body_a, headers=self._hdr(1, c1)).status_code, 200)
            self.assertEqual(self.client.post("/api/flows", json=body_b, headers=self._hdr(1, c2)).status_code, 200)

            list_a = self.client.get("/api/orchestrator/templates", headers=self._hdr(1, c1)).get_json()
            list_b = self.client.get("/api/orchestrator/templates", headers=self._hdr(1, c2)).get_json()
            names_a = {str(x.get("name")) for x in list_a}
            names_b = {str(x.get("name")) for x in list_b}

            self.assertIn(tpl_a, names_a)
            self.assertNotIn(tpl_b, names_a)
            self.assertIn(tpl_b, names_b)
            self.assertNotIn(tpl_a, names_b)
        finally:
            self._delete_flow_by_name(tpl_a)
            self._delete_flow_by_name(tpl_b)
            self._delete_client(c1)
            self._delete_client(c2)

    def test_fallback_templates_unknown_client_returns_empty(self):
        r = self.client.get("/api/orchestrator/templates", headers=self._hdr(1, 99999117))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), [])
    # ── Smart Routing ──────────────────────────────────────────────

    def test_route_ppc_task(self):
        r = self.client.post("/api/orchestrator/route",
            json={"task": "optimize google ads campaign and improve ROAS"})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("matches", data)
        self.assertGreater(len(data["matches"]), 0)
        top = data["matches"][0]
        self.assertEqual(top["agent_slug"], "ppc-specialist")
        self.assertGreater(top["confidence"], 0.3)

    def test_route_devops_task(self):
        r = self.client.post("/api/orchestrator/route",
            json={"task": "deploy to AWS infrastructure with CI/CD pipeline"})
        data = r.get_json()
        slugs = [m["agent_slug"] for m in data["matches"]]
        self.assertIn("devops-infra", slugs)

    def test_route_finance_task(self):
        r = self.client.post("/api/orchestrator/route",
            json={"task": "analyze revenue profit and budget forecast"})
        data = r.get_json()
        top = data["matches"][0]
        self.assertEqual(top["agent_slug"], "cfo-finance")

    def test_route_returns_connectors(self):
        r = self.client.post("/api/orchestrator/route",
            json={"task": "google ads campaign bid optimization"})
        data = r.get_json()
        top = data["matches"][0]
        self.assertIn("connectors", top)
        connector_names = [c["name"] for c in top["connectors"]]
        self.assertIn("Google Ads", connector_names)

    def test_route_live_connector_status(self):
        r = self.client.post("/api/orchestrator/route",
            json={"task": "deploy infrastructure monitoring"})
        data = r.get_json()
        # devops-infra should have GitHub, AWS, Vercel as live
        devops = next((m for m in data["matches"] if m["agent_slug"] == "devops-infra"), None)
        self.assertIsNotNone(devops)
        live = [c for c in devops["connectors"] if c["status"] == "live"]
        live_names = [c["name"] for c in live]
        self.assertIn("GitHub", live_names)
        self.assertIn("AWS", live_names)
        self.assertIn("Vercel", live_names)

    def test_route_top_k(self):
        r = self.client.post("/api/orchestrator/route",
            json={"task": "marketing campaign analytics data", "top_k": 2})
        data = r.get_json()
        self.assertLessEqual(len(data["matches"]), 2)

    def test_route_no_task(self):
        r = self.client.post("/api/orchestrator/route", json={"task": ""})
        self.assertEqual(r.status_code, 400)

    def test_route_total_candidates(self):
        r = self.client.post("/api/orchestrator/route",
            json={"task": "marketing strategy growth brand campaign"})
        data = r.get_json()
        self.assertIn("total_candidates", data)
        self.assertGreater(data["total_candidates"], 0)

    # ── Agent Briefs ───────────────────────────────────────────────

    def test_agent_brief_ppc(self):
        r = self.client.get("/api/orchestrator/agent-brief/ppc-specialist")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("agent", data)
        self.assertEqual(data["agent"]["slug"], "ppc-specialist")
        self.assertIn("connector_summaries", data)
        self.assertGreater(data["total_live"], 0)

    def test_agent_brief_cfo(self):
        r = self.client.get("/api/orchestrator/agent-brief/cfo-finance")
        data = r.get_json()
        live_names = [c["name"] for c in data["connector_summaries"] if c["status"] == "live"]
        self.assertIn("Stripe", live_names)
        self.assertIn("PayPal", live_names)
        self.assertIn("Shopify", live_names)
        self.assertIn("QuickBooks", live_names)

    def test_agent_brief_has_kpis(self):
        r = self.client.get("/api/orchestrator/agent-brief/devops-infra")
        data = r.get_json()
        live = [c for c in data["connector_summaries"] if c["status"] == "live"]
        # At least GitHub, AWS, Vercel should have KPIs
        has_kpis = [c for c in live if c.get("kpis")]
        self.assertGreater(len(has_kpis), 0)

    def test_agent_brief_not_found(self):
        r = self.client.get("/api/orchestrator/agent-brief/nonexistent-agent")
        self.assertEqual(r.status_code, 404)

    # ── Flow Execution ─────────────────────────────────────────────

    def test_execute_simple_flow(self):
        flow = {
            "nodes": [
                {"id": "n1", "type": "trigger", "x": 0, "y": 0, "label": "Start"},
                {"id": "n2", "type": "connector", "x": 200, "y": 0, "slug": "github", "label": "GitHub"},
                {"id": "n3", "type": "output", "x": 400, "y": 0, "label": "Done"},
            ],
            "connections": [{"from": "n1", "to": "n2"}, {"from": "n2", "to": "n3"}],
        }
        r = self.client.post("/api/orchestrator/execute",
            json={"flow": flow, "name": "Test Simple"})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["steps_executed"], 3)
        self.assertEqual(data["nodes_total"], 3)
        self.assertGreater(data["elapsed_ms"], 0)

    def test_execute_connector_pulls_kpis(self):
        flow = {
            "nodes": [
                {"id": "n1", "type": "trigger", "x": 0, "y": 0, "label": "Start"},
                {"id": "n2", "type": "connector", "x": 200, "y": 0, "slug": "stripe", "label": "Stripe"},
                {"id": "n3", "type": "output", "x": 400, "y": 0, "label": "Report"},
            ],
            "connections": [{"from": "n1", "to": "n2"}, {"from": "n2", "to": "n3"}],
        }
        r = self.client.post("/api/orchestrator/execute", json={"flow": flow})
        data = r.get_json()
        # Step 2 should be the connector with live KPIs
        connector_step = data["results"][1]
        self.assertEqual(connector_step["type"], "connector")
        self.assertEqual(connector_step["status"], "ok")
        self.assertIn("kpis", connector_step["data"])
        self.assertGreater(len(connector_step["data"]["kpis"]), 0)

    def test_execute_agent_node(self):
        flow = {
            "nodes": [
                {"id": "n1", "type": "trigger", "x": 0, "y": 0, "label": "Start"},
                {"id": "n2", "type": "connector", "x": 200, "y": 0, "slug": "github", "label": "GitHub"},
                {"id": "n3", "type": "agent", "x": 400, "y": 0, "slug": "devops-infra", "label": "DevOps"},
                {"id": "n4", "type": "output", "x": 600, "y": 0, "label": "Report"},
            ],
            "connections": [
                {"from": "n1", "to": "n2"}, {"from": "n2", "to": "n3"}, {"from": "n3", "to": "n4"}
            ],
        }
        r = self.client.post("/api/orchestrator/execute", json={"flow": flow})
        data = r.get_json()
        agent_step = next(s for s in data["results"] if s["type"] == "agent")
        self.assertEqual(agent_step["status"], "ok")
        self.assertIn("analysis", agent_step["data"])
        self.assertEqual(agent_step["data"]["input_connectors"], 1)

    def test_execute_condition_node(self):
        flow = {
            "nodes": [
                {"id": "n1", "type": "trigger", "x": 0, "y": 0, "label": "Start"},
                {"id": "n2", "type": "condition", "x": 200, "y": 0, "label": "Is Critical?"},
                {"id": "n3", "type": "output", "x": 400, "y": 0, "label": "Alert"},
            ],
            "connections": [{"from": "n1", "to": "n2"}, {"from": "n2", "to": "n3"}],
        }
        r = self.client.post("/api/orchestrator/execute", json={"flow": flow})
        data = r.get_json()
        cond_step = next(s for s in data["results"] if s["type"] == "condition")
        self.assertTrue(cond_step["data"]["evaluated"])

    def test_execute_returns_structured_trace_steps(self):
        flow = {
            "nodes": [
                {"id": "n1", "type": "trigger", "x": 0, "y": 0, "label": "Start"},
                {"id": "n2", "type": "connector", "x": 200, "y": 0, "slug": "google-ads", "label": "Google Ads"},
                {"id": "n3", "type": "output", "x": 400, "y": 0, "label": "Done"},
            ],
            "connections": [{"from": "n1", "to": "n2"}, {"from": "n2", "to": "n3"}],
        }
        r = self.client.post("/api/orchestrator/execute", json={"flow": flow, "name": "Trace Struct"})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("steps", data)
        self.assertIsInstance(data["steps"], list)
        self.assertEqual(len(data["steps"]), 3)

    def test_execute_trace_step_fields(self):
        flow = {
            "nodes": [
                {"id": "n1", "type": "trigger", "x": 0, "y": 0, "label": "Start"},
                {"id": "n2", "type": "connector", "x": 200, "y": 0, "slug": "stripe", "label": "Stripe"},
                {"id": "n3", "type": "output", "x": 400, "y": 0, "label": "Done"},
            ],
            "connections": [{"from": "n1", "to": "n2"}, {"from": "n2", "to": "n3"}],
        }
        data = self.client.post("/api/orchestrator/execute", json={"flow": flow}).get_json()
        for step in data["steps"]:
            self.assertIn("node_label", step)
            self.assertIn("type", step)
            self.assertIn("status", step)
            self.assertIn("input", step)
            self.assertIn("output", step)
            self.assertIn("fail_reason", step)
            self.assertIn("duration_ms", step)
            self.assertIn(step["status"], ["success", "warning", "error"])

    def test_execute_trace_duration_real_and_varied(self):
        flow = {
            "nodes": [
                {"id": "n1", "type": "trigger", "x": 0, "y": 0, "label": "Start"},
                {"id": "n2", "type": "connector", "x": 180, "y": 0, "slug": "google-ads", "label": "Google Ads"},
                {"id": "n3", "type": "agent", "x": 360, "y": 0, "slug": "ppc-specialist", "label": "PPC"},
                {"id": "n4", "type": "condition", "x": 540, "y": 0, "label": "ROAS > 3"},
                {"id": "n5", "type": "output", "x": 720, "y": 0, "label": "Done"},
            ],
            "connections": [
                {"from": "n1", "to": "n2"},
                {"from": "n2", "to": "n3"},
                {"from": "n3", "to": "n4"},
                {"from": "n4", "to": "n5"},
            ],
        }
        data = self.client.post("/api/orchestrator/execute", json={"flow": flow}).get_json()
        durations = [float(s.get("duration_ms", 0)) for s in data["steps"]]
        self.assertTrue(all(d > 0 for d in durations))
        self.assertGreater(max(durations) - min(durations), 1.0)

    def test_execute_trace_condition_warning_status(self):
        flow = {
            "nodes": [
                {"id": "n1", "type": "trigger", "x": 0, "y": 0, "label": "Start"},
                {"id": "n2", "type": "connector", "x": 200, "y": 0, "slug": "google-ads", "label": "Google Ads"},
                {"id": "n3", "type": "condition", "x": 400, "y": 0, "label": "ROAS > 999", "config": {"condition_metric": "ROAS", "condition_operator": ">", "condition_value": "999"}},
                {"id": "n4", "type": "output", "x": 600, "y": 0, "label": "End"},
            ],
            "connections": [
                {"from": "n1", "to": "n2"},
                {"from": "n2", "to": "n3"},
                {"from": "n3", "to": "n4"},
            ],
        }
        data = self.client.post("/api/orchestrator/execute", json={"flow": flow}).get_json()
        cond = next(s for s in data["steps"] if s["type"] == "condition")
        self.assertEqual(cond["status"], "warning")
        self.assertTrue(cond.get("fail_reason"))

    def test_execute_trace_connector_kpi_output(self):
        flow = {
            "nodes": [
                {"id": "n1", "type": "trigger", "x": 0, "y": 0, "label": "Start"},
                {"id": "n2", "type": "connector", "x": 200, "y": 0, "slug": "google-ads", "label": "Google Ads"},
                {"id": "n3", "type": "output", "x": 400, "y": 0, "label": "Done"},
            ],
            "connections": [{"from": "n1", "to": "n2"}, {"from": "n2", "to": "n3"}],
        }
        data = self.client.post("/api/orchestrator/execute", json={"flow": flow}).get_json()
        connector = next(s for s in data["steps"] if s["type"] == "connector")
        self.assertIn("ROAS", connector.get("output", "").upper())

    def test_execute_trace_summary_counts_consistent(self):
        flow = {
            "nodes": [
                {"id": "n1", "type": "trigger", "x": 0, "y": 0, "label": "Start"},
                {"id": "n2", "type": "connector", "x": 200, "y": 0, "slug": "github", "label": "GitHub"},
                {"id": "n3", "type": "output", "x": 400, "y": 0, "label": "Done"},
            ],
            "connections": [{"from": "n1", "to": "n2"}, {"from": "n2", "to": "n3"}],
        }
        data = self.client.post("/api/orchestrator/execute", json={"flow": flow}).get_json()
        total = int(data.get("success_steps", 0)) + int(data.get("warning_steps", 0)) + int(data.get("failed_steps", 0))
        self.assertEqual(total, data.get("steps_executed"))
    def test_execute_trace_response_has_success_and_total_duration(self):
        flow = {
            "nodes": [
                {"id": "n1", "type": "trigger", "x": 0, "y": 0, "label": "Start"},
                {"id": "n2", "type": "output", "x": 200, "y": 0, "label": "Done"},
            ],
            "connections": [{"from": "n1", "to": "n2"}],
        }
        r = self.client.post("/api/orchestrator/execute", json={"flow": flow})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertTrue(data.get("success"))
        self.assertIn("total_duration_ms", data)
        self.assertGreater(float(data.get("total_duration_ms", 0) or 0), 0.0)
        self.assertAlmostEqual(float(data.get("total_duration_ms", 0) or 0), float(data.get("elapsed_ms", 0) or 0), places=2)

    def test_execute_trace_persists_flow_id_in_executions(self):
        tag = f"scope-{os.getpid()}-{self._testMethodName}"
        flow_name = f"{tag}-flow"
        run_name = f"{tag}-run"
        flow = {
            "nodes": [
                {"id": "n1", "type": "trigger", "x": 0, "y": 0, "label": "Start"},
                {"id": "n2", "type": "output", "x": 200, "y": 0, "label": "Done"},
            ],
            "connections": [{"from": "n1", "to": "n2"}],
        }

        flow_id = None
        try:
            create = self.client.post("/api/flows", json={"name": flow_name, "flow": flow})
            self.assertEqual(create.status_code, 200)
            create_data = create.get_json()
            self.assertTrue(create_data.get("success"))
            flow_id = int(create_data.get("flow_id"))

            run = self.client.post("/api/orchestrator/execute", json={"flow": flow, "flow_id": flow_id, "name": run_name})
            self.assertEqual(run.status_code, 200)
            run_data = run.get_json()
            trace_exec_id = int(run_data.get("trace_execution_id") or 0)
            self.assertGreater(trace_exec_id, 0)
            self.assertEqual(int(run_data.get("flow_id") or 0), flow_id)

            with app.app_context():
                conn = get_db()
                row = conn.execute("SELECT flow_id FROM executions WHERE id = ?", (trace_exec_id,)).fetchone()
                conn.close()

            self.assertIsNotNone(row)
            self.assertEqual(int(row[0] or 0), flow_id)
        finally:
            with app.app_context():
                conn = get_db()
                if flow_id:
                    conn.execute("DELETE FROM executions WHERE user_id = ? AND flow_id = ?", (1, flow_id))
                conn.execute("DELETE FROM flow_executions WHERE user_id = ? AND flow_name = ?", (1, run_name))
                conn.commit()
                conn.close()
            self._delete_flow_by_name(flow_name)

    def test_execute_trace_persists_in_executions_table(self):
        flow = {
            "nodes": [
                {"id": "n1", "type": "trigger", "x": 0, "y": 0, "label": "Start"},
                {"id": "n2", "type": "output", "x": 200, "y": 0, "label": "End"},
            ],
            "connections": [{"from": "n1", "to": "n2"}],
        }
        data = self.client.post("/api/orchestrator/execute", json={"flow": flow, "name": "Persist Trace"}).get_json()
        trace_exec_id = data.get("trace_execution_id")
        self.assertIsNotNone(trace_exec_id)

        with app.app_context():
            conn = get_db()
            row = conn.execute("SELECT id, status, steps_json, started_at, finished_at FROM executions WHERE id = ?", (trace_exec_id,)).fetchone()
            conn.close()

        self.assertIsNotNone(row)
        self.assertIn(row[1], ["success", "warning", "error"])
        saved_steps = json.loads(row[2] or "[]")
        self.assertIsInstance(saved_steps, list)
        self.assertGreaterEqual(len(saved_steps), 2)

    def test_execute_trace_timestamps_present(self):
        flow = {
            "nodes": [
                {"id": "n1", "type": "trigger", "x": 0, "y": 0, "label": "Start"},
                {"id": "n2", "type": "output", "x": 200, "y": 0, "label": "End"},
            ],
            "connections": [{"from": "n1", "to": "n2"}],
        }
        data = self.client.post("/api/orchestrator/execute", json={"flow": flow}).get_json()
        self.assertIn("started_at", data)
        self.assertIn("finished_at", data)
        self.assertIn("T", data["started_at"])
        self.assertIn("T", data["finished_at"])
    def test_execute_saves_history(self):
        flow = {
            "nodes": [
                {"id": "n1", "type": "trigger", "x": 0, "y": 0, "label": "Test"},
                {"id": "n2", "type": "output", "x": 200, "y": 0, "label": "End"},
            ],
            "connections": [{"from": "n1", "to": "n2"}],
        }
        r = self.client.post("/api/orchestrator/execute",
            json={"flow": flow, "name": "History Test Flow"})
        data = r.get_json()
        self.assertIsNotNone(data.get("execution_id"))
        exec_id = data["execution_id"]

        # Check it appears in history
        r2 = self.client.get("/api/orchestrator/history")
        history = r2.get_json()
        found = any(h["id"] == exec_id for h in history)
        self.assertTrue(found, "Execution should appear in history")

    def test_execute_no_flow(self):
        r = self.client.post("/api/orchestrator/execute", json={})
        self.assertEqual(r.status_code, 400)

    # ── Execution History ──────────────────────────────────────────

    def test_history_list(self):
        r = self.client.get("/api/orchestrator/history")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIsInstance(data, list)

    def test_history_detail(self):
        # First execute a flow
        flow = {
            "nodes": [
                {"id": "n1", "type": "trigger", "x": 0, "y": 0, "label": "Detail Test"},
                {"id": "n2", "type": "output", "x": 200, "y": 0, "label": "End"},
            ],
            "connections": [{"from": "n1", "to": "n2"}],
        }
        r = self.client.post("/api/orchestrator/execute",
            json={"flow": flow, "name": "Detail Flow"})
        exec_id = r.get_json()["execution_id"]

        # Get detail
        r2 = self.client.get(f"/api/orchestrator/history/{exec_id}")
        self.assertEqual(r2.status_code, 200)
        data = r2.get_json()
        self.assertEqual(data["id"], exec_id)
        self.assertEqual(data["flow_name"], "Detail Flow")
        self.assertIsInstance(data["results"], list)
        self.assertGreater(len(data["results"]), 0)

    def test_history_not_found(self):
        r = self.client.get("/api/orchestrator/history/999999")
        self.assertEqual(r.status_code, 404)

    def test_execute_rejects_unknown_client_scope(self):
        flow = {
            "nodes": [
                {"id": "n1", "type": "trigger", "x": 0, "y": 0, "label": "Start"},
                {"id": "n2", "type": "output", "x": 200, "y": 0, "label": "End"},
            ],
            "connections": [{"from": "n1", "to": "n2"}],
        }
        r = self.client.post("/api/orchestrator/execute", json={"flow": flow}, headers=self._hdr(1, 99999991))
        self.assertEqual(r.status_code, 404)

    def test_execute_response_includes_client_id(self):
        tag = f"scope-{os.getpid()}-{self._testMethodName}"
        c1 = self._create_client(f"{tag}-client")
        try:
            flow = {
                "nodes": [
                    {"id": "n1", "type": "trigger", "x": 0, "y": 0, "label": "Start"},
                    {"id": "n2", "type": "output", "x": 200, "y": 0, "label": "End"},
                ],
                "connections": [{"from": "n1", "to": "n2"}],
            }
            r = self.client.post("/api/orchestrator/execute", json={"flow": flow, "name": f"{tag}-run"}, headers=self._hdr(1, c1))
            self.assertEqual(r.status_code, 200)
            data = r.get_json()
            self.assertEqual(int(data.get("client_id") or 0), c1)
        finally:
            self._delete_executions_by_flow_name(f"{tag}-run")
            self._delete_client(c1)

    def test_history_isolated_per_client_scope(self):
        tag = f"scope-{os.getpid()}-{self._testMethodName}"
        c1 = self._create_client(f"{tag}-a")
        c2 = self._create_client(f"{tag}-b")
        run_a = f"{tag}-run-a"
        run_b = f"{tag}-run-b"
        try:
            flow = {
                "nodes": [
                    {"id": "n1", "type": "trigger", "x": 0, "y": 0, "label": "Start"},
                    {"id": "n2", "type": "output", "x": 200, "y": 0, "label": "End"},
                ],
                "connections": [{"from": "n1", "to": "n2"}],
            }
            self.assertEqual(self.client.post("/api/orchestrator/execute", json={"flow": flow, "name": run_a}, headers=self._hdr(1, c1)).status_code, 200)
            self.assertEqual(self.client.post("/api/orchestrator/execute", json={"flow": flow, "name": run_b}, headers=self._hdr(1, c2)).status_code, 200)

            h1 = self.client.get("/api/orchestrator/history", headers=self._hdr(1, c1)).get_json()
            h2 = self.client.get("/api/orchestrator/history", headers=self._hdr(1, c2)).get_json()
            names1 = {str(x.get("flow_name")) for x in h1}
            names2 = {str(x.get("flow_name")) for x in h2}

            self.assertIn(run_a, names1)
            self.assertNotIn(run_b, names1)
            self.assertIn(run_b, names2)
            self.assertNotIn(run_a, names2)
        finally:
            self._delete_executions_by_flow_name(run_a)
            self._delete_executions_by_flow_name(run_b)
            self._delete_client(c1)
            self._delete_client(c2)

    def test_history_detail_respects_client_scope(self):
        tag = f"scope-{os.getpid()}-{self._testMethodName}"
        c1 = self._create_client(f"{tag}-a")
        c2 = self._create_client(f"{tag}-b")
        run_name = f"{tag}-detail"
        try:
            flow = {
                "nodes": [
                    {"id": "n1", "type": "trigger", "x": 0, "y": 0, "label": "Start"},
                    {"id": "n2", "type": "output", "x": 200, "y": 0, "label": "End"},
                ],
                "connections": [{"from": "n1", "to": "n2"}],
            }
            r = self.client.post("/api/orchestrator/execute", json={"flow": flow, "name": run_name}, headers=self._hdr(1, c1))
            self.assertEqual(r.status_code, 200)
            exec_id = int(r.get_json()["execution_id"])

            ok = self.client.get(f"/api/orchestrator/history/{exec_id}", headers=self._hdr(1, c1))
            self.assertEqual(ok.status_code, 200)

            blocked = self.client.get(f"/api/orchestrator/history/{exec_id}", headers=self._hdr(1, c2))
            self.assertEqual(blocked.status_code, 404)
        finally:
            self._delete_executions_by_flow_name(run_name)
            self._delete_client(c1)
            self._delete_client(c2)

    def test_flow_templates_filtered_per_client_scope(self):
        tag = f"scope-{os.getpid()}-{self._testMethodName}"
        c1 = self._create_client(f"{tag}-a")
        c2 = self._create_client(f"{tag}-b")
        tpl_a = f"{tag}-template-a"
        tpl_b = f"{tag}-template-b"
        try:
            body_a = {
                "name": tpl_a,
                "flow": {"nodes": [{"id": "n1", "type": "trigger", "label": "A"}], "connections": []},
                "is_template": True,
                "category": "QA",
                "description": "scoped-a"
            }
            body_b = {
                "name": tpl_b,
                "flow": {"nodes": [{"id": "n1", "type": "trigger", "label": "B"}], "connections": []},
                "is_template": True,
                "category": "QA",
                "description": "scoped-b"
            }
            self.assertEqual(self.client.post("/api/flows", json=body_a, headers=self._hdr(1, c1)).status_code, 200)
            self.assertEqual(self.client.post("/api/flows", json=body_b, headers=self._hdr(1, c2)).status_code, 200)

            list_a = self.client.get("/api/flows/templates", headers=self._hdr(1, c1)).get_json()
            list_b = self.client.get("/api/flows/templates", headers=self._hdr(1, c2)).get_json()
            names_a = {str(x.get("name")) for x in list_a}
            names_b = {str(x.get("name")) for x in list_b}

            self.assertIn(tpl_a, names_a)
            self.assertNotIn(tpl_b, names_a)
            self.assertIn(tpl_b, names_b)
            self.assertNotIn(tpl_a, names_b)
        finally:
            self._delete_flow_by_name(tpl_a)
            self._delete_flow_by_name(tpl_b)
            self._delete_client(c1)
            self._delete_client(c2)

    def test_flow_templates_unknown_client_returns_empty(self):
        r = self.client.get("/api/flows/templates", headers=self._hdr(1, 99999111))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), [])

    def test_active_context_filters_connectors_by_client(self):
        tag = f"scope-{os.getpid()}-{self._testMethodName}"
        c1 = self._create_client(f"{tag}-a")
        c2 = self._create_client(f"{tag}-b")
        try:
            self.assertEqual(
                self.client.post("/api/connectors/google-ads", json={"status": "Connected", "config": {"source": "a"}}, headers=self._hdr(1, c1)).status_code,
                200,
            )
            self.assertEqual(
                self.client.post("/api/connectors/ga4", json={"status": "Connected", "config": {"source": "b"}}, headers=self._hdr(1, c2)).status_code,
                200,
            )

            ctx_a = self.client.get("/api/active-context", headers=self._hdr(1, c1)).get_json()
            ctx_b = self.client.get("/api/active-context", headers=self._hdr(1, c2)).get_json()

            con_a = {str(x) for x in (ctx_a.get("active_connectors") or [])}
            con_b = {str(x) for x in (ctx_b.get("active_connectors") or [])}

            self.assertIn("google-ads", con_a)
            self.assertNotIn("ga4", con_a)
            self.assertIn("ga4", con_b)
            self.assertNotIn("google-ads", con_b)
        finally:
            self._delete_connector_scope("google-ads", c1)
            self._delete_connector_scope("ga4", c2)
            self._delete_client(c1)
            self._delete_client(c2)
    # ── Orchestrator Page ──────────────────────────────────────────

    def test_orchestrator_page_renders(self):
        r = self.client.get("/orchestrator")
        self.assertEqual(r.status_code, 200)
        html = r.data.decode()
        self.assertIn("Orchestrator", html)
        self.assertIn("Templates", html)
        self.assertIn("History", html)
        self.assertIn("Route", html)
        self.assertIn("canvas", html)


if __name__ == "__main__":
    unittest.main()


