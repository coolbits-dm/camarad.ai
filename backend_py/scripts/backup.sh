#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/camarad"
BACKUP_DIR="${APP_DIR}/backups"
DATE="$(date +%Y%m%d_%H%M%S)"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
LOCK_FILE="${BACKUP_DIR}/.backup.lock"

# Optional runtime config for remote backup targets.
# Expected path: /opt/camarad/.env.backup
if [ -f "${APP_DIR}/.env.backup" ]; then
  set -a
  # shellcheck disable=SC1091
  . "${APP_DIR}/.env.backup"
  set +a
fi

mkdir -p "${BACKUP_DIR}"

# Prevent overlapping runs.
exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "Backup already running, exiting."
  exit 0
fi

DB_PATH="${APP_DIR}/camarad.db"
DB_BASENAME="camarad.db_${DATE}.sqlite"
DB_BACKUP_PATH="${BACKUP_DIR}/${DB_BASENAME}"

# Prefer SQLite online backup for consistency; fallback to file copy.
if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "${DB_PATH}" ".backup '${DB_BACKUP_PATH}'"
else
  cp -a "${DB_PATH}" "${DB_BACKUP_PATH}"
fi

gzip -f "${DB_BACKUP_PATH}"

# Build config archive from known app files/folders.
CONFIG_BACKUP="${BACKUP_DIR}/configs_${DATE}.tar.gz"
cd "${APP_DIR}"
TAR_ITEMS=()
for item in .env config.py templates static; do
  [ -e "$item" ] && TAR_ITEMS+=("$item")
done
for item in ecosystem*.js; do
  [ -e "$item" ] && TAR_ITEMS+=("$item")
done
if [ ${#TAR_ITEMS[@]} -gt 0 ]; then
  tar -czf "${CONFIG_BACKUP}" "${TAR_ITEMS[@]}"
fi

# Cleanup old backups by retention policy.
find "${BACKUP_DIR}" -type f -name "camarad.db_*.sqlite.gz" -mtime +"${RETENTION_DAYS}" -delete || true
find "${BACKUP_DIR}" -type f -name "configs_*.tar.gz" -mtime +"${RETENTION_DAYS}" -delete || true

# Optional remote sync.
# Supported modes:
#   REMOTE_BACKUP_MODE=rsync
#   REMOTE_BACKUP_MODE=s3
REMOTE_BACKUP_MODE="${REMOTE_BACKUP_MODE:-none}"
REMOTE_BACKUP_OK=1

if [ "${REMOTE_BACKUP_MODE}" = "rsync" ]; then
  RSYNC_TARGET="${RSYNC_TARGET:-}"
  RSYNC_SSH_KEY="${RSYNC_SSH_KEY:-}"
  if [ -z "${RSYNC_TARGET}" ]; then
    echo "Remote backup skipped: RSYNC_TARGET not set."
  elif ! command -v rsync >/dev/null 2>&1; then
    echo "Remote backup failed: rsync not installed."
    REMOTE_BACKUP_OK=0
  else
    RSYNC_ARGS=(-az --delete --exclude '*.tmp')
    if [ -n "${RSYNC_SSH_KEY}" ]; then
      RSYNC_ARGS+=(-e "ssh -i ${RSYNC_SSH_KEY} -o StrictHostKeyChecking=accept-new")
    fi
    if ! rsync "${RSYNC_ARGS[@]}" "${BACKUP_DIR}/" "${RSYNC_TARGET}/"; then
      echo "Remote backup failed: rsync error."
      REMOTE_BACKUP_OK=0
    fi
  fi
elif [ "${REMOTE_BACKUP_MODE}" = "s3" ]; then
  S3_URI="${S3_URI:-}"
  S3_ENDPOINT_URL="${S3_ENDPOINT_URL:-}"
  if [ -z "${S3_URI}" ]; then
    echo "Remote backup skipped: S3_URI not set."
  elif ! command -v aws >/dev/null 2>&1; then
    echo "Remote backup failed: aws cli not installed."
    REMOTE_BACKUP_OK=0
  else
    AWS_ARGS=(s3 sync "${BACKUP_DIR}/" "${S3_URI}" --delete)
    if [ -n "${S3_ENDPOINT_URL}" ]; then
      AWS_ARGS+=(--endpoint-url "${S3_ENDPOINT_URL}")
    fi
    if ! aws "${AWS_ARGS[@]}"; then
      echo "Remote backup failed: aws s3 sync error."
      REMOTE_BACKUP_OK=0
    fi
  fi
fi

echo "Backup completed: ${DATE}"
ls -lh "${BACKUP_DIR}" | tail -n 10

if [ "${REMOTE_BACKUP_OK}" -ne 1 ]; then
  echo "Backup finished with remote-sync warnings (local backup is OK)."
  exit 0
fi
