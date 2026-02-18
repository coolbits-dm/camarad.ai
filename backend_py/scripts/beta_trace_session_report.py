#!/usr/bin/env python3
import argparse
import re
from datetime import datetime
from pathlib import Path

TOKENS = ["beta_u1", "beta_u2", "beta_u3"]

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


def latest_trace_text(trace_dir: Path, token: str) -> str:
    files = sorted(trace_dir.glob(f"*{token}*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return ""
    return files[0].read_text(encoding="utf-8", errors="ignore")


def first_match(events, pred):
    for e in events:
        if pred(e):
            return e
    return None


def session_report(events, token: str):
    landings = [e for e in events if e["method"] == "GET" and f"src={token}" in e["path"]]
    if not landings:
        return None
    # best candidate: latest landing with highest funnel coverage in 45m window
    best = None
    for l in landings:
        window = [e for e in events if e["ua"] == l["ua"] and 0 <= (e["ts"] - l["ts"]).total_seconds() <= 2700]
        demo = first_match(window, lambda e: e["method"] == "GET" and ("/platform-demo" in e["path"] or "/chat-demo" in e["path"]))
        signup = first_match(window, lambda e: e["method"] == "GET" and "/signup" in e["path"])
        chat_post = first_match(
            window,
            lambda e: e["method"] == "POST" and ("/chat/" in e["path"] or "/api/chat" in e["path"] or "/api/chats" in e["path"]),
        )
        score = int(True) + int(demo is not None) + int(signup is not None) + int(chat_post is not None)
        cand = {"landing": l, "demo": demo, "signup": signup, "chat_post": chat_post, "score": score}
        if best is None or cand["score"] > best["score"] or (
            cand["score"] == best["score"] and cand["landing"]["ts"] > best["landing"]["ts"]
        ):
            best = cand
    return best


def dt_str(event):
    return event["ts"].strftime("%Y-%m-%d %H:%M:%S %z") if event else "-"


def delta_s(a, b):
    if not a or not b:
        return "-"
    return str(int((b["ts"] - a["ts"]).total_seconds()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace-dir", default="logs/beta_traces")
    args = ap.parse_args()

    trace_dir = Path(args.trace_dir)
    print("| Token | Landing | Demo | Signup | First Chat Send | Landing->Demo (s) | Landing->Signup (s) | Signup->First Send (s) |")
    print("|---|---|---|---|---|---:|---:|---:|")
    for t in TOKENS:
        txt = latest_trace_text(trace_dir, t)
        rep = session_report(parse_events(txt), t) if txt else None
        if not rep:
            print(f"| {t} | - | - | - | - | - | - | - |")
            continue
        l, d, s, c = rep["landing"], rep["demo"], rep["signup"], rep["chat_post"]
        print(
            f"| {t} | {dt_str(l)} | {dt_str(d)} | {dt_str(s)} | {dt_str(c)} | {delta_s(l,d)} | {delta_s(l,s)} | {delta_s(s,c)} |"
        )


if __name__ == "__main__":
    main()
