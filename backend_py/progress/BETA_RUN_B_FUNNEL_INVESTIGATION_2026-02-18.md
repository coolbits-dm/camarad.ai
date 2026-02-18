# Run B Funnel Investigation (2026-02-18)

## Objective
Explain and fix inconsistency:
- old debrief showed `3/3` complete
- later audit showed `0/3` complete

## A) Sources + windows (reproduced)

### Scripts and sources
- `scripts/beta_trace_collect_save.sh`
  - writes:
    - `logs/beta_traces/trace_beta_uX_<ts>.log` (legacy collector output)
    - `logs/beta_traces/trace_v2_beta_uX_<ts>.log` (v2 collector output)
- `scripts/build_beta_run_b_debrief.py`
  - reads latest `*beta_uX*.log` in `logs/beta_traces`
  - parses nginx-style lines and selects best session in `45m` post-landing window, same UA
- `scripts/beta_trace_funnel_audit.py` (patched in this block)
  - now reads the same latest trace files and uses same parser logic as debrief

### Permission / fallback behavior
- Collectors attempt `/var/log/nginx/access.log*` first.
- In this environment collector output includes:
  - `/var/log/nginx/access.log: Permission denied`
  - `/var/log/nginx/access.log.1: Permission denied`
- Fallback source is available and used:
  - `/opt/camarad/logs/access.log`

## B) Event definition comparison + evidence

### Root mismatch
- Old debrief (`BETA_RUN_B_DEBRIEF_2026-02-18T00-46-38Z.md`) used permissive text matching over full trace dump.
- That allowed false positives from hint lines and unrelated requests.
- Current debrief + audit use parsed log events only (method/path/ts/ua).

### Event definitions (current, aligned)
- landing: `GET /?src=beta_uX`
- demo: `GET /platform-demo` or `GET /chat-demo`
- signup: `GET /signup`
- first_chat_send: `POST /chat/*` or `POST /api/chat` or `POST /api/chats`

### Evidence snippets from raw traces (selected)

#### beta_u2 (landing/demo/signup observed)
- `GET /?src=beta_u2` @ `14/Feb/2026:22:23:12 +0200`
- `GET /platform-demo?src=landing_demo` @ `14/Feb/2026:22:23:15 +0200`
- `GET /signup?next=/app` @ `14/Feb/2026:22:23:57 +0200`
- No matching `POST /chat/*|/api/chat|/api/chats` in selected session window.

#### beta_u1 (landing observed, no session-local demo/signup/send)
- `GET /?src=beta_u1` @ `14/Feb/2026:22:28:18 +0200`
- demo/signup lines in file are from unrelated `curl` probe (different UA), not same user session.

#### beta_u3 (landing observed, no session-local demo/signup/send)
- `GET /?src=beta_u3` @ `14/Feb/2026:22:28:15 +0200`
- demo/signup lines in file are from unrelated `curl` probe (different UA), not same user session.

## C) Layer conclusions

- Frontend eventing:
  - Server-observable for landing/demo/signup when full-page requests occur.
  - `first_chat_send` requires actual POST hit; missing for all 3 in selected sessions.
- Backend logging:
  - Evidence available in `/opt/camarad/logs/access.log` via collector traces.
  - Parsed event counts confirm no first chat send.
- CDN/cache:
  - Not primary root cause here; mismatch was parser permissiveness, not cache.
- Deployment/pipeline:
  - Inconsistency caused by different parser generations, now aligned.

## D) Fix implemented

### Chosen option
- **Option 1** (preferred): audit consumes same truth source + same logic as debrief.

### Changes
- `scripts/beta_trace_funnel_audit.py`
  - imports and uses debrief parser (`_load_latest_trace`, `_parse_log_events`, `_extract_trace_summary`)
  - adds `--verbose`
  - reports:
    - sources read
    - fixed session window (`2700s`)
    - raw event counts per token
    - funnel verdict with missing steps
    - root cause/what changed/remaining limitation
- `progress/BETA_RUN_B_OPERATOR_PACK_2026-02-17.md`
  - explicit observability note added

## E) Re-run result

- New audit report:
  - `progress/BETA_RUN_B_FUNNEL_AUDIT_2026-02-18T07-41-17Z.md`
- Result:
  - `pass_count: 0/3`
  - `beta_u2`: reached signup, missing first chat send
  - `beta_u1`, `beta_u3`: missing demo/signup/first_chat_send in selected session

## Remaining limitation
- If a journey step is not represented as an origin request in server logs, automated log-based audit cannot prove it.
- Qualitative value/TTFUO usefulness still needs manual tester feedback.
