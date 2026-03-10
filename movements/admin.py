from django.contrib import admin

from .models import Movement


@admin.register(Movement)
class MovementAdmin(admin.ModelAdmin):
    list_display = (
        "item",
        "movement_type",
        "from_book_station",
        "to_book_station",
        "reported_by",
        "timestamp",
    )
    list_filter = ("movement_type", "timestamp", "from_book_station", "to_book_station")
    search_fields = ("item__title", "reported_by__username", "notes")
