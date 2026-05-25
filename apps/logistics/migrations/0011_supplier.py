from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("logistics", "0010_cargoitem_is_stocked"),
    ]

    operations = [
        migrations.CreateModel(
            name="Supplier",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=180, verbose_name="Название")),
                ("region", models.CharField(blank=True, max_length=120, verbose_name="Регион")),
                ("contact_name", models.CharField(blank=True, max_length=120, verbose_name="Контакт")),
                ("phone", models.CharField(blank=True, max_length=40, verbose_name="Телефон")),
                ("email", models.EmailField(blank=True, verbose_name="Email")),
                ("notes", models.TextField(blank=True, verbose_name="Заметки")),
            ],
            options={
                "verbose_name": "Поставщик",
                "verbose_name_plural": "Поставщики",
                "ordering": ["name"],
            },
        ),
    ]
