"""OTP / verification-code extraction from email bodies."""
from __future__ import annotations
import re

# ordered by specificity
PATTERNS = [
    r"(?:verification|verify|access|security|login|auth|one[- ]time)[^0-9]{0,20}(\d{4,8})",
    r"(?:code|pin|otp)[^0-9]{0,20}(\d{4,8})",
    r"\b(\d{6})\b",
    r"\b(\d{4,8})\b",
]
COMPILED = [re.compile(p, re.I) for p in PATTERNS]

# also catch "magic link" verification URLs
LINK_RE = re.compile(r"https?://[^\s\"'<>]+(?:verify|confirm|activate|token|code)[^\s\"'<>]*", re.I)


def extract_code(text: str) -> str | None:
    if not text:
        return None
    for rx in COMPILED:
        m = rx.search(text)
        if m:
            return m.group(1)
    return None


def extract_link(text: str) -> str | None:
    if not text:
        return None
    m = LINK_RE.search(text)
    return m.group(0).rstrip(".,);") if m else None


def analyze(text: str) -> dict:
    return {"code": extract_code(text), "link": extract_link(text)}
