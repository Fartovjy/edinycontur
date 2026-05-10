from django.db import migrations, models


def map_attachment_types(apps, schema_editor):
    Attachment = apps.get_model("documents", "Attachment")
    mapping = {
        "pdf": "pdf_document",
        "photo": "cargo_photo",
        "other": "other",
    }
    for attachment in Attachment.objects.all():
        attachment.file_type = mapping.get(attachment.attachment_type, "other")
        attachment.save(update_fields=["file_type"])


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="attachment",
            name="description",
            field=models.TextField(blank=True, verbose_name="Описание"),
        ),
        migrations.AddField(
            model_name="attachment",
            name="file_type",
            field=models.CharField(
                choices=[
                    ("pdf_document", "PDF-документ"),
                    ("cargo_photo", "Фото груза"),
                    ("damage_photo", "Фото повреждения"),
                    ("delivery_photo", "Фото доставки"),
                    ("cz_photo", "Фото Честного Знака"),
                    ("other", "Другое"),
                ],
                default="other",
                max_length=32,
                verbose_name="Тип файла",
            ),
        ),
        migrations.RunPython(map_attachment_types, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="attachment",
            name="attachment_type",
        ),
    ]
