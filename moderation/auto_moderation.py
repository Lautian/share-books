"""
Auto-moderation for item text fields.

``auto_moderate_item`` is the single entry-point used by item create/edit views.
The implementation performs simple heuristic checks for:

- links / URLs
- unsuitable language (profanity, slurs, sexual content)
- overtly commercial spam phrases

The optional ``ITEM_AUTOMODERATION_STUB_FLAGGED_FIELDS`` setting is still honored
as a manual override for tests or manual verification.

Expected return value of ``auto_moderate_item``:

    {
        "has_bad_language": bool,
        "flagged_fields": list[str],   # subset of the fields checked
    }
"""

import re
from django.conf import settings


_URL_PATTERNS = (
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"www\.", re.IGNORECASE),
)

_COMMON_TLDS = (
    "com",
    "net",
    "org",
    "io",
    "co",
    "me",
    "biz",
    "info",
    "dev",
    "app",
    "shop",
    "online",
    "store",
    "link",
    "xyz",
)

_URL_PATTERNS += (
    re.compile(
        rf"\b[a-z0-9](?:[a-z0-9-]{{0,61}}[a-z0-9])?\.(?:{'|'.join(_COMMON_TLDS)})\b",
        re.IGNORECASE,
    ),
)

_PROFANITY_TERMS = (
    "fuck",
    "fucking",
    "shit",
    "bitch",
    "asshole",
    "bastard",
    "cunt",
    "slut",
    "whore",
)
_SLUR_TERMS = ("nigger", "nigga", "spic", "kike", "chink")
_SEXUAL_CONTENT_TERMS = ("porn", "xxx", "nsfw", "nude", "hentai")

_PROFANITY_PATTERNS = (
    re.compile(rf"\b(?:{'|'.join(re.escape(term) for term in _PROFANITY_TERMS)})\b", re.IGNORECASE),
)
_SLURS_PATTERNS = (
    re.compile(rf"\b(?:{'|'.join(re.escape(term) for term in _SLUR_TERMS)})\b", re.IGNORECASE),
)
_SEXUAL_CONTENT_PATTERNS = (
    re.compile(
        rf"\b(?:{'|'.join(re.escape(term) for term in _SEXUAL_CONTENT_TERMS)})\b",
        re.IGNORECASE,
    ),
)

_SPAM_PHRASES = (
    "promo code",
    "promotional code",
    "discount code",
    "limited time offer",
    "buy now",
    "order now",
    "click here",
    "act now",
    "subscribe now",
    "free shipping",
    "sale ends",
    "earn money fast",
    "work from home",
    "crypto giveaway",
    "investment opportunity",
    "guaranteed income",
)

_SPAM_PATTERNS = (
    re.compile(
        rf"\b(?:{'|'.join(re.escape(phrase) for phrase in _SPAM_PHRASES)})\b",
        re.IGNORECASE,
    ),
)

_CHECK_ORDER = ("title", "author", "description")


def _field_matches_auto_moderation(text: str) -> bool:
    if not text:
        return False

    return any(
        pattern.search(text)
        for pattern in (
            *_URL_PATTERNS,
            *_PROFANITY_PATTERNS,
            *_SLURS_PATTERNS,
            *_SEXUAL_CONTENT_PATTERNS,
            *_SPAM_PATTERNS,
        )
    )


def auto_moderate_item(*, title: str, author: str, description: str) -> dict:
    """Return an auto-moderation verdict for item text content.

    The optional Django setting ``ITEM_AUTOMODERATION_STUB_FLAGGED_FIELDS``
    (a list of field names) can be used to force flagged fields, which is useful
    for tests and manual verification of the moderation UI flow.
    """
    values = {
        "title": title or "",
        "author": author or "",
        "description": description or "",
    }

    flagged_fields = [
        field for field in _CHECK_ORDER if _field_matches_auto_moderation(values[field])
    ]

    configured_fields = getattr(settings, "ITEM_AUTOMODERATION_STUB_FLAGGED_FIELDS", [])
    if isinstance(configured_fields, str):
        configured_fields = [configured_fields]
    elif not configured_fields:
        configured_fields = []

    allowed_fields = set(_CHECK_ORDER)
    for field in configured_fields:
        if field in allowed_fields and field not in flagged_fields:
            flagged_fields.append(field)

    return {
        "has_bad_language": bool(flagged_fields),
        "flagged_fields": flagged_fields,
    }
