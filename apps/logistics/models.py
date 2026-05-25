from django.conf import settings
from django.db import IntegrityError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from .constants import STATUS_CHOICES, STATUS_CREATED


class Client(models.Model):
    name = models.CharField("Название", max_length=180)
    region = models.CharField("Регион", max_length=120)
    contact_name = models.CharField("Контакт", max_length=120, blank=True)
    phone = models.CharField("Телефон", max_length=40, blank=True)
    email = models.EmailField("Email", blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Клиент"
        verbose_name_plural = "Клиенты"

    def __str__(self):
        return self.name


class Supplier(models.Model):
    name = models.CharField("Название", max_length=180)
    region = models.CharField("Регион", max_length=120, blank=True)
    contact_name = models.CharField("Контакт", max_length=120, blank=True)
    phone = models.CharField("Телефон", max_length=40, blank=True)
    email = models.EmailField("Email", blank=True)
    notes = models.TextField("Заметки", blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Поставщик"
        verbose_name_plural = "Поставщики"

    def __str__(self):
        return self.name


class Warehouse(models.Model):
    name = models.CharField("Название", max_length=180)
    region = models.CharField("Регион", max_length=120)
    address = models.CharField("Адрес", max_length=255)

    class Meta:
        ordering = ["name"]
        verbose_name = "Склад"
        verbose_name_plural = "Склады"

    def __str__(self):
        return f"{self.name}, {self.region}"


class LogisticsRequest(models.Model):
    PRIORITY_NORMAL = "normal"
    PRIORITY_URGENT = "urgent"
    PRIORITY_VIP = "vip"
    PRIORITY_CRITICAL = "critical"
    PRIORITY_CHOICES = [
        (PRIORITY_NORMAL, "Обычный"),
        (PRIORITY_URGENT, "Срочный"),
        (PRIORITY_VIP, "VIP"),
        (PRIORITY_CRITICAL, "Критический"),
    ]

    CZ_NOT_REQUIRED = "not_required"
    CZ_PENDING = "pending"
    CZ_OK = "ok"
    CZ_PROBLEM = "problem"
    CZ_STATUS_CHOICES = [
        (CZ_NOT_REQUIRED, "Не требуется"),
        (CZ_PENDING, "Ожидает проверки"),
        (CZ_OK, "Проверено"),
        (CZ_PROBLEM, "Есть замечания"),
    ]

    request_number = models.CharField("Номер заявки", max_length=32, unique=True, blank=True, default="")
    client_name = models.CharField("Клиент", max_length=180, default="")
    client_address = models.CharField("Адрес клиента", max_length=255, blank=True)
    client_contact = models.CharField("Контакт клиента", max_length=160, blank=True)
    region = models.CharField("Регион", max_length=120, default="")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="requests", verbose_name="Склад")
    cargo_description = models.TextField("Описание груза", default="")
    cargo_places_count = models.PositiveIntegerField("Количество мест", default=1)
    cargo_weight_kg = models.DecimalField("Вес, кг", max_digits=10, decimal_places=2, default=0)
    cargo_volume_m3 = models.DecimalField("Объем, м3", max_digits=10, decimal_places=3, default=0)
    dimensions_text = models.CharField("Габариты", max_length=255, blank=True)
    supply_eta_date = models.DateField("Плановая дата поступления от снабжения", null=True, blank=True)
    warehouse_arrival_date = models.DateField("Дата поступления на склад", null=True, blank=True)
    planned_ship_date = models.DateField("Плановая дата отгрузки", null=True, blank=True)
    actual_ship_date = models.DateField("Фактическая дата отгрузки", null=True, blank=True)
    planned_delivery_date = models.DateField("Плановая дата доставки", null=True, blank=True)
    actual_delivery_date = models.DateField("Фактическая дата доставки", null=True, blank=True)
    status = models.CharField("Статус", max_length=32, choices=STATUS_CHOICES, default=STATUS_CREATED, db_index=True)
    priority = models.CharField("Приоритет", max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_NORMAL)
    cz_required = models.BooleanField("Требуется проверка Честного Знака", default=False)
    cz_checked = models.BooleanField("Честный Знак проверен", default=False)
    cz_status = models.CharField("Статус Честного Знака", max_length=32, choices=CZ_STATUS_CHOICES, default=CZ_NOT_REQUIRED)
    cz_comment = models.TextField("Комментарий по Честному Знаку", blank=True)
    cz_problem = models.BooleanField("Проблема Честного Знака", default=False)
    assigned_vehicle = models.ForeignKey("transport.Vehicle", on_delete=models.SET_NULL, null=True, blank=True, related_name="requests", verbose_name="Автомобиль")
    assigned_driver = models.ForeignKey("transport.Driver", on_delete=models.SET_NULL, null=True, blank=True, related_name="requests", verbose_name="Водитель")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_requests", verbose_name="Создал")
    viewer_users = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="viewable_requests", verbose_name="Наблюдатели")
    created_at = models.DateTimeField("Создана", default=timezone.now)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)
    is_archived = models.BooleanField("В архиве", default=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Логистическая заявка"
        verbose_name_plural = "Логистические заявки"

    def __str__(self):
        return self.request_number

    def get_absolute_url(self):
        return reverse("request_detail", kwargs={"pk": self.pk})

    @classmethod
    def generate_request_number(cls):
        prefix = timezone.localdate().strftime("%d%m%y - ")
        last_request = cls.objects.filter(request_number__startswith=prefix).order_by("-request_number").first()
        if not last_request:
            return f"{prefix}01"

        try:
            last_number = int(last_request.request_number.rsplit("-", 1)[1])
        except (IndexError, ValueError):
            last_number = 0
        return f"{prefix}{last_number + 1:02d}"

    def save(self, *args, **kwargs):
        if self.request_number:
            super().save(*args, **kwargs)
            return

        last_error = None
        for _attempt in range(5):
            self.request_number = self.generate_request_number()
            try:
                super().save(*args, **kwargs)
                return
            except IntegrityError as exc:
                last_error = exc
                self.request_number = ""
        raise last_error


class CargoItem(models.Model):
    request = models.ForeignKey(
        LogisticsRequest,
        on_delete=models.CASCADE,
        related_name="cargo_items",
        verbose_name="Заявка",
    )
    name = models.TextField("Наименование")
    qty = models.CharField("Количество / единица", max_length=150, blank=True)
    needs_supply = models.BooleanField("К обеспечению", default=True)
    needs_cz = models.BooleanField("Честный Знак", default=False)
    supply_date = models.DateField("Дата поступления", null=True, blank=True)
    is_stocked = models.BooleanField("Оприходовано", default=False)
    position = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        ordering = ["position", "pk"]
        verbose_name = "Позиция заявки"
        verbose_name_plural = "Позиции заявки"

    def __str__(self):
        return self.name[:80]


class SupplyPickupRequest(models.Model):
    """Заявка транспортному отделу на забор товара у поставщика."""

    STATUS_PENDING = "pending"
    STATUS_TRANSPORT_ASSIGNED = "transport_assigned"
    STATUS_DELIVERED = "delivered"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Новая"),
        (STATUS_TRANSPORT_ASSIGNED, "Транспорт назначен"),
        (STATUS_DELIVERED, "Доставлено на склад"),
    ]

    request_number = models.CharField("Номер", max_length=32, unique=True, blank=True, default="")
    # Необязательная ссылка на родительскую заявку (доставка клиенту)
    logistics_request = models.ForeignKey(
        "LogisticsRequest",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="pickup_requests",
        verbose_name="Заявка на доставку",
    )
    # Позиция товара, из которой создана заявка (для отслеживания)
    source_cargo_item = models.ForeignKey(
        "CargoItem",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="pickup_requests",
        verbose_name="Позиция товара",
    )
    supplier = models.ForeignKey(
        "Supplier",
        on_delete=models.PROTECT,
        related_name="pickup_requests",
        verbose_name="Поставщик",
    )
    pickup_date = models.DateField("Дата забора", null=True, blank=True)
    weight_kg = models.DecimalField("Вес, кг", max_digits=10, decimal_places=2, default=0)
    cargo_notes = models.TextField("Перечень товаров", blank=True)
    assigned_vehicle = models.ForeignKey(
        "transport.Vehicle",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="pickup_requests",
        verbose_name="Автомобиль",
    )
    assigned_driver = models.ForeignKey(
        "transport.Driver",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="pickup_requests",
        verbose_name="Водитель",
    )
    odometer_km = models.PositiveIntegerField("Показания одометра, км", null=True, blank=True)
    status = models.CharField(
        "Статус", max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="created_pickup_requests",
        verbose_name="Создал",
    )
    created_at = models.DateTimeField("Создана", default=timezone.now)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Заявка на забор"
        verbose_name_plural = "Заявки на забор"

    def __str__(self):
        return self.request_number or f"Забор #{self.pk}"

    def get_absolute_url(self):
        return reverse("supply_pickup_detail", kwargs={"pk": self.pk})

    @classmethod
    def generate_request_number(cls):
        prefix = "З" + timezone.localdate().strftime("%d%m%y") + "-"
        last = cls.objects.filter(request_number__startswith=prefix).order_by("-request_number").first()
        if not last:
            return f"{prefix}01"
        try:
            last_number = int(last.request_number.rsplit("-", 1)[1])
        except (IndexError, ValueError):
            last_number = 0
        return f"{prefix}{last_number + 1:02d}"

    def save(self, *args, **kwargs):
        if self.request_number:
            super().save(*args, **kwargs)
            return
        last_error = None
        for _attempt in range(5):
            self.request_number = self.generate_request_number()
            try:
                super().save(*args, **kwargs)
                return
            except IntegrityError as exc:
                last_error = exc
                self.request_number = ""
        raise last_error


class RequestStatusHistory(models.Model):
    request = models.ForeignKey(LogisticsRequest, on_delete=models.CASCADE, related_name="status_history", verbose_name="Заявка")
    old_status = models.CharField("Старый статус", max_length=32, choices=STATUS_CHOICES, blank=True)
    new_status = models.CharField("Новый статус", max_length=32, choices=STATUS_CHOICES)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="status_changes", verbose_name="Кто изменил")
    comment = models.TextField("Комментарий", blank=True)
    created_at = models.DateTimeField("Создано", default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "История статуса"
        verbose_name_plural = "История статусов"

    def __str__(self):
        return f"{self.request.request_number}: {self.old_status or '-'} -> {self.new_status}"


class ArchivistSettings(models.Model):
    retention_days = models.PositiveIntegerField("Хранить заявки в работе, дней", default=180)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Настройки архивариуса"
        verbose_name_plural = "Настройки архивариуса"

    def __str__(self):
        return f"Архивировать старше {self.retention_days} дней"

    @classmethod
    def get_solo(cls):
        obj, _created = cls.objects.get_or_create(pk=1, defaults={"retention_days": 180})
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
