#!/usr/bin/env bash
set -euo pipefail

DB_NAME="${POSTGRES_DB:-anchor}"
DB_USER="${POSTGRES_USER:-anchor}"
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"
S3_BUCKET="${BACKUP_BUCKET:-anchor-backups}"
S3_ENDPOINT="${S3_ENDPOINT:-http://localhost:9000}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="anchor_backup_${TIMESTAMP}.sql.gz"
TMPDIR=$(mktemp -d)

echo "==> Dumping database ${DB_NAME}..."
pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" | gzip > "${TMPDIR}/${FILENAME}"

echo "==> Uploading to s3://${S3_BUCKET}/${FILENAME}..."
aws s3 cp "${TMPDIR}/${FILENAME}" "s3://${S3_BUCKET}/${FILENAME}" --endpoint-url "$S3_ENDPOINT"

echo "==> Cleaning up backups older than ${RETENTION_DAYS} days..."
CUTOFF=$(date -d "-${RETENTION_DAYS} days" +%Y%m%d 2>/dev/null || date -v-${RETENTION_DAYS}d +%Y%m%d)
aws s3 ls "s3://${S3_BUCKET}/" --endpoint-url "$S3_ENDPOINT" | while read -r line; do
    file=$(echo "$line" | awk '{print $4}')
    file_date=$(echo "$file" | grep -oP '\d{8}' | head -1 || true)
    if [ -n "$file_date" ] && [ "$file_date" -lt "$CUTOFF" ]; then
        echo "  Removing old backup: $file"
        aws s3 rm "s3://${S3_BUCKET}/${file}" --endpoint-url "$S3_ENDPOINT"
    fi
done

rm -rf "$TMPDIR"
echo "==> Backup complete: ${FILENAME}"
