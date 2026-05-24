#!/bin/bash
set -euo pipefail

# PostgreSQL Restore Script for CarbonVerify
# Usage: ./postgres-restore.sh [s3://bucket/path/to/backup.sql.gz]

ENVIRONMENT=${ENVIRONMENT:-production}
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_NAME=${DB_NAME:-carbonverify}
DB_USER=${DB_USER:-carbonverify}
DB_PASSWORD=${DB_PASSWORD:-}
S3_BUCKET=${S3_BUCKET:-carbonverify-backups-production}

RESTORE_FILE=${1:-"s3://$S3_BUCKET/postgres/latest.sql.gz"}
TEMP_DIR="/tmp/carbonverify-restore"

mkdir -p "$TEMP_DIR"

echo "[$(date)] Starting PostgreSQL restore from $RESTORE_FILE..."

# Download backup
LOCAL_FILE="$TEMP_DIR/restore.sql.gz"
aws s3 cp "$RESTORE_FILE" "$LOCAL_FILE"
echo "[$(date)] Backup downloaded."

# Drop and recreate database
echo "[$(date)] Recreating database..."
PGPASSWORD="$DB_PASSWORD" psql \
  -h "$DB_HOST" \
  -p "$DB_PORT" \
  -U "$DB_USER" \
  -d postgres \
  -c "DROP DATABASE IF EXISTS $DB_NAME;"

PGPASSWORD="$DB_PASSWORD" psql \
  -h "$DB_HOST" \
  -p "$DB_PORT" \
  -U "$DB_USER" \
  -d postgres \
  -c "CREATE DATABASE $DB_NAME;"

# Restore
echo "[$(date)] Restoring database..."
gunzip -c "$LOCAL_FILE" | PGPASSWORD="$DB_PASSWORD" psql \
  -h "$DB_HOST" \
  -p "$DB_PORT" \
  -U "$DB_USER" \
  -d "$DB_NAME"

# Cleanup
rm -rf "$TEMP_DIR"

echo "[$(date)] Restore completed successfully."
