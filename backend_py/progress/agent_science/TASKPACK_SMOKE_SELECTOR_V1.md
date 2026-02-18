# TASKPACK_SMOKE_SELECTOR_V1

Version: `v1.0`  
Purpose: deterministic smoke/baseline subset for Agent Science Pack v1.  
Total: `20 tasks` (`5 per agent`)  
Policy matrix: `eco` + `deep` (40 total runs)

Selection rules:
- Fixed order (no randomization).
- Mixed coverage from both sets (A+B).
- Includes ambiguous/messy inputs and tool-first cases.
- For CEO/DevOps, includes tool-context tasks to validate tool-first contract.

## Personal Assistant (5)
1. `PERS-01` (A) - day planning with deadlines  
2. `PERS-05` (A) - CT spend breakdown + optimization  
3. `PA_B_02` (B) - email complaint + evidence-first response  
4. `PA_B_07` (B) - action extraction from concise notes  
5. `PA_B_10` (B) - post-ship checklist, non-code

## PPC Specialist (5)
1. `PPC-01` (A) - weak campaign analysis + actions  
2. `PPC-06` (A) - GA4 path insights + fixes  
3. `PPC_B_03` (B) - spend pacing without infra changes  
4. `PPC_B_08` (B) - Ads vs GA4 conversion mismatch reconciliation  
5. `PPC_B_10` (B) - brand/non-brand leakage guardrails

## CEO (5)
1. `CEO-01` (A) - overspend scale/hold decision (tool context)  
2. `CEO-06` (A) - incident impact + preventive measures  
3. `CEO_B_04` (B) - Phase 3 rollout criteria + rollback posture  
4. `CEO_B_06` (B) - voucher allocation decision under constraints  
5. `CEO_B_09` (B) - transient 502 beta acceptability decision

## DevOps (5)
1. `DEV-01` (A) - API latency spike triage  
2. `DEV-04` (A) - intermittent Nginx 502 diagnosis  
3. `DO_B_02` (B) - OAuth callback cache-bypass verification  
4. `DO_B_03` (B) - PM2 restart transient 502 mitigation  
5. `DO_B_06` (B) - SQLite DB lock stability runbook

## Run Contract
- Output must validate against per-agent JSON schema.
- `policy_mode=deep` requires non-empty `why_deep`.
- CEO/DevOps tool-first rule enforced when tool context is present.
- Scoring and thresholds follow `RUBRIC_V1.md`.

## Report Contract
For each run batch, report:
- `schema_compliance_rate`
- `mean_weighted_score` (per agent)
- `deep_vs_eco_cost_multiplier`
- `top_failure_reasons` (top 3)

