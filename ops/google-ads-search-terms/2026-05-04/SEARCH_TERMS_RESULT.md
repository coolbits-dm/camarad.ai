# Search Terms Intelligence — Result
**Date:** 2026-05-05  
**Phase:** 2E.2  
**Commit:** TBD (post-commit)  
**Branch:** feature/google-ads-search-terms-2026-05-04  

---

## Endpoint Added

`GET /api/connectors/google-ads/intelligence/search-terms`

Parameters:
- `customer_id` (required)
- `mcc_id` (optional)
- `days` (default 30, range 7/14/30/90)
- `limit` (default 100, max 500)

---

## GAQL Fields Used

Resource: `search_term_view` (standard search campaigns only, not PMax)

```sql
SELECT
  search_term_view.search_term,
  search_term_view.status,
  campaign.id, campaign.name, campaign.status,
  ad_group.id, ad_group.name,
  metrics.impressions, metrics.clicks, metrics.cost_micros,
  metrics.conversions, metrics.conversions_value,
  metrics.ctr, metrics.average_cpc,
  customer.currency_code
FROM search_term_view
WHERE segments.date DURING {date_range}
ORDER BY metrics.cost_micros DESC
LIMIT {safe_limit}
```

---

## Row Classification

Each row classified as:
- `waste` — cost > 5 (native currency), conversions == 0
- `winner` — conversions >= 1, roas >= 3.0 (or good CPA / multiple conversions)
- `opportunity` — high CTR (>= 2%) with no conversions yet, OR high impressions/low CTR (<0.5%)
- `neutral` — none of the above

---

## Signals Implemented

| signal_id | severity | condition |
|---|---|---|
| `waste_search_terms` | warning | cost > 5, conversions == 0 |
| `high_cost_low_roas_terms` | warning | cost > 10, roas in (0, 2.0) |
| `winner_search_terms` | info | conversions >= 1, roas >= 3.0 |
| `high_ctr_no_conversion_terms` | warning | clicks >= 10, ctr >= 2.0%, conv == 0 |
| `low_ctr_high_impression_terms` | warning | impressions >= 200, ctr < 0.5% |
| `pmax_gap_notice` | info | account has PMax campaigns |

---

## PMax Limitation

`search_term_view` does **not** include Performance Max search term data.

- If account has PMax campaigns: `pmax_gap_notice` signal added + explicit warning in response
- Full PMax search term visibility requires `campaign_search_term_view` (see `PMAX_SEARCH_TERMS_NEXT.md`)
- `summary.pmax_gap = true/false` field signals completeness to UI

---

## Source Truth Behavior

| Condition | source | live_data |
|---|---|---|
| OAuth active + API success | `google_ads_api` | `true` |
| OAuth active + API error | `mock_fallback` | `false` + warning |
| No OAuth / no session | `mock` | `false` + warning |

Mock fallback warning: `"API call failed. Showing demo data."`

---

## Currency Behavior

- Per-row `currency_code` from `customer.currency_code` in API response
- Fallback: `_gads_resolve_currency_context()` → DB lookup → `currency_source=unknown`
- All signal evidence uses `_gads_format_currency_evidence()` — no USD default
- No currency conversion performed

---

## Module Registry Update

`search_terms` entry changed:
- `status`: `planned` → `partial_live`
- `endpoint`: `None` → `/api/connectors/google-ads/intelligence/search-terms`
- `notes`: PMax limitation explicit

---

## UI Changes

- Search Terms button: `disabled` removed, `onclick="gadsOpenModule('search_terms')"` added
- Badge: `Planned` → `Partial` (warning style)
- `gadsRenderSearchTerms(data)` renderer added
- Summary stat cards: Terms / Waste / Winners / Opportunity / Total Cost
- Waste terms table (top 10 by cost)
- Winner terms table (top 10 by ROAS)
- Negative keyword placeholder: "Negative keyword drafts coming later"

---

## Tests Passed

- `test_google_ads_search_terms.py`: 39/39 PASS (new)
- `test_google_ads_intelligence_modules.py`: 24/24 PASS (updated test_21)
- All Google Ads suites: 174/174 PASS (no regressions)
- Flows/Chat/MWR suites: 51/51 PASS
- Vacante: 9/9 PASS
- Conversation Brief: PASS
- Orchestrator: 18F+8E (pre-existing, identical to Phase 2E baseline)

---

## Negative Keyword Actions

**Not implemented.** All waste term signals are recommendations only.
- No `/apply`, `/add-negative`, or mutation endpoints exist
- UI shows: "Negative keyword drafts coming later"
- Planned: approval-gated draft flow in future Flows v3

---

## Known Limitations

1. `search_term_view` excludes PMax — see pmax_gap_notice
2. Classification thresholds (cost > 5, ctr >= 2%, etc.) are fixed — not account-calibrated
3. Account Health Score not yet computed from search terms signals
4. Match type (`segments.keyword.info.match_type`) not included in this v0 — omitted for simplicity
5. `EXCLUDED` targeting status terms not separately flagged — shown as neutral/waste based on metrics
