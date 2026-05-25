import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("logistics", "0011_supplier"),
        ("transport", "0005_driver_photo_notes_license"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SupplyPickupRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("request_number", models.CharField(blank=True, default="", max_length=32, unique=True, verbose_name="Номер")),
                ("pickup_date", models.DateField(blank=True, null=True, verbose_name="Дата забора")),
                ("weight_kg", models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="Вес, кг")),
                ("cargo_notes", models.TextField(blank=True, verbose_name="Перечень товаров")),
                ("odometer_km", models.PositiveIntegerField(blank=True, null=True, verbose_name="Показания одометра, км")),
                ("status", models.CharField(
                    choices=[("pending", "Новая"), ("transport_assigned", "Транспорт назначен"), ("delivered", "Доставлено на склад")],
                    db_index=True, default="pending", max_length=32, verbose_name="Статус",
                )),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="Создана")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлена")),
                ("assigned_driver", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="pickup_requests", to="transport.driver", verbose_name="Водитель")),
                ("assigned_vehicle", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="pickup_requests", to="transport.vehicle", verbose_name="Автомобиль")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_pickup_requests", to=settings.AUTH_USER_MODEL, verbose_name="Создал")),
                ("logistics_request", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="pickup_requests", to="logistics.logisticsrequest", verbose_name="Заявка на доставку")),
                ("source_cargo_item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="pickup_requests", to="logistics.cargoitem", verbose_name="Позиция товара")),
                ("supplier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="pickup_requests", to="logistics.supplier", verbose_name="Поставщик")),
            ],
            options={
                "verbose_name": "Заявка на забор",
                "verbose_name_plural": "Заявки на забор",
                "ordering": ["-created_at"],
            },
        ),
    ]
