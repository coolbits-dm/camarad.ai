#!/usr/bin/env python3
import argparse
import re
from datetime import datetime
from pathlib import Path


LOG_LINE_RE = re.compile(
    r'^\S+:\d+:(?P<ip>\S+)\s+-\s+-\s+\[(?P<ts>[^\]]+)\]\s+"(?P<method>[A-Z]+)\s+(?P<path>\S+)\s+HTTP/[0-9.]+"\s+\d+\s+\d+\s+"[^"]*"\s+"(?P<ua>[^"]+)"'
)


def parse_events(text: str):
    events = []
    for raw in text.splitlines():
        m = LOG_LINE_RE.match(raw.strip())
        if not m:
            continue
        try:
            ts = datetime.strptime(m.group("ts"), "%d/%b/%Y:%H:%M:%S %z")
        except ValueError:
            continue
        events.append(
            {
                "ts": ts,
                "method": m.group("method"),
                "path": m.group("path"),
                "ua": m.group("ua"),
            }
        )
    return events


def load_latest(trace_dir: Path, token: str):
    files = sorted(trace_dir.glob(f"*{token}*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None, ""
    return files[0], files[0].read_text(encoding="utf-8", errors="ignore")


def eval_token(events, token: str):
    landings = [e for e in events if e["method"] == "GET" and f"src={token}" in e["path"]]
    if not landings:
        return {
            "landing": False,
            "demo": False,
            "signup": False,
            "first_send": False,
            "status": "fail",
            "missing": ["landing"],
        }

    best = None
    for l in landings:
        scoped = [e for e in events if e["ua"] == l["ua"] and 0 <= (e["ts"] - l["ts"]).total_seconds() <= 2700]
        demo = any(e["method"] == "GET" and ("/platform-demo" in e["path"] or "/chat-demo" in e["path"]) for e in scoped)
        signup = any(e["method"] == "GET" and "/signup" in e["path"] for e in scoped)
        first_send = any(
            e["method"] == "POST" and ("/chat/" in e["path"] or "/api/chat" in e["path"] or "/api/chats" in e["path"])
            for e in scoped
        )
        score = 1 + int(demo) + int(signup) + int(first_send)
        cand = {"landing": True, "demo": demo, "signup": signup, "first_send": first_send, "score": score}
        if best is None or cand["score"] > best["score"]:
            best = cand

    missing = []
    if not best["demo"]:
        missing.append("demo")
    if not best["signup"]:
        missing.append("signup")
    if not best["first_send"]:
        missing.append("first_chat_send")

    status = "pass" if not missing else "fail"
    return {**best, "status": status, "missing": missing}


def recommendation(missing):
    if not missing:
        return "Session complete."
    if missing == ["first_chat_send"]:
        return "User reached signup but did not send first chat. Improve post-signup CTA to chat and auto-focus composer."
    if "signup" in missing:
        return "User did not reach signup in tracked session. Improve demo->signup CTA visibility and wording."
    if "demo" in missing:
        return "User did not open demo. Re-check landing CTA prominence and path consistency."
    return "Re-run with live watcher + explicit test script for user."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("token", help="beta token, e.g. beta_u1")
    ap.add_argument("--trace-dir", default="logs/beta_traces")
    args = ap.parse_args()

    path, text = load_latest(Path(args.trace_dir), args.token)
    if path is None:
        print(f"[goal-check] token={args.token} status=fail reason=no_trace_file")
        return 1

    summary = eval_token(parse_events(text), args.token)
    print(f"[goal-check] token={args.token}")
    print(f"[goal-check] trace={path}")
    print(f"[goal-check] status={summary['status']}")
    print(
        f"[goal-check] funnel landing={summary['landing']} demo={summary['demo']} signup={summary['signup']} first_chat_send={summary['first_send']}"
    )
    if summary["missing"]:
        print(f"[goal-check] missing={','.join(summary['missing'])}")
    print(f"[goal-check] recommendation={recommendation(summary['missing'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
