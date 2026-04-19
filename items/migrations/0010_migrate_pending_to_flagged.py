from django.db import migrations


def migrate_pending_to_flagged(apps, schema_editor):
    Item = apps.get_model("items", "Item")
    Item.objects.filter(moderation_status="PENDING").update(moderation_status="FLAGGED")


class Migration(migrations.Migration):

    dependencies = [
        ("items", "0009_alter_item_moderation_status"),
    ]

    operations = [
        migrations.RunPython(migrate_pending_to_flagged, migrations.RunPython.noop),
    ]
