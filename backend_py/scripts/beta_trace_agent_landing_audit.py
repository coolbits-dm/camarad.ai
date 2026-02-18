#!/usr/bin/env python3
import argparse
from datetime import datetime, timezone
from pathlib import Path

from build_beta_run_b_debrief import _load_latest_trace, _parse_log_events

TOKENS = ["beta_u1", "beta_u2", "beta_u3"]
WINDOW_SECONDS = 45 * 60

# Controlled mapping for agent-landing reruns.
TOKEN_AGENT_MAP = {
    "beta_u1": "ppc",
    "beta_u2": "ceo",
    "beta_u3": "devops",
}


def _now_tag():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _latest_trace_file(trace_dir: Path, token: str):
    files = sorted(trace_dir.glob(f"*{token}*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _event_flags(scoped_events, token: str, agent_id: str):
    token_q = f"src={token}"
    expected_agent = f"agent={agent_id}"

    landing_view = next(
        (
            e for e in scoped_events
            if e["method"] == "GET"
            and (
                f"/agents/{agent_id}" in e["path"]
                or (f"/{agent_id}-ai" in e["path"] if agent_id in ("ceo", "devops") else False)
                or ("/ppc-ai" in e["path"] if agent_id == "ppc" else False)
                or ("/personal-ai" in e["path"] if agent_id == "personal" else False)
            )
            and token_q in e["path"]
        ),
        None,
    )
    cta_click = next(
        (
            e for e in scoped_events
            if e["method"] == "GET"
            and "/api/auth/google/start" in e["path"]
            and "from=agent-landing" in e["path"]
            and expected_agent in e["path"]
        ),
        None,
    )
    post_oauth_chat = next(
        (
            e for e in scoped_events
            if e["method"] == "GET"
            and "/chat/" in e["path"]
            and "from=agent-landing" in e["path"]
            and expected_agent in e["path"]
        ),
        None,
    )
    first_send = next(
        (
            e for e in scoped_events
            if e["method"] == "POST"
            and ("/chat/" in e["path"] or "/api/chat" in e["path"] or "/api/chats" in e["path"])
        ),
        None,
    )
    return {
        "agent_landing_view": landing_view,
        "agent_landing_cta_click": cta_click,
        "post_oauth_redirect_to_chat": post_oauth_chat,
        "first_chat_send": first_send,
    }


def run_token(trace_dir: Path, token: str):
    source_file = _latest_trace_file(trace_dir, token)
    text = _load_latest_trace(trace_dir, token)
    agent_id = TOKEN_AGENT_MAP.get(token, "ppc")
    if not text:
        return {
            "token": token,
            "agent": agent_id,
            "source": str(source_file) if source_file else "-",
            "events_total": 0,
            "status": "fail",
            "missing": "agent_landing_view,agent_landing_cta_click,post_oauth_redirect_to_chat,first_chat_send",
            "agent_landing_view": False,
            "agent_landing_cta_click": False,
            "post_oauth_redirect_to_chat": False,
            "first_chat_send": False,
            "counts": {},
        }

    events = _parse_log_events(text)
    landing_candidates = [
        e for e in events
        if e["method"] == "GET"
        and f"src={token}" in e["path"]
    ]
    # Reuse same windowing philosophy as Run B: best candidate by funnel score.
    best = None
    for seed in landing_candidates:
        start = seed["ts_dt"]
        end_ts = start.timestamp() + WINDOW_SECONDS
        scoped = [
            e for e in events
            if e["ua"] == seed["ua"]
            and start.timestamp() <= e["ts_dt"].timestamp() <= end_ts
        ]
        flags = _event_flags(scoped, token, agent_id)
        score = sum(1 for v in flags.values() if v is not None)
        candidate = {"seed": seed, "scoped": scoped, "flags": flags, "score": score}
        if best is None or candidate["score"] > best["score"] or (
            candidate["score"] == best["score"] and seed["ts_dt"] > best["seed"]["ts_dt"]
        ):
            best = candidate

    scoped = best["scoped"] if best else events
    flags = best["flags"] if best else _event_flags(scoped, token, agent_id)
    bools = {k: (v is not None) for k, v in flags.items()}
    missing = [k for k, ok in bools.items() if not ok]

    counts = {
        "agent_landing_view_hits": sum(1 for e in scoped if e["method"] == "GET" and f"/agents/{agent_id}" in e["path"]),
        "agent_landing_cta_click_hits": sum(1 for e in scoped if e["method"] == "GET" and "/api/auth/google/start" in e["path"] and "from=agent-landing" in e["path"]),
        "post_oauth_redirect_to_chat_hits": sum(1 for e in scoped if e["method"] == "GET" and "/chat/" in e["path"] and "from=agent-landing" in e["path"]),
        "first_chat_send_hits": sum(1 for e in scoped if e["method"] == "POST" and ("/chat/" in e["path"] or "/api/chat" in e["path"] or "/api/chats" in e["path"])),
    }
    return {
        "token": token,
        "agent": agent_id,
        "source": str(source_file) if source_file else "-",
        "events_total": len(events),
        "status": "pass" if not missing else "fail",
        "missing": ",".join(missing),
        "counts": counts,
        **bools,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/opt/camarad")
    ap.add_argument("--trace-dir", default="logs/beta_traces")
    ap.add_argument("--out", default=None)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    root = Path(args.root)
    trace_dir = Path(args.trace_dir)
    if not trace_dir.is_absolute():
        trace_dir = root / trace_dir

    out_path = Path(args.out) if args.out else root / "progress" / f"BETA_AGENT_LANDING_FUNNEL_AUDIT_{_now_tag()}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = [run_token(trace_dir, token) for token in TOKENS]
    pass_count = sum(1 for r in rows if r["status"] == "pass")

    lines = [
        f"# Beta Agent Landing Funnel Audit ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')})",
        "",
        "## Method",
        "- source: latest per-token trace file from `logs/beta_traces`",
        f"- session selector: same UA + `{WINDOW_SECONDS}s` post-landing (best score candidate)",
        "- funnel events:",
        "  - `agent_landing_view`: GET `/agents/<id>` with `src=beta_uX`",
        "  - `agent_landing_cta_click`: GET `/api/auth/google/start` with `from=agent-landing&agent=<id>`",
        "  - `post_oauth_redirect_to_chat`: GET `/chat/...` with `from=agent-landing&agent=<id>`",
        "  - `first_chat_send`: first POST `/chat/*|/api/chat|/api/chats`",
        "",
        "## Sources Read",
        "| Token | Agent | Trace file | Parsed events |",
        "|---|---|---|---:|",
    ]
    for r in rows:
        lines.append(f"| {r['token']} | {r['agent']} | {r['source']} | {r['events_total']} |")

    lines.extend(
        [
            "",
            "## Funnel Verdict",
            "| Token | Agent | Status | Landing View | CTA Click | Post OAuth Chat | First Chat Send | Missing |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    for r in rows:
        lines.append(
            f"| {r['token']} | {r['agent']} | {r['status']} | {r['agent_landing_view']} | {r['agent_landing_cta_click']} | {r['post_oauth_redirect_to_chat']} | {r['first_chat_send']} | {r['missing'] or '-'} |"
        )

    lines.extend(
        [
            "",
            "## Raw Event Counts (selected session)",
            "| Token | view_hits | cta_hits | post_oauth_chat_hits | first_send_hits |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for r in rows:
        c = r["counts"] or {}
        lines.append(
            f"| {r['token']} | {c.get('agent_landing_view_hits', 0)} | {c.get('agent_landing_cta_click_hits', 0)} | {c.get('post_oauth_redirect_to_chat_hits', 0)} | {c.get('first_chat_send_hits', 0)} |"
        )

    lines.extend(
        [
            "",
            "## Summary",
            f"- pass_count: `{pass_count}/3`",
            "- gate condition: `3/3 full agent landing funnel` before scaling paid traffic",
        ]
    )

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[agent-landing-audit] wrote {out_path}")
    if args.verbose:
        for r in rows:
            c = r["counts"] or {}
            print(
                f"[agent-landing-audit][verbose] token={r['token']} agent={r['agent']} status={r['status']} "
                f"view={c.get('agent_landing_view_hits', 0)} cta={c.get('agent_landing_cta_click_hits', 0)} "
                f"post_oauth_chat={c.get('post_oauth_redirect_to_chat_hits', 0)} first_send={c.get('first_chat_send_hits', 0)}"
            )


if __name__ == "__main__":
    main()
