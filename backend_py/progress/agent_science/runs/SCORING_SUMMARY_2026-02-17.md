# Agent Science Scoring Summary (2026-02-17)

Source run:
- `progress/agent_science/runs/agent_science_smoke_20260217T205540Z.json`
- scored output:
  - `progress/agent_science/runs/agent_science_smoke_20260217T205540Z_scored.md`
  - `progress/agent_science/runs/agent_science_smoke_20260217T205540Z_scored.json`

## Result snapshot
- Contract gates: pass (`json_parse=1.000`, `schema=1.000`, `policy=1.000`)
- Rubric go/no-go: `2/4` agents pass
  - pass: `personal`, `ppc`
  - fail: `ceo`, `devops`

## Why CEO / DevOps failed
- CEO:
  - weighted score is above threshold, but `avg_cost=7.8` misses cost gate (`>=8`, i.e. <=1.5x eco target proxy).
- DevOps:
  - weighted score is above threshold, but `avg_cost=7.0` misses cost gate.

## Next corrective focus
1. Cost-policy tuning for `ceo` and `devops`:
   - shorter summaries by default in eco mode
   - tighter step/bullet caps where schema allows
2. Keep schema/policy enforcement unchanged (already stable).
3. Re-run same selector and verify all 4 agents pass rubric gates.

