from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("checklists", "0002_seed_default_templates"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("text", models.CharField(max_length=500, verbose_name="Текст задачи")),
                ("due_date", models.DateField(blank=True, null=True, verbose_name="Крайняя дата")),
                ("is_done", models.BooleanField(default=False, verbose_name="Выполнено")),
                ("done_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="user_tasks",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Пользователь",
                    ),
                ),
            ],
            options={
                "verbose_name": "Личное дело",
                "verbose_name_plural": "Личные дела",
                "ordering": ["is_done", "due_date", "-created_at"],
            },
        ),
    ]
