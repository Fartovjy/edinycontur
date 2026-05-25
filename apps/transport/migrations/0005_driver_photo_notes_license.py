from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("transport", "0004_vehicle_odometer"),
    ]

    operations = [
        migrations.AddField(
            model_name="driver",
            name="photo",
            field=models.ImageField(blank=True, upload_to="drivers/", verbose_name="Фото"),
        ),
        migrations.AddField(
            model_name="driver",
            name="license_number",
            field=models.CharField(blank=True, max_length=20, verbose_name="Номер ВУ"),
        ),
        migrations.AddField(
            model_name="driver",
            name="license_category",
            field=models.CharField(blank=True, max_length=20, verbose_name="Категории прав"),
        ),
        migrations.AddField(
            model_name="driver",
            name="notes",
            field=models.TextField(blank=True, verbose_name="Заметки"),
        ),
    ]
