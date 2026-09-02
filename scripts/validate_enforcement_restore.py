#!/usr/bin/env python3
"""Fail-closed preflight for restoring the SanctionsAI /enforcement family.

This validator is intentionally independent of the retired generator. Run it against
artifacts exported from the last known-good enforcement tree before any merge or deploy:

    python3 scripts/validate_enforcement_restore.py \
      --data /tmp/restore/data/ofac-enforcement.json \
      --meta /tmp/restore/data/ofac-enforcement.meta.json \
      --urls /tmp/restore/enforcement/urls.txt \
      --pages-root /tmp/restore

The concentration gate implements organic master-prompt guardrail 5.2 for the
published top-level numeric metrics. A failure blocks publication even when the
underlying values may be legitimate. Review and repair the publication design rather
than weakening this gate.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

MAX_MODE_SHARE = 0.20
MIN_BODY_CHARS = 1_000
EXPECTED_BRAND = "SanctionsAI"
METRIC_FIELDS = ("actions", "amountUSD")


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hidden_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "template"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "template"} and self.hidden_depth:
            self.hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
            self.parts.append(data)

    @property
    def text(self) -> str:
        return " ".join(" ".join(self.parts).split())


def artifact_path(root: Path, url: str) -> Path:
    relative = url.strip("/")
    return root / relative / "index.html"


def mode_result(rows: list[dict], field: str) -> tuple[object, int, float]:
    values = [row.get(field) for row in rows]
    value, count = collections.Counter(values).most_common(1)[0]
    return value, count, count / len(values)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--meta", required=True, type=Path)
    parser.add_argument("--urls", required=True, type=Path)
    parser.add_argument("--pages-root", required=True, type=Path)
    args = parser.parse_args()

    rows = json.loads(args.data.read_text(encoding="utf-8"))
    meta = json.loads(args.meta.read_text(encoding="utf-8"))
    urls = [line.strip() for line in args.urls.read_text(encoding="utf-8").splitlines() if line.strip()]
    failures: list[str] = []

    if not isinstance(rows, list) or not rows:
        failures.append("dataset is not a non-empty list")
        rows = []

    if rows:
        declared = meta.get("counts", {}).get("actions")
        if declared != len(rows):
            failures.append(f"metadata actions={declared!r}, rows={len(rows)}")

        for field in METRIC_FIELDS:
            mode, count, share = mode_result(rows, field)
            status = "PASS" if share <= MAX_MODE_SHARE else "FAIL"
            print(
                f"5.2 metric={field} mode={mode!r} count={count}/{len(rows)} "
                f"share={share:.3%} limit={MAX_MODE_SHARE:.0%} {status}"
            )
            if share > MAX_MODE_SHARE:
                failures.append(f"5.2 concentration: {field}={mode!r} occupies {share:.3%} of records")

        missing_sources = [i for i, row in enumerate(rows) if not row.get("sourceUrl")]
        invalid_sources = [
            i
            for i, row in enumerate(rows)
            if row.get("sourceUrl")
            and (urlparse(str(row["sourceUrl"])).scheme != "https" or not urlparse(str(row["sourceUrl"])).netloc)
        ]
        if missing_sources:
            failures.append(f"{len(missing_sources)} records lack sourceUrl")
        if invalid_sources:
            failures.append(f"{len(invalid_sources)} records have invalid sourceUrl")

    duplicates = len(urls) - len(set(urls))
    if duplicates:
        failures.append(f"URL manifest has {duplicates} duplicates")

    missing_pages = 0
    missing_h1 = 0
    short_body = 0
    wrong_brand = 0
    bad_jsonld = 0
    for url in urls:
        page_path = artifact_path(args.pages_root, url)
        if not page_path.is_file():
            missing_pages += 1
            continue
        html = page_path.read_text(encoding="utf-8")
        if EXPECTED_BRAND not in html:
            wrong_brand += 1
        if not re.search(r"<h1(?:\s[^>]*)?>\s*.+?\s*</h1>", html, flags=re.IGNORECASE | re.DOTALL):
            missing_h1 += 1
        text_parser = VisibleTextParser()
        text_parser.feed(html)
        if len(text_parser.text) < MIN_BODY_CHARS:
            short_body += 1
        for block in re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            try:
                json.loads(block)
            except json.JSONDecodeError:
                bad_jsonld += 1

    if missing_pages:
        failures.append(f"{missing_pages} URLs have no HTML artifact")
    if missing_h1:
        failures.append(f"{missing_h1} pages lack a real h1")
    if short_body:
        failures.append(f"{short_body} pages have under {MIN_BODY_CHARS} visible-text chars")
    if wrong_brand:
        failures.append(f"{wrong_brand} pages do not contain exact brand {EXPECTED_BRAND!r}")
    if bad_jsonld:
        failures.append(f"{bad_jsonld} JSON-LD blocks do not parse")

    print(
        f"artifacts rows={len(rows)} urls={len(urls)} missing_pages={missing_pages} "
        f"missing_h1={missing_h1} short_body={short_body} wrong_brand={wrong_brand} "
        f"bad_jsonld={bad_jsonld}"
    )
    if failures:
        print("BLOCKED")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
