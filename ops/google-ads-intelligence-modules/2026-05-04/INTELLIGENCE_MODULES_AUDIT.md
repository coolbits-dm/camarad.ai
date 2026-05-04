# Google Ads Intelligence Modules — Phase 2E Audit

Date: 2026-05-04  
Branch: feature/google-ads-intelligence-modules-2026-05-04  
Base: feature/google-ads-report-query-2026-05-04 @ 69afca9  

---

## 1. Current Report Presets (Phase 2D)

Four basic quick-report presets exist via `POST /api/connectors/google-ads/report/query`:

| Preset | Metrics | Sort | Filter |
|--------|---------|------|--------|
| Account Health | cost, impressions, clicks, ctr, conversions, cpa, roas | -cost | ENABLED |
| Waste Finder | cost, clicks, conversions, cpa | -cost | none |
| ROAS Leaders | cost, conversions_value, roas, conversions | -roas | ENABLED |
| Conversion Efficiency | clicks, conversions, conversion_rate, cost, cpa, value_per_conversion | -conversions | ENABLED |

These return raw table rows only. No signals, no summary, no recommendations.

---

## 2. Current Data Fields Available (from campaign rows)

Guaranteed fields on every campaign row:
- `id`, `name`, `status` (ENABLED/PAUSED/REMOVED)
- `type` / `advertising_channel_type`
- `budget_daily`, `budget_total`
- `spent` (cost), `impressions`, `clicks`, `conversions`, `conversion_value`
- `ctr`, `avg_cpc`, `roas`, `cpa`

Derived fields (report query rows):
- `cost`, `impressions`, `clicks`, `ctr`, `avg_cpc`
- `conversions`, `conversions_value`, `all_conversions`
- `roas`, `cpa`, `conversion_rate`, `value_per_conversion`
- `cost_per_all_conversions`
- `currency_code` (from `customer.currency_code` in GAQL)
- `campaign`, `campaign_id`, `campaign_status`, `advertising_channel_type`
- `bidding_strategy_type`

---

## 3. Current Source Truth Behavior

`_gads_resolve_live_campaigns()` returns a 4-tuple: `(campaigns, date_range, source, api_currency_code)`

Source values:
- `"google_ads_api"` — live API call succeeded
- `"mock_fallback"` — connected but API call failed
- `"mock"` — no OAuth connection, demo data

Every endpoint exposes `source` in its response. Mock never claims to be live.

`_gads_resolve_currency_context()` returns:
```json
{
  "currency_code": "RON",
  "currency_source": "google_ads_api_query|cached_hierarchy|row_data|unknown",
  "conversion_applied": false,
  "mixed_currency": false,
  "display_currency": null,
  "native_currency": "RON",
  "warning": null
}
```

Priority: live API code > row set > hierarchy DB > null (never fallback to USD).

---

## 4. Current Currency Behavior

- `_gads_get_account_currency(customer_id, manager_customer_id, user_id)` — DB lookup from `google_ads_customer_hierarchy`
- `_gads_resolve_currency_context(...)` — resolves currency with source priority
- Unknown currency → `null`, never `"USD"`
- `conversion_applied` always `false` — no FX
- `_gadsCurrencySymbol(code)` in JS — maps 20+ ISO codes to symbols

---

## 5. Current Diagnostics Rules (_gads_compute_diagnostics)

Six rules, evaluated per campaign:
1. `high_spend_no_conversions` — enabled, cost>50, conversions==0 → **critical**
2. `low_roas_enabled` — enabled, cost>50, 0<roas<2.0 → **warning**
3. `zero_impressions_enabled` — enabled, impressions==0 → **warning**
4. `paused_with_conversions` — paused, conversions>0 → **info**
5. `high_cpc_low_ctr` — enabled, avg_cpc>5, ctr<1, impr>100 → **warning**
6. `budget_overspend_or_missing_budget` — enabled, budget_daily==0 → **info**

Sorted: critical > warning > info.

Note: These use hardcoded `$` in recommendation text — not currency-aware.

---

## 6. Proposed Module Registry

Each module entry shape:
```json
{
  "id": "...",
  "label": "...",
  "category": "...",
  "status": "live_v0|live_basic|partial|planned|planned_limited",
  "description": "...",
  "endpoint": "...",
  "requires": ["campaign_rows"],
  "source": "derived|google_ads_api|planned",
  "currency_sensitive": true,
  "campaign_types": ["ALL"],
  "notes": []
}
```

### Module Registry (Phase 2E initial)

1. **account_health** — `live_v0` — health — signals from campaign performance
2. **waste_finder** — `live_basic` — waste — zero-conv spend, low ROAS, high CPA
3. **roas_leaders** — `live_basic` — growth — best ROAS/conversion value
4. **conversion_efficiency** — `live_basic` — growth — CPA, conversion rate, value per conv
5. **search_terms** — `planned` — search_terms — search term view + PMax campaign_search_term_view
6. **performance_max** — `planned` — pmax — asset groups, assets, search terms, listing groups
7. **budget_pacing** — `planned` — budget — budget usage, limited by budget signals
8. **assets_creatives** — `planned` — assets — asset coverage, ad strength, creative fatigue
9. **audiences_targeting** — `planned_limited` — audiences — AudienceInsightsService may require allowlist
10. **geo_device** — `planned` — geo_device — geo and device performance
11. **landing_pages** — `planned` — landing_pages — landing page performance
12. **conversion_tracking** — `planned` — conversion_tracking — conversion sanity

---

## 7. Proposed Module Response Contract

```json
{
  "success": true,
  "module_id": "account_health",
  "module_label": "Account Health",
  "source": "google_ads_api|mock_fallback|mock",
  "live_data": true,
  "customer_id": "...",
  "manager_customer_id": "...",
  "date_range": "LAST_30_DAYS",
  "currency": {
    "currency_code": "RON",
    "currency_source": "cached_hierarchy",
    "conversion_applied": false
  },
  "summary": {
    "signal_counts": {"critical": 1, "warning": 3, "info": 2},
    "score_status": "planned",
    "top_signal": "zero_conversion_spend"
  },
  "signals": [
    {
      "id": "zero_conversion_spend",
      "category": "waste",
      "severity": "critical",
      "label": "Spend with zero conversions",
      "evidence": {
        "campaign_name": "Brand Search",
        "spend": {"amount": 450.00, "currency_code": "RON", "formatted": "lei 450.00"},
        "conversions": 0
      },
      "recommendation": "Review targeting and conversion tracking. Consider pausing until resolved."
    }
  ],
  "recommendations": ["..."],
  "rows": [],
  "warnings": []
}
```

---

## 8. Proposed Account Health v0 Signals

Category: waste
- `zero_conversion_spend` — enabled, cost > 50, conversions == 0 — **critical/warning**
- `low_roas_spend` — enabled, cost > threshold, roas < 2.0 — **warning**
- `high_cpa_campaign` — campaign CPA > 2x account average — **warning**
- `enabled_loser` — enabled, heavy spend, zero conversions or roas < 0.5 — **critical**

Category: efficiency
- `low_ctr_campaign` — enabled, ctr < 0.5%, impressions > 500 — **warning**
- `high_cpc_outlier` — avg_cpc > 2x account median — **warning**

Category: growth
- `paused_winner` — paused, conversions > 5 or roas > 3.0 — **info**
- `roas_scale_opportunity` — enabled, roas > 4.0, cost < 10% total spend — **info**

Category: tracking
- `tracking_sanity_warning` — spend > 100 across all enabled, but total conversions == 0 — **critical**

Category: structure
- `no_active_campaigns` — zero enabled campaigns — **warning**
- `spend_concentration_risk` — top campaign > 80% of total spend — **warning**
- `conversion_concentration_risk` — top campaign > 90% of total conversions — **warning**

---

## 9. Test Plan

File: `backend_py/test_google_ads_intelligence_modules.py`

Tests required (24):
1. `/intelligence/modules` returns registry
2. Registry includes required module IDs
3. Planned modules marked planned, not falsely live
4. `account_health` requires customer_id
5. `account_health` returns standard module response contract
6. `account_health` returns currency metadata
7. `account_health` returns signal summary
8. `zero_conversion_spend` signal generated
9. `low_roas_spend` signal generated
10. `high_cpa_campaign` signal generated
11. `paused_winner` signal generated
12. `enabled_loser` signal generated
13. `spend_concentration_risk` signal generated
14. `tracking_sanity_warning` signal generated
15. Signals sorted critical > warning > info
16. Monetary evidence includes currency_code and formatted value
17. source=mock_fallback → live_data=false
18. source=google_ads_api → live_data=true
19. `waste_finder` endpoint returns waste-related signals
20. Reports UI contains module labels
21. Planned module buttons are disabled/marked planned
22. No response exposes tokens/secrets
23. No mutate/write API called
24. Existing report/query endpoints still pass

---

## 10. Risks and Blockers

- **No search_term_view for PMax**: `search_term_view` is documented to exclude Performance Max results. Use `campaign_search_term_view` for PMax-adjacent search terms where supported. PMax is a planned module only.
- **AudienceInsightsService allowlist**: May be restricted. Audiences module is `planned_limited`.
- **Budget data gaps**: `budget_daily` may be 0/null in mock/fallback. Pacing signals should handle gracefully.
- **Account health score**: Score v1 is planned. Phase 2E returns `score_status: "planned"` only.
- **Mixed currency MCC rollup**: Not in Phase 2E scope. Mixed currency warning surfaced in signals but no aggregation.
- **Currency for signals**: Evidence values must use `amount + currency_code + formatted`. All hardcoded `$` in existing diagnostics text must be fixed before signals are exposed as intelligence output.
