import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("problems", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameField(
            model_name="problemreport",
            old_name="resolution_status",
            new_name="status",
        ),
        migrations.RenameField(
            model_name="problemreport",
            old_name="responsible",
            new_name="responsible_user",
        ),
        migrations.RemoveField(
            model_name="problemreport",
            name="photo",
        ),
        migrations.RemoveField(
            model_name="problemreport",
            name="updated_at",
        ),
        migrations.AddField(
            model_name="problemreport",
            name="resolution_comment",
            field=models.TextField(blank=True, verbose_name="Комментарий решения"),
        ),
        migrations.AddField(
            model_name="problemreport",
            name="resolved_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Решена"),
        ),
        migrations.AlterField(
            model_name="problemreport",
            name="responsible_user",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assigned_problems", to=settings.AUTH_USER_MODEL, verbose_name="Ответственный"),
        ),
        migrations.AlterField(
            model_name="problemreport",
            name="status",
            field=models.CharField(
                choices=[
                    ("open", "Открыта"),
                    ("in_progress", "В работе"),
                    ("resolved", "Решена"),
                ],
                default="open",
                max_length=32,
                verbose_name="Статус",
            ),
        ),
    ]
