#!/usr/bin/env sh
set -eu

BACKUP_DIR="${BACKUP_DIR:-./backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > "$BACKUP_DIR/postgres-$STAMP.sql"

docker compose -f docker-compose.prod.yml run --rm \
  -v "$(pwd)/$BACKUP_DIR:/backup" \
  web sh -c "cd /app/media && tar -czf /backup/media-$STAMP.tar.gz ."

echo "Backup saved to $BACKUP_DIR"
