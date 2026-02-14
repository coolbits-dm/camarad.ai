# Controlled Beta Launch Prep (Run A)

Date: 2026-02-14
Owner: Andrei
Mode: No code changes

## 1) Tester Links (traceable)
Share one unique link per tester:
- Tester 1: `https://camarad.ai/?src=beta_u1`
- Tester 2: `https://camarad.ai/?src=beta_u2`
- Tester 3: `https://camarad.ai/?src=beta_u3`

Important:
- Tester must keep the same browser session from landing -> demo -> signup -> first chat.
- Prefer Incognito/private window for a clean trace.

## 2) Funnel to Capture
Target sequence:
1. `landing_view` (open `/` with `src=beta_uX`)
2. `demo_open` (open `/platform-demo` or `/chat-demo`)
3. `signup_click` (click `/signup?...`)
4. `first_chat_send` (first send in authenticated chat)

## 3) Manual Operator Checklist (per tester)
- [ ] Landing loaded with assigned `src` token
- [ ] Demo opened at least once
- [ ] Signup clicked
- [ ] First chat sent
- [ ] First useful output reached (record elapsed time)

Record times (UTC):
- Landing timestamp:
- Demo open timestamp:
- Signup click timestamp:
- First chat send timestamp:
- First useful output timestamp:
- Time-to-first-useful-output (TTFUO):

## 4) Acceptance (Run A)
- >= 3 complete first-session traces
- >= 1 tester reaches useful output in < 3 minutes
- Top 5 blockers + Top 5 value moments collected

## 5) Debrief Questions (send after session)
1. What did you try to do first?
2. What confused you in first 60 seconds?
3. What felt immediately valuable?
4. What blocked or slowed you down?
5. If this cost EUR 50-100/month, what must improve first?

## 6) Data Sources
- GA4 DebugView / events dashboard (if GTM/GA4 events already configured)
- Access logs grep by `src=beta_uX`

Use helper script:
```bash
bash scripts/beta_trace_collect.sh beta_u1
bash scripts/beta_trace_collect.sh beta_u2
bash scripts/beta_trace_collect.sh beta_u3
```
