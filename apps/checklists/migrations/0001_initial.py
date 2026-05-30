import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


ROLE_CHOICES = [
    ("admin", "Администратор"),
    ("operator", "Оператор"),
    ("supply", "Снабжение"),
    ("transport", "Транспорт"),
    ("warehouse", "Склад"),
    ("driver", "Водитель"),
    ("manager", "Руководитель"),
    ("viewer", "Наблюдатель"),
]


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("logistics", "0014_add_client_phone"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ChecklistTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=ROLE_CHOICES, max_length=32, unique=True, verbose_name="Роль")),
                ("name", models.CharField(blank=True, help_text="Для удобства в админке, например «Чек-лист оператора».", max_length=120, verbose_name="Название")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активен")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Шаблон чек-листа",
                "verbose_name_plural": "Шаблоны чек-листов",
            },
        ),
        migrations.CreateModel(
            name="ChecklistTemplateItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("text", models.CharField(max_length=255, verbose_name="Текст пункта")),
                ("order", models.PositiveIntegerField(default=0, verbose_name="Порядок")),
                ("is_active", models.BooleanField(default=True, help_text="Снимите, чтобы исключить из новых чек-листов без удаления.", verbose_name="Активен")),
                ("template", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="checklists.checklisttemplate", verbose_name="Шаблон")),
            ],
            options={
                "verbose_name": "Пункт шаблона",
                "verbose_name_plural": "Пункты шаблонов",
                "ordering": ["order", "id"],
            },
        ),
        migrations.CreateModel(
            name="RequestChecklistItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=ROLE_CHOICES, max_length=32, verbose_name="Роль")),
                ("text", models.CharField(max_length=255, verbose_name="Текст пункта (snapshot)")),
                ("order", models.PositiveIntegerField(default=0)),
                ("is_done", models.BooleanField(default=False, verbose_name="Выполнено")),
                ("checked_at", models.DateTimeField(blank=True, null=True)),
                ("checked_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="checked_checklist_items", to=settings.AUTH_USER_MODEL)),
                ("request", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="checklist_items", to="logistics.logisticsrequest", verbose_name="Заявка")),
                ("template_item", models.ForeignKey(blank=True, help_text="Исходный пункт шаблона; null если шаблон удалён.", null=True, on_delete=django.db.models.deletion.SET_NULL, to="checklists.checklisttemplateitem")),
            ],
            options={
                "verbose_name": "Пункт чек-листа заявки",
                "verbose_name_plural": "Пункты чек-листа заявки",
                "ordering": ["role", "order", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="requestchecklistitem",
            index=models.Index(fields=["request", "role"], name="checklists__req_role_idx"),
        ),
    ]
