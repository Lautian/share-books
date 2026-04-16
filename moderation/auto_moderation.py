"""
Auto-moderation for item text fields.

``auto_moderate_item`` is the single entry-point used by item create/edit views.
The current implementation is a **stub** that always passes unless specific fields
are listed in the ``ITEM_AUTOMODERATION_STUB_FLAGGED_FIELDS`` Django setting
(a list of field names: ``"title"``, ``"author"``, and/or ``"description"``).

Replace this module with real classification logic in a future issue.
Expected return value of ``auto_moderate_item``:

    {
        "has_bad_language": bool,
        "flagged_fields": list[str],   # subset of the fields checked
    }
"""

from django.conf import settings


def auto_moderate_item(*, title: str, author: str, description: str) -> dict:
    """Return an auto-moderation verdict for item text content.

    Currently a **stub** – returns no bad language by default.

    The optional Django setting ``ITEM_AUTOMODERATION_STUB_FLAGGED_FIELDS``
    (a list of field names) can be used to simulate a positive finding,
    which is useful for tests and manual verification of the UI flow.
    """
    configured_fields = getattr(settings, "ITEM_AUTOMODERATION_STUB_FLAGGED_FIELDS", [])
    if isinstance(configured_fields, str):
        configured_fields = [configured_fields]

    allowed_fields = {"title", "author", "description"}
    flagged_fields = []
    for field in configured_fields:
        if field in allowed_fields and field not in flagged_fields:
            flagged_fields.append(field)

    return {
        "has_bad_language": bool(flagged_fields),
        "flagged_fields": flagged_fields,
    }
