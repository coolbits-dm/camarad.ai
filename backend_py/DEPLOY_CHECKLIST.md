# Camarad Deploy Checklist

1. `git rev-parse HEAD` (confirm release commit)
2. `python3 -m py_compile app.py database.py`
3. `python3 test_m3_scoping.py`
4. `python3 test_ga4_oauth.py`
5. `python3 test_plan_recommendations.py`
6. `pm2 restart camarad --update-env`
7. `bash scripts/smoke.sh`

## Notes
- Set `BILLING_INTERNAL_TOKEN` in shell/env before running smoke for billing checks.
- `readyz` may be optional depending on environment.
