# Google Ads AI Ask — Next Plan

Phase: PLANNED (not implemented in Phase 2E)  
Target: Phase 2G or later  

---

## Overview

`POST /api/connectors/google-ads/ask` — natural language queries about account
intelligence. Backed by Responses API with structured JSON output.

No mutations. No invented data. Context-grounded responses only.

---

## Endpoint

```
POST /api/connectors/google-ads/ask
Content-Type: application/json
```

### Request Body

```json
{
  "customer_id": "1234567890",
  "manager_customer_id": "8924163684",
  "question": "Why is my ROAS dropping?",
  "mode": "basic",
  "context_modules": ["account_health", "overview"],
  "date_range": "LAST_30_DAYS"
}
```

### mode values

- `"basic"` — fast, concise answer using gpt-4o-mini or equivalent
- `"reasoning"` — deeper analysis using o3-mini or equivalent with reasoning effort

---

## Behavior

1. Resolve customer_id → fetch intelligence context (overview + account_health + signals)
2. Build structured prompt with:
   - Account performance summary
   - Signal list (severity, evidence, recommendations)
   - Currency context
   - Explicit "you are looking at demo data" warning if source=mock
3. Call Responses API (not Chat Completions)
4. Request structured JSON output with schema enforcement
5. Return answer with source_truth, currency context, and confidence flag

---

## Responses API Integration

```python
# mode=basic
client.responses.create(
    model="gpt-4o-mini",
    input=[{"role": "user", "content": prompt}],
    text={"format": {"type": "json_schema", "schema": GADS_ASK_RESPONSE_SCHEMA}}
)

# mode=reasoning
client.responses.create(
    model="o3-mini",
    reasoning={"effort": "medium"},
    input=[{"role": "user", "content": prompt}],
    text={"format": {"type": "json_schema", "schema": GADS_ASK_RESPONSE_SCHEMA}}
)
```

reasoning.effort values: `"low"` / `"medium"` / `"high"`

---

## Structured Output Schema

```json
{
  "answer": "string — main answer, 2-4 sentences",
  "key_findings": ["string", "..."],
  "recommended_actions": ["string", "..."],
  "confidence": "high|medium|low",
  "caveats": ["string — data quality caveats"],
  "data_source": "google_ads_api|mock_fallback|mock"
}
```

---

## Hard Rules

- **No invented data**: Model must only reference metrics present in the context payload.
  Prompt must include: "Do not invent metrics not present in the data provided."
- **No mutations**: Response must never suggest specific Google Ads API write calls.
  "Consider pausing X" is OK. "Call mutateAdGroup with..." is not.
- **No secrets in prompt**: Never include access_token, refresh_token, developer_token,
  client_secret, or any OAuth material in the prompt or response.
- **Source truth in prompt**: If source=mock or mock_fallback, prompt must include:
  "Note: this data is demo/fallback data, not live account data. Caveat all insights accordingly."
- **Currency in prompt**: Always include currency_code in the prompt context.
  Never let the model guess or assume USD.
- **Rate limiting**: AI Ask endpoint must have per-user rate limiting.

---

## Orchestrator Draft Integration (Future)

- AI Ask responses may feed into a draft Flows v3 step for human approval
- Draft step: "AI suggested pausing 2 campaigns. Review and approve."
- No auto-apply
- Approval required before any action

---

## Rollout

1. Phase 2G: `mode=basic` only, context-only (no user-free-text questions)
2. Phase 2H: `mode=reasoning` + user questions via text input
3. Phase 2I: Orchestrator draft integration for recommendation review
