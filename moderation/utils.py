MODERATOR_GROUP_NAME = "Moderators"


def is_moderator(user):
    """Return True if the user has moderator privileges."""
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_staff or user.is_superuser:
        return True
    # Cache the group membership check on the user object to avoid repeated
    # DB queries within the same request.
    if not hasattr(user, "_is_moderator_group_member"):
        user._is_moderator_group_member = user.groups.filter(
            name=MODERATOR_GROUP_NAME
        ).exists()
    return user._is_moderator_group_member
