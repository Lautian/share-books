from django.contrib import admin

from moderation.models import ModerationLog


@admin.register(ModerationLog)
class ModerationLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "moderator", "action", "item", "book_station", "from_status", "to_status")
    list_filter = ("action",)
    search_fields = ("moderator__username", "item__title", "book_station__name")
    readonly_fields = ("timestamp", "moderator", "item", "book_station", "action", "from_status", "to_status")
    ordering = ("-timestamp",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
