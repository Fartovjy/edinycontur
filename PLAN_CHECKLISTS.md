# План: Чек-листы по ролям + страница «Текущие дела»

**Статус:** план утверждён, к реализации не приступали.
**Контекст:** Оператор и Снабжение завалены задачами; нужны структурированные чек-листы по каждой заявке, шаблоны которых редактируются из админки.

---

## Решения, зафиксированные с пользователем

| Развилка | Решение |
|----------|---------|
| Структура чек-листа | Плоский список с нумерацией 1, 2, 3 … (без подпунктов) |
| Кто чекает | Только та роль, для которой чек-лист (admin/superuser — всегда) |
| Изменение шаблона | **Snapshot** — старые заявки сохраняют исторический чек-лист, новые получают актуальный |
| «Текущие дела» | Список заявок с **раскрывающимися** чек-листами |
| Редактирование шаблона | Через Django admin |
| Какие роли получают чек-лист | На старте: **Оператор** и **Снабжение**. Архитектура — любая роль (одна запись `ChecklistTemplate` на роль). |

---

## Архитектура

### Новое приложение `apps/checklists`

Отдельное приложение — изолированная логика, не плодим хаос в `logistics`.

### Модели

```python
# apps/checklists/models.py

class ChecklistTemplate(models.Model):
    """Шаблон чек-листа для одной роли. Одна запись на роль."""
    role = models.CharField("Роль", max_length=32, choices=ROLE_CHOICES, unique=True)
    name = models.CharField("Название", max_length=120, blank=True,
                            help_text="Для удобства в админке, например «Чек-лист оператора».")
    is_active = models.BooleanField("Активен", default=True)
    updated_at = models.DateTimeField(auto_now=True)

class ChecklistTemplateItem(models.Model):
    """Пункт шаблона."""
    template = models.ForeignKey(ChecklistTemplate, on_delete=models.CASCADE,
                                  related_name="items", verbose_name="Шаблон")
    text = models.CharField("Текст пункта", max_length=255)
    order = models.PositiveIntegerField("Порядок", default=0)
    is_active = models.BooleanField("Активен", default=True,
                                     help_text="Снимите, чтобы исключить из новых чек-листов без удаления.")
    class Meta:
        ordering = ["order", "id"]

class RequestChecklistItem(models.Model):
    """Snapshot пункта для конкретной заявки."""
    request = models.ForeignKey("logistics.LogisticsRequest",
                                 on_delete=models.CASCADE,
                                 related_name="checklist_items",
                                 verbose_name="Заявка")
    role = models.CharField("Роль", max_length=32, choices=ROLE_CHOICES)
    text = models.CharField("Текст пункта (snapshot)", max_length=255)
    order = models.PositiveIntegerField(default=0)
    template_item = models.ForeignKey(ChecklistTemplateItem,
                                       on_delete=models.SET_NULL,
                                       null=True, blank=True,
                                       help_text="Исходный пункт шаблона; null если шаблон удалён.")
    is_done = models.BooleanField("Выполнено", default=False)
    checked_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    on_delete=models.SET_NULL,
                                    null=True, blank=True,
                                    related_name="checked_checklist_items")
    checked_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ["role", "order", "id"]
        indexes = [models.Index(fields=["request", "role"])]
```

### Создание snapshot'а

**Helper:**
```python
# apps/checklists/services.py
def create_checklist_for_request(request_obj):
    """Создаёт RequestChecklistItem'ы из активных шаблонов."""
    items = []
    for tpl in ChecklistTemplate.objects.filter(is_active=True).prefetch_related("items"):
        for it in tpl.items.filter(is_active=True):
            items.append(RequestChecklistItem(
                request=request_obj,
                role=tpl.role,
                text=it.text,
                order=it.order,
                template_item=it,
            ))
    RequestChecklistItem.objects.bulk_create(items)
```

**Где вызывать:**
- `request_create` (views.py, после `request_obj.save()` — там где номер заявки уже сформирован)
- `request_create_from_pdf` (если есть отдельный путь сохранения; проверить, не использует ли он `request_create` под капотом)

### Toggle endpoint

```python
# apps/checklists/views.py
@login_required
def checklist_item_toggle(request, item_pk):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    item = get_object_or_404(RequestChecklistItem, pk=item_pk)

    # Проверка доступа к заявке (берём из существующей логики logistics)
    if not can_view_request(request.user, item.request):
        raise PermissionDenied

    # Проверка роли: только своя или admin/superuser
    user_role = get_user_role(request.user)
    if not (request.user.is_superuser or user_role == ROLE_ADMIN or user_role == item.role):
        raise PermissionDenied

    item.is_done = not item.is_done
    if item.is_done:
        item.checked_by = request.user
        item.checked_at = timezone.now()
    else:
        item.checked_by = None
        item.checked_at = None
    item.save(update_fields=["is_done", "checked_by", "checked_at"])
    return JsonResponse({
        "is_done": item.is_done,
        "checked_by": item.checked_by.get_full_name() if item.checked_by else None,
        "checked_at": item.checked_at.isoformat() if item.checked_at else None,
    })
```

### Admin

```python
class ChecklistTemplateItemInline(admin.TabularInline):
    model = ChecklistTemplateItem
    extra = 1
    fields = ("order", "text", "is_active")
    ordering = ("order",)

@admin.register(ChecklistTemplate)
class ChecklistTemplateAdmin(admin.ModelAdmin):
    list_display = ("role", "name", "is_active", "updated_at")
    list_filter = ("is_active",)
    inlines = [ChecklistTemplateItemInline]

@admin.register(RequestChecklistItem)
class RequestChecklistItemAdmin(admin.ModelAdmin):
    list_display = ("request", "role", "text", "is_done", "checked_by", "checked_at")
    list_filter = ("role", "is_done")
    search_fields = ("request__request_number", "text")
    readonly_fields = ("checked_at", "checked_by")
```

### UI на странице заявки (`request_detail.html`)

Новый блок после «Основная информация»:

```
┌─────────────────────────────────────────┐
│ Чек-лист оператора            [2 / 5]   │  ← прогресс-бэйдж
├─────────────────────────────────────────┤
│ ☑ 1. Счёт выслан?                       │
│ ☑ 2. Дата отгрузки согласована?         │
│ ☐ 3. Спецификация есть?                 │
│ ☐ 4. Цены верны?                        │
│ ☐ 5. ТТН готов?                         │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ Чек-лист снабжения            [1 / 3]   │
├─────────────────────────────────────────┤
│ ☑ 1. Поставщик найден?                  │
│ ☐ 2. Цена согласована?                  │
│ ☐ 3. ТТН готов?                         │
└─────────────────────────────────────────┘
```

- Свой чек-лист: чекбоксы кликабельные, AJAX toggle.
- Чужой чек-лист: чекбоксы видны, но `disabled`.
- Заголовок блока — кликабельный, сворачивает чек-лист (`collapse` Bootstrap).
- Цвет прогресс-бэйджа: зелёный 100%, жёлтый 50-99%, серый <50%.
- Под чекнутым пунктом мелким курсивом: «Иванов И.И., 23.05.2026 14:32».

### Страница «Текущие дела»

**URL:** `/my-tasks/` (имя `current_tasks`)
**Меню:** добавить пункт «Дела» рядом с «Уведомления». Показывать всем ролям, у которых есть шаблон чек-листа.

**View:**
```python
@login_required
def current_tasks(request):
    role = get_user_role(request.user)
    # Только активные заявки (не Доставлено/Закрыто/Отменено)
    incomplete_qs = (
        RequestChecklistItem.objects
        .filter(role=role, is_done=False)
        .exclude(request__status__in=COMPLETED_STATUSES)
        .filter(request_filter_for_user(request.user))  # учёт viewer_users и пр.
        .values_list("request_id", flat=True)
        .distinct()
    )
    requests = (
        LogisticsRequest.objects
        .filter(pk__in=incomplete_qs)
        .prefetch_related("checklist_items")
        .order_by("-priority", "planned_delivery_date")
    )
    return render(request, "checklists/current_tasks.html", {"requests": requests, "role": role})
```

**UI:**
- Каждая заявка — карточка-аккордеон (Bootstrap `collapse`).
- Свёрнутая: номер заявки + клиент + статус + прогресс [N / M невыполненных].
- Развёрнутая: тот же чек-лист, что на странице заявки (общий include-шаблон).
- Кнопка «Открыть заявку» — переход на полную страницу заявки.
- Заявки сортируются по priority↓, дате доставки↑.

---

## Этапы реализации

### Этап 1: Скелет приложения + модели + миграция + admin
- [ ] `python manage.py startapp checklists` → `apps/checklists/`
- [ ] Добавить в `INSTALLED_APPS`
- [ ] 3 модели (см. выше)
- [ ] Миграция `0001_initial.py`
- [ ] `apps/checklists/admin.py` с inline
- [ ] **Data migration `0002_seed_default_templates.py`** — создаёт пустые шаблоны для ROLE_OPERATOR и ROLE_SUPPLY (без пунктов; пользователь заполнит через админку)
- [ ] **Делегировать Ollama**: модели + миграции + admin — шаблонный код

**Готовность:** в админке появляются ChecklistTemplate / Items, пользователь может создавать шаблоны.

### Этап 2: Snapshot при создании заявки
- [ ] `apps/checklists/services.py` → `create_checklist_for_request()`
- [ ] Вызов в `request_create` (apps/logistics/views.py)
- [ ] Проверить путь `request_create_from_pdf` — он использует `request_create` через redirect или это отдельный путь?
- [ ] Тест: создать заявку → проверить, что у неё появились RequestChecklistItem'ы

### Этап 3: Toggle endpoint + права доступа
- [ ] `apps/checklists/views.py` → `checklist_item_toggle()`
- [ ] `apps/checklists/urls.py` → подключить в корневой `ediny_kontur/urls.py`
- [ ] Проверки: доступ к заявке + соответствие роли
- [ ] **Делегировать OpenRouter Agent**: разобрать существующий `cargo_item_toggle_cz` в `logistics/views.py` как образец и написать аналогичный

### Этап 4: Блок чек-листов на странице заявки
- [ ] Include-шаблон `apps/templates/checklists/_checklist_block.html`
  - Принимает `request_obj`, `role`, `editable` (bool)
  - Рендерит один блок (заголовок + пункты + JS-хендлер)
- [ ] В `request_detail.html` подключить include для каждого активного шаблона
  - Свой блок: `editable=True`
  - Чужие: `editable=False`
- [ ] CSS: прогресс-бэйдж (зелёный/жёлтый/серый)
- [ ] JS: AJAX toggle (по аналогии с CZ-чекбоксами в `request_detail.html`)
- [ ] **Делегировать**: я (Claude) — нужна логика интеграции и понимание существующей вёрстки

### Этап 5: Страница «Текущие дела»
- [ ] `apps/checklists/views.py` → `current_tasks()`
- [ ] URL `/my-tasks/` имя `current_tasks`
- [ ] Шаблон `apps/templates/checklists/current_tasks.html` — аккордеон, переиспользует include-блок
- [ ] Пункт меню в `base.html` для ролей с шаблоном (`if request.user.profile.role in CHECKLIST_ROLES`)
- [ ] **Делегировать**: OpenRouter — найти все места, где надо вставить меню; я — финальная сборка

### Этап 6: Деплой
- [ ] Прогон тестов локально (если будут)
- [ ] Коммит и push
- [ ] Деплой: build + up -d + миграция
- [ ] Зайти в админку прод и наполнить шаблоны Оператора и Снабжения пунктами

---

## Что куда делегировать

| Этап | Кто |
|------|-----|
| 1: модели + миграция + admin | **Ollama Agent** — шаблонный код, после ревью моей моделью |
| 2: snapshot + интеграция | **OpenRouter Agent** — анализ существующего `request_create` |
| 3: toggle endpoint | **OpenRouter Agent** (использовать `cargo_item_toggle_cz` как образец) |
| 4: UI блок чек-листа | **Я (Claude Opus)** — интеграция в существующий шаблон |
| 5: «Текущие дела» | **Я** — UX-композиция |
| 6: деплой | **Я** — стандартная процедура |

---

## Открытые вопросы (на потом)

1. Нужно ли уведомление о невыполненных пунктах? (например бэйдж в меню «Дела (3)» с количеством)
2. Нужно ли блокировать переход статуса заявки, если есть невыполненные пункты роли, ответственной за этот шаг? (например, чтобы Оператор не мог передать в Снабжение, пока не отчекал все свои пункты)
3. Хранить ли историю чек-листов (audit log, кто что отчекал/откатил)? Сейчас храним только последнее состояние.
4. Drag-and-drop переупорядочивания пунктов в админке (django-admin-sortable2)?
5. Поле `comment` у `RequestChecklistItem` — чтобы оставить пометку рядом с пунктом? (например «Цена отличается от спецификации, согласовать»)

---

## После запуска

1. Наполнить начальные шаблоны:
   - **Оператор:** Счёт выслан / Дата отгрузки согласована / Спецификация есть / Цены верны / Перепродажа не нужна / ТТН готов
   - **Снабжение:** пользователь напишет свои пункты
2. Объявить команде, как пользоваться.
3. Через неделю — обратная связь, добавить в шаблоны то, чего не хватает.
