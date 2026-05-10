from django.db import migrations, models


def copy_client_fields(apps, schema_editor):
    LogisticsRequest = apps.get_model("logistics", "LogisticsRequest")
    for request in LogisticsRequest.objects.select_related("client").all():
        client = request.client
        request.client_name = client.name
        request.client_contact = ", ".join(value for value in [client.contact_name, client.phone] if value)
        request.save(update_fields=["client_name", "client_contact"])


class Migration(migrations.Migration):
    dependencies = [
        ("logistics", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="logisticsrequest",
            old_name="number",
            new_name="request_number",
        ),
        migrations.RenameField(
            model_name="logisticsrequest",
            old_name="cargo_name",
            new_name="cargo_description",
        ),
        migrations.RenameField(
            model_name="logisticsrequest",
            old_name="requested_delivery_date",
            new_name="planned_delivery_date",
        ),
        migrations.AddField(
            model_name="logisticsrequest",
            name="actual_delivery_date",
            field=models.DateField(blank=True, null=True, verbose_name="Фактическая дата доставки"),
        ),
        migrations.AddField(
            model_name="logisticsrequest",
            name="actual_ship_date",
            field=models.DateField(blank=True, null=True, verbose_name="Фактическая дата отгрузки"),
        ),
        migrations.AddField(
            model_name="logisticsrequest",
            name="cargo_places_count",
            field=models.PositiveIntegerField(default=1, verbose_name="Количество мест"),
        ),
        migrations.AddField(
            model_name="logisticsrequest",
            name="cargo_volume_m3",
            field=models.DecimalField(decimal_places=3, default=0, max_digits=10, verbose_name="Объем, м3"),
        ),
        migrations.AddField(
            model_name="logisticsrequest",
            name="client_address",
            field=models.CharField(blank=True, max_length=255, verbose_name="Адрес клиента"),
        ),
        migrations.AddField(
            model_name="logisticsrequest",
            name="client_contact",
            field=models.CharField(blank=True, max_length=160, verbose_name="Контакт клиента"),
        ),
        migrations.AddField(
            model_name="logisticsrequest",
            name="client_name",
            field=models.CharField(default="", max_length=180, verbose_name="Клиент"),
        ),
        migrations.AddField(
            model_name="logisticsrequest",
            name="cz_checked",
            field=models.BooleanField(default=False, verbose_name="Честный Знак проверен"),
        ),
        migrations.AddField(
            model_name="logisticsrequest",
            name="cz_comment",
            field=models.TextField(blank=True, verbose_name="Комментарий по Честному Знаку"),
        ),
        migrations.AddField(
            model_name="logisticsrequest",
            name="cz_required",
            field=models.BooleanField(default=False, verbose_name="Требуется проверка Честного Знака"),
        ),
        migrations.AddField(
            model_name="logisticsrequest",
            name="cz_status",
            field=models.CharField(
                choices=[
                    ("not_required", "Не требуется"),
                    ("pending", "Ожидает проверки"),
                    ("ok", "Проверено"),
                    ("problem", "Есть замечания"),
                ],
                default="not_required",
                max_length=32,
                verbose_name="Статус Честного Знака",
            ),
        ),
        migrations.AddField(
            model_name="logisticsrequest",
            name="dimensions_text",
            field=models.CharField(blank=True, max_length=255, verbose_name="Габариты"),
        ),
        migrations.AddField(
            model_name="logisticsrequest",
            name="is_archived",
            field=models.BooleanField(default=False, verbose_name="В архиве"),
        ),
        migrations.AddField(
            model_name="logisticsrequest",
            name="planned_ship_date",
            field=models.DateField(blank=True, null=True, verbose_name="Плановая дата отгрузки"),
        ),
        migrations.AddField(
            model_name="logisticsrequest",
            name="priority",
            field=models.CharField(
                choices=[
                    ("low", "Низкий"),
                    ("normal", "Обычный"),
                    ("high", "Высокий"),
                    ("urgent", "Срочный"),
                ],
                default="normal",
                max_length=20,
                verbose_name="Приоритет",
            ),
        ),
        migrations.AddField(
            model_name="logisticsrequest",
            name="supply_eta_date",
            field=models.DateField(blank=True, null=True, verbose_name="Плановая дата поступления от снабжения"),
        ),
        migrations.AddField(
            model_name="logisticsrequest",
            name="warehouse_arrival_date",
            field=models.DateField(blank=True, null=True, verbose_name="Дата поступления на склад"),
        ),
        migrations.RunPython(copy_client_fields, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="logisticsrequest",
            name="client",
        ),
        migrations.RemoveField(
            model_name="logisticsrequest",
            name="description",
        ),
        migrations.AlterField(
            model_name="logisticsrequest",
            name="cargo_description",
            field=models.TextField(default="", verbose_name="Описание груза"),
        ),
        migrations.AlterField(
            model_name="logisticsrequest",
            name="cargo_weight_kg",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="Вес, кг"),
        ),
        migrations.AlterField(
            model_name="logisticsrequest",
            name="planned_delivery_date",
            field=models.DateField(blank=True, null=True, verbose_name="Плановая дата доставки"),
        ),
        migrations.AlterField(
            model_name="logisticsrequest",
            name="region",
            field=models.CharField(default="", max_length=120, verbose_name="Регион"),
        ),
        migrations.AlterField(
            model_name="logisticsrequest",
            name="request_number",
            field=models.CharField(default="", max_length=32, unique=True, verbose_name="Номер заявки"),
        ),
    ]
