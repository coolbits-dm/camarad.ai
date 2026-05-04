# Audiences & Targeting Intelligence Module — Next Plan

Phase: PLANNED / LIMITED (not implemented in Phase 2E)  
Status: planned_limited — AudienceInsightsService may require allowlist  
Target: Phase 2H or later (after capability check)  

---

## Why "planned_limited"?

Google Ads **AudienceInsightsService** requires explicit API access and may be
allowlisted/restricted per developer token. The module must capability-check
before attempting to call it and must never promise full audience insights
to all users.

Fallback audience reporting via `campaign_audience_view` or `ad_group_audience_view`
may be available without allowlist restrictions and is the preferred starting point.

---

## Reporting Resources (Available Without Allowlist)

### 1. Campaign Audience View
Resource: `campaign_audience_view`

Fields:
- `campaign_criterion.criterion_id`
- `campaign_criterion.type` — USER_LIST / USER_INTEREST / LIFE_EVENT / DETAILED_DEMOGRAPHIC
- `campaign_criterion.bid_modifier`
- `campaign_criterion.status`
- `campaign.id`, `campaign.name`
- `metrics.impressions`, `metrics.clicks`, `metrics.cost_micros`
- `metrics.conversions`, `metrics.conversions_value`

### 2. Ad Group Audience View
Resource: `ad_group_audience_view`

Fields:
- `ad_group_criterion.criterion_id`, `ad_group_criterion.status`
- `ad_group_criterion.bid_modifier`
- `ad_group.id`, `ad_group.name`
- `campaign.id`, `campaign.name`
- `user_list.id`, `user_list.name`, `user_list.membership_status`
- `metrics.impressions`, `metrics.clicks`, `metrics.cost_micros`
- `metrics.conversions`, `metrics.conversions_value`

### 3. User Lists (Remarketing Lists)
Resource: `user_list`

Fields:
- `user_list.id`, `user_list.name`, `user_list.type`
- `user_list.membership_status` — OPEN / CLOSED
- `user_list.size_range_for_search`
- `user_list.eligible_for_search`, `user_list.eligible_for_display`
- `user_list.integration_code` (if exists)

---

## AudienceInsightsService (Requires Capability Check)

This service provides:
- Audience composition insights
- Reach estimates for audience segments
- Top interest categories

**Before calling AudienceInsightsService:**
1. Check if `developer_token` has beta/allowlist access
2. Attempt a lightweight probe call
3. If 403 / PERMISSION_DENIED → mark module as `capability_unavailable`
4. Never show capability_unavailable as a user error — show "Audience Insights not available for this account"

---

## Planned Signals

### Small Remarketing List
- User list size < 1000 (too small for targeting)
- severity: warning
- recommendation: "Remarketing list too small. Expand to at least 1,000 members to enable targeting."

### Excluded Audience with Conversions
- Audience segment excluded from a campaign with historical conversion value
- severity: info
- recommendation: "Review excluded audience — this segment had conversions."

### No Remarketing Lists in Use
- Account has spend but no remarketing audiences applied to any campaign
- severity: info
- recommendation: "Consider adding remarketing lists to relevant campaigns."

---

## Constraints

- **No mutations**: No audience creation, no list modification.
- **Capability gate**: Always check AudienceInsightsService capability first.
- **Do not promise**: Module description must note "AudienceInsightsService may require allowlist."
- **No synthetic data**: If audience data not available, return empty rows + warning.

---

## Endpoint Shape (planned)

`GET /api/connectors/google-ads/intelligence/audiences?customer_id=&mcc_id=&days=`

Response includes:
- `module_id: "audiences_targeting"`
- `source` + `live_data`
- `currency` context
- `remarketing_lists` — user list summary (if available)
- `campaign_audiences` — campaign audience view rows (if available)
- `audience_insights_available: true|false` — capability check result
- `signals`
- `warnings` — AudienceInsightsService availability disclaimer
