"""TDD spec for the /data/ofac-sdn-list/ landing page (2026-08-31).

The page upgrades the old 301-to-glossary redirect into a real 200 landing
page: official OFAC search/download guidance, honest limitations, no mirrored
dataset, no fake search, disclaimer, schema, sitemap + pinned lastmod.
These tests parse the static HTML file and the api.py wiring directly, so
they run without a live server.
"""
from __future__ import annotations

import ast
import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).parents[1]
PAGE = ROOT / "data" / "ofac-sdn-list" / "index.html"
API = ROOT / "api.py"
CANONICAL = "https://sanctionsai.dev/data/ofac-sdn-list/"


def _page_text() -> str:
    return PAGE.read_text(encoding="utf-8")


def _api_source() -> str:
    return API.read_text(encoding="utf-8")


def _local_dict_keys(source: str, name: str) -> set[str]:
    """String keys of every local dict assigned to `name` anywhere in the module."""
    keys: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    value = node.value
                    if isinstance(value, ast.Dict):
                        for key in value.keys:
                            if isinstance(key, ast.Constant):
                                keys.add(str(key.value))
    return keys


class PageFileTest(unittest.TestCase):
    def test_page_file_exists(self) -> None:
        self.assertTrue(PAGE.is_file(), f"missing landing page: {PAGE}")


class PageMetaTest(unittest.TestCase):
    def test_canonical_and_title(self) -> None:
        page = _page_text()
        self.assertIn(CANONICAL, page)
        self.assertIn('rel="canonical"', page)
        self.assertRegex(page, r"<title>[^<]*OFAC SDN List[^<]*</title>")
        self.assertRegex(page, r'<meta name="description" content="[^"]{50,}"')

    def test_no_em_dash(self) -> None:
        self.assertNotIn("\u2014", _page_text(), "em dash found in page content")


class OfficialSourcesTest(unittest.TestCase):
    def test_links_official_ofac_resources(self) -> None:
        page = _page_text()
        for url in (
            "https://sanctionslist.ofac.treas.gov/Home/SdnList",
            "https://ofac.treasury.gov/sanctions-list-service",
            "https://ofac.treasury.gov/sanctions-list-search-tool",
            "https://ofac.treasury.gov/recent-actions",
        ):
            self.assertIn(url, page, f"missing official OFAC link: {url}")

    def test_names_official_file_formats(self) -> None:
        page = _page_text()
        for fmt in ("SDN.XML", "SDN.CSV", "fixed-width", "Advanced", "Enhanced"):
            self.assertIn(fmt, page, f"missing SDN file format mention: {fmt}")


class HonestyTest(unittest.TestCase):
    def test_disclaims_mirroring_and_on_site_search(self) -> None:
        page = _page_text().lower()
        self.assertIn("does not mirror", page)
        self.assertIn("no on-site search", page)

    def test_disclaimer_not_legal_advice(self) -> None:
        page = _page_text().lower()
        self.assertIn("not legal advice", page)
        self.assertIn("not a compliance program", page)

    def test_declares_review_date_not_live_data(self) -> None:
        page = _page_text()
        self.assertIn("2026-08-31", page)
        self.assertIn("last reviewed", page.lower())

    def test_search_cta_points_to_real_existing_flow(self) -> None:
        page = _page_text()
        self.assertIn('href="/tools/name-checker"', page)
        # The CTA target must be a real route in api.py.
        self.assertIn('"/tools/name-checker"', _api_source())

    def test_internal_links(self) -> None:
        page = _page_text()
        for link in (
            "/glossary/ofac-sdn-list",
            "/sanctions-lists/ofac-sdn",
            "/data/ofac-crypto-wallets/",
            "/data/",
        ):
            self.assertIn(f'href="{link}"', page, f"missing internal link: {link}")


class SchemaTest(unittest.TestCase):
    def test_json_ld_blocks_parse_and_cover_required_types(self) -> None:
        page = _page_text()
        blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', page, re.S
        )
        self.assertGreaterEqual(len(blocks), 1, "no JSON-LD blocks found")
        types: set[str] = set()
        for block in blocks:
            parsed = json.loads(block)  # raises on broken/unclosed script
            types.add(parsed.get("@type", ""))
        self.assertIn("WebPage", types)
        self.assertIn("FAQPage", types)
        self.assertIn("BreadcrumbList", types)

    def test_faq_questions_nonempty(self) -> None:
        page = _page_text()
        blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', page, re.S
        )
        faq = next(json.loads(b) for b in blocks
                   if json.loads(b).get("@type") == "FAQPage")
        questions = [q["name"] for q in faq["mainEntity"]]
        self.assertGreaterEqual(len(questions), 3)
        for question in questions:
            self.assertTrue(question.strip())


class ApiWiringTest(unittest.TestCase):
    def test_old_redirect_removed(self) -> None:
        keys = _local_dict_keys(_api_source(), "HALLUCINATED_REDIRECTS")
        self.assertNotIn("/data/ofac-sdn-list", keys)

    def test_url_lastmod_pinned(self) -> None:
        source = _api_source()
        keys = _local_dict_keys(source, "URL_LASTMOD")
        self.assertIn("/data/ofac-sdn-list/", keys)
        self.assertIn(
            '"/data/ofac-sdn-list/": "2026-08-31"', source,
            "lastmod pin must be a durable literal date, not computed",
        )

    def test_sitemap_tuple_present(self) -> None:
        source = _api_source()
        self.assertRegex(
            source,
            r'\("/data/ofac-sdn-list/",\s*"weekly",\s*"0\.9",\s*"[^"]+"\)',
        )


if __name__ == "__main__":
    unittest.main()
