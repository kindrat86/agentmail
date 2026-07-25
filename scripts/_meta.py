"""Shared title/description length handling for every page generator.

Why this exists as one module rather than a helper per script: a full crawl on
2026-07-26 found 337 of 561 live pages carrying a meta description over 165
characters — 257 of them from a single generator — and 179 carrying a title
over 65. Every generator had grown its own copy of the same slicing bug, so
fixing one fixed one. The matching gate is scripts/check_meta_lengths.py, which
runs in the Docker build; keep the limits here and there in agreement.

Truncation is on a word boundary. A mid-word slice is what produced live
descriptions ending "...depending on seats and volu".
"""

# Google renders roughly 155-160 characters of a description and roughly 60 of
# a title on desktop. The gate allows a little more than these so that a page
# that just misses is not a build failure; these are what the generators aim at.
DESC_TARGET = 157
TITLE_TARGET = 60

# Hard limits enforced by scripts/check_meta_lengths.py.
DESC_MAX = 165
TITLE_MAX = 70


def clip(text, limit):
    """Collapse whitespace and trim to `limit` on a word boundary."""
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:—–-")
    # A single word longer than the limit has no boundary to fall back on.
    return (cut or text[:limit].rstrip()) + "…"


def clip_desc(text):
    return clip(text, DESC_TARGET)


def clip_title(text, suffix=""):
    """Trim a title, preserving a trailing brand/section suffix if one is given.

    Passing the suffix separately matters: clipping
    "Alpha Pharmaceutical, Inc.; ICN Farmaceutica… OFAC Penalty — $198,711.73"
    from the right throws away the penalty amount, which is the part a searcher
    is looking for. The subject gets shortened instead and the suffix survives.
    """
    text = " ".join(str(text or "").split())
    suffix = " ".join(str(suffix or "").split())
    if not suffix:
        return clip(text, TITLE_TARGET)
    room = TITLE_TARGET - len(suffix) - 3  # 3 for the " — " join
    if room < 12:  # suffix alone is already long; nothing sensible to preserve
        return clip(f"{text} — {suffix}" if text else suffix, TITLE_TARGET)
    return f"{clip(text, room)} — {suffix}"
