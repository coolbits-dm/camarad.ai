# Search Terms Intelligence Module — Next Plan

Phase: PLANNED (not implemented in Phase 2E)  
Target: Phase 2F or later  

---

## Standard Search Campaigns — search_term_view

GAQL resource: `search_term_view`

Key fields:
- `search_term_view.search_term` — actual query user typed
- `search_term_view.status` — ADDED / EXCLUDED / NONE
- `campaign.id`, `campaign.name`, `campaign.advertising_channel_type`
- `ad_group.id`, `ad_group.name`
- `metrics.impressions`, `metrics.clicks`, `metrics.cost_micros`
- `metrics.conversions`, `metrics.conversions_value`
- `metrics.ctr`, `metrics.average_cpc`
- `segments.keyword.info.text` — matched keyword text (if available)
- `segments.keyword.info.match_type` — EXACT / PHRASE / BROAD

**Important**: `search_term_view` does NOT include Performance Max search term data.

---

## Performance Max — campaign_search_term_view

For PMax campaigns, use `campaign_search_term_view` where supported.

GAQL resource: `campaign_search_term_view`

Key fields:
- `campaign_search_term_view.search_term`
- `campaign_search_term_view.status`
- `campaign.id`, `campaign.name`, `campaign.advertising_channel_type`
- Metrics: impressions, clicks, cost_micros, conversions, conversions_value

**Note**: PMax search terms via `campaign_search_term_view` may have limited visibility and
matching details. This path should be capability-tested before promising users full pMax
search term reporting.

---

## Proposed Output Shape (per row)

```json
{
  "search_term": "running shoes for men",
  "campaign_id": "123456789",
  "campaign_name": "Brand Search",
  "ad_group_id": "987654321",
  "ad_group_name": "Footwear",
  "match_source": "standard_search|pmax",
  "match_type": "BROAD|PHRASE|EXACT|UNKNOWN",
  "targeting_status": "ADDED|EXCLUDED|NONE",
  "impressions": 1200,
  "clicks": 45,
  "cost": {"amount": 67.50, "currency_code": "RON", "formatted": "lei 67.50"},
  "conversions": 3,
  "conversions_value": {"amount": 450.00, "currency_code": "RON", "formatted": "lei 450.00"},
  "roas": 6.67,
  "cpa": {"amount": 22.50, "currency_code": "RON", "formatted": "lei 22.50"},
  "ctr": 3.75,
  "avg_cpc": {"amount": 1.50, "currency_code": "RON", "formatted": "lei 1.50"}
}
```

---

## Planned Signals

### Negative Keyword Candidates
- Search term with clicks > threshold AND conversions == 0 AND cost > threshold
- severity: warning
- recommendation: "Consider adding as negative keyword — review and approve before applying."
- No auto-apply. No mutation endpoint.

### Expansion Opportunities
- Search term with high conversions/ROAS not yet in a keyword list
- severity: info
- recommendation: "Consider adding as exact-match keyword in a tightly-themed ad group."

### Brand Protection
- Competitor brand name appearing in search terms
- severity: info
- recommendation: "Review brand term presence in your campaigns."

---

## Constraints

- **Read-only**: No negative keyword apply/add mutations in this module.
- **Draft flow only**: Negative keyword suggestions may be output as draft recommendations
  for human review and approval via a future Flows v3 draft step.
- **No bulk apply**: Even if draft flow is implemented, batch negative operations require
  explicit user confirmation per account.
- **PMax caveat**: PMax search terms may be partial — always surface a disclaimer.

---

## Endpoint Shape (planned)

`GET /api/connectors/google-ads/intelligence/search-terms?customer_id=&mcc_id=&days=&level=search|pmax|all`

Response includes:
- `module_id: "search_terms"`
- `source` + `live_data`
- `currency` context
- `rows` — search term rows
- `signals` — negative candidates, expansion opportunities
- `summary` — top wasted spend, top converters
- `warnings` — PMax caveat if pmax rows included
