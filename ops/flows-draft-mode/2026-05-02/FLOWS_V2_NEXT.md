# Flows v2 — Next Steps

**Status**: Planning (not started)  
**Depends on**: `b518a2a` (draft mode gate) deployed and stable in production

---

## 1. Human Approval Layer

**Goal**: Allow a manager/admin to review drafts before promotion.

- Add `status='pending_approval'` between `draft` and `promoted`
- Add `POST /api/flows/drafts/<id>/request_approval` — sets status, stores approver_user_id
- Add `POST /api/flows/drafts/<id>/approve` — sets status=approved (approver only)
- Add `POST /api/flows/drafts/<id>/reject` — sets status=rejected, stores reason
- UI: draft banner shows approval state; promote button only active when `approved`
- Optional: notify approver via in-app notification or email

---

## 2. Connector Dry-Run Adapters

**Goal**: Let a draft "simulate" a connector read without real write/mutation.

- Add `dry_run: true` flag to connector nodes
- Implement per-connector dry-run handlers (GA4: return fixture data, Google Ads: return last known snapshot)
- Gate all writes behind `if not node.get("config", {}).get("dry_run"):`
- Add `POST /api/flows/drafts/<id>/dry_run` — runs flow in sandbox, returns simulated output
- No CT spend during dry run (mock LLM too, or use minimal prompt)

---

## 3. Agent Blueprint Mapping

**Goal**: Draft generator currently uses keyword→slug heuristics. Replace with a catalog-driven approach.

- Create `AGENT_DRAFT_BLUEPRINTS` dict in `app.py` (or separate `blueprints.py`)
- Each blueprint: `{slug, display_name, input_connectors: [...], output_format, sample_prompt_keywords: [...]}`
- Draft generator picks blueprint by keyword overlap with prompt → richer node configs
- Blueprints can be loaded from DB or YAML config (configurable)

---

## 4. Conversation → Draft Integration

**Goal**: Allow a chat message to generate a draft in-context without navigating away.

- Chat sidebar: "Create Flow from this conversation" button
- Sends `conversation_id` to `/api/flows/drafts/generate`
- Draft is scoped to conversation + client
- Assistant can propose flow outline in chat message, user clicks "Save as Draft"

---

## 5. Draft Version History

**Goal**: Allow iterative editing of a draft (non-destructive).

- Add `parent_draft_id` column to `flow_drafts`
- Each edit creates a new row linked to the original
- UI shows version list, allows rollback
- Promote always uses latest non-rejected version

---

## 6. UI Polish

- [ ] Draft list page at `/orchestrator/drafts`
- [ ] Filter by client, agent type, date
- [ ] Draft name is editable before promotion
- [ ] Preview connector inputs before promotion
- [ ] Diff view between draft nodes and last promoted version
