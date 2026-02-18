# TaskPack A v1 (40 Tasks Total)

Version: `v1.0`  
Agents: `personal`, `ppc`, `ceo`, `devops`  
Format per task: `task_id`, `agent`, `input_payload`, `expected_output_shape`, `must_use_tools`, `success_criteria`

## Personal Assistant (10)

### 1) PERS-01
- task_id: `PERS-01`
- agent: `personal`
- input_payload: `{ "goal": "Plan my day", "meetings": ["09:30 client sync", "13:00 team standup", "17:00 investor check-in"], "hard_deadline": "Submit report by 18:00" }`
- expected_output_shape: `personal_next_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Includes prioritized schedule actions with realistic time blocks.
  - Flags deadline risk and mitigation.

### 2) PERS-02
- task_id: `PERS-02`
- agent: `personal`
- input_payload: `{ "email_summary": "Client asks for revised KPI dashboard and Monday delivery", "current_load": "high" }`
- expected_output_shape: `personal_next_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Extracts concrete actions from email context.
  - Assigns owner and urgency correctly.

### 3) PERS-03
- task_id: `PERS-03`
- agent: `personal`
- input_payload: `{ "week_context": "Multiple launches ongoing", "need": "Weekly status and next actions" }`
- expected_output_shape: `personal_next_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Produces weekly status-ready actions.
  - Keeps action list concise and ordered.

### 4) PERS-04
- task_id: `PERS-04`
- agent: `personal`
- input_payload: `{ "reminder_request": "Investor call tomorrow 14:00", "need": "3 prep questions" }`
- expected_output_shape: `personal_next_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Includes reminder setup action and prep actions.
  - Questions are relevant to investor call.

### 5) PERS-05
- task_id: `PERS-05`
- agent: `personal`
- input_payload: `{ "ct_spend_today": 450, "workspace": "agency", "ask": "Breakdown and optimization suggestions" }`
- expected_output_shape: `personal_next_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Suggests cost-aware actions.
  - Recommends immediate optimization steps.

### 6) PERS-06
- task_id: `PERS-06`
- agent: `personal`
- input_payload: `{ "ppc_chat_summary": "Keyword waste and bid volatility noted", "ask": "Summarize pending actions" }`
- expected_output_shape: `personal_next_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Captures pending PPC follow-ups clearly.
  - Assigns priority by business impact.

### 7) PERS-07
- task_id: `PERS-07`
- agent: `personal`
- input_payload: `{ "initiative": "New feature launch this week", "ask": "Launch TODO list" }`
- expected_output_shape: `personal_next_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Covers prep, launch, and post-launch checks.
  - Includes dependencies.

### 8) PERS-08
- task_id: `PERS-08`
- agent: `personal`
- input_payload: `{ "alert": "Low balance warning", "context": "Active campaigns running" }`
- expected_output_shape: `personal_next_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Prioritizes immediate risk containment actions.
  - Includes communication/escalation step.

### 9) PERS-09
- task_id: `PERS-09`
- agent: `personal`
- input_payload: `{ "horizon": "next week", "constraints": ["2 demos", "board prep", "deadline Friday"] }`
- expected_output_shape: `personal_next_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Produces realistic next-week plan.
  - Balances deadlines and workload.

### 10) PERS-10
- task_id: `PERS-10`
- agent: `personal`
- input_payload: `{ "meeting_notes": "Discussed pricing, KPI ownership, and hiring freeze", "ask": "Extract actions" }`
- expected_output_shape: `personal_next_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Extracts decisions into concrete actions.
  - Includes owners and timing hints.

## PPC Specialist (10)

### 11) PPC-01
- task_id: `PPC-01`
- agent: `ppc`
- input_payload: `{ "campaign_state": "weak performance", "metrics": { "ctr": 1.2, "cvr": 0.9, "roas": 1.8 } }`
- expected_output_shape: `ppc_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Diagnoses likely causes.
  - Returns actionable campaign changes.

### 12) PPC-02
- task_id: `PPC-02`
- agent: `ppc`
- input_payload: `{ "search_terms": ["free template", "cheap option", "brand misspells"], "ask": "Add negatives" }`
- expected_output_shape: `ppc_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Proposes sensible negative keywords.
  - Avoids blocking high-intent terms.

### 13) PPC-03
- task_id: `PPC-03`
- agent: `ppc`
- input_payload: `{ "roas_target": 4.0, "keyword_perf": [{ "kw": "crm software", "roas": 2.1 }, { "kw": "sales automation", "roas": 5.2 }] }`
- expected_output_shape: `ppc_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Suggests bid adjustments aligned to target.
  - Includes risk-aware changes.

### 14) PPC-04
- task_id: `PPC-04`
- agent: `ppc`
- input_payload: `{ "offer": "14-day free trial", "audience": "SMB founders", "ask": "3 ad copies" }`
- expected_output_shape: `ppc_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Produces 3 distinct copy test actions.
  - Clear value proposition per variant.

### 15) PPC-05
- task_id: `PPC-05`
- agent: `ppc`
- input_payload: `{ "daily_budget": 1200, "spend_today": 1560, "campaign_split": { "brand": 300, "search": 900, "display": 360 } }`
- expected_output_shape: `ppc_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Recommends pause/reallocation actions.
  - Protects highest-intent campaigns.

### 16) PPC-06
- task_id: `PPC-06`
- agent: `ppc`
- input_payload: `{ "ga4_paths": ["paid search > pricing > signup", "display > blog > exit"], "ask": "Insights + fixes" }`
- expected_output_shape: `ppc_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Uses path insights to refine actions.
  - Prioritizes conversion-impact fixes.

### 17) PPC-07
- task_id: `PPC-07`
- agent: `ppc`
- input_payload: `{ "product": "AI workflow tool", "ask": "Keyword research 15 terms" }`
- expected_output_shape: `ppc_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Returns relevant keyword action plan.
  - Balances intent coverage.

### 18) PPC-08
- task_id: `PPC-08`
- agent: `ppc`
- input_payload: `{ "weekly_metrics": { "impr": 230000, "clicks": 5400, "conv": 178, "roas": 3.7 }, "ask": "Weekly report actions" }`
- expected_output_shape: `ppc_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Gives concise reporting actions.
  - Links actions to KPI movement.

### 19) PPC-09
- task_id: `PPC-09`
- agent: `ppc`
- input_payload: `{ "budget_change_pct": 30, "current_structure": "brand/non-brand generic split", "ask": "New structure" }`
- expected_output_shape: `ppc_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Proposes scalable structure modifications.
  - Includes transition steps.

### 20) PPC-10
- task_id: `PPC-10`
- agent: `ppc`
- input_payload: `{ "issue": "mobile CTR drop", "segment_metrics": { "mobile_ctr": 0.8, "desktop_ctr": 2.4 } }`
- expected_output_shape: `ppc_actions.schema.json`
- must_use_tools: `no`
- success_criteria:
  - Diagnoses mobile-specific root causes.
  - Suggests testable fixes.

## CEO / Vision & Strategy (10)

### 21) CEO-01
- task_id: `CEO-01`
- agent: `ceo`
- input_payload: `{ "tool_context_provided": true, "spend_vs_plan": { "month": "current", "delta_pct": 20 }, "question": "Scale or hold?" }`
- expected_output_shape: `ceo_exec_brief.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Returns clear go/no-go/hold decision.
  - Uses tool context before decision.

### 22) CEO-02
- task_id: `CEO-02`
- agent: `ceo`
- input_payload: `{ "tool_context_provided": true, "deal": { "client": "X", "requested_discount_pct": 20, "margin_impact": "high" } }`
- expected_output_shape: `ceo_exec_brief.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Gives decision and negotiation posture.
  - Identifies margin risk mitigation.

### 23) CEO-03
- task_id: `CEO-03`
- agent: `ceo`
- input_payload: `{ "tool_context_provided": true, "signal": "churn spike", "delta_pct": 14 }`
- expected_output_shape: `ceo_exec_brief.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Highlights probable root causes.
  - Prioritizes immediate actions.

### 24) CEO-04
- task_id: `CEO-04`
- agent: `ceo`
- input_payload: `{ "tool_context_provided": true, "month_review": { "roas": 4.2, "revenue_trend": "flat" }, "ask": "Next strategy" }`
- expected_output_shape: `ceo_exec_brief.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Produces strategic recommendation.
  - Includes risks and next actions.

### 25) CEO-05
- task_id: `CEO-05`
- agent: `ceo`
- input_payload: `{ "tool_context_provided": true, "proposal": "Increase search budget 50%", "guardrails": "CAC must stay < 35" }`
- expected_output_shape: `ceo_exec_brief.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Decision tied to guardrails.
  - Defines review checkpoints.

### 26) CEO-06
- task_id: `CEO-06`
- agent: `ceo`
- input_payload: `{ "tool_context_provided": true, "incident": "API outage 42 min", "impact": "missed runs and delayed reports" }`
- expected_output_shape: `ceo_exec_brief.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Business impact summarized clearly.
  - Response plan and accountability present.

### 27) CEO-07
- task_id: `CEO-07`
- agent: `ceo`
- input_payload: `{ "tool_context_provided": true, "beta_feedback": { "top_pains": ["onboarding confusion", "slow first value"], "top_value": ["run trace"] } }`
- expected_output_shape: `ceo_exec_brief.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Prioritization logic is explicit.
  - Converts feedback to roadmap actions.

### 28) CEO-08
- task_id: `CEO-08`
- agent: `ceo`
- input_payload: `{ "tool_context_provided": true, "cashflow_projection": "3 months runway at current burn", "proposal": "Hire one backend engineer" }`
- expected_output_shape: `ceo_exec_brief.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Go/no-go with financial rationale.
  - Includes risk-controlled alternative.

### 29) CEO-09
- task_id: `CEO-09`
- agent: `ceo`
- input_payload: `{ "tool_context_provided": true, "market_event": "Competitor launched similar orchestration feature" }`
- expected_output_shape: `ceo_exec_brief.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Recommends response strategy.
  - Balances speed vs focus trade-off.

### 30) CEO-10
- task_id: `CEO-10`
- agent: `ceo`
- input_payload: `{ "tool_context_provided": true, "eval_score": 7.8, "question": "Fine-tune now or iterate prompt/RAG first?" }`
- expected_output_shape: `ceo_exec_brief.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Decision references thresholds.
  - Suggests concrete next iteration.

## DevOps & Infrastructure (10)

### 31) DEV-01
- task_id: `DEV-01`
- agent: `devops`
- input_payload: `{ "tool_context_provided": true, "incident": "API latency spike", "metrics": { "p95_ms": 2400, "baseline_ms": 620 } }`
- expected_output_shape: `devops_runbook.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Root-cause hypothesis grounded in context.
  - Actionable remediation sequence.

### 32) DEV-02
- task_id: `DEV-02`
- agent: `devops`
- input_payload: `{ "tool_context_provided": true, "incident": "orchestrator crashloop", "recent_deploy": true }`
- expected_output_shape: `devops_runbook.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Includes safe rollback/check steps.
  - Escalation criteria included.

### 33) DEV-03
- task_id: `DEV-03`
- agent: `devops`
- input_payload: `{ "tool_context_provided": true, "alert": "CT burn anomaly", "window": "last 2h", "delta_pct": 180 }`
- expected_output_shape: `devops_runbook.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Proposes validation checks for leak source.
  - Contains containment and follow-up actions.

### 34) DEV-04
- task_id: `DEV-04`
- agent: `devops`
- input_payload: `{ "tool_context_provided": true, "incident": "intermittent nginx 502", "frequency": "every 3-5 min" }`
- expected_output_shape: `devops_runbook.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Runbook includes log correlation checks.
  - Clear expected outcomes per step.

### 35) DEV-05
- task_id: `DEV-05`
- agent: `devops`
- input_payload: `{ "tool_context_provided": true, "incident": "DB pool exhausted", "symptom": "timeouts on chat POST" }`
- expected_output_shape: `devops_runbook.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Provides hypothesis and capacity checks.
  - Includes risk-aware mitigation.

### 36) DEV-06
- task_id: `DEV-06`
- agent: `devops`
- input_payload: `{ "tool_context_provided": true, "incident": "deploy failed", "error_excerpt": "migration lock timeout" }`
- expected_output_shape: `devops_runbook.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Rollback and recovery path is explicit.
  - Avoids destructive unverified actions.

### 37) DEV-07
- task_id: `DEV-07`
- agent: `devops`
- input_payload: `{ "tool_context_provided": true, "incident": "Cloudflare rate-limit hit", "paths": ["/api/chat", "/api/orchestrator/execute"] }`
- expected_output_shape: `devops_runbook.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Distinguishes false-positive vs abuse.
  - Proposes safe threshold tuning.

### 38) DEV-08
- task_id: `DEV-08`
- agent: `devops`
- input_payload: `{ "tool_context_provided": true, "incident": "PM2 app down", "service": "camarad" }`
- expected_output_shape: `devops_runbook.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Includes restart and root-cause prevention.
  - Contains post-recovery verification steps.

### 39) DEV-09
- task_id: `DEV-09`
- agent: `devops`
- input_payload: `{ "tool_context_provided": true, "issue": "Run trace retention too large", "storage_growth": "high" }`
- expected_output_shape: `devops_runbook.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Recommends retention optimization safely.
  - Mentions observability trade-offs.

### 40) DEV-10
- task_id: `DEV-10`
- agent: `devops`
- input_payload: `{ "tool_context_provided": true, "incident": "beta invites not arriving", "suspected_component": "email connector" }`
- expected_output_shape: `devops_runbook.schema.json`
- must_use_tools: `yes`
- success_criteria:
  - Includes connector health checks.
  - Escalates correctly if delivery blocked.
