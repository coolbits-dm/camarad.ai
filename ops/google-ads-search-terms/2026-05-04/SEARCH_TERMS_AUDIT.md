# Search Terms Intelligence — Audit
**Date:** 2026-05-05  
**Phase:** 2E.2 — Search Terms Intelligence  
**Branch:** feature/google-ads-search-terms-2026-05-04  
**Base commit:** 8b82475  

---

## 1. Current Module Registry Status

`_GADS_INTELLIGENCE_MODULE_REGISTRY` at app.py ~line 21435:

| id | label | status | endpoint |
|---|---|---|---|
| account_health | Account Health | live_v0 | /intelligence/account-health |
| waste_finder | Waste Finder | live_basic | /intelligence/waste-finder |
| roas_leaders | ROAS Leaders | live_basic | /report/query |
| conversion_efficiency | Conversion Efficiency | live_basic | /report/query |
| **search_terms** | **Search Terms** | **planned → partial_live** | **→ /intelligence/search-terms** |
| performance_max | PMax | planned | None |
| budget_pacing | Budget & Pacing | planned | None |
| assets_creatives | Assets & Creatives | planned | None |
| audiences_targeting | Audiences | planned_limited | None |
| geo_device | Geo & Device | planned | None |
| landing_pages | Landing Pages | planned | None |
| conversion_tracking | Conversion Tracking | planned | None |

**Action:** Change `search_terms` entry from `status="planned"` to `status="partial_live"`,
add `endpoint="/api/connectors/google-ads/intelligence/search-terms"`, add note re: PMax gap.

---

## 2. Available Helper Functions

### Live campaign resolver
- `_gads_resolve_live_campaigns(customer_id, mcc_id, days, user_id)` → (campaigns, date_range, source, currency)
- Pattern: check meta.status=active + api_validated → get fresh token → call query helper → fallback on error

### Search stream helper
- `_gads_searchstream_campaigns(account_id, access_token, developer_token, login_customer_id, days)` → raw campaigns
- Template for new `_gads_fetch_search_terms` helper

### Currency helpers
- `_gads_resolve_currency_context(customer_id, manager_customer_id, api_currency_code, rows, user_id)` → currency dict
- `_gads_format_currency_evidence(amount, currency_code)` → {amount, currency_code, formatted}

### Source truth
- `_gads_resolve_live_campaigns` returns source: `google_ads_api` | `mock_fallback` | `mock`
- `_gads_build_module_response` maps source to `live_data: bool`

### Signal/response builder
- `_gads_compute_account_health_signals(campaigns, totals, currency_ctx)` — campaign-level signals
- `_gads_build_module_response(...)` — standard envelope

---

## 3. Proposed GAQL Query

```sql
SELECT
  search_term_view.search_term,
  search_term_view.status,
  campaign.id,
  campaign.name,
  campaign.status,
  ad_group.id,
  ad_group.name,
  metrics.impressions,
  metrics.clicks,
  metrics.cost_micros,
  metrics.conversions,
  metrics.conversions_value,
  metrics.ctr,
  metrics.average_cpc,
  customer.currency_code
FROM search_term_view
WHERE segments.date DURING LAST_30_DAYS
  AND campaign.status IN ('ENABLED', 'PAUSED')
ORDER BY metrics.cost_micros DESC
LIMIT 200
```

**Note:** `search_term_view` does NOT include Performance Max. PMax requires
`campaign_search_term_view` (see PMAX_SEARCH_TERMS_NEXT.md).

**Note:** `campaign.status IN (...)` filter may require `UNKNOWN` inclusion on some accounts.
The filter is best-effort and fallback gracefully handled.

---

## 4. Source Truth Behavior

| Condition | source | live_data |
|---|---|---|
| OAuth active + API success | `google_ads_api` | `true` |
| OAuth active + API error | `mock_fallback` | `false` |
| No OAuth / no customer_id | `mock` | `false` |

- `mock_fallback` adds warning: "API call failed. Showing fallback demo data."
- `mock` adds warning: "No live Google Ads connection. Showing demo data."
- `live_data=false` rows always contain `currency_code` from mock/fallback, not live account

---

## 5. Currency Behavior

- All cost/cpa/roas values use account-native currency from API response (`customer.currency_code`)
- If API unavailable: currency resolved from `google_ads_customer_hierarchy` DB (user-scoped)
- If DB also unavailable: `currency_code=null`, `currency_source="unknown"`
- No currency conversion performed
- Per-row `currency_code` field shows account currency or null
- Signal evidence uses `_gads_format_currency_evidence()` — never defaults to USD

---

## 6. Signal Definitions

| signal_id | category | severity | condition |
|---|---|---|---|
| waste_search_terms | waste | warning | cost > 5, conversions == 0 |
| high_cost_low_roas_terms | waste | warning | cost > 10, roas > 0 but < 2.0 |
| winner_search_terms | growth | info | conversions >= 1, roas >= 3.0 or good CPA |
| high_ctr_no_conversion_terms | efficiency | warning | clicks >= 10, ctr >= 2.0, conversions == 0 |
| low_ctr_high_impression_terms | efficiency | warning | impressions >= 200, ctr < 0.5% |
| pmax_gap_notice | data_quality | info | account has PMax campaigns |

**Thresholds are in account-native currency units (not USD-adjusted).**

---

## 7. Row Classification

Each row classified as one of:
- `waste` — cost > 5 AND conversions == 0
- `winner` — conversions >= 1 AND (roas >= 3.0 OR cost-efficient CPA)
- `opportunity` — high CTR (>= 2.0%) OR high impressions/low CTR, no conversions yet, low cost
- `neutral` — doesn't meet any of the above

---

## 8. Tests to Add

File: `backend_py/test_google_ads_search_terms.py`

1. `test_registry_marks_search_terms_partial_live` — registry status is `partial_live`
2. `test_endpoint_requires_customer_id` — missing customer_id → 400
3. `test_endpoint_returns_standard_module_response` — response has all required fields
4. `test_row_normalization_cost_cpa_roas` — cost/cpa/roas derived correctly
5. `test_waste_signal_generated` — waste_search_terms signal for cost>5, conv=0
6. `test_winner_signal_generated` — winner_search_terms for conv>=1, roas>=3
7. `test_high_ctr_no_conversion_signal` — clicks>=10, ctr>=2%, conv=0
8. `test_low_ctr_high_impression_signal` — imp>=200, ctr<0.5%
9. `test_monetary_values_include_currency_code` — cost evidence has currency_code
10. `test_live_source_gives_live_data_true` — source=google_ads_api → live_data=True
11. `test_mock_fallback_gives_live_data_false` — source=mock_fallback → live_data=False + warning
12. `test_pmax_gap_warning_present` — pmax_gap_notice signal or warning exists
13. `test_no_secret_leak` — access_token/refresh_token/developer_token not in response
14. `test_no_mutate_api_called` — no calls to googleAds:mutate
15. `test_ui_search_terms_live_partial` — HTML has search-terms as live/partial, not disabled
16. `test_negative_keyword_actions_not_implemented` — no mutation endpoint, placeholder only

---

## 9. Risks / Blockers

- **Filter compatibility**: `campaign.status IN ('ENABLED','PAUSED')` is valid GAQL but some accounts may require `UNKNOWN` inclusion. Handle API error gracefully.
- **Zero results**: Some accounts may have no `search_term_view` data (Shopping-only, new accounts). Handle empty rows gracefully.
- **PMax gap**: Users with PMax campaigns will see incomplete picture. `pmax_gap_notice` signal + warning mitigates this.
- **CTR percentage**: `metrics.ctr` from API is 0–1 float. Multiply by 100 for display.
- **average_cpc micros**: `metrics.average_cpc` is in micros. Divide by 1,000,000.
- **Targeting status**: `search_term_view.status` = ADDED/EXCLUDED/NONE. EXCLUDED terms should be skipped or flagged separately.
