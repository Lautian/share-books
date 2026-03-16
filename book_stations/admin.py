from django.contrib import admin

from .models import BookStation


@admin.register(BookStation)
class BookStationAdmin(admin.ModelAdmin):
	list_display = ("name", "readable_id", "location", "added_by", "moderation_status")
	list_filter = ("moderation_status",)
	search_fields = ("name", "readable_id", "location")
