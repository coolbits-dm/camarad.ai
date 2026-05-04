# Search Terms — Next Actions Plan
**Phase:** 2F  
**After:** Phase 2E.2 (Search Terms Intelligence v0)

---

## 1. Negative Keyword Draft Recommendations

**Status:** Not implemented. Planned for approval-gated flow.

### Design
- New endpoint: `POST /api/connectors/google-ads/intelligence/search-terms/draft-negatives`
  - Reads current waste signals
  - Returns a list of draft negative keyword suggestions
  - Does NOT apply anything
  - Each suggestion includes: term, match type, campaign, ad group, reason
- Draft is stored in DB table `google_ads_negative_kw_drafts`
- User reviews in UI before any action

### Approval Gate
- UI shows draft table with approve/reject per term
- Batch approve only available after per-term review
- Approval stores state in `google_ads_negative_kw_actions` table
- Actual application to Google Ads requires a separate confirmed action

### No Auto-Apply
- Negative keywords are never applied without explicit user approval
- Even when approved, actual mutation requires a future flow step with explicit confirmation

---

## 2. Exact/Phrase Keyword Expansion Candidates

**Status:** Planned.

### Design
- Winner terms with high conversions and no exact-match keyword in the ad group
- Recommendation: "Consider adding as [exact match] keyword"
- Output as draft expansion candidates — not auto-added
- Endpoint: `GET /api/connectors/google-ads/intelligence/search-terms/expansion-candidates`

---

## 3. Approval-Gated Action Drafts

**Status:** Planned. Requires Flows v3 draft step.

### Draft Flow Integration
- Orchestrator flow: `google_ads_negative_kw_draft_flow`
- Steps:
  1. `fetch_search_terms` — read-only, produces waste candidates
  2. `draft_negatives` — human reviews, approves/rejects per term
  3. `confirm_apply` — explicit confirmation with account + term list shown
  4. `apply_negatives` — only executes if step 3 confirmed; mutates Google Ads API

### Safeguards
- Every mutation step shows account_id, customer_name, change preview before executing
- Applied changes logged to `google_ads_action_log` table
- Rollback not automated but log enables manual undo

---

## 4. Orchestrator Flow Draft Integration

**Status:** Design only. Not implemented.

```yaml
flow: google_ads_search_terms_review
trigger: manual | scheduled
steps:
  - id: fetch_terms
    type: connector
    action: google_ads_search_terms
    params: {customer_id, days: 30}
  - id: review_waste
    type: human_approval
    input: fetch_terms.signals[waste_search_terms]
    required: true
  - id: draft_negatives
    type: connector
    action: google_ads_draft_negatives
    condition: review_waste.approved_terms is not empty
  - id: apply_negatives
    type: connector
    action: google_ads_apply_negatives
    condition: draft_negatives.confirmed == true
    gate: explicit_confirmation
```

---

## 5. Constraints (must not change)

- No direct mutation until approval system is connected
- Approval system must be connected before any write endpoint is created
- All negative keyword mutations require human confirmation per account
- No bulk apply across accounts without per-account confirmation
- Every applied mutation logged with user_id, timestamp, account_id, term, match_type
