from django.conf import settings
from django.db import models
from django.utils import timezone


class Attachment(models.Model):
    PDF_DOCUMENT = "pdf_document"
    CARGO_PHOTO = "cargo_photo"
    DAMAGE_PHOTO = "damage_photo"
    DELIVERY_PHOTO = "delivery_photo"
    CZ_PHOTO = "cz_photo"
    OTHER = "other"
    FILE_TYPE_CHOICES = [
        (PDF_DOCUMENT, "PDF-документ"),
        (CARGO_PHOTO, "Фото груза"),
        (DAMAGE_PHOTO, "Фото повреждения"),
        (DELIVERY_PHOTO, "Фото доставки"),
        (CZ_PHOTO, "Фото Честного Знака"),
        (OTHER, "Другое"),
    ]

    request = models.ForeignKey("logistics.LogisticsRequest", on_delete=models.CASCADE, related_name="attachments", verbose_name="Заявка")
    file = models.FileField("Файл", upload_to="attachments/%Y/%m/")
    file_type = models.CharField("Тип файла", max_length=32, choices=FILE_TYPE_CHOICES, default=OTHER)
    description = models.TextField("Описание", blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="attachments", verbose_name="Загрузил")
    uploaded_at = models.DateTimeField("Загружено", default=timezone.now)

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "Вложение"
        verbose_name_plural = "Вложения"

    def __str__(self):
        return f"{self.request.request_number} - {self.get_file_type_display()}"
