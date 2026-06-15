# Интеграция расчета направлений и дней поездки для кнопок-пилюль в календаре

Добавление автоматического расчета сторон света (8 направлений) и длительности поездки в днях (исходя из километража «туда-обратно») для заявок транспортного отдела. Скрипт [Qwen_python_20260611_kyb04d55a.py](file:///c:/Temp/Qwen_python_20260611_kyb04d55a.py) взят за основу для интеграции геокодирования Яндекс.Карт и маршрутизации OSRM.

## Вопросы для уточнения (Open Questions)

> [!IMPORTANT]
> Пожалуйста, подтвердите следующие детали перед началом реализации:

1. **Координаты складов**:
   Поскольку складов будет несколько, мы добавим поля `latitude` (широта) и `longitude` (долгота) в модель `Warehouse` (Склад).
   * Вы согласны вводить их вручную через административную панель Django? Или хотите, чтобы адрес склада автоматически геокодировался через API Яндекс.Карт при сохранении, если координаты не заданы?
   
2. **Формула расчета количества дней**:
   Мы предлагаем следующую логику для перевода общего километража $D$ (туда-обратно в км) в календарные дни $N$:
   * $D \le 500$ км $\implies 1$ день
   * $500 < D \le 1000$ км $\implies 2$ дня
   * $1000 < D \le 1500$ км $\implies 3$ дня
   * Формула в коде: `days = max(1, math.ceil(total_distance_km / 500))`
   * *Вопрос:* Устраивает ли вас такой расчет (шаг в 500 км) или нужно использовать другую дневную норму?

3. **Отображение многодневных пилюль в календаре**:
   Поскольку календарь построен на стандартной сетке CSS Grid, самый надежный и простой способ заставить кнопку «растягиваться» на несколько дней вправо — задать ей ширину в процентах относительно ячейки:
   * 1 день $\implies$ `width: 100%`
   * 2 дня $\implies$ `width: calc(200% + 0.4rem)` (с учетом зазора между колонками)
   * 3 дня $\implies$ `width: calc(300% + 0.8rem)`
   * *Обратите внимание:* Карточка физически находится в дне старта (дата отгрузки) и визуально перекрывает ячейки справа. Если в последующих днях есть другие заявки, они могут визуально перекрываться или сдвигаться вниз. Устраивает ли вас такое поведение для визуальной оценки загрузки?

4. **Где хранить Yandex API Key**:
   * Мы добавим настройку `YANDEX_API_KEY` в `settings.py` с чтением из переменной окружения. Вы сможете прописать ее в файле `.env` на сервере.

---

## Предлагаемые изменения (Proposed Changes)

### 1. Изменение базы данных и моделей

#### [MODIFY] [models.py](file:///C:/Users/Home/Documents/biovak/apps/logistics/models.py)
* В модель `Warehouse` добавим поля координат склада:
  ```python
  latitude = models.DecimalField("Широта", max_digits=9, decimal_places=6, null=True, blank=True)
  longitude = models.DecimalField("Долгота", max_digits=9, decimal_places=6, null=True, blank=True)
  ```
* В модель `LogisticsRequest` добавим поля для кэширования результатов геокодирования и расчетов:
  ```python
  client_latitude = models.DecimalField("Широта клиента", max_digits=9, decimal_places=6, null=True, blank=True)
  client_longitude = models.DecimalField("Долгота клиента", max_digits=9, decimal_places=6, null=True, blank=True)
  route_distance_km = models.DecimalField("Расстояние туда-обратно, км", max_digits=8, decimal_places=1, null=True, blank=True)
  route_direction = models.CharField("Направление (сторона света)", max_length=4, blank=True, default="")
  route_days = models.PositiveSmallIntegerField("Длительность поездки в днях", default=1)
  ```

---

### 2. Логика расчетов (Сервисы)

#### [NEW] [route_utils.py](file:///C:/Users/Home/Documents/biovak/apps/logistics/route_utils.py)
Создадим модуль для выполнения расчетов:
1. `geocode_address(address)`: запрос к Яндекс.Геокодеру (через `settings.YANDEX_API_KEY`).
2. `get_road_distance(lat1, lon1, lat2, lon2)`: запрос к публичному OSRM API для получения расстояния по дорогам. Если запрос падает или расстояние не найдено, возвращает расстояние по прямой (Хаверсин) $\times 1.3$ (коэффициент извилистости дорог).
3. `calculate_bearing(lat1, lon1, lat2, lon2)`: вычисление азимута между точками.
4. `bearing_to_direction(bearing)`: сопоставление азимута с 8 направлениями:
   * `С` (Север)
   * `СВ` (Северо-Восток)
   * `В` (Восток)
   * `ЮВ` (Юго-Восток)
   * `Ю` (Юг)
   * `ЮЗ` (Юго-Запад)
   * `З` (Запад)
   * `СЗ` (Северо-Запад)
5. `update_request_route_info(request_obj)`: общая функция, которая:
   * Находит координаты склада (если не заданы в модели `Warehouse` — геокодирует адрес склада).
   * Геокодирует адрес клиента (если в поле `client_address` уже введены координаты вроде `55.75, 37.61` — использует их напрямую без внешнего запроса).
   * Вычисляет расстояние по дорогам туда-обратно (в одну сторону $\times 2$).
   * Определяет сторону света.
   * Рассчитывает длительность в днях (`ceil(расстояние / 500)`).

---

### 3. Автоматический запуск при сохранении заявки

#### [MODIFY] [models.py](file:///C:/Users/Home/Documents/biovak/apps/logistics/models.py)
* Переопределим метод `save` модели `LogisticsRequest`, чтобы при изменении адреса клиента или склада автоматически вызывалась функция `update_request_route_info` (в блоке `try-except`, чтобы ошибки сети/геокодера не блокировали сохранение заявки):
  ```python
  def save(self, *args, **kwargs):
      # Проверка изменения адреса
      is_new = self.pk is None
      address_changed = False
      if not is_new:
          orig = LogisticsRequest.objects.get(pk=self.pk)
          address_changed = (orig.client_address != self.client_address) or (orig.warehouse_id != self.warehouse_id)
      
      if is_new or address_changed:
          from .route_utils import update_request_route_info
          update_request_route_info(self)
          
      super().save(*args, **kwargs)
  ```

---

### 4. Стилизация и отображение в шаблоне календаря

#### [MODIFY] [request_calendar.html](file:///C:/Users/Home/Documents/biovak/apps/templates/logistics/request_calendar.html)
* В блоке стилей `<style>` добавим цветовые темы для 8 сторон света (используем благородные, не кричащие цвета):
  ```css
  /* Цвета для сторон света (пилюли транспортного календаря) */
  .direction-pill {
    position: relative;
    z-index: 5;
    transition: transform 0.1s ease;
  }
  .direction-pill:hover {
    transform: scale(1.02);
    z-index: 10;
  }
  .dir-C  { background: #eff6ff; color: #1e40af; border-left: 3px solid #3b82f6; } /* Синий */
  .dir-CB { background: #f0fdfa; color: #115e59; border-left: 3px solid #0d9488; } /* Бирюзовый */
  .dir-В  { background: #f0fdf4; color: #166534; border-left: 3px solid #22c55e; } /* Зеленый */
  .dir-ЮВ { background: #f9fde7; color: #4d7c0f; border-left: 3px solid #84cc16; } /* Салатовый */
  .dir-Ю  { background: #fef2f2; color: #991b1b; border-left: 3px solid #ef4444; } /* Красный */
  .dir-ЮЗ { background: #fffbeb; color: #92400e; border-left: 3px solid #f59e0b; } /* Оранжевый */
  .dir-З  { background: #faf5ff; color: #6b21a8; border-left: 3px solid #a855f7; } /* Фиолетовый */
  .dir-СЗ { background: #eef2ff; color: #3730a3; border-left: 3px solid #6366f1; } /* Индиго */
  ```
* Изменим рендеринг пилюли в календаре:
  ```html
  <a class="calendar-request direction-pill dir-{{ item.route_direction|default:'C' }}"
     href="{{ item.get_absolute_url }}"
     draggable="true"
     data-drag-id="{{ item.drag_id }}"
     data-drag-type="{{ item.drag_type }}"
     style="width: calc({{ item.route_days|default:1 }}00% + {{ item.route_days|default:1|add:-1 }} * 0.4rem);"
     title="{{ item.request_number }} · {{ item.client_name }} ({{ item.route_direction }}, {{ item.route_distance_km }} км, {{ item.route_days }} дн.)">
    {{ item.client_name|default:item.request_number }}
    <span style="display:block;font-size:.68em;opacity:.75;">
      {{ item.route_direction }} · {{ item.route_distance_km|default:"0" }} км · {{ item.route_days }} дн.
    </span>
  </a>
  ```

---

## План проверки (Verification Plan)

### Автоматические тесты
1. Написание unit-тестов в `apps/logistics/tests.py`:
   * Тест расчета азимута и перевода его в 8 направлений.
   * Тест мокирования внешних запросов к Яндекс.Геокодеру и OSRM.
   * Тест вычисления расстояний и дней.

### Ручная проверка
1. Создание новой заявки с адресом (например, Тверь) и проверка:
   * Автоматического заполнения полей координат, направления и километров в БД.
   * Отображения в календаре пилюли соответствующего цвета и ширины (дней).
