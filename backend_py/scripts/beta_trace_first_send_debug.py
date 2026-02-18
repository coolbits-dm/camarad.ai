#!/usr/bin/env python3
import argparse
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

TOKENS = ["beta_u1", "beta_u2", "beta_u3"]
WINDOW_SECONDS = 45 * 60

LOG_LINE_RE = re.compile(
    r'^\S+:\d+:(?P<ip>\S+)\s+-\s+-\s+\[(?P<ts>[^\]]+)\]\s+"(?P<method>[A-Z]+)\s+(?P<path>\S+)\s+HTTP/[0-9.]+"\s+(?P<status>\d{3})\s+\d+\s+"[^"]*"\s+"(?P<ua>[^"]+)"'
)


def _now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _load_latest_trace_file(trace_dir: Path, token: str):
    files = sorted(trace_dir.glob(f"*{token}*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _parse_events(text: str):
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
                "ts_dt": ts_dt,
                "method": m.group("method"),
                "path": m.group("path"),
                "status": int(m.group("status")),
                "ua": m.group("ua"),
                "ip": m.group("ip"),
            }
        )
    return events


def _select_session(events, token: str):
    landings = [e for e in events if e["method"] == "GET" and f"src={token}" in e["path"]]
    if not landings:
        return None

    best = None
    for landing in landings:
        start = landing["ts_dt"].timestamp()
        end = start + WINDOW_SECONDS
        scoped = [
            e
            for e in events
            if e["ua"] == landing["ua"]
            and start <= e["ts_dt"].timestamp() <= end
        ]
        demo = any(e["method"] == "GET" and ("/platform-demo" in e["path"] or "/chat-demo" in e["path"]) for e in scoped)
        signup = any(e["method"] == "GET" and "/signup" in e["path"] for e in scoped)
        first_send = any(
            e["method"] == "POST"
            and ("/chat/" in e["path"] or "/api/chat" in e["path"] or "/api/chats" in e["path"])
            for e in scoped
        )
        score = 1 + int(demo) + int(signup) + int(first_send)
        candidate = {
            "landing": landing,
            "events": scoped,
            "score": score,
            "demo": demo,
            "signup": signup,
            "first_send": first_send,
        }
        if best is None or candidate["score"] > best["score"] or (
            candidate["score"] == best["score"] and candidate["landing"]["ts_dt"] > best["landing"]["ts_dt"]
        ):
            best = candidate
    return best


def _ua_fingerprint(ua: str) -> str:
    return hashlib.sha1(ua.encode("utf-8")).hexdigest()[:10]


def _fmt_ts(ev):
    return ev["ts_dt"].strftime("%Y-%m-%d %H:%M:%S %z")


def _interesting(ev):
    p = ev["path"]
    if "src=beta_" in p:
        return True
    if "/platform-demo" in p or "/chat-demo" in p:
        return True
    if "/signup" in p:
        return True
    if ev["method"] == "POST" and ("/chat/" in p or "/api/chat" in p or "/api/chats" in p):
        return True
    return False


def _counts(events):
    return {
        "landing": sum(1 for e in events if e["method"] == "GET" and "src=beta_" in e["path"]),
        "demo": sum(1 for e in events if e["method"] == "GET" and ("/platform-demo" in e["path"] or "/chat-demo" in e["path"])),
        "signup": sum(1 for e in events if e["method"] == "GET" and "/signup" in e["path"]),
        "first_send": sum(
            1
            for e in events
            if e["method"] == "POST" and ("/chat/" in e["path"] or "/api/chat" in e["path"] or "/api/chats" in e["path"])
        ),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace-dir", default="logs/beta_traces")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    trace_dir = Path(args.trace_dir)
    out_path = Path(args.out) if args.out else Path(f"progress/BETA_RUN_B_FIRST_SEND_DEBUG_{_now_tag()}.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# Run B First Chat Send Debug ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')})",
        "",
        "## Method",
        f"- source: latest per-token trace in `{trace_dir}`",
        f"- session selector: same UA as landing + {WINDOW_SECONDS}s window + max funnel score",
        "- first_chat_send event: `POST /chat/*` OR `POST /api/chat` OR `POST /api/chats`",
        "",
    ]

    for token in TOKENS:
        f = _load_latest_trace_file(trace_dir, token)
        lines.append(f"## {token}")
        if not f:
            lines.append("- trace file: not found")
            lines.append("")
            continue

        txt = f.read_text(encoding="utf-8", errors="ignore")
        events = _parse_events(txt)
        session = _select_session(events, token)
        lines.append(f"- trace file: `{f}`")
        lines.append(f"- parsed events: `{len(events)}`")

        if not session:
            lines.append("- session: not found (no landing token hit)")
            lines.append("")
            continue

        landing = session["landing"]
        ua_hash = _ua_fingerprint(landing["ua"])
        scoped = session["events"]
        c = _counts(scoped)

        lines.append(f"- selected landing: `{_fmt_ts(landing)}`")
        lines.append(f"- selected session key: `ua_sha1={ua_hash}`")
        lines.append(f"- session events in window: `{len(scoped)}`")
        lines.append(f"- funnel flags: landing=`True`, demo=`{session['demo']}`, signup=`{session['signup']}`, first_chat_send=`{session['first_send']}`")
        lines.append(f"- event counts in selected session: landing=`{c['landing']}`, demo=`{c['demo']}`, signup=`{c['signup']}`, first_chat_send=`{c['first_send']}`")

        lines.append("")
        lines.append("### Evidence Lines (selected session)")
        lines.append("| timestamp | method | status | path |")
        lines.append("|---|---|---:|---|")
        shown = 0
        for ev in scoped:
            if not _interesting(ev):
                continue
            lines.append(f"| {_fmt_ts(ev)} | {ev['method']} | {ev['status']} | `{ev['path']}` |")
            shown += 1
            if shown >= 20:
                break

        if c["first_send"] == 0:
            lines.append("")
            lines.append("- conclusion: **no first_chat_send POST observed in selected session**")

        lines.append("")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[first-send-debug] wrote {out_path}")


if __name__ == "__main__":
    main()
