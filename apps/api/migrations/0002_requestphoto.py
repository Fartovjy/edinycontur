import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0001_initial"),
        ("logistics", "0014_add_client_phone"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RequestPhoto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "request",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="driver_photos",
                        to="logistics.logisticsrequest",
                        verbose_name="Заявка",
                    ),
                ),
                (
                    "uploaded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="uploaded_photos",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Загрузил",
                    ),
                ),
                ("photo", models.ImageField(upload_to="driver_photos/%Y/%m/", verbose_name="Фото")),
                (
                    "photo_type",
                    models.CharField(
                        choices=[
                            ("loading", "При погрузке"),
                            ("delivery", "При доставке"),
                            ("problem", "Проблема"),
                        ],
                        default="loading",
                        max_length=20,
                        verbose_name="Тип фото",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Загружено")),
            ],
            options={
                "verbose_name": "Фото водителя",
                "verbose_name_plural": "Фото водителей",
                "ordering": ["created_at"],
            },
        ),
    ]
