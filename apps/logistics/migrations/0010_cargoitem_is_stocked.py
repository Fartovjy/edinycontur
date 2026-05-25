from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("logistics", "0009_cargoitem_needs_cz_supply_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="cargoitem",
            name="is_stocked",
            field=models.BooleanField(default=False, verbose_name="Оприходовано"),
        ),
    ]
