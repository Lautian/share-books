from django.conf import settings
from django.db import models


class ModerationLog(models.Model):
    class Action(models.TextChoices):
        ITEM_APPROVED = "ITEM_APPROVED", "Item approved"
        ITEM_EDIT_APPROVED = "ITEM_EDIT_APPROVED", "Item edit approved"
        ITEM_EDIT_REJECTED = "ITEM_EDIT_REJECTED", "Item edit rejected"
        STATION_APPROVED = "STATION_APPROVED", "Station approved"
        STATION_EDIT_APPROVED = "STATION_EDIT_APPROVED", "Station edit approved"
        STATION_EDIT_REJECTED = "STATION_EDIT_REJECTED", "Station edit rejected"

    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="moderation_logs",
    )
    item = models.ForeignKey(
        "items.Item",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderation_logs",
    )
    book_station = models.ForeignKey(
        "book_stations.BookStation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderation_logs",
    )
    action = models.CharField(max_length=32, choices=Action)
    from_status = models.CharField(max_length=32, blank=True)
    to_status = models.CharField(max_length=32, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.moderator} – {self.get_action_display()} at {self.timestamp}"
