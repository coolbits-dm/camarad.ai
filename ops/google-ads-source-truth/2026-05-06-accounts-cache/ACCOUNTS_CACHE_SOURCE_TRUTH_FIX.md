# Google Ads Accounts Cache Source Truth Fix

Date: 2026-05-06

## Issue

`GET /api/connectors/google-ads/accounts` and `GET /api/connectors/google-ads/mcc/hierarchy` read account selector data from local DB cache but labeled those responses as `source=google_ads_api`. That made cached data look like a fresh live API read.

## Changed

- `backend_py/app.py`
  - Added `_gads_cached_accounts_source_policy()`.
  - Labeled cached account selector and cached MCC hierarchy reads as `source=cached_google_ads_api`.
  - Added `live_data=false`, `cache=true`, `fresh=false`, and a cached-data warning to cached account responses.
  - Preserved `connected_live=true` separately when OAuth/API validation exists.
  - Kept `POST /api/connectors/google-ads/mcc/hierarchy` as the fresh API path with `source=google_ads_api`, `live_data=true`, `cache=false`, `fresh=true`.
  - Marked POST hierarchy token/API failure paths as `source=google_ads_api_error`, `live_data=false`, with no mock fallback.
- Existing contract tests were updated where they asserted the previous misleading cached-as-live label.
- Added `backend_py/test_google_ads_source_truth_accounts_cache.py`.

## Before And After

| Path | Before | After |
| --- | --- | --- |
| `GET /api/connectors/google-ads/accounts` for connected/API-validated users | Cached DB rows labeled `google_ads_api` | Cached DB rows labeled `cached_google_ads_api`, non-live |
| `GET /api/connectors/google-ads/mcc/hierarchy` | Cached DB rows labeled `google_ads_api` | Cached DB rows labeled `cached_google_ads_api`, non-live |
| `POST /api/connectors/google-ads/mcc/hierarchy` success | Fresh API source | Fresh API source plus explicit live/cache/fresh fields |
| `POST /api/connectors/google-ads/mcc/hierarchy` failure | Safe error without source policy | `google_ads_api_error`, non-live, no mock rows |
| Unauthenticated/demo accounts | Mock data | Mock data remains explicitly non-live |

## Cached Source Contract

- Fresh API success: `source=google_ads_api`, `live_data=true`, `cache=false`, `fresh=true`.
- Cached DB read: `source=cached_google_ads_api`, `live_data=false`, `cache=true`, `fresh=false`, warning: `Using cached Google Ads account data.`
- Mock/demo: `source=mock`, `live_data=false`, `mock_used=true`.
- API/token failure: `source=google_ads_api_error`, `live_data=false`, no mock rows.

## Tests

Passed:

- `python3 -m py_compile backend_py/app.py backend_py/database.py backend_py/models.py backend_py/ai/__init__.py backend_py/ai/provider_policy.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_source_truth_accounts_cache.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_source_truth_search_terms.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_source_truth_campaigns.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_mcc_hierarchy.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_mcc_ui_mapping.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_api_validation.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_oauth_phase1.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_truth_mode.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_report_query.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_intelligence_modules.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_search_terms.py`
- Core smoke unit tests listed in the implementation request, except the known orchestrator suite.
- `AUTH_REQUIRED=0 DATABASE=/tmp/camarad_source_truth_accounts_cache_conversation_brief.db PYTHONPATH=backend_py:. python3 backend_py/test_conversation_brief.py`

Known pre-existing failure:

- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_orchestrator.py` remains `18` failures and `8` errors.

## Remaining Source-Truth Work

- Debug/test endpoint source labeling.
- UI source badges everywhere.
- Legacy endpoints: keywords, metrics, reports, generate-assets.
