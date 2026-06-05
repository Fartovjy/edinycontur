# План: Android-приложение для роли «Наблюдатель»

**Статус:** Этапы 1-4 — РЕАЛИЗОВАНО (коммиты 5e96a8f → 87ba360).
**Целевая роль:** только ROLE_VIEWER (наблюдатель).
**Целевая платформа:** только Android (iOS — нет).

---

## Решения, зафиксированные с пользователем

| Развилка | Решение |
|----------|---------|
| Платформа | Только Android (нативно) |
| Push-уведомления | Да, обязательно. Через Firebase Cloud Messaging |
| Офлайн-режим | Да. Локальный кеш (Room) + sync при наличии сети |
| Действия пользователя | Только просмотр. Никаких чек-боксов, комментариев и т.п. |
| Авторизация | Те же логин/пароль что и на сайте + флаг в админке «разрешён мобильный доступ» |
| UI start flow | Splash (логотип, 3 сек) → Список заявок |
| Карточка списка | Крупно: клиент. Мелким: №, дата доставки, этапы. ⚠ при проблеме |
| Карточка деталь | Лаконично — вся информация заявки |
| Цвета | Такие же, как на сайте (CSS-переменные из base.html) |

---

## Архитектура: монорепо

```
biovak/
├── apps/                          # текущий Django
│   ├── api/                       # ← НОВОЕ: REST API для мобилки
│   ├── ...
├── ediny_kontur/
├── android/                       # ← НОВОЕ: Android Studio проект
│   ├── app/
│   ├── build.gradle.kts
│   └── ...
├── PLAN_CHECKLISTS.md
└── PLAN_ANDROID.md  ← этот файл
```

**Преимущества:** атомарные коммиты «API + клиент» в одном PR, одна точка истины.

---

## Часть 1. Бэкенд (Django)

### 1.1. Зависимости

В `requirements.txt`:
```
djangorestframework>=3.15
firebase-admin>=6.4   # для отправки push
```

### 1.2. Расширение UserProfile

Добавить поле `mobile_access_enabled = models.BooleanField("Доступ к Android-приложению", default=False)` в `apps/accounts/models.py::UserProfile`. Миграция + отображение в админке (`apps/accounts/admin.py`).

### 1.3. Новое приложение `apps/api`

```
apps/api/
├── __init__.py
├── apps.py
├── urls.py
├── serializers.py        # сериализаторы DRF
├── views.py              # ViewSet / APIView
├── permissions.py        # IsMobileViewerAuthenticated
├── authentication.py     # (используем стандартный TokenAuthentication)
├── models.py             # DeviceToken
└── migrations/
```

### 1.4. Permission `IsMobileViewerAuthenticated`

```python
class IsMobileViewerAuthenticated(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        if not u.is_authenticated: return False
        profile = getattr(u, "profile", None)
        if not profile: return False
        if not profile.mobile_access_enabled: return False
        return profile.role == ROLE_VIEWER
```

### 1.5. Endpoints (REST API)

```
POST   /api/v1/auth/login/                   {username, password} → {token, user}
POST   /api/v1/auth/logout/                  → 204
POST   /api/v1/devices/register/             {fcm_token} → {ok}
DELETE /api/v1/devices/<token>/              → 204

GET    /api/v1/me/                           → профиль пользователя
GET    /api/v1/requests/                     → список заявок viewer'а
       ?since=2026-05-30T12:00:00Z           → только обновлённые после даты (для sync)
GET    /api/v1/requests/<id>/                → детали заявки
GET    /api/v1/notifications/                → персональные уведомления
POST   /api/v1/notifications/<id>/read/      → пометить прочитанным
```

Все, кроме `auth/login`, требуют `Authorization: Token xxx` + permission `IsMobileViewerAuthenticated`.

В `/api/v1/requests/` фильтр: `viewer_users=request.user`.

### 1.6. Модель DeviceToken

```python
class DeviceToken(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="device_tokens")
    fcm_token = models.CharField(max_length=512, unique=True)
    platform = models.CharField(max_length=20, default="android")
    last_seen_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### 1.7. Сериализаторы

#### RequestListSerializer (для списка)
- `id, request_number, client_name, planned_delivery_date, status, status_display, priority, has_open_problem, updated_at`

#### RequestDetailSerializer (для детали)
- Всё из List +
- даты: `supply_eta_date, warehouse_arrival_date, planned_ship_date, actual_ship_date, actual_delivery_date, planned_delivery_date`
- груз: `cargo_description, cargo_places_count, cargo_weight_kg, cargo_volume_m3, dimensions_text`
- клиент: `client_address, client_contact, client_phone, region`
- `warehouse_name` (через source="warehouse.name")
- `vehicle_plate, driver_name`
- ЧЗ: `cz_required, cz_status, cz_comment`
- `status_history` — вложенный сериализатор (список)
- `open_problems` — вложенный сериализатор
- `cargo_items` — вложенный (название, кол-во, supply_date, needs_cz)

### 1.8. FCM-отправка пушей

Создать `apps/api/services.py::send_push_to_user(user, title, body, request_id=None)`:
1. Найти все `DeviceToken` пользователя
2. Через firebase-admin отправить multicast
3. Удалить токены с ошибкой `unregistered` (устройство удалило приложение)

**Интеграция в существующий код:**
В `apps/notifications/services.py::create_user_notification` (уже есть!) — после `objects.create` вызвать `send_push_to_user`. Так все персональные уведомления автоматически уходят пушами.

```python
def create_user_notification(user, request_obj, message):
    notif = Notification.objects.create(
        recipient_user=user, request=request_obj, message=message
    )
    from apps.api.services import send_push_to_user
    send_push_to_user(user, "Единый Контур", message, request_id=request_obj.id if request_obj else None)
    return notif
```

### 1.9. Конфигурация Firebase

1. В Firebase Console создать проект «Edinyy Kontur»
2. Добавить **Android-приложение**, package name `com.edinykontur.observer`
3. Скачать `google-services.json` → положить в `android/app/`
4. В **Project Settings → Service accounts** → Generate new private key → JSON
5. Файл положить в репозиторий (или secrets) — `firebase-service-account.json`
6. На прод: `.env.prod` → `FIREBASE_CREDENTIALS_PATH=/app/firebase-service-account.json`
7. Файл прокинуть в Docker-контейнер через volume

---

## Часть 2. Android (Kotlin + Compose)

### 2.1. Стек

| Слой | Технология |
|------|-----------|
| Язык | Kotlin |
| UI | Jetpack Compose + Material 3 |
| Архитектура | MVVM / Repository |
| HTTP | Retrofit2 + Moshi |
| Локальный кеш | Room + Coroutines Flow |
| DI | Hilt |
| Async | Coroutines + Flow |
| Background | WorkManager (периодический sync) |
| Push | Firebase Messaging SDK |
| Хранение токена | EncryptedSharedPreferences |
| Минимальный SDK | API 26 (Android 8) |
| Target SDK | API 34 (актуальный) |

### 2.2. Структура

```
android/app/src/main/kotlin/com/edinykontur/observer/
├── EdinyKonturApp.kt                # @HiltAndroidApp
├── MainActivity.kt                  # один Activity, NavHost
├── data/
│   ├── api/
│   │   ├── ApiService.kt            # Retrofit interface
│   │   ├── dto/                     # DTO под JSON ответы
│   │   └── AuthInterceptor.kt       # вставляет токен
│   ├── db/
│   │   ├── AppDatabase.kt
│   │   ├── entity/                  # RequestEntity, ProblemEntity, ...
│   │   └── dao/                     # RequestDao, ProblemDao, ...
│   ├── repository/
│   │   ├── RequestRepository.kt     # API → Room → Flow<List<Request>>
│   │   ├── NotificationRepository.kt
│   │   └── AuthRepository.kt
│   └── prefs/
│       └── TokenStorage.kt          # EncryptedSharedPreferences
├── domain/
│   └── model/                       # доменные модели для UI
├── ui/
│   ├── theme/
│   │   ├── Color.kt                 # цвета сайта
│   │   ├── Type.kt
│   │   └── Theme.kt
│   ├── splash/SplashScreen.kt
│   ├── login/LoginScreen.kt + LoginViewModel
│   ├── list/RequestListScreen.kt + ListViewModel
│   └── detail/RequestDetailScreen.kt + DetailViewModel
├── di/
│   ├── NetworkModule.kt
│   ├── DatabaseModule.kt
│   └── RepositoryModule.kt
├── fcm/
│   └── EdinyKonturMessagingService.kt
└── sync/
    └── SyncWorker.kt                # периодический WorkManager
```

### 2.3. Цвета (Color.kt)

Извлечь из `apps/templates/logistics/base.html` точные значения CSS-переменных (`--amber`, `--brown-darkest`, `--ek-bg`, `--ek-text`, `--ek-surface`, `--ek-border`, `--green`) и определить в Compose:

```kotlin
object EkColors {
    val Amber        = Color(0xFFD9A35E)   // ← уточнить по base.html
    val AmberDarker  = Color(0xFFC1893F)
    val BrownDarkest = Color(0xFF3D2818)
    val Bg           = Color(0xFFFBF5EA)
    val Surface      = Color(0xFFFFFFFF)
    val Text         = Color(0xFF2A1D10)
    val Border       = Color(0xFFE8D9B8)
    val Muted        = Color(0xFF7A5230)
    val Green        = Color(0xFF15803D)
    val Red          = Color(0xFFD83434)
}
```

### 2.4. Splash (3 сек)

`SplashScreen.kt`: фон `EkColors.Bg`, по центру логотип проекта (PNG в `res/drawable/`), снизу подпись «Единый Контур • Наблюдатель». Через 3 секунды — навигация:
- если токен в EncryptedSharedPreferences есть → `RequestListScreen`
- иначе → `LoginScreen`

### 2.5. Список заявок

`RequestListScreen.kt`:
- `LazyColumn` карточек
- `pullRefresh` (Material) запускает sync
- Карточка:
  ```
  ┌──────────────────────────────────────┐
  │ ПЕТРОВ И.И., ООО «Маяк»     ⚠       │  ← клиент (text-h6), знак если проблема
  │ № 533/2026  ·  дост. 30.05  ·  📦   │  ← мелким серым
  │ ●────●────●────○────○                │  ← этапы (прогресс)
  └──────────────────────────────────────┘
  ```
- Иконка ⚠ красная если `has_open_problem = true`
- Тап по карточке → `RequestDetailScreen(id)`

### 2.6. Деталь заявки

Прокручиваемая карта с секциями (раскрывающиеся `Card` с заголовками):

1. **Клиент** — имя, адрес, контакт, телефон (с возможностью позвонить через `tel:`)
2. **Груз** — описание, мест/вес/объём, размеры
3. **Даты** — Timeline-стиль:
   ```
   ┌●  03.05  Поставка заказана
   │
   ├●  10.05  На склад прибыло
   │
   ├○  15.05  План отгрузки
   │
   └○  20.05  План доставки
   ```
4. **Транспорт** — машина, водитель
5. **ЧЗ** — статус и комментарий, если включено
6. **История статусов** — список с датами
7. **Открытые проблемы** — карточки красным цветом

### 2.7. Sync-стратегия (Room + Repository)

```kotlin
class RequestRepository {
    fun observeRequests(): Flow<List<Request>> = dao.observeAll()  // реактивно из БД

    suspend fun syncFromServer(forced: Boolean = false) {
        val lastSync = prefs.lastSyncAt()
        val response = api.getRequests(since = lastSync)
        db.transaction {
            response.requests.forEach { dao.upsert(it.toEntity()) }
            prefs.setLastSyncAt(response.serverTime)
        }
    }
}
```

**SyncWorker** (WorkManager):
- Запуск каждые 15 минут (только при сети)
- Дёргает `syncFromServer()`
- Backoff exponential на ошибках

**UI:** всегда читает из БД через Flow. Если сеть упала — кэш на месте, ничего не теряется.

### 2.8. FCM (push)

#### Регистрация токена
В `Application.onCreate` или после логина:
```kotlin
FirebaseMessaging.getInstance().token.addOnSuccessListener { fcmToken ->
    api.registerDevice(DeviceTokenRequest(fcm_token = fcmToken))
}
```

#### EdinyKonturMessagingService
```kotlin
class EdinyKonturMessagingService : FirebaseMessagingService() {
    override fun onNewToken(token: String) {
        // отправить на сервер
    }
    override fun onMessageReceived(msg: RemoteMessage) {
        val title = msg.data["title"] ?: "Единый Контур"
        val body  = msg.data["body"]  ?: ""
        val requestId = msg.data["request_id"]?.toLongOrNull()
        showNotification(title, body, requestId)
        // также — инициировать sync чтобы обновить кеш
        WorkManager.getInstance(this).enqueue(...)
    }
}
```

Тап по уведомлению → открыть `RequestDetailScreen(requestId)`.

---

## Часть 3. План реализации (этапы)

### Этап 1: Бэкенд API — авторизация и базовые endpoints ✅ DONE
- [x] `pip install djangorestframework firebase-admin` → обновить requirements.txt
- [x] Добавить `rest_framework`, `rest_framework.authtoken`, `apps.api` в INSTALLED_APPS
- [x] Миграция authtoken
- [x] Поле `mobile_access_enabled` в UserProfile + миграция + отображение в админке
- [x] Модель `DeviceToken` + миграция
- [x] `IsMobileViewerAuthenticated` permission
- [x] Endpoint `POST /api/v1/auth/login/`
- [x] Endpoint `GET /api/v1/me/`
- [x] Деплой, тесты через curl — всё работает
- [x] fix: `/api/` добавлен в публичные пути LoginRequiredMiddleware

**Делегировать:** OpenRouter (deepseek-coder) — стандартный DRF-код, шаблонный

### Этап 2: Endpoints заявок ✅ DONE (реализовано вместе с Этапом 1)
- [x] Сериализаторы `RequestListSerializer`, `RequestDetailSerializer`, `StatusHistorySerializer`, `ProblemSerializer`, `CargoItemSerializer`
- [x] ViewSet или APIView для `/requests/` и `/requests/<id>/`
- [x] Фильтр по viewer_users
- [x] Endpoint `/notifications/` + `/notifications/<id>/read/`
- [x] Поддержка `?since=<datetime>` для sync

**Делегировать:** частично Ollama (сериализаторы), интеграцию — сам

### Этап 3: Android — скелет проекта ✅ DONE
- [x] Android Studio проект в `biovak/android/`
- [x] Gradle: AGP 8.5, Kotlin 2.0, Compose BOM, Hilt, Retrofit/Moshi, Room, EncryptedSharedPreferences, FCM
- [x] Структура папок (data/api/dto, prefs, repository, ui, di, fcm, sync, navigation)
- [x] `ApiService` интерфейс (все endpoints)
- [x] `AuthInterceptor` для токена
- [x] Login экран + LoginViewModel
- [x] TokenStorage (EncryptedSharedPreferences)

### Этап 4: Android — список и деталь (онлайн) ✅ DONE
- [x] `RequestListScreen` + ListViewModel + Retrofit
- [x] `RequestDetailScreen` + DetailViewModel + Retrofit
- [x] Навигация: NavGraph (Login → List → Detail)
- [x] Тема: EdinyKonturTheme — точные цвета сайта
- [x] Карточки списка с ⚠ (проблема), статусным бэйджем
- [x] Pull-to-refresh (PullToRefreshBox)
- [x] FCM: EdinyKonturMessagingService (push → деталь заявки)
- [x] SyncWorker (WorkManager, 15 мин)

### Этап 5: Room + офлайн
- [ ] `AppDatabase` + Entity + DAO
- [ ] `RequestRepository` с sync
- [ ] UI читает из БД через Flow
- [ ] WorkManager periodic sync (15 мин)
- [ ] Индикатор «оффлайн» в AppBar

### Этап 6: Firebase Cloud Messaging
- [ ] Создать Firebase проект
- [ ] Скачать `google-services.json`, положить в `android/app/`
- [ ] Service account JSON, положить на сервер
- [ ] Добавить FCM зависимость в Gradle
- [ ] `EdinyKonturMessagingService`
- [ ] `POST /api/v1/devices/register/` — регистрация токена
- [ ] `apps/api/services.py::send_push_to_user` — отправка через firebase-admin
- [ ] Интеграция в `notifications.services.create_user_notification`
- [ ] Тап по пушу → открыть деталь заявки
- [ ] Удаление невалидных токенов

### Этап 7: Polish + раздача
- [ ] Иконка приложения (мипмап)
- [ ] Логотип splash
- [ ] Подпись Release APK
- [ ] Раздача: Google Play (~$25, нужен аккаунт), или прямая ссылка через сайт (`/static/edinykontur.apk`)
- [ ] Документация для наблюдателей: как установить

---

## Что подготовить ДО Этапа 1

1. **Точные цвета сайта** — извлечь из `apps/templates/logistics/base.html` все CSS-переменные (`--amber`, `--brown-darkest`, `--ek-bg`, и т.д.) и положить в начало `PLAN_ANDROID.md` как справочник.
2. **Иконка/логотип приложения** — нужен PNG 1024×1024 (адаптивная иконка) и логотип для splash. Если нет — на время Этапа 1-5 можно использовать заглушку.
3. **Firebase аккаунт** — если у пользователя нет Google-аккаунта для Firebase Console, нужен.

---

## Открытые вопросы (на потом)

1. Локализация: только русский, или сразу зашить i18n?
2. Тёмная тема — нужна?
3. Биометрия (отпечаток для разблокировки приложения)?
4. История уведомлений в приложении (отдельный экран) или только OS-уведомления?
5. Что показывать в карточке списка для завершённых заявок (Доставлено) — оставлять, скрывать, отдельная вкладка?
6. Шифрование локального кеша Room (через SQLCipher)?
7. Тесты: писать ли с самого начала или после Этапа 5?

---

## После запуска

1. На проде создать тестового наблюдателя.
2. Установить APK на один телефон, проверить весь flow.
3. Раздать 1-2 реальным наблюдателям, собрать обратную связь.
4. Если всё ок — публикация в Google Play.
