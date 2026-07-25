#!/usr/bin/env python3
"""Build the OFAC Civil Penalties Database surface from the verified dataset.

    python3 scripts/build_enforcement.py --data data/ofac-enforcement.json --root .

Renders, under <root>/enforcement/:
    index.html            the hub — every action, searchable, with downloads
    <year>/index.html     one page per year OFAC published actions
    <slug>/index.html     one page per action above PAGE_THRESHOLD

HONESTY GATE — this file renders, it does not author. Every number, name, date
and quotation on every generated page comes from data/ofac-enforcement.json,
which is transcribed verbatim from OFAC's own published chart and enforcement
releases. There is no estimation, no interpolation and no inferred field: an
attribute missing from the record is omitted from the page rather than guessed.
Derived values (ranks, totals, shares, statutory-maximum ratios) are arithmetic
over those verbatim figures and nothing else. Do not add prose here that makes a
claim the dataset cannot support.
"""
import argparse
import html
import json
import os
import re
import unicodedata
from collections import Counter, defaultdict

SITE = "https://sanctionsai.dev"
PAGE_THRESHOLD = 100_000  # actions at or above this get a dedicated page

POSTHOG = (
    '<script>!function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){'
    'function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){'
    't.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script"))'
    '.type="text/javascript",p.crossOrigin="anonymous",p.async=!0,p.src=s.api_host.replace('
    '".i.posthog.com","-assets.i.posthog.com")+"/static/array.js",(r=t.getElementsByTagName('
    '"script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",'
    'u.people=u.people||[],u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),'
    't||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)+".people (stub)"},'
    'o="capture identify alias people.set people.set_once set_config register register_once '
    'unregister opt_out_capturing has_opted_out_capturing opt_in_capturing reset isFeatureEnabled '
    'onFeatureFlags getFeatureFlag getFeatureFlagPayload reloadFeatureFlags group '
    'updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures getActiveMatchingSurveys '
    'getSurveys".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=!0}'
    '(document,window.posthog||[]);posthog.init("phc_lyZCgvTpicjLzAO3rY2GhxuX5WUc5jQjP8ZVwwJqauX",'
    '{api_host:"https://eu.i.posthog.com",person_profiles:"identified_only"})</script>'
)

CSS = """
*{box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;line-height:1.65;color:#0a0a0a;max-width:1040px;margin:0 auto;padding:2rem 1.25rem;background:#fff}
h1{font-size:2.1rem;line-height:1.2;margin:.3em 0}
h2{font-size:1.45rem;margin-top:2.4rem;border-bottom:2px solid #e5e7eb;padding-bottom:.3rem}
h3{font-size:1.12rem;margin-top:1.5rem}
a{color:#0066cc;text-decoration:none}a:hover{text-decoration:underline}
.lede{font-size:1.12rem;color:#374151;margin-bottom:1.5rem}
nav.crumb{font-size:.88rem;color:#6b7280;margin-bottom:1rem}
table{border-collapse:collapse;width:100%;margin:1rem 0;font-size:.93rem}
th,td{border:1px solid #e5e7eb;padding:.5rem .7rem;text-align:left;vertical-align:top}
th{background:#f9fafb;font-weight:600}
td.num,th.num,td.n,th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
.stats{display:grid;grid-template-columns:repeat(2,1fr);gap:.75rem;margin:1.5rem 0}
@media(min-width:640px){.stats{grid-template-columns:repeat(4,1fr)}}
.stat{background:#f9fafb;border:1px solid #e5e7eb;border-radius:.5rem;padding:.9rem 1rem}
.stat .k{display:block;font-size:1.5rem;font-weight:700;font-variant-numeric:tabular-nums;line-height:1.15}
.stat .l{display:block;font-size:.8rem;color:#6b7280;margin-top:.15rem}
.callout{background:#f0f7ff;border-left:4px solid #0066cc;padding:1rem 1.25rem;margin:1.5rem 0;border-radius:0 .375rem .375rem 0}
.callout.warn{background:#fef3c7;border-left-color:#d97706}
.src{font-size:.85rem;color:#6b7280}
.controls{display:flex;gap:.6rem;flex-wrap:wrap;margin:1rem 0}
.controls input,.controls select{font:inherit;padding:.5rem .7rem;border:1px solid #d1d5db;border-radius:.375rem;background:#fff}
.controls input{flex:1;min-width:220px}
.dl a{display:inline-block;background:#f9fafb;border:1px solid #d1d5db;border-radius:.375rem;padding:.5rem .9rem;margin:.25rem .4rem .25rem 0;font-size:.92rem}
blockquote{margin:1rem 0;padding:.75rem 1.1rem;border-left:3px solid #d1d5db;color:#374151;background:#fafafa}
.related-links{background:#f9fafb;padding:1rem 1.25rem;border-radius:.5rem;margin-top:2rem}
.related-links ul{list-style:none;padding-left:0;margin:0}
.related-links li{padding:.22rem 0}
.cta{background:linear-gradient(135deg,#0066cc,#004499);color:#fff;padding:1.6rem;border-radius:.75rem;margin-top:2rem}
.cta h2{color:#fff;border:none;margin-top:0}
.cta a{color:#fff;font-weight:600;text-decoration:underline}
footer{margin-top:3rem;padding-top:1.5rem;border-top:1px solid #e5e7eb;color:#6b7280;font-size:.88rem}
.hidden{display:none}
"""

DISCLAIMER = (
    '<p class="src"><strong>Not legal or compliance advice.</strong> This page reproduces figures '
    'published by the U.S. Department of the Treasury’s Office of Foreign Assets Control. '
    'OFAC’s own enforcement release is the authoritative record; where this page and OFAC '
    'differ, OFAC is correct. Consult qualified counsel for advice on any specific matter.</p>'
)


def esc(s):
    return html.escape(str(s), quote=True)


def usd(n, cents=None):
    # Never round a penalty. OFAC publishes figures like $2,980,265.94, and
    # rounding that to $2,980,266 prints an amount OFAC never issued — on a
    # dataset whose whole claim is verbatim fidelity. Show cents iff they exist.
    if cents is None:
        cents = n % 1 != 0
    return "$" + (format(n, ",.2f") if cents else format(int(n), ","))


def compact(n):
    n = float(n)
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if n >= div:
            v = n / div
            return "$%s%s" % (("%.2f" % v).rstrip("0").rstrip("."), suf)
    return "$%d" % n


def slugify(s):
    # OFAC's markup sometimes splits a word at an accented letter, e.g.
    # "Soci é té Générale, New York". Close those gaps first — a space between an
    # accented letter and a plain one is always this artifact, never a word
    # break. The entity name is still rendered verbatim on the page; this only
    # stops the URL becoming "soci-e-te-generale-new-york".
    s = re.sub(r"(?<=[A-Za-z]) ([À-ɏ]) (?=[A-Za-z])", r"\1", s)
    # Fold accents to ASCII. Without this "Société Générale S.A." slugs as
    # "soci-t-g-n-rale-s-a", because every accented letter falls outside [a-z0-9].
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("&", " and ").replace("ø", "o").replace("ł", "l")
    s = re.sub(r"[‘’'\"]", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"-{2,}", "-", s).strip("-")[:70]


def page(title, desc, canonical, body, ld=None, extra_head=""):
    lds = "".join(
        '<script type="application/ld+json">%s</script>' % json.dumps(x, separators=(",", ":"))
        for x in (ld or [])
    )
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
        '<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        "<title>%s</title>\n" % esc(title)
        + '<meta name="description" content="%s">\n' % esc(desc)
        + '<link rel="canonical" href="%s">\n' % esc(canonical)
        + '<meta property="og:title" content="%s">\n' % esc(title)
        + '<meta property="og:description" content="%s">\n' % esc(desc)
        + '<meta property="og:type" content="article">\n'
        + '<meta property="og:url" content="%s">\n' % esc(canonical)
        + '<meta property="og:image" content="%s/og.png">\n' % SITE
        + '<meta name="twitter:card" content="summary_large_image">\n'
        + '<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">\n'
        + lds
        + "<style>%s</style>\n" % CSS
        + extra_head
        + POSTHOG
        + "\n</head>\n<body>\n"
        + body
        + "\n</body>\n</html>\n"
    )


def footer(meta):
    return (
        "<footer>"
        '<p><strong>Source.</strong> U.S. Department of the Treasury, Office of Foreign Assets '
        'Control — <a href="%s" rel="nofollow noopener" target="_blank">Civil Penalties and '
        "Enforcement Information</a>. Retrieved %s. Works of the U.S. federal government are in "
        "the public domain (17 U.S.C. § 105).</p>"
        '<p>This compilation is published by <a href="%s/">SanctionsAI</a> under '
        '<a href="https://creativecommons.org/licenses/by/4.0/" rel="license noopener" '
        'target="_blank">CC BY 4.0</a>. Cite as: SanctionsAI, “OFAC Civil Penalties '
        "Database”, %s, %s/enforcement.</p>"
        "%s</footer>"
        % (esc(meta["sourceUrl"]), esc(meta["retrieved"]), SITE, meta["retrieved"][:4], SITE, DISCLAIMER)
    )


def cta():
    return (
        '<div class="cta"><h2>Screen against the live SDN list before you transact</h2>'
        "<p>Every action on this page began with a payment or transfer that was not screened. "
        'SanctionsAI is a free OFAC screening API for names and crypto wallets — '
        '<a href="%s/docs">read the API docs</a> or '
        '<a href="%s/tools/wallet-checker">check a wallet in the browser</a>.</p></div>'
        % (SITE, SITE)
    )


# --------------------------------------------------------------------------- hub

def build_hub(rows, meta, out):
    total = sum(r["amountUSD"] for r in rows)
    years = sorted({r["year"] for r in rows})
    by_year = defaultdict(list)
    for r in rows:
        by_year[r["year"]].append(r)
    ranked = sorted(rows, key=lambda r: -r["amountUSD"])
    biggest = ranked[0]

    title = "OFAC Civil Penalties Database — Every Enforcement Action, %d–%d" % (years[0], years[-1])
    desc = (
        "All %s OFAC civil penalties and settlements published by the U.S. Treasury from %d to %d, "
        "totalling %s. Searchable, sourced to each enforcement release, free CSV and JSON download."
        % (format(len(rows), ","), years[0], years[-1], compact(total))
    )

    # searchable table of every action
    trs = []
    for i, r in enumerate(ranked):
        slug = r.get("slug")
        name = (
            '<a href="/enforcement/%s">%s</a>' % (esc(slug), esc(r["entity"]))
            if slug
            else esc(r["entity"])
        )
        src = (
            ' <a href="%s" rel="nofollow noopener" target="_blank" title="OFAC enforcement release">↗</a>'
            % esc(r["sourceUrl"])
            if r.get("sourceUrl")
            else ""
        )
        # No data-* search key: it would duplicate every row's text and roughly
        # double the page weight on a 1,000-row table. The filter reads the
        # cells it already has.
        trs.append(
            '<tr><td class=n>%d</td><td>%s%s</td><td class=n>%s</td>'
            '<td class=n><a href="/enforcement/%d">%s</a></td><td class=n>%s</td></tr>'
            % (i + 1, name, src, esc(r["date"]), r["year"], r["year"], usd(r["amountUSD"]))
        )

    year_rows = "".join(
        '<tr><td><a href="/enforcement/%d">%d</a></td><td class="num">%d</td>'
        '<td class="num">%s</td><td>%s</td></tr>'
        % (
            y,
            y,
            len(by_year[y]),
            usd(sum(x["amountUSD"] for x in by_year[y])),
            '<a href="/enforcement/%s">%s</a>'
            % (esc(max(by_year[y], key=lambda x: x["amountUSD"])["slug"]), esc(max(by_year[y], key=lambda x: x["amountUSD"])["entity"]))
            if max(by_year[y], key=lambda x: x["amountUSD"]).get("slug")
            else esc(max(by_year[y], key=lambda x: x["amountUSD"])["entity"]),
        )
        for y in reversed(years)
    )

    ld = [
        {
            "@context": "https://schema.org",
            "@type": "Dataset",
            "name": "OFAC Civil Penalties Database",
            "description": desc,
            "url": SITE + "/enforcement",
            "keywords": ["OFAC", "sanctions", "civil penalties", "enforcement actions", "compliance"],
            "license": "https://creativecommons.org/licenses/by/4.0/",
            "isAccessibleForFree": True,
            "creator": {"@type": "Organization", "name": "SanctionsAI", "url": SITE},
            "temporalCoverage": "%d/%d" % (years[0], years[-1]),
            "isBasedOn": meta["sourceUrl"],
            "dateModified": meta["retrieved"],
            "distribution": [
                {"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": SITE + "/data/ofac-enforcement.csv"},
                {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": SITE + "/data/ofac-enforcement.json"},
            ],
        },
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
                {"@type": "ListItem", "position": 2, "name": "OFAC Civil Penalties Database", "item": SITE + "/enforcement"},
            ],
        },
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": "What is the largest OFAC penalty ever issued?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "The largest single civil penalty in OFAC's published chart is %s, paid by %s on %s."
                        % (usd(biggest["amountUSD"]), biggest["entity"], biggest["date"]),
                    },
                },
                {
                    "@type": "Question",
                    "name": "How much has OFAC collected in civil penalties?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "OFAC's published chart records %s civil penalties, settlements and findings of violation between %d and %d, totalling %s."
                        % (format(len(rows), ","), years[0], years[-1], usd(total)),
                    },
                },
                {
                    "@type": "Question",
                    "name": "Where does this OFAC penalty data come from?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "Every row is transcribed from OFAC's own Civil Penalties and Enforcement Information chart at ofac.treasury.gov, retrieved %s. Each row links to the underlying enforcement release. No figure is estimated."
                        % meta["retrieved"],
                    },
                },
            ],
        },
    ]

    script = """<script>
(function(){
var q=document.getElementById('q'),y=document.getElementById('y'),
    rows=[].slice.call(document.querySelectorAll('#all tbody tr')),
    n=document.getElementById('n'),keys=rows.map(function(r){
      return (r.cells[1].textContent+' '+r.cells[2].textContent).toLowerCase();
    }),t;
function f(){
  var s=q.value.toLowerCase().trim(),yr=y.value,c=0;
  for(var i=0;i<rows.length;i++){
    var ok=(!s||keys[i].indexOf(s)>-1)&&(!yr||rows[i].cells[3].textContent.trim()===yr);
    if(ok!==!rows[i].classList.contains('hidden'))rows[i].classList.toggle('hidden',!ok);
    if(ok)c++;
  }
  n.textContent=c.toLocaleString();
}
function d(){clearTimeout(t);t=setTimeout(f,120)}
q.addEventListener('input',d); y.addEventListener('change',f);
})();
</script>"""

    body = (
        "<article>"
        '<nav class="crumb"><a href="/">SanctionsAI</a> › OFAC Civil Penalties Database</nav>'
        "<h1>OFAC Civil Penalties Database</h1>"
        '<p class="lede">Every civil penalty, settlement and finding of violation published by the '
        "U.S. Treasury’s Office of Foreign Assets Control between %d and %d — %s actions "
        "totalling %s. Each row is transcribed from OFAC’s own chart and links to the "
        "enforcement release behind it.</p>"
        % (years[0], years[-1], format(len(rows), ","), usd(total))
        + '<div class="stats">'
        + '<div class="stat"><span class="k">%s</span><span class="l">enforcement actions</span></div>' % format(len(rows), ",")
        + '<div class="stat"><span class="k">%s</span><span class="l">total penalties</span></div>' % compact(total)
        + '<div class="stat"><span class="k">%s</span><span class="l">largest single action</span></div>' % compact(biggest["amountUSD"])
        + '<div class="stat"><span class="k">%d–%d</span><span class="l">years covered</span></div>' % (years[0], years[-1])
        + "</div>"
        + '<div class="callout"><p><strong>Why this exists.</strong> OFAC publishes its enforcement '
        "record as %d separate year pages, each a static HTML table with the detail locked inside "
        "linked PDFs. There is no combined view, no search across years and no machine-readable "
        "export. This page is that combined view, rebuilt from the source and free to reuse under "
        "CC BY 4.0.</p></div>" % len(years)
        + '<div class="dl"><a href="/data/ofac-enforcement.csv" download>⬇ Download CSV</a>'
        '<a href="/data/ofac-enforcement.json" download>⬇ Download JSON</a>'
        '<a href="%s" rel="nofollow noopener" target="_blank">OFAC source chart ↗</a></div>' % esc(meta["sourceUrl"])
        + "<h2>Search every OFAC enforcement action</h2>"
        + '<div class="controls">'
        '<input id="q" type="search" placeholder="Search by company name, e.g. Binance, Standard Chartered…" aria-label="Search enforcement actions">'
        '<select id="y" aria-label="Filter by year"><option value="">All years</option>%s</select>'
        "</div>"
        % "".join('<option value="%d">%d</option>' % (y, y) for y in reversed(years))
        + '<p class="src"><span id="n">%s</span> actions shown, ranked by penalty amount.</p>' % format(len(rows), ",")
        + '<div class="wrap"><table id="all"><thead><tr><th class="num">#</th><th>Entity</th>'
        '<th class="num">Date</th><th class="num">Year</th><th class="num">Penalty (USD)</th>'
        "</tr></thead><tbody>%s</tbody></table></div>" % "".join(trs)
        + "<h2>OFAC penalties by year</h2>"
        + '<div class="wrap"><table><thead><tr><th>Year</th><th class="num">Actions</th>'
        '<th class="num">Total penalties</th><th>Largest action</th></tr></thead>'
        "<tbody>%s</tbody></table></div>" % year_rows
        + "<h2>How to cite this dataset</h2>"
        + "<p>SanctionsAI, “OFAC Civil Penalties Database”, %s. "
        "Derived from U.S. Department of the Treasury, Office of Foreign Assets Control, "
        "“Civil Penalties and Enforcement Information”, retrieved %s. "
        "Published under CC BY 4.0 — reuse it, including commercially, with attribution.</p>"
        % (meta["retrieved"][:4], meta["retrieved"])
        + '<div class="related-links"><ul>'
        '<li><a href="/penalties/ofac-violation-costs">What an OFAC violation actually costs</a></li>'
        '<li><a href="/glossary/voluntary-self-disclosure">Voluntary self-disclosure, and what it saves</a></li>'
        '<li><a href="/glossary/ofac-sdn-list">The OFAC SDN list explained</a></li>'
        '<li><a href="/tools/wallet-checker">Free crypto wallet sanctions check</a></li>'
        "</ul></div>"
        + cta()
        + "</article>"
        + footer(meta)
        + script
    )
    write(os.path.join(out, "enforcement", "index.html"), page(title, desc, SITE + "/enforcement", body, ld))


# -------------------------------------------------------------------------- year

def build_year(y, rows, all_rows, meta, out):
    yr = sorted([r for r in rows if r["year"] == y], key=lambda r: -r["amountUSD"])
    if not yr:
        return
    total = sum(r["amountUSD"] for r in yr)
    biggest = yr[0]
    years = sorted({r["year"] for r in all_rows})
    prev = [r for r in all_rows if r["year"] == y - 1]
    prev_total = sum(r["amountUSD"] for r in prev)

    title = "OFAC Enforcement Actions %d — All %d Penalties, %s Total" % (y, len(yr), compact(total))
    desc = (
        "Every OFAC civil penalty published for %d: %d actions totalling %s. Largest was %s at %s. "
        "Sourced to each Treasury enforcement release." % (y, len(yr), usd(total), biggest["entity"], usd(biggest["amountUSD"]))
    )

    trs = "".join(
        '<tr><td class="num">%s</td><td>%s%s</td><td class="num">%s</td><td class="num">%s</td></tr>'
        % (
            esc(r["date"]),
            '<a href="/enforcement/%s">%s</a>' % (esc(r["slug"]), esc(r["entity"])) if r.get("slug") else esc(r["entity"]),
            ' <a href="%s" rel="nofollow noopener" target="_blank" title="OFAC enforcement release">↗</a>' % esc(r["sourceUrl"]) if r.get("sourceUrl") else "",
            esc(r.get("actions") if r.get("actions") is not None else "—"),
            usd(r["amountUSD"]),
        )
        for r in sorted(yr, key=lambda r: r["date"])
    )

    if prev:
        pct = ((total - prev_total) / prev_total * 100) if prev_total else None
        cmp_txt = (
            "OFAC published %d actions in %d totalling %s, against %d actions totalling %s in %d"
            % (len(yr), y, usd(total), len(prev), usd(prev_total), y - 1)
            + (" — a %s of %.0f%% in total penalties." % ("rise" if pct > 0 else "fall", abs(pct)) if pct is not None else ".")
        )
    else:
        cmp_txt = "%d is the first year in OFAC’s published enforcement chart." % y

    nav = []
    if y - 1 in years:
        nav.append('<a href="/enforcement/%d">← %d</a>' % (y - 1, y - 1))
    nav.append('<a href="/enforcement">All years</a>')
    if y + 1 in years:
        nav.append('<a href="/enforcement/%d">%d →</a>' % (y + 1, y + 1))

    ld = [
        {
            "@context": "https://schema.org",
            "@type": "Dataset",
            "name": "OFAC Civil Penalties %d" % y,
            "description": desc,
            "url": "%s/enforcement/%d" % (SITE, y),
            "license": "https://creativecommons.org/licenses/by/4.0/",
            "isAccessibleForFree": True,
            "temporalCoverage": str(y),
            "isPartOf": {"@type": "Dataset", "name": "OFAC Civil Penalties Database", "url": SITE + "/enforcement"},
            "creator": {"@type": "Organization", "name": "SanctionsAI", "url": SITE},
        },
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
                {"@type": "ListItem", "position": 2, "name": "OFAC Civil Penalties Database", "item": SITE + "/enforcement"},
                {"@type": "ListItem", "position": 3, "name": str(y), "item": "%s/enforcement/%d" % (SITE, y)},
            ],
        },
    ]

    body = (
        "<article>"
        '<nav class="crumb"><a href="/">SanctionsAI</a> › <a href="/enforcement">OFAC Civil Penalties Database</a> › %d</nav>' % y
        + "<h1>OFAC enforcement actions in %d</h1>" % y
        + '<p class="lede">OFAC published %d civil penalties, settlements and findings of violation in '
        "%d, totalling %s. The largest was %s at %s on %s.</p>"
        % (len(yr), y, usd(total), esc(biggest["entity"]), usd(biggest["amountUSD"]), esc(biggest["date"]))
        + '<div class="stats">'
        + '<div class="stat"><span class="k">%d</span><span class="l">actions in %d</span></div>' % (len(yr), y)
        + '<div class="stat"><span class="k">%s</span><span class="l">total penalties</span></div>' % compact(total)
        + '<div class="stat"><span class="k">%s</span><span class="l">largest action</span></div>' % compact(biggest["amountUSD"])
        + '<div class="stat"><span class="k">%s</span><span class="l">median action</span></div>'
        % compact(sorted(x["amountUSD"] for x in yr)[len(yr) // 2])
        + "</div>"
        + "<p>%s</p>" % cmp_txt
        + "<h2>Every %d OFAC enforcement action</h2>" % y
        + '<div class="wrap"><table><thead><tr><th class="num">Date</th><th>Entity</th>'
        '<th class="num">Violations</th><th class="num">Penalty (USD)</th></tr></thead>'
        "<tbody>%s</tbody></table></div>" % trs
        + '<p class="src">“Violations” is OFAC’s aggregate count of penalties, settlements '
        "or findings of violation for that entry. ↗ opens OFAC’s enforcement release.</p>"
        + '<div class="related-links"><ul>%s</ul></div>'
        % "".join("<li>%s</li>" % x for x in nav)
        + cta()
        + "</article>"
        + footer(meta)
    )
    write(os.path.join(out, "enforcement", str(y), "index.html"), page(title, desc, "%s/enforcement/%d" % (SITE, y), body, ld))


# ------------------------------------------------------------------------ action

def build_action(r, rows, meta, out):
    y = r["year"]
    yr = [x for x in rows if x["year"] == y]
    ranked = sorted(rows, key=lambda x: -x["amountUSD"])
    rank = ranked.index(r) + 1
    yrank = sorted(yr, key=lambda x: -x["amountUSD"]).index(r) + 1
    ytotal = sum(x["amountUSD"] for x in yr)
    rel = r.get("release") or {}
    same = [x for x in rows if x is not r and slugify(x["entity"])[:16] == slugify(r["entity"])[:16]]

    amt = usd(r["amountUSD"])
    title = "%s OFAC Penalty — %s (%s)" % (r["entity"], amt, r["date"])
    if len(title) > 95:
        title = "%s OFAC Penalty — %s" % (r["entity"][:45], amt)
    desc = (
        "OFAC recorded a %s civil penalty against %s on %s. Exact figure, the Treasury enforcement "
        "release, and how it ranks among all %s published OFAC actions."
        % (amt, r["entity"], r["date"], format(len(rows), ","))
    )

    facts = [
        ("Entity, as published by OFAC", esc(r["entity"])),
        ("Penalty / settlement amount", "<strong>%s</strong>" % usd(r["amountUSD"])),
        ("Date published by OFAC", esc(r["date"]) + (" (OFAC entry %s)" % r["suffix"] if r.get("suffix") else "")),
        ("Aggregate penalties, settlements or findings", esc(r["actions"]) if r.get("actions") is not None else "—"),
        ("Rank among all published OFAC actions", "#%d of %s" % (rank, format(len(rows), ","))),
        ("Rank within %d" % y, "#%d of %d" % (yrank, len(yr))),
        ("Share of %d penalty total" % y, "%.1f%%" % (100 * r["amountUSD"] / ytotal) if ytotal else "—"),
    ]
    if rel.get("apparentViolations"):
        facts.append(("Apparent violations cited", format(rel["apparentViolations"], ",")))
    if rel.get("statutoryMaxUSD"):
        facts.append(("Statutory maximum penalty", usd(rel["statutoryMaxUSD"])))
    if rel.get("basePenaltyUSD"):
        facts.append(("Base penalty", usd(rel["basePenaltyUSD"])))
    if "voluntarilySelfDisclosed" in rel:
        facts.append(("Voluntarily self-disclosed", "Yes" if rel["voluntarilySelfDisclosed"] else "No"))
    if "egregious" in rel:
        facts.append(("OFAC egregiousness determination", "Egregious" if rel["egregious"] else "Non-egregious"))
    if rel.get("conductPeriod"):
        facts.append(("Conduct period cited", esc(rel["conductPeriod"])))
    if rel.get("programsMentioned"):
        facts.append(("Sanctions programs named in the release", esc(", ".join(rel["programsMentioned"]))))

    fact_rows = "".join("<tr><th>%s</th><td>%s</td></tr>" % (k, v) for k, v in facts)

    parts = [
        "<article>",
        '<nav class="crumb"><a href="/">SanctionsAI</a> › <a href="/enforcement">OFAC Civil Penalties Database</a> › <a href="/enforcement/%d">%d</a> › %s</nav>' % (y, y, esc(r["entity"])),
        "<h1>%s — %s OFAC penalty</h1>" % (esc(r["entity"]), amt),
        '<p class="lede">OFAC published a %s civil penalty against %s on %s. It is the #%d largest '
        "action in OFAC’s %s-entry enforcement chart and #%d of the %d actions published that year.</p>"
        % (amt, esc(r["entity"]), esc(r["date"]), rank, format(len(rows), ","), yrank, len(yr)),
    ]

    if rel.get("summarySentence"):
        parts.append(
            "<h2>What OFAC said</h2>"
            "<blockquote><p>%s</p></blockquote>" % esc(rel["summarySentence"])
            + '<p class="src">Quoted verbatim from OFAC’s enforcement release%s.</p>'
            % (' — <a href="%s" rel="nofollow noopener" target="_blank">read the original</a>' % esc(r["sourceUrl"]) if r.get("sourceUrl") else "")
        )

    parts.append("<h2>The record</h2>")
    parts.append('<div class="wrap"><table><tbody>%s</tbody></table></div>' % fact_rows)

    if rel.get("statutoryMaxUSD") and rel["statutoryMaxUSD"] > 0:
        ratio = r["amountUSD"] / rel["statutoryMaxUSD"] * 100
        parts.append(
            "<h2>Settlement against statutory maximum</h2>"
            "<p>OFAC put the statutory maximum civil monetary penalty for this case at %s. The "
            "settled amount of %s is <strong>%.1f%%</strong> of that maximum%s.</p>"
            % (
                usd(rel["statutoryMaxUSD"]),
                amt,
                ratio,
                ", which OFAC's Enforcement Guidelines tie to factors including voluntary self-disclosure and whether the conduct was egregious"
                if ("voluntarilySelfDisclosed" in rel or "egregious" in rel)
                else "",
            )
        )

    if r.get("sourceUrl"):
        parts.append(
            "<h2>Primary source</h2>"
            '<p>OFAC enforcement release: <a href="%s" rel="nofollow noopener" target="_blank">%s</a>. '
            "This page adds no facts beyond that document and OFAC’s published penalty chart.</p>"
            % (esc(r["sourceUrl"]), esc(r.get("sourceDoc") or "Treasury enforcement release (PDF)"))
        )

    if same:
        parts.append(
            "<h2>Other published actions involving this name</h2><ul>%s</ul>"
            % "".join(
                "<li>%s — %s on %s</li>"
                % (
                    '<a href="/enforcement/%s">%s</a>' % (esc(x["slug"]), esc(x["entity"])) if x.get("slug") else esc(x["entity"]),
                    usd(x["amountUSD"]),
                    esc(x["date"]),
                )
                for x in sorted(same, key=lambda x: -x["amountUSD"])[:8]
            )
            + '<p class="src">Matched on the entity name OFAC published. Similar names do not always '
            "mean the same legal entity — check each release.</p>"
        )

    peers = sorted([x for x in yr if x is not r], key=lambda x: abs(x["amountUSD"] - r["amountUSD"]))[:5]
    if peers:
        parts.append(
            "<h2>Comparable %d actions</h2><ul>%s</ul>"
            % (
                y,
                "".join(
                    "<li>%s — %s</li>"
                    % (
                        '<a href="/enforcement/%s">%s</a>' % (esc(x["slug"]), esc(x["entity"])) if x.get("slug") else esc(x["entity"]),
                        usd(x["amountUSD"]),
                    )
                    for x in peers
                ),
            )
        )

    parts.append(
        '<div class="related-links"><ul>'
        '<li><a href="/enforcement/%d">All %d OFAC enforcement actions</a></li>'
        '<li><a href="/enforcement">The full OFAC Civil Penalties Database</a></li>'
        '<li><a href="/penalties/ofac-violation-costs">What an OFAC violation costs</a></li>'
        "</ul></div>" % (y, y)
    )
    parts.append(cta())
    parts.append("</article>")

    ld = [
        {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": title,
            "description": desc,
            "author": {"@type": "Organization", "name": "SanctionsAI", "url": SITE},
            "publisher": {"@type": "Organization", "name": "SanctionsAI", "url": SITE},
            "mainEntityOfPage": {"@type": "WebPage", "@id": "%s/enforcement/%s" % (SITE, r["slug"])},
            "dateModified": meta["retrieved"],
            "isBasedOn": r.get("sourceUrl") or meta["sourceUrl"],
            "citation": {"@type": "CreativeWork", "name": "OFAC Civil Penalties and Enforcement Information", "url": r.get("sourceUrl") or meta["sourceUrl"]},
        },
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
                {"@type": "ListItem", "position": 2, "name": "OFAC Civil Penalties Database", "item": SITE + "/enforcement"},
                {"@type": "ListItem", "position": 3, "name": str(y), "item": "%s/enforcement/%d" % (SITE, y)},
                {"@type": "ListItem", "position": 4, "name": r["entity"], "item": "%s/enforcement/%s" % (SITE, r["slug"])},
            ],
        },
    ]

    write(
        os.path.join(out, "enforcement", r["slug"], "index.html"),
        page(title, desc, "%s/enforcement/%s" % (SITE, r["slug"]), "".join(parts) + footer(meta), ld),
    )


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def assign_slugs(rows):
    used = Counter()
    for r in sorted(rows, key=lambda r: -r["amountUSD"]):
        if r["amountUSD"] < PAGE_THRESHOLD:
            continue
        base = "%s-%d" % (slugify(r["entity"]), r["year"])
        used[base] += 1
        r["slug"] = base if used[base] == 1 else "%s-%d" % (base, used[base])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/ofac-enforcement.json")
    ap.add_argument("--meta", default="data/ofac-enforcement.meta.json")
    ap.add_argument("--root", default=".")
    a = ap.parse_args()

    rows = json.load(open(a.data))
    meta = json.load(open(a.meta))
    assign_slugs(rows)

    build_hub(rows, meta, a.root)
    years = sorted({r["year"] for r in rows})
    for y in years:
        build_year(y, rows, rows, meta, a.root)
    pages = [r for r in rows if r.get("slug")]
    for r in pages:
        build_action(r, rows, meta, a.root)

    # The sitemap reads this file rather than carrying its own copy of the URL
    # list, so the two cannot drift as the dataset grows.
    urls = ["/enforcement"] + ["/enforcement/%d" % y for y in years] + \
           ["/enforcement/%s" % r["slug"] for r in pages]
    write(os.path.join(a.root, "enforcement", "urls.txt"), "\n".join(urls) + "\n")

    print("hub 1 | years %d | actions %d | total pages %d" % (len(years), len(pages), 1 + len(years) + len(pages)))
    print("wrote enforcement/urls.txt (%d urls)" % len(urls))


if __name__ == "__main__":
    main()
