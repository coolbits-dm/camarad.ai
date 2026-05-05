# Live/Repo Reconciliation

Date: 2026-05-05 Europe/Bucharest

## Guardrails

- No production files changed.
- No deploy or service restart performed.
- No rsync used.
- No secrets or `.env` content read or printed.
- No Google Ads write/mutation API called.

## Repo State

- Repo path: `/opt/camarad-repo`
- Branch: `feature/google-ads-search-terms-2026-05-04`
- Starting HEAD: `7825bb71e7d75d1790d84517b0e02f7901a57de5`
- Reconciliation commit created: `e18b37f` (`chore(reconcile): capture live marketing audit ppc work`)
- Origin branch: `origin/feature/google-ads-search-terms-2026-05-04`
- Origin SHA: `7825bb71e7d75d1790d84517b0e02f7901a57de5`
- Local branch had no upstream configured before this stabilization pass.

Recent relevant HEAD history:

- `7825bb7` Search Terms Intelligence
- `8b82475` Google Ads intelligence modules
- `69afca9` safe report query and currency normalization
- `8287e0d` source truth fix
- `2c277e5` Google Ads Account Intelligence

## Dirty Working Tree

Tracked dirty files at the start of the pass:

- `README.md`
- `backend_py/app.py`
- `backend_py/templates/connectors.html`

Dirty stat before this stabilization pass:

```text
README.md                            |   27 +
backend_py/app.py                    |  831 ++++++++++++++++++++++++
backend_py/templates/connectors.html | 1157 ++++++++++++++++++++++++++++++++--
3 files changed, 1945 insertions(+), 70 deletions(-)
```

Tracked diff against HEAD after the UI simplification edits:

```text
README.md                            |   27 +
backend_py/app.py                    |  831 ++++++++++++++++++++
backend_py/templates/connectors.html | 1413 ++++++++++++++++++++++++++++++----
3 files changed, 2111 insertions(+), 160 deletions(-)
```

Tracked dirty files after the Marketing Audit/PPC reconciliation commit and UI simplification reapply:

- `README.md`
- `backend_py/templates/connectors.html`

Notable untracked files still present:

- `CURRENT_SPRINT.md`
- `ROADMAP.md`
- `WORK_QUEUE.md`
- `docs/PRODUCT_BRIEF.md`
- `ops/CLAW_OPERATING_PLAN.md`
- prior ops/reconciliation, review, deploy, and audit docs
- `backend_py/opt/` copied operational artifacts

## Live Vs Repo

Mapping: repo `backend_py/` maps to live `/opt/camarad/`.

Direct comparisons at the start of this stabilization pass:

- `diff -u backend_py/app.py /opt/camarad/app.py`: no output
- `diff -u backend_py/templates/connectors.html /opt/camarad/templates/connectors.html`: no output

SHA evidence:

- repo `backend_py/app.py` matches live `/opt/camarad/app.py`
- repo `backend_py/templates/connectors.html` matches live `/opt/camarad/templates/connectors.html`

Conclusion at start: live production source matched the dirty repo worktree, not clean HEAD.

After the reconciliation split and repo-only UI simplification pass:

- `backend_py/app.py` still matches live `/opt/camarad/app.py`.
- `backend_py/templates/connectors.html` no longer matches live because the repo now contains the undeployed UI simplification.
- The live template still has six visible Google Ads tabs, including `Diagnostics` and `Intelligence`.
- The repo template now has five visible Google Ads tabs: `Overview`, `Campaigns`, `Reports`, `AI Brief`, `Settings`.
- No production file was copied or modified.
- The live app/template source is represented by reconciliation commit `e18b37f`; the UI simplification is the next repo-only delta after that commit.

## Buildinfo And Deploy Traceability

- Live `/api/_buildinfo` reports `commit=unknown`.
- Latest explicit deploy report found in production is for `8b82475`.
- Search Terms commit `7825bb7` appears pushed and live by source/endpoint evidence, but no deploy report was found for it.
- Marketing Audit/PPC-Agent work appears live by source parity and is now captured in commit `e18b37f`, but production still has no deploy report or buildinfo marker for that commit.

This means production source is now explainable from git, but production runtime metadata still cannot prove that commit because `/api/_buildinfo` reports `unknown` and no deploy report exists for it. The repo also has an additional undeployed UI-only template delta.

## Search Terms Status

- `7825bb7` is pushed.
- Live source contains `/api/connectors/google-ads/intelligence/search-terms`.
- Live unauthenticated smoke from the audit returned `source=mock`, `live_data=false`, rows and signals.
- Existing Search Terms tests pass when run with the correct Python path.
- Missing: deploy report for `7825bb7`.

## Marketing Audit / PPC Agent Status

Files involved:

- `backend_py/app.py`
- `backend_py/templates/connectors.html`
- `backend_py/test_ppc_agent.py`
- README/product/ops docs (dirty/untracked)

Routes/endpoints added in dirty `app.py`:

- `POST /api/intelligence/marketing/context`
- `POST /api/agents/ppc/run`

UI added in dirty `connectors.html`:

- Agency workspace banner
- Marketing Audit panel
- multi-section audit renderers
- PPC Specialist action-plan renderer
- GA4 Intelligence panels
- calls into the new marketing context and PPC endpoints

Tests:

- `backend_py/test_ppc_agent.py` is tracked by reconciliation commit `e18b37f`.
- It passed during audit with `AUTH_REQUIRED=0 COOLBITS_GATEWAY_ENABLED=false DATABASE=/tmp/ppc_agent_test.db PYTHONPATH=backend_py:.`.
- It passed again during this split with `AUTH_REQUIRED=0 COOLBITS_GATEWAY_ENABLED=false DATABASE=/tmp/camarad_ppc_agent_reconcile.db PYTHONPATH=backend_py:.`.

Live status:

- Live `app.py` and `connectors.html` contain this work because they match the dirty repo worktree.

Safety to commit:

- Technically test-backed for the PPC endpoint.
- Product-wise not safe to mix into the Google Ads UI simplification commit because it adds new backend product endpoints and a new marketing-audit workflow.
- It was committed separately as `e18b37f`.

Recommendation:

- Do not stage `backend_py/app.py` in the UI simplification commit.
- Do not stage `README.md` or product-roadmap docs in the UI simplification commit.
- Treat Marketing Audit/PPC-Agent as an already-live reconciliation commit:
  1. keep it separate from UI simplification,
  2. keep `backend_py/test_ppc_agent.py` with it,
  3. write a deploy report before any future production deploy,
  4. then decide whether to keep, hide, or back out that product surface.

## Recommended Split/Commit Plan

1. Stabilization docs and UI simplification:
   - `backend_py/templates/connectors.html`
   - `backend_py/test_google_ads_ui_simplification.py`
   - `ops/stabilization/2026-05-04/*.md`
   - Now safe to commit separately because Marketing Audit/PPC has been split into `e18b37f`.

2. Marketing Audit/PPC-Agent, completed:
   - `backend_py/app.py`
   - `backend_py/templates/connectors.html` hunks specific to Marketing Audit/PPC
   - `backend_py/test_ppc_agent.py`
   - committed as `e18b37f`
   - README/product docs intentionally not included.

3. Buildinfo/deploy traceability, separate later:
   - make `/api/_buildinfo` expose a real git SHA or deploy marker
   - require deploy report for every production change

## Current Risk

- Production runtime metadata is still not traceable because `_buildinfo` reports `commit=unknown`.
- The latest explicit deploy report is still older than Search Terms and the Marketing Audit/PPC reconciliation.
- The repo now has undeployed UI simplification changes after `e18b37f`.
- README/product-roadmap edits and historical ops artifacts remain dirty/untracked and were intentionally not staged.
