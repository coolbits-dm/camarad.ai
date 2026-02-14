#!/usr/bin/env bash
set -euo pipefail

TOKEN="${1:-}"
if [[ -z "$TOKEN" ]]; then
  echo "Usage: $0 beta_u1"
  exit 1
fi

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
  echo "No access logs found in known paths."
  exit 2
fi

echo "=== Trace for token: $TOKEN ==="
for f in "${FOUND[@]}"; do
  echo "\n--- $f ---"
  rg -n "src=${TOKEN}|/platform-demo|/chat-demo|/signup|/api/chat|/api/conversations|/chat" "$f" | rg "$TOKEN|/platform-demo|/chat-demo|/signup|/api/chat|/api/conversations|/chat" | tail -n 200 || true
done

echo "\nTip: extract first timestamps for /, demo, signup, first chat send to compute TTFUO."
