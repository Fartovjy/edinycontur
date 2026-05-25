from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("transport", "0002_update_vehicle_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicle",
            name="color",
            field=models.CharField(blank=True, default="", max_length=60, verbose_name="Цвет"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="vehicle",
            name="year",
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="Год выпуска"),
        ),
        migrations.AddField(
            model_name="vehicle",
            name="notes",
            field=models.TextField(blank=True, verbose_name="Заметки"),
        ),
        migrations.AddField(
            model_name="vehicle",
            name="photo",
            field=models.ImageField(blank=True, upload_to="vehicles/", verbose_name="Фото"),
        ),
    ]
