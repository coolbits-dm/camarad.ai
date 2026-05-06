# Next Google Ads Source Truth Fixes

Date: 2026-05-06

## Remaining Priorities

1. Debug/test endpoint
   - Audit any Google Ads debug or test-call endpoints.
   - Ensure read-only test responses distinguish real API checks, cached data, mock/demo data, and API errors.
   - Keep these endpoints safe and do not expose sensitive values.

2. UI source badges everywhere
   - Normalize display labels for `google_ads_api`, `cached_google_ads_api`, `google_ads_api_error`, `mock`, and `mock_fallback`.
   - Ensure cached data is visibly labeled as cached, not fresh live API data.
   - Ensure fallback/mock warnings are visible near affected tables and panels.

3. Legacy endpoints
   - Audit and update keywords, metrics, reports, and generate-assets paths.
   - Connected/API-validated users should not receive silent demo rows when API calls fail.
   - Every response should expose source, live/cache/fresh, mock/fallback flags, and warnings where applicable.

## Done Before This File

- Campaign rows no longer silently fall back to mock for connected/API-validated users.
- Search Terms no longer silently falls back to mock on token/API failure.
- Cached accounts and cached MCC hierarchy reads now use `source=cached_google_ads_api`.
