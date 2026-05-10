from django.conf import settings
from django.db import models


class Vehicle(models.Model):
    name = models.CharField("Название", max_length=120, default="")
    plate_number = models.CharField("Госномер", max_length=20, unique=True)
    max_weight_kg = models.PositiveIntegerField("Максимальный вес, кг", default=0)
    max_volume_m3 = models.DecimalField("Максимальный объем, м3", max_digits=10, decimal_places=3, default=0)
    vehicle_type = models.CharField("Тип автомобиля", max_length=80, default="")
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        ordering = ["plate_number"]
        verbose_name = "Автомобиль"
        verbose_name_plural = "Автомобили"

    def __str__(self):
        return f"{self.plate_number} - {self.name}"


class Driver(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="driver_profile", verbose_name="Пользователь")
    full_name = models.CharField("ФИО", max_length=160)
    phone = models.CharField("Телефон", max_length=40)
    telegram_chat_id = models.CharField("Telegram chat ID", max_length=64, blank=True)
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        ordering = ["full_name"]
        verbose_name = "Водитель"
        verbose_name_plural = "Водители"

    def __str__(self):
        return self.full_name

    @property
    def chat_id(self):
        return self.telegram_chat_id or (self.user.telegram_chat_id if self.user else "")
