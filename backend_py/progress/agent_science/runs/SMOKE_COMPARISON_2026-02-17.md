# Agent Science Smoke Comparison (2026-02-17)

Runs compared:
- Baseline (simulated/cheap): `agent_science_smoke_20260217T204457Z`
- Comparative (`allow_real=true`): `agent_science_smoke_20260217T204630Z`

## Totals
- HTTP 200 rate: `1.000` -> `1.000`
- JSON parse rate: `0.750` -> `0.300`
- Schema compliance rate: `0.000` -> `0.000`
- Policy compliance rate: `0.000` -> `0.300`

## Per-agent signals
- `personal`
  - schema compliance (eco/deep): `0.000/0.000` -> `0.000/0.000`
  - policy compliance (eco/deep): `0.000/0.000` -> `1.000/0.000`
- `ppc`
  - schema compliance (eco/deep): `0.000/0.000` -> `0.000/0.000`
  - policy compliance (eco/deep): `0.000/0.000` -> `1.000/0.000`
- `ceo`
  - schema compliance (eco/deep): `0.000/0.000` -> `0.000/0.000`
  - policy compliance (eco/deep): `0.000/0.000` -> `0.400/0.000`
- `devops`
  - schema compliance (eco/deep): `0.000/0.000` -> `0.000/0.000`
  - policy compliance (eco/deep): `0.000/0.000` -> `0.000/0.000`

## Conclusion
- Enabling real responses improved partial policy-field behavior for some eco runs.
- Strict schema compliance remains `0.000` in both runs.
- Deep-mode policy behavior (`why_deep`) is still non-compliant in practice.

## Immediate priority
1. Enforce schema envelope at response layer (eval path).
2. Enforce deep policy contract (`policy_used=deep`, non-empty `why_deep`).
3. Re-run same selector to validate deltas against these two runs.

