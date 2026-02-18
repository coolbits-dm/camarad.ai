#!/usr/bin/env bash
set -euo pipefail

TOKEN="${1:-}"
LOG_FILE="${2:-/opt/camarad/logs/access.log}"

if [[ -z "$TOKEN" ]]; then
  echo "Usage: $0 beta_u1 [/opt/camarad/logs/access.log]"
  exit 1
fi

if [[ ! -f "$LOG_FILE" ]]; then
  echo "[beta-watch] log file not found: $LOG_FILE"
  exit 1
fi

echo "[beta-watch] token=$TOKEN log=$LOG_FILE"
echo "[beta-watch] watching for: landing -> demo -> signup -> first_chat_send"

tail -Fn0 "$LOG_FILE" | while IFS= read -r line; do
  if [[ "$line" == *"src=${TOKEN}"* ]] || \
     [[ "$line" == *" /platform-demo"* ]] || \
     [[ "$line" == *" /chat-demo"* ]] || \
     [[ "$line" == *" /signup"* ]] || \
     [[ "$line" == *"\"POST /chat/"* ]] || \
     [[ "$line" == *"\"POST /api/chat"* ]] || \
     [[ "$line" == *"\"POST /api/chats"* ]]; then
    echo "$line"
  fi
done
