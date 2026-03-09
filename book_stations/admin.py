from django.contrib import admin

from .models import BookStation, Item


@admin.register(BookStation)
class BookStationAdmin(admin.ModelAdmin):
	list_display = ("name", "readable_id", "location")
	search_fields = ("name", "readable_id", "location")


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
	list_display = (
		"title",
		"item_type",
		"status",
		"current_book_station",
		"last_seen_at",
		"last_activity",
	)
	list_filter = ("item_type", "status", "current_book_station", "last_seen_at")
	search_fields = ("title", "author", "description")
