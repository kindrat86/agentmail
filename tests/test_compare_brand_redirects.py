"""Regression spec for the /compare/* -> /vs/* brand consolidation (2026-09-09).

The /compare/* family rendered the stale pre-rebrand brand ("agentmail vs X")
while the parallel /vs/* family correctly says "SanctionsAI vs X". Fix: 301
every /compare page (14 detail + hub) to its 1:1 /vs twin, drop them from the
sitemap, and stop emitting internal links to /compare. These tests parse
api.py and the static tree directly, so they run without a live server.
"""
from __future__ import annotations

import ast
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).parents[1]
API = ROOT / "api.py"
SRC = API.read_text(encoding="utf-8")

EXPECTED_REDIRECTS = {
    "/compare/chainalysis": "/vs/chainalysis",
    "/compare/elliptic": "/vs/elliptic",
    "/compare/complyadvantage": "/vs/comply-advantage",
    "/compare/amlbot": "/vs/amlbot",
    "/compare/blockdaemon": "/vs/blockdaemon",
    "/compare/charmverse": "/vs/charmverse",
    "/compare/ciphertrace": "/vs/ciphertrace",
    "/compare/dow-jones-risk": "/vs/dow-jones-rdc",
    "/compare/identitymind": "/vs/identitymind",
    "/compare/notabene": "/vs/notabene",
    "/compare/scorechain": "/vs/scorechain",
    "/compare/sumsub": "/vs/sumsub",
    "/compare/trm-labs": "/vs/trm-labs",
    "/compare/world-check": "/vs/world-check",
    "/compare": "/vs",
}


def _redirects_literal() -> dict:
    tree = ast.parse(SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "HALLUCINATED_REDIRECTS":
            return ast.literal_eval(node.value)
    raise AssertionError("HALLUCINATED_REDIRECTS not found")


class TestCompareRedirects(unittest.TestCase):
    def test_every_compare_page_301s_to_its_vs_twin(self):
        reds = _redirects_literal()
        for src_path, target in EXPECTED_REDIRECTS.items():
            self.assertEqual(reds.get(src_path), target, f"{src_path} must 301 to {target}")

    def test_redirect_targets_exist_as_static_vs_pages(self):
        for target in set(EXPECTED_REDIRECTS.values()):
            if target == "/vs":
                continue
            self.assertTrue((ROOT / target.lstrip("/") / "index.html").is_file(),
                            f"{target} must exist as a static page")

    def test_no_compare_urls_left_in_sitemap_rows(self):
        rows = re.findall(r'\("/compare[^"]*",\s*"[^"]*",\s*"[^"]*",\s*"[^"]*"\)', SRC)
        self.assertEqual(rows, [], f"sitemap still lists /compare URLs: {rows}")

    def test_no_internal_links_point_at_compare(self):
        links = re.findall(r'href="/compare(/[a-z0-9-]+)?"', SRC)
        self.assertEqual(links, [], f"api.py still links to /compare: {links}")

    def test_footer_signoff_uses_public_brand(self):
        m = re.search(r"_FOOTER = '(.*?)</footer>'", SRC, re.S)
        assert m is not None, "_FOOTER not found"
        signoff = m.group(1)[-260:]
        self.assertIn(">SanctionsAI - OFAC sanctions screening", signoff)
        self.assertNotIn(">agentmail - OFAC sanctions screening", signoff)

    def test_vs_hub_cards_link_to_vs_pages(self):
        # _vs_index_page must emit href="/vs/{slug}", not /compare/{slug}
        m = re.search(r"def _vs_index_page.*?return self\._page", SRC, re.S)
        assert m is not None, "_vs_index_page not found"
        self.assertNotIn('href="/compare/{slug}"', m.group(0))
        self.assertIn('href="/vs/{slug}"', m.group(0))

    def test_static_tree_has_no_live_compare_links(self):
        offenders = []
        skip_names = {".bak", ".prebrunson", "-soft404-consolidation"}
        for p in ROOT.rglob("index.html"):
            rel = str(p.relative_to(ROOT))
            if any(s in p.name for s in skip_names) or "/.git/" in rel:
                continue
            for m in re.finditer(r'href="/compare(/[a-z0-9-]+)?"', p.read_text(encoding="utf-8", errors="ignore")):
                offenders.append(f"{rel}: {m.group(0)}")
        self.assertEqual(offenders, [], f"static pages still link /compare: {offenders}")


if __name__ == "__main__":
    unittest.main()
