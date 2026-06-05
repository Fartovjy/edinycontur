from django.conf import settings
from django.db import models


class DeviceToken(models.Model):
    """FCM-токен устройства пользователя для отправки push-уведомлений."""

    PLATFORM_ANDROID = "android"
    PLATFORM_IOS = "ios"
    PLATFORM_CHOICES = [
        (PLATFORM_ANDROID, "Android"),
        (PLATFORM_IOS, "iOS"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="device_tokens",
        verbose_name="Пользователь",
    )
    fcm_token = models.CharField("FCM токен", max_length=512, unique=True)
    platform = models.CharField(
        "Платформа", max_length=20, choices=PLATFORM_CHOICES, default=PLATFORM_ANDROID
    )
    last_seen_at = models.DateTimeField("Последнее использование", auto_now=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Токен устройства"
        verbose_name_plural = "Токены устройств"

    def __str__(self):
        return f"{self.user} [{self.platform}] …{self.fcm_token[-12:]}"
