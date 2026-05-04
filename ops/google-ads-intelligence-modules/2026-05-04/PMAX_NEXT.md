# Performance Max Intelligence Module — Next Plan

Phase: PLANNED (not implemented in Phase 2E)  
Target: Phase 2G or later  

---

## Overview

Performance Max (PMax) campaigns require separate reporting paths from standard Search/Shopping.
Standard reports (search_term_view, keyword_view) do NOT work for PMax.

---

## Reporting Resources for PMax

### 1. Campaign-level Performance
Resource: `campaign`  
Filter: `campaign.advertising_channel_type = 'PERFORMANCE_MAX'`

Fields:
- `campaign.id`, `campaign.name`, `campaign.status`
- `campaign.bidding_strategy_type`
- `metrics.impressions`, `metrics.clicks`, `metrics.cost_micros`
- `metrics.conversions`, `metrics.conversions_value`
- `metrics.ctr`

### 2. Asset Group Performance
Resource: `asset_group`

Fields:
- `asset_group.id`, `asset_group.name`, `asset_group.status`
- `asset_group.ad_strength` — POOR / GOOD / EXCELLENT / PENDING / UNKNOWN
- `campaign.id`, `campaign.name`
- `metrics.impressions`, `metrics.clicks`, `metrics.cost_micros`
- `metrics.conversions`, `metrics.conversions_value`

### 3. Asset Group Assets
Resource: `asset_group_asset`

Fields:
- `asset_group_asset.asset`, `asset_group_asset.field_type`
- `asset_group_asset.status`
- `asset_group_asset.performance_label` — UNKNOWN / PENDING / LEARNING / LOW / GOOD / BEST

Asset field types:
- HEADLINE, LONG_HEADLINE, DESCRIPTION
- MARKETING_IMAGE, SQUARE_MARKETING_IMAGE, PORTRAIT_MARKETING_IMAGE
- YOUTUBE_VIDEO
- CALL_TO_ACTION_SELECTION
- BUSINESS_NAME, LOGO

### 4. PMax Search Terms (where supported)
Resource: `campaign_search_term_view`
See SEARCH_TERMS_NEXT.md for details.

### 5. Listing Groups / Product Groups (Shopping-feed PMax)
Resource: `asset_group_listing_group_filter`
- For PMax campaigns with shopping feed attached
- Not in Phase 2E or 2F scope — deferred to Phase 2H+

---

## Planned Signals

### Asset Coverage
- Missing required asset types (no YOUTUBE_VIDEO, fewer than 5 headlines, etc.)
- severity: warning
- recommendation: "Add missing asset types to improve Ad Strength."

### Ad Strength
- Asset groups with POOR ad strength
- severity: warning
- recommendation: "Review and improve asset group ad strength."

### Low Performing Assets
- Assets with performance_label = LOW
- severity: info
- recommendation: "Consider replacing underperforming assets."

### PMax vs Search Cost Share
- PMax consumes > X% of budget with no ROAS signal
- severity: warning

---

## Constraints

- **No mutations**: Asset additions/removals are read-only analysis only.
- **PMax search term caveat**: `campaign_search_term_view` may return partial data.
  Always surface a disclaimer: "PMax search term visibility may be limited."
- **Asset performance lag**: New assets may show PENDING or LEARNING — skip signals
  for assets with fewer than 7 days of data.
- **Listing groups**: Deferred. Product-level attribution requires Shopping feed access.

---

## Endpoint Shape (planned)

`GET /api/connectors/google-ads/intelligence/performance-max?customer_id=&mcc_id=&days=`

Response includes:
- `module_id: "performance_max"`
- `source` + `live_data`
- `currency` context
- `asset_groups` — asset group performance rows
- `asset_coverage` — per-asset-group asset coverage summary
- `signals` — coverage gaps, ad strength alerts, low performers
- `warnings` — PMax caveat, data lag notice
