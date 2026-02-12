#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://camarad.ai}"
API_URL="${API_URL:-https://camarad.ai}"
INTERNAL_TOKEN="${BILLING_INTERNAL_TOKEN:-}"

fail() { echo "[smoke][FAIL] $*" >&2; exit 1; }
ok()   { echo "[smoke][OK] $*"; }
retry() {
  # retry <attempts> <sleep_seconds> <cmd...>
  local attempts="$1"; shift
  local sleep_s="$1"; shift
  local n=1
  until "$@"; do
    if [[ $n -ge $attempts ]]; then
      return 1
    fi
    sleep "$sleep_s"
    n=$((n + 1))
  done
  return 0
}

wait_http_ok() {
  # wait_http_ok <url> <seconds_total>
  local url="$1"
  local total="$2"
  local end=$((SECONDS + total))
  while [[ $SECONDS -lt $end ]]; do
    code="$(curl -sS -o /dev/null -w '%{http_code}' "$url" || true)"
    if [[ "$code" =~ ^2[0-9][0-9]$ ]]; then
      return 0
    fi
    sleep 2
  done
  return 1
}

printf '[smoke] BASE_URL=%s\n' "$BASE_URL"
printf '[smoke] API_URL=%s\n' "$API_URL"

wait_http_ok "$BASE_URL/healthz" 30 || fail "healthz did not become 2xx within 30s"
ok "healthz"

wait_http_ok "$BASE_URL/" 30 || fail "landing did not become 2xx within 30s"
ok "landing /"

wait_http_ok "$BASE_URL/signup" 30 || fail "signup did not become 2xx within 30s"
ok "signup"

wait_http_ok "$BASE_URL/chat-demo" 30 || fail "chat-demo did not become 2xx within 30s"
ok "chat-demo"

wait_http_ok "$BASE_URL/api/search?q=ppc" 30 || fail "public search did not become 2xx within 30s"
ok "public search /api/search"

app_search_hdrs="$(curl -sSI "$BASE_URL/api/app/search?q=ppc" || true)"
app_search_code="$(printf '%s\n' "$app_search_hdrs" | awk 'BEGIN{IGNORECASE=1} /^HTTP\//{print $2; exit}')"
[[ "$app_search_code" == "401" ]] || fail "app search without auth expected 401, got ${app_search_code:-none}"
printf '%s\n' "$app_search_hdrs" | grep -Eiq '^Cache-Control:.*no-store' || fail "app search missing Cache-Control: no-store"
ok "app search protected (401 + no-store)"

code="$(curl -sS -o /dev/null -w '%{http_code}' "$BASE_URL/readyz" || true)"
if [[ "$code" == "404" ]]; then
  ok "readyz (not implemented)"
else
  wait_http_ok "$BASE_URL/readyz" 30 || fail "readyz did not become 2xx within 30s"
  ok "readyz"
fi

hdrs="$(curl -sSI "$API_URL/api/connectors/ga4/oauth/callback" || true)"
printf '%s\n' "$hdrs" | sed -n '1,20p'
printf '%s\n' "$hdrs" | grep -Eiq '^HTTP/.* 400' || fail "GA4 callback expected 400 without OAuth params"
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

retry 6 2 bash -lc "code=\"\$(curl -sS -o /dev/null -w '%{http_code}' -H 'X-Internal-Token: $INTERNAL_TOKEN' '$API_URL/api/billing/cost-telemetry?window=48' || true)\"; [[ \"\$code\" == \"200\" ]]"
[[ $? -eq 0 ]] || fail "cost-telemetry with token expected 200"
ok "billing cost-telemetry 200 with token"

retry 6 2 bash -lc "code=\"\$(curl -sS -o /dev/null -w '%{http_code}' -H 'X-Internal-Token: $INTERNAL_TOKEN' '$API_URL/api/billing/plan-recommendations?window_days=7' || true)\"; [[ \"\$code\" == \"200\" ]]"
[[ $? -eq 0 ]] || fail "plan-recommendations expected 200"
ok "billing plan-recommendations 200"

echo "[smoke] done"
