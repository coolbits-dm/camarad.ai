# Stack Audit - 2026-02-11

Scop: snapshot tehnic complet pentru prioritizarea roadmap-ului.

## 1) Infra + Runtime

- Host activ productie: `185.146.87.91`
- Domenii active:
  - `camarad.ai`
  - `www.camarad.ai`
  - `api.camarad.ai`
- Edge:
  - Cloudflare proxied activ
  - Nginx reverse proxy catre `127.0.0.1:5051`
- App runtime:
  - PM2 process `camarad` (Gunicorn + gevent, 4 workers)
  - PM2 process `coolbits` online, separat, neatins
- Health:
  - `/healthz`
  - `/readyz`
- Backup:
  - local backup automat (`/opt/camarad/scripts/backup.sh`)
  - systemd timer daily 03:00 (`camarad-backup.timer`)
  - remote backup: disponibil in script, dar amanat operational

## 2) Aplicatie (backend)

- Backend principal este monolit Flask in `app.py`.
- Date principale:
  - `camarad.db` (aplicatie)
  - `connectors_api_docs.db` (API docs/RAG context)
- Structura de scoping client:
  - suport `X-Client-ID` in endpoint-uri cheie
  - tabele si relatii pentru `clients`, `client_connectors`, `flows`, `conversations`, `agents_config`, `connectors_config`

## 3) Conectori - stare curenta

- Endpoint-uri Google stack existente:
  - Google Ads: `accounts`, `campaigns`, `keywords`, `metrics`, `reports`, `generate-assets`, `test-call`
  - GA4: `properties`, `overview`, `pages`, `sources`, `events`, `devices`, `countries`, `funnel`, `timeseries`, `test-call`
  - GSC/GTM: endpoint-uri mock complete
- Realitate actuala:
  - majoritatea endpoint-urilor de mai sus ruleaza pe mock data
  - helper-ele Coolbits exista (`COOLBITS_GATEWAY_ENABLED`, `_coolbits_request`), dar nu sunt inca conectate la endpoint-urile Google Ads/GA4

## 4) Orchestrator

- API disponibile:
  - `/api/orchestrator/templates`
  - `/api/orchestrator/route`
  - `/api/orchestrator/agent-brief/<slug>`
  - `/api/orchestrator/execute`
  - `/api/orchestrator/history`
- Stare:
  - functional pentru demo/live mock-first
  - run trace + export + history deja existente

## 5) RAG + Knowledge

- Endpoint-uri active:
  - `/api/rag/search`
  - `/api/rag/api-docs`
- Stare:
  - retrieval bazat pe SQLite/text matching
  - fara vector store dedicat in productie
  - bun pentru baseline, dar necesita imbunatatire ranking/citations

## 6) Security + Ops

- Secret management:
  - tokenurile Cloudflare au fost rotite; recomandat sa ramana doar in medii controlate
- Logging:
  - noise filters Nginx implementate (scan paths)
  - urmeaza logrotate + monitorizare minima (5xx burst)
- Dependinte Python:
  - Flask, markdown, requests, beautifulsoup4, tqdm
  - gunicorn/gevent instalate in venv pentru runtime

## 7) Gaps prioritare (impact/risc)

1. Connector realism:
   - Google Ads/GA4/GSC/GTM inca mock-first
2. Client data safety:
   - necesar audit complet + teste automate cross-client
3. Observability:
   - lipseste metrica simpla de rata erori/latenta pe endpoint
4. RAG quality:
   - lipsesc citations robuste si evaluare retrieval

## 8) Decizii operationale active

- Backup remote amanat temporar:
  - motiv: Acronis activ pe VPS curent + lipsa credentiale VPS secundar
  - actiune ulterioara: activare rsync/s3 cand credentialele sunt disponibile

