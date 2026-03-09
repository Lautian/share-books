from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("book_stations", "0004_bookstation_item_added_by_and_item_thumbnail"),
        ("items", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(name="Item"),
            ],
        ),
    ]
