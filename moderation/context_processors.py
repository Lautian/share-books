from moderation.utils import is_moderator


def moderator_context(request):
    """Expose moderator status to all templates."""
    return {"user_is_moderator": is_moderator(request.user)}
