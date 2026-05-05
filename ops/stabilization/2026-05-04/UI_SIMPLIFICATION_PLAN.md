# Google Ads UI Simplification Plan

## Goal

Simplify the Google Ads connector without adding backend product features, deployment changes, or Google Ads API calls.

## Primary Tabs

Keep exactly five visible top-level Google Ads tabs:

1. Overview
2. Campaigns
3. Reports
4. AI Brief
5. Settings

Changes:

- Remove Diagnostics as a visible top-level tab.
- Rename Intelligence to Reports.
- Keep the Diagnostics DOM/functionality available, but route it through Overview/Reports context rather than a primary tab.
- Keep Test API, Budget Pacing, and Asset Generator out of the primary tab list.

## Reports

Reports should remain the home for focused read-only modules.

Primary live/partial module cards:

- Account Health
- Waste Finder
- ROAS Leaders
- Conv. Efficiency
- Search Terms

Planned modules:

- PMax
- Budget
- Assets
- Audiences

Planned modules should be compact and disabled so they do not dominate the UI.

## Diagnostics

Diagnostics should not be a primary tab.

Implementation approach:

- Add a compact Health / Diagnostics strip under Overview.
- Keep the existing diagnostics pane hidden for compatibility.
- Make Reports clearly include Account Health as the diagnostics-oriented module.

## Advanced / Legacy

Move these behind Advanced / Legacy in Settings:

- Test API
- Budget Pacing old view
- Asset Generator old view

Do not remove functionality. Keep hidden panes callable from the Advanced section.

## Source Badges

Normalize source labels:

- `google_ads_api` -> Live
- `mock_fallback` -> API Error / Fallback
- `mock` -> Mock
- `mock_demo` -> Mock
- `planned` -> Planned
- unknown/error -> Unknown/Error

Use a single helper so labels stay consistent.

## Currency Badges And Formatting

Normalize currency labels:

- known account currency -> `Native: RON`, `Native: EUR`, etc.
- unknown -> `Currency unknown`
- unsupported conversion -> `Conversion unavailable`

Currency display rules:

- Do not guess USD.
- Do not use hardcoded `$` as the default in Google Ads UI.
- Use account/report native currency where present.
- If currency is unknown, show a number without pretending it is USD and show the currency badge.

## Account Selector

Keep the same flow but compact the copy and layout:

```text
Direct Access -> Manager/MCC -> Client Account
```

Label copy:

- Direct Access: OAuth-visible accounts
- Manager/MCC: Manager context
- Client Account: Reporting account

## Tests

Add `backend_py/test_google_ads_ui_simplification.py` with checks for:

- five primary tabs only
- no Diagnostics primary tab
- Advanced / Legacy exists
- source badge labels
- currency helper and no hardcoded Google Ads default `$`
- planned modules disabled
- Reports includes live/partial module cards
- Test API not primary
- compact account selector copy
- no mutation/write UI

## Commit Policy

- Do not stage `backend_py/app.py` for this UI-only pass.
- Do not commit Marketing Audit/PPC-Agent backend endpoints here.
- Commit only if tests pass, except known `test_orchestrator.py` failures that are documented.
