#!/usr/bin/env python3
"""Build the OFAC SDN Change Log served at /updates/.

Source of truth is OFAC's own Delta File — the official, machine-readable record
of every entity added to, removed from, or modified on the sanctions lists in a
given publication:

    https://sanctionslistservice.ofac.treas.gov/changes/latest

Nothing on the generated pages is inferred, summarised by a model, or editorial.
Names, aliases, addresses, programs, legal authorities and identity documents are
rendered verbatim from the delta. The only derived values are counts (len() of a
list) and the URL slug. If a field is absent from OFAC's file it is absent from
the page — there are no placeholders and no "unknown" filler.

Why this exists: every other page on sanctionsai.dev is commentary that competes
with Chainalysis and ComplyAdvantage on head terms. This is the one surface where
the site holds primary-source material nobody else has packaged — and it renews
itself on OFAC's publication cadence, so the archive compounds. Publication IDs
in OFAC's API are UUIDs and are not enumerable, so history cannot be back-filled:
each publication is only capturable while it is `latest`. That is precisely why
the raw XML is archived to data/sdn-deltas/ on every run and never deleted —
the archive IS the asset, and a missed run is a permanent hole in it.

Run:   python3 scripts/build_sdn_updates.py
Flags: --offline   rebuild pages from the existing archive, fetch nothing
Out:   updates/                 hub, per-publication and per-entity pages, feeds
       data/sdn-deltas/         raw XML + normalised JSON, one pair per publication
       public/updates-sitemap.xml
Exit:  0 on success (whether or not the publication was new), 1 on a hard failure.
"""
import argparse
import html
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

SITE = "https://sanctionsai.dev"
DELTA_URL = "https://sanctionslistservice.ofac.treas.gov/changes/latest"
OFAC_SEARCH = "https://sanctionssearch.ofac.treas.gov/"
OFAC_RECENT = "https://ofac.treasury.gov/recent-actions"

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE = os.path.join(HERE, "data", "sdn-deltas")
OUT = os.path.join(HERE, "updates")
# Lives inside updates/ so one Dockerfile COPY ships the whole surface, and so it
# is served by the same handler — which returns a real 404 on a miss.
SITEMAP = os.path.join(OUT, "sitemap.xml")

ACTION_LABEL = {
    "add": "Added",
    "remove": "Removed",
    "change": "Modified",
    "modify": "Modified",
    "update": "Modified",
}

DISCLAIMER = (
    "This page reproduces a public record published by the U.S. Department of the "
    "Treasury's Office of Foreign Assets Control. It is provided for informational "
    "purposes and is not legal or compliance advice. OFAC's published list is the "
    "only authoritative source; confirm any name against "
    '<a href="%s" rel="nofollow noopener">OFAC Sanctions List Search</a> before '
    "acting on it." % OFAC_SEARCH
)


# --------------------------------------------------------------------------
# fetch + parse
# --------------------------------------------------------------------------

def strip_ns(tag):
    return re.sub(r"\{.*?\}", "", tag)


def fetch_delta():
    """Download the current delta file. Returns raw bytes."""
    r = subprocess.run(
        ["curl", "-sL", "--max-time", "120", DELTA_URL],
        capture_output=True,
    )
    if r.returncode != 0:
        sys.exit("curl failed for %s: %s" % (DELTA_URL, r.stderr.decode()[:300]))
    body = r.stdout
    if len(body) < 500:
        sys.exit("delta response was %d bytes — refusing to archive a truncated file" % len(body))
    try:
        ET.fromstring(body)
    except ET.ParseError as e:
        sys.exit("delta file did not parse as XML (%s) — refusing to archive it" % e)
    return body


def child_text(node, name):
    for c in node:
        if strip_ns(c.tag) == name:
            return (c.text or "").strip()
    return ""


def children(node, name):
    return [c for c in node if strip_ns(c.tag) == name]


def descendants(node, name):
    return [c for c in node.iter() if strip_ns(c.tag) == name]


def parse_names(entity):
    """Every name OFAC carries for the entity, across every script."""
    out = []
    for name in descendants(entity, "name"):
        # identityDocument also has a <name> child; those are documents, not names
        if strip_ns(name.tag) != "name" or not children(name, "translations"):
            continue
        alias_type = child_text(name, "aliasType")
        is_primary = child_text(name, "isPrimary") == "true"
        low_quality = child_text(name, "isLowQuality") == "true"
        for tr in descendants(name, "translation"):
            full = child_text(tr, "formattedFullName")
            if not full:
                continue
            # nameParts carry OFAC's own natural casing ("Zanjani"), where the
            # formatted* fields carry the display casing ("ZANJANI"). Prefer the
            # parts so a headline never shouts a surname — this is OFAC's string
            # either way, not a case transformation of ours.
            parts = {}
            for np in descendants(tr, "namePart"):
                ptype = child_text(np, "type")
                pval = child_text(np, "value")
                if ptype and pval:
                    parts[ptype] = pval
            out.append({
                "full": full,
                "first": parts.get("First Name") or child_text(tr, "formattedFirstName"),
                "middle": parts.get("Middle Name"),
                "last": parts.get("Last Name") or child_text(tr, "formattedLastName"),
                "script": child_text(tr, "script"),
                "aliasType": alias_type,
                "isPrimary": is_primary and child_text(tr, "isPrimary") == "true",
                "isLowQuality": low_quality,
            })
    return out


def parse_addresses(entity):
    out = []
    for addr in descendants(entity, "address"):
        country = child_text(addr, "country")
        for tr in descendants(addr, "translation"):
            parts = []
            for part in descendants(tr, "addressPart"):
                val = child_text(part, "value")
                if val:
                    parts.append({"type": child_text(part, "type"), "value": val})
            if parts or country:
                out.append({
                    "country": country,
                    "script": child_text(tr, "script"),
                    "parts": parts,
                })
    return out


def parse_features(entity):
    out = []
    for feat in descendants(entity, "feature"):
        val = child_text(feat, "value")
        typ = child_text(feat, "type")
        if not typ:
            continue
        out.append({
            "type": typ.rstrip(":- ").strip(),
            "value": val,
            "reliability": child_text(feat, "reliability"),
        })
    return out


def parse_documents(entity):
    out = []
    for doc in descendants(entity, "identityDocument"):
        num = child_text(doc, "documentNumber")
        typ = child_text(doc, "type")
        if not typ:
            continue
        out.append({
            "type": typ,
            "number": num,
            "country": child_text(doc, "issuingCountry"),
            "isValid": child_text(doc, "isValid") == "true",
            "expires": child_text(doc, "expirationDate"),
        })
    return out


def parse_relationships(entity):
    out = []
    for rel in descendants(entity, "relationship"):
        related = children(rel, "relatedEntity")
        out.append({
            "type": child_text(rel, "type"),
            "relatedEntity": (related[0].text or "").strip() if related else "",
            "relatedEntityId": related[0].get("entityId") if related else "",
        })
    return [r for r in out if r["type"] or r["relatedEntity"]]


def slugify(text, fallback):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    return s[:80].strip("-") or fallback


def display_name(entity_type, names):
    """OFAC's own primary rendering, plus a natural-order form for individuals.

    The natural-order form is a join of OFAC's own formattedFirstName and
    formattedLastName fields — not a re-parse of the full name — so it cannot
    reorder a name incorrectly. Where OFAC gives no first name (entities,
    vessels) it is simply absent.
    """
    primary = next((n for n in names if n["isPrimary"] and n["script"] == "Latin"), None)
    if primary is None:
        primary = next((n for n in names if n["script"] == "Latin"), None)
    if primary is None:
        primary = names[0] if names else None
    if primary is None:
        return "", ""
    official = primary["full"]
    natural = official
    if entity_type == "Individual" and primary.get("first") and primary.get("last"):
        natural = " ".join(x for x in (primary["first"], primary.get("middle"),
                                       primary["last"]) if x)
    return official, natural


def parse_delta(raw, published_fallback=None):
    root = ET.fromstring(raw)
    pubinfo = descendants(root, "publicationInfo")
    date_published = ""
    pub_type = ""
    if pubinfo:
        date_published = child_text(pubinfo[0], "datePublished")
        pub_type = child_text(pubinfo[0], "publicationType")
    date_only = (date_published or published_fallback or "")[:10]
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_only):
        sys.exit("delta file carried no usable datePublished — refusing to build an undated page")

    entities = []
    for e in descendants(root, "entity"):
        if not children(e, "generalInfo"):
            continue
        names = parse_names(e)
        etype = ""
        gi = children(e, "generalInfo")
        if gi:
            etype = child_text(gi[0], "entityType")
        official, natural = display_name(etype, names)
        if not official:
            continue
        entities.append({
            "id": e.get("id") or "",
            "action": (e.get("action") or "").lower(),
            "type": etype or "Entity",
            "officialName": official,
            "displayName": natural,
            "names": names,
            "programs": [c.text.strip() for c in descendants(e, "sanctionsProgram") if c.text],
            "lists": [c.text.strip() for c in descendants(e, "sanctionsList") if c.text],
            "sanctionsTypes": [c.text.strip() for c in descendants(e, "sanctionsType") if c.text],
            "legalAuthorities": [c.text.strip() for c in descendants(e, "legalAuthority") if c.text],
            "addresses": parse_addresses(e),
            "features": parse_features(e),
            "documents": parse_documents(e),
            "relationships": parse_relationships(e),
        })

    # slugs are assigned after sorting so they are stable across rebuilds
    entities.sort(key=lambda x: (x["action"], x["officialName"]))
    seen = {}
    for ent in entities:
        base = slugify(ent["displayName"] or ent["officialName"], "entity-%s" % ent["id"])
        if base in seen:
            base = "%s-%s" % (base, ent["id"])
        seen[base] = True
        ent["slug"] = base

    return {
        "datePublished": date_only,
        "publicationType": pub_type,
        "retrieved": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sourceUrl": DELTA_URL,
        "entities": entities,
        "counts": {
            "total": len(entities),
            "add": sum(1 for e in entities if e["action"] == "add"),
            "remove": sum(1 for e in entities if e["action"] == "remove"),
            "other": sum(1 for e in entities if e["action"] not in ("add", "remove")),
        },
    }


# --------------------------------------------------------------------------
# archive
# --------------------------------------------------------------------------

def capture(offline):
    """Fetch the current delta and archive it if we have not seen it before.

    Returns (is_new, date_published_or_None).
    """
    os.makedirs(ARCHIVE, exist_ok=True)
    if offline:
        return False, None
    raw = fetch_delta()
    parsed = parse_delta(raw)
    date = parsed["datePublished"]
    xml_path = os.path.join(ARCHIVE, "%s.xml" % date)
    json_path = os.path.join(ARCHIVE, "%s.json" % date)
    is_new = not os.path.exists(json_path)
    # Rewrite even when not new: OFAC can republish a correction under the same
    # date, and the archived copy should be the current one. The first-seen
    # timestamp is preserved so the page can still say when we captured it.
    if not is_new:
        try:
            with open(json_path, encoding="utf-8") as fh:
                parsed["retrieved"] = json.load(fh).get("retrieved", parsed["retrieved"])
        except (OSError, ValueError):
            pass
    with open(xml_path, "wb") as fh:
        fh.write(raw)
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(parsed, fh, ensure_ascii=False, indent=1)
    return is_new, date


def load_archive():
    """Every captured publication, newest first.

    Re-parsed from the archived XML rather than the JSON beside it. The XML is
    exactly what OFAC served and is the canonical copy; the JSON is a derived
    artifact that also happens to be published at /updates/<date>/data.json.
    Deriving on every build means a parser fix applies retroactively to the whole
    archive instead of only to publications captured after the fix.
    """
    pubs = []
    if not os.path.isdir(ARCHIVE):
        return pubs
    for fn in sorted(os.listdir(ARCHIVE)):
        if not fn.endswith(".xml"):
            continue
        path = os.path.join(ARCHIVE, fn)
        try:
            with open(path, "rb") as fh:
                parsed = parse_delta(fh.read(), published_fallback=fn[:-4])
        except (OSError, ET.ParseError, SystemExit) as e:
            print("  ! skipping unreadable archive file %s (%s)" % (fn, e))
            continue
        # preserve the original capture timestamp recorded when first fetched
        json_path = os.path.join(ARCHIVE, "%s.json" % parsed["datePublished"])
        try:
            with open(json_path, encoding="utf-8") as fh:
                parsed["retrieved"] = json.load(fh).get("retrieved", parsed["retrieved"])
        except (OSError, ValueError):
            pass
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(parsed, fh, ensure_ascii=False, indent=1)
        pubs.append(parsed)
    pubs.sort(key=lambda p: p["datePublished"], reverse=True)
    return pubs


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

def esc(s):
    return html.escape(s or "", quote=True)


def human_date(iso):
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%-d %B %Y")
    except ValueError:
        return iso


CSS = (
    "body{font:16px/1.65 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;"
    "max-width:820px;margin:0 auto;padding:2rem 1rem;color:#0f172a;background:#fff}"
    "@media(prefers-color-scheme:dark){body{background:#0b1120;color:#e2e8f0}}"
    "h1{font-size:1.9rem;line-height:1.2;margin:.4rem 0 .6rem}"
    "h2{font-size:1.25rem;margin:2rem 0 .6rem}h3{font-size:1.05rem;margin:1.4rem 0 .4rem}"
    "a{color:#2563eb;text-decoration:none}a:hover{text-decoration:underline}"
    ".crumb{font-size:.85rem;color:#64748b}"
    ".lede{font-size:1.08rem}"
    ".src{font-size:.85rem;background:#f8fafc;border-left:3px solid #2563eb;padding:.9rem 1.1rem;"
    "border-radius:6px;margin:1.2rem 0}"
    "@media(prefers-color-scheme:dark){.src{background:#111a2e}}"
    ".card{border:1px solid #e2e8f0;border-radius:8px;padding:1rem 1.2rem;margin:1rem 0}"
    "@media(prefers-color-scheme:dark){.card{border-color:#1e293b}}"
    ".tag{display:inline-block;font-size:.75rem;font-weight:600;padding:.15rem .5rem;"
    "border-radius:4px;background:#e0e7ff;color:#3730a3;margin-right:.35rem}"
    "@media(prefers-color-scheme:dark){.tag{background:#1e1b4b;color:#c7d2fe}}"
    ".tag.rm{background:#fee2e2;color:#991b1b}"
    "@media(prefers-color-scheme:dark){.tag.rm{background:#450a0a;color:#fecaca}}"
    ".tag.ch{background:#fef3c7;color:#92400e}"
    "@media(prefers-color-scheme:dark){.tag.ch{background:#451a03;color:#fde68a}}"
    "table{border-collapse:collapse;width:100%;font-size:.92rem;margin:.6rem 0}"
    "th,td{text-align:left;padding:.35rem .6rem;border-bottom:1px solid #e2e8f0;vertical-align:top}"
    "@media(prefers-color-scheme:dark){th,td{border-color:#1e293b}}"
    "th{color:#64748b;font-weight:600;white-space:nowrap;width:1%}"
    ".rtl{direction:rtl;unicode-bidi:isolate}"
    ".disc{font-size:.85rem;color:#64748b;border-top:1px solid #e2e8f0;margin-top:2.5rem;padding-top:1rem}"
    "@media(prefers-color-scheme:dark){.disc{border-color:#1e293b}}"
    "ul{padding-left:1.2rem}li{margin:.2rem 0}"
    ".cta{background:#f1f5f9;border-radius:8px;padding:1rem 1.2rem;margin:1.6rem 0;font-size:.95rem}"
    "@media(prefers-color-scheme:dark){.cta{background:#111a2e}}"
)


def page(title, description, canonical, body, jsonld):
    blocks = "".join(
        '<script type="application/ld+json">%s</script>'
        % json.dumps(b, ensure_ascii=False, separators=(",", ":"))
        for b in jsonld
    )
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>%s</title><meta name=\"description\" content=\"%s\">"
        "<link rel=\"canonical\" href=\"%s\">"
        "<meta name=\"robots\" content=\"index,follow,max-snippet:-1,max-image-preview:large\">"
        "<link rel=\"alternate\" type=\"application/rss+xml\" title=\"OFAC SDN Change Log\" "
        "href=\"%s/updates/feed.xml\">"
        "<style>%s</style>%s</head><body>%s</body></html>"
    ) % (esc(title), esc(description), esc(canonical), SITE, CSS, blocks, body)


def action_tag(action):
    cls = {"add": "", "remove": " rm"}.get(action, " ch")
    return '<span class="tag%s">%s</span>' % (cls, esc(ACTION_LABEL.get(action, action.title() or "Changed")))


def render_entity_record(ent, date, detailed):
    """The factual record. `detailed` controls whether long tables are included."""
    rows = []

    def row(label, value):
        if value:
            rows.append("<tr><th>%s</th><td>%s</td></tr>" % (esc(label), value))

    row("Type", esc(ent["type"]))
    row("Sanctions program", ", ".join(esc(p) for p in ent["programs"]))
    row("List", ", ".join(esc(x) for x in ent["lists"]))
    row("Sanctions type", ", ".join(esc(x) for x in ent["sanctionsTypes"]))
    row("Legal authority", ", ".join(esc(x) for x in ent["legalAuthorities"]))
    row("Publication date", esc(human_date(date)))

    aliases = [n for n in ent["names"] if not n["isPrimary"]]
    if aliases:
        items = []
        for n in aliases[: (None if detailed else 6)]:
            cls = ' class="rtl"' if n["script"] and n["script"] != "Latin" else ""
            meta = " / ".join(x for x in (n["aliasType"], n["script"]) if x)
            extra = ' <span style="color:#64748b">(%s%s)</span>' % (
                esc(meta), ", low quality" if n["isLowQuality"] else "")
            items.append("<li><span%s>%s</span>%s</li>" % (cls, esc(n["full"]), extra if meta else ""))
        more = ""
        if not detailed and len(aliases) > 6:
            more = "<li>… and %d more</li>" % (len(aliases) - 6)
        row("Also known as", "<ul>%s%s</ul>" % ("".join(items), more))

    for f in ent["features"]:
        if f["value"]:
            row(f["type"], esc(f["value"]))

    if detailed and ent["addresses"]:
        items = []
        for a in ent["addresses"]:
            line = ", ".join(esc(p["value"]) for p in a["parts"])
            if a["country"]:
                line = ", ".join(x for x in (line, esc(a["country"])) if x)
            cls = ' class="rtl"' if a["script"] and a["script"] != "Latin" else ""
            items.append("<li><span%s>%s</span></li>" % (cls, line))
        row("Address", "<ul>%s</ul>" % "".join(items))

    if detailed and ent["documents"]:
        items = []
        for d in ent["documents"]:
            bits = [esc(d["type"])]
            if d["number"]:
                bits.append(esc(d["number"]))
            if d["country"]:
                bits.append("issued by %s" % esc(d["country"]))
            items.append("<li>%s</li>" % " — ".join(bits))
        row("Identification", "<ul>%s</ul>" % "".join(items))

    if detailed and ent["relationships"]:
        items = ["<li>%s: %s</li>" % (esc(r["type"]), esc(r["relatedEntity"]))
                 for r in ent["relationships"] if r["relatedEntity"]]
        if items:
            row("Linked to", "<ul>%s</ul>" % "".join(items))

    return "<table>%s</table>" % "".join(rows)


def render_entity_page(ent, pub):
    date = pub["datePublished"]
    name = ent["displayName"] or ent["officialName"]
    canonical = "%s/updates/entity/%s" % (SITE, ent["slug"])
    verbed = {"add": "added", "remove": "removed"}.get(ent["action"], "modified")
    prep = {"add": "to", "remove": "from"}.get(ent["action"], "on")
    programs = ", ".join(ent["programs"])

    title = "Is %s sanctioned? OFAC SDN List, %s %s" % (
        name, verbed, human_date(date))
    desc = ("OFAC %s %s %s the Specially Designated Nationals (SDN) List on %s%s. "
            "Full record: aliases, identifiers and legal authority, verbatim from Treasury's "
            "published delta file." % (
                verbed, name, prep, human_date(date),
                (" under %s" % programs) if programs else ""))

    # Direct answer first, in the page's own words but strictly within what the
    # delta says. The scope caveat is not boilerplate: a name on the list is not
    # the same fact as the person in front of you being that listee, and a page
    # that blurs the two would be actively harmful to someone screening.
    if ent["action"] == "remove":
        answer = ("<strong>Not currently, on this record.</strong> OFAC <strong>removed</strong> "
                  "this listing from the Specially Designated Nationals and Blocked Persons (SDN) "
                  "List in the publication dated %s.") % esc(human_date(date))
    elif ent["action"] == "add":
        answer = ("<strong>Yes — a record under this name is on the OFAC SDN List.</strong> "
                  "OFAC <strong>added</strong> it on %s%s.") % (
            esc(human_date(date)), (" under %s" % esc(programs)) if programs else "")
    else:
        answer = ("<strong>Yes — a record under this name is on the OFAC SDN List</strong>, and "
                  "OFAC <strong>modified</strong> it in the publication dated %s.") % esc(human_date(date))
    answer += (" A name match is not an identity match: confirm the identifiers below against "
               "the party you are screening before you treat them as the same person or entity.")

    alias_count = len([n for n in ent["names"] if not n["isPrimary"]])
    alias_note = ""
    if alias_count:
        alias_note = (
            "<p>OFAC lists <strong>%d alternate spelling%s</strong> for this record. A screening "
            "system that only matches the primary name will miss the rest, which is the most "
            "common reason a listed party clears a check.</p>" % (
                alias_count, "" if alias_count == 1 else "s"))

    body = (
        '<p class="crumb"><a href="/">SanctionsAI</a> › <a href="/updates/">SDN Change Log</a> › '
        '<a href="/updates/%s/">%s</a> › %s</p>'
        "<h1>Is %s sanctioned?</h1>"
        '<p class="lede">%s %s Published in the OFAC delta dated '
        '<a href="/updates/%s/">%s</a>.</p>'
        '<div class="src"><strong>Source:</strong> U.S. Department of the Treasury, Office of '
        'Foreign Assets Control — official delta file for the %s publication '
        '(<a href="/updates/%s/data.json">machine-readable copy</a>). '
        'Verify at <a href="%s" rel="nofollow noopener">OFAC Sanctions List Search</a>.</div>'
        "<h2>Record as published</h2>%s"
        "%s"
        '<div class="cta"><strong>Screening against this list in code?</strong> SanctionsAI '
        'exposes the whole SDN list — every alias included — over an HTTP API, CLI and MCP '
        'server. <a href="/docs">Read the docs →</a> or run a name through the '
        '<a href="/tools/name-checker">free name checker</a>.</div>'
        "<h2>Other records in this publication</h2>"
        '<p><a href="/updates/%s/">See all %d changes published on %s →</a></p>'
        '<p class="disc">%s</p>'
    ) % (
        esc(date), esc(human_date(date)), esc(name),
        esc(name),
        action_tag(ent["action"]), answer,
        esc(date), esc(human_date(date)),
        esc(human_date(date)), esc(date), OFAC_SEARCH,
        render_entity_record(ent, date, detailed=True),
        alias_note,
        esc(date), pub["counts"]["total"], esc(human_date(date)),
        DISCLAIMER,
    )

    jsonld = [
        {
            "@context": "https://schema.org",
            "@type": "Article",
            "@id": canonical + "#article",
            "headline": title[:110],
            "description": desc[:300],
            "datePublished": date,
            "dateModified": date,
            "inLanguage": "en",
            "isPartOf": {"@type": "WebSite", "@id": SITE + "#website", "name": "SanctionsAI", "url": SITE},
            "publisher": {"@type": "Organization", "@id": SITE + "#org", "name": "SanctionsAI", "url": SITE},
            "citation": {
                "@type": "CreativeWork",
                "name": "OFAC sanctions list delta file, %s" % date,
                "url": DELTA_URL,
                "publisher": {"@type": "GovernmentOrganization",
                              "name": "U.S. Department of the Treasury, Office of Foreign Assets Control"},
            },
        },
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "SanctionsAI", "item": SITE},
                {"@type": "ListItem", "position": 2, "name": "SDN Change Log", "item": SITE + "/updates/"},
                {"@type": "ListItem", "position": 3, "name": human_date(date),
                 "item": "%s/updates/%s/" % (SITE, date)},
                {"@type": "ListItem", "position": 4, "name": name, "item": canonical},
            ],
        },
    ]
    return page(title, desc, canonical, body, jsonld)


def render_publication_page(pub, newer, older):
    date = pub["datePublished"]
    c = pub["counts"]
    # trailing slash deliberately: every internal link and the sitemap entry use
    # the slash form, and the handler serves both, so a slashless canonical would
    # point Google at a URL nothing links to.
    canonical = "%s/updates/%s/" % (SITE, date)
    programs = sorted({p for e in pub["entities"] for p in e["programs"]})

    parts = []
    if c["add"]:
        parts.append("%d addition%s" % (c["add"], "" if c["add"] == 1 else "s"))
    if c["remove"]:
        parts.append("%d removal%s" % (c["remove"], "" if c["remove"] == 1 else "s"))
    if c["other"]:
        parts.append("%d modification%s" % (c["other"], "" if c["other"] == 1 else "s"))
    summary = ", ".join(parts) or "no entity-level changes"

    title = "OFAC SDN List Update — %s (%s)" % (human_date(date), summary)
    desc = ("Every change OFAC published to the SDN List on %s: %s. Names, aliases, programs and "
            "legal authorities verbatim from Treasury's official delta file, plus a machine-readable "
            "JSON copy." % (human_date(date), summary))

    cards = []
    for ent in pub["entities"]:
        cards.append(
            '<div class="card">%s<h3><a href="/updates/entity/%s">%s</a></h3>%s</div>' % (
                action_tag(ent["action"]), esc(ent["slug"]),
                esc(ent["displayName"] or ent["officialName"]),
                render_entity_record(ent, date, detailed=False),
            ))

    nav = []
    if newer:
        nav.append('<a href="/updates/%s/">← %s (newer)</a>' % (esc(newer), esc(human_date(newer))))
    if older:
        nav.append('<a href="/updates/%s/">%s (older) →</a>' % (esc(older), esc(human_date(older))))

    body = (
        '<p class="crumb"><a href="/">SanctionsAI</a> › <a href="/updates/">SDN Change Log</a> › %s</p>'
        "<h1>OFAC SDN List Update — %s</h1>"
        '<p class="lede">OFAC published %s to the Specially Designated Nationals and Blocked '
        "Persons (SDN) List on %s%s.</p>"
        '<div class="src"><strong>Source:</strong> U.S. Department of the Treasury, Office of Foreign '
        'Assets Control — official delta file, publication type "%s". Captured %s. '
        'Machine-readable copy: <a href="/updates/%s/data.json">data.json</a> · '
        'Raw OFAC XML archived as published. '
        'Cross-check at <a href="%s" rel="nofollow noopener">OFAC Recent Actions</a>.</div>'
        "%s"
        "<h2>Changes in this publication</h2>%s"
        '<div class="cta"><strong>Track this automatically.</strong> Subscribe to the '
        '<a href="/updates/feed.xml">RSS feed</a> or the <a href="/updates/feed.json">JSON feed</a>, '
        'or screen names and wallets against the full list through the '
        '<a href="/docs">SanctionsAI API</a>.</div>'
        "%s"
        '<p class="disc">%s</p>'
    ) % (
        esc(human_date(date)),
        esc(human_date(date)),
        esc(summary), esc(human_date(date)),
        (" affecting %s" % esc(", ".join(programs))) if programs else "",
        esc(pub.get("publicationType") or "Standard Action"),
        esc(pub.get("retrieved", "")[:10]),
        esc(date), OFAC_RECENT,
        ("<p><strong>Programs affected:</strong> %s</p>" % esc(", ".join(programs))) if programs else "",
        "".join(cards) or "<p>OFAC published this delta with no entity-level changes.</p>",
        ('<p class="crumb">%s</p>' % " · ".join(nav)) if nav else "",
        DISCLAIMER,
    )

    jsonld = [
        {
            "@context": "https://schema.org",
            "@type": "Dataset",
            "@id": canonical + "#dataset",
            "name": "OFAC SDN List changes published %s" % human_date(date),
            "description": desc[:300],
            "datePublished": date,
            "dateModified": date,
            "license": "https://www.usa.gov/government-works",
            "isAccessibleForFree": True,
            "creator": {"@type": "GovernmentOrganization",
                        "name": "U.S. Department of the Treasury, Office of Foreign Assets Control",
                        "url": "https://ofac.treasury.gov/"},
            "publisher": {"@type": "Organization", "@id": SITE + "#org", "name": "SanctionsAI", "url": SITE},
            "distribution": [{
                "@type": "DataDownload",
                "encodingFormat": "application/json",
                "contentUrl": "%s/updates/%s/data.json" % (SITE, date),
            }],
            "variableMeasured": ["entity name", "alias", "sanctions program",
                                 "legal authority", "change action"],
        },
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "SanctionsAI", "item": SITE},
                {"@type": "ListItem", "position": 2, "name": "SDN Change Log", "item": SITE + "/updates/"},
                {"@type": "ListItem", "position": 3, "name": human_date(date), "item": canonical},
            ],
        },
    ]
    return page(title, desc, canonical, body, jsonld)


def render_hub(pubs):
    canonical = SITE + "/updates/"
    total_changes = sum(p["counts"]["total"] for p in pubs)
    latest = pubs[0] if pubs else None

    title = "OFAC SDN List Change Log — every update, with the full record"
    desc = ("A dated archive of every change OFAC publishes to the SDN List: who was added, who was "
            "removed, under which program and legal authority — verbatim from Treasury's official "
            "delta file, with RSS and JSON feeds.")

    rows = []
    for p in pubs:
        c = p["counts"]
        bits = []
        if c["add"]:
            bits.append("%d added" % c["add"])
        if c["remove"]:
            bits.append("%d removed" % c["remove"])
        if c["other"]:
            bits.append("%d modified" % c["other"])
        programs = sorted({pr for e in p["entities"] for pr in e["programs"]})
        rows.append(
            "<tr><th><a href=\"/updates/%s/\">%s</a></th><td>%s%s</td></tr>" % (
                esc(p["datePublished"]), esc(human_date(p["datePublished"])),
                esc(", ".join(bits) or "no entity-level changes"),
                (" — %s" % esc(", ".join(programs))) if programs else "",
            ))

    latest_block = ""
    if latest:
        names = [e["displayName"] or e["officialName"] for e in latest["entities"][:8]]
        latest_block = (
            "<h2>Most recent publication — %s</h2>"
            "<p>%s. %s</p>"
            '<p><a href="/updates/%s/">Read the full record →</a></p>'
        ) % (
            esc(human_date(latest["datePublished"])),
            esc(", ".join(
                "%d %s" % (latest["counts"][k], lbl)
                for k, lbl in (("add", "added"), ("remove", "removed"), ("other", "modified"))
                if latest["counts"][k]) or "No entity-level changes"),
            ("Includes " + esc(", ".join(names)) + ".") if names else "",
            esc(latest["datePublished"]),
        )

    body = (
        '<p class="crumb"><a href="/">SanctionsAI</a> › SDN Change Log</p>'
        "<h1>OFAC SDN List Change Log</h1>"
        '<p class="lede">OFAC amends the Specially Designated Nationals list without warning, and the '
        "official announcement is prose. This is the same information as structured data: every "
        "publication we have captured, every entity added, removed or modified, with the aliases and "
        "identifiers that screening actually depends on.</p>"
        '<div class="src"><strong>Source:</strong> the U.S. Treasury Office of Foreign Assets Control '
        "delta file — OFAC's own machine-readable record of each publication. Nothing here is "
        "summarised or interpreted; fields are reproduced as published. "
        '<strong>%d change%s across %d publication%s</strong> captured so far.</div>'
        "%s"
        '<div class="cta"><strong>Feeds.</strong> '
        '<a href="/updates/feed.xml">RSS</a> · <a href="/updates/feed.json">JSON Feed</a> — '
        "new entry on every OFAC publication. Free to consume, no key. "
        "Screening in code? The <a href=\"/docs\">SanctionsAI API</a> checks names and wallets "
        "against the full list.</div>"
        "<h2>Archive</h2><table>%s</table>"
        '<p class="disc">%s</p>'
    ) % (
        total_changes, "" if total_changes == 1 else "s",
        len(pubs), "" if len(pubs) == 1 else "s",
        latest_block,
        "".join(rows) or "<tr><td>No publications captured yet.</td></tr>",
        DISCLAIMER,
    )

    jsonld = [
        {
            "@context": "https://schema.org",
            "@type": "Dataset",
            "@id": canonical + "#dataset",
            "name": "OFAC SDN List Change Log",
            "description": desc,
            "url": canonical,
            "license": "https://www.usa.gov/government-works",
            "isAccessibleForFree": True,
            "creator": {"@type": "GovernmentOrganization",
                        "name": "U.S. Department of the Treasury, Office of Foreign Assets Control",
                        "url": "https://ofac.treasury.gov/"},
            "publisher": {"@type": "Organization", "@id": SITE + "#org", "name": "SanctionsAI", "url": SITE},
            "distribution": [
                {"@type": "DataDownload", "encodingFormat": "application/json",
                 "contentUrl": SITE + "/updates/feed.json"},
                {"@type": "DataDownload", "encodingFormat": "application/rss+xml",
                 "contentUrl": SITE + "/updates/feed.xml"},
            ],
            "temporalCoverage": ("%s/%s" % (pubs[-1]["datePublished"], pubs[0]["datePublished"]))
            if pubs else None,
        },
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "SanctionsAI", "item": SITE},
                {"@type": "ListItem", "position": 2, "name": "SDN Change Log", "item": canonical},
            ],
        },
    ]
    # drop null temporalCoverage rather than emit a null-valued property
    jsonld[0] = {k: v for k, v in jsonld[0].items() if v is not None}
    return page(title, desc, canonical, body, jsonld)


def rfc2822(date):
    try:
        return datetime.strptime(date, "%Y-%m-%d").replace(
            tzinfo=timezone.utc).strftime("%a, %d %b %Y 00:00:00 +0000")
    except ValueError:
        return date


def render_feeds(pubs):
    items_xml = []
    items_json = []
    for p in pubs[:50]:
        date = p["datePublished"]
        c = p["counts"]
        bits = [("%d added" % c["add"]) if c["add"] else "",
                ("%d removed" % c["remove"]) if c["remove"] else "",
                ("%d modified" % c["other"]) if c["other"] else ""]
        summary = ", ".join(b for b in bits if b) or "no entity-level changes"
        names = [e["displayName"] or e["officialName"] for e in p["entities"]]
        text = "OFAC published %s to the SDN List on %s.%s" % (
            summary, human_date(date),
            (" Records: " + "; ".join(names) + ".") if names else "")
        url = "%s/updates/%s/" % (SITE, date)
        items_xml.append(
            "<item><title>%s</title><link>%s</link><guid isPermaLink=\"true\">%s</guid>"
            "<pubDate>%s</pubDate><description>%s</description></item>" % (
                esc("OFAC SDN List Update — %s (%s)" % (human_date(date), summary)),
                esc(url), esc(url), rfc2822(date), esc(text)))
        items_json.append({
            "id": url,
            "url": url,
            "title": "OFAC SDN List Update — %s (%s)" % (human_date(date), summary),
            "content_text": text,
            "date_published": date + "T00:00:00Z",
        })

    rss = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
        "<title>OFAC SDN List Change Log — SanctionsAI</title>"
        "<link>%s/updates/</link>"
        "<description>Every change OFAC publishes to the Specially Designated Nationals list, "
        "as structured data.</description>"
        "<language>en-us</language>"
        '<atom:link href="%s/updates/feed.xml" rel="self" type="application/rss+xml"/>'
        "%s</channel></rss>\n"
    ) % (SITE, SITE, "".join(items_xml))

    jsonfeed = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": "OFAC SDN List Change Log — SanctionsAI",
        "home_page_url": SITE + "/updates/",
        "feed_url": SITE + "/updates/feed.json",
        "description": ("Every change OFAC publishes to the Specially Designated Nationals list, "
                        "as structured data. Source: U.S. Treasury OFAC delta file."),
        "items": items_json,
    }
    return rss, json.dumps(jsonfeed, ensure_ascii=False, indent=1)


def render_sitemap(pubs):
    urls = [(SITE + "/updates/", pubs[0]["datePublished"] if pubs else "", "daily", "0.9")]
    for p in pubs:
        urls.append(("%s/updates/%s/" % (SITE, p["datePublished"]), p["datePublished"], "yearly", "0.8"))
        for e in p["entities"]:
            urls.append(("%s/updates/entity/%s" % (SITE, e["slug"]),
                         p["datePublished"], "yearly", "0.7"))
    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod, freq, prio in urls:
        xml.append("  <url>\n    <loc>%s</loc>\n    <lastmod>%s</lastmod>\n"
                   "    <changefreq>%s</changefreq>\n    <priority>%s</priority>\n  </url>"
                   % (esc(loc), esc(lastmod), freq, prio))
    xml.append("</urlset>")
    return "\n".join(xml) + "\n", len(urls)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true",
                    help="rebuild pages from the existing archive without contacting OFAC")
    args = ap.parse_args()

    is_new, date = capture(args.offline)
    pubs = load_archive()
    if not pubs:
        sys.exit("no publications in the archive and nothing fetched — nothing to build")

    # entity slugs must be unique across the whole site, not just within one
    # publication: a name re-designated later would otherwise overwrite the
    # earlier page. Oldest publication wins the bare slug.
    taken = {}
    for p in sorted(pubs, key=lambda x: x["datePublished"]):
        for e in p["entities"]:
            if e["slug"] in taken and taken[e["slug"]] != (p["datePublished"], e["id"]):
                e["slug"] = "%s-%s" % (e["slug"], p["datePublished"])
            taken[e["slug"]] = (p["datePublished"], e["id"])

    write(os.path.join(OUT, "index.html"), render_hub(pubs))
    entity_count = 0
    for i, p in enumerate(pubs):
        newer = pubs[i - 1]["datePublished"] if i > 0 else None
        older = pubs[i + 1]["datePublished"] if i + 1 < len(pubs) else None
        d = p["datePublished"]
        write(os.path.join(OUT, d, "index.html"), render_publication_page(p, newer, older))
        write(os.path.join(OUT, d, "data.json"),
              json.dumps(p, ensure_ascii=False, indent=1))
        for ent in p["entities"]:
            write(os.path.join(OUT, "entity", ent["slug"], "index.html"),
                  render_entity_page(ent, p))
            entity_count += 1

    rss, jsonfeed = render_feeds(pubs)
    write(os.path.join(OUT, "feed.xml"), rss)
    write(os.path.join(OUT, "feed.json"), jsonfeed)
    sitemap, url_count = render_sitemap(pubs)
    write(SITEMAP, sitemap)

    print("OFAC SDN Change Log built")
    print("  publications archived : %d" % len(pubs))
    print("  newest publication    : %s%s" % (pubs[0]["datePublished"],
                                              "  (NEW this run)" if is_new else ""))
    print("  entity pages          : %d" % entity_count)
    print("  sitemap URLs          : %d" % url_count)
    if args.offline:
        print("  (offline rebuild — OFAC was not contacted)")
    # Exit code 10 signals "new publication captured" to the cron wrapper, which
    # only commits and deploys when there is something new to ship.
    sys.exit(10 if is_new else 0)


if __name__ == "__main__":
    main()
