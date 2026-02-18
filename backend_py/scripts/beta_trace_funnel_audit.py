#!/usr/bin/env python3
import argparse
from datetime import datetime, timezone
from pathlib import Path
import re

from build_beta_run_b_debrief import _load_latest_trace, _parse_log_events, _extract_trace_summary

TOKENS = ["beta_u1", "beta_u2", "beta_u3"]
WINDOW_SECONDS = 45 * 60


def _now_tag():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _latest_trace_file(trace_dir: Path, token: str):
    files = sorted(trace_dir.glob(f"*{token}*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _raw_event_counts(events, token: str):
    return {
        "landing_hits": sum(1 for e in events if e["method"] == "GET" and f"src={token}" in e["path"]),
        "demo_hits": sum(
            1 for e in events if e["method"] == "GET" and ("/platform-demo" in e["path"] or "/chat-demo" in e["path"])
        ),
        "signup_hits": sum(1 for e in events if e["method"] == "GET" and "/signup" in e["path"]),
        "first_chat_send_hits": sum(
            1
            for e in events
            if e["method"] == "POST"
            and ("/chat/" in e["path"] or "/api/chat" in e["path"] or "/api/chats" in e["path"])
        ),
    }


def _recommendation(missing):
    if not missing:
        return "Session complete."
    if missing == ["first_chat_send"]:
        return "Reached signup but no chat send; improve post-signup CTA to first message."
    if "signup" in missing:
        return "Did not reach signup; improve demo->signup CTA visibility and copy."
    if "demo" in missing:
        return "Did not open demo; re-check landing CTA prominence/path consistency."
    return "Re-run with live watcher and explicit guided test flow."


def run_token(trace_dir: Path, token: str):
    source_file = _latest_trace_file(trace_dir, token)
    text = _load_latest_trace(trace_dir, token)
    if not text:
        return {
            "token": token,
            "status": "fail",
            "landing": "False",
            "demo": "False",
            "signup": "False",
            "first_chat_send": "False",
            "missing": "landing",
            "recommendation": "No trace file found for token.",
            "source": str(source_file) if source_file else "-",
            "events_total": 0,
            "landing_hits": 0,
            "demo_hits": 0,
            "signup_hits": 0,
            "first_chat_send_hits": 0,
        }

    events = _parse_log_events(text)
    counts = _raw_event_counts(events, token)
    summary = _extract_trace_summary(text, token)
    missing = []
    if not summary["demo"]:
        missing.append("demo")
    if not summary["signup"]:
        missing.append("signup")
    if not summary["first_chat_send"]:
        missing.append("first_chat_send")
    status = "pass" if summary["completed"] else "fail"
    return {
        "token": token,
        "status": status,
        "landing": str(summary["landing"]),
        "demo": str(summary["demo"]),
        "signup": str(summary["signup"]),
        "first_chat_send": str(summary["first_chat_send"]),
        "missing": ",".join(missing),
        "recommendation": _recommendation(missing),
        "source": str(source_file) if source_file else "-",
        "events_total": len(events),
        **counts,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/opt/camarad")
    ap.add_argument("--trace-dir", default="logs/beta_traces")
    ap.add_argument("--out", default=None, help="Output markdown file")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    root = Path(args.root)
    trace_dir = Path(args.trace_dir)
    if not trace_dir.is_absolute():
        trace_dir = root / trace_dir
    out_path = Path(args.out) if args.out else root / "progress" / f"BETA_RUN_B_FUNNEL_AUDIT_{_now_tag()}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = [run_token(trace_dir, token) for token in TOKENS]
    pass_count = sum(1 for r in rows if r["status"] == "pass")

    old_debrief_path = root / "progress" / "BETA_RUN_B_DEBRIEF_2026-02-18T00-46-38Z.md"
    old_debrief_line = ""
    if old_debrief_path.exists():
        txt = old_debrief_path.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"complete traces:\s*`([^`]+)`", txt)
        old_debrief_line = m.group(1) if m else ""

    lines = [
        f"# Beta Run B Funnel Audit ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')})",
        "",
        "## Method",
        "- source of truth: latest per-token trace file from `logs/beta_traces` (same source as debrief generator)",
        f"- session window: `{WINDOW_SECONDS}s` post-landing, same-User-Agent matching (same logic as `build_beta_run_b_debrief.py`)",
        "- event defs: landing=`GET /?src=beta_uX`, demo=`GET /platform-demo|/chat-demo`, signup=`GET /signup`, first_chat_send=`POST /chat/*|/api/chat|/api/chats`",
        "",
        "## Sources Read",
        "| Token | Trace file | Parsed log events |",
        "|---|---|---:|",
    ]
    for r in rows:
        lines.append(f"| {r['token']} | {r['source']} | {r['events_total']} |")

    lines.extend(
        [
            "",
            "## Funnel Verdict",
            "| Token | Status | Landing | Demo | Signup | First Chat Send | Missing | Recommendation |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    for r in rows:
        lines.append(
            f"| {r['token']} | {r['status']} | {r['landing']} | {r['demo']} | {r['signup']} | {r['first_chat_send']} | {r['missing'] or '-'} | {r['recommendation'] or '-'} |"
        )

    lines.extend(
        [
            "",
            "## Raw Event Counts (in selected trace file)",
            "| Token | landing_hits | demo_hits | signup_hits | first_chat_send_hits |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for r in rows:
        lines.append(
            f"| {r['token']} | {r['landing_hits']} | {r['demo_hits']} | {r['signup_hits']} | {r['first_chat_send_hits']} |"
        )

    lines.extend(
        [
            "",
            "## Summary",
            f"- pass_count: `{pass_count}/3`",
            "- gate condition: `3/3 complete` before external beta expansion",
            "",
            "## Root Cause (3 bullets)",
            "1. Initial debrief version (`...00-46-38Z`) used permissive text matching over whole trace dump and could count hint lines / unrelated curl probes as funnel events.",
            "2. Audit scripts switched to parsed nginx-style log events and session-scoped matching; this removed false positives and exposed real missing steps.",
            "3. Source mismatch risk existed across helper scripts; this audit now uses the same trace source and event logic as current debrief parser.",
            "",
            "## What Changed",
            "- `beta_trace_funnel_audit.py` now consumes same source + logic as debrief (`build_beta_run_b_debrief.py`).",
            "- Added explicit `Method`, `Sources Read`, and `Raw Event Counts` sections for evidence.",
            "- Added `--verbose` option to print per-token sources and counts.",
            "",
            "## Remaining Limitation",
            "- If a user journey happens mostly client-side without corresponding origin log requests, server-log-based audit cannot observe that step; manual feedback/event beacon is still needed.",
        ]
    )
    if old_debrief_line:
        lines.append(f"- historical note: old debrief reported `complete traces: {old_debrief_line}` before parser hardening.")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[funnel-audit] wrote {out_path}")
    if args.verbose:
        for r in rows:
            print(
                f"[funnel-audit][verbose] token={r['token']} source={r['source']} events={r['events_total']} "
                f"landing_hits={r['landing_hits']} demo_hits={r['demo_hits']} signup_hits={r['signup_hits']} "
                f"first_chat_send_hits={r['first_chat_send_hits']} status={r['status']}"
            )


if __name__ == "__main__":
    main()
