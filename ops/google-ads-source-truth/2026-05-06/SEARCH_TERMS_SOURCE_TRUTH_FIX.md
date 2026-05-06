# Google Ads Search Terms Source Truth Fix

Date: 2026-05-06

## Issue

`_gads_resolve_live_search_terms()` still used the older fallback pattern. For a connected
and API-validated user, a Google Ads Search Terms token/API failure could fall through to
mock rows and label them as `mock_fallback` based only on whether a live call was attempted.

That left the token-refresh path weaker than the campaigns source-truth contract.

## Functions Changed

- `backend_py/app.py`
  - Updated `_gads_resolve_live_search_terms()`.
  - Updated `/api/connectors/google-ads/intelligence/search-terms`.
  - Reused the existing `_gads_source_policy()` from the campaigns source-truth fix.

- `backend_py/test_google_ads_source_truth_search_terms.py`
  - Added focused resolver and endpoint source-truth coverage.

## Behavior Before

- Connected/API-validated Search Terms live API failure could return fallback mock rows.
- Token refresh failure did not clearly distinguish connected live API error from unauthenticated demo.
- Endpoint warnings were hand-built and did not consistently use the shared source policy.

## Behavior After

- Live API success:
  - `source=google_ads_api`
  - `live_data=true`
  - `mock_used=false`
  - `fallback_used=false`
- Connected/API-validated token refresh or Search Terms API failure by default:
  - `source=google_ads_api_error`
  - `live_data=false`
  - `mock_used=false`
  - `fallback_used=false`
  - `rows=[]`
  - warning present
- Explicit fallback (`allow_fallback=1`) only:
  - `source=mock_fallback`
  - `live_data=false`
  - `fallback_used=true`
  - warning present
- Unauthenticated/demo:
  - `source=mock`
  - `live_data=false`
  - `mock_used=true`

## PMax Limitation

Search Terms remains read-only `search_term_view` only.

This fix does not implement Performance Max search terms. The endpoint still preserves the
limitation notice that PMax terms require a separate `campaign_search_term_view` path.

No negative keyword actions were added.

## Source Contract

| Source | live_data | mock_used | fallback_used | Meaning |
|---|---:|---:|---:|---|
| `google_ads_api` | true | false | false | Real Search Terms data from Google Ads API. |
| `google_ads_api_error` | false | false | false | Connected live path failed; no demo rows substituted. |
| `mock_fallback` | false | false | true | Explicit fallback was requested after live failure. |
| `mock` | false | true | false | Demo or unauthenticated safe response. |

## Tests

Passed:

- `python3 -m py_compile backend_py/app.py backend_py/database.py backend_py/models.py backend_py/ai/__init__.py backend_py/ai/provider_policy.py`
- `python3 -m unittest backend_py/test_google_ads_source_truth_search_terms.py`
- `python3 -m unittest backend_py/test_google_ads_source_truth_campaigns.py`
- `python3 -m unittest backend_py/test_google_ads_oauth_phase1.py`
- `python3 -m unittest backend_py/test_google_ads_api_validation.py`
- `python3 -m unittest backend_py/test_google_ads_mcc_hierarchy.py`
- `python3 -m unittest backend_py/test_google_ads_mcc_ui_mapping.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_search_terms.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_intelligence_modules.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_report_query.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_truth_mode.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_chat_runtime_hardening.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_ai_provider_policy.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_flows_draft_mode.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_flows_approval_dry_run.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_vacante_flow.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_mwr_landing.py`
- `AUTH_REQUIRED=0 DATABASE=/tmp/camarad_source_truth_search_terms_conversation_brief.db PYTHONPATH=backend_py:. python3 backend_py/test_conversation_brief.py`

Known failures:

- Root-form runs for `test_google_ads_search_terms.py`,
  `test_google_ads_intelligence_modules.py`, `test_google_ads_report_query.py`, and
  `test_google_ads_truth_mode.py` fail due to the known import-path issue when
  `backend_py` is not on `PYTHONPATH`.
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_orchestrator.py`
  remains in the unrelated known-failure bucket: 18 failures and 8 errors.

## Remaining Source Truth Work

See `NEXT_SOURCE_TRUTH_FIXES.md` for remaining priorities.
