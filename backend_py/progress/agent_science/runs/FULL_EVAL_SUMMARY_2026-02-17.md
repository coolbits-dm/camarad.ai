# Agent Science Full Eval Summary (2026-02-17)

Run artifacts:
- `progress/agent_science/runs/agent_science_full_20260217T210117Z.md`
- `progress/agent_science/runs/agent_science_full_20260217T210117Z.json`
- `progress/agent_science/runs/agent_science_full_20260217T210117Z_scored.md`
- `progress/agent_science/runs/agent_science_full_20260217T210117Z_scored.json`

Scope:
- Task set: full `A+B` (80 tasks total)
- Policy matrix: `eco + deep` (160 total runs)
- Mode: eval-header contract path enabled

## Contract metrics
- HTTP 200 rate: `1.000`
- JSON parse rate: `1.000`
- Schema compliance rate: `1.000`
- Policy compliance rate: `1.000`

## Rubric result
- `personal`: pass
- `ppc`: pass
- `ceo`: pass
- `devops`: pass
- Overall: `4/4` pass on go/no-go.

## Cost proxy (deep vs eco)
- personal: `1.071x`
- ppc: `1.071x`
- ceo: `1.067x`
- devops: `1.069x`

## Decision
- Agent Science Pack v1 passes full-pack eval gate under current eval contract.
- Next step: optional quality-hardening track (real-response quality under same schema gates), then controlled beta feedback loop.

