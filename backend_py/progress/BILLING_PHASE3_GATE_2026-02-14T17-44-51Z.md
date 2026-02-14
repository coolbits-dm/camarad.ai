# Billing Phase 3 Design Gate

Date: 2026-02-14 17:44:51Z

## Current Snapshot

- Gate status: **GO**
- calibration_proposal(48h).insufficient_data: `False`
- reasons: `[]`
- current_ct_value_usd: `0.0001`
- implied_ct_value_usd: `0.0001892647`
- proposed_ct_value_usd: `0.0001045`

## Coverage (48h)

- rows_with_tokens: `1800`
- rows_with_billable: `1800`
- ct_actual_sum: `30600`
- billable_sum_usd: `5.7915`

## Gate Thresholds (for Phase 3 enable)

- rows_with_tokens_min: `500`
- rows_with_billable_min: `500`
- ct_actual_sum_min: `10000`
- billable_sum_usd_min: `5.0`
- max_delta_pct: `0.15`

## Decision

- Decision: **GO** for controlled Phase 3 enable behind env flag.
- Enable window: 24-48h monitored rollout.

## Operator Runbook (Rollback-ready)

1. Keep `BILLING_PHASE3_ENABLED=0` until gate is GO.
2. On GO: set `BILLING_PHASE3_ENABLED=1`, restart PM2 with `--update-env`.
3. Monitor 48h:
   - `/api/billing/cost-telemetry?window=24`
   - cap hit rates (429/402)
   - support complaints / false positives
4. Instant rollback:
   - set `BILLING_PHASE3_ENABLED=0`
   - `pm2 restart camarad --update-env`
   - verify smoke + billing endpoints

## Reference Files

- `progress/baseline_2026-02-14T11-47-44Z/*`
- `progress/BETA_READINESS_2026-02-14T11-58-04Z.md`
- `progress/BILLING_PHASE3_GATE_2026-02-14T17-44-51Z.md`
