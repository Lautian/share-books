from django.db import migrations, models


def clear_current_station_for_non_station_items(apps, schema_editor):
    Item = apps.get_model("items", "Item")
    Item.objects.exclude(status="AT_BOOK_STATION").filter(
        current_book_station__isnull=False
    ).update(current_book_station=None)


class Migration(migrations.Migration):
    dependencies = [
        ("items", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            clear_current_station_for_non_station_items,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="item",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(status="AT_BOOK_STATION")
                    | models.Q(current_book_station__isnull=True)
                ),
                name="item_station_must_be_empty_unless_at_station",
            ),
        ),
    ]
