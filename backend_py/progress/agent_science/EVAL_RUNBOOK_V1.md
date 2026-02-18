# Eval Runbook v1

Version: `v1.0`  
Scope: Agent Science Pack for `personal`, `ppc`, `ceo`, `devops`  
Policy modes compared: `eco` vs `deep` (optional `auto` after baseline)

## Principles

- Provider is abstracted by gateway; do not couple eval logic to vendor names.
- Policies are runtime/UI controls.
- Same task, same input, same schema, different policy => comparable run.
- Prompt/RAG/tooling fixes come before fine-tune.

## Phase 1: Smoke Eval (20 runs)

- Run `5 tasks per agent` (`20 total`)
- Execute each task twice:
  - once with `policy=eco`
  - once with `policy=deep`

Outputs to record per run:
- raw JSON output
- schema_valid
- utilitate, format, reasoning, cost scores
- penalties and compliance flags
- latency and cost proxy

Goal:
- detect obvious schema violations
- verify tool-first behavior (CEO/DevOps)
- verify why_deep behavior

## Phase 2: Full Eval (40 tasks x 2 policies)

- Run all `40 tasks` from TaskPack A
- Execute for `eco` and `deep`
- Aggregate by agent and global

## Output Table Template

| agent | policy | runs | schema_compliance_rate | hard_fail_rate | pass_rate | mean_weighted_score | p50_cost | p90_cost | p50_latency_ms | p90_latency_ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| personal | eco | 10 |  |  |  |  |  |  |  |  |
| personal | deep | 10 |  |  |  |  |  |  |  |  |
| ppc | eco | 10 |  |  |  |  |  |  |  |  |
| ppc | deep | 10 |  |  |  |  |  |  |  |  |
| ceo | eco | 10 |  |  |  |  |  |  |  |  |
| ceo | deep | 10 |  |  |  |  |  |  |  |  |
| devops | eco | 10 |  |  |  |  |  |  |  |  |
| devops | deep | 10 |  |  |  |  |  |  |  |  |
| all | eco | 40 |  |  |  |  |  |  |  |  |
| all | deep | 40 |  |  |  |  |  |  |  |  |

Pass criterion per run:
- format >= 9 (hard requirement)
- utilitate >= 8
- weighted_total >= 8.2
- cost <= 1.5x eco baseline (comparable task)

## Iteration Decision Rule

After each full eval cycle:

1. If failures are mostly schema/format:
   - fix system prompt + schema constraints first
2. If failures are mostly reasoning/tool-first:
   - fix tool contracts + retrieval/tool invocation logic
3. If failures are mostly cost:
   - tighten policy routing and caps; reduce unnecessary deep usage
4. Only consider fine-tune if:
   - after `2-3` prompt/RAG/tooling iterations
   - role still below thresholds
   - expected uplift justifies cost

## Fine-Tune Gate

Fine-tune can be considered only when:
- baseline is stable and reproducible
- failure cluster is persistent and role-specific
- estimated gain > operational complexity

Otherwise continue with:
- prompt and schema optimization
- tool-order improvements
- retrieval quality tuning
