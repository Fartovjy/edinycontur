from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("logistics", "0008_cargo_item"),
    ]

    operations = [
        migrations.AddField(
            model_name="cargoitem",
            name="needs_cz",
            field=models.BooleanField(default=False, verbose_name="Честный Знак"),
        ),
        migrations.AddField(
            model_name="cargoitem",
            name="supply_date",
            field=models.DateField(blank=True, null=True, verbose_name="Дата поступления"),
        ),
    ]
