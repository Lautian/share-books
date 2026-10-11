from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext, gettext_lazy as _

from book_stations.models import BookStation


class Movement(models.Model):
    class MovementType(models.TextChoices):
        TAKEN_OUT = "TAKEN_OUT", _("Taken out")
        PLACED_IN = "PLACED_IN", _("Placed in")
        MARKED_LOST = "MARKED_LOST", _("Marked lost")
        MARKED_FOUND = "MARKED_FOUND", _("Marked found")
        TRANSFERRED = "TRANSFERRED", _("Transferred")
        CREATED = "CREATED", _("Created")

    UI_TYPE_LABELS = {
        MovementType.TAKEN_OUT: _("Taken out"),
        MovementType.PLACED_IN: _("Placed in station"),
        MovementType.MARKED_LOST: _("Marked lost"),
        MovementType.MARKED_FOUND: _("Marked found"),
        MovementType.TRANSFERRED: _("Transferred"),
        MovementType.CREATED: _("Added to catalog"),
    }

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

    @property
    def user_friendly_type_label(self):
        return self.UI_TYPE_LABELS.get(self.movement_type, self.get_movement_type_display())

    @property
    def timeline_marker(self):
        marker_map = {
            self.MovementType.TAKEN_OUT: "OUT",
            self.MovementType.PLACED_IN: "IN",
            self.MovementType.MARKED_LOST: "LOST",
            self.MovementType.MARKED_FOUND: "FOUND",
            self.MovementType.TRANSFERRED: "MOVE",
            self.MovementType.CREATED: "NEW",
        }
        return marker_map.get(self.movement_type, "LOG")

    @property
    def timeline_description(self):
        from_station_name = (
            self.from_book_station.name
            if self.from_book_station is not None
            else gettext("unknown")
        )
        to_station_name = (
            self.to_book_station.name
            if self.to_book_station is not None
            else gettext("unknown")
        )

        if self.movement_type == self.MovementType.CREATED:
            if self.to_book_station is not None:
                return gettext("Item record created at %(station)s.") % {
                    "station": to_station_name,
                }
            return gettext("Item record created with no station assigned yet.")

        if self.movement_type == self.MovementType.TRANSFERRED:
            return gettext("Moved from %(from_station)s to %(to_station)s.") % {
                "from_station": from_station_name,
                "to_station": to_station_name,
            }

        if self.movement_type == self.MovementType.PLACED_IN:
            if self.to_book_station is not None:
                return gettext("Placed in %(station)s.") % {"station": to_station_name}
            return gettext("Placed in a station.")

        if self.movement_type == self.MovementType.TAKEN_OUT:
            if self.from_book_station is not None:
                return gettext("Taken out from %(station)s.") % {
                    "station": from_station_name,
                }
            return gettext("Taken out from station.")

        if self.movement_type == self.MovementType.MARKED_LOST:
            if self.from_book_station is not None:
                return gettext("Marked as lost after being at %(station)s.") % {
                    "station": from_station_name,
                }
            return gettext("Marked as lost.")

        if self.movement_type == self.MovementType.MARKED_FOUND:
            if self.to_book_station is not None:
                return gettext("Marked as found at %(station)s.") % {
                    "station": to_station_name,
                }
            return gettext("Marked as found.")

        return gettext("Movement recorded.")
