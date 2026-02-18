# TaskPack B v1 (Anti-Overfit Rotated Set)

Version: `v1.0`  
Purpose: rotated benchmark set to reduce overfit against `TASKPACK_A_V1.md`.  
Scope: same 4 agents, same schemas, same rubric, same policy controls.

## Personal Assistant (10)

### PA_B_01
- task_id: `PA_B_01`
- agent: `personal`
- input_payload: `{"context":"Today: 2 client calls + 1 dev block. Deadline: GA4 confidence report by 17:00. Need 30min break.","constraints":{"working_hours":"09:00-18:00","timezone":"Europe/Bucharest"}}`
- expected_output_shape: `personal_next_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - 3-8 actions with priority + ETA.
  - Ordering includes realistic buffers.
  - No prose outside schema.

### PA_B_02
- task_id: `PA_B_02`
- agent: `personal`
- input_payload: `{"context":"Email summary: client complains about spend spike and asks for explanation by noon. You also have deploy window 14:00-15:00.","knowns":["billing telemetry exists","confidence harness exists"]}`
- expected_output_shape: `personal_next_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Includes explicit evidence-collection action before reply.

### PA_B_03
- task_id: `PA_B_03`
- agent: `personal`
- input_payload: `{"context":"Last 7 days: started P0/P1, then P2 behind flag, then paused Phase3 for beta. Feeling scattered. Make a 2-day plan.","goal":"restore focus"}`
- expected_output_shape: `personal_next_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - 2-day plan with dependencies.

### PA_B_04
- task_id: `PA_B_04`
- agent: `personal`
- input_payload: `{"context":"Invite 2 internal reviewers for iPhone Safari overlap tests and collect repro steps.","constraints":{"no_new_code":true}}`
- expected_output_shape: `personal_next_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Includes device/OS/browser version capture and screenshots list.

### PA_B_05
- task_id: `PA_B_05`
- agent: `personal`
- input_payload: `{"context":"You have 90 minutes. Prepare executive update: what's stable, what's next, top risks.","format":"action-oriented"}`
- expected_output_shape: `personal_next_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Action-only format with send/submit step.

### PA_B_06
- task_id: `PA_B_06`
- agent: `personal`
- input_payload: `{"context":"Low energy day. Minimize cognitive load.","outcome":"Agent Science Pack baseline eval run"}`
- expected_output_shape: `personal_next_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Includes 5 tasks/agent Eco vs Deep prep.

### PA_B_07
- task_id: `PA_B_07`
- agent: `personal`
- input_payload: `{"context":"Meeting notes: OAuth cache rules pending, mobile header overlap, plan limits proposal. Extract tasks."}`
- expected_output_shape: `personal_next_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - No hallucinated details beyond notes.

### PA_B_08
- task_id: `PA_B_08`
- agent: `personal`
- input_payload: `{"context":"Need cheap internal weekly synthesis routine (Eco mode).","note":"don't propose new infra"}`
- expected_output_shape: `personal_next_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Cost-aware, repeatable weekly routine.

### PA_B_09
- task_id: `PA_B_09`
- agent: `personal`
- input_payload: `{"context":"Prepare 3 questions for meeting: mirror Camarad UI onto CoolBits?","constraints":{"avoid_solution_framing":true}}`
- expected_output_shape: `personal_next_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Questions are crisp and risk-aware.

### PA_B_10
- task_id: `PA_B_10`
- agent: `personal`
- input_payload: `{"context":"Post-ship checklist for today (non-code).","scope":["smoke","confidence harness","basic UX sanity"]}`
- expected_output_shape: `personal_next_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Ordered checklist with completion-ready actions.

## PPC Specialist (10)

### PPC_B_01
- task_id: `PPC_B_01`
- agent: `ppc`
- input_payload: `{"context":"Search campaign ROAS dropped 30% WoW. No other data yet. Provide triage plan + exact data requests.","account_type":"MCC"}`
- expected_output_shape: `ppc_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - First action is data request/validation.

### PPC_B_02
- task_id: `PPC_B_02`
- agent: `ppc`
- input_payload: `{"context":"Client wants cheaper leads but conversion quality unknown.","channels":["Google Ads","GA4"]}`
- expected_output_shape: `ppc_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Includes measurement fixes + low-risk optimizations.

### PPC_B_03
- task_id: `PPC_B_03`
- agent: `ppc`
- input_payload: `{"context":"Spend pacing issue: daily spend too high early.","constraints":{"no_scripts_deploy_today":true}}`
- expected_output_shape: `ppc_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Practical pacing controls without infra change.

### PPC_B_04
- task_id: `PPC_B_04`
- agent: `ppc`
- input_payload: `{"context":"Need 10 negative keyword themes for dental leadgen.","note":"avoid overblocking brand terms"}`
- expected_output_shape: `ppc_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Theme-level negatives with rationale.

### PPC_B_05
- task_id: `PPC_B_05`
- agent: `ppc`
- input_payload: `{"context":"Mobile CTR low; landing slow. Give ad-side mitigation + measurement steps.","constraints":{"no_web_perf_tools_now":true}}`
- expected_output_shape: `ppc_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Includes mobile-specific ad tests and tracking checks.

### PPC_B_06
- task_id: `PPC_B_06`
- agent: `ppc`
- input_payload: `{"context":"Need 3 RSA copy angles for services business.","constraints":{"language":"RO","diacritics":true}}`
- expected_output_shape: `ppc_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Distinct copy angles as concrete action entries.

### PPC_B_07
- task_id: `PPC_B_07`
- agent: `ppc`
- input_payload: `{"context":"Budget increase +30% approved. Propose conservative vs aggressive structure options + risks.","goal":"minimize volatility"}`
- expected_output_shape: `ppc_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Two options with risk framing and migration steps.

### PPC_B_08
- task_id: `PPC_B_08`
- agent: `ppc`
- input_payload: `{"context":"GA4 shows more conversions than Ads. Propose reconciliation steps.","note":"don’t assume attribution model"}`
- expected_output_shape: `ppc_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Clear investigation flow and likely causes.

### PPC_B_09
- task_id: `PPC_B_09`
- agent: `ppc`
- input_payload: `{"context":"Need weekly report template in JSON: winners/losers + next 5 actions.","constraints":{"max_lines":"~12 bullets equivalent"}}`
- expected_output_shape: `ppc_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Reportable structure + actionability.

### PPC_B_10
- task_id: `PPC_B_10`
- agent: `ppc`
- input_payload: `{"context":"Brand terms leaking into non-brand. Propose separation tactics + guardrails.","note":"avoid breaking learnings"}`
- expected_output_shape: `ppc_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Specific structure and guardrail actions.

## CEO (10)

### CEO_B_01
- task_id: `CEO_B_01`
- agent: `ceo`
- input_payload: `{"tool_context_provided":true,"context":"Mirror Camarad UI onto CoolBits for 1-week sprint.","knowns":["shared gateway","separate domains"],"constraints":["avoid regressions","keep routes without /app"]}`
- expected_output_shape: `ceo_exec_brief.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Explicit decision + rationale + top risks.

### CEO_B_02
- task_id: `CEO_B_02`
- agent: `ceo`
- input_payload: `{"tool_context_provided":true,"context":"Beta now vs continue polishing.","risk_tolerance":"low"}`
- expected_output_shape: `ceo_exec_brief.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Clear decision path with mitigation.

### CEO_B_03
- task_id: `CEO_B_03`
- agent: `ceo`
- input_payload: `{"tool_context_provided":true,"context":"Stay 100% Vertex now vs add OpenAI/xAI/Anthropic later.","goal":"cost control + optional deep reasoning"}`
- expected_output_shape: `ceo_exec_brief.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Sequencing decision, not generic opinion.

### CEO_B_04
- task_id: `CEO_B_04`
- agent: `ceo`
- input_payload: `{"tool_context_provided":true,"context":"Phase 3 billing behind flag exists. Decide rollout criteria and rollback posture.","knowns":["gate doc exists","caps exist"]}`
- expected_output_shape: `ceo_exec_brief.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Defines criteria and stop conditions.

### CEO_B_05
- task_id: `CEO_B_05`
- agent: `ceo`
- input_payload: `{"tool_context_provided":true,"context":"iPhone Safari overlap impacts trust. Prioritize vs roadmap.","constraints":{"ui_only_patch":true}}`
- expected_output_shape: `ceo_exec_brief.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Priority justified against tradeoffs.

### CEO_B_06
- task_id: `CEO_B_06`
- agent: `ceo`
- input_payload: `{"tool_context_provided":true,"context":"Allocate $1000 Vertex voucher across evals/prompt-RAG/fine-tune.","principle":"no fine-tune without baseline uplift evidence"}`
- expected_output_shape: `ceo_exec_brief.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Allocation with measurable checkpoints.

### CEO_B_07
- task_id: `CEO_B_07`
- agent: `ceo`
- input_payload: `{"tool_context_provided":true,"context":"Anti-leak matrix + CI green. Freeze M3 and move to conversion work?"}`
- expected_output_shape: `ceo_exec_brief.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Decision tied to residual risk.

### CEO_B_08
- task_id: `CEO_B_08`
- agent: `ceo`
- input_payload: `{"tool_context_provided":true,"context":"Cost control: Eco default vs Deep on request. Decide UI exposure model.","goal":"avoid accidental deep burn"}`
- expected_output_shape: `ceo_exec_brief.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Policy recommendation with user-safety considerations.

### CEO_B_09
- task_id: `CEO_B_09`
- agent: `ceo`
- input_payload: `{"tool_context_provided":true,"context":"Transient 502 after restart. Acceptable for beta?","options":["warmup retry","status page","do nothing"]}`
- expected_output_shape: `ceo_exec_brief.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Decision + operational next actions.

### CEO_B_10
- task_id: `CEO_B_10`
- agent: `ceo`
- input_payload: `{"tool_context_provided":true,"context":"Define done for Agent Science Pack v1.","knowns":["rubric thresholds defined"]}`
- expected_output_shape: `ceo_exec_brief.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Done-criteria and iteration plan are explicit.

## DevOps (10)

### DO_B_01
- task_id: `DO_B_01`
- agent: `devops`
- input_payload: `{"tool_context_provided":true,"symptom":"iPhone Safari titles hidden under fixed topbar on some pages.","scope":["/chat","/connectors","/agents","/orchestrator"],"constraints":["CSS/JS only","no backend changes"]}`
- expected_output_shape: `devops_runbook.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Runbook covers repro, diagnosis, rollback-safe patching.

### DO_B_02
- task_id: `DO_B_02`
- agent: `devops`
- input_payload: `{"tool_context_provided":true,"symptom":"OAuth callback must never be cached.","paths":["/api/connectors/ga4/oauth/callback*","/api/connectors/*/oauth/*"]}`
- expected_output_shape: `devops_runbook.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Includes rule checks and header verification steps.

### DO_B_03
- task_id: `DO_B_03`
- agent: `devops`
- input_payload: `{"tool_context_provided":true,"symptom":"PM2 restart causes transient 502 for ~10s.","current":"smoke has warmup retry"}`
- expected_output_shape: `devops_runbook.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Root-cause hypotheses + mitigation options.

### DO_B_04
- task_id: `DO_B_04`
- agent: `devops`
- input_payload: `{"tool_context_provided":true,"symptom":"Daily CT burn spikes unexpectedly.","available":["usage_ledger rows","top_models","top_agents"],"constraints":["no Phase3 changes"]}`
- expected_output_shape: `devops_runbook.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Contains containment + investigation sequence.

### DO_B_05
- task_id: `DO_B_05`
- agent: `devops`
- input_payload: `{"tool_context_provided":true,"symptom":"Nginx repeated probes for /_next and /rsc.","goal":"reduce noise without hiding real errors"}`
- expected_output_shape: `devops_runbook.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Noise reduction strategy without observability loss.

### DO_B_06
- task_id: `DO_B_06`
- agent: `devops`
- input_payload: `{"tool_context_provided":true,"symptom":"SQLite DB locked warnings during peak.","constraints":["no Postgres migration now"],"goal":"stability"}`
- expected_output_shape: `devops_runbook.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Practical stabilization actions with risk levels.

### DO_B_07
- task_id: `DO_B_07`
- agent: `devops`
- input_payload: `{"tool_context_provided":true,"symptom":"Cloudflare rate limiting hits demo traffic.","need":"headers + rule strategy","constraints":["low-risk only"]}`
- expected_output_shape: `devops_runbook.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Includes safe tuning and monitoring checks.

### DO_B_08
- task_id: `DO_B_08`
- agent: `devops`
- input_payload: `{"tool_context_provided":true,"symptom":"GA4 connect popup blocked by browser settings.","need":"fallback UX flow validation steps"}`
- expected_output_shape: `devops_runbook.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Validation plan includes fallback path checks.

### DO_B_09
- task_id: `DO_B_09`
- agent: `devops`
- input_payload: `{"tool_context_provided":true,"symptom":"Disk usage grows from artifacts/knowledge base.","need":"retention plan + risk assessment","constraints":["no external storage today"]}`
- expected_output_shape: `devops_runbook.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Retention plan with rollback and auditability.

### DO_B_10
- task_id: `DO_B_10`
- agent: `devops`
- input_payload: `{"tool_context_provided":true,"symptom":"CI passes locally but fails on permissions/executables intermittently.","need":"repo hygiene checklist"}`
- expected_output_shape: `devops_runbook.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Checklist is deterministic and low-risk.

## Run Notes

- Use this set with `TASKPACK_A_V1.md` for anti-overfit comparison.
- If Set A passes but Set B fails, treat as overfit signal.
- Recommended first pass: smoke selector = 5 tasks/agent from this file (20 total), Eco vs Deep.
