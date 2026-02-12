# Camarad.ai

Production-first repository for Camarad.ai.

## Structure

- `backend_py/` - live Flask/Python backend and UI templates currently running in production.
- `legacy/next_mock/` - archived legacy Next.js/TypeScript mock UI and early backend.

## Local Run (backend_py)

```bash
cd backend_py
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

App default health endpoint:

- `GET /healthz`

## PM2 run

From project root (`backend_py` already synced in deploy path):

```bash
pm2 restart camarad --update-env
```

## Required environment variables

Copy `.env.example` and set values for your environment.
Do not commit real secrets.
