import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
        ("logistics", "0012_supply_pickup_request"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="request",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="notifications",
                to="logistics.logisticsrequest",
                verbose_name="Заявка",
            ),
        ),
        migrations.AddField(
            model_name="notification",
            name="pickup_request",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="notifications",
                to="logistics.supplypickuprequest",
                verbose_name="Заявка на забор",
            ),
        ),
    ]
