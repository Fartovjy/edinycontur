from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("transport", "0006_vehicle_next_inspection_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicle",
            name="default_driver",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="default_vehicle",
                to="transport.driver",
                verbose_name="Водитель по умолчанию",
            ),
        ),
    ]
