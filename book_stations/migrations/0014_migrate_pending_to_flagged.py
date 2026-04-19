from django.db import migrations


def migrate_pending_to_flagged(apps, schema_editor):
    BookStation = apps.get_model("book_stations", "BookStation")
    BookStation.objects.filter(moderation_status="PENDING").update(moderation_status="FLAGGED")


class Migration(migrations.Migration):

    dependencies = [
        ("book_stations", "0013_alter_bookstation_moderation_status"),
    ]

    operations = [
        migrations.RunPython(migrate_pending_to_flagged, migrations.RunPython.noop),
    ]
