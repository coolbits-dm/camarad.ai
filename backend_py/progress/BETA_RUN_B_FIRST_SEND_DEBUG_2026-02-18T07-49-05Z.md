# Run B First Chat Send Debug (2026-02-18 07:49:05Z)

## Method
- source: latest per-token trace in `logs/beta_traces`
- session selector: same UA as landing + 2700s window + max funnel score
- first_chat_send event: `POST /chat/*` OR `POST /api/chat` OR `POST /api/chats`

## beta_u1
- trace file: `logs/beta_traces/trace_v2_beta_u1_20260218T004614Z.log`
- parsed events: `204`
- selected landing: `2026-02-14 22:28:18 +0200`
- selected session key: `ua_sha1=05d4d98396`
- session events in window: `2`
- funnel flags: landing=`True`, demo=`False`, signup=`False`, first_chat_send=`False`
- event counts in selected session: landing=`2`, demo=`0`, signup=`0`, first_chat_send=`0`

### Evidence Lines (selected session)
| timestamp | method | status | path |
|---|---|---:|---|
| 2026-02-14 22:28:18 +0200 | GET | 200 | `/?src=beta_u1` |
| 2026-02-14 22:28:18 +0200 | GET | 200 | `/?src=beta_u1` |

- conclusion: **no first_chat_send POST observed in selected session**

## beta_u2
- trace file: `logs/beta_traces/trace_v2_beta_u2_20260218T004621Z.log`
- parsed events: `213`
- selected landing: `2026-02-14 22:23:12 +0200`
- selected session key: `ua_sha1=ee0f495596`
- session events in window: `9`
- funnel flags: landing=`True`, demo=`True`, signup=`True`, first_chat_send=`False`
- event counts in selected session: landing=`3`, demo=`1`, signup=`1`, first_chat_send=`0`

### Evidence Lines (selected session)
| timestamp | method | status | path |
|---|---|---:|---|
| 2026-02-14 22:23:12 +0200 | GET | 200 | `/?src=beta_u2` |
| 2026-02-14 22:23:15 +0200 | GET | 200 | `/platform-demo?src=landing_demo` |
| 2026-02-14 22:23:47 +0200 | GET | 302 | `/?src=beta_u2` |
| 2026-02-14 22:23:53 +0200 | GET | 200 | `/?src=beta_u2` |
| 2026-02-14 22:23:57 +0200 | GET | 200 | `/signup?next=/app` |

- conclusion: **no first_chat_send POST observed in selected session**

## beta_u3
- trace file: `logs/beta_traces/trace_v2_beta_u3_20260218T004628Z.log`
- parsed events: `204`
- selected landing: `2026-02-14 22:28:15 +0200`
- selected session key: `ua_sha1=05d4d98396`
- session events in window: `2`
- funnel flags: landing=`True`, demo=`False`, signup=`False`, first_chat_send=`False`
- event counts in selected session: landing=`2`, demo=`0`, signup=`0`, first_chat_send=`0`

### Evidence Lines (selected session)
| timestamp | method | status | path |
|---|---|---:|---|
| 2026-02-14 22:28:15 +0200 | GET | 200 | `/?src=beta_u3` |
| 2026-02-14 22:28:15 +0200 | GET | 200 | `/?src=beta_u3` |

- conclusion: **no first_chat_send POST observed in selected session**

