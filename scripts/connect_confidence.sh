#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://camarad.ai}"
MODE="${MODE:-AUTHED}"               # AUTHED | MOCK
ATTEMPTS="${ATTEMPTS:-20}"
AUTH_COOKIE_HEADER="${AUTH_COOKIE_HEADER:-}"  # e.g. 'Cookie: camarad_user_id=1; camarad_cb_token=...; camarad_client_id=123'

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

fail() { echo "[connect-confidence][FAIL] $*" >&2; exit 1; }
warn() { echo "[connect-confidence][WARN] $*" >&2; }
info() { echo "[connect-confidence] $*"; }

if [[ "$MODE" != "AUTHED" && "$MODE" != "MOCK" ]]; then
  fail "Invalid MODE='$MODE'. Use MODE=AUTHED or MODE=MOCK."
fi

if [[ "$MODE" == "AUTHED" && -z "$AUTH_COOKIE_HEADER" ]]; then
  cat >&2 <<'USAGE'
[connect-confidence] AUTHED mode requires AUTH_COOKIE_HEADER.
Example:
  BASE_URL=https://camarad.ai \
  MODE=AUTHED \
  AUTH_COOKIE_HEADER='Cookie: camarad_user_id=1; camarad_cb_token=...; camarad_client_id=123' \
  scripts/connect_confidence.sh
USAGE
  exit 2
fi

strip_client_cookie_header() {
  local hdr="$1"
  local value="${hdr#Cookie: }"
  value="$(printf '%s' "$value" | sed -E 's/(^|;[[:space:]]*)camarad_client_id=[^;]*//g' | sed -E 's/^;[[:space:]]*//; s/;[[:space:]]*;/;/g; s/[[:space:]]+$//')"
  printf 'Cookie: %s' "$value"
}

request_with_retry() {
  # request_with_retry METHOD PATH OUT_PREFIX [DATA] [EXTRA_HEADER]
  local method="$1"
  local path="$2"
  local out_prefix="$3"
  local data="${4:-}"
  local extra_header="${5:-}"
  local url="${BASE_URL}${path}"
  local hdr_file="${out_prefix}.hdr"
  local body_file="${out_prefix}.body"
  local code_file="${out_prefix}.code"
  local attempt=1
  local code=""

  while [[ $attempt -le 5 ]]; do
    local cmd=(curl -sS -X "$method" -D "$hdr_file" -o "$body_file" -w '%{http_code}' "$url")
    if [[ "$MODE" == "AUTHED" ]]; then
      cmd+=(-H "$AUTH_COOKIE_HEADER")
    fi
    if [[ -n "$extra_header" ]]; then
      cmd+=(-H "$extra_header")
    fi
    if [[ -n "$data" ]]; then
      cmd+=(-H "Content-Type: application/json" --data "$data")
    fi

    code="$("${cmd[@]}" || true)"
    printf '%s' "$code" > "$code_file"

    if [[ "$code" =~ ^50[234]$ ]]; then
      sleep 1
      ((attempt++))
      continue
    fi
    break
  done
  printf '%s' "$code"
}

body_contains() {
  local file="$1"
  local needle="$2"
  grep -qi "$needle" "$file"
}

header_has_no_store() {
  local file="$1"
  grep -Eiq '^Cache-Control:.*(no-store|no-cache)' "$file"
}

summary_ga4=""
summary_ads=""

ga4_attempt() {
  local i="$1"
  local pfx="$TMP_DIR/ga4_${i}"

  # 1) auth-url
  local code
  code="$(request_with_retry GET "/api/connectors/ga4/auth-url" "${pfx}_auth")"
  [[ "$code" == "200" ]] || { summary_ga4="auth-url:$code"; return 1; }
  body_contains "${pfx}_auth.body" '"url"' || { summary_ga4="auth-url:no-url"; return 1; }

  # 2) callback path deterministic + no-store (no real Google code in curl harness)
  code="$(request_with_retry GET "/api/connectors/ga4/oauth/callback" "${pfx}_cb1")"
  [[ "$code" == "400" ]] || { summary_ga4="callback:$code"; return 1; }
  header_has_no_store "${pfx}_cb1.hdr" || { summary_ga4="callback:no-store-missing"; return 1; }
  code="$(request_with_retry GET "/api/connectors/ga4/oauth/callback" "${pfx}_cb2")"
  [[ "$code" == "400" ]] || { summary_ga4="callback-repeat:$code"; return 1; }

  if [[ "$MODE" == "MOCK" ]]; then
    summary_ga4="ok(mock)"
    return 0
  fi

  # 3) status
  code="$(request_with_retry GET "/api/connectors/ga4/status" "${pfx}_status")"
  [[ "$code" == "200" ]] || { summary_ga4="status:$code"; return 1; }

  # 4) property select (if route active)
  code="$(request_with_retry POST "/api/connectors/ga4/property" "${pfx}_prop" '{"propertyId":"properties/123456"}')"
  [[ "$code" =~ ^(200|400|502)$ ]] || { summary_ga4="property:$code"; return 1; }
  # Missing client scope should return 400 (only when we can strip client cookie and keep auth)
  local no_client_cookie
  no_client_cookie="$(strip_client_cookie_header "$AUTH_COOKIE_HEADER")"
  if [[ "$no_client_cookie" != "$AUTH_COOKIE_HEADER" ]]; then
    code="$(curl -sS -X POST -H "$no_client_cookie" -H "Content-Type: application/json" \
      -D "${pfx}_prop_nocid.hdr" -o "${pfx}_prop_nocid.body" -w '%{http_code}' \
      "${BASE_URL}/api/connectors/ga4/property" --data '{"propertyId":"properties/123456"}' || true)"
    [[ "$code" == "400" ]] || { summary_ga4="property-missing-scope:$code"; return 1; }
  else
    warn "Attempt $i: could not derive no-client cookie; missing-scope check skipped."
  fi

  # 5) one read endpoint with range
  code="$(request_with_retry GET "/api/connectors/ga4/overview?range=7days" "${pfx}_overview")"
  [[ "$code" == "200" ]] || { summary_ga4="overview:$code"; return 1; }

  summary_ga4="ok"
  return 0
}

ads_attempt() {
  local i="$1"
  local pfx="$TMP_DIR/ads_${i}"
  local code

  # 1) accounts
  code="$(request_with_retry GET "/api/connectors/google-ads/accounts" "${pfx}_accounts")"
  [[ "$code" == "200" ]] || { summary_ads="accounts:$code"; return 1; }

  # 2) campaigns with range-ish params
  code="$(request_with_retry GET "/api/connectors/google-ads/campaigns?days=30" "${pfx}_campaigns")"
  [[ "$code" == "200" ]] || { summary_ads="campaigns:$code"; return 1; }

  # 3) one read metrics endpoint
  code="$(request_with_retry GET "/api/connectors/google-ads/metrics?days=7" "${pfx}_metrics")"
  [[ "$code" == "200" ]] || { summary_ads="metrics:$code"; return 1; }

  summary_ads="ok"
  return 0
}

printf "\n%-8s | %-8s | %-8s | %s\n" "ATTEMPT" "GA4" "ADS" "SUMMARY"
printf -- "-------------------------------------------------------------\n"

pass_count=0
for i in $(seq 1 "$ATTEMPTS"); do
  ga4_ok="FAIL"
  ads_ok="FAIL"
  summary_ga4="-"
  summary_ads="-"

  if ga4_attempt "$i"; then ga4_ok="OK"; fi
  if ads_attempt "$i"; then ads_ok="OK"; fi

  local_summary="ga4=${summary_ga4}; ads=${summary_ads}"
  printf "%-8s | %-8s | %-8s | %s\n" "$i" "$ga4_ok" "$ads_ok" "$local_summary"

  if [[ "$ga4_ok" == "OK" && "$ads_ok" == "OK" ]]; then
    ((pass_count+=1))
  fi
done

info "Result: ${pass_count}/${ATTEMPTS} attempts passed."
if [[ "$pass_count" -ne "$ATTEMPTS" ]]; then
  exit 1
fi
exit 0
