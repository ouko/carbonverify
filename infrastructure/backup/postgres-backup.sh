#!/bin/bash
set -euo pipefail

# PostgreSQL Backup Script for CarbonVerify
# Runs daily via cron or Kubernetes CronJob

ENVIRONMENT=${ENVIRONMENT:-production}
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_NAME=${DB_NAME:-carbonverify}
DB_USER=${DB_USER:-carbonverify}
DB_PASSWORD=${DB_PASSWORD:-}
S3_BUCKET=${S3_BUCKET:-carbonverify-backups-production}
RETENTION_DAYS=${RETENTION_DAYS:-30}

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="carbonverify_${ENVIRONMENT}_${TIMESTAMP}.sql.gz"
BACKUP_DIR="/tmp/carbonverify-backups"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting PostgreSQL backup for $DB_NAME..."

# Create backup
PGPASSWORD="$DB_PASSWORD" pg_dump \
  -h "$DB_HOST" \
  -p "$DB_PORT" \
  -U "$DB_USER" \
  -d "$DB_NAME" \
  --verbose \
  --no-owner \
  --no-privileges \
  | gzip > "$BACKUP_DIR/$BACKUP_FILE"

BACKUP_SIZE=$(du -h "$BACKUP_DIR/$BACKUP_FILE" | cut -f1)
echo "[$(date)] Backup completed: $BACKUP_FILE ($BACKUP_SIZE)"

# Upload to S3
aws s3 cp "$BACKUP_DIR/$BACKUP_FILE" "s3://$S3_BUCKET/postgres/daily/"
echo "[$(date)] Uploaded to s3://$S3_BUCKET/postgres/daily/$BACKUP_FILE"

# Also create a "latest" symlink
aws s3 cp "s3://$S3_BUCKET/postgres/daily/$BACKUP_FILE" "s3://$S3_BUCKET/postgres/latest.sql.gz"

# Cleanup old backups
echo "[$(date)] Cleaning up backups older than $RETENTION_DAYS days..."
aws s3 ls "s3://$S3_BUCKET/postgres/daily/" | \
  awk '{print $4}' | \
  while read -r file; do
    FILE_DATE=$(echo "$file" | grep -oP '\d{8}' || true)
    if [ -n "$FILE_DATE" ]; then
      FILE_EPOCH=$(date -d "$FILE_DATE" +%s 2>/dev/null || date -j -f "%Y%m%d" "$FILE_DATE" +%s)
      CUTOFF_EPOCH=$(date -d "$RETENTION_DAYS days ago" +%s 2>/dev/null || date -v-${RETENTION_DAYS}d +%s)
      if [ "$FILE_EPOCH" -lt "$CUTOFF_EPOCH" ]; then
        echo "Deleting old backup: $file"
        aws s3 rm "s3://$S3_BUCKET/postgres/daily/$file"
      fi
    fi
  done

# Cleanup local temp file
rm -f "$BACKUP_DIR/$BACKUP_FILE"

echo "[$(date)] Backup process completed successfully."
