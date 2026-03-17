from django.contrib import admin, messages
from django.contrib.admin.sites import NotRegistered
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group

from moderation.utils import MODERATOR_GROUP_NAME

User = get_user_model()


@admin.action(description="Assign selected users to Moderators group")
def assign_moderator_role(modeladmin, request, queryset):
    moderator_group, _ = Group.objects.get_or_create(name=MODERATOR_GROUP_NAME)
    assigned_count = 0
    for user in queryset:
        if not user.groups.filter(pk=moderator_group.pk).exists():
            user.groups.add(moderator_group)
            assigned_count += 1
    messages.success(request, f"Assigned moderator role to {assigned_count} user(s).")


@admin.action(description="Remove selected users from Moderators group")
def remove_moderator_role(modeladmin, request, queryset):
    moderator_group = Group.objects.filter(name=MODERATOR_GROUP_NAME).first()
    if moderator_group is None:
        messages.info(request, "Moderators group does not exist yet.")
        return

    removed_count = 0
    for user in queryset:
        if user.groups.filter(pk=moderator_group.pk).exists():
            user.groups.remove(moderator_group)
            removed_count += 1
    messages.success(request, f"Removed moderator role from {removed_count} user(s).")


class UserAdmin(DjangoUserAdmin):
    list_display = DjangoUserAdmin.list_display + ("has_moderator_role",)
    actions = (DjangoUserAdmin.actions or []) + [
        assign_moderator_role,
        remove_moderator_role,
    ]

    @admin.display(boolean=True, description="Moderator")
    def has_moderator_role(self, obj):
        return obj.groups.filter(name=MODERATOR_GROUP_NAME).exists()


try:
    admin.site.unregister(User)
except NotRegistered:
    pass

admin.site.register(User, UserAdmin)
