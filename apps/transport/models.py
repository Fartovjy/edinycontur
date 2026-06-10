from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Vehicle(models.Model):
    name = models.CharField("Название", max_length=120, default="")
    plate_number = models.CharField("Госномер", max_length=20, unique=True)
    max_weight_kg = models.PositiveIntegerField("Максимальный вес, кг", default=0)
    max_volume_m3 = models.DecimalField("Максимальный объем, м3", max_digits=10, decimal_places=3, default=0)
    vehicle_type = models.CharField("Тип автомобиля", max_length=80, default="")
    color = models.CharField("Цвет", max_length=60, blank=True)
    year = models.PositiveSmallIntegerField("Год выпуска", null=True, blank=True)
    notes = models.TextField("Заметки", blank=True)
    photo = models.ImageField("Фото", upload_to="vehicles/", blank=True)
    odometer_km = models.PositiveIntegerField("Пробег, км", null=True, blank=True)
    service_due_km = models.PositiveIntegerField("До следующего ТО, км", null=True, blank=True)
    next_inspection_date = models.DateField("Дата следующего технического осмотра", null=True, blank=True)
    is_active = models.BooleanField("Активен", default=True)
    default_driver = models.ForeignKey(
        "Driver",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_vehicle",
        verbose_name="Водитель по умолчанию",
    )

    class Meta:
        ordering = ["plate_number"]
        verbose_name = "Автомобиль"
        verbose_name_plural = "Автомобили"

    def __str__(self):
        return f"{self.plate_number} - {self.name}"

    @property
    def service_remaining_km(self):
        """Остаток пробега до следующего ТО.
        service_due_km хранит абсолютный целевой пробег (odometer + интервал).
        """
        if self.service_due_km is None:
            return None
        return max(0, self.service_due_km - (self.odometer_km or 0))

    @property
    def inspection_days_left(self):
        """Сколько дней до даты следующего техосмотра.
        Отрицательное значение — осмотр уже просрочен."""
        if not self.next_inspection_date:
            return None
        return (self.next_inspection_date - timezone.localdate()).days

    @property
    def inspection_warning(self):
        """True, если до ТО осталось <= 21 день (включая просрочку)."""
        d = self.inspection_days_left
        return d is not None and d <= 21

    @property
    def inspection_overdue(self):
        """True, если дата техосмотра уже прошла."""
        d = self.inspection_days_left
        return d is not None and d < 0


class Driver(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="driver_profile", verbose_name="Пользователь")
    full_name = models.CharField("ФИО", max_length=160)
    phone = models.CharField("Телефон", max_length=40)
    telegram_chat_id = models.CharField("Telegram chat ID", max_length=64, blank=True)
    photo = models.ImageField("Фото", upload_to="drivers/", blank=True)
    license_number = models.CharField("Номер ВУ", max_length=20, blank=True)
    license_category = models.CharField("Категории прав", max_length=20, blank=True)
    notes = models.TextField("Заметки", blank=True)
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        ordering = ["full_name"]
        verbose_name = "Водитель"
        verbose_name_plural = "Водители"

    def __str__(self):
        return self.full_name

    @property
    def chat_id(self):
        profile = getattr(self.user, "profile", None) if self.user else None
        return self.telegram_chat_id or (profile.telegram_id if profile else "")
