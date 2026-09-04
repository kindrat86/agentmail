#!/usr/bin/env python3
"""Fail the build when a page ships a title or meta description Google will cut.

Runs in the Docker build alongside validate_jsonld.py, for the same reason that
one exists: four separate generators independently grew the same slicing bug,
and a crawl found 337 of 561 live pages carrying an over-length description
before anyone noticed. A generator added next week will hit this on its first
build instead of on the next audit.

Limits live in scripts/_meta.py so the generators aim at the same numbers this
enforces. Titles are checked at a looser limit than descriptions: a long title
is truncated in the SERP, while a long description is usually a sign the text
was sliced mid-word.

Usage:  python3 scripts/check_meta_lengths.py [root]
"""
import html
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _meta import DESC_MAX, TITLE_MAX  # noqa: E402

TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
DESC_RE = re.compile(
    r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', re.S | re.I
)

# Directories that are not served as pages, plus the API's own vendored copies.
SKIP_DIRS = {
    ".git", ".venv", "node_modules", "__pycache__", "dist", ".vercel",
    "sanctions_mcp.egg-info", "email_templates", "benchmarks",
}


def text_of(raw):
    return " ".join(html.unescape(raw or "").split())


def main(root="."):
    over_title, over_desc, scanned = [], [], 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith(".html"):
                continue
            fp = os.path.join(dirpath, fn)
            try:
                with open(fp, "r", encoding="utf-8") as fh:
                    raw = fh.read()
            except (OSError, UnicodeDecodeError):
                continue
            scanned += 1
            rel = os.path.relpath(fp, root)
            m = TITLE_RE.search(raw)
            if m:
                t = text_of(m.group(1))
                if len(t) > TITLE_MAX:
                    over_title.append((len(t), rel, t))
            m = DESC_RE.search(raw)
            if m:
                d = text_of(m.group(1))
                if len(d) > DESC_MAX:
                    over_desc.append((len(d), rel, d))

    print(f"[check_meta_lengths] scanned {scanned} HTML file(s) in {root}")
    for label, rows, limit in (
        ("description", over_desc, DESC_MAX),
        ("title", over_title, TITLE_MAX),
    ):
        if rows:
            print(f"\n[check_meta_lengths] {len(rows)} {label}(s) over {limit} chars:")
            for n, rel, val in sorted(rows, reverse=True)[:20]:
                print(f"  {n:4d}  {rel}")
                print(f"        {val[:110]}…")
            if len(rows) > 20:
                print(f"  … and {len(rows) - 20} more")

    if over_desc or over_title:
        print(
            "\n[check_meta_lengths] FAIL — clip these in the generator, not the "
            "output. scripts/_meta.py has clip_desc() and clip_title()."
        )
        return 1
    print("[check_meta_lengths] OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
