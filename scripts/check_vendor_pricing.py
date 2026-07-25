#!/usr/bin/env python3
"""Re-verify every competitor pricing claim in the /cost-of/ cluster.

The cluster exists because vendor-pricing queries are the only shape this domain
currently ranks for. That makes it the worst possible place to be wrong, and it
already was: the pages this replaced carried invented ranges, including
"~$20K-$40K/yr (est.)" for ComplyAdvantage, whose entry plan is published at
$99/month. Roughly twenty times over, on the page a buyer was most likely to
read before choosing between them and us.

So the claims are data in build_cost_of.py, and this checks them against the
source. For each vendor it fetches the evidence URL and compares reality to what
we assert:

  * marked quote-only, but the page now shows prices   -> FAIL (we are stale)
  * marked published, but no figure is on the page     -> FAIL (we are stale)
  * a published figure we quote is no longer on it     -> FAIL (we are stale)
  * unreachable (403/timeout/bot-wall)                 -> WARN, never a pass

Run it before shipping a change to the cluster, and on a schedule — a price is
perishable and a page that prints "Checked <date>" is making a promise about how
recently someone looked.

    python3 scripts/check_vendor_pricing.py          # exit 1 on any FAIL
    python3 scripts/check_vendor_pricing.py -v       # show what was found

Stdlib + curl only, same as everything else in this repo.
"""
import html
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_cost_of import CHECKED, VENDORS  # noqa: E402

UA = "Mozilla/5.0 (compatible; sanctionsai-pricing-check/1.0)"
MONEY = re.compile(r"[$€£]\s?\d[\d,]*(?:\.\d{2})?")

# Figures that are not prices: phone numbers, years, stat callouts on a
# marketing homepage ("$23B traced"). Only applied to the has-any-price test,
# never to the does-our-quoted-figure-still-appear test.
NOISE = re.compile(r"^[$€£]\s?\d{1,3}$")


def fetch(url):
    r = subprocess.run(
        ["curl", "-sL", "--max-time", "40", "-A", UA, "-w", "\n%{http_code}", url],
        capture_output=True)
    body, _, code = r.stdout.decode("utf-8", "replace").rpartition("\n")
    text = re.sub(r"<(script|style)\b.*?</\1>", " ", body, flags=re.S | re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return code.strip(), re.sub(r"\s+", " ", text)


def quoted_figures(v):
    """Every money string this repo prints as a fact about the vendor."""
    out = set()
    pub = v.get("published")
    if pub:
        for _, price in pub["plans"]:
            out.update(MONEY.findall(price))
    return out


def main():
    verbose = "-v" in sys.argv
    fails, warns = [], []
    print("verifying %d vendors (pages claim they were checked %s)\n"
          % (len(VENDORS), CHECKED))

    for v in VENDORS:
        name, url = v["name"], v["evidence"]
        code, text = fetch(url)
        found = {m for m in MONEY.findall(text) if not NOISE.match(m)}
        publishes = bool(v.get("published"))

        if code != "200":
            warns.append("%s: HTTP %s from %s — could not verify" % (name, code, url))
            print("  WARN %-18s HTTP %s" % (name, code))
            continue

        if publishes:
            want = quoted_figures(v)
            # Figures the vendor renders client-side are invisible to curl.
            # Warn so they still get re-read by hand, but do not fail a claim
            # that is true and simply not in the HTML we can fetch.
            js_only = set(v["published"].get("js_only", []))
            for f in sorted(js_only):
                warns.append("%s: %s is rendered client-side — re-verify in a browser"
                             % (name, f))
            want -= js_only
            missing = {f for f in want if f not in text}
            if missing:
                fails.append("%s: we publish %s but the page no longer shows %s"
                             % (name, sorted(want), sorted(missing)))
                print("  FAIL %-18s missing from source: %s" % (name, sorted(missing)))
            else:
                print("  ok   %-18s all %d quoted figures still on the page"
                      % (name, len(want)))
        else:
            # A vendor we call quote-only that has started publishing is the
            # failure that matters most: it means the page is telling a buyer to
            # go get a quote for something they could have bought self-serve.
            if found:
                fails.append("%s: marked quote-only but %s now shows %s"
                             % (name, url, sorted(found)[:6]))
                print("  FAIL %-18s now publishes figures: %s" % (name, sorted(found)[:6]))
            else:
                print("  ok   %-18s still no published figure" % name)
        if verbose and found:
            print("       found on page: %s" % sorted(found)[:12])

    print()
    for w in warns:
        print("WARN  " + w)
    for f in fails:
        print("FAIL  " + f)
    if fails:
        print("\n%d claim(s) no longer match the source. Update VENDORS and CHECKED "
              "in scripts/build_cost_of.py, then re-run it." % len(fails))
        return 1
    print("all verifiable claims match their source"
          + (" (%d unverifiable)" % len(warns) if warns else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
