#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from statistics import median


def _score_format(row):
    return 10.0 if row.get("schema_ok") else 0.0


def _score_reasoning(row):
    m = row.get("parsed_metrics") or {}
    agent = row.get("agent")
    base = 7.0 if row.get("json_parse_ok") else 4.0
    if agent in ("ceo", "devops") and m.get("tool_context_present"):
        base = 8.0 if m.get("tool_context_used") else 5.5
    return max(0.0, min(10.0, base))


def _score_utility(row):
    m = row.get("parsed_metrics") or {}
    agent = row.get("agent")
    if not row.get("schema_ok"):
        return 0.0
    if agent == "personal":
        return 9.0 if m.get("actions_count", 0) >= 2 else 7.5
    if agent == "ppc":
        return 9.0 if m.get("actions_count", 0) >= 2 and m.get("summary_bullets_count", 0) >= 1 else 7.0
    if agent == "ceo":
        ok = m.get("insights_count", 0) >= 1 and m.get("next_actions_count", 0) >= 1 and bool(m.get("decision"))
        return 9.0 if ok else 7.0
    if agent == "devops":
        return 9.0 if m.get("remediation_steps_count", 0) >= 2 else 7.0
    return 7.0


def _build_cost_baselines(rows):
    out = {}
    for agent in ("personal", "ppc", "ceo", "devops"):
        eco = [r["response_tokens_est"] for r in rows if r.get("agent") == agent and r.get("policy") == "eco"]
        out[agent] = max(1, int(median(eco) if eco else 1))
    return out


def _score_cost(row, eco_baselines):
    agent = row.get("agent")
    denom = max(1, eco_baselines.get(agent, 1))
    ratio = float(row.get("response_tokens_est") or 1) / float(denom)
    if ratio <= 1.0:
        return 10.0
    if ratio <= 1.5:
        return 8.0
    if ratio <= 2.0:
        return 6.0
    return 4.0


def _apply_penalties(row, utility, fmt, reasoning):
    m = row.get("parsed_metrics") or {}
    policy = row.get("policy")
    if policy == "deep" and not m.get("why_deep_present"):
        utility -= 2.0
        fmt -= 2.0
    if row.get("agent") in ("ceo", "devops") and m.get("tool_context_present") and not m.get("tool_context_used"):
        utility -= 1.0
        reasoning -= 1.5
    return max(0.0, utility), max(0.0, fmt), max(0.0, reasoning)


def _weighted(u, f, r, c):
    return (0.40 * u) + (0.30 * f) + (0.15 * r) + (0.15 * c)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_json", type=str)
    args = parser.parse_args()

    run_path = Path(args.run_json)
    obj = json.loads(run_path.read_text(encoding="utf-8"))
    rows = obj["rows"]
    summary = obj["summary"]
    run_id = summary["run_id"]
    eco_base = _build_cost_baselines(rows)

    scored = []
    for r in rows:
        u = _score_utility(r)
        f = _score_format(r)
        rr = _score_reasoning(r)
        c = _score_cost(r, eco_base)
        u, f, rr = _apply_penalties(r, u, f, rr)
        s = _weighted(u, f, rr, c)
        rec = dict(r)
        rec["rubric"] = {"utility": round(u, 3), "format": round(f, 3), "reasoning": round(rr, 3), "cost": round(c, 3), "weighted": round(s, 3)}
        scored.append(rec)

    by_agent = {}
    for agent in ("personal", "ppc", "ceo", "devops"):
        arr = [x for x in scored if x["agent"] == agent]
        if not arr:
            continue
        def avg(k):
            return round(sum(x["rubric"][k] for x in arr) / len(arr), 3)
        avg_u = avg("utility")
        avg_f = avg("format")
        avg_r = avg("reasoning")
        avg_c = avg("cost")
        avg_s = avg("weighted")
        by_agent[agent] = {
            "avg_utility": avg_u,
            "avg_format": avg_f,
            "avg_reasoning": avg_r,
            "avg_cost": avg_c,
            "avg_weighted": avg_s,
            "go_no_go": bool(avg_u >= 8.0 and avg_f >= 9.0 and avg_s >= 8.2 and avg_c >= 8.0 and avg_r >= 7.0),
        }

    out = {
        "run_id": run_id,
        "source_run": str(run_path),
        "eco_baseline_tokens_median": eco_base,
        "agents": by_agent,
    }
    out_json = run_path.with_name(run_path.stem + "_scored.json")
    out_md = run_path.with_name(run_path.stem + "_scored.md")
    out_json.write_text(json.dumps({"summary": out, "rows": scored}, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Agent Science Rubric Scoring - {run_id}",
        "",
        f"- source_run: `{run_path}`",
        "",
        "## Per Agent",
    ]
    for agent in ("personal", "ppc", "ceo", "devops"):
        a = by_agent.get(agent, {})
        lines.extend(
            [
                f"### {agent}",
                f"- avg_utility: `{a.get('avg_utility', 0)}`",
                f"- avg_format: `{a.get('avg_format', 0)}`",
                f"- avg_reasoning: `{a.get('avg_reasoning', 0)}`",
                f"- avg_cost: `{a.get('avg_cost', 0)}`",
                f"- avg_weighted: `{a.get('avg_weighted', 0)}`",
                f"- go_no_go: `{str(a.get('go_no_go', False)).lower()}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Artifacts",
            f"- JSON: `{out_json}`",
            f"- Markdown: `{out_md}`",
        ]
    )
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[agent-science-score] json={out_json}")
    print(f"[agent-science-score] md={out_md}")


if __name__ == "__main__":
    main()

