#!/usr/bin/env python3
"""Emit the PUBLISHED OFAC SDN dataset from the compact screening index.

Two different artefacts come out of the same OFAC download:

  * ``data/ofac-sdn-index.json``  — built by build_sdn_index.py. Positional
    arrays, minified, tuned for the browser screener's download size.
  * ``data/ofac-sdn-list/*``      — built here. Named fields, a flat CSV, and a
    dataset card. This is the artefact other people consume, so it optimises for
    being readable and citable rather than small.

Nothing is inferred or edited. Names, types and programs are OFAC's own strings;
the only transformations are splitting the bracketed program field into a list
and joining alternate names onto their primary entry.

Run:  python3 scripts/build_sdn_dataset.py
In:   data/ofac-sdn-index.json  (+ .meta.json)
Out:  data/ofac-sdn-list/ofac-sdn.json
      data/ofac-sdn-list/ofac-sdn.csv
      data/ofac-sdn-list/metadata.json
      data/ofac-sdn-list/index.html

index.html is generated rather than hand-maintained so its counts and dates come
from the same build as the files it describes. A landing page claiming 19,254
records next to a download holding a different number is the failure mode this
avoids.

The publication date is OFAC's, carried through from the index build. A dataset
that displays its own build date as the list date tells a compliance officer the
data is fresher than it is, which is the one error in this file that would
actually matter.
"""
import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(HERE, "data", "ofac-sdn-index.json")
INDEX_META = os.path.join(HERE, "data", "ofac-sdn-index.meta.json")
OUTDIR = os.path.join(HERE, "data", "ofac-sdn-list")

SITE = "https://sanctionsai.dev"
BASE = SITE + "/data/ofac-sdn-list"

# 17 U.S.C. 105: works of the U.S. Government are not under copyright. The list
# itself is therefore public domain — we hold no rights in it and must not
# advertise one. CC0 covers only the parsing/packaging done in this repo.
LICENSE_URL = "https://creativecommons.org/publicdomain/zero/1.0/"

DISCLAIMER = (
    "This is an unofficial machine-readable mirror provided for engineering use. "
    "OFAC's own SDN search at https://sanctionssearch.ofac.treas.gov/ is the "
    "authoritative source and should be used for any compliance decision. "
    "Nothing here is legal or compliance advice."
)


def split_programs(raw):
    """'[SDGT] [IFSR]' -> ['SDGT', 'IFSR']. OFAC's own strings, unmodified."""
    out = []
    for part in re.split(r"\]\s*\[", (raw or "").strip().strip("[]")):
        part = part.strip()
        if part and part not in out:
            out.append(part)
    return out


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def mb(n):
    return "%.1f MB" % (n / 1048576.0)


def render_page(card):
    """Landing page for the dataset, with the schema.org/Dataset block that
    Google Dataset Search reads. JSON-LD is json.dumps'd, never hand-written —
    the Docker build gates on it parsing, and a hand-edited block is how the
    portfolio has broken that gate before."""
    c = card["counts"]
    tc = card.get("typeCounts", {})
    ld = {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "@id": BASE + "/#dataset",
        "name": card["name"],
        "description": card["description"],
        "url": BASE + "/",
        "license": card["licenseUrl"],
        "isAccessibleForFree": True,
        "datePublished": card["published"],
        "dateModified": card.get("retrieved") or card["published"],
        "temporalCoverage": card["published"],
        "version": card["published"],
        "keywords": [
            "OFAC", "SDN list", "sanctions", "Specially Designated Nationals",
            "sanctions screening", "AML", "compliance", "blocked persons",
            "US Treasury", "sanctions data",
        ],
        "measurementTechnique": "Direct parse of OFAC's published SDN.CSV and ALT.CSV exports",
        "isBasedOn": card["sourceUrl"],
        "sameAs": card["officialSearchUrl"],
        "creator": {
            "@type": "GovernmentOrganization",
            "name": "U.S. Department of the Treasury, Office of Foreign Assets Control",
            "url": "https://ofac.treasury.gov/",
        },
        "publisher": {"@id": SITE + "/#organization"},
        "includedInDataCatalog": {
            "@type": "DataCatalog",
            "name": "SanctionsAI Research Data",
            "url": SITE + "/data/",
        },
        "variableMeasured": [
            {"@type": "PropertyValue", "name": f["name"], "description": f["description"]}
            for f in card["fields"]
        ],
        "distribution": [
            {
                "@type": "DataDownload",
                "encodingFormat": d["mediaType"],
                "contentUrl": d["url"],
                "name": "%s — %s" % (card["name"], d["format"]),
                "contentSize": str(card["bytes"]["json" if d["format"] == "JSON" else "csv"]),
            }
            for d in card["distributions"]
        ],
    }
    bc = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Research Data", "item": SITE + "/data/"},
            {"@type": "ListItem", "position": 3, "name": "OFAC SDN List", "item": BASE + "/"},
        ],
    }
    title = "OFAC SDN List in JSON &amp; CSV — %s Entries, Updated %s" % (
        "{:,}".format(c["entries"]), card["published"])
    desc = ("Download the U.S. Treasury OFAC Specially Designated Nationals (SDN) list as "
            "clean JSON or CSV. %s designated entries, %s alternate names, parsed straight "
            "from OFAC's own export. Free, no signup, no API key."
            % ("{:,}".format(c["entries"]), "{:,}".format(c["alternateNames"])))

    prog_rows = "".join(
        "<tr><td><code>%s</code></td><td class=\"num\">%s</td></tr>" % (esc(p), "{:,}".format(n))
        for p, n in card.get("topPrograms", [])[:10]
    )
    type_rows = "".join(
        "<tr><td>%s</td><td class=\"num\">%s</td></tr>" % (esc(k), "{:,}".format(v))
        for k, v in sorted(tc.items(), key=lambda kv: -kv[1])
    )
    field_rows = "".join(
        "<tr><td><code>%s</code></td><td><code>%s</code></td><td>%s</td></tr>"
        % (esc(f["name"]), esc(f["type"]), esc(f["description"]))
        for f in card["fields"]
    )

    return PAGE % {
        "title": title,
        "desc": esc(desc),
        "base": BASE,
        "site": SITE,
        "ld": json.dumps(ld, ensure_ascii=False),
        "bc": json.dumps(bc, ensure_ascii=False),
        "published": esc(card["published"]),
        "retrieved": esc(card.get("retrieved") or card["published"]),
        "entries": "{:,}".format(c["entries"]),
        "alts": "{:,}".format(c["alternateNames"]),
        "total": "{:,}".format(c["totalNames"]),
        "json_size": mb(card["bytes"]["json"]),
        "csv_size": mb(card["bytes"]["csv"]),
        "prog_rows": prog_rows,
        "type_rows": type_rows,
        "field_rows": field_rows,
        "scope": esc(card["scope"]),
        "disclaimer": esc(card["disclaimer"]),
        "license": esc(card["license"]),
        "license_url": esc(card["licenseUrl"]),
        "source_url": esc(card["sourceUrl"]),
        "official": esc(card["officialSearchUrl"]),
    }


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>%(title)s | SanctionsAI</title>
<meta name="description" content="%(desc)s">
<meta name="robots" content="index, follow">
<link rel="canonical" href="%(base)s/">
<meta property="og:title" content="%(title)s">
<meta property="og:description" content="%(desc)s">
<meta property="og:type" content="website">
<meta property="og:url" content="%(base)s/">
<script type="application/ld+json">%(ld)s</script>
<script type="application/ld+json">%(bc)s</script>
<style>
:root{--bg:#fafbfc;--fg:#1a1a2e;--accent:#2563eb;--muted:#6b7280;--border:#e5e7eb;--card:#fff;--green:#059669}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--fg);line-height:1.7}
.container{max-width:960px;margin:0 auto;padding:2rem 1.5rem}
h1{font-size:2.1rem;font-weight:800;margin-bottom:.5rem;line-height:1.25}
h2{font-size:1.4rem;font-weight:700;margin:2.25rem 0 .75rem}
h3{font-size:1.1rem;font-weight:600;margin:1.5rem 0 .5rem}
p{margin-bottom:.9rem}
.lead{font-size:1.12rem;color:var(--muted);margin-bottom:1.25rem}
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:1.5rem;margin-bottom:1rem}
table{width:100%%;border-collapse:collapse;margin:1rem 0;font-size:.92rem}
th,td{padding:.6rem .9rem;text-align:left;border-bottom:1px solid var(--border);vertical-align:top}
th{background:var(--bg);font-weight:600;color:var(--muted);font-size:.78rem;text-transform:uppercase;letter-spacing:.05em}
td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
code{background:#eef2f7;padding:.12rem .35rem;border-radius:4px;font-size:.88em}
pre{background:#1e293b;color:#e2e8f0;padding:1rem;border-radius:8px;overflow-x:auto;font-size:.83rem;margin:.5rem 0 1rem}
pre code{background:none;padding:0;color:inherit}
.stats{display:flex;flex-wrap:wrap;gap:1rem;margin:1.5rem 0}
.stat{flex:1;min-width:140px;background:var(--card);border:1px solid var(--border);border-radius:10px;padding:1rem}
.stat .n{font-size:1.7rem;font-weight:800;color:var(--accent);font-variant-numeric:tabular-nums;line-height:1.1}
.stat .l{font-size:.78rem;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin-top:.2rem}
.dl{display:flex;flex-wrap:wrap;gap:.75rem;margin:1.25rem 0}
.btn{display:inline-block;padding:.7rem 1.4rem;border-radius:8px;font-weight:600;text-decoration:none;font-size:.95rem}
.btn-primary{background:var(--accent);color:#fff}
.btn-outline{border:2px solid var(--border);color:var(--fg)}
/* Literal colours, not var(--fg): these boxes hardcode a LIGHT background, so
   their text must hardcode a dark colour to match. The sitewide stylesheet is
   injected after this one and themes the page dark, which re-colours anything
   left to inherit — that put the scope disclaimer at 1.7:1 contrast, the one
   paragraph on this page a reader most needs to be able to read. */
.note{border-radius:8px;padding:1rem 1.15rem;margin:1.25rem 0;font-size:.9rem;color:#1a1a2e}
.note p,.note strong,.note em{color:#1a1a2e}
.note a{color:#1d4ed8}
.note-warn{background:#fef3c7;border:1px solid #fcd34d}
.note-info{background:#f0f7ff;border:1px solid #bfdbfe}
/* Deliberately NOT applied to the tables: they inherit the dark theme's light
   text on a dark surface and read fine. Forcing dark text there would produce
   the mirror-image bug. Only elements that carry their OWN light background
   are re-coloured here. */
.breadcrumb{font-size:.85rem;color:var(--muted);margin-bottom:1.25rem}
.breadcrumb a{color:var(--muted);text-decoration:none}
footer{margin-top:3rem;padding:1.5rem 0;border-top:1px solid var(--border);color:var(--muted);font-size:.85rem}
a{color:var(--accent)}
@media(max-width:640px){.container{padding:1rem}h1{font-size:1.55rem}}
</style>
</head>
<body>
<div class="container">
<nav class="breadcrumb"><a href="/">Home</a> &rsaquo; <a href="/data/">Research Data</a> &rsaquo; OFAC SDN List</nav>

<h1>OFAC SDN list, as JSON and CSV</h1>
<p class="lead">The U.S. Treasury's Specially Designated Nationals list, parsed straight from
OFAC's own export into two files you can actually load. No signup, no API key, no rate limit.</p>

<div class="stats">
<div class="stat"><div class="n">%(entries)s</div><div class="l">Designated entries</div></div>
<div class="stat"><div class="n">%(alts)s</div><div class="l">Alternate names</div></div>
<div class="stat"><div class="n">%(total)s</div><div class="l">Names total</div></div>
<div class="stat"><div class="n">%(published)s</div><div class="l">OFAC publication date</div></div>
</div>

<div class="dl">
<a class="btn btn-primary" href="%(base)s/ofac-sdn.json" download>Download JSON &middot; %(json_size)s</a>
<a class="btn btn-outline" href="%(base)s/ofac-sdn.csv" download>Download CSV &middot; %(csv_size)s</a>
<a class="btn btn-outline" href="%(base)s/metadata.json">metadata.json</a>
</div>

<p style="font-size:.88rem;color:var(--muted)">Published by OFAC on <strong>%(published)s</strong>;
retrieved and parsed on <strong>%(retrieved)s</strong>. The publication date is OFAC's own, read from
the export URL &mdash; not our build date.</p>

<h2>Why this exists</h2>
<p>OFAC publishes the SDN list, but it publishes it as a headerless CSV with a separate
alternate-names file, a bracketed multi-value program column, and <code>-0-</code> standing in for
empty fields. Every team that needs it writes the same parser. This is that parser's output,
rebuilt from source and republished so you don't have to.</p>
<p>Names, types and program codes are OFAC's own strings, unmodified. The only transformations are
splitting the bracketed program field into a list and joining alternate names onto their primary
entry by <code>uid</code>.</p>

<h2>Schema</h2>
<table><thead><tr><th>Field</th><th>Type</th><th>Description</th></tr></thead>
<tbody>%(field_rows)s</tbody></table>

<h3>One record</h3>
<pre><code>{
 "uid": 36,
 "name": "AEROCARIBBEAN AIRLINES",
 "type": "entity",
 "programs": ["CUBA"],
 "alternateNames": ["AERO-CARIBBEAN"]
}</code></pre>

<h2>Load it</h2>
<pre><code># Python
import urllib.request, json
url = "%(base)s/ofac-sdn.json"
data = json.load(urllib.request.urlopen(url))
print(data["published"], len(data["entries"]))</code></pre>
<pre><code># Shell
curl -s %(base)s/ofac-sdn.csv -o ofac-sdn.csv</code></pre>
<pre><code>// JavaScript
const res = await fetch("%(base)s/ofac-sdn.json");
const { published, entries } = await res.json();</code></pre>

<h2>What's in it</h2>
<h3>By entity type</h3>
<table><thead><tr><th>Type</th><th style="text-align:right">Entries</th></tr></thead>
<tbody>%(type_rows)s</tbody></table>
<h3>Largest sanctions programs</h3>
<table><thead><tr><th>Program</th><th style="text-align:right">Entries</th></tr></thead>
<tbody>%(prog_rows)s</tbody></table>

<h2>Scope &mdash; read this before you rely on it</h2>
<div class="note note-warn">
<p style="margin:0 0 .6rem"><strong>%(scope)s</strong></p>
<p style="margin:0">%(disclaimer)s</p>
</div>

<h2>Licence and citation</h2>
<p>%(license)s See <a href="%(license_url)s" rel="license">CC0 1.0</a>.
Source export: <a href="%(source_url)s">OFAC SDN.CSV</a>.
Authoritative search: <a href="%(official)s">sanctionssearch.ofac.treas.gov</a>.</p>
<div class="note note-info">
<p style="margin:0 0 .4rem"><strong>Cite as</strong></p>
<p style="margin:0;font-size:.86rem">U.S. Department of the Treasury, Office of Foreign Assets Control.
<em>Specially Designated Nationals and Blocked Persons List</em>, published %(published)s.
Machine-readable edition, SanctionsAI, <a href="%(base)s/">%(base)s/</a>.</p>
</div>

<h2>Related</h2>
<ul style="margin:0 0 1rem 1.25rem">
<li><a href="/free/ofac-screening">Free browser screener</a> &mdash; paste a list of names, screen it against this data client-side. Nothing leaves your machine.</li>
<li><a href="/docs">Screening API</a> &mdash; the hosted endpoint, if you want matching, fuzzy logic and wallet screening rather than raw files.</li>
<li><a href="/data/">All research data</a></li>
</ul>

<footer>
<p><strong>SanctionsAI</strong> &mdash; OFAC sanctions screening for AI agents</p>
<p><a href="%(site)s">sanctionsai.dev</a> &middot; <a href="/data/">Research Data</a> &middot; <a href="/llms.txt">llms.txt</a></p>
</footer>
</div>
</body>
</html>
"""


def main():
    if not os.path.isfile(INDEX):
        sys.exit("missing %s — run scripts/build_sdn_index.py first" % INDEX)
    with open(INDEX, "r", encoding="utf-8") as fh:
        idx = json.load(fh)
    with open(INDEX_META, "r", encoding="utf-8") as fh:
        meta = json.load(fh)

    entries = idx.get("entries") or []
    if len(entries) < 5000:
        sys.exit("only %d entries in the index — refusing to publish a truncated dataset" % len(entries))

    published = idx.get("published")
    if not published:
        sys.exit("the index carries no OFAC publication date — refusing to publish an undated dataset")

    os.makedirs(OUTDIR, exist_ok=True)

    records = []
    for ent, name, typ, prog, alts in entries:
        records.append({
            "uid": ent,
            "name": name,
            "type": typ,
            "programs": split_programs(prog),
            "alternateNames": alts or [],
        })
    records.sort(key=lambda r: r["uid"])

    card = {
        "name": "OFAC Specially Designated Nationals (SDN) List — machine-readable",
        "description": (
            "The U.S. Treasury OFAC SDN list parsed into JSON and CSV: %d designated "
            "entries and %d alternate identities (%d names total), each with its OFAC "
            "uid, entity type and sanctions programs. Published %s by OFAC."
            % (
                meta["counts"]["entries"],
                meta["counts"]["alternateNames"],
                meta["counts"]["totalNames"],
                published,
            )
        ),
        "source": idx["source"],
        "sourceUrl": idx["sourceUrl"],
        "altSourceUrl": idx["altSourceUrl"],
        "officialSearchUrl": idx["officialSearchUrl"],
        "published": published,
        "retrieved": idx.get("retrieved"),
        "counts": meta["counts"],
        "typeCounts": meta.get("typeCounts", {}),
        "topPrograms": meta.get("topPrograms", []),
        "scope": idx["scope"],
        "disclaimer": DISCLAIMER,
        "license": "CC0-1.0 (packaging). The underlying list is a U.S. Government work in the public domain (17 U.S.C. 105).",
        "licenseUrl": LICENSE_URL,
        "landingPage": BASE + "/",
        "distributions": [
            {"format": "JSON", "url": BASE + "/ofac-sdn.json", "mediaType": "application/json"},
            {"format": "CSV", "url": BASE + "/ofac-sdn.csv", "mediaType": "text/csv"},
        ],
        "fields": [
            {"name": "uid", "type": "integer", "description": "OFAC's own entity number (ent_num) for the designated party."},
            {"name": "name", "type": "string", "description": "Primary designated name, verbatim from OFAC's SDN.CSV."},
            {"name": "type", "type": "string", "description": "individual, entity, vessel or aircraft."},
            {"name": "programs", "type": "array<string>", "description": "OFAC sanctions program codes, e.g. RUSSIA-EO14024, SDGT."},
            {"name": "alternateNames", "type": "array<string>", "description": "AKAs joined from OFAC's ALT.CSV on the same uid."},
        ],
    }

    payload = dict(card)
    payload["entries"] = records
    with open(os.path.join(OUTDIR, "ofac-sdn.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)

    with open(os.path.join(OUTDIR, "ofac-sdn.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["uid", "name", "type", "programs", "alternate_names"])
        for r in records:
            w.writerow([
                r["uid"],
                r["name"],
                r["type"],
                "; ".join(r["programs"]),
                "; ".join(r["alternateNames"]),
            ])

    card["bytes"] = {
        "json": os.path.getsize(os.path.join(OUTDIR, "ofac-sdn.json")),
        "csv": os.path.getsize(os.path.join(OUTDIR, "ofac-sdn.csv")),
    }
    with open(os.path.join(OUTDIR, "metadata.json"), "w", encoding="utf-8") as fh:
        json.dump(card, fh, ensure_ascii=False, indent=1)

    with open(os.path.join(OUTDIR, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(render_page(card))

    print("OFAC SDN dataset built")
    print("  OFAC published : %s" % published)
    print("  records        : %d" % len(records))
    print("  json           : %.2f MB" % (card["bytes"]["json"] / 1048576.0))
    print("  csv            : %.2f MB" % (card["bytes"]["csv"] / 1048576.0))


if __name__ == "__main__":
    main()
