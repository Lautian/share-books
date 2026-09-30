from django.contrib import admin

from .models import BookStation


@admin.register(BookStation)
class BookStationAdmin(admin.ModelAdmin):
	list_display = ("name", "readable_id", "location", "added_by")
	search_fields = ("name", "readable_id", "location")
