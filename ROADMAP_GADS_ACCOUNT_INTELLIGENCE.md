# Google Ads Account Intelligence — Codex Roadmap

**Branch:** `feature/google-ads-mcc-ui-mapping-fix-2026-05-04`  
**Last commit:** Phase 2C (this file)  
**Date:** 2026-05-04

---

## What was done (Phases 2A–2C)

| Phase | Description | Commit |
|-------|-------------|--------|
| 2A.1 | MCC hierarchy loading (DB + API) | `42004e5` |
| 2A.2 | UI mapping fix — `selected_manager_customer_id` in `_gads_token_get_meta()` | `8e1ed16` |
| 2B   | Live campaign data via `googleAds:searchStream` + `login-customer-id` | `78ae3a1` |
| 2C   | Account Intelligence — Overview / Diagnostics / AI Brief endpoints + UI | *this commit* |

---

## Architecture (current state)

### Backend (`backend_py/app.py`)

```
Helpers:
  _gads_searchstream_campaigns()       — POST GAQL to searchStream, returns campaign list
  _gads_resolve_live_campaigns()       — try live API → fall back to mock
  _gads_compute_overview_totals()      — KPI aggregation from campaign list
  _gads_compute_diagnostics()          — 6 rule-based findings (critical/warning/info)
  _gads_compute_ai_brief()             — structured Orchestrator-ready intelligence brief

Routes:
  GET /api/connectors/google-ads/campaigns    — Phase 2B (live + mock fallback)
  GET /api/connectors/google-ads/overview     — Phase 2C: KPI totals
  GET /api/connectors/google-ads/diagnostics  — Phase 2C: rule-based findings
  GET /api/connectors/google-ads/ai-brief     — Phase 2C: Orchestrator brief
```

All Phase 2C routes share `_gads_resolve_live_campaigns()` which:
1. Checks `meta.api_validated` and `meta.status == active`
2. Calls `_gads_get_fresh_access_token()`
3. POSTs GAQL to `customers/{cid}/googleAds:searchStream` with `login-customer-id: {mcc_manager}`
4. Falls back to mock on any error (never surfaces credentials)

### Frontend (`backend_py/templates/connectors.html`)

5 visible tabs: **Overview | Campaigns | Diagnostics | AI Brief | Settings**  
Hidden (dev-only): Test API, Budget Pacing, Reports, Asset Generator

Lazy loading: Campaigns / Diagnostics / AI Brief tabs load on first click.  
Overview loads immediately on account select.

---

## Known limitations (as of Phase 2C)

| Item | Details |
|------|---------|
| `budget_daily` / `budget_total` always `0.0` | GAQL does not query `campaign_budget` resource. Fix in Phase 2D. |
| No server-side caching | Each tab trigger = 1 searchStream API call. Fix with Redis/TTL cache in Phase 2E. |
| `_gads_compute_ai_brief()` is deterministic | No LLM. AI Brief = rule-based logic. LLM integration deferred to Phase 3. |
| Diagnostics only covers 6 rules | See Phase 2D for more rules. |
| No write operations | All read-only. Write APIs not implemented by design. |

---

## Phase 2D — Budget & Extended Diagnostics (next)

**Goal:** Add real budget data and more diagnostic rules.

### 2D.1 — Budget data in campaigns GAQL

Add a second searchStream call in `_gads_searchstream_campaigns()` (or a new helper) to fetch:
```gaql
SELECT campaign.id, campaign_budget.amount_micros, campaign_budget.total_amount_micros
FROM campaign
WHERE campaign.status IN ('ENABLED','PAUSED')
```
Merge into campaign dicts: `budget_daily = amount_micros / 1_000_000 / 30`, `budget_total = total_amount_micros / 1_000_000`.

Then the Budget Pacing hidden tab will show real data, and can be unhidden.

### 2D.2 — Additional diagnostic rules

Add to `_gads_compute_diagnostics()`:

| Rule | Type | Severity | Condition |
|------|------|----------|-----------|
| Low Quality Score | `low_quality_score` | warning | Avg QS < 5 (requires keyword-level data) |
| High impression share lost | `high_impression_share_lost` | warning | impr_share_lost_budget > 0.3 (needs IS field in GAQL) |
| Declining CTR trend | `ctr_decline_trend` | info | CTR < 50% of 90-day avg (needs dual-period queries) |
| All keywords paused | `all_keywords_paused` | warning | 0 active keywords for enabled campaign |
| Missing sitelinks | `missing_ad_extensions` | info | campaign has no sitelink extensions |

### 2D.3 — Diagnostics date comparison

Add `?compare_days=90` param to diagnostics endpoint. Run GAQL for both windows and surface trend data.

---

## Phase 2E — Performance Optimization

### 2E.1 — Server-side campaign data cache

Add an in-memory TTL cache (5-minute default) per `(user_id, account_id, days)` tuple:

```python
import threading, time

_GADS_CAMPAIGN_CACHE = {}  # key → (timestamp, campaigns, date_range)
_GADS_CACHE_LOCK = threading.Lock()
_GADS_CACHE_TTL = 300  # seconds

def _gads_campaign_cache_get(user_id, account_id, days):
    key = f"{user_id}:{account_id}:{days}"
    with _GADS_CACHE_LOCK:
        entry = _GADS_CAMPAIGN_CACHE.get(key)
        if entry and (time.time() - entry[0]) < _GADS_CACHE_TTL:
            return entry[1], entry[2]
    return None, None

def _gads_campaign_cache_set(user_id, account_id, days, campaigns, date_range):
    key = f"{user_id}:{account_id}:{days}"
    with _GADS_CACHE_LOCK:
        _GADS_CAMPAIGN_CACHE[key] = (time.time(), campaigns, date_range)
```

Then `_gads_resolve_live_campaigns()` checks cache first, writes to cache on success.  
This reduces 4 API calls (overview + campaigns + diagnostics + ai-brief) to 1.

### 2E.2 — Cache invalidation

Add `DELETE /api/connectors/google-ads/cache` endpoint that clears cache for current user.  
Auto-invalidate on OAuth disconnect or account switch.

---

## Phase 3 — LLM-powered AI Brief

**Goal:** Replace deterministic `_gads_compute_ai_brief()` with LLM-generated narrative.

### 3.1 — LLM integration point

`_gads_compute_ai_brief()` already returns clean structured data. Pass it to the Camarad AI orchestrator:

```python
def _gads_generate_ai_brief_narrative(brief_data, llm_client):
    prompt = f"""You are a Google Ads expert analyst. Given this campaign performance data:
{json.dumps(brief_data, indent=2)}
Write a concise 3-paragraph executive summary:
1. Overall performance assessment
2. Top 2-3 specific findings with evidence
3. Recommended next actions (be specific, not generic)
"""
    return llm_client.complete(prompt, max_tokens=500)
```

Add `?narrative=1` param to `/api/connectors/google-ads/ai-brief` to trigger LLM path.

### 3.2 — Orchestrator integration

The "Send to Orchestrator" button in AI Brief tab (currently disabled placeholder) should:
1. POST the AI brief JSON to `/api/orchestrator/context/google-ads`
2. The Orchestrator stores it as context for the current session
3. Follow-up questions like "Why is my ROAS low?" use this context

---

## Phase 4 — Multi-account Intelligence

**Goal:** Roll up metrics across all 18 MCC children into a manager-level dashboard.

### 4.1 — Batch fetch all child accounts

```python
GET /api/connectors/google-ads/mcc/overview?days=30
```

Iterates `google_ads_customer_hierarchy` WHERE `user_id = X AND account_type = 'CLIENT'`,
fires searchStream for each, aggregates into:
```json
{
  "manager_id": "8924163684",
  "date_range": "LAST_30_DAYS",
  "total_accounts": 18,
  "accounts": [
    { "customer_id": "...", "name": "...", "spend": ..., "roas": ..., "conversions": ..., "status": "ok|warning|critical" }
  ],
  "totals": { "spend": ..., "roas": ..., "conversions": ... }
}
```

### 4.2 — MCC-level diagnostics

Surface top 5 most critical campaigns across all accounts.  
"Worst performers" tab at MCC level for quick triage.

---

## Phase 5 — Report Scheduler (optional)

Weekly automated AI brief emails:
- Cron job runs `_gads_compute_ai_brief()` for each user's active accounts
- Generates LLM narrative (Phase 3)
- Sends via `/api/notifications/email` (if implemented)

---

## Test coverage

| Test file | Tests | What |
|-----------|-------|------|
| `test_google_ads_oauth_phase1.py` | N | OAuth flow, token storage |
| `test_google_ads_api_validation.py` | N | Developer token validation |
| `test_google_ads_mcc_hierarchy.py` | N | Hierarchy load + DB |
| `test_google_ads_mcc_ui_mapping.py` | 22 | `selected_manager_customer_id` fix |
| `test_google_ads_campaigns_phase2b.py` | 26 | searchStream + campaign mapping |
| `test_google_ads_account_intelligence.py` | 54 | Overview/Diagnostics/AI Brief |
| **Total** | **177** | All pass ✅ |

---

## Deployment notes

- No DB migrations required for Phase 2C (pure compute from existing campaign data)
- PM2 restart: `pm2 restart camarad --update-env`
- Smoke test: `curl https://camarad.ai/api/connectors/google-ads/overview?customer_id=REAL_ID`
- Template changes require `pm2 restart` (Flask serves templates from disk in debug=False mode)

---

*Roadmap authored by GitHub Copilot for Codex continuation. Last updated: 2026-05-04.*
