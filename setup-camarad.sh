#!/usr/bin/env bash
# setup-camarad.sh
# Camarad/cbLM: Proxy identity tokens → Cloud Run (private) via nginx
# - Installs python deps
# - Writes /usr/local/bin/refresh_iap_token.py (mints ID tokens for UI/RELAY/CORE)
# - Writes /usr/local/bin/refresh_oidc.sh (runs Python and reloads nginx if valid)
# - Creates systemd units iap-refresh.service + iap-refresh.timer (45 min)
# - Runs initial refresh and prints validation summary

set -euo pipefail

# Constants (project and services)
PROJECT="camarad-ai"
REGION="europe-west3"
SA_EMAIL="proxy-invoker@${PROJECT}.iam.gserviceaccount.com"

# Fixed Cloud Run service URLs (audiences)
UI_URL="https://camarad-ui-735022872619.europe-west3.run.app"
RELAY_URL="https://relay-735022872619.europe-west3.run.app"
CORE_URL="https://core-735022872619.europe-west3.run.app"

# Paths
TOK_DIR="/run/camarad-tokens"
INC_DIR="/etc/nginx/includes"
URLS_FILE="/etc/camarad-cloudrun.urls"
SA_KEY="/etc/proxy-invoker.json"             # Optional; if present, used as ADC
PYTHON_SCRIPT="/usr/local/bin/refresh_iap_token.py"
OIDC_SCRIPT="/usr/local/bin/refresh_oidc.sh"
SYSTEMD_SERVICE="/etc/systemd/system/iap-refresh.service"
SYSTEMD_TIMER="/etc/systemd/system/iap-refresh.timer"
GCLOUD_BIN="${GCLOUD_BIN:-/usr/bin/gcloud}"

require_root() {
  if [[ $(id -u) -ne 0 ]]; then
    echo "[ERROR] Must run as root (sudo)." >&2
    exit 1
  fi
}

have_cmd() { command -v "$1" >/dev/null 2>&1; }

install_deps() {
  echo "[+] Installing dependencies (python3, venv, pip, nginx, curl, jq)…"
  apt-get update -y
  DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 python3-venv python3-pip nginx curl jq
  echo "[+] Installing Google auth libraries (system)…"
  pip3 install --upgrade google-auth google-auth-httplib2 google-auth-oauthlib >/dev/null 2>&1 || true

  mkdir -p "$TOK_DIR" "$INC_DIR"
  chown root:www-data "$TOK_DIR" "$INC_DIR"
  chmod 750 "$TOK_DIR" "$INC_DIR"
}

write_urls_file() {
  if [[ -f "$URLS_FILE" ]]; then
    echo "[i] ${URLS_FILE} already exists; leaving as-is."
  else
    echo "[+] Writing ${URLS_FILE} with service URLs"
    cat >"$URLS_FILE" <<EOF
UI_URL=${UI_URL}
RELAY_URL=${RELAY_URL}
CORE_URL=${CORE_URL}
EOF
    chmod 640 "$URLS_FILE"
  fi
}

write_python_script() {
  echo "[+] Writing ${PYTHON_SCRIPT}"
  cat >"$PYTHON_SCRIPT" <<'PY'
#!/usr/bin/env python3
import os
import json
import subprocess
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2 import service_account, id_token as google_id_token
import google.auth

TOK_DIR = Path("/run/camarad-tokens")
INC_DIR = Path("/etc/nginx/includes")
URLS_FILE = Path("/etc/camarad-cloudrun.urls")
GCLOUD_BIN = os.environ.get("GCLOUD_BIN", "/usr/bin/gcloud")
SA_KEY = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "/etc/proxy-invoker.json")

def load_urls():
    # Defaults; allow overrides from file
    urls = {
        "ui": os.environ.get("UI_URL", "https://camarad-ui-735022872619.europe-west3.run.app"),
        "relay": os.environ.get("RELAY_URL", "https://relay-735022872619.europe-west3.run.app"),
        "core": os.environ.get("CORE_URL", "https://core-735022872619.europe-west3.run.app"),
    }
    if URLS_FILE.exists():
        try:
            # shell-style VAR=... lines
            for line in URLS_FILE.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                if k == "UI_URL" and v:
                    urls["ui"] = v
                elif k == "RELAY_URL" and v:
                    urls["relay"] = v
                elif k == "CORE_URL" and v:
                    urls["core"] = v
        except Exception as e:
            print(f"[WARN] Failed to parse {URLS_FILE}: {e}", file=sys.stderr)
    return urls

def get_token_via_gcloud(audience: str) -> str | None:
    try:
        if not os.path.exists(GCLOUD_BIN):
            return None
        out = subprocess.check_output(
            [GCLOUD_BIN, "auth", "print-identity-token", f"--audiences={audience}"],
            stderr=subprocess.STDOUT,
            timeout=10,
        )
        tok = out.decode().strip()
        return tok if tok and tok.count(".") >= 2 else None
    except Exception:
        return None

def get_token_via_sa_key(audience: str) -> str | None:
    try:
        if not os.path.exists(SA_KEY):
            return None
        creds = service_account.IDTokenCredentials.from_service_account_file(
            SA_KEY, target_audience=audience
        )
        creds.refresh(Request())
        return creds.token
    except Exception:
        return None

def get_token_via_adc(audience: str) -> str | None:
    try:
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        # fetch_id_token will try using ADC-capable creds (service account/metadata)
        tok = google_id_token.fetch_id_token(Request(), audience)
        return tok
    except Exception:
        return None

def mint_token(audience: str) -> str:
    # Preference: gcloud → SA key → ADC
    tok = get_token_via_gcloud(audience)
    if not tok:
        tok = get_token_via_sa_key(audience)
    if not tok:
        tok = get_token_via_adc(audience)
    if not tok:
        print(f"[ERROR] Unable to mint identity token for audience={audience}", file=sys.stderr)
        sys.exit(3)
    return tok

def write_token_and_include(name: str, token: str):
    TOK_DIR.mkdir(parents=True, exist_ok=True)
    INC_DIR.mkdir(parents=True, exist_ok=True)

    tok_path = TOK_DIR / f"{name}.token"
    tok_path.write_text(token)
    os.chmod(tok_path, 0o640)

    inc_path = INC_DIR / f"auth_{name}.conf"
    # Only what nginx needs per requirement
    inc_path.write_text(f'proxy_set_header Authorization "Bearer {token}";\n')
    os.chmod(inc_path, 0o640)

def main():
    urls = load_urls()
    results = {}
    for key in ("ui", "relay", "core"):
        aud = urls.get(key)
        if not aud:
            print(f"[ERROR] Missing audience for {key}", file=sys.stderr)
            sys.exit(2)
        tok = mint_token(aud)
        write_token_and_include(key, tok)
        results[key] = len(tok)

    print(json.dumps({"status": "ok", "written": results}))
    return 0

if __name__ == "__main__":
    sys.exit(main())
PY
  chmod 750 "$PYTHON_SCRIPT"
  chown root:root "$PYTHON_SCRIPT"
}

write_refresh_script() {
  echo "[+] Writing ${OIDC_SCRIPT}"
  cat >"$OIDC_SCRIPT" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
PYTHON_SCRIPT="/usr/local/bin/refresh_iap_token.py"

# If service account key exists, export it for ADC
if [[ -f "/etc/proxy-invoker.json" ]]; then
  export GOOGLE_APPLICATION_CREDENTIALS="/etc/proxy-invoker.json"
fi

# Allow override of GCLOUD_BIN in env if needed
export GCLOUD_BIN="${GCLOUD_BIN:-/usr/bin/gcloud}"

# Run Python minter
"$PYTHON_SCRIPT"

# Reload nginx safely
if nginx -t; then
  systemctl reload nginx
else
  echo "[WARN] nginx config test failed; not reloading." >&2
fi
SH
  chmod 750 "$OIDC_SCRIPT"
  chown root:root "$OIDC_SCRIPT"
}

write_systemd_units() {
  echo "[+] Writing ${SYSTEMD_SERVICE}"
  cat >"$SYSTEMD_SERVICE" <<EOF
[Unit]
Description=Refresh IAP/OIDC tokens for Camarad Cloud Run upstreams
After=network-online.target

[Service]
Type=oneshot
ExecStart=${OIDC_SCRIPT}
User=root
Group=www-data
EOF

  echo "[+] Writing ${SYSTEMD_TIMER}"
  cat >"$SYSTEMD_TIMER" <<'EOF'
[Unit]
Description=Refresh IAP/OIDC tokens every 45 minutes

[Timer]
OnBootSec=15sec
OnUnitActiveSec=45min
Unit=iap-refresh.service

[Install]
WantedBy=timers.target
EOF

  systemctl daemon-reload
  systemctl enable --now iap-refresh.timer
}

run_initial_refresh() {
  echo "[+] Running initial refresh (mint tokens, write includes, reload nginx)…"
  # Run service once
  if ! systemctl start iap-refresh.service; then
    echo "[WARN] iap-refresh.service failed; running script directly." >&2
    "$OIDC_SCRIPT" || true
  fi
}

summarize() {
  echo "== Summary =="
  # 1) Token paths exist and size > 0
  ok_tokens=true
  for n in ui relay core; do
    if [[ ! -s "${TOK_DIR}/${n}.token" ]]; then
      echo "[-] Missing or empty token: ${TOK_DIR}/${n}.token"
      ok_tokens=false
    else
      echo "[+] Token present: ${TOK_DIR}/${n}.token ($(stat -c%s "${TOK_DIR}/${n}.token") bytes)"
    fi
  done

  # 2) nginx -t passes
  if nginx -t >/dev/null 2>&1; then
    echo "[+] nginx -t: OK"
  else
    echo "[-] nginx -t: FAILED"
  fi

  # 3) Cloud Run anonymous curl returns 403
  source "$URLS_FILE" || true
  RELAY="${RELAY_URL:-$RELAY_URL}"
  CORE="${CORE_URL:-$CORE_URL}"

  code_relay=$(curl -sS -o /dev/null -w '%{http_code}' "${RELAY}/api/health" || true)
  code_core=$(curl -sS -o /dev/null -w '%{http_code}' "${CORE}/api/health" || true)
  echo "[i] Direct Cloud Run (expect 403): relay=${code_relay}, core=${code_core}"

  # 4) Proxy path curl returns 200 (assumes nginx site already routes /relay/ and /core/)
  pr_relay=$(curl -sS -o /dev/null -w '%{http_code}' https://api.camarad.ai/relay/api/health || true)
  pr_core=$(curl -sS -o /dev/null -w '%{http_code}' https://api.camarad.ai/core/api/health || true)
  echo "[i] Via proxy (expect 200): relay=${pr_relay}, core=${pr_core}"

  echo
  echo "Helper note: If Cloud Run still returns 401/403, verify /etc/camarad-cloudrun.urls and IAM binding:"
  cat <<'IAM'
gcloud run services add-iam-policy-binding <service> \
  --project camarad-ai \
  --region europe-west3 \
  --member "serviceAccount:proxy-invoker@camarad-ai.iam.gserviceaccount.com" \
  --role roles/run.invoker
IAM
}

main() {
  require_root
  install_deps
  write_urls_file
  write_python_script
  write_refresh_script
  write_systemd_units
  run_initial_refresh
  summarize
  echo "[DONE] Camarad proxy token injector set up."
}

main "$@"