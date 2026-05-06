# Google Ads UI Data Flow Audit

Date: 2026-05-06

## Scope

Audited:

- `backend_py/templates/connectors.html`
- `backend_py/app.py`
- Google Ads UI state, account selectors, date controls, tab loaders, and source/currency/date rendering.

Production was not changed during this audit/fix branch.

## Findings

The panel had working live API paths, but UI state was split:

- Campaigns used `#gadsDateRange` as a days selector.
- Reports and Intelligence modules used `#gadsReportDateRange` as a GAQL `date_range` selector.
- Overview, Campaigns, Diagnostics, AI Brief, report presets, and Intelligence modules each built request params independently.
- Changing date range called `gadsLoadAccount()`, which reset account state and always loaded Overview rather than reloading the active panel.
- Source/currency/date metadata was rendered inconsistently. Some panels showed source, but not date or currency; some source warnings were panel-specific.
- Stale output could remain in report/module panels after account or date changes.

## Account Selector Flow

| UI area | Current behavior | Audit result |
| --- | --- | --- |
| Direct Access | `gadsOnDirectAccessChange()` prefills Manager/MCC input | OK, but it does not itself select the reporting account |
| Manager/MCC | `gadsLoadMccHierarchy()` POSTs to `/api/connectors/google-ads/mcc/hierarchy` | OK, read-only fresh API path |
| Client Account | `gadsLoadAccount()` sets selected client and reloads data | Needed central state and active-tab reload |

## Date Selector Flow

| Control | Previous behavior | Fixed behavior |
| --- | --- | --- |
| `#gadsDateRange` | Lived in Campaigns tab, called `gadsLoadAccount()` | Moved to shared Google Ads context bar, updates central `gadsState.days/dateRange` |
| `#gadsReportDateRange` | Reports-only selector, not synced with Campaigns selector | Synced through `gadsGetDateParams()` and `gadsSyncDateControls()` |
| Date change | Reloaded Overview via account reload | Clears stale UI and reloads only active panel |

## Tab Loader Matrix

| Tab / Module | JS loader | Endpoint | Sends customer_id | Sends MCC | Sends days/date_range | Source rendered | Currency rendered | Stale risk after fix |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Overview | `gadsLoadOverview()` | `/api/connectors/google-ads/overview` | Yes | `mcc_id` | `days`, `date_range` | `gadsRenderDataMeta()` | Yes | Low |
| Campaigns | `gadsLoadCampaigns()` | `/api/connectors/google-ads/campaigns` | Yes, plus `account_id` compatibility | `mcc_id` | `days`, `date_range` | `gadsRenderDataMeta()` | Yes | Low |
| Diagnostics | `gadsLoadDiagnostics()` | `/api/connectors/google-ads/diagnostics` | Yes | `mcc_id` | `days`, `date_range` | `gadsRenderDataMeta()` | Yes | Low |
| AI Brief | `gadsLoadAiBrief()` | `/api/connectors/google-ads/ai-brief` | Yes | `mcc_id` | `days`, `date_range` | `gadsRenderDataMeta()` | Yes | Low |
| Account Health | `gadsOpenModule('account_health')` | `/api/connectors/google-ads/intelligence/account-health` | Yes | `mcc_id` | `days`, `date_range` | `gadsRenderDataMeta()` | Yes | Low |
| Waste Finder | `gadsOpenModule('waste_finder')` | `/api/connectors/google-ads/intelligence/waste-finder` | Yes | `mcc_id` | `days`, `date_range` | `gadsRenderDataMeta()` | Yes | Low |
| Search Terms | `gadsOpenModule('search_terms')` | `/api/connectors/google-ads/intelligence/search-terms` | Yes | `mcc_id` | `days`, `date_range` | `gadsRenderDataMeta()` | Yes | Low |
| Report presets | `gadsRunPreset()` | `/api/connectors/google-ads/report/query` | JSON `customer_id` | JSON `manager_customer_id` | JSON `date_range` | `gadsRenderDataMeta()` | Yes | Low |

## Backend Echo Check

Before this branch, endpoints generally used `days` internally but did not always echo it. This branch adds minimal `days` echoing to:

- `/api/connectors/google-ads/campaigns`
- `/api/connectors/google-ads/overview`
- `/api/connectors/google-ads/diagnostics`
- `/api/connectors/google-ads/ai-brief`
- `/api/connectors/google-ads/intelligence/account-health`
- `/api/connectors/google-ads/intelligence/waste-finder`
- `/api/connectors/google-ads/intelligence/search-terms`

`/api/connectors/google-ads/report/query` already echoes `date_range` in the response and query plan.

## Risk Notes

- The repo template differs from current production rollback UI. This branch modifies repo template only and does not touch `/opt/camarad`.
- No Google Ads mutation APIs were added.
- No OAuth/MCC validation behavior was changed.
- PMax and AI Ask remain unimplemented.
