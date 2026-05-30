from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("transport", "0005_driver_photo_notes_license"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicle",
            name="next_inspection_date",
            field=models.DateField(
                blank=True,
                null=True,
                verbose_name="Дата следующего технического осмотра",
            ),
        ),
    ]
