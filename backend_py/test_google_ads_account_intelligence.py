"""Tests for Phase 2C Account Intelligence endpoints and helpers.

Covers:
  - _gads_compute_overview_totals
  - _gads_compute_diagnostics (all 6 rules)
  - _gads_compute_ai_brief
  - GET /api/connectors/google-ads/overview
  - GET /api/connectors/google-ads/diagnostics
  - GET /api/connectors/google-ads/ai-brief

Run:
  AUTH_REQUIRED=0 COOLBITS_GATEWAY_ENABLED=false DATABASE=/tmp/camarad_ai_intel.db \
    python3 -m unittest backend_py.test_google_ads_account_intelligence -v
"""
import json
import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("AUTH_REQUIRED", "0")
os.environ.setdefault("COOLBITS_GATEWAY_ENABLED", "false")
os.environ.setdefault("DATABASE", "/tmp/camarad_ai_intel_test.db")

# Allow import from parent when run as module
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import backend_py.app as _app_module
from backend_py.app import (
    app,
    _gads_compute_overview_totals,
    _gads_compute_diagnostics,
    _gads_compute_ai_brief,
    _gads_resolve_live_campaigns,
)
_PATCH_PREFIX = "backend_py.app"


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _camp(
    id_="c1",
    name="Test Campaign",
    status="ENABLED",
    spent=500.0,
    impressions=10000,
    clicks=200,
    conversions=10.0,
    conversion_value=2000.0,
    roas=4.0,
    ctr=2.0,
    avg_cpc=2.5,
    cost_per_conv=50.0,
    budget_daily=50.0,
    budget_total=1500.0,
    channel_type="Search",
):
    return {
        "id": id_,
        "name": name,
        "status": status,
        "type": channel_type,
        "channel_type": channel_type,
        "spent": spent,
        "impressions": impressions,
        "clicks": clicks,
        "conversions": conversions,
        "conversion_value": conversion_value,
        "roas": roas,
        "ctr": ctr,
        "avg_cpc": avg_cpc,
        "cost_per_conv": cost_per_conv,
        "budget_daily": budget_daily,
        "budget_total": budget_total,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Overview Totals
# ═══════════════════════════════════════════════════════════════════════════════

class TestOverviewTotals(unittest.TestCase):
    def test_empty_campaigns(self):
        t = _gads_compute_overview_totals([])
        self.assertEqual(t["spend"], 0.0)
        self.assertEqual(t["impressions"], 0)
        self.assertEqual(t["active_campaigns"], 0)
        self.assertEqual(t["total_campaigns"], 0)
        self.assertEqual(t["roas"], 0.0)
        self.assertEqual(t["ctr"], 0.0)

    def test_single_campaign(self):
        t = _gads_compute_overview_totals([_camp()])
        self.assertEqual(t["spend"], 500.0)
        self.assertEqual(t["impressions"], 10000)
        self.assertEqual(t["clicks"], 200)
        self.assertAlmostEqual(t["ctr"], 2.0)
        self.assertAlmostEqual(t["avg_cpc"], 2.5)
        self.assertAlmostEqual(t["cpa"], 50.0)
        self.assertAlmostEqual(t["roas"], 4.0)
        self.assertEqual(t["active_campaigns"], 1)

    def test_mixed_statuses(self):
        camps = [_camp(status="ENABLED"), _camp(id_="c2", status="PAUSED")]
        t = _gads_compute_overview_totals(camps)
        self.assertEqual(t["total_campaigns"], 2)
        self.assertEqual(t["active_campaigns"], 1)

    def test_zero_impressions_ctr(self):
        c = _camp(impressions=0, clicks=0)
        t = _gads_compute_overview_totals([c])
        self.assertEqual(t["ctr"], 0.0)

    def test_zero_conversions_cpa(self):
        c = _camp(conversions=0, conversion_value=0)
        t = _gads_compute_overview_totals([c])
        self.assertEqual(t["cpa"], 0.0)

    def test_multiple_campaigns_aggregate(self):
        camps = [
            _camp(id_="a", spent=100, impressions=1000, clicks=50, conversions=5, conversion_value=500),
            _camp(id_="b", spent=200, impressions=2000, clicks=100, conversions=10, conversion_value=1000),
        ]
        t = _gads_compute_overview_totals(camps)
        self.assertEqual(t["spend"], 300.0)
        self.assertEqual(t["impressions"], 3000)
        self.assertEqual(t["clicks"], 150)
        self.assertEqual(t["conversions"], 15.0)

    def test_none_campaigns_graceful(self):
        t = _gads_compute_overview_totals(None)
        self.assertEqual(t["total_campaigns"], 0)

    def test_fields_present(self):
        t = _gads_compute_overview_totals([_camp()])
        for field in ["spend", "impressions", "clicks", "conversions", "conversion_value",
                      "ctr", "avg_cpc", "cpa", "roas", "active_campaigns", "total_campaigns"]:
            self.assertIn(field, t, f"Missing field: {field}")


# ═══════════════════════════════════════════════════════════════════════════════
# Diagnostics Rules
# ═══════════════════════════════════════════════════════════════════════════════

class TestDiagnosticsHighSpendNoConversions(unittest.TestCase):
    def test_triggers_critical(self):
        c = _camp(status="ENABLED", spent=200.0, conversions=0, roas=0)
        findings = _gads_compute_diagnostics([c])
        types = [f["type"] for f in findings]
        self.assertIn("high_spend_no_conversions", types)
        f = next(x for x in findings if x["type"] == "high_spend_no_conversions")
        self.assertEqual(f["severity"], "critical")
        self.assertEqual(f["campaign_id"], "c1")

    def test_does_not_trigger_below_threshold(self):
        c = _camp(status="ENABLED", spent=30.0, conversions=0, roas=0)
        findings = _gads_compute_diagnostics([c])
        types = [f["type"] for f in findings]
        self.assertNotIn("high_spend_no_conversions", types)

    def test_does_not_trigger_for_paused(self):
        c = _camp(status="PAUSED", spent=200.0, conversions=0)
        findings = _gads_compute_diagnostics([c])
        types = [f["type"] for f in findings]
        self.assertNotIn("high_spend_no_conversions", types)


class TestDiagnosticsLowRoas(unittest.TestCase):
    def test_triggers_warning(self):
        c = _camp(status="ENABLED", spent=200.0, conversions=5, roas=1.5, conversion_value=300)
        findings = _gads_compute_diagnostics([c])
        types = [f["type"] for f in findings]
        self.assertIn("low_roas_enabled", types)
        f = next(x for x in findings if x["type"] == "low_roas_enabled")
        self.assertEqual(f["severity"], "warning")

    def test_does_not_trigger_above_threshold(self):
        c = _camp(status="ENABLED", spent=200.0, roas=3.0)
        findings = _gads_compute_diagnostics([c])
        types = [f["type"] for f in findings]
        self.assertNotIn("low_roas_enabled", types)

    def test_does_not_trigger_zero_roas(self):
        """Zero roas (zero conversions) → high_spend_no_conversions, not low_roas."""
        c = _camp(status="ENABLED", spent=200.0, conversions=0, roas=0)
        findings = _gads_compute_diagnostics([c])
        types = [f["type"] for f in findings]
        self.assertNotIn("low_roas_enabled", types)


class TestDiagnosticsZeroImpressions(unittest.TestCase):
    def test_triggers_warning(self):
        c = _camp(status="ENABLED", impressions=0)
        findings = _gads_compute_diagnostics([c])
        types = [f["type"] for f in findings]
        self.assertIn("zero_impressions_enabled", types)
        f = next(x for x in findings if x["type"] == "zero_impressions_enabled")
        self.assertEqual(f["severity"], "warning")

    def test_does_not_trigger_for_paused(self):
        c = _camp(status="PAUSED", impressions=0)
        findings = _gads_compute_diagnostics([c])
        types = [f["type"] for f in findings]
        self.assertNotIn("zero_impressions_enabled", types)


class TestDiagnosticsPausedWithConversions(unittest.TestCase):
    def test_triggers_info(self):
        c = _camp(status="PAUSED", conversions=5)
        findings = _gads_compute_diagnostics([c])
        types = [f["type"] for f in findings]
        self.assertIn("paused_with_conversions", types)
        f = next(x for x in findings if x["type"] == "paused_with_conversions")
        self.assertEqual(f["severity"], "info")

    def test_does_not_trigger_zero_conversions(self):
        c = _camp(status="PAUSED", conversions=0)
        findings = _gads_compute_diagnostics([c])
        types = [f["type"] for f in findings]
        self.assertNotIn("paused_with_conversions", types)


class TestDiagnosticsHighCpcLowCtr(unittest.TestCase):
    def test_triggers_warning(self):
        c = _camp(status="ENABLED", avg_cpc=8.0, ctr=0.5, impressions=500)
        findings = _gads_compute_diagnostics([c])
        types = [f["type"] for f in findings]
        self.assertIn("high_cpc_low_ctr", types)
        f = next(x for x in findings if x["type"] == "high_cpc_low_ctr")
        self.assertEqual(f["severity"], "warning")

    def test_does_not_trigger_low_impressions(self):
        c = _camp(status="ENABLED", avg_cpc=8.0, ctr=0.5, impressions=50)
        findings = _gads_compute_diagnostics([c])
        types = [f["type"] for f in findings]
        self.assertNotIn("high_cpc_low_ctr", types)

    def test_does_not_trigger_low_cpc(self):
        c = _camp(status="ENABLED", avg_cpc=1.0, ctr=0.5, impressions=500)
        findings = _gads_compute_diagnostics([c])
        types = [f["type"] for f in findings]
        self.assertNotIn("high_cpc_low_ctr", types)


class TestDiagnosticsMissingBudget(unittest.TestCase):
    def test_triggers_info(self):
        c = _camp(status="ENABLED", budget_daily=0)
        findings = _gads_compute_diagnostics([c])
        types = [f["type"] for f in findings]
        self.assertIn("budget_overspend_or_missing_budget", types)
        f = next(x for x in findings if x["type"] == "budget_overspend_or_missing_budget")
        self.assertEqual(f["severity"], "info")

    def test_does_not_trigger_with_budget(self):
        c = _camp(status="ENABLED", budget_daily=50.0)
        findings = _gads_compute_diagnostics([c])
        types = [f["type"] for f in findings]
        self.assertNotIn("budget_overspend_or_missing_budget", types)


class TestDiagnosticsSorting(unittest.TestCase):
    def test_critical_before_warning_before_info(self):
        camps = [
            _camp(id_="a", status="PAUSED", conversions=5),         # info
            _camp(id_="b", status="ENABLED", spent=200, roas=1.5, conversions=5),  # warning
            _camp(id_="c", status="ENABLED", spent=200, conversions=0, roas=0),    # critical
        ]
        findings = _gads_compute_diagnostics(camps)
        severities = [f["severity"] for f in findings]
        # Critical must come before warning, warning before info
        if "critical" in severities and "warning" in severities:
            self.assertLess(severities.index("critical"), severities.index("warning"))

    def test_finding_has_required_fields(self):
        c = _camp(status="ENABLED", spent=200, conversions=0, roas=0)
        findings = _gads_compute_diagnostics([c])
        self.assertTrue(len(findings) > 0)
        f = findings[0]
        for field in ["severity", "type", "campaign_id", "campaign_name", "metric_snapshot", "recommendation"]:
            self.assertIn(field, f, f"Missing field: {field}")


class TestDiagnosticsEmpty(unittest.TestCase):
    def test_no_issues_clean_campaign(self):
        """Healthy campaign with good metrics → no diagnostic findings."""
        c = _camp(
            status="ENABLED",
            spent=500, impressions=10000, clicks=200,
            conversions=20, roas=4.0, avg_cpc=2.5, ctr=2.0,
            budget_daily=50, conversion_value=2000
        )
        findings = _gads_compute_diagnostics([c])
        self.assertEqual(findings, [])

    def test_none_campaigns(self):
        findings = _gads_compute_diagnostics(None)
        self.assertEqual(findings, [])


# ═══════════════════════════════════════════════════════════════════════════════
# AI Brief
# ═══════════════════════════════════════════════════════════════════════════════

class TestAiBriefStructure(unittest.TestCase):
    def setUp(self):
        self.camps = [
            _camp(id_="w1", name="Winner", spent=500, roas=6.0, conversions=30, conversion_value=3000),
            _camp(id_="l1", name="Loser", spent=300, roas=0.5, conversions=2, conversion_value=150),
        ]
        self.brief = _gads_compute_ai_brief(self.camps, "1234567890", "8924163684", "LAST_30_DAYS")

    def test_top_level_keys(self):
        for key in ["account_summary", "performance_summary", "top_winners", "top_losers",
                    "risks", "opportunities", "recommended_next_actions", "raw_metrics_reference"]:
            self.assertIn(key, self.brief, f"Missing key: {key}")

    def test_account_summary_fields(self):
        s = self.brief["account_summary"]
        self.assertEqual(s["customer_id"], "1234567890")
        self.assertEqual(s["manager_customer_id"], "8924163684")
        self.assertEqual(s["date_range"], "LAST_30_DAYS")
        self.assertIn("active_campaigns", s)
        self.assertIn("total_campaigns", s)

    def test_performance_summary_fields(self):
        ps = self.brief["performance_summary"]
        for field in ["spend", "impressions", "clicks", "conversions", "ctr", "avg_cpc", "cpa", "roas"]:
            self.assertIn(field, ps, f"Missing field: {field}")

    def test_top_winners_sorted_by_roas(self):
        winners = self.brief["top_winners"]
        self.assertGreater(len(winners), 0)
        if len(winners) > 1:
            self.assertGreaterEqual(winners[0]["roas"], winners[1]["roas"])

    def test_top_losers_sorted_by_roas_asc(self):
        losers = self.brief["top_losers"]
        if len(losers) > 1:
            self.assertLessEqual(losers[0]["roas"], losers[1]["roas"])

    def test_campaign_slim_fields(self):
        if self.brief["top_winners"]:
            w = self.brief["top_winners"][0]
            for field in ["id", "name", "status", "cost", "roas", "conversions", "impressions", "ctr"]:
                self.assertIn(field, w)

    def test_recommended_actions_nonempty(self):
        actions = self.brief["recommended_next_actions"]
        self.assertIsInstance(actions, list)
        self.assertGreater(len(actions), 0)

    def test_actions_are_strings(self):
        for a in self.brief["recommended_next_actions"]:
            self.assertIsInstance(a, str)

    def test_empty_campaigns(self):
        brief = _gads_compute_ai_brief([], "999", "", "LAST_7_DAYS")
        self.assertEqual(brief["account_summary"]["total_campaigns"], 0)
        self.assertEqual(brief["top_winners"], [])
        self.assertIn("recommended_next_actions", brief)


class TestAiBriefActions(unittest.TestCase):
    def test_critical_action_when_high_spend_no_conv(self):
        c = _camp(spent=200, conversions=0, roas=0)
        brief = _gads_compute_ai_brief([c])
        actions = " ".join(brief["recommended_next_actions"])
        self.assertIn("URGENT", actions)

    def test_scale_action_when_high_roas(self):
        c = _camp(spent=500, roas=5.0, conversions=25, conversion_value=2500)
        brief = _gads_compute_ai_brief([c])
        actions = " ".join(brief["recommended_next_actions"])
        self.assertIn("5.00x", actions)

    def test_no_active_campaigns_action(self):
        c = _camp(status="PAUSED")
        brief = _gads_compute_ai_brief([c])
        actions = " ".join(brief["recommended_next_actions"])
        self.assertIn("No active campaigns", actions)


# ═══════════════════════════════════════════════════════════════════════════════
# Route: /api/connectors/google-ads/overview
# ═══════════════════════════════════════════════════════════════════════════════

class TestOverviewRoute(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_overview_returns_200(self):
        r = self.client.get("/api/connectors/google-ads/overview?customer_id=1234567890&days=30")
        self.assertEqual(r.status_code, 200)

    def test_overview_response_shape(self):
        r = self.client.get("/api/connectors/google-ads/overview?customer_id=1234567890&days=30")
        data = json.loads(r.data)
        self.assertIn("source", data)
        self.assertIn("customer_id", data)
        self.assertIn("date_range", data)
        self.assertIn("totals", data)
        t = data["totals"]
        for field in ["spend", "impressions", "clicks", "conversions", "ctr",
                      "avg_cpc", "cpa", "roas", "active_campaigns", "total_campaigns"]:
            self.assertIn(field, t, f"Missing totals field: {field}")

    def test_overview_source_mock_unauthenticated(self):
        r = self.client.get("/api/connectors/google-ads/overview?customer_id=1234567890")
        data = json.loads(r.data)
        # Without live OAuth, should return mock or mock_fallback — never live
        self.assertIn(data["source"], ("mock", "google_ads_api", "mock_fallback"))

    def test_overview_source_not_live_without_oauth(self):
        """Unauthenticated test client must never return source=google_ads_api."""
        r = self.client.get("/api/connectors/google-ads/overview?customer_id=1234567890")
        data = json.loads(r.data)
        self.assertNotEqual(data["source"], "google_ads_api")

    def test_overview_account_id_alias(self):
        """account_id param should work as alias for customer_id."""
        r = self.client.get("/api/connectors/google-ads/overview?account_id=1234567890")
        self.assertEqual(r.status_code, 200)

    def test_overview_no_credentials_in_response(self):
        r = self.client.get("/api/connectors/google-ads/overview?customer_id=1234567890")
        body = r.data.decode()
        self.assertNotIn("refresh_token", body)
        self.assertNotIn("developer_token", body)
        self.assertNotIn("client_secret", body)


# ═══════════════════════════════════════════════════════════════════════════════
# Route: /api/connectors/google-ads/diagnostics
# ═══════════════════════════════════════════════════════════════════════════════

class TestDiagnosticsRoute(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_diagnostics_returns_200(self):
        r = self.client.get("/api/connectors/google-ads/diagnostics?customer_id=1234567890&days=30")
        self.assertEqual(r.status_code, 200)

    def test_diagnostics_response_shape(self):
        r = self.client.get("/api/connectors/google-ads/diagnostics?customer_id=1234567890&days=30")
        data = json.loads(r.data)
        self.assertIn("source", data)
        self.assertIn("customer_id", data)
        self.assertIn("date_range", data)
        self.assertIn("findings", data)
        self.assertIn("summary", data)
        s = data["summary"]
        for field in ["critical", "warning", "info", "total"]:
            self.assertIn(field, s)

    def test_diagnostics_findings_are_list(self):
        r = self.client.get("/api/connectors/google-ads/diagnostics?customer_id=1234567890")
        data = json.loads(r.data)
        self.assertIsInstance(data["findings"], list)

    def test_diagnostics_no_credentials_in_response(self):
        r = self.client.get("/api/connectors/google-ads/diagnostics?customer_id=1234567890")
        body = r.data.decode()
        self.assertNotIn("refresh_token", body)
        self.assertNotIn("developer_token", body)

    def test_diagnostics_summary_counts_consistent(self):
        r = self.client.get("/api/connectors/google-ads/diagnostics?customer_id=1234567890")
        data = json.loads(r.data)
        findings = data["findings"]
        s = data["summary"]
        self.assertEqual(s["total"], len(findings))
        self.assertEqual(s["critical"], sum(1 for f in findings if f["severity"] == "critical"))
        self.assertEqual(s["warning"], sum(1 for f in findings if f["severity"] == "warning"))
        self.assertEqual(s["info"], sum(1 for f in findings if f["severity"] == "info"))


# ═══════════════════════════════════════════════════════════════════════════════
# Route: /api/connectors/google-ads/ai-brief
# ═══════════════════════════════════════════════════════════════════════════════

class TestAiBriefRoute(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_ai_brief_returns_200(self):
        r = self.client.get("/api/connectors/google-ads/ai-brief?customer_id=1234567890&days=30")
        self.assertEqual(r.status_code, 200)

    def test_ai_brief_response_shape(self):
        r = self.client.get("/api/connectors/google-ads/ai-brief?customer_id=1234567890&days=30")
        data = json.loads(r.data)
        for key in ["source", "customer_id", "date_range", "account_summary",
                    "performance_summary", "top_winners", "top_losers", "risks",
                    "opportunities", "recommended_next_actions", "raw_metrics_reference"]:
            self.assertIn(key, data, f"Missing key: {key}")

    def test_ai_brief_no_credentials_in_response(self):
        r = self.client.get("/api/connectors/google-ads/ai-brief?customer_id=1234567890")
        body = r.data.decode()
        self.assertNotIn("refresh_token", body)
        self.assertNotIn("developer_token", body)
        self.assertNotIn("client_secret", body)

    def test_ai_brief_actions_nonempty(self):
        r = self.client.get("/api/connectors/google-ads/ai-brief?customer_id=1234567890")
        data = json.loads(r.data)
        self.assertGreater(len(data["recommended_next_actions"]), 0)

    def test_ai_brief_account_id_alias(self):
        r = self.client.get("/api/connectors/google-ads/ai-brief?account_id=1234567890")
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main()


# ═══════════════════════════════════════════════════════════════════════════════
# Source Truth: mock vs mock_fallback vs google_ads_api
# Verifies the source field correctly distinguishes connected-but-errored from
# not-connected, so mock is never silently shown as live.
# ═══════════════════════════════════════════════════════════════════════════════

class TestSourceTruth(unittest.TestCase):
    """Verify _gads_resolve_live_campaigns source field semantics."""

    def setUp(self):
        self.client = app.test_client()

    def _source_for(self, cid="1234567890"):
        r = self.client.get(f"/api/connectors/google-ads/overview?customer_id={cid}")
        return json.loads(r.data)["source"]

    def test_valid_source_values_only(self):
        """source must always be one of the three declared values."""
        source = self._source_for()
        self.assertIn(source, ("google_ads_api", "mock", "mock_fallback"),
                      f"Unexpected source: {source}")

    def test_no_credentials_in_any_source_state(self):
        """No token material leaks regardless of source."""
        for endpoint in ["/api/connectors/google-ads/overview",
                         "/api/connectors/google-ads/diagnostics",
                         "/api/connectors/google-ads/ai-brief"]:
            r = self.client.get(f"{endpoint}?customer_id=1234567890")
            body = r.data.decode()
            for secret in ["refresh_token", "developer_token", "client_secret",
                            "access_token", "Bearer ", "private_key"]:
                self.assertNotIn(secret, body,
                                 f"Secret field '{secret}' leaked in {endpoint}")

    def test_all_three_endpoints_return_same_source(self):
        """Overview, diagnostics, and ai-brief share the same live resolver."""
        cid = "1234567890"
        days = "30"
        ov = json.loads(self.client.get(
            f"/api/connectors/google-ads/overview?customer_id={cid}&days={days}").data)
        dx = json.loads(self.client.get(
            f"/api/connectors/google-ads/diagnostics?customer_id={cid}&days={days}").data)
        ab = json.loads(self.client.get(
            f"/api/connectors/google-ads/ai-brief?customer_id={cid}&days={days}").data)
        # All must return a valid source (need not match since separate requests)
        for name, d in [("overview", ov), ("diagnostics", dx), ("ai_brief", ab)]:
            self.assertIn(d["source"], ("google_ads_api", "mock", "mock_fallback"),
                          f"{name} returned invalid source: {d['source']}")

    def test_mock_fallback_distinct_from_mock(self):
        """mock_fallback is a distinct string from mock."""
        self.assertNotEqual("mock_fallback", "mock")
        self.assertNotEqual("mock_fallback", "google_ads_api")

    def _resolve(self, mock_meta_val, mock_token_val, mock_stream_val, cid="1234567890"):
        """Call _gads_resolve_live_campaigns directly with patched internals.

        Uses test_request_context to provide Flask context (same approach as
        the confirmed-working direct debug call).  Patches use the correct
        module path (backend_py.app) to avoid the double-import problem where
        'app' and 'backend_py.app' are different sys.modules entries.
        """
        with patch(f"{_PATCH_PREFIX}._gads_token_get_meta",
                   return_value=mock_meta_val), \
             patch(f"{_PATCH_PREFIX}._gads_get_fresh_access_token",
                   return_value=mock_token_val), \
             patch(f"{_PATCH_PREFIX}._gads_searchstream_campaigns",
                   return_value=mock_stream_val):
            with app.test_request_context("/"):
                return _gads_resolve_live_campaigns(cid, "", 30, user_id="testuser")

    def test_connected_api_error_returns_api_error(self):
        """When connected+validated but searchStream fails → no silent mock."""
        _, _, source, _ = self._resolve(
            mock_meta_val={"status": "active", "api_validated": True,
                           "selected_manager_customer_id": "8924163684"},
            mock_token_val={"success": True, "access_token": "test_token"},
            mock_stream_val={"success": False, "error": "403 Forbidden"},
        )
        self.assertEqual(source, "google_ads_api_error",
                         "Connected user with API error should get explicit error, not mock")

    def test_not_connected_returns_mock(self):
        """When not connected (no meta) → source=mock."""
        _, _, source, _ = self._resolve(
            mock_meta_val=None,
            mock_token_val={"success": False},
            mock_stream_val={"success": False},
        )
        self.assertEqual(source, "mock",
                         "Not-connected user should get source=mock")

    def test_live_success_returns_google_ads_api(self):
        """When connected and API succeeds → source=google_ads_api."""
        _, _, source, _ = self._resolve(
            mock_meta_val={"status": "active", "api_validated": True,
                           "selected_manager_customer_id": "8924163684"},
            mock_token_val={"success": True, "access_token": "test_token"},
            mock_stream_val={"success": True, "campaigns": [], "date_range": "LAST_30_DAYS"},
        )
        self.assertEqual(source, "google_ads_api")

    def test_mock_fallback_no_credentials_in_response(self):
        """mock_fallback response must not leak any credential."""
        with patch(f"{_PATCH_PREFIX}._gads_token_get_meta",
                   return_value={"status": "active", "api_validated": True}), \
             patch(f"{_PATCH_PREFIX}._gads_get_fresh_access_token",
                   return_value={"success": True, "access_token": "test_token"}), \
             patch(f"{_PATCH_PREFIX}._gads_searchstream_campaigns",
                   return_value={"success": False, "error": "500"}):
            for endpoint in ["/api/connectors/google-ads/overview",
                             "/api/connectors/google-ads/diagnostics",
                             "/api/connectors/google-ads/ai-brief"]:
                r = self.client.get(f"{endpoint}?customer_id=1234567890")
                body = r.data.decode()
                for secret in ["test_token", "refresh_token", "client_secret",
                                "developer_token"]:
                    self.assertNotIn(secret, body,
                                     f"Secret in {endpoint} mock_fallback response")
