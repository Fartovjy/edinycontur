STATUS_CREATED = "created"
STATUS_WAITING_SUPPLY = "waiting_supply"
STATUS_WAITING_ARRIVAL = "waiting_arrival"
STATUS_IN_WAREHOUSE = "in_warehouse"
STATUS_CZ_CHECK = "cz_check"
STATUS_READY_TO_SHIP = "ready_to_ship"
STATUS_TRANSPORT_ASSIGNED = "transport_assigned"
STATUS_SHIPPED = "shipped"
STATUS_IN_TRANSIT = "in_transit"
STATUS_DELIVERED = "delivered"
STATUS_PROBLEM = "problem"
STATUS_CLOSED = "closed"
STATUS_CANCELLED = "cancelled"

STATUS_CHOICES = [
    (STATUS_CREATED, "Создана"),
    (STATUS_WAITING_SUPPLY, "Ожидает снабжение"),
    (STATUS_WAITING_ARRIVAL, "Ожидает поступление"),
    (STATUS_IN_WAREHOUSE, "На складе"),
    (STATUS_CZ_CHECK, "Проверка ЦЗ"),
    (STATUS_READY_TO_SHIP, "Готова к отгрузке"),
    (STATUS_TRANSPORT_ASSIGNED, "Назначен транспорт"),
    (STATUS_SHIPPED, "Отгружена"),
    (STATUS_IN_TRANSIT, "В пути"),
    (STATUS_DELIVERED, "Доставлена"),
    (STATUS_PROBLEM, "Проблема"),
    (STATUS_CLOSED, "Закрыта"),
    (STATUS_CANCELLED, "Отменена"),
]
