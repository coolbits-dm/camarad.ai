#!/usr/bin/env python3
import argparse
from datetime import datetime, timezone
from pathlib import Path
import subprocess

TOKENS = ["beta_u1", "beta_u2", "beta_u3"]


def _now_tag():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def run_goal_check(root: Path, token: str, trace_dir: str):
    cmd = [
        str(root / ".venv" / "bin" / "python"),
        str(root / "scripts" / "beta_trace_goal_check.py"),
        token,
        "--trace-dir",
        trace_dir,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    lines = [ln.strip() for ln in res.stdout.splitlines() if ln.strip()]
    out = {
        "token": token,
        "status": "fail",
        "landing": "False",
        "demo": "False",
        "signup": "False",
        "first_chat_send": "False",
        "missing": "",
        "recommendation": "",
    }
    for ln in lines:
        if ln.startswith("[goal-check] status="):
            out["status"] = ln.split("=", 1)[1].strip()
        elif ln.startswith("[goal-check] funnel "):
            payload = ln.replace("[goal-check] funnel ", "")
            for part in payload.split():
                if "=" in part:
                    k, v = part.split("=", 1)
                    out[k] = v
        elif ln.startswith("[goal-check] missing="):
            out["missing"] = ln.split("=", 1)[1].strip()
        elif ln.startswith("[goal-check] recommendation="):
            out["recommendation"] = ln.split("=", 1)[1].strip()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/opt/camarad")
    ap.add_argument("--trace-dir", default="logs/beta_traces")
    ap.add_argument("--out", default=None, help="Output markdown file")
    args = ap.parse_args()

    root = Path(args.root)
    out_path = Path(args.out) if args.out else root / "progress" / f"BETA_RUN_B_FUNNEL_AUDIT_{_now_tag()}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = [run_goal_check(root, token, args.trace_dir) for token in TOKENS]
    pass_count = sum(1 for r in rows if r["status"] == "pass")

    lines = [
        f"# Beta Run B Funnel Audit ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')})",
        "",
        "| Token | Status | Landing | Demo | Signup | First Chat Send | Missing | Recommendation |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['token']} | {r['status']} | {r['landing']} | {r['demo']} | {r['signup']} | {r['first_chat_send']} | {r['missing'] or '-'} | {r['recommendation'] or '-'} |"
        )

    lines.extend(
        [
            "",
            "## Summary",
            f"- pass_count: `{pass_count}/3`",
            "- gate condition: `3/3 complete` before external beta expansion",
        ]
    )
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[funnel-audit] wrote {out_path}")


if __name__ == "__main__":
    main()
