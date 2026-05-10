from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

from .constants import ROLE_CHOICES, USER_PROFILE_ROLE_CHOICES


class Role(models.Model):
    code = models.CharField("Код", max_length=32, choices=ROLE_CHOICES, unique=True)
    title = models.CharField("Название", max_length=80)

    class Meta:
        ordering = ["code"]
        verbose_name = "Роль"
        verbose_name_plural = "Роли"

    def __str__(self):
        return self.title


class User(AbstractUser):
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, related_name="users", verbose_name="Роль")
    telegram_chat_id = models.CharField("Telegram chat ID", max_length=64, blank=True)

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile", verbose_name="Пользователь")
    role = models.CharField("Роль", max_length=32, choices=USER_PROFILE_ROLE_CHOICES)
    phone = models.CharField("Телефон", max_length=40, blank=True)
    telegram_id = models.CharField("Telegram ID", max_length=64, blank=True)
    default_vehicle = models.ForeignKey("transport.Vehicle", on_delete=models.SET_NULL, null=True, blank=True, related_name="driver_profiles", verbose_name="Автомобиль по умолчанию")
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"

    def __str__(self):
        return f"{self.user} - {self.get_role_display()}"
