from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_userprofile_request_list_period"),
    ]

    operations = [
        # Remove ForeignKey to Role from User
        migrations.RemoveField(
            model_name="user",
            name="role",
        ),
        # Remove legacy telegram_chat_id from User
        migrations.RemoveField(
            model_name="user",
            name="telegram_chat_id",
        ),
        # Drop the legacy Role table entirely
        migrations.DeleteModel(
            name="Role",
        ),
    ]
