# Next Google Ads Source Truth Fixes

## 1. Accounts Cached-Source Labeling

`/api/connectors/google-ads/accounts` and MCC hierarchy GET can return cached DB rows while
using `source=google_ads_api`. Follow-up should distinguish fresh API reads from cached data.

Recommended contract:

- `source=cached_google_ads_api`
- `live_data=false`
- `cache=true`
- `fresh=false`

MCC hierarchy POST can remain fresh `source=google_ads_api`.

## 2. Debug/Test Endpoint

`/api/connectors/google-ads/test-call` is simulated and should not look like a live API call.

Recommended fix:

- restrict to internal/dev or remove from production UI
- return `source=simulated_debug`
- return `live_data=false`
- remove fake token-like request headers from JSON response

## 3. UI Source Badges Everywhere

Campaigns and Search Terms now have backend source truth. UI follow-up should normalize source
badges across all tables and module panels.

Priorities:

- show local source badges for every data table/panel
- visibly warn on `mock_fallback` and `google_ads_api_error`
- avoid static `Live` labels before a module has run
- keep unknown currency explicit instead of falling back to USD

## 4. Legacy Google Ads Endpoints

Legacy endpoints still need cleanup:

- `/api/connectors/google-ads/keywords`
- `/api/connectors/google-ads/metrics`
- `/api/connectors/google-ads/reports`
- `/api/connectors/google-ads/generate-assets`

Either implement live read behavior with the same source policy or mark/hide them as explicit
demo/draft surfaces.
