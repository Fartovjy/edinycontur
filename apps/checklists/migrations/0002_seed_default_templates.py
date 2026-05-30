from django.db import migrations


def seed_default_templates(apps, schema_editor):
    ChecklistTemplate = apps.get_model("checklists", "ChecklistTemplate")
    ChecklistTemplate.objects.get_or_create(
        role="operator",
        defaults={"name": "Чек-лист оператора", "is_active": True},
    )
    ChecklistTemplate.objects.get_or_create(
        role="supply",
        defaults={"name": "Чек-лист снабжения", "is_active": True},
    )


def remove_default_templates(apps, schema_editor):
    ChecklistTemplate = apps.get_model("checklists", "ChecklistTemplate")
    ChecklistTemplate.objects.filter(role__in=["operator", "supply"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("checklists", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_default_templates, remove_default_templates),
    ]
