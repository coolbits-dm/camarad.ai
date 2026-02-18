# Beta Gate Pack - Agent Science v1 (2026-02-17)

Purpose:
- Single go/no-go checklist for launching next controlled external beta wave.
- Consolidates smoke, eval, quality, and runtime safety artifacts.

## Gate Scope
- Agent Science v1 (4 agents): `personal`, `ppc`, `ceo`, `devops`
- Policies: `eco` + `deep`
- Sets: smoke selector + full TaskPack A/B

## Required Artifacts (must exist)
- Smoke selector:
  - `progress/agent_science/TASKPACK_SMOKE_SELECTOR_V1.md`
- Smoke baseline + enforcement deltas:
  - `progress/agent_science/runs/agent_science_smoke_20260217T204457Z.md`
  - `progress/agent_science/runs/SMOKE_ENFORCEMENT_DELTA_2026-02-17.md`
- Full eval pass:
  - `progress/agent_science/runs/agent_science_full_20260217T210117Z.md`
  - `progress/agent_science/runs/agent_science_full_20260217T210117Z_scored.md`
  - `progress/agent_science/runs/FULL_EVAL_SUMMARY_2026-02-17.md`
- Real quality track + remediation pass:
  - `progress/agent_science/runs/agent_science_quality_20260217T225135Z.md`
  - `progress/agent_science/runs/QUALITY_GAP_REPORT_2026-02-17.md`
  - `progress/agent_science/runs/agent_science_quality_20260217T235148Z.md`
  - `progress/agent_science/runs/QUALITY_REMEDIATION_PASS_2026-02-17.md`

## Acceptance Checklist
1. Contract gate (eval path):
   - json parse rate = `1.000`
   - schema compliance = `1.000`
   - policy compliance = `1.000`
2. Rubric gate (full A+B):
   - all 4 agents `go_no_go=true`
3. Quality gate (real responses, quality track mode):
   - personal >= `9.0`
   - ppc >= `8.5`
   - ceo >= `8.0`
   - devops >= `8.0`
4. Runtime safety gate:
   - `scripts/smoke.sh` green
   - `scripts/connect_confidence.sh` green (AUTHED)
   - no regressions in search split (`/api/search`, `/api/app/search`)
5. Security gate:
   - M3 anti-leak tests pass (`test_m3_scoping.py`)

## Runtime/Ops Verification (pre-beta)
```bash
# smoke
cd /opt/camarad && BILLING_INTERNAL_TOKEN="$(grep -E '^BILLING_INTERNAL_TOKEN=' .env | cut -d= -f2-)" bash scripts/smoke.sh

# confidence (authed)
cd /opt/camarad && MODE=AUTHED BASE_URL=https://camarad.ai ATTEMPTS=20 AUTH_COOKIE_HEADER='Cookie: camarad_user_id=1; camarad_client_id=1' bash scripts/connect_confidence.sh

# key tests
cd /opt/camarad && /opt/camarad/.venv/bin/python test_m3_scoping.py && /opt/camarad/.venv/bin/python test_ga4_oauth.py && /opt/camarad/.venv/bin/python test_plan_recommendations.py
```

## Go / No-Go Note
- Decision: `GO (controlled beta)` if all checklist items above are green in the same run window.
- Constraints:
  - keep `BILLING_PHASE3_ENABLED=0` during first external beta wave
  - preserve demo/public mode and route compatibility without `/app`
  - no auth/core connector rewrites during beta execution window

## Rollback/Containment
- If any runtime regression appears:
  1. stop beta invites
  2. keep traffic to current stable path
  3. rerun smoke + confidence + M3 tests
  4. reopen gate only after green re-validation

