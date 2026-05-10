import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("logistics", "0003_alter_logisticsrequest_request_number"),
    ]

    operations = [
        migrations.RenameField(
            model_name="requeststatushistory",
            old_name="user",
            new_name="changed_by",
        ),
        migrations.RenameField(
            model_name="requeststatushistory",
            old_name="changed_at",
            new_name="created_at",
        ),
        migrations.AlterModelOptions(
            name="requeststatushistory",
            options={
                "ordering": ["-created_at"],
                "verbose_name": "История статуса",
                "verbose_name_plural": "История статусов",
            },
        ),
        migrations.AlterField(
            model_name="requeststatushistory",
            name="changed_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="status_changes", to=settings.AUTH_USER_MODEL, verbose_name="Кто изменил"),
        ),
        migrations.AlterField(
            model_name="requeststatushistory",
            name="created_at",
            field=models.DateTimeField(default=django.utils.timezone.now, verbose_name="Создано"),
        ),
    ]
