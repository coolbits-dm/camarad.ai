#!/usr/bin/env bash
set -euo pipefail

TOKEN="${1:-}"
if [[ -z "$TOKEN" ]]; then
  echo "Usage: $0 beta_u1 [window_minutes]"
  exit 1
fi

WINDOW_MINUTES="${2:-180}"

# Candidate log locations (first existing wins)
LOGS=(
  "/var/log/nginx/access.log"
  "/var/log/nginx/access.log.1"
  "/opt/camarad/logs/access.log"
)

FOUND=()
for f in "${LOGS[@]}"; do
  [[ -f "$f" ]] && FOUND+=("$f")
done

if [[ ${#FOUND[@]} -eq 0 ]]; then
  echo "[beta-trace-v2] No access logs found in known paths."
  exit 2
fi

echo "=== Beta Trace v2 ==="
echo "token: $TOKEN"
echo "window_minutes: $WINDOW_MINUTES"
echo "log_files: ${FOUND[*]}"

# 1) Find first/last hit containing src token and capture IP.
TOKEN_LINES="$(rg -n "src=${TOKEN}" "${FOUND[@]}" || true)"
if [[ -z "$TOKEN_LINES" ]]; then
  echo "[beta-trace-v2] No lines found for src=${TOKEN}."
  exit 3
fi

FIRST_LINE="$(printf "%s\n" "$TOKEN_LINES" | head -n1)"
LAST_LINE="$(printf "%s\n" "$TOKEN_LINES" | tail -n1)"

# line format from rg with multiple files: file:line:content
FIRST_CONTENT="$(printf "%s\n" "$FIRST_LINE" | sed -E 's/^[^:]+:[0-9]+://')"
LAST_CONTENT="$(printf "%s\n" "$LAST_LINE" | sed -E 's/^[^:]+:[0-9]+://')"

FIRST_IP="$(printf "%s\n" "$FIRST_CONTENT" | awk '{print $1}')"
LAST_IP="$(printf "%s\n" "$LAST_CONTENT" | awk '{print $1}')"

echo ""
echo "[beta-trace-v2] token first hit:"
echo "$FIRST_LINE"
echo "[beta-trace-v2] token last hit:"
echo "$LAST_LINE"
echo "[beta-trace-v2] inferred IPs: first=$FIRST_IP last=$LAST_IP"

# 2) Build endpoint filters for funnel and chat activity.
ENDPOINT_RE='/(\\?|$)|/platform-demo|/chat-demo|/signup|/chat/|/api/chat|/api/conversations|/api/chats'

echo ""
echo "[beta-trace-v2] Funnel/event lines by token:"
printf "%s\n" "$TOKEN_LINES" | tail -n 80

echo ""
echo "[beta-trace-v2] Candidate session lines by first IP + funnel endpoints (tail 200):"
rg -n "^[[:space:]]*${FIRST_IP}[[:space:]].*(/|/platform-demo|/chat-demo|/signup|/chat/|/api/chat|/api/conversations|/api/chats)" "${FOUND[@]}" | tail -n 200 || true

if [[ "$LAST_IP" != "$FIRST_IP" ]]; then
  echo ""
  echo "[beta-trace-v2] Candidate session lines by last IP + funnel endpoints (tail 200):"
  rg -n "^[[:space:]]*${LAST_IP}[[:space:]].*(/|/platform-demo|/chat-demo|/signup|/chat/|/api/chat|/api/conversations|/api/chats)" "${FOUND[@]}" | tail -n 200 || true
fi

echo ""
echo "[beta-trace-v2] Quick extraction hints:"
echo "- landing_view: first line containing 'src=${TOKEN}'"
echo "- demo_open: first '/platform-demo' or '/chat-demo' in same IP session block"
echo "- signup_click: first '/signup' in same IP session block"
echo "- first_chat_send: first POST to '/chat/<ws>/<agent>' or '/api/chat' after signup"
echo "- compute TTFUO manually from tester feedback timestamp + first useful response moment"

