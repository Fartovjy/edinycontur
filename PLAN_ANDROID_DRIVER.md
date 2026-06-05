# План: Android-приложение «ЕК Водитель»

**Статус:** проектирование.
**Целевая роль:** только ROLE_DRIVER.
**Платформа:** только Android (нативно, Kotlin + Compose).

---

## Решения, зафиксированные с пользователем

| Развилка | Решение |
|----------|---------|
| Платформа | Android, отдельное приложение («ЕК Водитель») |
| Главный экран | Только сегодняшние рейсы (плановая отгрузка или доставка = сегодня) |
| Действия | Сменить статус, сфотографировать груз, сообщить о проблеме, ввести одометр |
| Фото груза | Прикрепляются к карточке заявки на сайте (видны всем ролям) |
| Навигация | Тап по адресу → открыть Яндекс.Карты / Google Maps с маршрутом |
| Офлайн | Да: данные кешируются в Room, действия выполняются при появлении сети |
| Поломка авто | Уведомление уходит Транспортному отделу; создаётся ProblemReport |
| Кол-во рейсов | Варьируется; список фильтруется по дате, можно переключить на другой день |

---

## Архитектура

### Монорепо (рядом с Наблюдателем)
```
biovak/
├── android/          ← уже есть (Наблюдатель)
├── android_driver/   ← НОВОЕ (Водитель)
│   ├── app/
│   └── ...
└── apps/api/         ← дополняем новыми endpoints
```

Два отдельных Android-проекта в одном git-репозитории.  
Package name: `com.edinykontur.driver`

---

## Часть 1. Бэкенд (дополнения к существующему `apps/api/`)

### 1.1. Новые endpoints

```
GET    /api/v1/driver/trips/              → сегодняшние рейсы водителя
       ?date=2026-06-05                   → рейсы на конкретный день
GET    /api/v1/driver/trips/<id>/         → детали заявки (= существующий /requests/<id>/ с доп. полями)

POST   /api/v1/driver/trips/<id>/status/  → сменить статус заявки
       {status, comment?}
POST   /api/v1/driver/trips/<id>/odometer/ → записать одометр
       {odometer_km}
POST   /api/v1/driver/trips/<id>/photos/  → загрузить фото груза (multipart)
       file, photo_type (loading|delivery|problem)
GET    /api/v1/driver/trips/<id>/photos/  → список фото заявки

POST   /api/v1/driver/breakdown/          → сообщить о поломке автомобиля
       {request_id?, description, vehicle_id?}
```

Все endpoints доступны только `IsMobileDriverAuthenticated` (аналог существующего, роль = ROLE_DRIVER).

### 1.2. Permission `IsMobileDriverAuthenticated`

```python
class IsMobileDriverAuthenticated(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated: return False
        if user.is_superuser: return True
        profile = getattr(user, "profile", None)
        if not profile: return False
        if not profile.mobile_access_enabled: return False
        return profile.role == ROLE_DRIVER
```

### 1.3. Новая модель `RequestPhoto`

```python
class RequestPhoto(models.Model):
    PHOTO_LOADING  = "loading"    # при погрузке
    PHOTO_DELIVERY = "delivery"   # при доставке
    PHOTO_PROBLEM  = "problem"    # при проблеме
    PHOTO_TYPE_CHOICES = [...]

    request      = ForeignKey(LogisticsRequest, related_name="driver_photos")
    uploaded_by  = ForeignKey(AUTH_USER_MODEL)
    photo        = ImageField(upload_to="driver_photos/%Y/%m/")
    photo_type   = CharField(choices=PHOTO_TYPE_CHOICES)
    created_at   = DateTimeField(auto_now_add=True)
```

Фото будут отображаться на странице заявки (вкладка / секция «Фото водителя»).

### 1.4. Логика смены статуса водителем

Водителю доступны только переходы своей «ветки»:
```
TRANSPORT_ASSIGNED → SHIPPED       (забрал груз со склада)
SHIPPED            → IN_TRANSIT    (выехал к клиенту)
IN_TRANSIT         → DELIVERED     (доставил)
```
Если водитель пытается поставить другой статус — 400.  
При смене статуса: вызывается существующий `change_request_status` → уведомления уходят автоматически.

### 1.5. Логика поломки автомобиля

`POST /api/v1/driver/breakdown/`:
1. Создать `ProblemReport` с `problem_type=TRANSPORT_DELAY`, описанием.
2. Вызвать `create_role_notification(ROLE_TRANSPORT, request_obj, message)`.
3. Опционально перевести заявку в статус `STATUS_PROBLEM`.

### 1.6. Сериализаторы

**TripListSerializer:**
```
id, request_number, client_name, client_address, client_phone,
planned_ship_date, planned_delivery_date, actual_ship_date,
status, status_display, priority,
vehicle_plate, warehouse_name,
has_open_problem, cargo_summary
```

**TripDetailSerializer:** всё из TripList +
```
cargo_description, cargo_items, cargo_weight_kg, cargo_volume_m3,
dimensions_text, region,
cz_required, cz_status,
odometer_km (последний),
driver_photos (список),
allowed_status_transitions (список допустимых переходов для UI)
```

**RequestPhotoSerializer, BreakdownSerializer**

---

## Часть 2. Android («ЕК Водитель»)

### 2.1. Стек

Идентичен Наблюдателю (Kotlin + Compose + Hilt + Retrofit + Room + FCM).  
Package: `com.edinykontur.driver`  
Минимальный SDK: API 26 (Android 8).

### 2.2. Экраны

```
Splash (3 сек)
    └── Login
            └── TripList (главный, сегодня)
                    ├── TripDetail
                    │       ├── фото-галерея заявки
                    │       ├── кнопки смены статуса
                    │       ├── поле одометра
                    │       └── репорт проблемы
                    └── BreakdownScreen (кнопка на тулбаре)
```

### 2.3. Главный экран — список рейсов

```
┌──────────────────────────────────────────┐
│  ЕК Водитель          Пт, 6 июня  🔧    │  ← toolbar, кнопка поломки
├──────────────────────────────────────────┤
│ ┌────────────────────────────────────┐   │
│ │ ООО «Маяк»                   ⚠    │   │
│ │ № 053/2026  ·  📦 14 мест         │   │
│ │ ул. Ленина, 5, Москва       [→]   │   │  ← тап → карты
│ │ ● Назначен транспорт              │   │
│ └────────────────────────────────────┘   │
│                                          │
│ ┌────────────────────────────────────┐   │
│ │ ИП Сидоров А.П.                   │   │
│ │ № 051/2026  ·  📦 3 места          │   │
│ │ пр. Мира, 12, Раменское     [→]   │   │
│ │ ✅ В пути                          │   │
│ └────────────────────────────────────┘   │
│                                          │
│    ◀ Вчера         Сегодня  Завтра ▶     │  ← переключатель дня
└──────────────────────────────────────────┘
```

### 2.4. Экран детали рейса

Прокручиваемый, секции:

1. **Клиент** — имя, адрес (тап → карты), телефон (тап → звонок)
2. **Груз** — описание, мест / вес / объём, список позиций
3. **Действия** — кнопки статуса + поле одометра:
   ```
   ┌───────────────────────────────────────┐
   │  Статус: Назначен транспорт           │
   │  [  ✅ Забрал груз (SHIPPED)  ]       │  ← следующий статус
   │                                       │
   │  Одометр: [______] км  [Сохранить]   │
   └───────────────────────────────────────┘
   ```
4. **Фото** — сетка превью + кнопка «Сделать фото»:
   - Тип: Погрузка / Доставка / Проблема
   - После съёмки — немедленная отправка на сервер (или в очередь офлайн)
5. **Проблемы** — открытые ProblemReport + кнопка «Сообщить о проблеме»

### 2.5. Экран «Поломка автомобиля»

Отдельный экран (кнопка 🔧 на тулбаре главного экрана):
```
┌───────────────────────────────────────┐
│  🔴 Сообщить о поломке               │
│                                       │
│  Заявка (опционально): [выбрать ▼]   │
│                                       │
│  Описание проблемы:                   │
│  [_________________________________]  │
│                                       │
│  [ Фото поломки (опционально)  📷 ]  │
│                                       │
│  [  🔴 Отправить диспетчеру  ]       │
└───────────────────────────────────────┘
```
После отправки: уведомление в транспортный отдел, диалог «Сообщение отправлено».

### 2.6. Офлайн-очередь действий

Пока нет сети, действия (смена статуса, одометр, фото) складываются в Room:

```kotlin
@Entity
data class PendingAction(
    @PrimaryKey(autoGenerate = true) val id: Int = 0,
    val type: String,         // "status" | "odometer" | "photo" | "breakdown"
    val requestId: Int,
    val payload: String,      // JSON
    val photoPath: String?,   // локальный путь к фото
    val createdAt: Long,
)
```

WorkManager (`OfflineSyncWorker`) при появлении сети:
1. Берёт все `PendingAction` по порядку
2. Отправляет на сервер
3. Удаляет из очереди
4. Показывает уведомление «Синхронизировано N действий»

### 2.7. Push-уведомления водителю

Водитель получает push когда:
- Ему назначена новая заявка (`TRANSPORT_ASSIGNED`)
- Оператор изменил дату доставки
- Заявка переведена в «Проблема»

Интеграция: водитель тоже вызывает `create_user_notification` → FCM.  
**НО**: для водителя нужен `recipient_user` (персональное уведомление, как у Наблюдателя).

---

## Часть 3. Изменения на сайте

### 3.1. Фото водителя в карточке заявки

На странице `request_detail.html` добавить секцию «Фото водителя»:
- Сетка превью (3 колонки)
- Клик → lightbox (увеличение)
- Подпись: тип фото, дата/время, имя водителя

### 3.2. Контекст водителя в `_request_detail_context`

Добавить `driver_photos = request_obj.driver_photos.order_by("created_at")`.

---

## Часть 4. Этапы реализации

### Этап 1: Бэкенд — новые endpoints водителя
- [ ] `IsMobileDriverAuthenticated` permission
- [ ] `RequestPhoto` модель + миграция
- [ ] `apps/api/views.py` — новые views для водителя (trips, status, odometer, photos, breakdown)
- [ ] `apps/api/urls.py` — маршруты `/api/v1/driver/...`
- [ ] Сериализаторы: TripList, TripDetail, RequestPhoto, Breakdown
- [ ] Логика допустимых переходов статуса для водителя
- [ ] Деплой + curl-тесты

### Этап 2: Фото на сайте
- [ ] Секция «Фото водителя» в `request_detail.html`
- [ ] Lightbox (Bootstrap modal или плагин)
- [ ] `apps/api/admin.py` → `RequestPhotoAdmin`

### Этап 3: Android — скелет + авторизация
- [ ] Проект `android_driver/` в монорепо
- [ ] Gradle (тот же стек что у Наблюдателя)
- [ ] Login экран, TokenStorage
- [ ] ApiService (driver endpoints)
- [ ] DTOs

### Этап 4: Android — главный экран (список рейсов)
- [ ] `TripListScreen` + ViewModel
- [ ] Переключатель дня (◀ Вчера / Сегодня / Завтра ▶)
- [ ] Карточка рейса с адресом, статусом, кнопкой «→ карты»
- [ ] Pull-to-refresh

### Этап 5: Android — деталь рейса + действия
- [ ] `TripDetailScreen`
- [ ] Кнопка смены статуса (только допустимые переходы)
- [ ] Поле одометра
- [ ] Съёмка фото через камеру + загрузка
- [ ] Форма сообщения о проблеме
- [ ] Экран «Поломка автомобиля»

### Этап 6: Android — офлайн-очередь
- [ ] `PendingAction` Room entity + DAO
- [ ] Перехват действий при отсутствии сети → в очередь
- [ ] `OfflineSyncWorker` (WorkManager)
- [ ] Индикатор «оффлайн» в тулбаре
- [ ] Уведомление после синхронизации

### Этап 7: FCM + Polish + APK
- [ ] Push-уведомления водителю (новая заявка, изменение даты)
- [ ] Иконка приложения (другой цвет/стиль — чтобы не путать с Наблюдателем)
- [ ] Подпись Release APK
- [ ] Раздача (прямая ссылка на сайте или Google Play)

---

## Открытые вопросы

1. **Подпись при доставке** — нужна ли электронная подпись клиента (рисунок пальцем)?
2. **Маршрут нескольких точек** — если в день 3+ доставки, строить общий маршрут?
3. **Ограничение на фото** — максимум N фото на заявку? Максимальный размер?
4. **История рейсов** — видит ли водитель свои прошлые доставки (за неделю, месяц)?
5. **Чек-лист водителя** — стоит ли добавить чек-лист для водителя (проверил машину, взял ТТН, и т.п.)?
6. **Тёмная тема** — нужна?
7. **Иконка приложения** — отдельный дизайн или вариация на тему логотипа?

---

## После запуска

1. Установить на один телефон тестового водителя.
2. Проверить полный flow: авторизация → список рейсов → смена статуса → фото → доставка.
3. Проверить офлайн: отключить сеть, выполнить действия, включить — убедиться что синхронизировалось.
4. Раздать водителям, собрать обратную связь.
