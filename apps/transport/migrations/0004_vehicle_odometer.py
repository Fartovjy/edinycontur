from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("transport", "0003_vehicle_photo_color_year_notes"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicle",
            name="odometer_km",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="Пробег, км"),
        ),
        migrations.AddField(
            model_name="vehicle",
            name="service_due_km",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="До следующего ТО, км"),
        ),
    ]
