# Next Steps (Execution Backlog)

Data: 2026-02-12

## P0 - In lucru acum (execution order)

### 0) P0 confidence harness + OAuth cache audit
- Status: `done`
- Owner: `codex`
- Task:
  - script nou `scripts/connect_confidence.sh` (20x loop GA4 + Ads, AUTHED/MOCK, retry pe 502/503/504)
  - doc nou `docs/OAUTH_CLOUDFLARE_AUDIT.md` (bypass paths + verificare `curl -I` + expected headers)
  - `scripts/smoke.sh` consolidat: callback GA4 trebuie sa raspunda `400` + `Cache-Control: no-store`
- Done cand:
  - harness ruleaza 20/20 pe sesiune autentificata
  - callback OAuth nu mai este cache-uit pe edge

### 1) M2.B GA4 real via Coolbits - polish final
- Status: `in_progress`
- Owner: `codex`
- ETA: `1-2 zile`
- Task:
  - stabilizeaza callback OAuth GA4 (`/api/connectors/ga4/oauth/callback`) pe toate host-urile folosite
  - elimina ultimele ecrane `404 Not Found` dupa consent
  - unifica UX `Connect` + `Date Range` + refresh pe toate tab-urile GA4
- Done cand:
  - flow OAuth GA4 este 100% consistent (fara refresh workaround)
  - `overview/pages/sources/events/funnels/audience` incarca date reale fara regresii

### 2) M2.C Billing/Stripe productionization
- Status: `in_progress`
- Owner: `codex + cblm`
- ETA: `2 zile`
- Task:
  - aliniaza planurile Camarad cu produsele/price IDs reale din Stripe
  - blocheaza upgrade-ul de plan local daca nu exista subscriptie activa in Stripe
  - finalizeaza currency standard in EUR pe pricing + billing views + payload-uri
- Done cand:
  - selectia de plan deschide checkout real si sincronizeaza corect entitlement-urile
  - statusul subscriptiei din Settings/Billing este determinist (fara mock ambiguity)

### 2.1) Billing engine calibration (shadow mode)
- Status: `in_progress`
- Owner: `codex`
- ETA: `1-2 zile`
- Task:
  - finalizeaza Faza 2 shadow pricing (`pricing_catalog`, `ct_rates`, `ct_shadow_debit`) fara debit CT real
  - ruleaza 48h telemetrie pe trafic real si extrage `ct_shadow vs ct_actual` delta per model/agent
  - propune recalibrare `ct_value` + `buffer` + `margin` pe date reale (nu estimari)
- Done cand:
  - `/api/billing/cost-telemetry` arata consistent agregatele 24h/7d + delta
  - exista recomandare de calibrare planuri/CT cu impact estimat pe profitabilitate

### 3) M3 Client-scoping audit complet
- Status: `in_progress`
- Owner: `codex + cblm`
- ETA: `2 zile`
- Task:
  - audit endpoint-uri critice pentru izolarea per client (`X-Client-ID`)
  - teste automate pentru leakage cross-client (chat, agents, flows, connectors)
  - audit by-id API routes + fix queries cu `user_id` + `client_id` pe rutele client-scoped
  - matrix anti-leak extins in `test_m3_scoping.py` (owned client A vs owned client B, missing scope, spoof guard)
- Done cand:
  - zero leakage cross-client confirmat pe rute critice + UI

## P1 - Urmatoarele 7 zile

### 4) Agent grounding v1 (3 agenti reali)
- Status: `in_progress`
- Owner: `codex`
- ETA: `2-3 zile`
- Scope:
  - Personal Assistant (router/context)
  - PPC Specialist
  - SEO & Content Strategist
- Task:
  - system prompts pe rol + boundaries + tool-usage rules
  - raspunsuri initiale relevante pentru environment (fara generic LLM boilerplate)
  - sugestii dinamice in composer pe context curent (client + conectori activi)
- Done cand:
  - fiecare agent raspunde consistent pe rol in 10/10 probe de smoke

### 5) Orchestrator demo pack (live connectors)
- Status: `in_progress`
- Owner: `codex`
- ETA: `1-2 zile`
- Task:
  - slefuieste template-ul `Growth War Room (Live Ads + GA4)`
  - run trace curat + export util pentru demo
  - fallback explicit cand gateway e OFF
- Done cand:
  - demo repeatable, fara mock confusion, pe cont real conectat

### 6) Landing/public trust polish
- Status: `in_progress`
- Owner: `codex`
- ETA: `1 zi`
- Task:
  - verifica convergenta globala pentru `/legal`, `/privacy`, `/terms`
  - clarifica rolul `api.camarad.ai` (API root behavior/documentatie)
  - pastreaza footer links coerente (`Pricing`, `Legal`, `Privacy`, `Terms`)
  - landing polish v1: autocomplete (`/api/search`), CTA clar signup/demo, blocuri "what you get/how it works/proof"
  - split search endpoint: public deterministic `/api/search` + scoped auth `/api/app/search`
  - demo chat public read-only (`/chat-demo`, plus `?demo=1` pe `/chat` pentru user neautentificat)

## P2 - Dupa stabilizare

### 7) Flow Composer Agent (prompt -> orchestrator JSON)
- Status: `planned`
- Owner: `codex`
- Scope:
  - endpoint `/api/orchestrator/compose`
  - validare schema flow + salvare draft + deschidere in canvas

### 8) Avatar pipeline v2
- Status: `planned`
- Scope:
  - upgrade stil vizual premium + animatii discrete (strict contained in circle)

---

## Tracking format

Pentru fiecare task nou:
- `Owner`
- `Status` (`todo` / `in_progress` / `blocked` / `done`)
- `ETA`
- `Blockers`

### P2 Billing Phase 3 (flagged)
- Status: `in_progress`
- Implemented behind env flag `BILLING_PHASE3_ENABLED` (default OFF)
- Added server-side caps: `MAX_CT_PER_REQUEST`, `MAX_DAILY_CT_PER_WORKSPACE`
- Added idempotent debit by `request_id` and telemetry `phase3` block
- Next: controlled 24-48h enable window + rollback drill
