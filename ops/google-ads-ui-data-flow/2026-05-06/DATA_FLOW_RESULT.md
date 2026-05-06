# Google Ads UI Data Flow Result

Date: 2026-05-06

## What Was Broken

- The visible date selector was tied to Campaigns and called `gadsLoadAccount()`, so changing the date could reload Overview instead of the active panel.
- Reports/Intelligence had a separate date selector and did not share the same state as Campaigns.
- Loaders built account/date params independently.
- Several panels rendered source but not a consistent combination of source, live/non-live status, date range, currency, and warnings.
- Report/module output could remain stale after changing account or date range.

## Fixed

- Added central Google Ads UI state:
  - `customerId`
  - `managerCustomerId`
  - `accountName`
  - `currencyCode`
  - `timezone`
  - `days`
  - `dateRange`
  - `activeTab`
  - `connectedLive`
- Added shared helpers:
  - `gadsGetDateParams()`
  - `gadsGetAccountParams()`
  - `gadsSyncDateControls()`
  - `gadsReloadActiveTab()`
  - `gadsRenderDataMeta(container, response)`
- Moved `#gadsDateRange` to the shared Google Ads account context bar.
- Synced `#gadsDateRange` and `#gadsReportDateRange`.
- Changing date range clears stale outputs and reloads only the active panel.
- Changing selected client account clears stale outputs and reloads the active panel.
- Loaders now require a selected client account before calling Google Ads data endpoints.

## Tabs And Loaders Updated

- Overview: sends selected `customer_id`, `mcc_id`, `days`, `date_range`.
- Campaigns: sends selected `customer_id`, compatibility `account_id`, `mcc_id`, `days`, `date_range`.
- Diagnostics: sends selected `customer_id`, `mcc_id`, `days`, `date_range`.
- AI Brief: sends selected `customer_id`, `mcc_id`, `days`, `date_range`.
- Account Health: sends selected `customer_id`, `mcc_id`, `days`, `date_range`.
- Waste Finder: sends selected `customer_id`, `mcc_id`, `days`, `date_range`.
- Search Terms: sends selected `customer_id`, `mcc_id`, `days`, `date_range`.
- Report presets: send JSON `customer_id`, `manager_customer_id`, and `date_range`.

## Metadata Rendering

`gadsRenderDataMeta()` now provides shared rendering for:

- Source badge:
  - `google_ads_api`: Live
  - `cached_google_ads_api`: Cached Google Ads
  - `mock_fallback`: API Error / Fallback
  - `mock`: Mock
  - `google_ads_api_error`: API Error
- `live_data` true/false.
- Date range and days.
- Currency/native currency.
- Warnings.

Used in:

- Overview
- Campaigns
- Diagnostics
- AI Brief
- Account Health
- Waste Finder
- Search Terms
- Report presets

## Backend Changes

Minimal backend changes only:

- `/api/connectors/google-ads/campaigns` accepts `customer_id` as an alias for `account_id`.
- Campaigns, overview, diagnostics, AI brief, account-health, waste-finder, and search-terms echo `days`.
- Date range mapping is centralized server-side for supported day windows.

No OAuth, MCC validation, DB schema, or Google Ads write behavior was changed.

## Tests

Passed:

- `python3 -m py_compile backend_py/app.py backend_py/database.py backend_py/models.py backend_py/ai/__init__.py backend_py/ai/provider_policy.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_ui_data_flow.py` (`16` tests)
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_source_truth_accounts_cache.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_source_truth_search_terms.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_source_truth_campaigns.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_search_terms.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_intelligence_modules.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_report_query.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_mcc_hierarchy.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_mcc_ui_mapping.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_api_validation.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_oauth_phase1.py`
- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_google_ads_truth_mode.py`
- Core non-orchestrator tests requested in the implementation task.
- `AUTH_REQUIRED=0 DATABASE=/tmp/camarad_ui_data_flow_conversation_brief.db PYTHONPATH=backend_py:. python3 backend_py/test_conversation_brief.py`

Known pre-existing failure:

- `PYTHONPATH=backend_py:. python3 -m unittest backend_py/test_orchestrator.py`
  - `18` failures
  - `8` errors

## Deploy Recommendation

Deploy only after focused and core tests pass. This branch changes both `backend_py/app.py` and `backend_py/templates/connectors.html`, so deployment needs a separate no-surprises plan because current production template is a rollback UI while the repo template differs.
