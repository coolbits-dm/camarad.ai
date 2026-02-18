# Agent Science Smoke Baseline Summary (2026-02-17)

Run artifact:
- `progress/agent_science/runs/agent_science_smoke_20260217T204457Z.md`
- `progress/agent_science/runs/agent_science_smoke_20260217T204457Z.json`

Run configuration:
- selector: `TASKPACK_SMOKE_SELECTOR_V1` (20 tasks, 5/agent)
- matrix: `eco + deep` (40 total runs)
- mode: local test-client, `allow_real=false` (cheap deterministic baseline)

Headline results:
- HTTP 200 rate: `1.000`
- JSON parse rate: `0.750`
- Schema compliance rate: `0.000`
- Policy compliance rate (`policy_used`, `why_deep`): `0.000`

Per-agent schema compliance:
- personal: eco `0.000`, deep `0.000`
- ppc: eco `0.000`, deep `0.000`
- ceo: eco `0.000`, deep `0.000`
- devops: eco `0.000`, deep `0.000`

Top failure reasons:
1. `policy_fields_missing_or_wrong`: 40/40
2. `schema_mismatch`: 30/40
3. `non_json_response`: 10/40 (all from PPC tasks in this run)

Cost proxy (deep vs eco, estimated tokens):
- personal: `1.016x`
- ppc: `1.000x`
- ceo: `0.977x`
- devops: `1.007x`

Interpretation:
- Routing stack is stable, but Agent Science output contract is not enforced yet.
- Current chat responses are mostly free-form and do not satisfy strict schema gates.
- Baseline is now concrete and reproducible; next run should target format/policy enforcement.

Next corrective run:
1. Add eval-only output contract layer (strict JSON envelope per schema).
2. Enforce `policy_used` and `why_deep` behavior for deep mode.
3. Rerun same selector and compare deltas against this baseline.

