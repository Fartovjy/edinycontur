from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.accounts.constants import ROLE_CHOICES


class ChecklistTemplate(models.Model):
    """Шаблон чек-листа для одной роли. Одна запись на роль."""

    role = models.CharField("Роль", max_length=32, choices=ROLE_CHOICES, unique=True)
    name = models.CharField(
        "Название",
        max_length=120,
        blank=True,
        help_text="Для удобства в админке, например «Чек-лист оператора».",
    )
    is_active = models.BooleanField("Активен", default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Шаблон чек-листа"
        verbose_name_plural = "Шаблоны чек-листов"

    def __str__(self):
        return self.name or f"Чек-лист ({self.get_role_display()})"


class ChecklistTemplateItem(models.Model):
    """Пункт шаблона чек-листа."""

    template = models.ForeignKey(
        ChecklistTemplate,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Шаблон",
    )
    text = models.CharField("Текст пункта", max_length=255)
    order = models.PositiveIntegerField("Порядок", default=0)
    is_active = models.BooleanField(
        "Активен",
        default=True,
        help_text="Снимите, чтобы исключить из новых чек-листов без удаления.",
    )

    class Meta:
        verbose_name = "Пункт шаблона"
        verbose_name_plural = "Пункты шаблонов"
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.order}. {self.text}"


class RequestChecklistItem(models.Model):
    """Snapshot пункта чек-листа для конкретной заявки."""

    request = models.ForeignKey(
        "logistics.LogisticsRequest",
        on_delete=models.CASCADE,
        related_name="checklist_items",
        verbose_name="Заявка",
    )
    role = models.CharField("Роль", max_length=32, choices=ROLE_CHOICES)
    text = models.CharField("Текст пункта (snapshot)", max_length=255)
    order = models.PositiveIntegerField(default=0)
    template_item = models.ForeignKey(
        ChecklistTemplateItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Исходный пункт шаблона; null если шаблон удалён.",
    )
    is_done = models.BooleanField("Выполнено", default=False)
    checked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checked_checklist_items",
    )
    checked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Пункт чек-листа заявки"
        verbose_name_plural = "Пункты чек-листа заявки"
        ordering = ["role", "order", "id"]
        indexes = [models.Index(fields=["request", "role"], name="checklists__req_role_idx")]

    def __str__(self):
        return f"[{self.role}] {self.text[:60]}"


class UserTask(models.Model):
    """Произвольное дело, созданное пользователем вручную."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_tasks",
        verbose_name="Пользователь",
    )
    text = models.CharField("Текст задачи", max_length=500)
    due_date = models.DateField("Крайняя дата", null=True, blank=True)
    is_done = models.BooleanField("Выполнено", default=False)
    done_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Личное дело"
        verbose_name_plural = "Личные дела"
        ordering = ["is_done", "due_date", "-created_at"]

    def __str__(self):
        return self.text[:80]

    @property
    def is_overdue(self):
        if self.is_done or not self.due_date:
            return False
        return self.due_date < timezone.localdate()
