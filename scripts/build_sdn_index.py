#!/usr/bin/env python3
"""Build the compact OFAC SDN index that /free/ofac-screening screens against.

Source of truth is OFAC's own published export. Nothing here is derived, inferred
or edited — the only transformations are (a) joining alternate names onto their
primary entry and (b) dropping columns the screening tool does not use (vessel
tonnage, call sign, addresses). Names are emitted verbatim; normalisation happens
in the browser at match time so the raw OFAC string is always what gets displayed.

Run:  python3 scripts/build_sdn_index.py
Out:  data/ofac-sdn-index.json   (+ .meta.json for the freshness banner)

The publication date is read from OFAC's redirect URL, which embeds the
publication folder (…/Published/<id>/YYYY-MM-DD/…). It is NOT today's date —
a screening tool that displays its own build date as the list date would tell a
compliance officer the data is fresher than it is.
"""
import csv
import io
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

BASE = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports"
SDN_URL = BASE + "/SDN.CSV"
ALT_URL = BASE + "/ALT.CSV"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "data", "ofac-sdn-index.json")
META = os.path.join(HERE, "data", "ofac-sdn-index.meta.json")

# OFAC uses the literal string "-0- " for an empty field.
EMPTY = {"-0-", "-0- ", ""}


def fetch(url):
    """Return (bytes, effective_url). curl follows OFAC's signed-S3 redirect."""
    r = subprocess.run(
        ["curl", "-sL", "--max-time", "120", "-w", "\n%{url_effective}", url],
        capture_output=True,
    )
    if r.returncode != 0:
        sys.exit("curl failed for %s: %s" % (url, r.stderr.decode()[:200]))
    body, _, eff = r.stdout.rpartition(b"\n")
    if len(body) < 50000:
        sys.exit("suspiciously small download from %s (%d bytes) — refusing to ship" % (url, len(body)))
    return body, eff.decode().strip()


def clean(v):
    v = (v or "").strip()
    return "" if v in EMPTY else v


def published_date(effective_url):
    m = re.search(r"/(\d{4}-\d{2}-\d{2})/", effective_url)
    return m.group(1) if m else None


def main():
    sdn_raw, sdn_eff = fetch(SDN_URL)
    alt_raw, _ = fetch(ALT_URL)
    published = published_date(sdn_eff)
    if not published:
        sys.exit("could not read the publication date from OFAC's URL — refusing to ship an undated list")

    # alternates first, keyed by ent_num
    alts = {}
    alt_count = 0
    for row in csv.reader(io.StringIO(alt_raw.decode("utf-8", "replace"))):
        if len(row) < 4:
            continue
        ent, name = clean(row[0]), clean(row[3])
        if not ent or not name:
            continue
        alts.setdefault(ent, [])
        if name not in alts[ent]:
            alts[ent].append(name)
            alt_count += 1

    entries = []
    programs = {}
    types = {}
    for row in csv.reader(io.StringIO(sdn_raw.decode("utf-8", "replace"))):
        if len(row) < 4:
            continue
        ent, name, typ, prog = clean(row[0]), clean(row[1]), clean(row[2]), clean(row[3])
        if not ent or not name:
            continue
        typ = typ or "entity"
        types[typ] = types.get(typ, 0) + 1
        for p in re.split(r"\]\s*\[", prog.strip("[]")):
            p = p.strip()
            if p:
                programs[p] = programs.get(p, 0) + 1
        entries.append([int(ent), name, typ, prog, alts.get(ent, [])])

    if len(entries) < 5000:
        sys.exit("only %d SDN entries parsed — the format likely changed; refusing to ship" % len(entries))

    payload = {
        "source": "U.S. Treasury OFAC — Specially Designated Nationals and Blocked Persons List (SDN)",
        "sourceUrl": SDN_URL,
        "altSourceUrl": ALT_URL,
        "officialSearchUrl": "https://sanctionssearch.ofac.treas.gov/",
        "published": published,
        "retrieved": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "counts": {
            "entries": len(entries),
            "alternateNames": alt_count,
            "totalNames": len(entries) + alt_count,
        },
        "scope": (
            "OFAC SDN list primary names and alternate identities only. Does NOT include "
            "the OFAC Consolidated (non-SDN) lists, the Sectoral Sanctions Identifications "
            "list, EU/UK/UN or any other jurisdiction's list, and does NOT perform 50 Percent "
            "Rule ownership analysis."
        ),
        "entries": entries,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))

    meta = {k: v for k, v in payload.items() if k != "entries"}
    meta["topPrograms"] = sorted(programs.items(), key=lambda kv: -kv[1])[:15]
    meta["typeCounts"] = types
    meta["indexBytes"] = os.path.getsize(OUT)
    with open(META, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=1)

    print("OFAC SDN index built")
    print("  published (OFAC)  : %s" % published)
    print("  retrieved         : %s" % payload["retrieved"])
    print("  entries           : %d" % len(entries))
    print("  alternate names   : %d" % alt_count)
    print("  total names       : %d" % payload["counts"]["totalNames"])
    print("  types             : %s" % types)
    print("  index size        : %.2f MB" % (os.path.getsize(OUT) / 1048576.0))


if __name__ == "__main__":
    main()
