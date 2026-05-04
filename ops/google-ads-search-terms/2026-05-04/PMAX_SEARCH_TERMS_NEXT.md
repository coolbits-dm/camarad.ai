# PMax Search Terms — Next Plan
**Phase:** 2F or 2G  
**After:** Phase 2E.2 (standard search terms via search_term_view)

---

## Why PMax Search Terms Are Separate

`search_term_view` does **not** include Performance Max search term data.

PMax search terms require `campaign_search_term_view`, which:
- Is a separate GAQL resource
- Has limited field availability compared to standard search_term_view
- May not be available on all API access levels
- Returns terms aggregated at campaign level (no ad group breakdown)

---

## campaign_search_term_view Fields

Available in Google Ads API v20:

```sql
SELECT
  campaign_search_term_view.search_term,
  campaign_search_term_view.status,
  campaign.id,
  campaign.name,
  campaign.advertising_channel_type,
  metrics.impressions,
  metrics.clicks,
  metrics.cost_micros,
  metrics.conversions,
  metrics.conversions_value
FROM campaign_search_term_view
WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'
  AND segments.date DURING LAST_30_DAYS
ORDER BY metrics.cost_micros DESC
LIMIT 200
```

**Limitations:**
- No ad group breakdown (PMax doesn't have traditional ad groups)
- No `metrics.average_cpc` (may not be available)
- No `metrics.ctr` (may not be available via this resource)
- `status` field values may differ from search_term_view

---

## Proposed Implementation

### New helper: `_gads_fetch_pmax_search_terms()`
- GAQL against `campaign_search_term_view`
- Filter: `campaign.advertising_channel_type = 'PERFORMANCE_MAX'`
- Returns rows with `match_source = "pmax"`

### Merged endpoint option: `?include_pmax=true`
- Add `include_pmax` query parameter to existing `/intelligence/search-terms`
- If `include_pmax=true`: run both `search_term_view` + `campaign_search_term_view`
- Merge rows, tag each with `match_source = standard | pmax`
- If `campaign_search_term_view` is unavailable (API error): surface as partial data warning

### Separate endpoint option: `/intelligence/search-terms/pmax`
- Cleaner — separate endpoint for PMax-specific analysis
- Avoids mixing different row schemas

**Recommendation:** Separate endpoint. Less risk of confusion about data completeness.

---

## Risks

1. `campaign_search_term_view` availability depends on account type and API access level
2. PMax search terms have fewer fields — UI must degrade gracefully
3. Terms from PMax may overlap with standard search if cross-campaign bidding active
4. Merging both sets without deduplication can inflate numbers — need clear labeling

---

## Capability Test Required

Before implementing, test `campaign_search_term_view` against a live MATCA PMax campaign:

```bash
curl -X POST "https://googleads.googleapis.com/v20/customers/{cid}/googleAds:searchStream" \
  -H "Authorization: Bearer {token}" \
  -H "developer-token: {dev_token}" \
  -H "login-customer-id: {mcc_id}" \
  -d '{"query": "SELECT campaign_search_term_view.search_term, campaign.name, metrics.impressions, metrics.cost_micros FROM campaign_search_term_view WHERE campaign.advertising_channel_type = '"'"'PERFORMANCE_MAX'"'"' LIMIT 5"}'
```

Expected outcomes:
- HTTP 200 + data: ready to implement
- HTTP 400 `INVALID_ARGUMENT`: resource not available, needs investigation
- HTTP 403: API access level insufficient, may need allowlist

---

## Acceptance Criteria (when implemented)

- [ ] `campaign_search_term_view` query succeeds against MATCA PMax campaign
- [ ] PMax rows tagged `match_source = "pmax"`
- [ ] Warning shown: "PMax search terms may have limited field availability"
- [ ] No mixing of standard/PMax rows without clear tagging
- [ ] `pmax_gap_notice` signal removed from standard endpoint when PMax endpoint is live
- [ ] Tests: 15+ covering PMax-specific row parsing, fallback, and source truth
