# Flows Draft Mode — Result Report
**Date**: 2026-05-02  
**Branch**: `feature/flows-draft-mode-2026-05-02`  
**Commit**: `b518a2a`  
**Status**: ✅ All 14 tests pass. Ready for deploy on request.

---

## What Was Built

### New API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/flows/drafts/generate` | Generate a draft flow from a text prompt |
| GET | `/api/flows/drafts` | List current user's drafts |
| GET | `/api/flows/drafts/<id>` | Fetch single draft (ownership enforced) |
| POST | `/api/flows/drafts/<id>/promote` | Promote draft to saved flow (no execution) |

### DB Changes

- New table: `flow_drafts` in `backend_py/database.py`
- Created via `ensure_flow_drafts_table(conn)` — idempotent, safe on existing DB
- Columns: `id, user_id, client_id, conversation_id, source_message_id, name, description, prompt, flow_json, status, safety_level, created_by_agent_slug, source, promoted_flow_id, created_at, updated_at`
- Indexes on `(user_id)` and `(user_id, client_id)`

### Draft Generator

- `_generate_flow_draft_from_prompt()` in `app.py` — pure deterministic keyword heuristics
- **Zero LLM calls** — no CT spend, no provider dependency
- **Zero external HTTP calls** — no connector API calls during generation
- Domains recognized: ppc, analytics/ga4, gmail, docs, hubspot, salesforce, seo/gsc, social/meta
- Outputs: `trigger → [connector(s)] → agent → output` node graph
- Every generated draft has:
  - `draft: true`
  - `version: "draft_v1"`
  - `safety: {mode: "draft_only", requires_human_approval: true, external_actions_enabled: false}`
  - Connector nodes: `config.external_action: false, config.draft_placeholder: true`

### Safety Guard

Added to `orchestrator_execute()` in `app.py`:
```python
if flow.get("safety", {}).get("mode") == "draft_only":
    return jsonify({"success": False, "error": "draft_not_executable", ...}), 400
```
- Fires **before** any CT spend or LLM call
- Returns `400 draft_not_executable`
- Non-draft flows are completely unaffected

### UI Changes

**chat.html** — `composeFlowFromPrompt()` rewired:
- Was: POST `/api/orchestrator/compose` → LLM call → auto-navigate to Orchestrator
- Now: POST `/api/flows/drafts/generate` → toast with link → user navigates when ready

**orchestrator.html**:
- Draft mode banner (fixed, dismissible) — shows when `?draft_id=<id>` is in URL
- `?draft_id=` URL handler — loads draft nodes/connections, shows banner
- `runFlow` is patched: draft mode blocks execution with warning toast
- `promoteDraftToFlow()` — POSTs promote, then loads saved flow
- `clearDraftMode()` — dismisses banner

---

## Tests

File: `backend_py/test_flows_draft_mode.py` — 14 tests, all pass.

```
test_connector_nodes_are_draft_placeholders         ok
test_draft_has_safety_metadata                      ok
test_execute_non_draft_flow_not_blocked             ok
test_execute_rejects_draft_only_flow                ok
test_generate_empty_prompt_returns_400              ok
test_generate_generic_prompt_creates_draft          ok
test_generate_makes_no_external_calls               ok
test_generate_missing_prompt_returns_400            ok
test_generate_ppc_prompt_includes_ppc_nodes         ok
test_generate_response_has_orchestrator_url         ok
test_get_draft_by_id                                ok
test_get_draft_other_user_returns_404               ok
test_list_drafts_scoped_to_user                     ok
test_promote_creates_flow_and_does_not_execute      ok
```

Pre-existing `test_orchestrator` failures (12 pre-date this branch, confirmed via `git stash` baseline) — unchanged.

---

## What Is Explicitly Disabled

- No autonomous flow execution
- No real connector API calls from draft generation
- No LLM usage during draft generation
- Draft flows cannot be executed via Orchestrator without promotion
- Promotion saves to DB only — does not run the flow

---

## Deploy Recommendation

1. Run `ensure_flow_drafts_table(conn)` on startup — already wired in `init_db()` path
2. No migration needed — idempotent DDL
3. No environment variable changes required
4. No MWR / Vacante routes affected
5. Controlled deploy: `pm2 restart camarad --update-env` after copying files
