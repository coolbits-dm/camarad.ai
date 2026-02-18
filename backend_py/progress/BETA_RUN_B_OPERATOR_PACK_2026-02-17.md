# Run B Operator Pack (2026-02-17)

Purpose:
- Execute controlled beta sessions with 1-3 external users.
- Capture deterministic funnel traces + structured feedback in one pass.

## 1) Assign Tester Links
- U1: `https://camarad.ai/?src=beta_u1`
- U2: `https://camarad.ai/?src=beta_u2`
- U3: `https://camarad.ai/?src=beta_u3`

Hard rules for testers:
- Keep same browser session end-to-end (landing -> demo -> signup -> first chat).
- Do not switch device mid-session.
- Complete at least one useful chat output after signup.

## 2) Invite Message (short)
Use template:
- `progress/BETA_USER_MESSAGE_TEMPLATE_2026-02-14.md`

## 3) Session Flow to Validate
1. `landing_view` (`/` with `src=beta_uX`)
2. `demo_open` (`/platform-demo` or `/chat-demo`)
3. `signup_click` (`/signup`)
4. `first_chat_send` (chat POST/API message)
5. `first_useful_output` (manual tester confirmation)

## 4) Trace Collection Commands
Live watch during tester session (recommended):
```bash
cd /opt/camarad
bash scripts/beta_trace_watch.sh beta_u1
```
Stop with `Ctrl+C`, then run collectors below.

After each tester session:
```bash
cd /opt/camarad
bash scripts/beta_trace_collect.sh beta_u1
bash scripts/beta_trace_collect_v2.sh beta_u1
```
Repeat for `beta_u2`, `beta_u3`.

Recommended (saves both traces to files automatically):
```bash
cd /opt/camarad
bash scripts/beta_trace_collect_save.sh beta_u1
bash scripts/beta_trace_collect_save.sh beta_u2
bash scripts/beta_trace_collect_save.sh beta_u3
```

## 5) Feedback Capture
Fill:
- `progress/BETA_FEEDBACK_GRID_2026-02-14.md`

Required per tester:
- Completed funnel (yes/no)
- TTFUO (minutes)
- Top blockers (1-3)
- Top value moments (1-3)

Strict feedback block format (copy/paste per user):
```text
## beta_uX — feedback

### Top 5 blockers (cu severitate)
1) [P0/P1/P2] ce s-a blocat + unde + de ce
2)
3)
4)
5)

### Top 5 value moments
1) moment + ce a fost util + impact
2)
3)
4)
5)

### 3 UI-only fixes (impact mare, risc mic)
1) Fix: ... | Unde: ... | Expected: ...
2)
3)

### TTFUO
- useful output definition:
- observed:
- what slowed first value:
```

## 6) Acceptance Gate for Run B
- >= 3 complete first-session traces
- >= 1 tester reaches useful output in < 3 minutes
- Consolidated top 5 blockers + top 5 value moments filled

## 7) Debrief Output (what to produce after Run B)
Create one short note (new file suggested):
- `progress/BETA_RUN_B_DEBRIEF_<timestamp>.md`

Include:
- funnel completion table
- TTFUO distribution
- ranked blockers (freq x severity)
- ranked value moments
- top 3 UI-only fixes to implement next

Fast generator (from latest trace files + feedback grid):
```bash
cd /opt/camarad
/opt/camarad/.venv/bin/python scripts/build_beta_run_b_debrief.py \
  --trace-dir logs/beta_traces \
  --feedback-grid progress/BETA_FEEDBACK_GRID_2026-02-14.md
```
