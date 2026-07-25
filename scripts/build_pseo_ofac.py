#!/usr/bin/env python3
"""Generate three dataset-native pSEO families from OFAC's own SDN export.

    /programs/<code>              one page per OFAC sanctions program code
    /sanctioned-addresses/<chain> one page per chain with SDN-listed addresses
    /designations/<year>          one page per designation year

Everything on these pages is derived from OFAC's ENHANCED_XML export. Nothing is
estimated, inferred or written from memory: counts are counted, dates are the
dates OFAC published, program descriptions are the legal-authority strings OFAC
itself attaches to the designation. That constraint is the point: the /cost-of/
cluster had to be rebuilt once because it shipped invented "(est.)" pricing
ranges, and on a compliance domain those are the pages a reader has no reason to
trust. See scripts/build_cost_of.py and scripts/check_vendor_pricing.py.

Two-stage so the 100 MB source is never committed:

    python3 scripts/build_pseo_ofac.py --fetch    # XML -> data/ofac-pseo.json
    python3 scripts/build_pseo_ofac.py            # JSON -> the three families

The committed intermediate (data/ofac-pseo.json, ~1 MB) makes a rebuild
reproducible without a 100 MB download, and is itself published at
/data/ofac-pseo.json under the same CC BY terms as the other datasets.

Wiring these families into the server needs two edits kept in sync with this
script: the two static-prefix tuples in api.py's do_GET, and the COPY lines in
the Dockerfile. A page that exists on disk but is missing from either is a 404
in production.
"""
import html
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import date

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data", "ofac-pseo.json")
XML_URL = ("https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview"
           "/exports/SDN_ENHANCED.XML")
NS = ("{https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview"
      "/exports/ENHANCED_XML}")
SITE = "https://sanctionsai.dev"

# Minimum size for a page to be worth publishing. A program with two
# designations has nothing on it that the hub table does not already say, and a
# few dozen such pages is how a useful cluster turns into scaled-content abuse.
MIN_PROGRAM_ENTRIES = 5
MIN_CHAIN_ADDRESSES = 3
FIRST_YEAR = 2015

# OFAC's ticker -> the name people actually search for. Ticker only; no claim
# about the asset beyond what OFAC's own feature label says.
CHAINS = {
    "XBT":  ("Bitcoin", "bitcoin", "BTC"),
    "ETH":  ("Ethereum", "ethereum", "ETH"),
    "TRX":  ("Tron", "tron", "TRX"),
    "USDT": ("Tether (USDT)", "tether-usdt", "USDT"),
    "LTC":  ("Litecoin", "litecoin", "LTC"),
    "XMR":  ("Monero", "monero", "XMR"),
    "BCH":  ("Bitcoin Cash", "bitcoin-cash", "BCH"),
    "DASH": ("Dash", "dash", "DASH"),
    "ZEC":  ("Zcash", "zcash", "ZEC"),
    "SOL":  ("Solana", "solana", "SOL"),
    "USDC": ("USD Coin (USDC)", "usd-coin-usdc", "USDC"),
    "DOGE": ("Dogecoin", "dogecoin", "DOGE"),
    "BSC":  ("BNB Smart Chain", "bnb-smart-chain", "BSC"),
    "ARB":  ("Arbitrum", "arbitrum", "ARB"),
    "XRP":  ("XRP Ledger", "xrp-ledger", "XRP"),
    "ETC":  ("Ethereum Classic", "ethereum-classic", "ETC"),
    "BSV":  ("Bitcoin SV", "bitcoin-sv", "BSV"),
    "BTG":  ("Bitcoin Gold", "bitcoin-gold", "BTG"),
    "XVG":  ("Verge", "verge", "XVG"),
}


def slugify(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


def esc(s):
    return html.escape(str(s), quote=True)


# ───────────────────────────────────────────────────────────── stage 1: fetch

def _text(el, tag):
    x = el.find(tag)
    return x.text if x is not None else None


def fetch():
    """Download the enhanced XML and reduce it to the committed intermediate."""
    tmp = os.path.join(HERE, ".sdn_enhanced.xml")
    print("fetching %s ..." % XML_URL, flush=True)
    r = subprocess.run(["curl", "-sL", "--max-time", "600", "-o", tmp, XML_URL])
    if r.returncode != 0 or not os.path.exists(tmp):
        sys.exit("curl failed for the SDN enhanced XML")
    size = os.path.getsize(tmp)
    if size < 10_000_000:
        os.remove(tmp)
        sys.exit("enhanced XML was only %d bytes — refusing to build from a "
                 "truncated download" % size)

    entities, as_of = [], None
    for _, el in ET.iterparse(tmp, events=("end",)):
        if el.tag == NS + "dataAsOf" and as_of is None:
            as_of = (el.text or "")[:10]
        if el.tag != NS + "entity":
            continue
        gi = el.find(NS + "generalInfo")
        d = {"id": el.get("id"),
             "type": (_text(gi, NS + "entityType") if gi is not None else None)}

        sl = el.find(NS + "sanctionsLists")
        d["listed"] = None
        if sl is not None:
            for x in sl.findall(NS + "sanctionsList"):
                d["listed"] = x.get("datePublished")
                break

        sp = el.find(NS + "sanctionsPrograms")
        d["programs"] = ([x.text for x in sp.findall(NS + "sanctionsProgram")]
                         if sp is not None else [])
        la = el.find(NS + "legalAuthorities")
        d["authorities"] = (sorted({x.text for x in la.findall(NS + "legalAuthority")})
                            if la is not None else [])

        name = None
        names = el.find(NS + "names")
        if names is not None:
            for n in names.findall(NS + "name"):
                if (_text(n, NS + "isPrimary") or "") != "true":
                    continue
                for tr in n.iter(NS + "translation"):
                    if (_text(tr, NS + "isPrimary") or "") == "true":
                        name = _text(tr, NS + "formattedFullName")
                        break
                if name:
                    break
        d["name"] = name

        crypto, countries = [], set()
        fs = el.find(NS + "features")
        if fs is not None:
            for f in fs.findall(NS + "feature"):
                ty, val = _text(f, NS + "type") or "", _text(f, NS + "value")
                if not val:
                    continue
                if ty.startswith("Digital Currency Address - "):
                    crypto.append([ty[len("Digital Currency Address - "):], val])
                elif ty in ("Nationality Country", "Citizenship Country"):
                    countries.add(val)
        ads = el.find(NS + "addresses")
        if ads is not None:
            for c in ads.iter(NS + "country"):
                if c.text:
                    countries.add(c.text)
        d["crypto"] = crypto
        d["countries"] = sorted(countries)
        entities.append(d)
        el.clear()

    os.remove(tmp)
    if len(entities) < 15000:
        sys.exit("only %d entities parsed — the export shape probably changed; "
                 "refusing to overwrite the committed dataset" % len(entities))

    payload = {
        "source": ("U.S. Treasury OFAC — Specially Designated Nationals and "
                   "Blocked Persons List (SDN), enhanced XML export"),
        "sourceUrl": XML_URL,
        "officialSearchUrl": "https://sanctionssearch.ofac.treas.gov/",
        "dataAsOf": as_of,
        "retrieved": date.today().isoformat(),
        "license": "Public domain (U.S. Government work). Page text CC BY 4.0.",
        "scope": ("SDN list only. Excludes the OFAC Consolidated (non-SDN) lists, "
                  "the Sectoral Sanctions Identifications list, and EU/UK/UN or "
                  "any other jurisdiction's list. No 50 Percent Rule ownership "
                  "analysis is applied."),
        "entities": entities,
    }
    os.makedirs(os.path.dirname(DATA), exist_ok=True)
    with open(DATA, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, separators=(",", ":"))
    print("wrote %s — %d entities, dataAsOf %s"
          % (DATA, len(entities), as_of), flush=True)


# ───────────────────────────────────────────────────────────── page furniture

# api.py's _shell_static() injects the site design system (_DARK_CSS +
# _STATIC_CSS), the nav and the footer into every static page it serves, AFTER
# this file's <head>. So a stylesheet here does not decorate the page, it
# fights one that wins on order — and any token named --bg or --fg is simply
# overwritten by the design system's, leaving rules that reference it painting
# with the wrong colour. The first cut of these pages shipped its own light
# theme and rendered near-invisible in production for exactly that reason.
#
# So: no tokens, no element selectors, no theme. Use the design system's own
# classes (.stat-grid/.stat-card/.num, .callout, .cta, .related-links,
# .breadcrumb, .disc) and add only what it has no class for, under an sa-
# prefix that cannot collide. Tables are deliberately left unwrapped —
# _wrap_tables() gives each one a scrolling .tbl container, and bails entirely
# if it finds a wrapper already there.
CSS = """.sa-r{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.sa-addr{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.8125rem;word-break:break-all}
.sa-auth{margin:12px 0 0;padding-left:1.1rem}
.sa-auth li{margin:4px 0}
"""

POSTHOG = ('<script>!function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],'
           'e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&'
           '(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice'
           '.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",'
           'p.crossOrigin="anonymous",p.async=!0,p.src=s.api_host.replace('
           '".i.posthog.com","-assets.i.posthog.com")+"/static/array.js",'
           '(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);'
           'var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],'
           'u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),'
           't||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)+'
           '".people (stub)"},o="capture identify alias people.set people.set_once '
           'set_config register register_once unregister opt_out_capturing '
           'has_opted_out_capturing opt_in_capturing reset isFeatureEnabled '
           'onFeatureFlags getFeatureFlag getFeatureFlagPayload reloadFeatureFlags '
           'group updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures '
           'getActiveMatchingSurveys getSurveys".split(" "),n=0;n<o.length;n++)g(u,o[n]);'
           'e._i.push([i,s,a])},e.__SV=!0}(document,window.posthog||[]);'
           'posthog.init("phc_lyZCgvTpicjLzAO3rY2GhxuX5WUc5jQjP8ZVwwJqauX",'
           '{api_host:"https://eu.i.posthog.com",person_profiles:"identified_only"})</script>')


def ldjson(obj):
    return ('<script type="application/ld+json">%s</script>'
            % json.dumps(obj, separators=(",", ":"), ensure_ascii=False))


def crumbs(trail):
    items = [{"@type": "ListItem", "position": 1, "name": "Home",
              "item": SITE + "/"}]
    for i, (name, url) in enumerate(trail, start=2):
        items.append({"@type": "ListItem", "position": i, "name": name,
                      "item": SITE + url})
    return ldjson({"@context": "https://schema.org", "@type": "BreadcrumbList",
                   "itemListElement": items})


def faq_ld(pairs):
    return ldjson({"@context": "https://schema.org", "@type": "FAQPage",
                   "mainEntity": [{"@type": "Question", "name": q,
                                   "acceptedAnswer": {"@type": "Answer", "text": a}}
                                  for q, a in pairs]})


def dataset_ld(name, desc, url, as_of):
    return ldjson({
        "@context": "https://schema.org", "@type": "Dataset",
        "name": name, "description": desc, "url": SITE + url,
        "isBasedOn": XML_URL,
        "creator": {"@type": "GovernmentOrganization",
                    "name": "U.S. Department of the Treasury, Office of Foreign "
                            "Assets Control",
                    "url": "https://ofac.treasury.gov/"},
        "publisher": {"@type": "Organization", "name": "SanctionsAI",
                      "url": SITE},
        "temporalCoverage": as_of, "dateModified": as_of,
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "isAccessibleForFree": True,
    })


def page(title, desc, canonical, body, extra_ld, as_of):
    trail_ld = extra_ld
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{site}{canonical}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:type" content="article">
<meta property="og:url" content="{site}{canonical}">
<meta property="og:image" content="{site}/og.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="robots" content="index, follow, max-image-preview:large">
{ld}
<style>
{css}</style>
{ph}
</head>
<body>
<article>
{body}
<div class="disc">
<p><strong>Source.</strong> Every figure on this page is counted from the U.S. Treasury
OFAC <a href="{xml}">SDN enhanced XML export</a>, published <strong>{as_of}</strong>.
No figure is estimated. The authoritative list is OFAC's own
<a href="https://sanctionssearch.ofac.treas.gov/">Sanctions List Search</a>.</p>
<p><strong>Scope.</strong> SDN list only. This page does not cover the OFAC
Consolidated (non-SDN) lists, the Sectoral Sanctions Identifications list, or the
EU, UK or UN lists, and it does not apply the
<a href="/glossary/ofac-50-percent-rule">50 Percent Rule</a>, under which entities
owned 50% or more by blocked persons are themselves blocked without being listed
by name.</p>
<p><strong>Not legal or compliance advice.</strong> A screening decision requires the
official list and, where the stakes warrant it, counsel.</p>
</div>
<footer>
<p><a href="/">SanctionsAI</a> &middot; <a href="/programs">Sanctions programs</a>
&middot; <a href="/sanctioned-addresses">Sanctioned crypto addresses</a>
&middot; <a href="/designations">Designations by year</a>
&middot; <a href="/glossary">Glossary</a> &middot; <a href="/docs">API docs</a></p>
</footer>
</article>
</body>
</html>
""".format(title=esc(title), desc=esc(desc), canonical=canonical, site=SITE,
           ld=trail_ld, css=CSS, ph=POSTHOG, body=body, as_of=esc(as_of),
           xml=XML_URL)


def stat_grid(pairs):
    # Labels are authored here, not user data, and a couple carry an entity —
    # so they go through unescaped. Values always escape.
    # .num here is the design system's big accent figure, which is what a stat
    # card wants. Table cells use .sa-r instead — .num on a <th> is what turned
    # "ADDRESSES" into a 1.75rem green heading in the first deploy.
    cells = "".join('<div class="stat-card"><div class="num">%s</div>'
                    '<div class="stat-desc">%s</div></div>' % (esc(n), l)
                    for n, l in pairs)
    return '<div class="stat-grid">%s</div>' % cells


def api_block(kind, sample):
    """The screening call for this page's subject, against the live endpoint."""
    if kind == "wallet":
        q, note = ("wallet=" + sample,
                   "checks an address against every digital-currency address on "
                   "the SDN list")
    else:
        q, note = ("name=" + sample.replace(" ", "%20"),
                   "checks a counterparty name against all SDN primary names and "
                   "alternate identities")
    return """<h2>Screen this programmatically</h2>
<p>The same data behind this page is available as a single unauthenticated GET.
It {note}, and returns a match list rather than a yes/no so you can log what
matched and why:</p>
<pre><code>curl "{site}/sanctions?{q}"</code></pre>
<p>The free tier allows 5 checks per day with no signup, which is enough to wire
the call up and see the response shape. Production limits and the audit log are
on the <a href="/pricing">paid tiers</a>; the
<a href="/docs">API reference</a> covers batch screening and the
<code>degraded</code> flag you should alert on.</p>""".format(
        site=SITE, q=q, note=note)


# Which of the three families' URLs actually get a page. Populated in main()
# before anything renders, because pages cross-link to each other and both
# families have a floor: a program below MIN_PROGRAM_ENTRIES and a year before
# FIRST_YEAR are real values in the data with no page behind them. Linking to
# one is a 404 emitted from a page whose whole claim is that it is accurate.
LINKABLE = set()


def linkable(url):
    return url in LINKABLE


def related(links):
    links = [(u, t) for u, t in links
             if not u.startswith(("/programs/", "/sanctioned-addresses/",
                                  "/designations/")) or linkable(u)]
    return ('<div class="related-links"><h3 style="margin-top:0">Related</h3><ul>%s</ul></div>'
            % "".join('<li><a href="%s">%s</a></li>' % (u, esc(t)) for u, t in links))


def program_cell(code):
    """A program code, linked when it has a page and plain text when it does not."""
    url = "/programs/" + slugify(code)
    return ('<a href="%s">%s</a>' % (url, esc(code))) if linkable(url) else esc(code)


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


# ────────────────────────────────────────────────────────── stage 2: generate

def load():
    if not os.path.exists(DATA):
        sys.exit("%s missing — run: python3 scripts/build_pseo_ofac.py --fetch"
                 % DATA)
    return json.load(open(DATA, encoding="utf-8"))


TYPE_LABEL = {"Individual": "individuals", "Entity": "entities",
              "Vessel": "vessels", "Aircraft": "aircraft"}


def authority_sentence(auths):
    """Describe a program using only the legal-authority labels OFAC attaches."""
    if not auths:
        return ""
    if len(auths) == 1:
        return ("Designations under this program are made under %s." % auths[0])
    head = ", ".join(auths[:-1])
    return ("Designations under this program are made under %s and %s."
            % (head, auths[-1]))


def build_programs(entities, as_of, out_root):
    from collections import Counter, defaultdict
    members = defaultdict(list)
    for e in entities:
        for p in e["programs"]:
            members[p].append(e)

    kept = {p: v for p, v in members.items() if len(v) >= MIN_PROGRAM_ENTRIES}
    order = sorted(kept, key=lambda p: -len(kept[p]))
    urls = []

    for code in order:
        rows = kept[code]
        slug = slugify(code)
        url = "/programs/" + slug
        types = Counter(r["type"] for r in rows)
        auths = [a for a, _ in Counter(
            a for r in rows for a in r["authorities"]).most_common()]
        countries = Counter(c for r in rows for c in r["countries"]).most_common(12)
        dated = sorted((r for r in rows if r["listed"]), key=lambda r: r["listed"])
        first, last = (dated[0]["listed"], dated[-1]["listed"]) if dated else ("", "")
        crypto_n = sum(len(r["crypto"]) for r in rows)
        recent = list(reversed(dated[-12:]))
        co_progs = Counter(p for r in rows for p in r["programs"] if p != code)

        title = "OFAC %s Sanctions Program — %d SDN Designations [%s]" % (
            code, len(rows), as_of)
        desc = ("%d entries on the OFAC SDN list carry the %s program code, "
                "counted from Treasury's own export of %s. Breakdown by type, "
                "country and designation date." % (len(rows), code, as_of))

        body = ['<nav class="breadcrumb"><a href="/">Home</a> &rsaquo; '
                '<a href="/programs">Sanctions programs</a> &rsaquo; %s</nav>' % esc(code)]
        body.append("<h1>OFAC %s sanctions program</h1>" % esc(code))
        body.append('<p class="lede">%s is one of the program codes OFAC attaches to '
                    'entries on the Specially Designated Nationals list. As of %s it '
                    'appears on <strong>%s</strong> SDN entries. %s</p>'
                    % (esc(code), esc(as_of), f"{len(rows):,}",
                       esc(authority_sentence(auths[:3]))))

        body.append(stat_grid([
            (f"{len(rows):,}", "SDN entries"),
            (f"{types.get('Individual', 0):,}", "individuals"),
            (f"{types.get('Entity', 0):,}", "entities"),
            (f"{types.get('Vessel', 0) + types.get('Aircraft', 0):,}",
             "vessels &amp; aircraft"),
        ]))

        body.append("<h2>What the %s code means on an SDN entry</h2>" % esc(code))
        body.append("<p>OFAC does not maintain one list per sanctions program. It "
                    "maintains one SDN list, and tags each entry with the program or "
                    "programs it was designated under. An entry can carry several: of "
                    "the %s entries tagged %s, <strong>%s</strong> also carry at least "
                    "one other program code.</p>"
                    % (f"{len(rows):,}", esc(code),
                       f"{sum(1 for r in rows if len(r['programs']) > 1):,}"))
        if auths:
            body.append("<p>The legal authorities OFAC records against these "
                        "designations are:</p><ul>%s</ul>"
                        % "".join("<li>%s</li>" % esc(a) for a in auths[:10]))
        body.append("<p>That matters for screening: if you filter an SDN extract to a "
                    "single program code you will silently drop entries that were "
                    "designated under a different code but are blocked all the same. "
                    "Screen the whole list, then use the program code to explain a hit "
                    "— not to decide which entries to load.</p>")

        body.append("<h2>%s designations by type</h2>" % esc(code))
        rows_html = "".join(
            "<tr><td>%s</td><td class=\"num\">%s</td><td class=\"num\">%s%%</td></tr>"
            % (esc(TYPE_LABEL.get(t, t or "unspecified").capitalize()), f"{n:,}",
               round(100.0 * n / len(rows), 1))
            for t, n in types.most_common())
        body.append('<table><thead><tr><th>Type</th>'
                    '<th class="sa-r">Entries</th><th class="sa-r">Share</th></tr></thead>'
                    '<tbody>%s</tbody></table>' % rows_html)

        if first:
            body.append("<h2>When %s designations were made</h2>" % esc(code))
            years = Counter(r["listed"][:4] for r in dated)
            yr_html = "".join(
                '<tr><td>%s</td><td class="sa-r">%s</td></tr>' % (esc(y), f"{n:,}")
                for y, n in sorted(years.items(), reverse=True)[:10])
            body.append("<p>The earliest entry still carrying this code was published "
                        "<strong>%s</strong>; the most recent was <strong>%s</strong>. "
                        "Designations per year, most recent first:</p>" % (esc(first), esc(last)))
            body.append('<table><thead><tr><th>Year published</th>'
                        '<th class="sa-r">Entries</th></tr></thead><tbody>%s</tbody>'
                        '</table>' % yr_html)

        if countries:
            body.append("<h2>Countries recorded against %s entries</h2>" % esc(code))
            body.append("<p>Counted from the address, nationality and citizenship "
                        "fields on each entry. An entry can record more than one "
                        "country, and many record none, so these do not sum to the "
                        "entry count:</p>")
            c_html = "".join(
                '<tr><td>%s</td><td class="sa-r">%s</td></tr>' % (esc(c), f"{n:,}")
                for c, n in countries)
            body.append('<table><thead><tr><th>Country</th>'
                        '<th class="sa-r">Entries</th></tr></thead><tbody>%s</tbody>'
                        '</table>' % c_html)

        if recent:
            body.append("<h2>Most recent %s designations</h2>" % esc(code))
            r_html = "".join(
                "<tr><td>%s</td><td>%s</td><td>%s</td></tr>"
                % (esc(r["name"] or "—"), esc(r["type"] or "—"), esc(r["listed"]))
                for r in recent)
            body.append('<table><thead><tr><th>Name as published</th>'
                        '<th>Type</th><th>Date published</th></tr></thead><tbody>%s'
                        '</tbody></table>' % r_html)
            body.append("<p>Names are reproduced exactly as OFAC publishes them. OFAC "
                        "also publishes alternate identities (a.k.a. spellings and "
                        "transliterations) for many entries, and a screening system "
                        "that matches only the primary name will miss them.</p>")

        if crypto_n:
            body.append("<h2>Digital-currency addresses under %s</h2>" % esc(code))
            body.append('<p>OFAC publishes <strong>%s</strong> digital-currency '
                        'addresses on entries carrying this program code. Those are '
                        'broken out by chain on the '
                        '<a href="/sanctioned-addresses">sanctioned address pages</a>.'
                        '</p>' % f"{crypto_n:,}")

        body.append(api_block("name", (recent[0]["name"] if recent else "") or "Bank Markazi"))

        faqs = [
            ("What does the OFAC program code %s mean?" % code,
             "%s is a program code OFAC attaches to entries on the Specially "
             "Designated Nationals list. As of %s, %s SDN entries carry it. %s"
             % (code, as_of, f"{len(rows):,}",
                authority_sentence(auths[:3]) or
                "OFAC records the governing authority on each individual entry.")),
            ("How many entries are on the %s sanctions list?" % code,
             "There is no separate %s list. %s SDN entries carry the %s program "
             "code as of %s: %s. Counted from Treasury's SDN enhanced XML export."
             % (code, f"{len(rows):,}", code, as_of,
                ", ".join("%s %s" % (f"{n:,}", TYPE_LABEL.get(t, t or "unspecified"))
                          for t, n in types.most_common()))),
            ("Does screening against %s alone make me compliant?" % code,
             "No. Blocking obligations attach to the whole SDN list, not to one "
             "program, and the 50 Percent Rule extends them to unlisted entities "
             "owned 50% or more by blocked persons. Filtering an extract down to a "
             "single program code drops entries you are still prohibited from "
             "dealing with."),
        ]

        ld = "\n".join([
            crumbs([("Sanctions programs", "/programs"), (code, url)]),
            faq_ld(faqs),
            dataset_ld("OFAC %s program designations" % code,
                       "SDN entries carrying the %s OFAC sanctions program code, "
                       "with type, country and date breakdowns." % code, url, as_of),
        ])

        rel = [("/programs", "All OFAC sanctions programs"),
               ("/sanctioned-addresses", "OFAC-sanctioned crypto addresses by chain")]
        if last:
            rel.append(("/designations/" + last[:4],
                        "OFAC designations in %s" % last[:4]))
        rel += [("/programs/" + slugify(p), "OFAC %s program" % p)
                for p, _ in co_progs.most_common(4)]
        body.append(related(rel))

        body.append("""<div class="cta"><h2>Screening this in an agent or payment flow?</h2>
<p>SanctionsAI is an OFAC screening API built for automated systems: one GET per
counterparty, name and digital-currency address matching against the full SDN
list, and an audit trail of what matched. Free tier, no signup.</p>
<a class="btn" href="/pricing">See pricing</a></div>""")

        write(os.path.join(out_root, "programs", slug, "index.html"),
              page(title, desc, url, "\n".join(body), ld, as_of))
        urls.append((url, code, len(rows), types, last))

    # ── hub
    total = len({id(r) for v in kept.values() for r in v})
    hub_rows = "".join(
        '<tr><td><a href="/programs/%s">%s</a></td><td class="sa-r">%s</td>'
        '<td class="sa-r">%s</td><td class="sa-r">%s</td><td>%s</td></tr>'
        % (slugify(c), esc(c), f"{n:,}", f"{t.get('Individual', 0):,}",
           f"{t.get('Entity', 0):,}", esc(last or "—"))
        for _, c, n, t, last in urls)
    body = ['<nav class="breadcrumb"><a href="/">Home</a> &rsaquo; Sanctions programs</nav>',
            "<h1>OFAC sanctions programs on the SDN list</h1>",
            '<p class="lede">OFAC tags every entry on the Specially Designated '
            'Nationals list with the program it was designated under. This is every '
            'program code with at least %d SDN entries as of %s — %d of them, counted '
            'from Treasury\'s own export.</p>' % (MIN_PROGRAM_ENTRIES, as_of, len(urls)),
            stat_grid([(f"{len(entities):,}", "SDN entries"),
                       (str(len(members)), "program codes"),
                       (str(len(urls)), "profiled here"),
                       (as_of, "list published")]),
            "<h2>Why one entry can carry several codes</h2>",
            "<p>A designation is made under a legal authority — an executive order or "
            "a statute — and one person or company can be designated under more than "
            "one. OFAC records each as a separate program code on the same entry. "
            "There is no separate list per program, which is why screening should run "
            "against the whole SDN list and use the program code afterwards, to "
            "explain a hit rather than to narrow the search.</p>",
            "<h2>Every OFAC program code with %d or more SDN entries</h2>" % MIN_PROGRAM_ENTRIES,
            '<table><thead><tr><th>Program code</th>'
            '<th class="sa-r">Entries</th><th class="sa-r">Individuals</th>'
            '<th class="sa-r">Entities</th><th>Latest designation</th></tr></thead>'
            '<tbody>%s</tbody></table>' % hub_rows,
            related([("/sanctioned-addresses", "OFAC-sanctioned crypto addresses by chain"),
                     ("/designations", "OFAC designations by year"),
                     ("/sanctions-lists/ofac-sdn", "What the OFAC SDN list is"),
                     ("/glossary/ofac-50-percent-rule", "The OFAC 50 Percent Rule"),
                     ("/free/ofac-screening", "Free OFAC screening tool")]),
            api_block("name", "Bank Markazi")]
    ld = "\n".join([
        crumbs([("Sanctions programs", "/programs")]),
        dataset_ld("OFAC sanctions programs on the SDN list",
                   "Every OFAC sanctions program code appearing on the SDN list, "
                   "with entry counts by type and latest designation date.",
                   "/programs", as_of),
        ldjson({"@context": "https://schema.org", "@type": "ItemList",
                "name": "OFAC sanctions programs",
                "numberOfItems": len(urls),
                "itemListElement": [
                    {"@type": "ListItem", "position": i, "name": "OFAC %s" % c,
                     "url": SITE + u}
                    for i, (u, c, _, _, _) in enumerate(urls[:100], start=1)]}),
    ])
    write(os.path.join(out_root, "programs", "index.html"),
          page("OFAC Sanctions Programs — Every SDN Program Code [%s]" % as_of,
               "Every OFAC sanctions program code on the SDN list with real entry "
               "counts, counted from Treasury's export of %s." % as_of,
               "/programs", "\n".join(body), ld, as_of))
    return [u for u, _, _, _, _ in urls]


def build_addresses(entities, as_of, out_root):
    from collections import Counter, defaultdict
    by_chain = defaultdict(list)
    for e in entities:
        for ticker, addr in e["crypto"]:
            by_chain[ticker].append((addr, e))

    kept = {c: v for c, v in by_chain.items() if len(v) >= MIN_CHAIN_ADDRESSES}
    order = sorted(kept, key=lambda c: -len(kept[c]))
    total_addr = sum(len(v) for v in by_chain.values())
    total_ent = len({e["id"] for e in entities if e["crypto"]})
    urls = []

    for ticker in order:
        pairs = kept[ticker]
        name, slug, sym = CHAINS.get(ticker, (ticker, slugify(ticker), ticker))
        url = "/sanctioned-addresses/" + slug
        owners = Counter(e["name"] for _, e in pairs)
        progs = Counter(p for _, e in pairs for p in e["programs"])
        dated = sorted((e["listed"] for _, e in pairs if e["listed"]))
        first, last = (dated[0], dated[-1]) if dated else ("", "")

        title = ("OFAC-Sanctioned %s Addresses — All %d on the SDN List [%s]"
                 % (name, len(pairs), as_of))
        desc = ("Every %s address OFAC publishes on the SDN list — %d addresses "
                "across %d designated persons, with the owner and program for each. "
                "Counted from Treasury's export of %s."
                % (name, len(pairs), len(owners), as_of))

        body = ['<nav class="breadcrumb"><a href="/">Home</a> &rsaquo; '
                '<a href="/sanctioned-addresses">Sanctioned addresses</a> &rsaquo; %s</nav>'
                % esc(name)]
        body.append("<h1>OFAC-sanctioned %s addresses</h1>" % esc(name))
        body.append('<p class="lede">OFAC publishes digital-currency addresses as a '
                    'field on SDN entries, the same way it publishes a passport number '
                    'or a vessel IMO. As of %s the SDN list carries <strong>%s</strong> '
                    '%s (<code>%s</code>) addresses, belonging to <strong>%s</strong> '
                    'designated persons. All of them are below.</p>'
                    % (esc(as_of), f"{len(pairs):,}", esc(name), esc(ticker),
                       f"{len(owners):,}"))

        body.append(stat_grid([
            (f"{len(pairs):,}", "%s addresses" % esc(sym)),
            (f"{len(owners):,}", "designated persons"),
            (esc(first or "—"), "first designated"),
            (esc(last or "—"), "most recent"),
        ]))

        body.append('<div class="callout warn"><strong>Sending to any address below is '
                    'a prohibited transaction for a U.S. person, and a sanctions '
                    'exposure for everyone else.</strong> Strict liability applies: '
                    'intent is not an element of the violation, and neither is knowing '
                    'the address was listed. This page is a reference, not a screening '
                    'control — an address list you copied last month is out of date the '
                    'next time OFAC publishes.</div>')

        body.append("<h2>Why an address list is not a screening control</h2>")
        body.append("<p>OFAC adds and removes addresses without notice, and a "
                    "designated person can move funds to a fresh address at any time. "
                    "There are three specific ways a static copy of this table fails in "
                    "production:</p><ul>"
                    "<li><strong>It goes stale.</strong> The SDN list is republished on "
                    "OFAC's schedule, not yours. The list this page was built from was "
                    "published %s.</li>"
                    "<li><strong>It is chain-scoped.</strong> This page covers %s. A "
                    "product that settles on several chains needs all %s addresses "
                    "across every chain OFAC publishes, not one chain's worth.</li>"
                    "<li><strong>It only catches exact addresses.</strong> The same "
                    "designated persons are also blocked by name, and most sanctions "
                    "exposure arrives as a counterparty name rather than an address "
                    "already on the list.</li></ul>" % (esc(as_of), esc(name), f"{total_addr:,}"))

        body.append("<h2>Who these %s addresses belong to</h2>" % esc(name))
        o_html = "".join(
            '<tr><td>%s</td><td class="sa-r">%s</td><td>%s</td></tr>'
            % (esc(o or "—"), f"{n:,}",
               esc(", ".join(next(e for _, e in pairs if e["name"] == o)["programs"])))
            for o, n in owners.most_common(25))
        body.append('<table><thead><tr><th>Designated person</th>'
                    '<th class="sa-r">%s addresses</th><th>OFAC programs</th></tr></thead>'
                    '<tbody>%s</tbody></table>' % (esc(sym), o_html))

        body.append("<h2>All %s %s addresses on the SDN list</h2>"
                    % (f"{len(pairs):,}", esc(name)))
        body.append("<p>Reproduced exactly as OFAC publishes them, newest designation "
                    "first. The owner column is the primary name on the SDN entry the "
                    "address is attached to.</p>")
        srt = sorted(pairs, key=lambda x: (x[1]["listed"] or "", x[1]["name"] or ""),
                     reverse=True)
        a_html = "".join(
            '<tr><td class="sa-addr">%s</td><td>%s</td><td>%s</td></tr>'
            % (esc(a), esc(e["name"] or "—"), esc(e["listed"] or "—"))
            for a, e in srt)
        body.append('<table><thead><tr><th>%s address</th>'
                    '<th>Designated person</th><th>Date published</th></tr></thead>'
                    '<tbody>%s</tbody></table>' % (esc(sym), a_html))

        if progs:
            body.append("<h2>Programs these addresses were designated under</h2>")
            p_html = "".join(
                '<tr><td>%s</td><td class="sa-r">%s</td></tr>'
                % (program_cell(p), f"{n:,}") for p, n in progs.most_common(10))
            body.append('<table><thead><tr><th>Program</th>'
                        '<th class="sa-r">Addresses</th></tr></thead><tbody>%s</tbody>'
                        '</table>' % p_html)

        body.append(api_block("wallet", srt[0][0]))

        faqs = [
            ("How many %s addresses has OFAC sanctioned?" % name,
             "%s, as of the SDN list published %s. They belong to %s designated "
             "persons. Counted from Treasury's SDN enhanced XML export."
             % (f"{len(pairs):,}", as_of, f"{len(owners):,}")),
            ("Is it illegal to send %s to a sanctioned address?" % sym,
             "For a U.S. person, yes: dealing in the property of a blocked person is "
             "prohibited, and OFAC applies strict liability, so neither intent nor "
             "knowledge that the address was listed is a defence. Non-U.S. persons "
             "can face secondary sanctions exposure. This is not legal advice."),
            ("Where does this list of %s addresses come from?" % name,
             "Directly from OFAC. Digital-currency addresses are published as a field "
             "on SDN entries in Treasury's own export, alongside identifiers like "
             "passport and vessel numbers. Nothing here is added, inferred or "
             "estimated."),
        ]

        ld = "\n".join([
            crumbs([("Sanctioned addresses", "/sanctioned-addresses"), (name, url)]),
            faq_ld(faqs),
            dataset_ld("OFAC-sanctioned %s addresses" % name,
                       "All %d %s addresses published on the OFAC SDN list, with the "
                       "designated person and program for each."
                       % (len(pairs), name), url, as_of),
        ])

        rel = [("/sanctioned-addresses", "All chains OFAC has sanctioned addresses on"),
               ("/free/ofac-screening", "Free OFAC screening tool"),
               ("/tools/wallet-checker", "Wallet checker"),
               ("/glossary/ofac-50-percent-rule", "The OFAC 50 Percent Rule")]
        rel += [("/sanctioned-addresses/" + CHAINS.get(c, (c, slugify(c), c))[1],
                 "OFAC-sanctioned %s addresses" % CHAINS.get(c, (c, "", c))[0])
                for c in order if c != ticker][:4]
        body.append(related(rel))

        body.append("""<div class="cta"><h2>Screen addresses at transaction time, not from a page</h2>
<p>SanctionsAI is an OFAC screening API for automated systems: one GET per address
or counterparty name, matched against the full SDN list rather than a chain-scoped
copy, with an audit trail of what matched. Free tier, no signup.</p>
<a class="btn" href="/pricing">See pricing</a></div>""")

        write(os.path.join(out_root, "sanctioned-addresses", slug, "index.html"),
              page(title, desc, url, "\n".join(body), ld, as_of))
        urls.append((url, name, sym, len(pairs), len(owners)))

    hub_rows = "".join(
        '<tr><td><a href="%s">%s</a></td><td><code>%s</code></td>'
        '<td class="sa-r">%s</td><td class="sa-r">%s</td></tr>'
        % (u, esc(n), esc(s), f"{a:,}", f"{o:,}")
        for u, n, s, a, o in urls)
    tail = [c for c in by_chain if c not in kept]
    body = ['<nav class="breadcrumb"><a href="/">Home</a> &rsaquo; Sanctioned addresses</nav>',
            "<h1>OFAC-sanctioned crypto addresses, by chain</h1>",
            '<p class="lede">OFAC publishes digital-currency addresses as fields on '
            'SDN entries. As of %s there are <strong>%s</strong> of them across '
            '<strong>%d</strong> chains, belonging to <strong>%s</strong> designated '
            'persons. Every address is listed on the chain pages below.</p>'
            % (as_of, f"{total_addr:,}", len(by_chain), f"{total_ent:,}"),
            stat_grid([(f"{total_addr:,}", "addresses"),
                       (str(len(by_chain)), "chains"),
                       (f"{total_ent:,}", "designated persons"),
                       (as_of, "list published")]),
            "<h2>Addresses by chain</h2>",
            '<table><thead><tr><th>Chain</th><th>OFAC ticker</th>'
            '<th class="sa-r">Addresses</th><th class="sa-r">Designated persons</th>'
            '</tr></thead><tbody>%s</tbody></table>' % hub_rows]
    if tail:
        body.append("<p>OFAC also publishes one or two addresses each on %s. Those are "
                    "included in the API's matching set but do not have their own page "
                    "— a page for a single address would say nothing this table does "
                    "not.</p>" % esc(", ".join(
                        CHAINS.get(c, (c, "", c))[0] for c in sorted(tail))))
    body += ["<h2>What a sanctioned address actually obliges you to do</h2>",
             "<p>An address on this list is the property of a blocked person. For a "
             "U.S. person, dealing in it is prohibited and the property must be "
             "blocked and reported to OFAC, generally within 10 business days. OFAC "
             "applies strict liability, so a transfer made without knowing the address "
             "was listed is still a violation. Non-U.S. persons face secondary "
             "sanctions exposure rather than direct liability. None of this is legal "
             "advice.</p>",
             "<p>The practical consequence for anything automated is that screening has "
             "to happen before the transaction is signed, against a list fetched now "
             "rather than a copy taken at build time.</p>",
             api_block("wallet", "TNiq9AXBp9EjUqhDhrwrfvAA8U3GUQZH81"),
             related([("/programs", "Every OFAC sanctions program on the SDN list"),
                      ("/designations", "OFAC designations by year"),
                      ("/free/ofac-screening", "Free OFAC screening tool"),
                      ("/for/crypto", "OFAC screening for crypto products"),
                      ("/how-to/screen-crypto-wallet", "How to screen a crypto wallet")])]
    ld = "\n".join([
        crumbs([("Sanctioned addresses", "/sanctioned-addresses")]),
        dataset_ld("OFAC-sanctioned digital-currency addresses",
                   "Every digital-currency address published on the OFAC SDN list, "
                   "grouped by chain, with the designated person for each.",
                   "/sanctioned-addresses", as_of),
        faq_ld([("How many crypto addresses has OFAC sanctioned?",
                 "%s, across %d chains, belonging to %s designated persons, as of the "
                 "SDN list published %s." % (f"{total_addr:,}", len(by_chain),
                                             f"{total_ent:,}", as_of)),
                ("Which blockchain has the most OFAC-sanctioned addresses?",
                 "%s, with %s of the %s addresses on the SDN list."
                 % (urls[0][1], f"{urls[0][3]:,}", f"{total_addr:,}") if urls else "")]),
    ])
    write(os.path.join(out_root, "sanctioned-addresses", "index.html"),
          page("OFAC-Sanctioned Crypto Addresses — All %d on the SDN List [%s]"
               % (total_addr, as_of),
               "Every digital-currency address on the OFAC SDN list — %d addresses "
               "across %d chains, with the designated person for each."
               % (total_addr, len(by_chain)),
               "/sanctioned-addresses", "\n".join(body), ld, as_of))
    return [u for u, _, _, _, _ in urls]


def build_designations(entities, as_of, out_root):
    from collections import Counter, defaultdict
    by_year = defaultdict(list)
    for e in entities:
        if e["listed"]:
            by_year[e["listed"][:4]].append(e)

    years = sorted((y for y in by_year if y.isdigit() and int(y) >= FIRST_YEAR),
                   reverse=True)
    urls = []
    for y in years:
        rows = by_year[y]
        url = "/designations/" + y
        types = Counter(r["type"] for r in rows)
        progs = Counter(p for r in rows for p in r["programs"])
        countries = Counter(c for r in rows for c in r["countries"]).most_common(10)
        crypto_n = sum(len(r["crypto"]) for r in rows)
        months = Counter(r["listed"][:7] for r in rows)
        prev = str(int(y) - 1)
        delta = ""
        if prev in by_year:
            a, b = len(rows), len(by_year[prev])
            pct = round(100.0 * (a - b) / b, 1) if b else 0
            delta = (" That is %s%% %s than %s, when OFAC published %s."
                     % (abs(pct), "more" if pct >= 0 else "fewer", prev, f"{b:,}"))

        partial = (y == as_of[:4])
        title = "OFAC Designations in %s — %d SDN Entries Published [%s]" % (
            y, len(rows), as_of)
        desc = ("OFAC published %d SDN entries in %s. Breakdown by program, entity "
                "type and country, counted from Treasury's export of %s."
                % (len(rows), y, as_of))

        body = ['<nav class="breadcrumb"><a href="/">Home</a> &rsaquo; '
                '<a href="/designations">Designations by year</a> &rsaquo; %s</nav>' % y]
        body.append("<h1>OFAC designations in %s</h1>" % y)
        body.append('<p class="lede">OFAC published <strong>%s</strong> entries to the '
                    'Specially Designated Nationals list in %s.%s%s</p>'
                    % (f"{len(rows):,}", y, esc(delta),
                       " %s is still in progress — this counts entries published "
                       "through %s." % (y, as_of) if partial else ""))

        body.append(stat_grid([
            (f"{len(rows):,}", "entries published"),
            (f"{types.get('Individual', 0):,}", "individuals"),
            (f"{types.get('Entity', 0):,}", "entities"),
            (f"{len(progs):,}", "programs used"),
        ]))

        body.append("<h2>Which programs %s designations were made under</h2>" % y)
        p_html = "".join(
            '<tr><td>%s</td><td class="sa-r">%s</td><td class="sa-r">%s%%</td></tr>'
            % (program_cell(p), f"{n:,}", round(100.0 * n / len(rows), 1))
            for p, n in progs.most_common(15))
        body.append('<table><thead><tr><th>Program</th>'
                    '<th class="sa-r">Entries</th><th class="sa-r">Share of %s</th>'
                    '</tr></thead><tbody>%s</tbody></table>' % (y, p_html))
        body.append("<p>Shares sum to more than 100% because a single entry can be "
                    "designated under several programs at once.</p>")

        body.append("<h2>%s designations by month</h2>" % y)
        m_html = "".join(
            '<tr><td>%s</td><td class="sa-r">%s</td></tr>' % (esc(m), f"{n:,}")
            for m, n in sorted(months.items()))
        body.append('<table><thead><tr><th>Month published</th>'
                    '<th class="sa-r">Entries</th></tr></thead><tbody>%s</tbody>'
                    '</table>' % m_html)
        body.append("<p>OFAC publishes in batches rather than continuously, so the "
                    "month-to-month shape is the designation calendar, not a trend. A "
                    "screening system that refreshes weekly can be a full batch behind "
                    "the list.</p>")

        body.append("<h2>Entity types designated in %s</h2>" % y)
        t_html = "".join(
            '<tr><td>%s</td><td class="sa-r">%s</td></tr>'
            % (esc(TYPE_LABEL.get(t, t or "unspecified").capitalize()), f"{n:,}")
            for t, n in types.most_common())
        body.append('<table><thead><tr><th>Type</th>'
                    '<th class="sa-r">Entries</th></tr></thead><tbody>%s</tbody>'
                    '</table>' % t_html)

        if countries:
            body.append("<h2>Countries recorded on %s designations</h2>" % y)
            c_html = "".join(
                '<tr><td>%s</td><td class="sa-r">%s</td></tr>' % (esc(c), f"{n:,}")
                for c, n in countries)
            body.append('<table><thead><tr><th>Country</th>'
                        '<th class="sa-r">Entries</th></tr></thead><tbody>%s</tbody>'
                        '</table>' % c_html)

        if crypto_n:
            body.append("<h2>Digital-currency addresses added in %s</h2>" % y)
            body.append('<p>Entries published in %s carry <strong>%s</strong> '
                        'digital-currency addresses. See the '
                        '<a href="/sanctioned-addresses">per-chain breakdown</a> for '
                        'the addresses themselves.</p>' % (y, f"{crypto_n:,}"))

        body.append(api_block("name", "Bank Markazi"))

        faqs = [
            ("How many entities did OFAC sanction in %s?" % y,
             "OFAC published %s entries to the SDN list in %s: %s. Counted from "
             "Treasury's SDN enhanced XML export of %s."
             % (f"{len(rows):,}", y,
                ", ".join("%s %s" % (f"{n:,}", TYPE_LABEL.get(t, t or "unspecified"))
                          for t, n in types.most_common()), as_of)),
            ("Which sanctions program was used most in %s?" % y,
             "%s, on %s of the %s entries published that year."
             % (progs.most_common(1)[0][0], f"{progs.most_common(1)[0][1]:,}",
                f"{len(rows):,}") if progs else ""),
        ]

        ld = "\n".join([
            crumbs([("Designations by year", "/designations"), (y, url)]),
            faq_ld([f for f in faqs if f[1]]),
            dataset_ld("OFAC SDN designations published in %s" % y,
                       "SDN entries OFAC published in %s, broken down by program, "
                       "entity type, country and month." % y, url, as_of),
        ])

        rel = [("/designations", "OFAC designations by year"),
               ("/programs", "Every OFAC sanctions program")]
        rel += [("/designations/" + z, "OFAC designations in %s" % z)
                for z in years if z != y][:3]
        rel += [("/programs/" + slugify(p), "OFAC %s program" % p)
                for p, _ in progs.most_common(2)]
        body.append(related(rel))

        body.append("""<div class="cta"><h2>Your screening is only as fresh as your last fetch</h2>
<p>SanctionsAI screens against the current SDN list on every call, so a batch
published this morning is live in your flow this morning. One GET per counterparty,
free tier, no signup.</p>
<a class="btn" href="/pricing">See pricing</a></div>""")

        write(os.path.join(out_root, "designations", y, "index.html"),
              page(title, desc, url, "\n".join(body), ld, as_of))
        urls.append((url, y, len(rows), progs.most_common(1)[0][0] if progs else "—"))

    hub_rows = "".join(
        '<tr><td><a href="%s">%s</a></td><td class="sa-r">%s</td><td>%s</td></tr>'
        % (u, y, f"{n:,}", esc(top)) for u, y, n, top in urls)
    older = sum(len(v) for k, v in by_year.items()
                if not (k.isdigit() and int(k) >= FIRST_YEAR))
    body = ['<nav class="breadcrumb"><a href="/">Home</a> &rsaquo; Designations by year</nav>',
            "<h1>OFAC designations by year</h1>",
            '<p class="lede">Every entry on the SDN list carries the date OFAC '
            'published it. Grouped by year, that shows how much the list has grown and '
            'which programs drove it. Counted from Treasury\'s export of %s.</p>' % as_of,
            stat_grid([(f"{len(entities):,}", "SDN entries"),
                       (str(len(urls)), "years profiled"),
                       (f"{older:,}", "published before %d" % FIRST_YEAR),
                       (as_of, "list published")]),
            "<h2>SDN entries published per year</h2>",
            '<table><thead><tr><th>Year</th>'
            '<th class="sa-r">Entries published</th><th>Most-used program</th>'
            '</tr></thead><tbody>%s</tbody></table>' % hub_rows,
            "<p>Entries published before %d are still on the list and still blocked — "
            "%s of them. A designation does not expire; it stays until OFAC removes it."
            "</p>" % (FIRST_YEAR, f"{older:,}"),
            api_block("name", "Bank Markazi"),
            related([("/programs", "Every OFAC sanctions program on the SDN list"),
                     ("/sanctioned-addresses", "OFAC-sanctioned crypto addresses"),
                     ("/sanctions-lists/ofac-sdn", "What the OFAC SDN list is"),
                     ("/free/ofac-screening", "Free OFAC screening tool")])]
    ld = "\n".join([
        crumbs([("Designations by year", "/designations")]),
        dataset_ld("OFAC SDN designations by year",
                   "SDN entries published per year, with the most-used sanctions "
                   "program for each.", "/designations", as_of),
        ldjson({"@context": "https://schema.org", "@type": "ItemList",
                "name": "OFAC designations by year", "numberOfItems": len(urls),
                "itemListElement": [
                    {"@type": "ListItem", "position": i,
                     "name": "OFAC designations in %s" % y, "url": SITE + u}
                    for i, (u, y, _, _) in enumerate(urls, start=1)]}),
    ])
    write(os.path.join(out_root, "designations", "index.html"),
          page("OFAC Designations by Year — SDN Entries Published [%s]" % as_of,
               "How many entries OFAC published to the SDN list each year, with the "
               "most-used program for each. Counted from Treasury's export.",
               "/designations", "\n".join(body), ld, as_of))
    return [u for u, _, _, _ in urls]


def main():
    if "--fetch" in sys.argv:
        return fetch()
    d = load()
    as_of = d["dataAsOf"]
    entities = d["entities"]
    print("building from %d entities, dataAsOf %s" % (len(entities), as_of))

    # Resolve which URLs will exist before rendering anything, so cross-links
    # between the three families can never point at a page the floors excluded.
    from collections import Counter
    prog_n = Counter(p for e in entities for p in e["programs"])
    chain_n = Counter(t for e in entities for t, _ in e["crypto"])
    year_n = Counter(e["listed"][:4] for e in entities if e["listed"])
    LINKABLE.update({"/programs", "/sanctioned-addresses", "/designations"})
    LINKABLE.update("/programs/" + slugify(c)
                    for c, n in prog_n.items() if n >= MIN_PROGRAM_ENTRIES)
    LINKABLE.update("/sanctioned-addresses/" + CHAINS.get(t, (t, slugify(t), t))[1]
                    for t, n in chain_n.items() if n >= MIN_CHAIN_ADDRESSES)
    LINKABLE.update("/designations/" + y for y in year_n
                    if y.isdigit() and int(y) >= FIRST_YEAR)

    p = build_programs(entities, as_of, HERE)
    a = build_addresses(entities, as_of, HERE)
    y = build_designations(entities, as_of, HERE)
    print("  /programs             %3d pages + hub" % len(p))
    print("  /sanctioned-addresses %3d pages + hub" % len(a))
    print("  /designations         %3d pages + hub" % len(y))

    urls = (["/programs", "/sanctioned-addresses", "/designations"] + p + a + y)
    out = os.path.join(HERE, "data", "pseo-ofac-urls.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"dataAsOf": as_of, "count": len(urls), "urls": urls}, fh, indent=1)
    print("  %d URLs -> %s" % (len(urls), out))
    print("\nRemember: api.py's two static-prefix tuples and the Dockerfile COPY "
          "lines must list /programs/, /sanctioned-addresses/ and /designations/, "
          "or these are 404s in production.")


if __name__ == "__main__":
    main()
