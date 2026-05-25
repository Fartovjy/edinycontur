# План работ по проекту «Единый Контур»

Документ для Claude Code. Содержит контекст по текущему состоянию проекта, конкретные пункты с привязкой к файлам и подробное техническое задание на редизайн интерфейса. Любую задачу можно брать независимо, но рекомендуемый порядок выполнения — сверху вниз внутри каждого блока.

Если по ходу работы выяснится, что какой-то пункт уже частично реализован, нужно проверить это в коде и обновить статус, а не дублировать работу.

---

## 0. Контекст проекта

Стек: Django 5 + PostgreSQL 16 + Docker Compose + aiogram 3 (Telegram-бот). Внутренний MVP для логистики: заявки с жизненным циклом статусов, ручной блок «Честного Знака», вложения, проблемы, транспорт, дашборд руководителя, уведомления в Telegram.

Основные приложения:

- `apps/accounts/` — пользователи, роли, права (`User`, `UserProfile`, `Role`).
- `apps/logistics/` — заявки (`LogisticsRequest`), переходы статусов (`services.py`), клиенты, склады, архивирование (`archivist.py`).
- `apps/documents/` — вложения (`Attachment`).
- `apps/problems/` — проблемные заявки (`ProblemReport`).
- `apps/transport/` — машины и водители (`Vehicle`, `Driver`).
- `apps/notifications/` — модель `Notification`, сигналы → Telegram, команда `runbot`.
- `apps/dashboard/` — сводка для руководителя, брендинг.

Шаблоны в `apps/templates/logistics/`. Базовый шаблон `base.html`, оттуда расширяется всё остальное.

Конфиг: `ediny_kontur/settings.py`, `ediny_kontur/urls.py`, `ediny_kontur/middleware.py` (свой `LoginRequiredMiddleware`), `docker-compose.yml`, `Dockerfile`, `requirements.txt`, `.env.example`.

Главная проблема, известная заранее: проект не стартует на боевом сервере. Логи появятся позже, см. блок «Боевой деплой» — там есть чек-лист, который нужно прогнать сразу после получения логов.

---

## 1. Боевой деплой (БЛОКЕР, делать после получения логов)

### 1.1. Разделить dev и prod конфигурации Docker Compose

В текущем `docker-compose.yml` web-сервис запускает `python manage.py runserver 0.0.0.0:8000`. Это dev-сервер Django, для прода не подходит. Кроме того, на старте он автоматически прогоняет `seed_demo_data`, что в проде уничтожит данные и создаст пользователей `admin/admin`.

Нужно:

- Создать `docker-compose.yml` (dev) и `docker-compose.prod.yml` (prod). В dev оставить `runserver` и `seed_demo_data`, в prod использовать `gunicorn ediny_kontur.wsgi:application --bind 0.0.0.0:8000 --workers 3 --access-logfile -` (gunicorn уже в `requirements.txt`).
- В prod заменить команду на `sh -c "python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn ..."`. **Не вызывать** `seed_demo_data` в prod-варианте.
- Прокинуть в prod-compose nginx-сервис (или подразумевать внешний обратный прокси) для отдачи `/static/` и `/media/` и SSL-терминации. Если внешний — описать пример конфигурации nginx в `deploy/nginx.conf`.
- Том `media_data` в prod вынести в именованный volume или bind-mount, и обязательно настроить бэкап (создать `scripts/backup.sh`, который дампит postgres и архивирует `media`).

### 1.2. Привести `settings.py` к боевому виду

Файл: `ediny_kontur/settings.py`.

- Убрать дефолт `SECRET_KEY = "dev-secret-key-change-me"` — падать с ошибкой, если переменная не задана в окружении: `SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]`.
- Дефолт `DJANGO_DEBUG` оставить `False` (сейчас `True`). В dev-compose явно проставлять `DJANGO_DEBUG=1`.
- Убрать дефолт `ALLOWED_HOSTS = "*"` — пустой список по умолчанию.
- Добавить блок безопасности (активен при `DEBUG=False`):
  ```python
  if not DEBUG:
      SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
      SESSION_COOKIE_SECURE = True
      CSRF_COOKIE_SECURE = True
      SECURE_HSTS_SECONDS = 31536000
      SECURE_HSTS_INCLUDE_SUBDOMAINS = True
      SECURE_HSTS_PRELOAD = True
      SECURE_REFERRER_POLICY = "same-origin"
      SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
      X_FRAME_OPTIONS = "DENY"
  ```
- В `docker-compose.prod.yml` обязательно подкинуть `CSRF_TRUSTED_ORIGINS` (например, `https://ediny-kontur.example.com`).
- Жёстко зашитый IP `79.174.46.33` из `docker-compose.yml` и `.env.example` убрать. Указывать только через переменные окружения.

### 1.3. Безопасное логирование при падении

Сейчас при отказе бот молча проглатывает ошибки (`apps/notifications/signals.py`, `_send_message`). Аналогично в архивисте. Добавить:

- Настроить `LOGGING` в `settings.py`: stdout-handler с уровнем `INFO`, отдельный `WARNING`-handler для `apps.notifications`, формат с timestamp + path.
- В `_send_message` (`apps/notifications/signals.py`) логировать `requests.RequestException` через `logging.getLogger(__name__).warning(...)`.
- В `apps/logistics/archivist.py` обернуть запись архивов try/except и логировать.
- Включить `django.request` логгер уровня `WARNING`, чтобы 500-е не терялись.

### 1.4. Чек-лист по логам сервера (выполнить, когда логи появятся)

Когда пользователь приложит вывод `docker compose logs web`, проверить в указанном порядке:

1. Есть ли `django.db.utils.OperationalError: could not connect to server` — значит контейнер `web` стартует раньше готовности `db`. В compose уже есть healthcheck `pg_isready`, но если он не сработал, добавить в команду `web` ожидание: `sh -c "until pg_isready -h db -U $$POSTGRES_USER; do sleep 1; done && ..."`.
2. `ImproperlyConfigured: The SECRET_KEY setting must not be empty` — см. 1.2.
3. `DisallowedHost` — проверить `DJANGO_ALLOWED_HOSTS` и доменное имя/IP.
4. `psycopg.OperationalError: FATAL: password authentication failed` — `POSTGRES_PASSWORD` в окружении web и db не совпадает. Привести к единому значению.
5. `Permission denied: '/app/media/...'` — проверить владельца volume `media_data`. В `Dockerfile` создать пользователя без root и сделать `chown -R app:app /app/media`.
6. `static files not found` — в prod забыли `collectstatic`. Добавить в стартовую команду.
7. `Bot polling: TelegramAPIError` или `TimeoutError` в `runbot` — проверить `TELEGRAM_BOT_TOKEN` и доступ исходящих к `api.telegram.org`.
8. `RuntimeError: Apps aren't loaded yet` при импорте в `apps/notifications/signals.py` — значит сигнал импортируется раньше готовности приложений; перенести регистрацию сигналов в `ready()` метод `AppConfig`.
9. Если падает на `seed_demo_data` — в prod вообще не запускать (см. 1.1). В dev должна быть идемпотентность: команда должна корректно отрабатывать на «уже наполненной» БД (проверить, что используется `get_or_create`/`update_or_create`).

После того как стартовал — убедиться, что:

- `/` отдаёт страницу логина (`LoginRequiredMiddleware` редиректит).
- `/admin/` доступен.
- Создан суперпользователь (отдельной командой `python manage.py createsuperuser`, **не** `seed_demo_data`).
- Telegram-бот ожил (если токен задан): отправить `/start` тестовому водителю.

---

## 2. Безопасность (после деплоя или параллельно)

### 2.1. Демо-пользователи и подсказки в UI

- Шаблон `apps/templates/registration/login.html`: убрать строку `<div class="text-muted small mt-3">Демо: admin / admin</div>`. Если нужна для dev, обернуть в `{% if debug %}` (потребуется добавить context-processor `django.template.context_processors.debug`).
- Команда `apps/logistics/management/commands/seed_demo_data.py` — добавить флаг `--force` и без него отказываться выполнять, если в БД уже есть хотя бы один реальный пользователь (не из ожидаемого списка). Запретить её запуск в prod через проверку `if not settings.DEBUG and not options["force"]: ...`.

### 2.2. Загрузка файлов

Файл: `apps/documents/forms.py` и `apps/problems/forms.py`.

- Добавить проверку MIME-типа по содержимому через `python-magic` (добавить в requirements `python-magic-bin` для Windows или `python-magic` + `libmagic1` в Dockerfile). Разрешить только `application/pdf`, `image/jpeg`, `image/png`, `image/webp`.
- Для PDF дополнительно проверять, что начинается с `%PDF-` (читать первые 5 байт).
- Для изображений — `PIL.Image.open(file).verify()` (Pillow уже есть в requirements).
- Хранить вложения по UUID-имени, а не по оригинальному (защита от path-injection и от перезаписи). Сделать в `Attachment.file = models.FileField(upload_to=upload_attachment_path)`, где `upload_attachment_path(instance, filename)` возвращает `f"attachments/{instance.request_id}/{uuid4()}{ext}"`.

### 2.3. Защита скачивания вложений

Сейчас `/media/attachments/...` отдаётся напрямую (в DEBUG-режиме Django, в prod — внешним nginx без авторизации). Любой, кто угадает URL, скачает файл.

- Сделать отдельный view `attachment_download(request, pk)` в `apps/documents/views.py`: получить `Attachment`, проверить, что у `request.user` есть доступ к `attachment.request` (роль + assigned_driver), отдать `FileResponse` (для prod лучше через `X-Accel-Redirect` в nginx).
- URL: `documents/<int:pk>/download/`.
- В шаблонах (`request_detail.html`) заменить `{{ attachment.file.url }}` на `{% url 'attachment_download' attachment.pk %}`.
- В nginx-конфиге prod закрыть прямой доступ к `/media/attachments/` (отдавать только через `internal` location и `X-Accel-Redirect`).

### 2.4. Унификация роли пользователя

Сейчас в `apps/accounts/models.py` параллельно живут `User.role` (FK на `Role`) и `UserProfile.role` (CharField). Функция `get_user_role` смотрит на оба места — путаница.

- Принять решение: оставить `UserProfile.role` (текущий код опирается в основном на него).
- Удалить FK `User.role` миграцией: сначала data-migration, копирующая `user.role.code` в `user.profile.role`, если профиля нет — создающая. Затем `RemoveField`.
- Подчистить все места, где читается `getattr(user, "role", None)`: `apps/accounts/permissions.py`, `apps/notifications/services.py`, `apps/notifications/signals.py`.

### 2.5. Защита от brute-force на логине

- Добавить `django-axes` в requirements. Подключить middleware и backend по документации. Лимит — 5 попыток за 30 минут с одного IP.
- В шаблоне логина показывать generic-сообщение «Неверный логин или пароль» (сейчас уже так).

### 2.6. Race condition в `generate_request_number`

Файл: `apps/logistics/models.py`, метод `LogisticsRequest.generate_request_number`.

Сейчас читает «последний номер за день» без блокировки. При параллельном создании двух заявок одного дня — конфликт.

- Перенести генерацию внутрь `save()` под `with transaction.atomic():` + `select_for_update()` на queryset с фильтром по префиксу даты.
- Альтернатива: отдельная таблица-счётчик `DailyRequestCounter(date, last_number)` с `select_for_update` на строке. Менее красиво, но устойчиво.
- Добавить тест: `transaction.atomic` + два потока создают заявку одновременно — оба номера уникальны.

### 2.7. Прочее

- В `ediny_kontur/middleware.py` `LoginRequiredMiddleware._is_public_path` пускает всё, что начинается с `/admin/`. Это нормально (там своя авторизация), но добавить комментарий.
- Сделать `MIN_PASSWORD_LENGTH = 10` в `AUTH_PASSWORD_VALIDATORS` (сейчас дефолт 8).
- Удалить `db.sqlite3` из репозитория (он в `.gitignore`, но физически лежит в `C:\Users\Home\Documents\biovak/db.sqlite3`). Проверить, что в git-истории его нет, иначе `git filter-repo`.

---

## 3. Качество кода

### 3.1. Распилить «жирный» `request_detail`

Файл: `apps/logistics/views.py`, функция `request_detail` (~280 строк, 7 веток `action`).

- Вынести каждое действие в отдельную функцию-обработчик в новом модуле `apps/logistics/actions.py`:
  - `handle_driver_delivered(request, request_obj)`
  - `handle_assign_driver(...)`
  - `handle_supply_date(...)`
  - `handle_supply_cz(...)`
  - `handle_assign_transport(...)`
  - `handle_warehouse_status(...)`
  - `handle_attachment(...)`
  - `handle_problem(...)`
  - `handle_close_problem(...)`
- В `request_detail` оставить диспетчер по `request.POST["action"]`.
- Проверки прав вынести в `permissions.py` (`can_assign_driver(user)`, `can_update_supply(user)` и т.д.) и использовать их в обработчиках.
- Покрыть каждое действие отдельным тестом в `apps/logistics/tests.py`.

### 3.2. Распилить `runbot.py`

Файл: `apps/notifications/management/commands/runbot.py` (643 строки).

- Разнести по модулям:
  - `apps/notifications/bot/keyboards.py` — все `_request_keyboard`, `_driver_start_keyboard`, и т.д.
  - `apps/notifications/bot/texts.py` — все `_request_text`, `_transport_request_text`.
  - `apps/notifications/bot/handlers/driver.py` — хэндлеры роли driver.
  - `apps/notifications/bot/handlers/transport.py` — хэндлеры роли transport.
  - `apps/notifications/bot/repository.py` — все `@sync_to_async` функции работы с БД.
- В `runbot.py` оставить только `Command.handle` со сборкой `Dispatcher` и регистрацией роутеров.

### 3.3. Индексы БД

Файл: `apps/logistics/models.py`.

Добавить в `Meta.indexes`:

```python
class Meta:
    ordering = ["-created_at"]
    indexes = [
        models.Index(fields=["planned_delivery_date"]),
        models.Index(fields=["planned_ship_date"]),
        models.Index(fields=["assigned_driver", "status"]),
        models.Index(fields=["is_archived", "status"]),
        models.Index(fields=["client_name"]),
    ]
```

Сгенерировать миграцию `makemigrations logistics`.

### 3.4. Заменить «магические строки» ролей в шаблонах

Сейчас в `apps/templates/logistics/base.html`, `request_detail.html`, `request_list.html` и др. фигурируют конструкции `{% if user.profile.role == "admin" %}` и подобные.

- Создать `apps/accounts/context_processors.py` с функцией `user_role_flags(request)`, которая возвращает `{"is_admin": ..., "is_operator": ..., "is_driver": ..., "can_create_request": ...}`.
- Зарегистрировать в `TEMPLATES.OPTIONS.context_processors`.
- В шаблонах заменить все `user.profile.role == "..."` на флаги (`{% if is_admin %}`).
- Аналогично для прав: `can_create_request`, `can_edit_request`, `can_assign_transport` — рассчитывать в `apps/accounts/permissions.py` и пробрасывать в шаблон.

### 3.5. Побочные эффекты GET-запросов

Файл: `apps/logistics/views.py`, функции `_request_list_period_for_user`, `_calendar_status_filters_for_request`.

Сейчас на GET сохраняют в профиль (`profile.save(update_fields=...)`). Это нарушает HTTP-семантику.

- Перевести сохранение настроек на отдельный POST-эндпойнт (например, `/preferences/list_period/` с `csrf`-токеном).
- При GET — только читать.
- На фронте сделать так, чтобы при смене вкладки делался AJAX-POST + перезагрузка.

### 3.6. Линтеры и форматирование

- Добавить `ruff` и `black` в `requirements-dev.txt`. Создать `pyproject.toml` с конфигурацией:
  ```toml
  [tool.ruff]
  line-length = 120
  target-version = "py312"
  select = ["E", "F", "W", "I", "B", "DJ"]
  ```
- Запустить `ruff check --fix .` и `black .`, закоммитить.
- Добавить `pre-commit` конфиг (`.pre-commit-config.yaml`) с хуками ruff, black, end-of-file-fixer, trailing-whitespace.

### 3.7. CI

- Создать `.github/workflows/ci.yml` (или `.gitlab-ci.yml`) с шагами:
  1. Запуск Postgres-сервиса.
  2. `pip install -r requirements.txt -r requirements-dev.txt`.
  3. `ruff check .`
  4. `python manage.py makemigrations --check --dry-run` (защита от незакоммиченных миграций).
  5. `python manage.py test`.

### 3.8. Тесты

- Добавить тесты в `apps/accounts/tests.py`: проверка `get_user_role` для всех ролей, `can_edit_request` для драйвера и не-драйвера, корректное создание `UserProfile` сигналом.
- Добавить тесты в `apps/dashboard/tests.py`: проверка доступа `manager_dashboard` для разных ролей, корректность метрик.
- Тесты на `attachment_download` (см. 2.3).
- Тест на race condition в `generate_request_number` (см. 2.6).

### 3.9. Бэкап и архив

Файл: `apps/logistics/archivist.py`.

- Сделать management-команду `run_archivist` (уже есть в `apps/logistics/management/commands/run_archivist.py` — проверить, не сломалась ли). Добавить расписание через `cron` в prod-compose (или через `django-q`/`celery-beat`).
- Логирование операций архивирования.
- Тест на восстановление из zip (хотя бы прочитать содержимое).

---

## 4. Редизайн интерфейса

Хочу современный, чистый интерфейс. Белый фон, светло-серые плашки (карточки), яркие акцентные цвета на действиях и статусах. Минимум градиентов, минимум теней. Bootstrap 5 пока оставляем как сетку, но переопределяем переменные и стили.

### 4.1. Дизайн-токены

Создать файл `static/css/tokens.css` со всеми CSS-переменными. Подключить в `base.html` **до** Bootstrap. Назначения:

#### Цвета

```css
:root {
  /* Фоны */
  --color-bg-page: #FFFFFF;          /* основной фон страницы */
  --color-bg-surface: #F5F6F8;       /* плашки/карточки */
  --color-bg-surface-2: #EEF0F3;     /* вложенные/выделенные плашки */
  --color-bg-hover: #F0F1F4;         /* hover-фон строк таблицы */

  /* Границы */
  --color-border: #E4E7EC;
  --color-border-strong: #CDD2D9;
  --color-divider: #EDEFF2;

  /* Текст */
  --color-text-primary: #0F172A;     /* почти чёрный */
  --color-text-secondary: #475569;
  --color-text-muted: #94A3B8;
  --color-text-inverse: #FFFFFF;

  /* Акценты */
  --color-accent: #4F46E5;           /* индиго — основной */
  --color-accent-hover: #4338CA;
  --color-accent-soft: #EEF2FF;

  /* Семантика */
  --color-success: #10B981;
  --color-success-soft: #ECFDF5;
  --color-warning: #F59E0B;
  --color-warning-soft: #FFFBEB;
  --color-danger: #EF4444;
  --color-danger-soft: #FEF2F2;
  --color-info: #0EA5E9;
  --color-info-soft: #F0F9FF;

  /* Подсветка приоритетов */
  --color-priority-normal: #94A3B8;
  --color-priority-urgent: #F97316;
  --color-priority-vip: #8B5CF6;
  --color-priority-critical: #EF4444;
}
```

#### Типографика

- Подключить шрифт Inter с Google Fonts (или self-host в `static/fonts/`). Веса: 400, 500, 600, 700.
- В `body` `font-family: "Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;`
- Базовый размер 14px, line-height 1.55. Для форм — 15px на инпутах.
- Заголовки: h1 28/700, h2 22/600, h3 18/600, h4 16/600.

```css
:root {
  --font-sans: "Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --fs-xs: 12px;
  --fs-sm: 13px;
  --fs-base: 14px;
  --fs-md: 15px;
  --fs-lg: 18px;
  --fs-xl: 22px;
  --fs-2xl: 28px;
}
```

#### Радиусы, тени, отступы

```css
:root {
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;
  --radius-pill: 999px;

  --shadow-xs: 0 1px 2px rgba(15, 23, 42, 0.04);
  --shadow-sm: 0 2px 6px rgba(15, 23, 42, 0.05);
  --shadow-md: 0 6px 16px rgba(15, 23, 42, 0.08);

  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 24px;
  --space-6: 32px;
  --space-7: 48px;
}
```

### 4.2. Базовый шаблон

Файл: `apps/templates/logistics/base.html`. Полностью переработать.

Структура:

```
[ Sidebar 240px ] [ Контент max-width 1440px, padding 32px ]
```

- Слева — фиксированный sidebar 240px на белом фоне с тонкой правой границей (`var(--color-border)`).
- В sidebar: логотип компании сверху (как сейчас, но в новом блоке), список навигации с иконками (использовать [Lucide Icons](https://lucide.dev) через CDN), внизу — карточка с именем пользователя, ролью и кнопкой «Выйти».
- На мобильном (≤768px) sidebar превращается в выезжающее меню (off-canvas) с кнопкой-гамбургером в шапке.
- Контент: фон `var(--color-bg-page)`, плашки `var(--color-bg-surface)`, между ними `gap: 16px`.

Пример HTML-каркаса:

```html
<div class="layout">
  <aside class="sidebar">
    <div class="sidebar__brand"> ... логотип + название ... </div>
    <nav class="sidebar__nav">
      <a href="..." class="nav-item">
        <svg class="nav-item__icon">...</svg>
        <span>Заявки</span>
      </a>
      ...
    </nav>
    <div class="sidebar__user"> ... </div>
  </aside>
  <main class="main">
    <header class="topbar"> ... breadcrumbs + действия страницы ... </header>
    <section class="content">{% block content %}{% endblock %}</section>
  </main>
</div>
```

### 4.3. Компоненты

Создать `static/css/components.css` с классами:

#### Карточка

```css
.card-surface {
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  box-shadow: var(--shadow-xs);
}
.card-surface__title { font-size: var(--fs-lg); font-weight: 600; margin-bottom: var(--space-3); }
```

Заменить во всех шаблонах `card border-0 shadow-sm` Bootstrap-овский на `card-surface`. Bootstrap-классы постепенно убираем.

#### Кнопки

Три варианта: `btn-primary` (заливка `--color-accent`, текст белый), `btn-secondary` (фон `var(--color-bg-surface-2)`, текст `var(--color-text-primary)`, граница `var(--color-border)`), `btn-ghost` (без фона, только акцентный текст).

```css
.btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  height: 36px;
  padding: 0 14px;
  border-radius: var(--radius-md);
  font-size: var(--fs-sm);
  font-weight: 500;
  border: 1px solid transparent;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}
.btn--primary { background: var(--color-accent); color: #fff; }
.btn--primary:hover { background: var(--color-accent-hover); }
.btn--secondary { background: var(--color-bg-surface-2); color: var(--color-text-primary); border-color: var(--color-border); }
.btn--secondary:hover { background: var(--color-bg-hover); }
.btn--ghost { background: transparent; color: var(--color-accent); }
.btn--ghost:hover { background: var(--color-accent-soft); }
.btn--danger { background: var(--color-danger); color: #fff; }
.btn--icon { width: 36px; padding: 0; justify-content: center; }
.btn--sm { height: 30px; padding: 0 10px; font-size: var(--fs-xs); }
```

#### Бэйджи статусов

Сделать пилюли с пастельным фоном и насыщенным текстом — современный читабельный вариант:

```css
.badge-status { display: inline-flex; align-items: center; padding: 4px 10px; border-radius: var(--radius-pill); font-size: var(--fs-xs); font-weight: 600; letter-spacing: 0.01em; }
.badge-status--created     { background: #EEF2FF; color: #4338CA; }
.badge-status--waiting     { background: #FFFBEB; color: #B45309; }
.badge-status--warehouse   { background: #ECFEFF; color: #0E7490; }
.badge-status--cz          { background: #F5F3FF; color: #6D28D9; }
.badge-status--ready       { background: #ECFDF5; color: #047857; }
.badge-status--transport   { background: #F0F9FF; color: #0369A1; }
.badge-status--in_transit  { background: #FEF3C7; color: #92400E; }
.badge-status--delivered   { background: #DCFCE7; color: #166534; }
.badge-status--problem     { background: #FEE2E2; color: #B91C1C; }
.badge-status--closed      { background: #F1F5F9; color: #475569; }
.badge-status--cancelled   { background: #F1F5F9; color: #64748B; }
```

В шаблонах: создать template-tag `{% status_badge request_obj.status %}` в `apps/dashboard/templatetags/logistics_extras.py` (там уже есть файл), который рендерит правильный класс по статусу. Заменить во всех местах ручные `{% if status == 'delivered' %}success{% endif %}`.

#### Приоритеты

Маркер слева от номера заявки в виде вертикальной полосы 3px шириной с цветом из `--color-priority-*`. В таблице — первая колонка с этой полосой.

#### Таблицы

Тонкие линии, без полосатого фона, hover в `var(--color-bg-hover)`.

```css
.table-modern { width: 100%; border-collapse: collapse; background: var(--color-bg-surface); border-radius: var(--radius-lg); overflow: hidden; }
.table-modern thead th { background: transparent; color: var(--color-text-muted); font-weight: 500; text-transform: uppercase; font-size: var(--fs-xs); letter-spacing: 0.05em; padding: 12px 16px; border-bottom: 1px solid var(--color-border); text-align: left; }
.table-modern tbody td { padding: 14px 16px; border-bottom: 1px solid var(--color-divider); font-size: var(--fs-sm); }
.table-modern tbody tr:hover { background: var(--color-bg-hover); }
.table-modern tbody tr:last-child td { border-bottom: none; }
```

#### Формы

- Метки — `font-weight: 500`, размер `--fs-xs`, цвет `--color-text-secondary`, `text-transform: uppercase`, отступ снизу 6px.
- Поля — высота 40px, padding 0 12px, `border: 1px solid var(--color-border)`, `border-radius: var(--radius-md)`, фон `#FFFFFF`. На фокусе — `border-color: var(--color-accent)` + `box-shadow: 0 0 0 3px rgba(79,70,229,0.15)`.
- Textarea — те же стили, минимальная высота 88px.
- Чекбоксы — кастомные, 16×16, в активном состоянии `background: var(--color-accent)` + белая галка.
- Группы полей в форме — сетка CSS Grid 12 колонок, плашки шириной 6 колонок по умолчанию, поля «описание» / «комментарий» — full width.

### 4.4. Постраничные правки

#### 4.4.1. Логин

Файл: `apps/templates/registration/login.html`.

- Центрировать карточку-логин в высоту вьюпорта.
- Карточка 400px шириной, белый фон, тонкая граница, тень `--shadow-md`.
- Логотип компании сверху по центру (если есть в `SiteBranding`).
- Заголовок «Вход в систему», подзаголовок «Единый Контур».
- Поля логина/пароля по новой форме (см. 4.3).
- Кнопка primary, full-width.
- Убрать строчку «Демо: admin / admin» (или показывать только при `DEBUG=True`).

#### 4.4.2. Список заявок

Файл: `apps/templates/logistics/request_list.html`.

- Шапка: слева `h1` «Заявки» + подзаголовок (количество в текущем периоде), справа крупная кнопка primary «+ Новая заявка» (с иконкой Lucide `plus`).
- Под шапкой — панель «Период» в виде сегментного контрола (4 кнопки в одной плашке, активная подсвечена `--color-accent`).
- Дальше — панель «Быстрые фильтры» (вкладки `quick_tabs`): горизонтальный скроллируемый ряд пилюль с цветами по семантике (Сегодня — нейтральная, Просрочено — красная пилюля, Проблемные — оранжевая, Доставлены — зелёная).
- Поле поиска справа в этой же панели, с иконкой `search` слева.
- Таблица заявок — по новому стилю (см. 4.3). Колонки:
  - Маркер приоритета (3px полоса слева)
  - Номер (моноширинный шрифт, цвет primary)
  - Клиент (имя + регион мелким серым снизу)
  - Адрес/GPS (truncate с tooltip)
  - Статус (бэйдж)
  - Водитель (avatar-кружок с инициалами + имя)
  - Даты (две строки: «Отгрузка дд.мм» / «Доставка дд.мм»)
  - Меню действий справа (3 точки → dropdown: «Открыть», «Редактировать», «Архивировать»)
- Пустое состояние: иконка `inbox`, заголовок «Заявок пока нет», подсказка «Создайте первую заявку, чтобы начать работу».

#### 4.4.3. Карточка заявки

Файл: `apps/templates/logistics/request_detail.html` (548 строк, разнести по include-ам в `apps/templates/logistics/includes/`).

- Шапка: номер заявки крупно (h1), бэйдж статуса справа, кнопки «Назад», «Редактировать», «Архивировать».
- Полоса прогресса по этапам (Снабжение → Склад → Доставка) — переработать. Сейчас сделана через clip-path. Новый вариант: горизонтальный stepper, кружки с номерами, между ними линии. Активный кружок — `--color-accent`, выполненный — `--color-success`, будущий — `--color-border`. Под каждым кружком — название этапа и дата.
- Двухколоночная сетка ниже:
  - Слева (`flex: 2`): «Основная информация» (плашка), «Даты» (плашка), «Контакты» (плашка для водителя), «Вложения» (плашка с drag-n-drop зоной + список превью).
  - Справа (`flex: 1`): «История статусов» (timeline с цветными точками и относительным временем), «Проблемы» (если есть), «Действия по роли» (например, для склада — кнопка «Принять на склад», для транспорта — «Назначить машину»).
- Вложения: миниатюры 80×80 для изображений, иконка PDF для документов, по hover — кнопки «Скачать», «Удалить».
- Формы внутри карточки (загрузка файла, новая проблема) — скрыты по умолчанию, раскрываются по клику «+ Добавить» (детали — `<details>` или alpine.js, без тяжёлых зависимостей).

#### 4.4.4. Создание / редактирование заявки

Файл: `apps/templates/logistics/request_form.html`.

- Две колонки: основные поля слева (флекс 2), вторичные (даты, флаги) справа (флекс 1) — на мобильных схлопывается в одну.
- Группы полей разделены маленькими заголовками-сепараторами («Клиент», «Груз», «Даты», «Транспорт», «Честный Знак»).
- Чекбокс «Товар уже на складе и зарезервирован» — в виде крупного toggle-switch, не обычной галки. Под ним пояснение.
- Кнопки внизу: «Сохранить» (primary), «Отмена» (ghost). Справа — служебная кнопка «Сохранить и создать новую» для оператора.

#### 4.4.5. Календарь

Файл: `apps/templates/logistics/request_calendar.html`.

- Шапка: название месяца крупно, стрелки «◀ ▶» и кнопка «Сегодня».
- Над сеткой — панель фильтров по группам (чипы с цветными точками: зелёная для «доставлено», оранжевая для «проблема» и т.д.).
- Сетка месяца: 7 колонок. Ячейка дня — белая плашка с тонкой границей, в углу число (сегодняшний день — кружок `--color-accent` с белой цифрой), выходные/праздники — фон `var(--color-bg-surface)`.
- Заявки внутри дня — маленькие плашки с цветной левой полосой (по группе статуса), коротко «№123 · Клиент». Hover — небольшой tooltip с полной информацией.
- Если в дне больше 4 заявок — показывать «+N ещё» (раскрыть в модалке).
- Снизу — «Заявки без даты» в виде сетки карточек.

#### 4.4.6. Дашборд

Файл: `apps/templates/logistics/dashboard.html`.

- Сверху — крупные метрики (5 карточек): каждая — белая плашка с цветной иконкой слева, цифра 36px справа, под ней подпись.
  - «Активные» — синий
  - «Проблемные» — красный
  - «Доставлено сегодня» — зелёный
  - «Без водителя» — жёлтый
  - «Просрочено» — серо-красный
- Ниже — две колонки:
  - «Открытые проблемы» (таблица или список)
  - «Просрочены» (список)
- Ещё ниже — две колонки:
  - «Активные заявки» (последние 10)
  - «Без водителя» (последние 10)

#### 4.4.7. Клиенты

Файлы: `apps/templates/logistics/client_list.html`, `client_form.html`, `client_confirm_delete.html`.

- Список — сетка карточек 3 колонки (на мобильных 1). На карточке — название, регион, контактное лицо, телефон с иконкой `phone`, email с иконкой `mail`. Кнопка «Редактировать» в правом нижнем углу.
- Поиск сверху.
- Кнопка «+ Новый клиент» — primary, справа.
- Форма редактирования — карточка по центру, 540px шириной.

### 4.5. Иконки

- Использовать [Lucide Icons](https://unpkg.com/lucide@latest) через CDN.
- Подключить скрипт в `base.html` и инициализировать `lucide.createIcons()` в DOMContentLoaded.
- В HTML использовать `<i data-lucide="package"></i>`.
- Конкретные иконки:
  - Заявки — `clipboard-list`
  - Календарь — `calendar`
  - Клиенты — `users`
  - Дашборд — `layout-dashboard`
  - Уведомления — `bell`
  - Админка — `settings`
  - Выйти — `log-out`
  - Создать — `plus`
  - Редактировать — `pencil`
  - Удалить — `trash-2`
  - Скачать — `download`
  - Фильтр — `filter`
  - Поиск — `search`

### 4.6. Анимации и переходы

Минимально, без вычурности:

- На всех интерактивных элементах `transition: background-color 0.15s, border-color 0.15s, transform 0.15s`.
- На карточках при hover — лёгкий подъём: `transform: translateY(-1px); box-shadow: var(--shadow-sm);`.
- На модалках и off-canvas — `opacity` + `translateY(8px)` 0.2s.

### 4.7. Мобильная адаптация

- Все основные страницы протестировать на 360px, 768px, 1024px, 1440px.
- Sidebar → off-canvas меню ниже 1024px.
- Таблицы → в карточный режим (`display: block`) на 768px и ниже, с метками-«псевдо-th» через `data-attr`.
- Формы — поля в одну колонку на 768px и ниже.
- Touch targets — минимум 44×44px (кнопки `btn--icon` сделать 44×44 на мобильных через media-query).

### 4.8. Тёмная тема (опционально, бонус)

Если останется время — продублировать токены в `@media (prefers-color-scheme: dark)` или через `data-theme="dark"` на `<html>`. Не блокирующая задача.

### 4.9. Очистка от Bootstrap

После переноса всех страниц на новые компоненты:

- Из `base.html` убрать `<link>` на Bootstrap CSS (или оставить только grid через `bootstrap-grid.min.css`, если сетка нужна).
- Из `<head>` убрать Bootstrap JS, если нигде не остались `data-bs-toggle` (проверить grep).
- Заменить все Bootstrap-классы (`row`, `col-*`, `d-flex`, `gap-*`, `text-muted`, и т.д.) на собственные утилитарные классы или CSS Grid. Можно подключить минимальный набор утилит из Tailwind через CDN (twind.dev / cdn.tailwindcss.com — только для dev), но в проде — собственный `utilities.css`.

### 4.10. Доступность

- Контраст текста — минимум 4.5:1 (проверить через Chrome DevTools → Lighthouse).
- На всех иконках без текста — `aria-label`.
- В таблицах — `scope="col"` на `th`.
- В формах — корректные `<label for="...">`.
- Кнопки — настоящие `<button>`, не `<div onclick>`.
- В off-canvas меню — управление с клавиатуры (Esc для закрытия, фокус на первом элементе).
- Sidebar с `role="navigation"` и `aria-label="Основная навигация"`.

---

## 5. Документация и наводки

- Обновить `README.md`: добавить раздел про prod-деплой, отдельную секцию про дизайн-токены, как добавлять новую страницу с новыми стилями.
- В `CHECKLIST.md` — обновить smoke-тест под новый UI.
- В `apps/accounts/permissions.py` — docstrings на каждую `can_*` функцию.

---

## 6. Чек-лист завершённости

Перед сдачей убедиться:

- [ ] Проект стартует через `docker compose -f docker-compose.prod.yml up -d` без ошибок.
- [ ] `python manage.py test` зелёный, ≥70 тестов.
- [ ] `ruff check .` без замечаний.
- [ ] В Lighthouse Accessibility ≥90, Performance ≥85.
- [ ] Любой неавторизованный пользователь не может скачать вложение, даже зная URL.
- [ ] Все шаблоны переведены на новые токены, Bootstrap-классы (кроме сетки, если решено оставить) не встречаются.
- [ ] Демо-подсказка на странице логина не показывается в prod.
- [ ] `SECRET_KEY` берётся строго из окружения.
- [ ] Все статусы заявок имеют корректные бэйджи в новом стиле.
- [ ] Календарь, дашборд, карточка заявки выглядят целостно и не «протекают» бутстраповскими стилями.

---

**Примечание для Claude Code.** При работе с шаблонами начинай с базы (`base.html`) и токенов — это ускоряет визуальную сборку остальных страниц. После каждой большой правки делай скриншот через Playwright/Chrome и сверяй с описанием. Если в этом документе что-то противоречит реальному коду — сначала уточняй у пользователя, не предполагай.
