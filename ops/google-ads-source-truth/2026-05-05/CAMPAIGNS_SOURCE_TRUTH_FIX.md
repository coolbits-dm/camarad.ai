# Google Ads Campaigns Source Truth Fix - 2026-05-05

## Issue

The scan found that `/api/connectors/google-ads/campaigns` could silently fall through to Coolbits/mock data after a connected/API-validated Google Ads API failure. The shared `_gads_resolve_live_campaigns()` helper also returned plain `source=mock` on token refresh failure, even when metadata said the user was connected and API validated.

That made it possible for mock rows to appear in live product behavior without `live_data=false`, `fallback_used=true`, or a visible warning.

## Functions Changed

- `backend_py/app.py`
  - Added `_gads_source_policy()`.
  - Added `_gads_truthy_request_arg()`.
  - Updated `/api/connectors/google-ads/campaigns`.
  - Updated `_gads_resolve_live_campaigns()`.
  - Propagated source policy fields through:
    - `/api/connectors/google-ads/overview`
    - `/api/connectors/google-ads/diagnostics`
    - `/api/connectors/google-ads/ai-brief`
    - `/api/connectors/google-ads/intelligence/account-health`
    - `/api/connectors/google-ads/intelligence/waste-finder`
  - Updated `_gads_build_module_response()` to include `mock_used` and `fallback_used`.

- `backend_py/templates/connectors.html`
  - Added a small campaign source/currency/warning banner above the campaign table.

## Endpoint Behavior

Before:

- Connected/API-validated `/campaigns` live API failure could fall through to Coolbits/mock.
- Mock campaign rows could be returned without `live_data=false` or warning.
- Derived endpoints did not consistently expose `live_data`, `mock_used`, `fallback_used`, or warnings.

After:

- Live success returns:
  - `source=google_ads_api`
  - `live_data=true`
  - `mock_used=false`
  - `fallback_used=false`
- Connected/API-validated live failure returns by default:
  - `source=google_ads_api_error`
  - `live_data=false`
  - `mock_used=false`
  - `fallback_used=false`
  - `campaigns=[]`
  - warning present
- Explicit fallback (`allow_fallback=1`) returns:
  - `source=mock_fallback`
  - `live_data=false`
  - `fallback_used=true`
  - warning present
- Explicit demo (`demo=1` or `mock=1`) returns:
  - `source=mock`
  - `live_data=false`
  - `mock_used=true`
- Unauthenticated/no-token behavior remains safe:
  - mock demo data is allowed only with `live_data=false`, `mock_used=true`, and warning.

## Source Contract

| Source | live_data | mock_used | fallback_used | Notes |
|---|---:|---:|---:|---|
| `google_ads_api` | true only for connected live users | false | false | Real Google Ads API data only. |
| `google_ads_api_error` | false | false | false | Connected live path failed; no demo rows substituted. |
| `mock_fallback` | false | false | true | Only when fallback/demo was explicitly allowed. |
| `mock` | false | true | false | Demo or unauthenticated safe response. |
| `coolbits` | false | false | false | Legacy gateway source; not marked live. |

## Tests

Added:

- `backend_py/test_google_ads_source_truth_campaigns.py`

Updated for the new contract:

- `backend_py/test_google_ads_campaigns_phase2b.py`
- `backend_py/test_google_ads_account_intelligence.py`

The focused source-truth test covers:

- source policy fields
- resolver behavior on connected live exceptions
- `/campaigns` live success
- `/campaigns` connected live API failure
- explicit fallback non-live behavior
- unauthenticated mock non-live behavior
- propagation into overview/account-health/waste-finder
- no sensitive values in response bodies
- no fallback gateway call on connected live failure

Passed:

- `python3 -B -m py_compile backend_py/app.py backend_py/database.py backend_py/models.py backend_py/ai/__init__.py backend_py/ai/provider_policy.py`
- `python3 -B -m unittest backend_py/test_google_ads_source_truth_campaigns.py`
- `PYTHONPATH=backend_py:. python3 -B -m unittest backend_py/test_google_ads_truth_mode.py`
- `PYTHONPATH=backend_py:. python3 -B -m unittest backend_py/test_google_ads_report_query.py`
- `PYTHONPATH=backend_py:. python3 -B -m unittest backend_py/test_google_ads_intelligence_modules.py`
- `PYTHONPATH=backend_py:. python3 -B -m unittest backend_py/test_google_ads_search_terms.py`
- `python3 -B -m unittest backend_py/test_google_ads_mcc_ui_mapping.py`
- `python3 -B -m unittest backend_py/test_google_ads_mcc_hierarchy.py`
- `python3 -B -m unittest backend_py/test_google_ads_api_validation.py`
- `python3 -B -m unittest backend_py/test_google_ads_oauth_phase1.py`
- `PYTHONPATH=backend_py:. python3 -B -m unittest backend_py/test_ppc_agent.py`
- `PYTHONPATH=backend_py:. python3 -B -m unittest backend_py/test_google_ads_campaigns_phase2b.py`
- `PYTHONPATH=backend_py:. python3 -B -m unittest backend_py/test_google_ads_account_intelligence.py`
- `PYTHONPATH=backend_py:. python3 -B -m unittest backend_py/test_chat_runtime_hardening.py`
- `PYTHONPATH=backend_py:. python3 -B -m unittest backend_py/test_ai_provider_policy.py`
- `PYTHONPATH=backend_py:. python3 -B -m unittest backend_py/test_flows_draft_mode.py`
- `PYTHONPATH=backend_py:. python3 -B -m unittest backend_py/test_flows_approval_dry_run.py`
- `PYTHONPATH=backend_py:. python3 -B -m unittest backend_py/test_vacante_flow.py`
- `PYTHONPATH=backend_py:. python3 -B -m unittest backend_py/test_mwr_landing.py`
- `AUTH_REQUIRED=0 DATABASE=/tmp/camarad_source_truth_campaigns_conversation_brief.db PYTHONPATH=backend_py:. python3 -B backend_py/test_conversation_brief.py`

Known failures:

- Root-form runs for `test_google_ads_truth_mode.py`, `test_google_ads_report_query.py`,
  `test_google_ads_intelligence_modules.py`, `test_google_ads_search_terms.py`, and
  `test_ppc_agent.py` failed only because the root command does not put
  `backend_py` on `PYTHONPATH`.
- `PYTHONPATH=backend_py:. python3 -B -m unittest backend_py/test_orchestrator.py`
  remains failing with the pre-existing client-scope/route assertions
  (18 failures, 8 errors).

## Remaining Later Fixes

This change intentionally does not fix every Google Ads source issue. Remaining work is tracked in `NEXT_SOURCE_TRUTH_FIXES.md`.
