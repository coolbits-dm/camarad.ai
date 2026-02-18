#!/usr/bin/env python3
import argparse
import re
from datetime import datetime, timezone
from pathlib import Path


TOKENS = ["beta_u1", "beta_u2", "beta_u3"]


def _now_tag():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _load_latest_trace(trace_dir: Path, token: str):
    files = sorted(trace_dir.glob(f"*{token}*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return ""
    return files[0].read_text(encoding="utf-8", errors="ignore")


LOG_LINE_RE = re.compile(
    r'^\S+:\d+:(?P<ip>\S+)\s+-\s+-\s+\[(?P<ts>[^\]]+)\]\s+"(?P<method>[A-Z]+)\s+(?P<path>\S+)\s+HTTP/[0-9.]+"\s+\d+\s+\d+\s+"[^"]*"\s+"(?P<ua>[^"]+)"'
)


def _parse_log_events(text: str):
    events = []
    for raw in text.splitlines():
        m = LOG_LINE_RE.match(raw.strip())
        if not m:
            continue
        try:
            ts_dt = datetime.strptime(m.group("ts"), "%d/%b/%Y:%H:%M:%S %z")
        except ValueError:
            continue
        events.append(
            {
                "ip": m.group("ip"),
                "ts": m.group("ts"),
                "ts_dt": ts_dt,
                "method": m.group("method"),
                "path": m.group("path"),
                "ua": m.group("ua"),
            }
        )
    return events


def _extract_trace_summary(text: str, token: str):
    events = _parse_log_events(text)
    landing_events = [e for e in events if f"src={token}" in e["path"] and e["method"] == "GET"]
    if not landing_events:
        return {
            "landing": False,
            "demo": False,
            "signup": False,
            "first_chat_send": False,
            "completed": False,
            "landing_ts": "",
            "demo_ts": "",
            "signup_ts": "",
            "first_chat_send_ts": "",
            "landing_to_demo_s": "",
            "landing_to_signup_s": "",
            "signup_to_first_send_s": "",
        }

    # Build best session per landing event:
    # - same UA
    # - events in fixed post-landing window
    # - select candidate with max funnel coverage; tie-break by latest landing
    window_seconds = 45 * 60
    best = None
    for landing_event in landing_events:
        start = landing_event["ts_dt"]
        end_ts = start.timestamp() + window_seconds
        scoped = [
            e
            for e in events
            if e["ua"] == landing_event["ua"]
            and e["ts_dt"].timestamp() >= start.timestamp()
            and e["ts_dt"].timestamp() <= end_ts
        ]
        landing = True
        demo_event = next(
            (e for e in scoped if e["method"] == "GET" and ("/platform-demo" in e["path"] or "/chat-demo" in e["path"])), None
        )
        signup_event = next((e for e in scoped if e["method"] == "GET" and "/signup" in e["path"]), None)
        chat_event = next(
            (
                e
                for e in scoped
                if e["method"] == "POST"
                and ("/chat/" in e["path"] or "/api/chat" in e["path"] or "/api/chats" in e["path"])
            ),
            None,
        )
        demo = demo_event is not None
        signup = signup_event is not None
        first_chat_send = chat_event is not None
        score = int(landing) + int(demo) + int(signup) + int(first_chat_send)
        candidate = {
            "landing": landing,
            "demo": demo,
            "signup": signup,
            "first_chat_send": first_chat_send,
            "completed": landing and demo and signup and first_chat_send,
            "score": score,
            "start_ts": start.timestamp(),
            "landing_event": landing_event,
            "demo_event": demo_event,
            "signup_event": signup_event,
            "chat_event": chat_event,
        }
        if best is None or candidate["score"] > best["score"] or (
            candidate["score"] == best["score"] and candidate["start_ts"] > best["start_ts"]
        ):
            best = candidate

    landing = best["landing"]
    demo = best["demo"]
    signup = best["signup"]
    first_chat_send = best["first_chat_send"]
    completed = best["completed"]

    def _ts(ev):
        return ev["ts_dt"].strftime("%Y-%m-%d %H:%M:%S %z") if ev else ""

    def _delta(a, b):
        if not a or not b:
            return ""
        return str(int(b["ts_dt"].timestamp() - a["ts_dt"].timestamp()))

    return {
        "landing": landing,
        "demo": demo,
        "signup": signup,
        "first_chat_send": first_chat_send,
        "completed": completed,
        "landing_ts": _ts(best["landing_event"]),
        "demo_ts": _ts(best["demo_event"]),
        "signup_ts": _ts(best["signup_event"]),
        "first_chat_send_ts": _ts(best["chat_event"]),
        "landing_to_demo_s": _delta(best["landing_event"], best["demo_event"]),
        "landing_to_signup_s": _delta(best["landing_event"], best["signup_event"]),
        "signup_to_first_send_s": _delta(best["signup_event"], best["chat_event"]),
    }


def _parse_feedback_grid(feedback_path: Path):
    if not feedback_path.exists():
        return {}
    txt = feedback_path.read_text(encoding="utf-8", errors="ignore")
    # Very light parse; keep raw lines for operator completion.
    out = {}
    for token in TOKENS:
        m = re.search(rf"\|\s*U{token[-1]}\s*\|\s*{token}\s*\|\s*([^|]*)\|\s*([^|]*)\|\s*([^|]*)\|\s*([^|]*)\|", txt)
        if m:
            out[token] = {
                "completed_funnel": m.group(1).strip(),
                "ttfuo": m.group(2).strip(),
                "top_blockers": m.group(3).strip(),
                "top_value": m.group(4).strip(),
            }
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-dir", default="logs/beta_traces")
    parser.add_argument("--feedback-grid", default="progress/BETA_FEEDBACK_GRID_2026-02-14.md")
    parser.add_argument("--out", default=None, help="Output markdown path")
    args = parser.parse_args()

    trace_dir = Path(args.trace_dir)
    feedback_path = Path(args.feedback_grid)
    out_path = Path(args.out) if args.out else Path(f"progress/BETA_RUN_B_DEBRIEF_{_now_tag()}.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    feedback = _parse_feedback_grid(feedback_path)
    rows = []
    completed_count = 0
    for token in TOKENS:
        trace_text = _load_latest_trace(trace_dir, token)
        summary = _extract_trace_summary(trace_text, token)
        completed_count += 1 if summary["completed"] else 0
        fb = feedback.get(token, {})
        rows.append(
            {
                "tester": f"U{token[-1]}",
                "token": token,
                "trace_completed": "yes" if summary["completed"] else "no",
                "landing": "yes" if summary["landing"] else "no",
                "demo": "yes" if summary["demo"] else "no",
                "signup": "yes" if summary["signup"] else "no",
                "first_chat_send": "yes" if summary["first_chat_send"] else "no",
                "ttfuo": fb.get("ttfuo", ""),
                "blockers": fb.get("top_blockers", ""),
                "value": fb.get("top_value", ""),
                "landing_ts": summary["landing_ts"],
                "demo_ts": summary["demo_ts"],
                "signup_ts": summary["signup_ts"],
                "first_chat_send_ts": summary["first_chat_send_ts"],
                "landing_to_demo_s": summary["landing_to_demo_s"],
                "landing_to_signup_s": summary["landing_to_signup_s"],
                "signup_to_first_send_s": summary["signup_to_first_send_s"],
            }
        )

    lines = [
        f"# Beta Run B Debrief ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')})",
        "",
        "## Funnel Table",
        "| Tester | Token | Trace Completed | Landing | Demo | Signup | First Chat Send | TTFUO | Top Blockers | Top Value Moments |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['tester']} | {r['token']} | {r['trace_completed']} | {r['landing']} | {r['demo']} | {r['signup']} | {r['first_chat_send']} | {r['ttfuo']} | {r['blockers']} | {r['value']} |"
        )

    lines.extend(
        [
            "",
            "## Session Timing (auto from traces)",
            "| Tester | Landing TS | Demo TS | Signup TS | First Chat Send TS | Landing->Demo (s) | Landing->Signup (s) | Signup->First Send (s) |",
            "|---|---|---|---|---|---:|---:|---:|",
        ]
    )
    for r in rows:
        lines.append(
            f"| {r['tester']} | {r['landing_ts'] or '-'} | {r['demo_ts'] or '-'} | {r['signup_ts'] or '-'} | {r['first_chat_send_ts'] or '-'} | {r['landing_to_demo_s'] or '-'} | {r['landing_to_signup_s'] or '-'} | {r['signup_to_first_send_s'] or '-'} |"
        )

    lines.extend(
        [
            "",
            "## Acceptance Snapshot",
            f"- complete traces: `{completed_count}/3`",
            "- at least one TTFUO < 3 min: `<fill from feedback>`",
            "",
            "## Consolidated Top 5 Blockers",
            "1. ",
            "2. ",
            "3. ",
            "4. ",
            "5. ",
            "",
            "## Consolidated Top 5 Value Moments",
            "1. ",
            "2. ",
            "3. ",
            "4. ",
            "5. ",
            "",
            "## Proposed Next 3 UI-only Fixes",
            "1. ",
            "2. ",
            "3. ",
            "",
            "## Sources",
            f"- trace_dir: `{trace_dir}`",
            f"- feedback_grid: `{feedback_path}`",
        ]
    )

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[beta-debrief] wrote {out_path}")


if __name__ == "__main__":
    main()
