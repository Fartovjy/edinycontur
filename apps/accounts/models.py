from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

from .constants import USER_PROFILE_ROLE_CHOICES


def default_calendar_status_filters():
    return ["created", "supply", "shipment", "delivery", "done", "problem"]


REQUEST_LIST_PERIOD_DAY = "day"
REQUEST_LIST_PERIOD_WEEK = "week"
REQUEST_LIST_PERIOD_TWO_WEEKS = "two_weeks"
REQUEST_LIST_PERIOD_MONTH = "month"
REQUEST_LIST_PERIOD_CHOICES = [
    (REQUEST_LIST_PERIOD_DAY, "День"),
    (REQUEST_LIST_PERIOD_WEEK, "Рабочая неделя"),
    (REQUEST_LIST_PERIOD_TWO_WEEKS, "2 недели"),
    (REQUEST_LIST_PERIOD_MONTH, "Месяц"),
]


class User(AbstractUser):
    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile", verbose_name="Пользователь")
    role = models.CharField("Роль", max_length=32, choices=USER_PROFILE_ROLE_CHOICES)
    phone = models.CharField("Телефон", max_length=40, blank=True)
    telegram_id = models.CharField("Telegram ID", max_length=64, blank=True)
    default_vehicle = models.ForeignKey("transport.Vehicle", on_delete=models.SET_NULL, null=True, blank=True, related_name="driver_profiles", verbose_name="Автомобиль по умолчанию")
    calendar_status_filters = models.JSONField("Фильтры статусов календаря", default=default_calendar_status_filters, blank=True)
    request_list_period = models.CharField("Период списка заявок", max_length=16, choices=REQUEST_LIST_PERIOD_CHOICES, default=REQUEST_LIST_PERIOD_MONTH)
    is_active = models.BooleanField("Активен", default=True)
    notify_via_telegram = models.BooleanField("Уведомления в Telegram", default=True)
    notify_via_email = models.BooleanField("Уведомления на email", default=False)
    telegram_link_token = models.CharField("Токен привязки Telegram", max_length=16, blank=True)
    mobile_access_enabled = models.BooleanField(
        "Доступ к Android-приложению",
        default=False,
        help_text="Разрешить пользователю авторизоваться в мобильном приложении.",
    )

    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"

    def __str__(self):
        return f"{self.user} - {self.get_role_display()}"
