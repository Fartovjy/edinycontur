from django.conf import settings
from django.db import models

from apps.accounts.constants import ROLE_CHOICES


class Notification(models.Model):
    recipient_role = models.CharField("Роль получателя", max_length=32, choices=ROLE_CHOICES, blank=True)
    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Получатель (персонально)",
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="personal_notifications",
        help_text="Если указано — уведомление видит только этот пользователь (используется для наблюдателей).",
    )
    request = models.ForeignKey(
        "logistics.LogisticsRequest",
        verbose_name="Заявка",
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="notifications",
    )
    pickup_request = models.ForeignKey(
        "logistics.SupplyPickupRequest",
        verbose_name="Заявка на забор",
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="notifications",
    )
    message = models.CharField("Сообщение", max_length=255)
    is_read = models.BooleanField("Прочитано", default=False)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"

    def __str__(self):
        return self.message
