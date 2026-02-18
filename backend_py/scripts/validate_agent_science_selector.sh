#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.}"
SEL="$ROOT/progress/agent_science/TASKPACK_SMOKE_SELECTOR_V1.md"
A="$ROOT/progress/agent_science/TASKPACK_A_V1.md"
B="$ROOT/progress/agent_science/TASKPACK_B_V1.md"

if [[ ! -f "$SEL" || ! -f "$A" || ! -f "$B" ]]; then
  echo "[validate-selector] missing required files under $ROOT"
  exit 1
fi

python3 - "$SEL" "$A" "$B" <<'PY'
import re
import sys
from pathlib import Path

sel_path, a_path, b_path = [Path(p) for p in sys.argv[1:4]]
sel = sel_path.read_text(encoding="utf-8")
a = a_path.read_text(encoding="utf-8")
b = b_path.read_text(encoding="utf-8")

id_pat = re.compile(r"^(PERS|PPC|CEO|DEV)-\d{2}$|^(PA_B|PPC_B|CEO_B|DO_B)_\d{2}$")
selected = set(
    x for x in re.findall(r"`([A-Za-z0-9_\-]+)`", sel)
    if id_pat.match(x)
)
existing = set(re.findall(r"task_id:\s*`([^`]+)`", a + "\n" + b))
missing = sorted(selected - existing)

if len(selected) != 20:
    print(f"[validate-selector] FAIL: expected 20 ids, got {len(selected)}")
    sys.exit(1)
if missing:
    print("[validate-selector] FAIL: missing ids:")
    for m in missing:
        print(f"  - {m}")
    sys.exit(1)

print("[validate-selector] OK")
print(f"[validate-selector] selected_ids={len(selected)} existing_ids={len(existing)}")
PY

