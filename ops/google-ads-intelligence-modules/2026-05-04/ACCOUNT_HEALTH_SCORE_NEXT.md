# Account Health Score v1 — Next Plan

Phase: PLANNED (not implemented in Phase 2E)  
Phase 2E returns score_status: "planned" only  
Target: Phase 2F  

---

## Overview

Account Health Score v1 is a 0–100 aggregate score computed from deterministic
signal subscores. It does not use an LLM. All inputs are transparent and
documented. Users can see what drives the score.

---

## Score Architecture

```
Account Health Score (0–100)
├── Efficiency (20 pts)    — CTR, CPC, Quality Score proxies
├── Waste Control (25 pts) — Spend with no conversions, low ROAS, high CPA
├── Growth Opportunity (20 pts) — Paused winners, scale candidates, ROAS headroom
├── Tracking Quality (15 pts) — Conversion setup, tracking sanity, value tracking
├── Budget Health (10 pts) — Budget pacing, limited by budget, zero-budget campaigns
└── Structure Hygiene (10 pts) — Removed/paused campaigns, naming conventions, inactive ad groups
```

---

## Score Band Labels

| Score | Label | Color |
|-------|-------|-------|
| 85–100 | Excellent | green |
| 70–84 | Good | teal |
| 50–69 | Needs Attention | yellow |
| 30–49 | Poor | orange |
| 0–29 | Critical | red |

---

## Subscore Details

### Efficiency (20 pts)
Signals:
- `low_ctr_campaign` — penalize (up to -8 pts per violating campaign, capped)
- `high_cpc_outlier` — penalize (up to -5 pts)
- Max deduction: 20 pts
- Start: 20 pts

### Waste Control (25 pts)
Signals:
- `zero_conversion_spend` — -12 pts per critical, -6 pts per warning
- `low_roas_spend` — -8 pts
- `high_cpa_campaign` — -5 pts
- `enabled_loser` — -10 pts
- Capped at 0 (can't go negative per subscore)

### Growth Opportunity (20 pts)
Signals:
- `paused_winner` — no penalty (but noted in recommendations)
- `roas_scale_opportunity` found → +5 pts bonus (up to 20 pts max)
- If spend > 0 and roas > 4.0 on at least one campaign → 20 pts
- If roas 2–4 → 14 pts
- If roas < 2 → 8 pts
- If no conversions → 5 pts

### Tracking Quality (15 pts)
Signals:
- `tracking_sanity_warning` (all conversions zero with spend) → -15 pts (floor 0)
- No conversions across account → 0 pts for this subscore
- Conversions present → 12–15 pts depending on value tracking completeness

### Budget Health (10 pts)
Signals:
- `budget_overspend_or_missing_budget` (multiple campaigns) → -3 pts each, capped at -10
- All budgets set and pacing normally → 10 pts

### Structure Hygiene (10 pts)
Signals:
- `no_active_campaigns` → 0 pts
- `many_removed_or_paused_campaigns` → -3 pts
- `spend_concentration_risk` or `conversion_concentration_risk` → -3 pts each

---

## Thresholds (Documented, Adjustable)

```python
HEALTH_SCORE_THRESHOLDS = {
  "zero_conv_spend_critical": 100,    # currency native units
  "zero_conv_spend_warning": 20,
  "low_roas_threshold": 2.0,
  "high_cpa_multiplier": 2.0,         # CPA > 2x account average = high
  "low_ctr_threshold_pct": 0.5,       # CTR < 0.5%
  "low_ctr_min_impressions": 500,
  "high_cpc_multiplier": 2.5,         # avg_cpc > 2.5x account median
  "paused_winner_min_conversions": 5,
  "paused_winner_min_roas": 3.0,
  "spend_concentration_risk_pct": 80, # >80% spend in one campaign
  "conv_concentration_risk_pct": 90,  # >90% convs in one campaign
}
```

---

## Trend (Future)

- Track score per day in `google_ads_health_snapshots` table
- Show 30-day trend sparkline
- Alert when score drops > 10 points in 7 days

---

## Rules

- No fake scores. If data is insufficient → score_status: "insufficient_data"
- All subscores must be traceable to specific signal evidence
- No LLM in score computation
- Score must be explainable: "Your Waste Control score is 15/25 because 2 campaigns have spend with no conversions."
