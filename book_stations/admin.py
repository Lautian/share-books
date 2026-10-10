from django.contrib import admin

from .models import BookStation, StationVisit


@admin.register(BookStation)
class BookStationAdmin(admin.ModelAdmin):
	list_display = ("name", "readable_id", "location", "added_by")
	search_fields = ("name", "readable_id", "location")


@admin.register(StationVisit)
class StationVisitAdmin(admin.ModelAdmin):
	list_display = ("user", "station", "visited_at")
	search_fields = ("user__username", "station__name")
