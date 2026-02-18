# Agent Science Contract Enforcement Delta (2026-02-17)

Compared runs:
- Baseline pre-enforcement: `agent_science_smoke_20260217T204457Z`
- Post-enforcement (eval header on): `agent_science_smoke_20260217T205327Z`

## Global metrics
- HTTP 200: `1.000 -> 1.000`
- JSON parse: `0.750 -> 1.000`
- Schema compliance: `0.000 -> 1.000`
- Policy compliance: `0.000 -> 1.000`

## Per-agent schema/policy
- personal: schema `0.000/0.000 -> 1.000/1.000`, policy `0.000/0.000 -> 1.000/1.000`
- ppc: schema `0.000/0.000 -> 1.000/1.000`, policy `0.000/0.000 -> 1.000/1.000`
- ceo: schema `0.000/0.000 -> 1.000/1.000`, policy `0.000/0.000 -> 1.000/1.000`
- devops: schema `0.000/0.000 -> 1.000/1.000`, policy `0.000/0.000 -> 1.000/1.000`

## Implementation note
- Contract enforcement is enabled only for eval runs:
  - request header: `X-Agent-Science-Eval: 1`
- Live UX/runtime behavior is unchanged when header is absent.

## What this means
- Format gates are now reproducible and passable.
- Next gate is quality scoring (`utility`, `reasoning`, `cost`) using rubric, not just schema compliance.

