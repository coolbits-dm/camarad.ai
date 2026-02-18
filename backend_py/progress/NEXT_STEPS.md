# Next Steps (Execution Backlog)

Data: 2026-02-17

## P0 - In lucru acum (execution order)

### 0) Agent Science Pack v1 (spec-only) - delivered
- Status: `done`
- Owner: `codex`
- Scope delivered:
  - `progress/agent_science/AGENT_SPEC_V1.yaml`
  - `progress/agent_science/SCHEMAS_V1/*` (4 strict JSON schemas)
  - `progress/agent_science/TASKPACK_A_V1.md` (40 task-uri)
  - `progress/agent_science/TASKPACK_B_V1.md` (40 task-uri, anti-overfit)
  - `progress/agent_science/RUBRIC_V1.md`
  - `progress/agent_science/EVAL_RUNBOOK_V1.md`
- Validation:
  - schema JSON parse: `OK`
  - YAML parse: `OK`
- Done cand:
  - artefactele sunt in repo/runtime si validate sintactic

### 1) P0 confidence harness + OAuth cache audit
- Status: `done`
- Owner: `codex`
- Task:
  - script nou `scripts/connect_confidence.sh` (20x loop GA4 + Ads, AUTHED/MOCK, retry pe 502/503/504)
  - doc nou `docs/OAUTH_CLOUDFLARE_AUDIT.md` (bypass paths + verificare `curl -I` + expected headers)
  - `scripts/smoke.sh` consolidat: callback GA4 trebuie sa raspunda `400` + `Cache-Control: no-store`
- Done cand:
  - harness ruleaza 20/20 pe sesiune autentificata
  - callback OAuth nu mai este cache-uit pe edge

### 2) M2.B GA4 real via Coolbits - polish final
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

### 3) M2.C Billing/Stripe productionization
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

### 3.1) Billing engine calibration (shadow mode)
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

### 4) M3 Client-scoping audit complet
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

### 5) Agent Science smoke baseline (A+B selector)
- Status: `in_progress`
- Owner: `codex + cblm`
- ETA: `1 zi`
- Task:
  - [done] `progress/agent_science/TASKPACK_SMOKE_SELECTOR_V1.md` adaugat (20 task-uri: 5/agent, mix A+B, ordine fixa)
  - [done] baseline matrix `Eco vs Deep` rulat pe selector (40 runs)
  - [done] raport exportat: `progress/agent_science/runs/agent_science_smoke_20260217T204457Z.md`
  - [done] summary: `progress/agent_science/runs/SMOKE_BASELINE_SUMMARY_2026-02-17.md`
- Done cand:
  - exista raport smoke reproducibil si comparabil pentru cei 4 agenti
  - fiecare agent are verdict clar `pass/fail` pe pragurile din `RUBRIC_V1.md`

### 5.1) Agent Science contract enforcement (post-baseline corrective run)
- Status: `done`
- Owner: `codex`
- ETA: `1 zi`
- Task:
  - [done] strict JSON schema envelope enforcement in eval path (no markdown/prose leakage)
  - [done] `policy_used` + `why_deep` behavior enforced for deep mode
  - [done] comparative rerun executed (`allow_real=true`) and logged:
    - `progress/agent_science/runs/agent_science_smoke_20260217T204630Z.md`
    - `progress/agent_science/runs/SMOKE_COMPARISON_2026-02-17.md`
  - [done] rerun after enforcement:
    - `progress/agent_science/runs/agent_science_smoke_20260217T205327Z.md`
    - `progress/agent_science/runs/SMOKE_ENFORCEMENT_DELTA_2026-02-17.md`
- Done cand:
  - schema compliance > 0 and policy compliance > 0 on same 40-run matrix
  - delta report available versus `agent_science_smoke_20260217T204457Z`

### 5.2) Agent Science scoring pass (utility/reasoning/cost)
- Status: `done`
- Owner: `codex + cblm`
- ETA: `1 zi`
- Task:
  - [done] `scripts/score_agent_science_smoke.py` added
  - [done] rubric scoring generated:
    - `progress/agent_science/runs/agent_science_smoke_20260217T205819Z_scored.md`
    - `progress/agent_science/runs/SCORING_PASS_2026-02-17.md`
  - [done] weighted scores computed per agent + pass/fail verdict
- Done cand:
  - scoring report exists per agent (eco/deep)
  - clear remediation backlog for lowest scoring role

### 5.3) Agent Science cost-gate tuning (CEO + DevOps)
- Status: `done`
- Owner: `codex`
- ETA: `0.5-1 zi`
- Task:
  - [done] reduced eval payload verbosity for `ceo` and `devops`
  - [done] kept schema/policy compliance at `1.000`
  - [done] reran selector and confirmed all 4 agents pass rubric
- Done cand:
  - `ceo` and `devops` pass cost gate (`avg_cost >= 8`)
  - all 4 agents `go_no_go=true` in scored report

### 5.4) Agent Science full eval (Set A/B complete)
- Status: `done`
- Owner: `codex + cblm`
- ETA: `1 zi`
- Task:
  - [done] runner supports `--set full` (A+B complete)
  - [done] full matrix executed (80 tasks x 2 policies = 160 runs)
  - [done] scored report exported:
    - `progress/agent_science/runs/agent_science_full_20260217T210117Z_scored.md`
    - `progress/agent_science/runs/FULL_EVAL_SUMMARY_2026-02-17.md`
- Done cand:
  - full-pack scored report exists
  - top 5 remediation items captured for next iteration

### 5.5) Agent Science v1 to beta quality track
- Status: `done`
- Owner: `codex + cblm`
- ETA: `1-2 zile`
- Task:
  - [done] real-response quality run script added: `scripts/run_agent_quality_track.py`
  - [done] quality run executed:
    - `progress/agent_science/runs/agent_science_quality_20260217T225135Z.md`
  - [done] gap report produced:
    - `progress/agent_science/runs/QUALITY_GAP_REPORT_2026-02-17.md`
  - [done] minimal prompt/tooling deltas prepared and validated in remediation pass
- Done cand:
  - quality gap report exists
  - prioritized fix list ready for implementation

### 5.6) Quality remediation patch set (real responses)
- Status: `done`
- Owner: `codex`
- ETA: `1 zi`
- Task:
  - [done] tightened fallback shaping for `ppc`, `ceo`, `devops` in real-response path
  - [done] quality-mode specific compaction added (`X-Agent-Quality-Track: 1`)
  - [done] reran quality track:
    - `progress/agent_science/runs/agent_science_quality_20260217T235148Z.md`
    - `progress/agent_science/runs/QUALITY_REMEDIATION_PASS_2026-02-17.md`
- Done cand:
  - ppc >= 8.5, ceo >= 8.0, devops >= 8.0 on quality run

### 5.7) Beta-run gating pack (Agent Science v1)
- Status: `done`
- Owner: `codex + cblm`
- ETA: `0.5 zi`
- Task:
  - [done] minimal gate checklist defined (smoke + full eval + quality run + runtime checks)
  - [done] single gate doc created:
    - `progress/BETA_GATE_AGENT_SCIENCE_V1_2026-02-17.md`
  - [done] go/no-go note prepared for next external beta wave
- Done cand:
  - beta gate doc exists and is actionable in one pass

### 5.8) Run B operational pack (invites + traces + debrief)
- Status: `done`
- Owner: `codex`
- ETA: `0.5 zi`
- Task:
  - [done] created operator pack:
    - `progress/BETA_RUN_B_OPERATOR_PACK_2026-02-17.md`
  - [done] added improved trace helper:
    - `scripts/beta_trace_collect_v2.sh`
  - [done] added one-shot trace saver:
    - `scripts/beta_trace_collect_save.sh`
  - [done] added debrief generator:
    - `scripts/build_beta_run_b_debrief.py`
  - [done] aligned with existing beta templates/grid files
- Done cand:
  - operator can run invite -> trace -> feedback -> debrief flow end-to-end without extra setup

### 6) Agent grounding v1 (3 agenti reali)
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

### 7) Orchestrator demo pack (live connectors)
- Status: `in_progress`
- Owner: `codex`
- ETA: `1-2 zile`
- Task:
  - slefuieste template-ul `Growth War Room (Live Ads + GA4)`
  - run trace curat + export util pentru demo
  - fallback explicit cand gateway e OFF
- Done cand:
  - demo repeatable, fara mock confusion, pe cont real conectat

### 8) Landing/public trust polish
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

### 9) Flow Composer Agent (prompt -> orchestrator JSON)
- Status: `planned`
- Owner: `codex`
- Scope:
  - endpoint `/api/orchestrator/compose`
  - validare schema flow + salvare draft + deschidere in canvas

### 10) Avatar pipeline v2
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
- Runtime current mode: `OFF` (kept off during beta/readiness runs)
- Next: controlled 24-48h enable window + rollback drill (only after explicit go/no-go)
