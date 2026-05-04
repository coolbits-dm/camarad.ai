# Google Ads Campaigns Read-Only — Phase 2B Plan

**Status**: Deferred  
**Precondition**: Phase 2A `connected_live` validation complete ✅  
**No mutations. No campaign writes. Read-only only.**

---

## Scope

Fetch campaign performance data from Google Ads for a selected customer ID. Display in the connector UI.

---

## New Endpoints

### `GET /api/connectors/google-ads/campaigns`
- Requires `connected_live=True` (api_validated).
- Accepts optional query param `customer_id`. Defaults to `customer_id` in metadata (first validated account).
- Fetches via GAQL search: `SELECT campaign.id, campaign.name, campaign.status, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions FROM campaign ORDER BY campaign.id LIMIT 50`
- Token auto-refreshed before call using `_gads_get_fresh_access_token`.
- Returns: `{ success: true, source: "google_ads_api", campaigns: [...], customer_id: str, connected_live: true }`

### `POST /api/connectors/google-ads/campaigns/search` (optional)
- Same as GET but accepts arbitrary GAQL in request body (validated against allowlist of read-only fields).
- Allowlist: `campaign.*`, `ad_group.*`, `metrics.*`, `segments.date` — no `mutate`, no `create`, no `remove`, no `budget.amount_micros` writes.

---

## New Helpers

| Helper | Purpose |
|--------|---------|
| `_gads_gaql_search(access_token, developer_token, customer_id, gaql)` | POST to `googleads.googleapis.com/v17/customers/{id}/googleAds:search`. Returns rows list. |
| `_gads_format_campaign_row(row)` | Parse gRPC-style JSON row into flat dict `{id, name, status, impressions, clicks, cost, conversions}`. |
| `_gads_get_fresh_access_token_for_call(user_id)` | Same as Phase 2A token refresh but used in per-call path. Caches result 50 minutes in app context. |

---

## Account Selector UI

- `#gadsAccountSelector` dropdown populated from `_gads_get_accessible_customers`.
- On change: fires `GET /api/connectors/google-ads/campaigns?customer_id=X`.
- Stores selected `customer_id` in localStorage key `gads_selected_customer_id`.
- Shown only when `connected_live=True` and `accessible_customers_count > 1`.

---

## GAQL Allowlist

Phase 2B validates outbound GAQL against an allowlist before sending to Google Ads API:
- **Allowed tables**: `campaign`, `ad_group`, `ad_group_ad`, `metrics`, `segments`
- **Blocked tokens**: `CREATE`, `REMOVE`, `MUTATE`, `DELETE`, `UPDATE`, `INSERT`, `budget.amount_micros` (write fields)
- **Validation**: regex scan on GAQL string before POST. If any blocked token present → 400 `gaql_blocked`.

---

## Caching

- Campaigns cached per `(user_id, customer_id)` in `google_ads_campaigns_cache` table for 15 minutes.
- `last_fetched_at` tracked. Stale flag returned in response when cache is used.
- On `_gads_token_revoke()` → invalidate cache for user.

---

## DB Table: `google_ads_campaigns_cache`

```sql
CREATE TABLE IF NOT EXISTS google_ads_campaigns_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    customer_id TEXT NOT NULL,
    campaigns_json TEXT NOT NULL,
    fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, customer_id)
)
```

---

## UI Changes (connectors.html)

- Campaigns tab: shows data table when `connected_live=True`.
- Shows "Loading campaigns..." spinner on first load.
- Shows `last_fetched_at` timestamp.
- Account selector shown above campaigns table when multiple accounts.
- No "create campaign" or "edit campaign" UI elements.

---

## Security

- All GAQL validated before send.
- No campaign mutations.
- No budget updates.
- No ad creative uploads.
- Access token: not stored, not logged, not returned.
- Campaign data: returned as-is (no PII in campaign names/IDs).

---

## Dependencies

- Phase 2A must be deployed and live (✅ as of this plan).
- Real Google Ads developer token must be approved by Google (basic access or standard). Test account tokens restricted to test accounts only — verify.
- No new pip packages. Uses `requests` (already imported).

---

## Deferred to Phase 2C

- Ad group level data
- Keyword-level metrics
- Attribution model selection
- GAQL query builder UI
- Bulk customer switching
- Scheduled refresh (cron)
