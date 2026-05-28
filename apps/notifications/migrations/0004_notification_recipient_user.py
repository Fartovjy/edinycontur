from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("notifications", "0003_alter_notification_recipient_role"),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="recipient_user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name="personal_notifications",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Получатель (персонально)",
                help_text="Если указано — уведомление видит только этот пользователь (используется для наблюдателей).",
            ),
        ),
        migrations.AlterField(
            model_name="notification",
            name="recipient_role",
            field=models.CharField(
                blank=True,
                max_length=32,
                verbose_name="Роль получателя",
                choices=[
                    ("admin", "Администратор"),
                    ("operator", "Оператор"),
                    ("supply", "Снабжение"),
                    ("transport", "Транспорт"),
                    ("warehouse", "Склад"),
                    ("driver", "Водитель"),
                    ("manager", "Руководитель"),
                    ("viewer", "Наблюдатель"),
                ],
            ),
        ),
    ]
