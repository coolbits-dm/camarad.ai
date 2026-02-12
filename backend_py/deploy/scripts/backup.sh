#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/var/www/camarad}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/camarad}"
TS="$(date +%Y%m%d_%H%M%S)"

mkdir -p "$BACKUP_DIR"

if [ -f "$APP_DIR/camarad.db" ]; then
  cp "$APP_DIR/camarad.db" "$BACKUP_DIR/camarad_${TS}.db"
fi

if [ -f "$APP_DIR/.env" ]; then
  cp "$APP_DIR/.env" "$BACKUP_DIR/camarad_env_${TS}.bak"
fi

tar -czf "$BACKUP_DIR/camarad_files_${TS}.tar.gz" -C "$APP_DIR" \
  app.py config.py ecosystem.production.config.js templates static requirements.txt

echo "Backup created in $BACKUP_DIR at $TS"
