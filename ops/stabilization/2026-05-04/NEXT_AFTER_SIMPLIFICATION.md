# Next After Simplification

## Recommended Order

1. Make repo/live explainable with clean commit and deploy traceability.
2. Polish Search Terms only if it remains a priority after the UI cleanup lands.
3. Account Health Score v1.
4. PMax Intelligence.
5. AI Ask Basic/Reasoning.

## 1. Make Repo/Live Explainable

Benefit:

- Restores a clean chain from git commit to production source.
- Removes ambiguity around Search Terms, Marketing Audit, and PPC Agent being live without a deploy report.

Risk:

- Requires careful splitting of already-live dirty work.
- `connectors.html` contains both Marketing Audit/PPC UI and Google Ads simplification deltas, so staging must be deliberate.

Dependencies:

- Decide whether Marketing Audit/PPC Agent should be kept, hidden, or backed out later.
- Add/commit `backend_py/test_ppc_agent.py` only if intentionally accepting that feature surface.

Recommendation:

- The source split is now handled by the Marketing Audit/PPC reconciliation commit. The remaining operational risk is deploy traceability: `_buildinfo` and deploy reports still need to name the actual SHA.

## 2. Search Terms Polish

Benefit:

- Search Terms appears live and test-backed; polish would improve immediate usefulness.

Risk:

- Can add UI complexity again if done before the Reports workspace is deployed and stabilized.

Dependencies:

- Keep read-only behavior.
- No Google Ads mutation/write APIs.
- Use source and currency badges consistently.

Recommendation:

- Next product-facing task after cleanup, not before.

## 3. Account Health Score v1

Benefit:

- Gives users a single summary signal and a clear recommended next action.

Risk:

- Score logic can become arbitrary unless based on explicit, inspectable inputs.

Dependencies:

- Stable Reports/Account Health card.
- Clear source/currency indicators.

Recommendation:

- Build after Search Terms polish or alongside it only if the scoring rubric is small and documented.

## 4. PMax Intelligence

Benefit:

- High value for Google Ads accounts using Performance Max.

Risk:

- PMax reporting surfaces can be sparse or segmented differently; risk of confusing partial data with account truth.

Dependencies:

- Capability detection.
- Clear `planned`, `partial`, `live`, and fallback states.

Recommendation:

- Keep planned until the read-only query surface is proven with tests.

## 5. AI Ask Basic/Reasoning

Benefit:

- Lets users ask natural-language questions over the selected account.

Risk:

- Higher trust/safety burden: answers must cite source, account, date range, and mock/live state.

Dependencies:

- Stable read-only data context.
- Provider policy and chat hardening remain green.

Recommendation:

- Defer until repo/live traceability and the core Google Ads UI are settled.

## Exact Next Prompt Recommendation

```text
Codex: make Camarad repo/live explainable without deploying.

Do not touch /opt/camarad, do not restart services, do not rsync, do not read .env, and do not deploy.

In /opt/camarad-repo, split the currently dirty work into traceable commits or a documented non-commit plan:
1. Identify all pre-existing Marketing Audit/PPC Agent changes in README.md, backend_py/app.py, backend_py/templates/connectors.html, backend_py/test_ppc_agent.py, and related docs.
2. Decide whether they can be committed as a separate already-live reconciliation commit with tests, or should remain uncommitted pending product review.
3. Keep the Google Ads UI simplification separate from Marketing Audit/PPC Agent.
4. Run the same PYTHONPATH test sweep and document root import-path noise separately.
5. Do not deploy. Provide commit SHA(s) only if commits are clean and scoped.
```
