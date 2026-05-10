# Единый Контур

MVP внутренней системы управления логистикой на Django, PostgreSQL, Docker Compose и Telegram-боте через aiogram.

## Что внутри

- Пользователи и роли: `admin`, `operator`, `supply`, `transport`, `warehouse`, `driver`, `manager`.
- Заявки с жизненным циклом статусов и историей каждой смены.
- Ручной блок Честного Знака: требуется, проверен, статус, комментарий, проблема.
- Вложения к заявкам: PDF, JPG, PNG, WEBP.
- Блок проблемных заявок с ответственным и статусом решения.
- Основные экраны: список заявок, карточка, создание, редактирование, фильтры, dashboard.
- Telegram-бот: уведомления по статусам, кнопки водителя `Доставлено` и `Проблема`, ссылка на заявку.

## Требования

- Docker Desktop с включённым Linux engine.
- Docker Compose v2.
- Git.
- Для локального запуска без Docker: Python 3.12+ и PostgreSQL 16+.

## Установка

Скопируйте проект и создайте файл окружения:

```bash
cp .env.example .env
```

На Windows PowerShell можно просто создать `.env` вручную по примеру `.env.example`.

## Переменные окружения

| Переменная | Пример | Назначение |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | `change-me` | Секретный ключ Django |
| `DJANGO_DEBUG` | `1` | Режим отладки: `1` или `0` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,0.0.0.0` | Разрешённые хосты |
| `POSTGRES_DB` | `ediny_kontur` | Имя базы PostgreSQL |
| `POSTGRES_USER` | `ediny_kontur` | Пользователь PostgreSQL |
| `POSTGRES_PASSWORD` | `ediny_kontur` | Пароль PostgreSQL |
| `WEB_APP_BASE_URL` | `http://localhost:8000` | Базовый URL для ссылок в Telegram |
| `TELEGRAM_BOT_TOKEN` | `123456:token` | Токен Telegram-бота |
| `MAX_UPLOAD_SIZE_MB` | `10` | Максимальный размер загружаемого файла |

## Запуск через Docker Compose

Запустите проект:

```bash
docker compose up
```

При старте сервис `web` выполняет миграции, загружает расширенные демоданные командой `seed_demo_data` и запускает Django на порту `8000`.

Если образ нужно пересобрать после изменений зависимостей или Dockerfile:

```bash
docker compose up --build
```

Откройте:

[http://localhost:8000](http://localhost:8000)

Админка:

[http://localhost:8000/admin/](http://localhost:8000/admin/)

## Миграции

В Docker:

```bash
docker compose exec web python manage.py migrate
```

Локально без Docker:

```bash
python manage.py migrate
```

## Создание суперпользователя

В Docker:

```bash
docker compose exec web python manage.py createsuperuser
```

Локально без Docker:

```bash
python manage.py createsuperuser
```

## Загрузка демоданных

В Docker:

```bash
docker compose exec web python manage.py seed_demo_data
```

Локально без Docker:

```bash
python manage.py seed_demo_data
```

Команда создаёт пользователей всех ролей, 5 машин, 5 водителей, 20 заявок в разных статусах, проблемные заявки, заявки с ЧЗ и просроченные заявки для dashboard.

## Статусы и приоритеты

Статусы заявок:

`created`, `waiting_supply`, `waiting_arrival`, `in_warehouse`, `cz_check`, `ready_to_ship`, `transport_assigned`, `shipped`, `in_transit`, `delivered`, `problem`, `closed`, `cancelled`.

Приоритеты:

`normal`, `urgent`, `vip`, `critical`.

## Тестовые пользователи

| Роль | Login | Password |
| --- | --- | --- |
| admin | `admin` | `admin` |
| operator | `operator` | `password` |
| supply | `supply` | `password` |
| transport | `transport` | `password` |
| warehouse | `warehouse` | `password` |
| driver | `driver` | `password` |
| manager | `manager` | `password` |

Дополнительные водители: `driver2`, `driver3`, `driver4`, `driver5`, пароль `password`.

## Запуск Telegram-бота

1. Создайте бота через BotFather.
2. Укажите в `.env`:

```bash
TELEGRAM_BOT_TOKEN=123456:token
WEB_APP_BASE_URL=http://localhost:8000
```

3. Запустите бота.

В Docker Compose сервис `bot` уже добавлен и стартует вместе с `docker compose up`.

Отдельный запуск в Docker:

```bash
docker compose run --rm bot
```

Локально без Docker:

```bash
python manage.py runbot
```

Если `TELEGRAM_BOT_TOKEN` пустой, web-приложение работает, а bot-service остаётся в idle-режиме.

Для привязки Telegram заполните `telegram_id` в профиле пользователя или `telegram_chat_id` у водителя/пользователя в админке. После этого пользователь может отправить боту `/start`.

## Тесты

В Docker:

```bash
docker compose exec web python manage.py test
```

Локально без Docker:

```bash
python manage.py test
```

## Основные сценарии проверки

Подробный ручной smoke-check находится в [CHECKLIST.md](CHECKLIST.md). В нём есть проверки входа под ролями, создания заявки, смены статусов, загрузки файла, проблем, транспорта, доставки, dashboard и Telegram-бота.

## Не входит в первую версию

В первой версии MVP намеренно не реализованы:

- интеграция с 1С;
- автоматическая работа с Честным Знаком через API;
- OCR документов;
- сложная маршрутизация транспорта;
- расчёт загрузки машины;
- отдельное мобильное приложение;
- бухгалтерские сценарии;
- юридически значимый документооборот;
- ЭДО;
- электронная подпись;
- автоматическое распознавание PDF/фото;
- автоматический подбор машины.

## Структура

- `ediny_kontur/` - настройки Django.
- `apps/accounts/` - пользователи, роли, права.
- `apps/logistics/` - заявки, статусы, timeline.
- `apps/documents/` - вложения, фото, PDF.
- `apps/problems/` - проблемные заявки.
- `apps/transport/` - машины, водители.
- `apps/notifications/` - Telegram-уведомления.
- `apps/dashboard/` - панель руководителя.
