from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_alter_userprofile_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='notify_via_telegram',
            field=models.BooleanField(default=True, verbose_name='Уведомления в Telegram'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='notify_via_email',
            field=models.BooleanField(default=False, verbose_name='Уведомления на email'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='telegram_link_token',
            field=models.CharField(blank=True, max_length=16, verbose_name='Токен привязки Telegram'),
        ),
    ]
