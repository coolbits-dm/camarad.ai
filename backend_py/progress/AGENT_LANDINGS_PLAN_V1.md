# Agent Landings Plan V1

Date: 2026-02-18
Owner: codex
Status: planned (no rush execution)

## Objective
Create dedicated landing pages per core agent (Personal, PPC, CEO, DevOps) to support paid/organic acquisition and route users directly into the correct chat after OAuth.

Phase 0 scope is content + structure + traceability. Heavy design/graphics iteration is explicitly out of scope for now.

## Constraints
- UI-only scope for this block.
- No auth/connectors/billing core logic changes.
- Keep existing main landing behavior unless explicitly enabled.
- Preserve route compatibility (no mandatory `/app` prefix).

## Route Plan
Primary dynamic route:
- `/agents/<agent_id>`

Optional marketing aliases (301 to canonical `/agents/<agent_id>`):
- `/personal-ai` -> `/agents/personal`
- `/ppc-ai` -> `/agents/ppc`
- `/ceo-ai` -> `/agents/ceo`
- `/devops-ai` -> `/agents/devops`

## Agent Mapping (proposed)
Adjustable to real workspace slugs if needed.

- `personal`:
  - target chat: `/chat/personal/life-coach`
  - keywords: `personal ai assistant`, `ai life coach`, `daily planning ai`
- `ppc`:
  - target chat: `/chat/agency/ppc-specialist`
  - keywords: `ppc ai agent`, `google ads ai assistant`, `roas optimization ai`
- `ceo`:
  - target chat: `/chat/business/ceo`
  - keywords: `ceo ai agent`, `executive ai assistant`, `strategy ai copilot`
- `devops`:
  - target chat: `/chat/development/devops`
  - keywords: `devops ai agent`, `incident response ai`, `sre ai assistant`

## Default Page Structure (phase 0)
Single shared template `templates/agent_landing.html` rendered from registry config:

1. Hero
   - title
   - tagline
   - single CTA: `Start with Google`
2. Value bullets (3-5)
3. Example prompts (3)
4. "How it works" (short, 3 steps)
5. Proof/expectation note
   - concise disclaimer if data is mock vs live

## CTA and Redirect Strategy
CTA target uses existing OAuth start endpoint and routes to agent-specific chat path.

Pattern:
- `/api/auth/google/start?returnTo=<target_chat_with_tracking>`

Tracking payload in `returnTo`:
- `from=agent-landing`
- `agent=<agent_id>`
- preserve inbound UTMs (`utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content`) and `gclid` when present

Example:
- `/api/auth/google/start?returnTo=/chat/agency/ppc-specialist?from=agent-landing&agent=ppc&utm_source=google&utm_campaign=ppc_ai_agent`

## Attribution and Session Persistence
On `/agents/<agent_id>`:
- capture inbound `utm_*`, `gclid`, `from`
- persist short-lived attribution context in cookie or server session for post-OAuth continuity

Minimum target:
- attribution values survive OAuth roundtrip and are visible in resulting chat URL/query and server logs.

## Observability (funnel-friendly)
Events/markers to support deterministic funnel trace:

1. `agent_landing_view`
   - observable via GET request path with query (`/agents/<id>?...`)
2. `agent_landing_cta_click`
   - observable via OAuth start request including `returnTo` with `from=agent-landing`
3. `post_oauth_redirect_to_chat`
   - observable via GET to target chat route with `from=agent-landing&agent=<id>`

Important:
- avoid relying only on SPA client transitions for funnel gates; ensure origin-visible requests exist.

## Minimal SEO (phase 0)
For each agent page:
- unique `<title>`
- unique meta description
- canonical URL (`/agents/<agent_id>`)
- basic keyword inclusion in H1/body
- clean Open Graph defaults (can be improved later with dedicated graphics)

## Rollout Control
Optional env flag:
- `AGENT_LANDINGS_ENABLED=0/1`

Behavior:
- `0` (default): pages can stay unlinked from main navigation; direct routes allowed only if explicitly desired.
- `1`: surface links in marketing/footer/ad campaigns.

Note:
- Do not change main landing CTA behavior in the first rollout unless explicitly approved.

## Testing Plan (hermetic)
1. Route render tests:
   - GET `/agents/ppc` returns 200 and contains agent-specific CTA.
2. CTA next-path test:
   - rendered CTA includes OAuth start URL with `returnTo` targeting correct chat path.
3. Safety test:
   - unknown agent id returns 404.
4. No external dependency:
   - tests should not require live gateway/network.

## Delivery Phases
Phase 0 (this plan):
- planning doc + route/config/template plan + observability contract

Phase 1 (minimal implementation):
- dynamic route + single template + registry + CTA wiring + tests

Phase 2:
- run controlled funnel traces (`beta_u1..u3` style for agent landings)
- analyze drop-offs before design iteration

Phase 3:
- design/graphics polish per page
- copy A/B tests per keyword cluster

## Acceptance Criteria (for Phase 1 implementation)
- each agent landing renders with distinct copy/examples
- CTA routes through OAuth and lands in correct chat route
- `from=agent-landing` + `agent=<id>` present post-login
- UTM/gclid preserved through redirect chain
- funnel steps observable in origin traces
