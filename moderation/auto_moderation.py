"""
Auto-moderation for generic named text fields and item text fields.

``auto_moderate_fields`` is the generic entry-point used to evaluate arbitrary
named text fields. ``auto_moderate_item`` is a convenience wrapper used by item
create/edit views.
The implementation performs heuristic checks for:

- links / URLs
- unsuitable language (profanity, slurs, sexual content) loaded from JSON word lists
  covering English, Dutch, German, French and Spanish
- overtly commercial spam phrases (multilingual)
- social-media account references (@ handles, profile links, phone numbers)
- junk text (excessive repeated characters, emoji overload)

Word lists are stored in ``moderation/resources/bad_words.json`` and
``moderation/resources/spam_phrases.json``, sourced from LDNOOBW (CC BY 4.0).

The optional ``ITEM_AUTOMODERATION_STUB_FLAGGED_FIELDS`` setting is still honored
as a manual override for tests or manual verification.

Expected return value of ``auto_moderate_fields`` / ``auto_moderate_item``:

    {
        "has_bad_language": bool,
        "flagged_fields": list[str],   # subset of the fields checked
    }
"""

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path

from django.conf import settings

_RESOURCES_DIR = Path(__file__).parent / "resources"


# ---------------------------------------------------------------------------
# Helper: load JSON resource file and flatten terms across all languages
# ---------------------------------------------------------------------------

def _load_terms_from_json(filename: str) -> list[str]:
    path = _RESOURCES_DIR / filename
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Auto-moderation resource file not found: {path}. "
            "Ensure the moderation/resources/ directory is present."
        ) from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Auto-moderation resource file is malformed JSON: {path}. "
            f"Parse error: {exc}"
        ) from exc
    terms: set[str] = set()
    for lang_terms in data.values():
        terms.update(t.strip() for t in lang_terms if t.strip())
    # Sort longest-first so the alternation matches the most specific phrase first.
    return sorted(terms, key=len, reverse=True)


def _build_word_boundary_pattern(terms: list[str]) -> re.Pattern | None:
    """Compile a regex that matches word-like terms and symbol-only terms safely.

    Word-like terms (containing at least one ``\\w`` character) are wrapped with
    ``(?<!\\w)...(?!\\w)`` to avoid partial-word matches.  Symbol-only terms
    (e.g. emoji such as ``🖕``) don't contain word characters so ``\\b`` would
    never match them; they are instead placed in a plain alternation.
    """
    if not terms:
        return None

    word_like_terms: list[str] = []
    symbol_only_terms: list[str] = []
    for term in terms:
        if re.search(r"\w", term, re.UNICODE):
            word_like_terms.append(re.escape(term))
        else:
            symbol_only_terms.append(re.escape(term))

    pattern_parts: list[str] = []
    if word_like_terms:
        pattern_parts.append(
            r"(?<!\w)(?:" + "|".join(word_like_terms) + r")(?!\w)"
        )
    if symbol_only_terms:
        pattern_parts.append(r"(?:" + "|".join(symbol_only_terms) + r")")

    if not pattern_parts:
        return None

    return re.compile(
        "|".join(pattern_parts),
        re.IGNORECASE | re.UNICODE,
    )


# ---------------------------------------------------------------------------
# Word-list patterns (loaded from JSON resources)
# ---------------------------------------------------------------------------

_ALL_BAD_WORDS: list[str] = _load_terms_from_json("bad_words.json")
_BAD_WORDS_PATTERN: re.Pattern | None = _build_word_boundary_pattern(_ALL_BAD_WORDS)

_ALL_SPAM_PHRASES: list[str] = _load_terms_from_json("spam_phrases.json")
_SPAM_PHRASES_PATTERN: re.Pattern | None = _build_word_boundary_pattern(_ALL_SPAM_PHRASES)


# ---------------------------------------------------------------------------
# URL patterns
# ---------------------------------------------------------------------------

_COMMON_TLDS = (
    "app", "biz", "co", "com", "dev", "info", "io", "link", "me", "net",
    "online", "org", "shop", "store", "xyz",
)

_URL_PATTERNS = (
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"www\.", re.IGNORECASE),
    # Bare domain names like "example.com"
    re.compile(
        rf"\b[a-z0-9](?:[a-z0-9-]{{0,61}}[a-z0-9])?\.(?:{'|'.join(_COMMON_TLDS)})\b",
        re.IGNORECASE,
    ),
)


# ---------------------------------------------------------------------------
# Social-media account patterns
# ---------------------------------------------------------------------------
#
# These patterns catch @username handles, direct social-media profile links,
# and WhatsApp-style phone numbers – all common spam vectors.

_SOCIAL_MEDIA_PATTERNS = (
    # @username handles (e.g. @myshop or @my.shop123)
    re.compile(r"@[a-z0-9][a-z0-9._]{2,}", re.IGNORECASE),
    # Profile links on major platforms, with a /username path
    re.compile(
        r"\b(?:instagram|facebook|fb|whatsapp|wa|telegram|tiktok|snapchat|twitter|youtube)"
        r"(?:\.(?:com|me|net))?/\S+",
        re.IGNORECASE,
    ),
    # WhatsApp / international phone numbers: + followed by 10–16 actual digits
    # The lookahead counts only digit characters so spaces and punctuation used
    # as separators don't inflate the digit tally.
    re.compile(r"\+(?=(?:[\s().-]*\d){10,16}(?![\d\s().-]*\d))[\d\s().-]*\d"),
)


# ---------------------------------------------------------------------------
# Junk-text patterns
# ---------------------------------------------------------------------------
#
# These catch text that would almost never appear in a legitimate book title
# or description: runs of repeated characters and emoji floods.

# Unicode ranges that cover the vast majority of emoji characters.
# Uses three well-defined blocks; kept separate to avoid over-large combined ranges.
_EMOJI_RE = re.compile(
    "(?:"
    "[\U0001F300-\U0001F9FF]"  # Misc Symbols, Pictographs, Emoticons, Transport
    "|[\U0001FA00-\U0001FAFF]"  # Chess Symbols / Extended Symbols and Pictographs
    "|[\U00002600-\U000027BF]"  # Misc Symbols / Dingbats
    ")",
    re.UNICODE,
)

_EMOJI_THRESHOLD = 3  # flag if 3 or more emoji characters appear

_JUNK_PATTERNS = (
    # 5+ identical non-whitespace characters in a row: "looooool", "!!!!!!", "aaaaaaa"
    re.compile(r"(\S)\1{4,}", re.UNICODE),
)


def _is_junk_text(text: str) -> bool:
    """Return True if the text looks like junk (spam obfuscation, emoji flood, etc.)."""
    if not text:
        return False
    if any(pattern.search(text) for pattern in _JUNK_PATTERNS):
        return True
    if len(_EMOJI_RE.findall(text)) >= _EMOJI_THRESHOLD:
        return True
    return False


# ---------------------------------------------------------------------------
# Core detection
# ---------------------------------------------------------------------------

_ITEM_CHECK_ORDER = ("title", "author", "description")


def _field_matches_auto_moderation(text: str) -> bool:
    """Return True if ``text`` triggers any auto-moderation rule."""
    if not text:
        return False

    # Junk-text check
    if _is_junk_text(text):
        return True

    # URL / bare-domain check
    if any(pattern.search(text) for pattern in _URL_PATTERNS):
        return True

    # Social-media account / handle check
    if any(pattern.search(text) for pattern in _SOCIAL_MEDIA_PATTERNS):
        return True

    # Bad-words check (multilingual word list)
    if _BAD_WORDS_PATTERN and _BAD_WORDS_PATTERN.search(text):
        return True

    # Spam-phrase check (multilingual phrase list)
    if _SPAM_PHRASES_PATTERN and _SPAM_PHRASES_PATTERN.search(text):
        return True

    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def auto_moderate_fields(
    *,
    values: Mapping[str, str | None],
    check_order: Sequence[str] | None = None,
) -> dict:
    """Return an auto-moderation verdict for arbitrary named text fields.

    ``values`` maps field names to their text content.
    ``check_order`` controls which field names are checked and in what order
    they appear in ``flagged_fields``.

    The optional Django setting ``ITEM_AUTOMODERATION_STUB_FLAGGED_FIELDS``
    (a list of field names) can be used to force flagged fields, which is useful
    for tests and manual verification of the moderation UI flow.
    """
    normalized_values = {field: (text or "") for field, text in values.items()}
    if check_order is None:
        normalized_check_order = tuple(normalized_values.keys())
    else:
        deduped_fields = dict.fromkeys(
            field for field in check_order if field in normalized_values
        )
        normalized_check_order = tuple(deduped_fields)

    configured_fields = getattr(settings, "ITEM_AUTOMODERATION_STUB_FLAGGED_FIELDS", [])
    if isinstance(configured_fields, str):
        configured_fields = [configured_fields]
    elif not configured_fields:
        configured_fields = []

    forced_fields = set(configured_fields) & set(normalized_check_order)
    flagged_fields = [
        field
        for field in normalized_check_order
        if field in forced_fields or _field_matches_auto_moderation(normalized_values[field])
    ]

    return {
        "has_bad_language": bool(flagged_fields),
        "flagged_fields": flagged_fields,
    }


def auto_moderate_item(*, title: str, author: str, description: str) -> dict:
    """Return an auto-moderation verdict for item text content."""
    return auto_moderate_fields(
        values={
            "title": title,
            "author": author,
            "description": description,
        },
        check_order=_ITEM_CHECK_ORDER,
    )
