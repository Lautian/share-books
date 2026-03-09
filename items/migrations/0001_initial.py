import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("book_stations", "0004_bookstation_item_added_by_and_item_thumbnail"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="Item",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        ("title", models.CharField(max_length=255)),
                        ("author", models.CharField(blank=True, max_length=255)),
                        ("thumbnail_url", models.URLField(blank=True)),
                        ("description", models.TextField(blank=True)),
                        (
                            "item_type",
                            models.CharField(
                                choices=[
                                    ("BOOK", "Book"),
                                    ("MAGAZINE", "Magazine"),
                                    ("DVD", "DVD"),
                                    ("OTHER", "Other"),
                                ],
                                default="BOOK",
                                max_length=16,
                            ),
                        ),
                        (
                            "status",
                            models.CharField(
                                choices=[
                                    ("AT_BOOK_STATION", "At book station"),
                                    ("TAKEN_OUT", "Taken out"),
                                    ("LOST", "Lost"),
                                    ("UNKNOWN", "Unknown"),
                                ],
                                default="UNKNOWN",
                                max_length=24,
                            ),
                        ),
                        ("last_activity", models.DateField(blank=True, null=True)),
                        (
                            "added_by",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.PROTECT,
                                related_name="added_items",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                        (
                            "current_book_station",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="current_items",
                                to="book_stations.bookstation",
                            ),
                        ),
                        (
                            "last_seen_at",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="last_seen_items",
                                to="book_stations.bookstation",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "book_stations_item",
                        "ordering": ["title", "id"],
                        "indexes": [
                            models.Index(
                                fields=["status", "current_book_station"],
                                name="book_statio_status_ea334b_idx",
                            ),
                            models.Index(
                                fields=["item_type"],
                                name="book_statio_item_ty_1d68a8_idx",
                            ),
                            models.Index(
                                fields=["last_activity"],
                                name="book_statio_last_ac_6c1fa4_idx",
                            ),
                        ],
                        "constraints": [
                            models.CheckConstraint(
                                condition=(
                                    ~models.Q(status="AT_BOOK_STATION")
                                    | models.Q(current_book_station__isnull=False)
                                ),
                                name="item_station_required_when_at_station",
                            )
                        ],
                    },
                ),
            ],
        ),
    ]
