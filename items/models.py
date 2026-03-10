from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from book_stations.models import BookStation


class Item(models.Model):
    class ItemType(models.TextChoices):
        BOOK = "BOOK", "Book"
        MAGAZINE = "MAGAZINE", "Magazine"
        DVD = "DVD", "DVD"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        AT_BOOK_STATION = "AT_BOOK_STATION", "At book station"
        TAKEN_OUT = "TAKEN_OUT", "Taken out"
        LOST = "LOST", "Lost"
        UNKNOWN = "UNKNOWN", "Unknown"

    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255, blank=True)
    thumbnail_url = models.URLField(blank=True)
    description = models.TextField(blank=True)
    item_type = models.CharField(
        max_length=16,
        choices=ItemType.choices,
        default=ItemType.BOOK,
    )
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.UNKNOWN,
    )
    current_book_station = models.ForeignKey(
        BookStation,
        related_name="current_items",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    last_seen_at = models.ForeignKey(
        BookStation,
        related_name="last_seen_items",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    last_activity = models.DateField(null=True, blank=True)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="added_items",
    )

    class Meta:
        db_table = "book_stations_item"
        ordering = ["title", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    ~models.Q(status="AT_BOOK_STATION")
                    | models.Q(current_book_station__isnull=False)
                ),
                name="item_station_required_when_at_station",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status="AT_BOOK_STATION")
                    | models.Q(current_book_station__isnull=True)
                ),
                name="item_station_must_be_empty_unless_at_station",
            )
        ]
        indexes = [
            models.Index(
                fields=["status", "current_book_station"],
                name="book_statio_status_ea334b_idx",
            ),
            models.Index(fields=["item_type"], name="book_statio_item_ty_1d68a8_idx"),
            models.Index(
                fields=["last_activity"],
                name="book_statio_last_ac_6c1fa4_idx",
            ),
        ]

    def __str__(self):
        return f"{self.title} [{self.status}]"

    def clean(self):
        super().clean()
        if self.item_type == self.ItemType.BOOK and not (self.author or "").strip():
            raise ValidationError(
                {"author": "Author is required when the item type is BOOK."}
            )
        if self.status == self.Status.AT_BOOK_STATION and self.current_book_station_id is None:
            raise ValidationError(
                {
                    "current_book_station": (
                        "Current book station is required when status is AT_BOOK_STATION."
                    )
                }
            )
        if (
            self.status != self.Status.AT_BOOK_STATION
            and self.current_book_station_id is not None
        ):
            raise ValidationError(
                {
                    "current_book_station": (
                        "Current book station must be empty unless status is "
                        "AT_BOOK_STATION."
                    )
                }
            )

    def save(self, *args, **kwargs):
        if self.last_activity is None:
            self.last_activity = timezone.localdate()
        if self.current_book_station_id is not None:
            self.last_seen_at = self.current_book_station
        super().save(*args, **kwargs)
