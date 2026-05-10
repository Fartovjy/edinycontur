from django.db import models

from apps.accounts.constants import ROLE_CHOICES


class Notification(models.Model):
    recipient_role = models.CharField("Роль получателя", max_length=32, choices=ROLE_CHOICES)
    request = models.ForeignKey(
        "logistics.LogisticsRequest",
        verbose_name="Заявка",
        on_delete=models.CASCADE,
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
