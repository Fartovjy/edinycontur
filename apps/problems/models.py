from django.conf import settings
from django.db import models
from django.utils import timezone


class ProblemReport(models.Model):
    DAMAGED_PACKAGING = "damaged_packaging"
    WRONG_PALLETS = "wrong_pallets"
    MISSING_GOODS = "missing_goods"
    CZ_ISSUE = "cz_issue"
    CLIENT_REFUSED = "client_refused"
    PARTIAL_ACCEPTANCE = "partial_acceptance"
    DOCUMENT_MISMATCH = "document_mismatch"
    TRANSPORT_DELAY = "transport_delay"
    OTHER = "other"
    PROBLEM_TYPES = [
        (DAMAGED_PACKAGING, "Повреждена упаковка"),
        (WRONG_PALLETS, "Неверные паллеты"),
        (MISSING_GOODS, "Недостача товара"),
        (CZ_ISSUE, "Проблема ЧЗ"),
        (CLIENT_REFUSED, "Клиент отказался"),
        (PARTIAL_ACCEPTANCE, "Частичная приёмка"),
        (DOCUMENT_MISMATCH, "Несоответствие документов"),
        (TRANSPORT_DELAY, "Задержка транспорта"),
        (OTHER, "Другое"),
    ]

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (OPEN, "Открыта"),
        (IN_PROGRESS, "В работе"),
        (RESOLVED, "Решена"),
        (CANCELLED, "Отменена"),
    ]

    request = models.ForeignKey("logistics.LogisticsRequest", on_delete=models.CASCADE, related_name="problems", verbose_name="Заявка")
    problem_type = models.CharField("Тип проблемы", max_length=32, choices=PROBLEM_TYPES)
    description = models.TextField("Описание")
    status = models.CharField("Статус", max_length=32, choices=STATUS_CHOICES, default=OPEN)
    responsible_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_problems", verbose_name="Ответственный")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reported_problems", verbose_name="Создал")
    created_at = models.DateTimeField("Создана", default=timezone.now)
    resolved_at = models.DateTimeField("Решена", null=True, blank=True)
    resolution_comment = models.TextField("Комментарий решения", blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Проблема"
        verbose_name_plural = "Проблемы"

    def __str__(self):
        return f"{self.request.request_number} - {self.get_problem_type_display()}"
