# Beta Agent Landing Funnel Audit (2026-02-18 17:08:24Z)

## Method
- source: latest per-token trace file from `logs/beta_traces`
- session selector: same UA + `2700s` post-landing (best score candidate)
- funnel events:
  - `agent_landing_view`: GET `/agents/<id>` with `src=beta_uX`
  - `agent_landing_cta_click`: GET `/api/auth/google/start` with `from=agent-landing&agent=<id>`
  - `post_oauth_redirect_to_chat`: GET `/chat/...` with `from=agent-landing&agent=<id>`
  - `first_chat_send`: first POST `/chat/*|/api/chat|/api/chats`

## Sources Read
| Token | Agent | Trace file | Parsed events |
|---|---|---|---:|
| beta_u1 | ppc | - | 0 |
| beta_u2 | ceo | - | 0 |
| beta_u3 | devops | - | 0 |

## Funnel Verdict
| Token | Agent | Status | Landing View | CTA Click | Post OAuth Chat | First Chat Send | Missing |
|---|---|---|---|---|---|---|---|
| beta_u1 | ppc | fail | False | False | False | False | agent_landing_view,agent_landing_cta_click,post_oauth_redirect_to_chat,first_chat_send |
| beta_u2 | ceo | fail | False | False | False | False | agent_landing_view,agent_landing_cta_click,post_oauth_redirect_to_chat,first_chat_send |
| beta_u3 | devops | fail | False | False | False | False | agent_landing_view,agent_landing_cta_click,post_oauth_redirect_to_chat,first_chat_send |

## Raw Event Counts (selected session)
| Token | view_hits | cta_hits | post_oauth_chat_hits | first_send_hits |
|---|---:|---:|---:|---:|
| beta_u1 | 0 | 0 | 0 | 0 |
| beta_u2 | 0 | 0 | 0 | 0 |
| beta_u3 | 0 | 0 | 0 | 0 |

## Summary
- pass_count: `0/3`
- gate condition: `3/3 full agent landing funnel` before scaling paid traffic
