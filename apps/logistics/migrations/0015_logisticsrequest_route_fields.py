from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("logistics", "0014_add_client_phone"),
    ]

    operations = [
        migrations.AddField(
            model_name="logisticsrequest",
            name="route_distance_km",
            field=models.FloatField(blank=True, null=True, verbose_name="Расстояние туда-обратно, км"),
        ),
        migrations.AddField(
            model_name="logisticsrequest",
            name="route_direction_css",
            field=models.CharField(blank=True, default="", max_length=10, verbose_name="CSS-класс направления"),
        ),
        migrations.AddField(
            model_name="logisticsrequest",
            name="route_direction_label",
            field=models.CharField(blank=True, default="", max_length=4, verbose_name="Направление"),
        ),
        migrations.AddField(
            model_name="logisticsrequest",
            name="route_direction_arrow",
            field=models.CharField(blank=True, default="", max_length=2, verbose_name="Стрелка направления"),
        ),
        migrations.AddField(
            model_name="logisticsrequest",
            name="route_days",
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="Дней в пути"),
        ),
    ]
