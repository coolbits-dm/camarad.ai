#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft7Validator


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PROGRESS = ROOT / "progress" / "agent_science"
RUNS_DIR = PROGRESS / "runs"

TASKPACK_A = PROGRESS / "TASKPACK_A_V1.md"
TASKPACK_B = PROGRESS / "TASKPACK_B_V1.md"
SELECTOR = PROGRESS / "TASKPACK_SMOKE_SELECTOR_V1.md"
SCHEMA_DIR = PROGRESS / "SCHEMAS_V1"

AGENT_ROUTE_MAP = {
    "personal": ("personal", "life-coach"),
    "ppc": ("agency", "ppc-specialist"),
    "ceo": ("business", "ceo-strategy"),
    "devops": ("development", "devops-infra"),
}

ID_RE = re.compile(r"^(PERS|PPC|CEO|DEV)-\d{2}$|^(PA_B|PPC_B|CEO_B|DO_B)_\d{2}$")


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
        shape_m = re.search(r"-\s+expected_output_shape:\s+`([^`]+)`", blk)
        if not (task_id_m and agent_m and payload_m and shape_m):
            continue
        task_id = task_id_m.group(1).strip()
        if not ID_RE.match(task_id):
            continue
        payload_raw = payload_m.group(1).strip()
        try:
            payload = json.loads(payload_raw)
        except Exception:
            payload = {"_raw_input_payload": payload_raw}
        out[task_id] = {
            "task_id": task_id,
            "agent": agent_m.group(1).strip(),
            "input_payload": payload,
            "expected_output_shape": shape_m.group(1).strip(),
            "source": path.name,
        }
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


def _extract_json_block(text: str):
    # remove fenced wrappers first
    t = re.sub(r"```(?:json)?", "", text or "", flags=re.I).strip()
    start = t.find("{")
    if start < 0:
        return None
    depth = 0
    for i, ch in enumerate(t[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = t[start : i + 1]
                try:
                    return json.loads(candidate)
                except Exception:
                    return None
    return None


def _load_validators():
    validators = {}
    for name in (
        "personal_next_actions.schema.json",
        "ppc_actions.schema.json",
        "ceo_exec_brief.schema.json",
        "devops_runbook.schema.json",
    ):
        obj = json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))
        validators[name] = Draft7Validator(obj)
    return validators


def _build_prompt(task, policy_mode):
    deep_note = (
        "Set policy_used to deep and include a short, concrete why_deep."
        if policy_mode == "deep"
        else "Set policy_used to eco and set why_deep to null."
    )
    payload = json.dumps(task["input_payload"], ensure_ascii=False)
    return (
        "You are responding for an agent evaluation. "
        "Return STRICT JSON ONLY (no markdown, no explanation). "
        f"Use schema: {task['expected_output_shape']}. "
        f"{deep_note} "
        f"Task ID: {task['task_id']}. "
        f"Input payload: {payload}"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", type=int, default=1)
    parser.add_argument("--client-id", type=int, default=1)
    parser.add_argument("--allow-real", action="store_true", help="Allow real vertex calls for real agents")
    parser.add_argument("--set", choices=("smoke", "full"), default="smoke", help="Run smoke selector or full TaskPack A+B")
    args = parser.parse_args()

    # Keep local run deterministic and cheap unless explicitly overridden.
    os.environ.setdefault("AUTH_REQUIRED", "0")
    os.environ.setdefault("APP_ENV", "development")
    if not args.allow_real:
        os.environ["REAL_AGENT_SLUGS"] = ""
        os.environ["FORCE_VERTEX_ALL_AGENTS"] = "0"

    # Import after env is prepared.
    from app import app

    tasks_a = _parse_taskpack(TASKPACK_A)
    tasks_b = _parse_taskpack(TASKPACK_B)
    tasks = {}
    tasks.update(tasks_a)
    tasks.update(tasks_b)
    if args.set == "full":
        selected_ids = list(tasks_a.keys()) + list(tasks_b.keys())
    else:
        selected_ids = _parse_selector(SELECTOR)
    validators = _load_validators()

    missing = [tid for tid in selected_ids if tid not in tasks]
    if missing:
        raise SystemExit(f"selector has missing task ids: {missing}")
    if args.set == "smoke" and len(selected_ids) != 20:
        raise SystemExit(f"selector must contain 20 tasks, got {len(selected_ids)}")

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_id = f"agent_science_{args.set}_{_now_tag()}"
    rows = []

    with app.test_client() as client:
        for policy in ("eco", "deep"):
            for task_id in selected_ids:
                task = tasks[task_id]
                ws_slug, agent_slug = AGENT_ROUTE_MAP[task["agent"]]
                prompt = _build_prompt(task, policy)
                headers = {
                    "X-User-ID": str(args.user_id),
                    "X-Client-ID": str(args.client_id),
                    "X-Agent-Science-Eval": "1",
                    "Content-Type": "application/json",
                }
                resp = client.post(
                    f"/chat/{ws_slug}/{agent_slug}",
                    data=json.dumps({"message": prompt}),
                    headers=headers,
                )
                body = {}
                try:
                    body = resp.get_json(silent=True) or {}
                except Exception:
                    body = {}
                response_text = str(body.get("response") or "")
                parsed = _extract_json_block(response_text)
                schema_name = task["expected_output_shape"]
                schema_ok = False
                policy_ok = False
                why_deep_ok = False
                parse_ok = parsed is not None
                if parse_ok:
                    errors = list(validators[schema_name].iter_errors(parsed))
                    schema_ok = len(errors) == 0
                    policy_used = str((parsed or {}).get("policy_used") or "").strip().lower()
                    why_deep = (parsed or {}).get("why_deep")
                    if policy == "deep":
                        why_deep_ok = isinstance(why_deep, str) and bool(why_deep.strip())
                        policy_ok = policy_used == "deep" and why_deep_ok
                    else:
                        policy_ok = policy_used == "eco"
                        why_deep_ok = why_deep in (None, "", "null")
                parsed_metrics = {
                    "policy_used": (parsed or {}).get("policy_used") if isinstance(parsed, dict) else None,
                    "why_deep_present": isinstance((parsed or {}).get("why_deep"), str) and bool(str((parsed or {}).get("why_deep")).strip()) if isinstance(parsed, dict) else False,
                    "actions_count": len((parsed or {}).get("actions") or []) if isinstance(parsed, dict) and isinstance((parsed or {}).get("actions"), list) else 0,
                    "summary_bullets_count": len((parsed or {}).get("summary_bullets") or []) if isinstance(parsed, dict) and isinstance((parsed or {}).get("summary_bullets"), list) else 0,
                    "insights_count": len((parsed or {}).get("insights") or []) if isinstance(parsed, dict) and isinstance((parsed or {}).get("insights"), list) else 0,
                    "next_actions_count": len((parsed or {}).get("next_actions") or []) if isinstance(parsed, dict) and isinstance((parsed or {}).get("next_actions"), list) else 0,
                    "remediation_steps_count": len((parsed or {}).get("remediation_steps") or []) if isinstance(parsed, dict) and isinstance((parsed or {}).get("remediation_steps"), list) else 0,
                    "tool_context_present": bool((parsed or {}).get("tool_context_present")) if isinstance(parsed, dict) else False,
                    "tool_context_used": bool((parsed or {}).get("tool_context_used")) if isinstance(parsed, dict) else False,
                    "decision": (parsed or {}).get("decision") if isinstance(parsed, dict) else None,
                }
                rows.append(
                    {
                        "run_id": run_id,
                        "policy": policy,
                        "task_id": task_id,
                        "agent": task["agent"],
                        "workspace": ws_slug,
                        "agent_slug": agent_slug,
                        "shape": schema_name,
                        "source": task["source"],
                        "http_status": int(resp.status_code),
                        "response_chars": len(response_text),
                        "response_tokens_est": max(1, len(response_text.split())),
                        "json_parse_ok": parse_ok,
                        "schema_ok": schema_ok,
                        "policy_ok": policy_ok,
                        "why_deep_ok": why_deep_ok,
                        "parsed_metrics": parsed_metrics,
                        "conv_id": body.get("conv_id"),
                        "request_id": body.get("request_id"),
                    }
                )

    # Aggregate
    by_agent_policy = defaultdict(list)
    for r in rows:
        by_agent_policy[(r["agent"], r["policy"])].append(r)

    summary = {
        "run_id": run_id,
        "mode": f"{args.set}_selector_v1" if args.set == "smoke" else "full_taskpack_v1",
        "allow_real": bool(args.allow_real),
        "selected_tasks": len(selected_ids),
        "total_runs": len(rows),
        "totals": {
            "http_200_rate": sum(1 for r in rows if r["http_status"] == 200) / len(rows),
            "json_parse_rate": sum(1 for r in rows if r["json_parse_ok"]) / len(rows),
            "schema_compliance_rate": sum(1 for r in rows if r["schema_ok"]) / len(rows),
            "policy_compliance_rate": sum(1 for r in rows if r["policy_ok"]) / len(rows),
        },
        "agents": {},
        "cost_proxy": {},
    }

    for agent in ("personal", "ppc", "ceo", "devops"):
        eco = by_agent_policy[(agent, "eco")]
        deep = by_agent_policy[(agent, "deep")]
        def _rate(arr, key):
            return (sum(1 for x in arr if x[key]) / len(arr)) if arr else 0.0
        eco_tokens = sum(r["response_tokens_est"] for r in eco) or 1
        deep_tokens = sum(r["response_tokens_est"] for r in deep) or 1
        summary["agents"][agent] = {
            "eco": {
                "runs": len(eco),
                "json_parse_rate": _rate(eco, "json_parse_ok"),
                "schema_compliance_rate": _rate(eco, "schema_ok"),
                "policy_compliance_rate": _rate(eco, "policy_ok"),
            },
            "deep": {
                "runs": len(deep),
                "json_parse_rate": _rate(deep, "json_parse_ok"),
                "schema_compliance_rate": _rate(deep, "schema_ok"),
                "policy_compliance_rate": _rate(deep, "policy_ok"),
            },
        }
        summary["cost_proxy"][agent] = {
            "eco_tokens_est_total": eco_tokens,
            "deep_tokens_est_total": deep_tokens,
            "deep_vs_eco_multiplier": round(deep_tokens / eco_tokens, 3),
        }

    json_path = RUNS_DIR / f"{run_id}.json"
    md_path = RUNS_DIR / f"{run_id}.md"
    json_path.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Agent Science {args.set.title()} Run - {run_id}",
        "",
        f"- allow_real: `{str(bool(args.allow_real)).lower()}`",
        f"- selected_tasks: `{len(selected_ids)}`",
        f"- total_runs: `{len(rows)}`",
        "",
        "## Totals",
        f"- http_200_rate: `{summary['totals']['http_200_rate']:.3f}`",
        f"- json_parse_rate: `{summary['totals']['json_parse_rate']:.3f}`",
        f"- schema_compliance_rate: `{summary['totals']['schema_compliance_rate']:.3f}`",
        f"- policy_compliance_rate: `{summary['totals']['policy_compliance_rate']:.3f}`",
        "",
        "## Per Agent",
    ]
    for agent in ("personal", "ppc", "ceo", "devops"):
        a = summary["agents"][agent]
        c = summary["cost_proxy"][agent]
        lines.extend(
            [
                f"### {agent}",
                f"- eco schema_compliance_rate: `{a['eco']['schema_compliance_rate']:.3f}`",
                f"- deep schema_compliance_rate: `{a['deep']['schema_compliance_rate']:.3f}`",
                f"- eco policy_compliance_rate: `{a['eco']['policy_compliance_rate']:.3f}`",
                f"- deep policy_compliance_rate: `{a['deep']['policy_compliance_rate']:.3f}`",
                f"- deep_vs_eco_cost_multiplier (tokens_est): `{c['deep_vs_eco_multiplier']}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Artifacts",
            f"- JSON: `{json_path}`",
            f"- Markdown: `{md_path}`",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[agent-science-smoke] run_id={run_id}")
    print(f"[agent-science-smoke] json={json_path}")
    print(f"[agent-science-smoke] md={md_path}")


if __name__ == "__main__":
    main()
