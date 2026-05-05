# Google Ads UI Simplification Result

Date: 2026-05-05 Europe/Bucharest

## Scope

- Repo edited only: `/opt/camarad-repo`.
- No production files changed.
- No deploy, restart, rsync, or Google Ads write/mutation API calls.
- Backend product behavior was not expanded.

## Tabs Before/After

Live/current dirty baseline before this pass exposed six visible Google Ads tabs:

- Overview
- Campaigns
- Diagnostics
- AI Brief
- Settings
- Intelligence

Repo after this pass exposes five visible Google Ads tabs:

- Overview
- Campaigns
- Reports
- AI Brief
- Settings

`Diagnostics`, `Test API`, `Budget Pacing`, and `Asset Generator` remain in hidden panes for compatibility, but they are no longer primary workspace tabs.

## What Changed

- Renamed the visible `Intelligence` workspace to `Reports`.
- Moved `Diagnostics` out of primary navigation.
- Added a compact `Health / Diagnostics` strip under Overview that points users to Account Health in Reports.
- Added an `Advanced / Legacy` accordion in Settings for:
  - Test API
  - Budget Pacing
  - Asset Generator
  - Diagnostics
- Kept planned modules compact under `Coming next`.
- Compact account selector copy now reads:
  - Direct Access: OAuth-visible accounts
  - Manager/MCC: Manager context
  - Client Account: Reporting account

## Badge And Currency Cleanup

Source badges now use a single helper:

- `google_ads_api` -> Live
- `mock_fallback` -> API Error / Fallback
- `mock` / `mock_demo` -> Mock
- `planned` -> Planned
- unknown/error -> Unknown/Error

Currency handling now uses `gadsCurrencyBadge()` and `gadsFormatMoney()` in the Google Ads UI path.

- Known currency displays as `Native: CODE`.
- Unknown currency displays as `Currency unknown`.
- Unsupported conversion can display `Conversion unavailable`.
- Campaign/report Google Ads UI no longer defaults to `$` when the account currency is unknown.

## Tests

Passed:

- `python3 -m py_compile backend_py/app.py backend_py/database.py backend_py/models.py backend_py/ai/__init__.py backend_py/ai/provider_policy.py`
- `python3 -m unittest backend_py/test_google_ads_ui_simplification.py`
- `python3 -m unittest backend_py/test_google_ads_mcc_ui_mapping.py`
- `python3 -m unittest backend_py/test_google_ads_mcc_hierarchy.py`
- `python3 -m unittest backend_py/test_google_ads_api_validation.py`
- `python3 -m unittest backend_py/test_google_ads_oauth_phase1.py`
- `python3 -m unittest backend_py/test_vacante_flow.py`
- `python3 -m unittest backend_py/test_mwr_landing.py`
- `AUTH_REQUIRED=0 DATABASE=/tmp/camarad_stabilization_conversation_brief.db python3 backend_py/test_conversation_brief.py`

Passed with `PYTHONPATH=backend_py:.`:

- `backend_py/test_google_ads_intelligence_modules.py`
- `backend_py/test_google_ads_report_query.py`
- `backend_py/test_google_ads_search_terms.py`
- `backend_py/test_google_ads_mcc_ui_mapping.py`
- `backend_py/test_google_ads_mcc_hierarchy.py`
- `backend_py/test_google_ads_api_validation.py`
- `backend_py/test_google_ads_oauth_phase1.py`
- `backend_py/test_google_ads_truth_mode.py`
- `backend_py/test_chat_runtime_hardening.py`
- `backend_py/test_ai_provider_policy.py`
- `backend_py/test_flows_draft_mode.py`
- `backend_py/test_flows_approval_dry_run.py`
- `backend_py/test_vacante_flow.py`
- `backend_py/test_mwr_landing.py`

Known failures/noise:

- Running several tests from repo root without `PYTHONPATH=backend_py:.` still fails with import-path errors such as `ModuleNotFoundError: No module named 'app'`, `config`, `models`, or `ai`.
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_orchestrator.py` remains unstable: 45 tests run, 18 failures, 8 errors. This matches the known orchestrator instability and was not caused by this UI-only pass.

## Known Limitations

- The UI simplification is repo-only and not deployed.
- `backend_py/templates/connectors.html` was already dirty before this pass with Marketing Audit/PPC Agent UI. That already-live work was split into reconciliation commit `e18b37f` before staging this UI simplification.
- Production still lacks a deploy report/buildinfo marker for the current live source; `/api/_buildinfo` still reports `commit=unknown`.
- README/product-roadmap edits and historical ops artifacts remain dirty/untracked and are intentionally outside this UI simplification.

## Deploy Recommendation

Do not deploy yet.

The source split is now traceable in git, but production metadata still needs a clean deploy report/buildinfo path. Deploy the Google Ads UI simplification only after reviewing the pushed commits and creating a deploy report for the chosen SHA.
