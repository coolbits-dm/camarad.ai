# Commit Split Plan

Branch: `chore/port-live-runtime-parity-2026-04-28`

## A. Camarad Runtime Parity Code

Stage for runtime parity commit:

- `backend_py/app.py`
- `backend_py/models.py`
- `backend_py/rag_store.py`
- `backend_py/requirements.txt`

Reason:

- live `app.py` is the runtime parity base
- live app imports registry helpers from `models.py`
- live app imports `rag_store.py`
- live requirements include optional runtime dependencies used by live code

## B. MWR/Vacante Co-Hosted Legacy Module Files

Stage for runtime parity commit, but document as non-Camarad product boundary:

- `backend_py/templates/_vacante/*.html`
- `backend_py/templates/mwr.html`
- `backend_py/templates/mwr_privacy.html`
- `backend_py/templates/mwr_terms.html`
- `backend_py/templates/afla-mai-mult.html`
- `backend_py/templates/intrebari-frecvente.html`
- `backend_py/templates/multumesc.html`
- `backend_py/static/images/mwr/*`
- `backend_py/test_mwr_landing.py`
- `backend_py/test_vacante_flow.py`

Reason:

- required to preserve current live behavior
- not a Camarad product feature
- future task should extract to cblm-level or dedicated runtime/module

## C. Conversation Brief Preservation

Stage for runtime parity commit:

- `backend_py/database.py`
- `backend_py/templates/base.html`
- `backend_py/templates/chat.html`
- `backend_py/templates/chat_home.html`
- `backend_py/test_conversation_brief.py`

Reason:

- repo-only Conversation Brief must survive the live-based `app.py` port
- tests confirm the route and UI still work

## D. Reconciliation Docs / Reports

Stage only small docs needed to explain the runtime parity commit:

- `ops/reconciliation/live-vs-repo-2026-04-28/PRODUCT_BOUNDARY_NOTE.md`
- `ops/reconciliation/live-vs-repo-2026-04-28/COMMIT_SPLIT_PLAN.md`
- `ops/reconciliation/live-vs-repo-2026-04-28/STAGED_RUNTIME_PARITY_FILES.txt`
- `ops/reconciliation/live-vs-repo-2026-04-28/TEST_RESULTS_BEFORE_RUNTIME_COMMIT.md`
- `ops/reconciliation/live-vs-repo-2026-04-28/SECRET_SCAN_STAGED_RUNTIME.md`

Keep larger reconciliation reports local unless a separate docs commit is
needed.

## E. Unrelated Old Drift

Do not stage for runtime parity commit:

- `.gitignore`
- `README.md`
- `CURRENT_SPRINT.md`
- `ROADMAP.md`
- `WORK_QUEUE.md`
- `docs/PRODUCT_BRIEF.md`
- `ops/CLAW_OPERATING_PLAN.md`
- `backend_py/opt/...`

Reason:

- these were dirty before this split and are not required for runtime parity

## F. Should Not Commit In This Task

Do not stage:

- `.env`
- DB files
- logs
- backups
- cache directories
- virtualenvs
- token/OAuth callback artifacts
- `ops/reconciliation/live-vs-repo-2026-04-28/patches/runtime_parity_wip_before_split.patch`
- `ops/reconciliation/live-vs-repo-2026-04-28/patches/conversation_brief.patch`
- `ops/reconciliation/live-vs-repo-2026-04-28/patches/conversation_brief_snapshot/`

AI Provider Policy remains out of scope for this task:

- `backend_py/ai/*`
- `backend_py/test_ai_provider_policy.py`
- `docs/AI_PROVIDERS.md`
- `.env.example`

Reason:

- AI Provider Policy is a validated patch source but must be replayed later as a
  separate small change
