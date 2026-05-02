# Flows Draft Mode Audit
**Date**: 2026-05-02  
**Branch**: feature/flows-draft-mode-2026-05-02  
**Base**: 54f2231 (feature/chat-runtime-hardening-2026-05-02)

---

## 1. Existing Orchestrator Routes

| Method | Path | Handler | Status |
|--------|------|---------|--------|
| GET | `/orchestrator` | `orchestrator()` | ✅ live |
| GET | `/api/orchestrator/flows` | `orchestrator_flow_discovery()` | ✅ live |
| GET | `/api/orchestrator/templates` | `orchestrator_templates()` | ✅ live |
| POST | `/api/orchestrator/compose` | `orchestrator_compose()` | ✅ live |
| POST | `/api/orchestrator/route` | `orchestrator_route()` | ✅ live |
| GET | `/api/orchestrator/agent-brief/<slug>` | `orchestrator_agent_brief()` | ✅ live |
| POST | `/api/orchestrator/execute` | `orchestrator_execute()` | ✅ live |
| GET | `/api/orchestrator/history` | `orchestrator_history()` | ✅ live |
| GET | `/api/orchestrator/history/<id>` | `orchestrator_history_detail()` | ✅ live |

## 2. Existing /api/flows Routes

| Method | Path | Handler |
|--------|------|---------|
| GET | `/api/flows` | `get_flows()` |
| POST | `/api/flows` | `post_flow()` |
| GET | `/api/flows/<id>` | `get_flow()` |
| DELETE | `/api/flows/<id>` | `delete_flow()` |
| PUT | `/api/flows/<id>` | `update_flow()` |
| POST | `/api/flows/<id>/duplicate` | `duplicate_flow()` |
| GET | `/api/flows/<id>/patches` | `get_flow_patch_proposals()` |
| GET | `/api/flows/<id>/patches/<pid>` | `get_flow_patch_proposal()` |
| POST | `/api/flows/<id>/patches/<pid>/request_apply` | `request_apply_flow_patch()` |
| GET | `/api/flows/templates` | `get_flow_templates()` |

**Missing**: No `/api/flows/drafts/*` routes exist yet.

## 3. Existing `flows` Table Schema

```sql
CREATE TABLE IF NOT EXISTS flows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL DEFAULT 'Untitled Flow',
    user_id INTEGER DEFAULT 1,
    client_id INTEGER,
    flow_json TEXT NOT NULL,
    thumbnail TEXT,
    category TEXT DEFAULT 'Uncategorized',
    description TEXT DEFAULT '',
    is_template INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    is_active INTEGER DEFAULT 1
)
```

**Verdict**: `flows` has no `status` field, no `draft` flag, no `safety` metadata, no `prompt` field, no `source` field. It conflates templates and user flows with `is_template`. It is NOT suitable for draft flows without schema additions that would risk breaking existing code. Use a **separate `flow_drafts` table**.

## 4. Existing Execution Table

Flow executions are stored in `flow_executions` table (created inside `orchestrator_execute()`). Schema inspected at runtime. Does not need to change for draft mode — drafts are blocked before reaching this table.

## 5. Generate Flow Button — Existing JS Path

**File**: `backend_py/templates/chat.html` line 113  
**Handler**: `composeFlowFromPrompt()` (line ~486)

Current behavior:
1. Takes `userInput.value.trim()` as prompt
2. POSTs to `/api/orchestrator/compose`
3. On success, navigates to `/orchestrator?flow_id=<id>` immediately

**Problem**: 
- `/api/orchestrator/compose` calls `get_llm_response()` — spends real tokens, costs CT
- Stores result directly in `flows` table (no draft concept)
- Redirects immediately without user review
- Flow appears in Orchestrator as a saved flow (not marked draft)
- User can immediately click Run without review

**Plan**: Rewire to `/api/flows/drafts/generate` instead. New endpoint is deterministic (no LLM), free, zero CT cost, stores in `flow_drafts`. Shows toast + link without navigating.

## 6. Orchestrator URL Load

**File**: `backend_py/templates/orchestrator.html` line 3638-3648  
Reads `?flow_id=` from URL → calls `loadFlowFromDb(id)` → fetches `/api/flows/<id>`.

**Plan**: Add `?draft_id=` handling that fetches `/api/flows/drafts/<id>` and loads the same way, plus renders a visible "Draft Mode" banner.

## 7. Run Flow Behavior

`window.runFlow()` in orchestrator.html line 1857:
1. Builds `flowData` from canvas nodes
2. POSTs CT spend to `/api/user/spend`
3. POSTs to `/api/orchestrator/execute`

**Plan**: Add draft guard check in `runFlow()` JS — if `window._activeDraftMode` is true, block run with a modal/toast. Also add server-side guard in `/api/orchestrator/execute` for flows with `safety.mode == 'draft_only'`.

## 8. Risk Areas

| Risk | Level | Notes |
|------|-------|-------|
| Modifying `flows` table schema | Medium | Has active rows in prod; use separate table instead |
| Modifying `orchestrator_execute()` | Medium | Guard is additive-only (early return for draft flows) |
| Rewiring `composeFlowFromPrompt()` | Low | Old endpoint preserved, new endpoint is new path |
| JS draft badge in orchestrator | Low | Additive JS, doesn't remove any node |
| `flow_drafts` table creation | Low | Idempotent CREATE TABLE IF NOT EXISTS |

## 9. Proposed Minimal Implementation

### A. `flow_drafts` table (new, idempotent)
```sql
CREATE TABLE IF NOT EXISTS flow_drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    client_id INTEGER,
    conversation_id INTEGER,
    source_message_id INTEGER,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    prompt TEXT NOT NULL,
    flow_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    safety_level TEXT NOT NULL DEFAULT 'draft_only',
    created_by_agent_slug TEXT,
    source TEXT DEFAULT 'chat_generate_flow',
    promoted_flow_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
)
```

### B. New API endpoints
- `POST /api/flows/drafts/generate` — deterministic generator, no LLM
- `GET /api/flows/drafts` — list user's drafts
- `GET /api/flows/drafts/<id>` — get single draft
- `POST /api/flows/drafts/<id>/promote` — save draft to flows table, mark `promoted`

### C. Draft generator — heuristic-only
Keyword detection for: ppc, report, gmail, docs, analytics, hubspot, linkedin, salesforce → include relevant connector placeholder nodes. No external calls.

### D. chat.html — rewire `composeFlowFromPrompt()`
Hit `/api/flows/drafts/generate` instead of `/api/orchestrator/compose`. Show toast with link. No auto-navigate.

### E. orchestrator.html
- Handle `?draft_id=<n>` URL param → fetch `/api/flows/drafts/<n>` → load into canvas
- Show "Draft Mode" banner when draft is loaded
- Block Run while `window._activeDraftMode === true`

### F. execute guard (server-side)
In `orchestrator_execute()`: if `flow.get('safety', {}).get('mode') == 'draft_only'`, return 400 `draft_not_executable`.

### G. Tests (10 tests in `test_flows_draft_mode.py`)
