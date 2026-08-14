"""Build the OFAC sanctioned crypto-wallet dataset from sdn_advanced.xml.

Source: US Treasury OFAC SDN Advanced XML (authoritative bulk file).
Extracts every 'Digital Currency Address - *' feature with:
  address, chain, entity name, SDN FixedRef, OFAC program(s), designation date.

Usage:
  python3 scripts/build_ofac_wallets.py --src /tmp/sdn_advanced.xml --out /tmp/ofac_wallets.json

Guards (§5.2): prints the top-value share for each categorical field so a
parser artifact (e.g. a constant default) is visible before anything publishes.
"""
import argparse
import collections
import csv
import json
import sys
import xml.etree.ElementTree as ET

# The SDN Advanced XML namespace. NOTE: it is case-sensitive and differs from
# the legacy sdn.xml namespace — 'ADVANCED_XML' is uppercase, 'PublicationPreview'
# has a capital P. ElementTree won't match child paths if this is wrong.
NS = "{https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/ADVANCED_XML}"


def tag(e):
    return e.tag.split("}", 1)[1] if "}" in e.tag else e.tag


def parse(src):
    # Pass 1: reference values — FeatureType IDs for digital currency, program values
    dc_feature_ids = {}
    sanctions_programs = {}
    parties = {}            # profile_id -> {"name":..., "addresses":[(chain,addr)]}
    entries = {}            # profile_id -> {"programs":[...], "date": "YYYY-MM-DD"}
    date_of_issue = None

    ctx = ET.iterparse(src, events=("end",))
    for event, elem in ctx:
        t = tag(elem)
        if t == "DateOfIssue":
            y = elem.findtext(NS + "Year")
            m = elem.findtext(NS + "Month")
            d = elem.findtext(NS + "Day")
            if y and m and d:
                date_of_issue = f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
            elem.clear()
        elif t == "FeatureType":
            txt = (elem.text or "").strip()
            if txt.startswith("Digital Currency Address"):
                chain = txt.split("-", 1)[1].strip() if "-" in txt else ""
                dc_feature_ids[elem.get("ID")] = chain
            elem.clear()
        elif t == "SanctionsProgram":
            sanctions_programs[elem.get("ID")] = (elem.text or "").strip()
            elem.clear()
        elif t == "DistinctParty":
            pid = None
            name = None
            addrs = []
            for prof in elem.iter(NS + "Profile"):
                pid = prof.get("ID")
                # primary name: first DocumentedName's NamePartValues joined
                for dn in prof.iter(NS + "DocumentedName"):
                    parts = [(v.text or "").strip() for v in dn.iter(NS + "NamePartValue")]
                    if parts:
                        name = " ".join(p for p in parts if p)
                        break
                for feat in prof.iter(NS + "Feature"):
                    ftid = feat.get("FeatureTypeID")
                    if ftid in dc_feature_ids:
                        for vd in feat.iter(NS + "VersionDetail"):
                            a = (vd.text or "").strip()
                            if a:
                                addrs.append((dc_feature_ids[ftid], a))
            if pid and addrs:
                parties[pid] = {"name": name or "", "addresses": addrs}
            elem.clear()
        elif t == "SanctionsEntry":
            pid = elem.get("ProfileID")
            progs = []
            date = None
            for sm in elem.iter(NS + "SanctionsMeasure"):
                c = sm.find(NS + "Comment")
                if c is not None and (c.text or "").strip():
                    progs.append(c.text.strip())
            for ev in elem.iter(NS + "EntryEvent"):
                d = ev.find(NS + "Date")
                if d is not None:
                    y = d.findtext(NS + "Year")
                    m = d.findtext(NS + "Month")
                    dy = d.findtext(NS + "Day")
                    if y and m and dy:
                        cand = f"{int(y):04d}-{int(m):02d}-{int(dy):02d}"
                        if date is None or cand < date:
                            date = cand
                break  # first EntryEvent = original designation
            if pid:
                entries[pid] = {"programs": sorted(set(progs)), "date": date}
            elem.clear()

    records = []
    for pid, p in parties.items():
        e = entries.get(pid, {"programs": [], "date": None})
        for chain, addr in p["addresses"]:
            records.append({
                "address": addr,
                "chain": chain,
                "entity": p["name"],
                "sdn_profile_id": pid,
                "ofac_programs": "; ".join(e["programs"]),
                "designation_date": e["date"] or "",
                "source": f"https://sanctionslist.ofac.treas.gov/Home/index — SDN profile {pid}",
            })

    records.sort(key=lambda r: (r["chain"], r["designation_date"], r["address"]))
    return records, date_of_issue


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="/tmp/sdn_advanced.xml")
    ap.add_argument("--out", default="/tmp/ofac_wallets.json")
    args = ap.parse_args()

    records, date_of_issue = parse(args.src)

    print("DATE_OF_ISSUE:", date_of_issue)
    print("total records:", len(records))
    print("unique addresses:", len({r['address'] for r in records}))
    cc = collections.Counter(r["chain"] for r in records)
    print("chains:", cc.most_common())
    missing_date = sum(1 for r in records if not r["designation_date"])
    missing_prog = sum(1 for r in records if not r["ofac_programs"])
    missing_name = sum(1 for r in records if not r["entity"])
    print("missing date:", missing_date, "missing prog:", missing_prog, "missing name:", missing_name)
    ec = collections.Counter(r["entity"] for r in records)
    print("top entities:", ec.most_common(5))

    # Guardrail 5.2 checks
    n = len(records)
    for field in ("chain", "entity", "ofac_programs", "designation_date"):
        top, cnt = collections.Counter(r[field] for r in records).most_common(1)[0]
        print(f"5.2 {field}: top value {top!r} = {cnt}/{n} = {cnt/n:.1%}")

    json.dump(records, open(args.out, "w"), indent=1)
    csv_path = args.out.rsplit(".", 1)[0] + ".csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        w.writeheader()
        w.writerows(records)
    print(f"written {args.out} + {csv_path}")


if __name__ == "__main__":
    main()
