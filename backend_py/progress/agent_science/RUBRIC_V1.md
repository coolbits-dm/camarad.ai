# Rubric v1

Version: `v1.0`  
Scope: `personal`, `ppc`, `ceo`, `devops`  
Applies to: Eco/Auto/Deep policy comparisons across providers

## Axes and Weights

- Utilitate / Business Value: `40%`
- Format / Schema Compliance: `30%`
- Reasoning / Coerență: `15%`
- Cost / Efficiency: `15%`

## Scoring Scale

Each axis is scored `0..10`.  
Weighted total:

`total = utilitate*0.40 + format*0.30 + reasoning*0.15 + cost*0.15`

## Go / No-Go Thresholds

- Utilitate `>= 8.0`
- Format `>= 9.0` (hard fail if lower)
- Weighted total `>= 8.2`
- Cost `<= 1.5x` Eco baseline for comparable task
- Reasoning minimum `>= 7.0` (not standalone blocker, but impacts total)

## Penalties

### Deep Policy Penalty

Condition:
- `policy_used = deep`
- `why_deep` missing, null, or empty

Penalty:
- `utilitate -= 2.0`
- `format -= 2.0`

### Tool-First Violation Penalty (CEO/DevOps)

Condition:
- Agent is `ceo` or `devops`
- Tool-relevant context exists
- Tool usage not performed before final conclusion

Penalty:
- `reasoning -= 1.5`
- `utilitate -= 1.0`
- `non_compliant = true`

## Compliance Flags

Every evaluation record should carry:

- `schema_valid` (boolean)
- `hard_fail` (boolean)
- `non_compliant` (boolean)
- `penalties_applied` (array of strings)

Hard fail triggers:
- Invalid JSON
- Schema invalid
- `format < 9.0`

## Notes

- Provider is abstract; this rubric evaluates behavior and economics, not vendor identity.
- Policy controls remain user/runtime-level (`auto`, `eco`, `deep`).
