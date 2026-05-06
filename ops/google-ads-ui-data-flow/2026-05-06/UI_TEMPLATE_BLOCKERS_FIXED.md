# Google Ads UI Template Blockers Fixed

Date: 2026-05-06

## Blockers From Deploy Readiness

Deploy readiness for `35707e5e4063a7914a7e56299347090cb5f1e3f9` found the backend changes acceptable, but blocked the template because it looked like the rejected simplification:

- The visible Google Ads `Intelligence` tab was renamed/replaced by `Reports`.
- `Diagnostics` was hidden from primary navigation.
- The intelligence module workspace still existed internally, but was no longer presented as the same visible Intelligence workspace.

## What Was Fixed

- Restored `Intelligence` as a visible primary Google Ads tab.
- Restored `Diagnostics` as a visible primary Google Ads tab.
- Kept `Reports` as a separate primary tab for report-query presets and metric catalog.
- Kept `AI Brief` and `Settings` separate.
- Kept Advanced / Legacy for dev/legacy tools only: Test API, Budget Pacing, and Asset Generator.
- Removed Diagnostics from Advanced / Legacy because it is primary again.

## Final Primary Tab List

1. Overview
2. Campaigns
3. Intelligence
4. Diagnostics
5. Reports
6. AI Brief
7. Settings

## Data-Flow Wiring Preserved

- Central `gadsState` remains in place.
- Selected customer, MCC, account metadata, currency, timezone, days, and date range are still centralized.
- Primary date selector remains in the account context bar.
- Campaigns and Intelligence date selectors stay synced.
- Date/account changes clear stale outputs and reload the active tab.
- `gadsGetDateParams()` and `gadsGetAccountParams()` remain the shared request helpers.
- `gadsRenderDataMeta()` remains the shared source/date/currency/warnings renderer.
- Intelligence and Diagnostics loaders continue using selected account, MCC, and date context.
- Reports presets continue using report/query with `date_range` from the shared helper.

## Tests

Passed:

- `python3 -m py_compile backend_py/app.py backend_py/database.py backend_py/models.py backend_py/ai/__init__.py backend_py/ai/provider_policy.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_ui_data_flow.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_ui_simplification.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_intelligence_modules.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_report_query.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_search_terms.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_source_truth_accounts_cache.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_source_truth_search_terms.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_source_truth_campaigns.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_mcc_hierarchy.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_mcc_ui_mapping.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_api_validation.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_oauth_phase1.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_truth_mode.py`
- Requested core non-orchestrator tests.
- `AUTH_REQUIRED=0 DATABASE=/tmp/camarad_ui_data_flow_template_fix_conversation_brief.db PYTHONPATH=backend_py:. python3 backend_py/test_conversation_brief.py`

Known pre-existing failure:

- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_orchestrator.py`
  - `18` failures
  - `8` errors

## Deploy Recommendation

The template blocker is fixed. Prepare a new no-surprises deploy readiness pass for the new commit before deploying, because production still has the rollback template and this branch changes `backend_py/templates/connectors.html`.
