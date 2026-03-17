MODERATOR_GROUP_NAME = "Moderators"


def is_moderator(user):
    """Return True if the user has moderator privileges."""
    if not user.is_authenticated or not user.is_active:
        return False
    return (
        user.is_staff
        or user.is_superuser
        or user.groups.filter(name=MODERATOR_GROUP_NAME).exists()
    )
