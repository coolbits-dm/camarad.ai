#!/usr/bin/env bash
set -euo pipefail

TOKEN="${1:-}"
if [[ -z "$TOKEN" ]]; then
  echo "Usage: $0 beta_u1"
  exit 1
fi

ROOT="${2:-/opt/camarad}"
OUT_DIR="$ROOT/logs/beta_traces"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "$OUT_DIR"

LEGACY_OUT="$OUT_DIR/trace_${TOKEN}_${TS}.log"
V2_OUT="$OUT_DIR/trace_v2_${TOKEN}_${TS}.log"

echo "[beta-trace-save] token=$TOKEN"
echo "[beta-trace-save] legacy=$LEGACY_OUT"
echo "[beta-trace-save] v2=$V2_OUT"

bash "$ROOT/scripts/beta_trace_collect.sh" "$TOKEN" | tee "$LEGACY_OUT"
bash "$ROOT/scripts/beta_trace_collect_v2.sh" "$TOKEN" | tee "$V2_OUT"

echo "[beta-trace-save] done"

