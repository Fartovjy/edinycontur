#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# deploy.sh — обновление приложения на сервере
# Запускается автоматически через GitHub Actions или вручную:
#   ssh deploy@<IP> "bash /home/deploy/app/deploy/deploy.sh"
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

APP_DIR="/home/deploy/app"
COMPOSE="docker compose -f docker-compose.prod.yml --env-file .env.prod"

echo "▶ [$(date '+%Y-%m-%d %H:%M:%S')] Начало деплоя"

cd "$APP_DIR"

# 0. Бэкап базы данных
echo "▶ Создание бэкапа БД..."
BACKUP_DIR="/home/deploy/backups"
mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/$(date '+%Y%m%d_%H%M%S').sql.gz"
PG_USER=$(docker exec app-db-1 printenv POSTGRES_USER)
PG_DB=$(docker exec app-db-1 printenv POSTGRES_DB)
docker exec app-db-1 pg_dump -U "$PG_USER" "$PG_DB" | gzip > "$BACKUP_FILE"
echo "  Бэкап сохранён: $BACKUP_FILE"
# Удалить бэкапы старше 30 дней
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +30 -delete

# 1. Получить свежий код
echo "▶ Обновление кода из GitHub..."
git fetch origin main
git reset --hard origin/main

# 2. Пересобрать и перезапустить контейнеры
echo "▶ Пересборка контейнеров..."
$COMPOSE build --no-cache web

echo "▶ Перезапуск..."
$COMPOSE up -d --no-deps web
$COMPOSE up -d --no-deps nginx

# 3. Применить миграции и собрать статику (внутри нового контейнера)
echo "▶ Миграции..."
$COMPOSE exec -T web python manage.py migrate --noinput

echo "▶ Сбор статики..."
$COMPOSE exec -T web python manage.py collectstatic --noinput --clear

# 4. Убрать старые образы
docker image prune -f

echo "✅ [$(date '+%Y-%m-%d %H:%M:%S')] Деплой завершён успешно"
