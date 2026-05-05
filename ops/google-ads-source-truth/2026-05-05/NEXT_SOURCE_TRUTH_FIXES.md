# Next Google Ads Source Truth Fixes

## 1. Finish Propagation Audit

Overview, diagnostics, ai-brief, account-health, and waste-finder now carry source policy fields for campaign-derived data. A follow-up should review response consumers and tests to make sure every UI and downstream agent path uses `live_data`, `mock_used`, and `fallback_used` rather than inferring from row presence.

## 2. Search Terms Token Refresh Path

`_gads_resolve_live_search_terms()` still has the same older token-refresh distinction identified in the scan. It should use the same source policy contract:

- connected/API-validated success: `source=google_ads_api`
- connected/API-validated failure: `source=google_ads_api_error` by default
- explicit fallback only: `source=mock_fallback`
- unauthenticated/demo: `source=mock`

## 3. Accounts Cached Source Labeling

`/api/connectors/google-ads/accounts` and MCC hierarchy GET can return cached DB rows as `source=google_ads_api`. That should be renamed or clarified with fields such as:

- `source=cached_google_ads_api`
- `live_data=false`
- `cache=true`
- `fresh=false`

MCC hierarchy POST can remain fresh `source=google_ads_api`.

## 4. Debug/Test Endpoint

`/api/connectors/google-ads/test-call` is simulated and should not look like a live API test. Follow-up:

- restrict to internal/dev, or remove from production UI
- return `source=simulated_debug`
- return `live_data=false`
- remove fake token-like request headers from the JSON response

## 5. UI Source Badges Everywhere

Campaign table now has a local source banner. Remaining UI follow-ups:

- add per-section source badges to audit campaign subtables
- avoid static `Live` labels on module chips before a module has run
- remove USD as a default for unknown account currency
- preserve explicit API failure warnings instead of filtering all generic fallback warnings

## 6. Legacy Google Ads Endpoints

The legacy endpoints still need source truth cleanup:

- `/api/connectors/google-ads/keywords`
- `/api/connectors/google-ads/metrics`
- `/api/connectors/google-ads/reports`
- `/api/connectors/google-ads/generate-assets`

Either implement live read behavior with the same source policy or mark/hide them as explicit demo/draft surfaces.
