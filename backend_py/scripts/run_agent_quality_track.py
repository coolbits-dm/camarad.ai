#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PROGRESS = ROOT / "progress" / "agent_science"
RUNS_DIR = PROGRESS / "runs"
TASKPACK_A = PROGRESS / "TASKPACK_A_V1.md"
TASKPACK_B = PROGRESS / "TASKPACK_B_V1.md"
SELECTOR = PROGRESS / "TASKPACK_SMOKE_SELECTOR_V1.md"

ID_RE = re.compile(r"^(PERS|PPC|CEO|DEV)-\d{2}$|^(PA_B|PPC_B|CEO_B|DO_B)_\d{2}$")

AGENT_ROUTE_MAP = {
    "personal": ("personal", "life-coach"),
    "ppc": ("agency", "ppc-specialist"),
    "ceo": ("business", "ceo-strategy"),
    "devops": ("development", "devops-infra"),
}

DOMAIN_KEYWORDS = {
    "personal": ["priority", "action", "today", "deadline", "plan", "next step"],
    "ppc": ["campaign", "roas", "ctr", "cpc", "keyword", "bid", "ga4", "conversion"],
    "ceo": ["decision", "risk", "priority", "next action", "recommend"],
    "devops": ["incident", "logs", "latency", "restart", "deploy", "check", "error"],
}

BAD_MARKERS = (
    "as an ai",
    "i am a large language model",
    "llmclient(",
    "class orchestrator",
    "step 1:",
    "```",
)


def _now_tag():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _parse_taskpack(path: Path):
    text = path.read_text(encoding="utf-8")
    blocks = re.split(r"\n###\s+", text)
    out = {}
    for blk in blocks[1:]:
        task_id_m = re.search(r"-\s+task_id:\s+`([^`]+)`", blk)
        agent_m = re.search(r"-\s+agent:\s+`([^`]+)`", blk)
        payload_m = re.search(r"-\s+input_payload:\s+`(.+?)`", blk, flags=re.S)
        if not (task_id_m and agent_m and payload_m):
            continue
        task_id = task_id_m.group(1).strip()
        if not ID_RE.match(task_id):
            continue
        raw = payload_m.group(1).strip()
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"_raw_input_payload": raw}
        out[task_id] = {"task_id": task_id, "agent": agent_m.group(1).strip(), "input_payload": payload}
    return out


def _parse_selector(path: Path):
    text = path.read_text(encoding="utf-8")
    ids = []
    for line in text.splitlines():
        m = re.match(r"\d+\.\s+`([A-Za-z0-9_\-]+)`", line.strip())
        if not m:
            continue
        task_id = m.group(1).strip()
        if ID_RE.match(task_id):
            ids.append(task_id)
    return ids


def _build_quality_prompt(task):
    payload = json.dumps(task["input_payload"], ensure_ascii=False)
    return (
        "Answer as the assigned specialist in Camarad. "
        "Be concrete, concise, and action-oriented. "
        "No code snippets, no generic framework explanations. "
        "Provide practical steps for this task input: "
        f"{payload}"
    )


def _has_action_structure(text):
    t = text or ""
    return bool(re.search(r"(^|\n)\s*([-*]|\d+\.)\s+", t)) or ("next steps" in t.lower())


def _score_response(agent, text):
    txt = str(text or "").strip()
    lower = txt.lower()
    score = 10.0
    gaps = []

    if not txt:
        return 0.0, ["empty_response"]
    if len(txt) > 1600:
        score -= 2.0
        gaps.append("too_long")
    if any(m in lower for m in BAD_MARKERS):
        score -= 4.0
        gaps.append("generic_or_tutorial_style")
    if "camarada" in lower:
        score -= 2.0
        gaps.append("brand_name_error")
    if not _has_action_structure(txt):
        score -= 1.5
        gaps.append("weak_action_structure")

    kw = DOMAIN_KEYWORDS.get(agent, [])
    hit = sum(1 for k in kw if k in lower)
    if hit == 0:
        score -= 2.0
        gaps.append("low_domain_specificity")
    elif hit == 1:
        score -= 1.0
        gaps.append("thin_domain_specificity")

    return max(0.0, round(score, 3)), gaps


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", type=int, default=1)
    parser.add_argument("--client-id", type=int, default=1)
    parser.add_argument("--allow-real", action="store_true", help="Allow real vertex calls")
    args = parser.parse_args()

    os.environ.setdefault("AUTH_REQUIRED", "0")
    os.environ.setdefault("APP_ENV", "development")
    if not args.allow_real:
        os.environ["REAL_AGENT_SLUGS"] = ""
        os.environ["FORCE_VERTEX_ALL_AGENTS"] = "0"

    from app import app

    tasks = {}
    tasks.update(_parse_taskpack(TASKPACK_A))
    tasks.update(_parse_taskpack(TASKPACK_B))
    selected_ids = _parse_selector(SELECTOR)

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_id = f"agent_science_quality_{_now_tag()}"
    rows = []
    gap_counter = Counter()
    by_agent_scores = defaultdict(list)

    with app.test_client() as client:
        for task_id in selected_ids:
            task = tasks[task_id]
            agent = task["agent"]
            ws_slug, agent_slug = AGENT_ROUTE_MAP[agent]
            prompt = _build_quality_prompt(task)
            resp = client.post(
                f"/chat/{ws_slug}/{agent_slug}",
                data=json.dumps({"message": prompt, "agent_quality_track": True}),
                headers={
                    "X-User-ID": str(args.user_id),
                    "X-Client-ID": str(args.client_id),
                    "X-Agent-Quality-Track": "1",
                    "Content-Type": "application/json",
                },
            )
            body = resp.get_json(silent=True) or {}
            text = str(body.get("response") or "")
            score, gaps = _score_response(agent, text)
            for g in gaps:
                gap_counter[f"{agent}:{g}"] += 1
            by_agent_scores[agent].append(score)
            rows.append(
                {
                    "run_id": run_id,
                    "task_id": task_id,
                    "agent": agent,
                    "workspace": ws_slug,
                    "agent_slug": agent_slug,
                    "http_status": int(resp.status_code),
                    "response_chars": len(text),
                    "response_tokens_est": max(1, len(text.split())),
                    "quality_score": score,
                    "gaps": gaps,
                    "response_preview": text[:500],
                }
            )

    agent_summary = {}
    for agent in ("personal", "ppc", "ceo", "devops"):
        vals = by_agent_scores.get(agent, [])
        avg = (sum(vals) / len(vals)) if vals else 0.0
        agent_summary[agent] = {"avg_quality_score": round(avg, 3), "runs": len(vals)}

    top_gaps = [{"gap": k, "count": v} for k, v in gap_counter.most_common(20)]
    summary = {
        "run_id": run_id,
        "allow_real": bool(args.allow_real),
        "selected_tasks": len(selected_ids),
        "http_200_rate": sum(1 for r in rows if r["http_status"] == 200) / max(1, len(rows)),
        "agents": agent_summary,
        "top_gaps": top_gaps,
    }

    json_path = RUNS_DIR / f"{run_id}.json"
    md_path = RUNS_DIR / f"{run_id}.md"
    json_path.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Agent Science Quality Track - {run_id}",
        "",
        f"- allow_real: `{str(bool(args.allow_real)).lower()}`",
        f"- selected_tasks: `{len(selected_ids)}`",
        f"- http_200_rate: `{summary['http_200_rate']:.3f}`",
        "",
        "## Per Agent Avg Quality",
    ]
    for agent in ("personal", "ppc", "ceo", "devops"):
        a = agent_summary[agent]
        lines.append(f"- {agent}: `{a['avg_quality_score']}` ({a['runs']} runs)")
    lines.extend(["", "## Top Gaps"])
    for g in top_gaps[:12]:
        lines.append(f"- {g['gap']}: `{g['count']}`")
    lines.extend(["", "## Artifacts", f"- JSON: `{json_path}`", f"- Markdown: `{md_path}`"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[agent-science-quality] run_id={run_id}")
    print(f"[agent-science-quality] json={json_path}")
    print(f"[agent-science-quality] md={md_path}")


if __name__ == "__main__":
    main()
