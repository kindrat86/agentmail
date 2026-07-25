#!/usr/bin/env python3
"""Guard: the OFAC penalty figures must be right, everywhere, all at once.

Twice now this site has shipped the wrong number for the statutory penalty
maximum — and both times it shipped *several* wrong numbers simultaneously, in
copy that was written months apart and never cross-checked. At the last count
the same statutory ceiling appeared as eight different values across the site.

That is uniquely damaging here. The audience is developers who verify claims;
the product is a compliance tool. A reader who checks the primary source and
finds our number wrong has learned something about our data quality, not just
our copywriting.

Run it:  python3 scripts/check_penalty_figures.py
Exit 0 = clean, 1 = a stale figure or floor framing is back.

── Ground truth (both primary sources, re-verify each January) ────────────────

  CIVIL, 50 U.S.C. 1705(b): the greater of $250,000 or twice the transaction
    value. The $250,000 is inflation-adjusted annually. Current adjustment:
    $377,700, Federal Register 2025-00786 (2025-01-15), amending 31 CFR 501.701.
    History: $368,136 (2024), $356,579 (2023), $330,947 (2022).

  CRIMINAL, 50 U.S.C. 1705(c): fined not more than $1,000,000, or if a natural
    person, imprisoned not more than 20 years, or both. NOT inflation-adjusted.

  Both are CEILINGS. "Penalties start at X" inverts the statute — X is the most
  OFAC can impose, not the least. Use "reach" / "up to" / "as much as".

── Annual maintenance ────────────────────────────────────────────────────────

  Each January, check for a new adjustment:

    curl -s "https://www.federalregister.gov/api/v1/documents.json\
?per_page=5&order=newest\
&conditions[term]=%22Inflation+Adjustment+of+Civil+Monetary+Penalties%22\
&conditions[agencies][]=foreign-assets-control-office"

  If a new rule exists, update CIVIL_MAX below, move the old value into
  STALE_CIVIL, and run scripts/check_penalty_figures.py to find every place
  that needs changing.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CIVIL_MAX = "$377,700"
CRIMINAL_MAX = "$1,000,000"
CRIMINAL_YEARS = "20 years"

# Every figure that has stood in for the civil maximum on this site at some
# point. Some were stale adjustments, some were typos of stale adjustments,
# some were invented. All are wrong now.
STALE_CIVIL = [
    r"\$356,000", r"\$356,571", r"\$356,579", r"\$353,634", r"\$358,256",
    r"\$368,000", r"\$368,136", r"\$368,236", r"\$330,944", r"\$330,947",
    r"\$330,000", r"\$300,000", r"\$356K", r"\$330K", r"\$300K",
]

# The criminal maximum has been overstated as $20M / 30 years. These must only
# fire in criminal-penalty context: "$20M" is also a legitimate way to describe
# the largest enforcement action of a given year (see /enforcement/2024), and a
# checker that flags real data is a checker people switch off.
CRIMINAL_CONTEXT = r"(?:criminal|imprison|willful|convict)"
STALE_CRIMINAL = [
    rf"\$20\s?(?:million|M)\b(?=[^.]{{0,120}}{CRIMINAL_CONTEXT})",
    rf"{CRIMINAL_CONTEXT}[^.]{{0,120}}\$20\s?(?:million|M)\b",
    rf"30 years(?=[^.]{{0,120}}{CRIMINAL_CONTEXT})",
    rf"{CRIMINAL_CONTEXT}[^.]{{0,120}}30 years",
]

# A ceiling described as a floor.
FLOOR_FRAMING = [
    r"(?:penalt|fine)\w*\s+(?:can\s+)?starts?\s+at",
    r"starts?\s+at\s+\$377,700",
]

# compliance/osint.py fetches exactly two sources, both OFAC: the
# vile/ofac-sdn-list releases (wallets) and Treasury sdn.csv (names). EU, UN and
# UK consolidated lists are NOT screened. Claiming otherwise on a compliance
# product exposes a customer to the fine we sell against.
#
# This has now slipped through twice in two different phrasings — the slashed
# form "OFAC/EU/UN/UK" and the prose form "OFAC SDN, EU, UN, or UK". The second
# was live inside the wallet checker's clean-result message, i.e. shown at the
# exact moment a user is told their counterparty is safe. Match both shapes.
COVERAGE_CLAIMS = [
    r"OFAC\s*/\s*EU\s*/\s*UN(\s*/\s*UK)?",
    r"OFAC[^.<>\n]{0,24}\b(?:EU|UN|UK)\b[^.<>\n]{0,24}\b(?:and|or)\b\s*(?:the\s+)?\b(?:EU|UN|UK)\b",
]

# Saying "OFAC SDN only, NOT EU, UN or UK" is the correct disclaimer and names
# the same list trio, so the patterns above match it. Flagging honest copy is
# how a gate gets ignored — or worse, how someone "fixes" the true sentence to
# make the gate green. Skip a hit whose immediate context negates it.
# The negation must govern the LIST TRIO, not merely appear in the sentence.
# "Not found on OFAC SDN, EU, UN, or UK" contains "not", but it negates "found"
# — the trio is still the scope being claimed, so that one must still fail.
# Only these shapes actually disclaim the trio:
COVERAGE_NEGATION = re.compile(
    r"only,?\s+not\b"          # "OFAC SDN only, not EU, UN or UK"
    r"|not\s+(?:the\s+)?(?:EU|UN|UK)\b"   # "...not EU, UN or UK lists"
    r"|(?:do|does|will|can)\s+not\s+(?:screen|cover|include|check)"
    r"|\bexclud\w*\s+(?:the\s+)?(?:EU|UN|UK)\b"
    r"|\bnever\s+(?:screen|cover|include|check)"
    r"|\bno\s+(?:EU|UN|UK)\b",
    re.I,
)

# Real enforcement settlements. These are history and must never be rewritten
# by a well-meaning sweep — they are the reason this checker matches on the
# specific stale figures above rather than on "any dollar amount".
PROTECTED = [
    "362,158",      # Kraken 2022
    "98,307",       # BitGo 2021
    "507,375",      # BitPay 2021
    "450,000",      # EtherDelta 2018
    "50,000,000",   # Coinbase 2023
    "968,618,202",  # Binance 2023
]

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".claude", "dist", ".venv"}
EXTS = (".py", ".html", ".md", ".json", ".txt", ".xml")
# Audit reports quote the figures as they stood at the time. That is the record.
# CLAUDE.md states the floor-framing rule, which it can only do by quoting the
# phrase the rule forbids. Scanning it made this checker fail on its own
# documentation, permanently — and a gate that always fails is a gate everyone
# learns to ignore, which is exactly how the figures drifted the first two times.
SKIP_NAMES = {"check_penalty_figures.py", "CLAUDE.md"}
SKIP_PATTERNS = ("AUDIT_", "HERMES_REPORT_", "CHANGELOG")


def _is_disclaimer(src, m):
    """True when the matched trio sits inside an explicit denial of coverage.

    Scoped to the SENTENCE containing the match, not a fixed character window.
    A ±70-char window reaches into neighbouring lines, so one honest disclaimer
    on the next line silently suppressed real claims above it — a false
    negative, which is far worse here than the false positive it was fixing.
    """
    start = max(
        src.rfind(".", 0, m.start()), src.rfind("\n", 0, m.start()),
        src.rfind(">", 0, m.start()), src.rfind("'", 0, m.start()),
    ) + 1
    end = min(
        (p for p in (src.find(".", m.end()), src.find("\n", m.end()),
                     src.find("<", m.end()), src.find("'", m.end()))
         if p != -1),
        default=len(src),
    )
    return bool(COVERAGE_NEGATION.search(src[start:end]))


def files():
    for root, dirs, fs in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in fs:
            if not f.endswith(EXTS) or f in SKIP_NAMES:
                continue
            if any(p in f for p in SKIP_PATTERNS):
                continue
            yield os.path.join(root, f)


def main():
    problems = []
    for path in files():
        try:
            src = open(path, encoding="utf-8").read()
        except (UnicodeDecodeError, OSError):
            continue
        rel = os.path.relpath(path, ROOT)
        for label, pats in (("stale civil figure", STALE_CIVIL),
                            ("overstated criminal penalty", STALE_CRIMINAL),
                            ("ceiling described as a floor", FLOOR_FRAMING),
                            ("claims EU/UN/UK coverage we do not have", COVERAGE_CLAIMS)):
            for pat in pats:
                for m in re.finditer(pat, src, re.I):
                    line = src.count("\n", 0, m.start()) + 1
                    ctx = re.sub(r"\s+", " ", src[max(0, m.start() - 70):m.end() + 70])
                    if pats is COVERAGE_CLAIMS and _is_disclaimer(src, m):
                        continue  # an explicit disclaimer, not a coverage claim
                    problems.append((rel, line, label, m.group(0), ctx))

    if not problems:
        print(f"OK — civil max {CIVIL_MAX}, criminal max {CRIMINAL_MAX} / "
              f"{CRIMINAL_YEARS}, no floor framing.")
        return 0

    print(f"FAIL — {len(problems)} penalty-figure problems:\n")
    for rel, line, label, hit, ctx in problems:
        print(f"  {rel}:{line}  [{label}] {hit}")
        print(f"      …{ctx}…")
    print(f"\nCorrect values: civil {CIVIL_MAX} (50 U.S.C. 1705(b), FR 2025-00786), "
          f"criminal {CRIMINAL_MAX} and {CRIMINAL_YEARS} (50 U.S.C. 1705(c)).")
    print("Both are ceilings — say 'reach' or 'up to', never 'start at'.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
