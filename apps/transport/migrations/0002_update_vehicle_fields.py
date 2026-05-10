from django.db import migrations, models


def copy_vehicle_fields(apps, schema_editor):
    Vehicle = apps.get_model("transport", "Vehicle")
    for vehicle in Vehicle.objects.all():
        vehicle.name = vehicle.model
        vehicle.max_weight_kg = vehicle.capacity_kg
        vehicle.vehicle_type = "грузовой"
        vehicle.save(update_fields=["name", "max_weight_kg", "vehicle_type"])


class Migration(migrations.Migration):
    dependencies = [
        ("transport", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicle",
            name="max_volume_m3",
            field=models.DecimalField(decimal_places=3, default=0, max_digits=10, verbose_name="Максимальный объем, м3"),
        ),
        migrations.AddField(
            model_name="vehicle",
            name="max_weight_kg",
            field=models.PositiveIntegerField(default=0, verbose_name="Максимальный вес, кг"),
        ),
        migrations.AddField(
            model_name="vehicle",
            name="name",
            field=models.CharField(default="", max_length=120, verbose_name="Название"),
        ),
        migrations.AddField(
            model_name="vehicle",
            name="vehicle_type",
            field=models.CharField(default="", max_length=80, verbose_name="Тип автомобиля"),
        ),
        migrations.RunPython(copy_vehicle_fields, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="vehicle",
            name="capacity_kg",
        ),
        migrations.RemoveField(
            model_name="vehicle",
            name="model",
        ),
    ]
