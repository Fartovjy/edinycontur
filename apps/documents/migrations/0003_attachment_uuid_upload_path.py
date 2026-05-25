from django.db import migrations, models

import apps.documents.models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0002_update_attachment_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="attachment",
            name="file",
            field=models.FileField(upload_to=apps.documents.models.upload_attachment_path, verbose_name="Файл"),
        ),
    ]
