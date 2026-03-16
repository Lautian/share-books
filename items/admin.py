from django.contrib import admin

from .models import Item


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "item_type",
        "status",
        "moderation_status",
        "current_book_station",
        "last_seen_at",
        "last_activity",
        "added_by",
    )
    list_filter = ("item_type", "status", "moderation_status", "current_book_station", "last_seen_at")
    search_fields = ("title", "author", "description")
