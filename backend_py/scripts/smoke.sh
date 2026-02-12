#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://camarad.ai}"
API_URL="${API_URL:-https://camarad.ai}"
INTERNAL_TOKEN="${BILLING_INTERNAL_TOKEN:-}"

fail() { echo "[smoke][FAIL] $*" >&2; exit 1; }
ok()   { echo "[smoke][OK] $*"; }

printf '[smoke] BASE_URL=%s\n' "$BASE_URL"
printf '[smoke] API_URL=%s\n' "$API_URL"

curl -fsS "$BASE_URL/healthz" >/dev/null || fail "healthz failed"
ok "healthz"

if curl -fsS "$BASE_URL/readyz" >/dev/null 2>&1; then
  ok "readyz"
else
  echo "[smoke][WARN] readyz unavailable (skipped)"
fi

hdrs="$(curl -sSI "$API_URL/api/connectors/ga4/oauth/callback" || true)"
printf '%s\n' "$hdrs" | sed -n '1,20p'
printf '%s\n' "$hdrs" | grep -Eiq '^HTTP/.* (200|400|401|403|404)' || fail "GA4 callback status unexpected"
printf '%s\n' "$hdrs" | grep -Eiq '^Cache-Control:.*no-store' || fail "GA4 callback missing Cache-Control: no-store"
ok "ga4 callback headers (no-store)"

if [[ -z "$INTERNAL_TOKEN" ]]; then
  echo "[smoke][WARN] BILLING_INTERNAL_TOKEN not set; skipping internal billing checks"
  echo "[smoke] done"
  exit 0
fi

code="$(curl -sS -o /dev/null -w '%{http_code}' "$API_URL/api/billing/cost-telemetry?window=48" || true)"
[[ "$code" == "403" ]] || fail "cost-telemetry without token expected 403, got $code"
ok "billing cost-telemetry 403 without token"

code="$(curl -sS -o /dev/null -w '%{http_code}' -H "X-Internal-Token: $INTERNAL_TOKEN" "$API_URL/api/billing/cost-telemetry?window=48" || true)"
[[ "$code" == "200" ]] || fail "cost-telemetry with token expected 200, got $code"
ok "billing cost-telemetry 200 with token"

code="$(curl -sS -o /dev/null -w '%{http_code}' -H "X-Internal-Token: $INTERNAL_TOKEN" "$API_URL/api/billing/plan-recommendations?window_days=7" || true)"
[[ "$code" == "200" ]] || fail "plan-recommendations expected 200, got $code"
ok "billing plan-recommendations 200"

echo "[smoke] done"
