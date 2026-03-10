from datetime import datetime, time, timedelta

from django.db import migrations
from django.db.models import Min
from django.utils import timezone


def backfill_created_movements(apps, schema_editor):
    Item = apps.get_model("items", "Item")
    Movement = apps.get_model("movements", "Movement")
    db_alias = schema_editor.connection.alias

    created_item_subquery = (
        Movement.objects.using(db_alias)
        .filter(movement_type="CREATED")
        .values("item_id")
    )
    items_without_created = Item.objects.using(db_alias).exclude(
        id__in=created_item_subquery
    )

    if not items_without_created.exists():
        return

    earliest_movement_map = dict(
        Movement.objects.using(db_alias)
        .filter(item_id__in=items_without_created.values("id"))
        .values("item_id")
        .annotate(first_timestamp=Min("timestamp"))
        .values_list("item_id", "first_timestamp")
    )

    default_tz = timezone.get_current_timezone()
    now = timezone.now()
    new_movements = []

    for item in items_without_created.iterator(chunk_size=500):
        to_station_id = (
            item.current_book_station_id if item.status == "AT_BOOK_STATION" else None
        )

        timestamp = earliest_movement_map.get(item.id)
        if timestamp is not None:
            timestamp = timestamp - timedelta(seconds=1)
        elif item.last_activity is not None:
            # Midday avoids edge cases around DST transitions at midnight.
            timestamp = timezone.make_aware(
                datetime.combine(item.last_activity, time(hour=12)),
                default_tz,
            )
        else:
            timestamp = now

        new_movements.append(
            Movement(
                item_id=item.id,
                reported_by_id=item.added_by_id,
                from_book_station_id=None,
                to_book_station_id=to_station_id,
                movement_type="CREATED",
                timestamp=timestamp,
                notes="Backfilled initial movement for existing item.",
            )
        )

    Movement.objects.using(db_alias).bulk_create(new_movements, batch_size=500)


class Migration(migrations.Migration):
    dependencies = [
        ("movements", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            backfill_created_movements,
            migrations.RunPython.noop,
        )
    ]
