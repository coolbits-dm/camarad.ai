# Beta Run B Funnel Audit (2026-02-18 07:42:09Z)

## Method
- source of truth: latest per-token trace file from `logs/beta_traces` (same source as debrief generator)
- session window: `2700s` post-landing, same-User-Agent matching (same logic as `build_beta_run_b_debrief.py`)
- event defs: landing=`GET /?src=beta_uX`, demo=`GET /platform-demo|/chat-demo`, signup=`GET /signup`, first_chat_send=`POST /chat/*|/api/chat|/api/chats`

## Sources Read
| Token | Trace file | Parsed log events |
|---|---|---:|
| beta_u1 | /opt/camarad/logs/beta_traces/trace_v2_beta_u1_20260218T004614Z.log | 204 |
| beta_u2 | /opt/camarad/logs/beta_traces/trace_v2_beta_u2_20260218T004621Z.log | 213 |
| beta_u3 | /opt/camarad/logs/beta_traces/trace_v2_beta_u3_20260218T004628Z.log | 204 |

## Funnel Verdict
| Token | Status | Landing | Demo | Signup | First Chat Send | Missing | Recommendation |
|---|---|---|---|---|---|---|---|
| beta_u1 | fail | True | False | False | False | demo,signup,first_chat_send | Did not reach signup; improve demo->signup CTA visibility and copy. |
| beta_u2 | fail | True | True | True | False | first_chat_send | Reached signup but no chat send; improve post-signup CTA to first message. |
| beta_u3 | fail | True | False | False | False | demo,signup,first_chat_send | Did not reach signup; improve demo->signup CTA visibility and copy. |

## Raw Event Counts (in selected trace file)
| Token | landing_hits | demo_hits | signup_hits | first_chat_send_hits |
|---|---:|---:|---:|---:|
| beta_u1 | 4 | 1 | 1 | 0 |
| beta_u2 | 7 | 2 | 2 | 0 |
| beta_u3 | 4 | 1 | 1 | 0 |

## Summary
- pass_count: `0/3`
- gate condition: `3/3 complete` before external beta expansion

## Root Cause (3 bullets)
1. Initial debrief version (`...00-46-38Z`) used permissive text matching over whole trace dump and could count hint lines / unrelated curl probes as funnel events.
2. Audit scripts switched to parsed nginx-style log events and session-scoped matching; this removed false positives and exposed real missing steps.
3. Source mismatch risk existed across helper scripts; this audit now uses the same trace source and event logic as current debrief parser.

## What Changed
- `beta_trace_funnel_audit.py` now consumes same source + logic as debrief (`build_beta_run_b_debrief.py`).
- Added explicit `Method`, `Sources Read`, and `Raw Event Counts` sections for evidence.
- Added `--verbose` option to print per-token sources and counts.

## Remaining Limitation
- If a user journey happens mostly client-side without corresponding origin log requests, server-log-based audit cannot observe that step; manual feedback/event beacon is still needed.
- historical note: old debrief reported `complete traces: 3/3` before parser hardening.
