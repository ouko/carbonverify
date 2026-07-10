#!/bin/bash
# PostgreSQL backup script for Docker Compose deployments.
# Run manually or via cron on the host.
#
# Usage:
#   ./scripts/backup-db.sh
#   S3_BUCKET=my-bucket ./scripts/backup-db.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${PROJECT_ROOT}/backups"
BACKUP_FILE="carbonverify_${TIMESTAMP}.sql.gz"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

# Find working docker-compose (handles stale standalone binaries on macOS)
find_docker_compose() {
  local project_root="${1:-$PROJECT_ROOT}"
  if command -v docker-compose >/dev/null 2>&1; then
    local test_output
    test_output=$(cd "$project_root" && docker-compose ps 2>&1) || true
    if ! echo "$test_output" | grep -q "client version 1.43 is too old"; then
      echo "docker-compose"
      return
    fi
  fi
  for path in /usr/local/Cellar/docker-compose/*/bin/docker-compose /opt/homebrew/Cellar/docker-compose/*/bin/docker-compose; do
    if [[ -x "$path" ]]; then
      local test_output
      test_output=$(cd "$project_root" && "$path" ps 2>&1) || true
      if ! echo "$test_output" | grep -q "client version 1.43 is too old"; then
        echo "$path"
        return
      fi
    fi
  done
  echo ""
}

DOCKER_COMPOSE=$(find_docker_compose "$PROJECT_ROOT")

echo "[backup] Starting PostgreSQL backup: $BACKUP_FILE"

# Source environment from .env if present
if [ -f "$PROJECT_ROOT/.env" ]; then
  # shellcheck source=/dev/null
  set -a && source "$PROJECT_ROOT/.env" && set +a
fi

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-carbonverify}"
DB_USER="${DB_USER:-postgres}"
DB_PASS="${DB_PASSWORD:-}"

if [ -n "$DB_PASS" ]; then
  export PGPASSWORD="$DB_PASS"
fi

# Run pg_dump (inside db container if docker-compose, else locally)
if [[ -n "$DOCKER_COMPOSE" ]] && $DOCKER_COMPOSE ps db &> /dev/null; then
  echo "[backup] Using docker-compose db container"
  $DOCKER_COMPOSE exec -T db pg_dump \
    --host=localhost \
    --username="$DB_USER" \
    --dbname="$DB_NAME" \
    --clean \
    --if-exists \
    --create | gzip > "$BACKUP_DIR/$BACKUP_FILE"
else
  echo "[backup] Using local pg_dump"
  pg_dump \
    --host="$DB_HOST" \
    --port="$DB_PORT" \
    --username="$DB_USER" \
    --dbname="$DB_NAME" \
    --clean \
    --if-exists \
    --create | gzip > "$BACKUP_DIR/$BACKUP_FILE"
fi

echo "[backup] Backup saved: $BACKUP_DIR/$BACKUP_FILE"
BACKUP_SIZE=$(du -h "$BACKUP_DIR/$BACKUP_FILE" | cut -f1)
echo "[backup] Size: $BACKUP_SIZE"

# Upload to S3 if bucket is configured
if [ -n "${S3_BUCKET:-}" ]; then
  S3_PREFIX="${S3_PREFIX:-postgres}"
  echo "[backup] Uploading to s3://$S3_BUCKET/$S3_PREFIX/$BACKUP_FILE"
  aws s3 cp "$BACKUP_DIR/$BACKUP_FILE" "s3://$S3_BUCKET/$S3_PREFIX/$BACKUP_FILE"
  echo "[backup] Upload complete"
fi

# Clean up old local backups
echo "[backup] Cleaning up backups older than $RETENTION_DAYS days"
find "$BACKUP_DIR" -name "carbonverify_*.sql.gz" -mtime +$RETENTION_DAYS -delete

# Clean up old S3 backups
if [ -n "${S3_BUCKET:-}" ]; then
  echo "[backup] Cleaning up S3 backups older than $RETENTION_DAYS days"
  CUTOFF=$(date -d "$RETENTION_DAYS days ago" +%Y-%m-%d 2>/dev/null || date -v-${RETENTION_DAYS}d +%Y-%m-%d)
  aws s3 ls "s3://$S3_BUCKET/$S3_PREFIX/" | \
    awk -v cutoff="$CUTOFF" '
    {
      file_date = $1
      file_name = $4
      if (file_date < cutoff) {
        print file_name
      }
    }' | \
    while read -r old_file; do
      if [ -n "$old_file" ]; then
        echo "[backup] Deleting old S3 backup: $old_file"
        aws s3 rm "s3://$S3_BUCKET/$S3_PREFIX/$old_file"
      fi
    done
fi

echo "[backup] Done"
