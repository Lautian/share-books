from django.conf import settings
from django.db import models
from django.utils import timezone

from book_stations.models import BookStation


class Movement(models.Model):
    class MovementType(models.TextChoices):
        TAKEN_OUT = "TAKEN_OUT", "Taken out"
        PLACED_IN = "PLACED_IN", "Placed in"
        MARKED_LOST = "MARKED_LOST", "Marked lost"
        MARKED_FOUND = "MARKED_FOUND", "Marked found"
        TRANSFERRED = "TRANSFERRED", "Transferred"
        CREATED = "CREATED", "Created"

    item = models.ForeignKey(
        "items.Item",
        on_delete=models.CASCADE,
        related_name="movements",
    )
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reported_movements",
    )
    from_book_station = models.ForeignKey(
        BookStation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="movements_from",
    )
    to_book_station = models.ForeignKey(
        BookStation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="movements_to",
    )
    movement_type = models.CharField(max_length=16, choices=MovementType.choices)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-timestamp", "-id"]
        indexes = [
            models.Index(fields=["item", "timestamp"], name="movements_item_time_idx"),
            models.Index(fields=["movement_type"], name="movements_type_idx"),
        ]

    def __str__(self):
        return f"{self.item.title} {self.movement_type}"
