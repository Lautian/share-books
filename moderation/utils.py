def is_moderator(user):
    """Return True if the user has moderator privileges (staff or superuser)."""
    return user.is_active and (user.is_staff or user.is_superuser)
