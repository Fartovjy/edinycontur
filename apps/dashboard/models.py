from django.db import models


class SiteBranding(models.Model):
    company_logo = models.FileField("Логотип компании", upload_to="branding/", blank=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Логотип компании"
        verbose_name_plural = "Логотип компании"

    def __str__(self):
        return "Логотип компании"

    @classmethod
    def current(cls):
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
