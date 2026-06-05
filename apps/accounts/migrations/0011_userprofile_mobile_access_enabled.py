from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0010_userprofile_notification_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="mobile_access_enabled",
            field=models.BooleanField(
                default=False,
                help_text="Разрешить пользователю авторизоваться в мобильном приложении.",
                verbose_name="Доступ к Android-приложению",
            ),
        ),
    ]
