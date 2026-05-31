#!/usr/bin/env bash
set -euo pipefail

DB_NAME="${POSTGRES_DB:-anchor}"
DB_USER="${POSTGRES_USER:-anchor}"
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"
S3_BUCKET="${BACKUP_BUCKET:-anchor-backups}"
S3_ENDPOINT="${S3_ENDPOINT:-http://localhost:9000}"

TMPDIR=$(mktemp -d)

echo "==> Finding latest backup..."
LATEST=$(aws s3 ls "s3://${S3_BUCKET}/" --endpoint-url "$S3_ENDPOINT" | sort | tail -1 | awk '{print $4}')

if [ -z "$LATEST" ]; then
    echo "ERROR: No backups found in s3://${S3_BUCKET}/"
    exit 1
fi

echo "==> Downloading ${LATEST}..."
aws s3 cp "s3://${S3_BUCKET}/${LATEST}" "${TMPDIR}/${LATEST}" --endpoint-url "$S3_ENDPOINT"

echo "==> Decompressing..."
gunzip "${TMPDIR}/${LATEST}"
SQL_FILE="${TMPDIR}/${LATEST%.gz}"

echo "==> Restoring to database ${DB_NAME}..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$SQL_FILE"

rm -rf "$TMPDIR"
echo "==> Restore complete from: ${LATEST}"
