# Agent Science Quality Gap Report (2026-02-17)

Source run:
- `progress/agent_science/runs/agent_science_quality_20260217T225135Z.md`
- `progress/agent_science/runs/agent_science_quality_20260217T225135Z.json`

Scope:
- 20 tasks (smoke selector), real responses enabled (`allow_real=true`), no eval wrapper.

## Quality snapshot (avg score / 10)
- personal: `9.4`
- ppc: `7.8`
- ceo: `6.3`
- devops: `6.1`

## Top cross-agent gaps
1. `weak_action_structure` (CEO, DevOps)
2. `too_long` (PPC, DevOps, CEO)
3. `low_domain_specificity` (CEO, DevOps)

## Top 5 remediation actions (next patch set)
1. **CEO prompt hard cap + structure lock**
   - enforce output as: `Decision -> 3 Risks -> 3 Next Actions`
   - cap length to ~220-320 words in eco mode.
2. **DevOps prompt runbook lock**
   - enforce sections: `Hypothesis / Checks / Remediation`
   - require at least 2 explicit command/check lines.
3. **PPC brevity and action density**
   - cap long narrative, enforce max 6 bullets + max 6 actions.
4. **Domain anchor injection**
   - prepend lightweight domain anchors per role (CEO/DevOps) to avoid generic wording.
5. **Real-response quality gate in CI-like local run**
   - keep this quality script and require per-agent floor before beta-facing rollout.

## Suggested acceptance for next quality pass
- personal >= 9.0
- ppc >= 8.5
- ceo >= 8.0
- devops >= 8.0
- no agent with `weak_action_structure` on more than 1/5 tasks.

