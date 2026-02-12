# Camarad Roadmap (2026)

Data de referinta: 2026-02-11

Acest roadmap este ordonat pentru impact maxim cu risc minim.

## M0 - Edge Migration Baseline

Obiectiv: mutare sigura pe noul stack, fara downtime vizibil.

Status: `done` (2026-02-11)

Livrat:
- Nginx reverse proxy pentru `camarad.ai`, `www.camarad.ai`, `api.camarad.ai`
- SSL Let's Encrypt activ
- PM2 stabil (`camarad` online), `coolbits` neatins
- cutover Cloudflare pentru `api.camarad.ai`
- worker route vechi eliminat pentru `api.camarad.ai/*`

Acceptanta:
- `https://api.camarad.ai/{,orchestrator,connectors,settings}` raspunde `HTTP 200`
- fara `x-powered-by: Express` pe `api.camarad.ai`

## M1 - Reliability Hardening

Obiectiv: reducere risc operational pe productie.

Status: `in_progress` (majoritar done)

Livrat:
- runtime mutat pe Gunicorn (`4 workers`, `gevent`) sub PM2
- health endpoints (`/healthz`, `/readyz`)
- backup automat local (`backup.sh` + `camarad-backup.timer`, daily 03:00)
- log hygiene Nginx (noise scan routes blocate/no-log)

Ramas pentru inchidere milestone:
- logrotate clar pentru `/opt/camarad/logs/*.log` (retentie)
- mini monitoring operational (alarma simpla pe 5xx burst)

Acceptanta:
- restart/reboot safe fara interventie manuala
- erorile reale ies clar din loguri
- backup zilnic verificabil + restore drill minimal

## M2 - Connector Reality Layer (Coolbits Gateway)

Obiectiv: inlocuirea mock-urilor critice cu date reale.

Status: `next`

Ordine:
1. Google Ads (prioritate maxima)
2. GA4
3. GSC + GTM

Scope:
- activare gateway sub flag (`COOLBITS_GATEWAY_ENABLED`)
- mapare endpoint-uri Camarad <-> Coolbits cu timeout/retry
- fallback sigur la mock la eroare gateway
- UI state clar: `connected`, `disconnected`, `degraded/fallback`

Acceptanta:
- `accounts/campaigns/keywords/metrics` aduc date reale pentru Google Ads
- fallback la mock nu rupe UI
- erorile API sunt explicite (`4xx/5xx`) cu mesaj util

## M3 - Client-Centric Data Safety

Obiectiv: izolarea stricta per client pe tot produsul.

Status: `planned`

Scope:
- audit complet endpoint-uri pentru `X-Client-ID`
- teste automate pentru leakage cross-client
- actiuni UX: `New Chat with Client`, `Client Drawer`, `Linked Accounts`

Acceptanta:
- zero leakage cross-client pe chat/flows/connectors/history/settings
- comportament consistent in sidebar, orchestrator, settings

## M4 - Orchestrator Production Readiness

Obiectiv: orchestrator utilizabil in demo si productie usoara.

Status: `planned`

Scope:
- template gallery reala (minim 10 template-uri business)
- run trace stabil (JSON/CSV) + execution history per client
- validari de flow (guardrails) inainte de run
- replay run din istoric

Acceptanta:
- run-uri repetitive fara regressii UI/API
- trace util pentru debugging/audit

## M5 - Data + Knowledge (RAG v2)

Obiectiv: raspunsuri mai bune, cu surse si ingestie controlata.

Status: `planned`

Scope:
- pipeline clar ingest (`documents -> chunks -> searchable index`)
- imbunatatire ranking/citations
- evaluare migrare vector store daca SQLite devine bottleneck

Acceptanta:
- raspunsuri cu surse consistente
- latenta stabila sub trafic normal

## M6 - Product UX and Conversion

Obiectiv: crestere adoptie + claritate first-run.

Status: `planned`

Scope:
- landing polish (autocomplete, CTA, micro-interactions)
- onboarding first session
- empty states/error states coerente

Acceptanta:
- first-time user ajunge la "first value" in < 2 minute

## M7 - Security and Governance

Obiectiv: control secret management si operare sigura.

Status: `planned`

Scope:
- policy token scopes minim + expirare
- checklist incident response pentru secret leak
- secret scan periodic in repo/workspace

Acceptanta:
- niciun token activ expus in documentatie/cod
- rotatie token standardizata si documentata

## Milestone Governance

- Nu avansam milestone fara criteriile de acceptanta bifate.
- Fiecare schimbare de productie are rollback explicit.
- Orice secret expus accidental este rotit imediat.
- Pentru fiecare milestone: update in `progress/STATUS_YYYY-MM-DD.md` + `progress/NEXT_STEPS.md`.
