# Flows v2 Approval + Dry Run — Pre-Implementation Audit
**Date**: 2026-05-02  
**Branch**: feature/flows-approval-dry-run-2026-05-02  
**Base**: f39946b (feat: draft mode gate)

---

## Current `flow_drafts` Schema

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
    status TEXT NOT NULL DEFAULT 'draft',          -- draft | promoted
    safety_level TEXT NOT NULL DEFAULT 'draft_only',
    created_by_agent_slug TEXT,
    source TEXT DEFAULT 'chat_generate_flow',
    promoted_flow_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
)
```

---

## Current `flows` Schema

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

**Note**: `flows` table has no `status`, `safety`, or `approval` columns. Safety metadata lives inside `flow_json`.

---

## Current `executions` Schema

Created lazily inside `orchestrator_execute()`:
```sql
CREATE TABLE IF NOT EXISTS executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flow_id INTEGER,
    user_id INTEGER NOT NULL,
    client_id INTEGER,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    status TEXT NOT NULL,
    steps_json TEXT NOT NULL
)
```

Also `flow_executions` (legacy, pre-trace):
```sql
CREATE TABLE IF NOT EXISTS flow_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    client_id INTEGER,
    flow_name TEXT,
    nodes_count INTEGER,
    steps_count INTEGER,
    elapsed_ms REAL,
    status TEXT,
    result_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

Neither table has `execution_type` or `dry_run` column. Must add idempotent migration.

---

## Current Promote Behavior

`POST /api/flows/drafts/<id>/promote`:
- Inserts into `flows` table with `category='Draft Promoted'`
- Sets `flow_drafts.status = 'promoted'`
- Returns `flow_id`
- Does NOT update `flow_json` to add `safety.mode = 'promoted_safe'`
- **Gap**: Promoted flow retains `draft_v1` version and `safety.mode = 'draft_only'` from original draft JSON

**Risk**: Promoted flow currently still has `safety.mode = 'draft_only'` in `flow_json`, which means `orchestrator_execute` would block it too.

**Fix needed**: Promote endpoint must set `safety.mode = 'promoted_safe'` in `flow_json` before storing.

---

## Current Execute Behavior

`POST /api/orchestrator/execute`:
- Checks `flow.safety.mode == 'draft_only'` → blocks with `draft_not_executable`
- Checks client scope
- Simulates execution (no real external calls in test mode)
- Stores in both `executions` and `flow_executions` tables

**Addition needed**:
- If promoted flow has `safety.requires_human_approval = true` and no approved `dry_run` approval → block with `approval_required`
- Block external connector actions unless `external_actions_enabled = true` (never in v2)

---

## Current UI Run Behavior

`window.runFlow()` in orchestrator.html:
- Patched in v1 to block if `window._activeDraftMode == true` → shows toast warning
- Otherwise calls original `runFlow`

**Addition needed**:
- If promoted flow loaded with `?flow_id=<id>`, check approval status
- Show approval banner if `requires_human_approval`
- Dry Run button → calls `/api/orchestrator/dry-run`

---

## Where Approval Should Attach

- Approval is keyed to `(user_id, client_id, flow_id, approval_scope)`
- Draft flows: approval gates promote, but in v2 we just block dry-run/execute
- Promoted flows: approval gates dry-run
- No approval needed for loading/viewing; only for running
- `approval_scope` values for v2: `dry_run` only (manual_run schema allowed but not wired)

---

## Dry-Run Risk Areas

1. **No external HTTP** — must patch/skip all connector HTTP calls
2. **No LLM calls** — agent nodes must be simulated deterministically
3. **DB mutation** — dry-run trace must be stored with `execution_type='dry_run'` to distinguish from real runs
4. **Error propagation** — dry-run exceptions must not affect production state
5. **Safety guard preservation** — `draft_not_executable` guard must not be bypassed by dry-run

---

## Minimal Implementation Plan

1. `database.py` — add `ensure_flow_approvals_table(conn)` (idempotent DDL)
2. `database.py` — add `ensure_execution_type_column(conn)` (idempotent ALTER TABLE)
3. `app.py` — fix promote: update `flow_json.safety.mode = 'promoted_safe'`
4. `app.py` — add 4 approval endpoints
5. `app.py` — add `POST /api/orchestrator/dry-run`
6. `app.py` — add approval guard in `orchestrator_execute()` for promoted flows
7. `orchestrator.html` — approval banner + Dry Run button
8. `test_flows_approval_dry_run.py` — 14 tests
