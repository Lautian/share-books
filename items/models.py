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

    class ModerationStatus(models.TextChoices):
        FLAGGED = "FLAGGED", "Flagged"
        APPROVED = "APPROVED", "Approved"
        REPORTED = "REPORTED", "Reported"
        REJECTED = "REJECTED", "Rejected"

    moderation_status = models.CharField(
        max_length=16,
        choices=ModerationStatus.choices,
        default=ModerationStatus.APPROVED,
    )
    claimed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="claimed_items",
    )
    pending_edit = models.JSONField(
        null=True,
        blank=True,
        default=None,
        help_text="Serialised pending edit fields submitted by the owner. None means no edit is awaiting moderation.",
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

    @classmethod
    def _effective_station_id(cls, status, station_id):
        if status == cls.Status.AT_BOOK_STATION:
            return station_id
        return None

    @classmethod
    def _resolve_movement_type(
        cls,
        *,
        is_create,
        previous_status,
        previous_station_id,
        status,
        station_id,
    ):
        if is_create:
            return "CREATED"

        if (
            previous_station_id is not None
            and station_id is not None
            and previous_station_id != station_id
        ):
            return "TRANSFERRED"

        if previous_station_id is not None and station_id is None:
            if status == cls.Status.LOST:
                return "MARKED_LOST"
            return "TAKEN_OUT"

        if previous_station_id is None and station_id is not None:
            if previous_status == cls.Status.LOST:
                return "MARKED_FOUND"
            return "PLACED_IN"

        if previous_status != status:
            if status == cls.Status.LOST:
                return "MARKED_LOST"
            if previous_status == cls.Status.LOST:
                return "MARKED_FOUND"
            if status == cls.Status.TAKEN_OUT:
                return "TAKEN_OUT"

        if status == cls.Status.AT_BOOK_STATION:
            return "PLACED_IN"
        return "TAKEN_OUT"

    def save(self, *args, **kwargs):
        reported_by = kwargs.pop("reported_by", None)
        movement_notes = kwargs.pop("movement_notes", "")
        create_movement = kwargs.pop("create_movement", True)

        is_create = self._state.adding
        previous_status = None
        previous_station_id = None

        if not is_create and self.pk:
            previous_state = (
                type(self)
                .objects.filter(pk=self.pk)
                .values("status", "current_book_station_id")
                .first()
            )
            if previous_state is not None:
                previous_status = previous_state["status"]
                previous_station_id = previous_state["current_book_station_id"]

        if self.last_activity is None:
            self.last_activity = timezone.localdate()
        if self.current_book_station_id is not None:
            self.last_seen_at = self.current_book_station
        super().save(*args, **kwargs)

        if not create_movement:
            return

        effective_previous_station_id = self._effective_station_id(
            previous_status,
            previous_station_id,
        )
        effective_current_station_id = self._effective_station_id(
            self.status,
            self.current_book_station_id,
        )

        has_movement_change = (
            is_create
            or previous_status != self.status
            or effective_previous_station_id != effective_current_station_id
        )
        if not has_movement_change:
            return

        if reported_by is None:
            reported_by = self.added_by

        from movements.models import Movement

        movement_type = self._resolve_movement_type(
            is_create=is_create,
            previous_status=previous_status,
            previous_station_id=effective_previous_station_id,
            status=self.status,
            station_id=effective_current_station_id,
        )

        Movement.objects.create(
            item=self,
            reported_by=reported_by,
            from_book_station_id=effective_previous_station_id,
            to_book_station_id=effective_current_station_id,
            movement_type=movement_type,
            notes=movement_notes,
        )
