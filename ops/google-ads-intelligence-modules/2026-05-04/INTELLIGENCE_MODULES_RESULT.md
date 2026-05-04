# Google Ads Intelligence Modules Framework — Phase 2E Result
Date: 2026-05-04/05
Branch: feature/google-ads-intelligence-modules-2026-05-04
Base: feature/google-ads-report-query-2026-05-04 @ 69afca9

---

## Endpoints Added

| Endpoint | Method | Description |
|---|---|---|
| `/api/connectors/google-ads/intelligence/modules` | GET | Module registry catalog |
| `/api/connectors/google-ads/intelligence/account-health` | GET | Account Health v0 signals |
| `/api/connectors/google-ads/intelligence/waste-finder` | GET | Waste Finder module signals |

---

## Module Registry

### Live Modules

| ID | Status | Category | Description |
|---|---|---|---|
| `account_health` | `live_v0` | health | Account-level health signals from campaign performance |
| `waste_finder` | `live_basic` | waste | Spend with low/no conversions, low ROAS, high CPA |
| `roas_leaders` | `live_basic` | growth | Best ROAS/conversion value candidates (via report/query) |
| `conversion_efficiency` | `live_basic` | growth | CPA, conversion rate, value per conversion (via report/query) |

### Planned Modules (visible, disabled in UI)

| ID | Status | Category | Notes |
|---|---|---|---|
| `search_terms` | `planned` | search_terms | Standard Search via `search_term_view`; PMax via `campaign_search_term_view`. Separated paths required. |
| `performance_max` | `planned` | pmax | Asset group, asset group asset, listing/product group reporting. |
| `budget_pacing` | `planned` | budget | Budget usage, limited-by-budget detection, pacing. |
| `assets_creatives` | `planned` | assets | Asset coverage, ad strength, creative fatigue. |
| `audiences_targeting` | `planned_limited` | audiences | Requires capability check; `AudienceInsightsService` may be allowlisted. |
| `geo_device` | `planned` | geo_device | Geo and device performance breakdown. |
| `landing_pages` | `planned` | landing_pages | Landing page performance and expanded pages. |
| `conversion_tracking` | `planned` | conversion_tracking | Conversion action sanity, lag, value tracking. |

---

## Account Health v0 Signals

12 deterministic signal types, no ML/LLM required:

| Signal ID | Category | Severity | Trigger |
|---|---|---|---|
| `zero_conversion_spend` | waste | critical (≥200) / warning (≥50) | Enabled campaign: cost > threshold, conversions == 0 |
| `low_roas_spend` | efficiency | warning | Enabled: cost ≥ 50, roas < 2.0, not already zero-conv critical |
| `high_cpa_campaign` | efficiency | warning | CPA > 2× account average |
| `paused_winner` | growth | info | Paused campaign with conversions ≥ 5 or roas ≥ 3.0 |
| `enabled_loser` | waste | warning | Enabled: cost ≥ 100, roas ≤ 0.2 |
| `low_ctr_campaign` | efficiency | info | CTR < 0.5%, impressions ≥ 5000 |
| `high_cpc_outlier` | efficiency | info | avg_cpc > 2× account average |
| `conversion_concentration_risk` | structure | info | One campaign > 70% of total conversions |
| `spend_concentration_risk` | structure | warning | One campaign > 80% of total spend |
| `tracking_sanity_warning` | tracking | critical | Account total spend > 100, total conversions == 0 |
| `no_active_campaigns` | structure | warning | Zero enabled campaigns |
| `many_paused_or_removed` | structure | info | > 5 non-enabled campaigns |

Signals are sorted: **critical → warning → info**.

---

## Source Truth Behavior

| source value | live_data | source_label | Behavior |
|---|---|---|---|
| `google_ads_api` | `true` | "Live Google Ads API" | Real campaign data |
| `mock_fallback` | `false` | "Demo data (no live connection)" | Warning appended |
| `mock` | `false` | "Demo data (no live connection)" | Warning appended |
| `google_ads_api_error` | `false` | "Demo data (API error fallback)" | Warning appended |

No mock source is ever presented as live.

---

## Currency Behavior

- All monetary evidence includes `{amount, currency_code, formatted}`.
- `currency_code` is account-native (from live API or `google_ads_customer_hierarchy` DB).
- Unknown currency → `null`, not `"USD"`.
- No FX conversion performed.
- `conversion_applied: false` always.
- Mixed-currency MCC rollups detected and warned.

---

## Test Results

| Suite | Tests | Result |
|---|---|---|
| `test_google_ads_intelligence_modules` | 24 | ✅ 24/24 PASS |
| `test_google_ads_report_query` | 43 | ✅ 43/43 PASS |
| `test_google_ads_mcc_ui_mapping` | 21 | ✅ 21/21 PASS |
| `test_google_ads_mcc_hierarchy` | 18 | ✅ 18/18 PASS |
| `test_google_ads_api_validation` | 13 | ✅ 13/13 PASS |
| `test_google_ads_oauth_phase1` | 27 | ✅ 27/27 PASS |
| `test_google_ads_truth_mode` | 28 | ✅ 28/28 PASS |
| `test_google_ads_account_intelligence` | 63 | ✅ 63/63 PASS |
| Google Ads total | **174** | ✅ **174/174** |
| `test_flows_approval_dry_run` | 20 | ✅ PASS |
| `test_flows_draft_mode` | 11 | ✅ PASS |
| `test_chat_runtime_hardening` | 12 | ✅ PASS |
| `test_ai_provider_policy` | 6 | ✅ PASS |
| `test_vacante_flow` | 9 | ✅ PASS |
| `test_conversation_brief` | (script) | ✅ PASS |
| `test_mwr_landing` | 2 | ✅ PASS |
| `test_orchestrator` | 45 | ⚠️ 12F+9E (pre-existing) |

**Pre-existing orchestrator failures are unrelated to Google Ads work.** Confirmed against Phase 2D baseline — same count.

---

## Known Limitations

1. **Health Score not computed** — `score_status: "planned"` returned. Score v1 spec in `ACCOUNT_HEALTH_SCORE_NEXT.md`.
2. **Search Terms module is planned** — not live. Separate spec in `SEARCH_TERMS_NEXT.md`.
3. **PMax module is planned** — not live. Spec in `PMAX_NEXT.md`.
4. **Audiences module is planned_limited** — `AudienceInsightsService` may require allowlist. Spec in `AUDIENCES_NEXT.md`.
5. **Account Health uses campaign-level data only** — keyword, asset, audience, search term signals not yet included.
6. **Thresholds are static** — no account-size normalization yet. Large accounts may need adjusted thresholds in Score v1.
7. **MCC rollup signals** — not yet implemented. Each module operates on a single customer_id.

---

## Deploy Recommendation

**Ready for controlled deploy to production.**

Pre-deploy procedure:
1. Clean checkout @ this commit SHA.
2. `python3 -m py_compile backend_py/app.py database.py models.py`
3. Run full test suites (all must pass except known orchestrator pre-existing).
4. Local smoke: healthz + `/intelligence/modules` + `/intelligence/account-health?customer_id=X`.
5. Backup production app + DB.
6. `rsync` to `/opt/camarad/` (no `--delete`).
7. `pm2 restart camarad --update-env`.
8. Live smoke on `https://camarad.ai`.

Rollback: `sudo rsync -a "$BACKUP_DIR/app/" /opt/camarad/ && pm2 restart camarad --update-env`

---

## Next Step

Phase 2E controlled deploy → then Phase 2F (Account Health Score v1 or Search Terms module).
