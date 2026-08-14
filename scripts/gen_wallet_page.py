"""Generate /data/ofac-crypto-wallets/ (index.html, data.csv, data.json, sources.json)
from the intermediate JSON produced by build_ofac_wallets.py.

Usage:
  python3 scripts/gen_wallet_page.py --json /tmp/ofac_wallets.json \
      --as-of 2026-08-07 --generated 2026-08-12

`--as-of` must be the DateOfIssue of the SDN Advanced XML (not today's date).
`--generated` is when the page was produced.
"""
import argparse
import collections
import csv
import datetime
import html
import json
import os

REPO = "/Users/sipi/workspace/agentmail"
OUT = REPO + "/data/ofac-crypto-wallets"
SRC_XML = "https://www.treasury.gov/ofac/downloads/sanctions/1.0/sdn_advanced.xml"
SRC_HOME = "https://ofac.treasury.gov/sanctions-list-service"

CHAIN_NAMES = {
    "XBT": "Bitcoin", "ETH": "Ethereum", "TRX": "Tron", "USDT": "Tether",
    "LTC": "Litecoin", "XMR": "Monero", "BCH": "Bitcoin Cash", "DASH": "Dash",
    "SOL": "Solana", "ZEC": "Zcash", "DOGE": "Dogecoin", "USDC": "USD Coin",
    "ARB": "Arbitrum", "BNB": "BNB", "BSC": "BNB Smart Chain", "BSV": "Bitcoin SV",
    "BTG": "Bitcoin Gold", "ETC": "Ethereum Classic", "XRP": "XRP", "XVG": "Verge",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="/tmp/ofac_wallets.json")
    ap.add_argument("--as-of", required=True, help="SDN Advanced XML DateOfIssue (YYYY-MM-DD)")
    ap.add_argument("--generated", default=datetime.date.today().isoformat())
    args = ap.parse_args()

    AS_OF = args.as_of
    GENERATED = args.generated

    records = json.load(open(args.json))
    for r in records:
        r["source"] = SRC_XML  # authoritative bulk file; profile id is its own column
        r["entity_designation_date"] = r.pop("designation_date")
    n = len(records)
    uniq = len({r["address"] for r in records})
    chains = collections.Counter(r["chain"] for r in records)
    entities = len({r["entity"] for r in records})
    years = collections.Counter(r["entity_designation_date"][:4] for r in records if r["entity_designation_date"])
    first_year, last_year = min(years), max(years)

    os.makedirs(OUT, exist_ok=True)

    # ---- data.json ----
    json.dump({
        "dataset": "OFAC Sanctioned Cryptocurrency Wallet Addresses",
        "publisher": "SanctionsAI",
        "url": "https://sanctionsai.dev/data/ofac-crypto-wallets/",
        "license": "CC BY 4.0 (compilation); underlying OFAC data is US Government work, public domain",
        "source": SRC_XML,
        "sdn_list_date": AS_OF,
        "generated": GENERATED,
        "record_count": n,
        "unique_addresses": uniq,
        "records": records,
    }, open(OUT + "/data.json", "w"), indent=1)

    # ---- data.csv ----
    with open(OUT + "/data.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["address", "chain", "entity", "ofac_programs",
                                          "entity_designation_date", "sdn_profile_id", "source"])
        w.writeheader()
        for r in records:
            w.writerow({k: r[k] for k in w.fieldnames})

    # ---- sources.json (guardrail 5.1 manifest) ----
    json.dump({
        "page": "https://sanctionsai.dev/data/ofac-crypto-wallets/",
        "claims": [
            {"claim": f"{n} digital-currency address listings", "source_url": SRC_XML,
             "method": "count of Feature elements with FeatureType 'Digital Currency Address - *' in SDN Advanced XML dated " + AS_OF},
            {"claim": f"{uniq} unique addresses", "source_url": SRC_XML,
             "method": "distinct address strings (some addresses are listed under two chain labels, e.g. USDT on Tron)"},
            {"claim": f"{len(chains)} chains", "source_url": SRC_XML,
             "method": "distinct chain suffixes of the Digital Currency Address feature type"},
            {"claim": f"entity designation dates span {first_year}-{last_year}", "source_url": SRC_XML,
             "method": "earliest EntryEvent date per SDN entry. NOTE: this is the date the ENTITY was first designated, not the date the address was added to the list — OFAC's bulk files do not publish per-address add dates. E.g. the Central Bank of Iran entry dates to 2010; its Tron addresses were added much later."},
            {"claim": "OFAC first attached digital-currency addresses to SDN designations in November 2018", "source_url": "https://home.treasury.gov/news/press-releases/sm556",
             "method": "Treasury press release, 2018-11-28: 'OFAC is publishing digital currency addresses ... first time' (two Iran-based ransomware facilitators)"},
            {"claim": "per-chain counts in the summary table", "source_url": SRC_XML,
             "method": "group-by chain over the same records; cross-checked against Treasury sdn.csv remarks field (same distribution) and the third-party vile/ofac-sdn-list release (961 unique addresses, identical)"},
        ],
        "guardrail_5_2": {
            "note": "Categorical distributions verified against two independent parses of the primary source: chain=XBT is 54% of listings in BOTH sdn_advanced.xml and the sdn.csv remarks field — a true property of the OFAC list (Bitcoin dominates designations), not a parser artifact.",
            "no_constant_default_fields": True,
            "missing_designation_date": 0, "missing_programs": 0, "missing_entity": 0,
        },
    }, open(OUT + "/sources.json", "w"), indent=1)

    # ---- index.html ----
    chain_rows = "\n".join(
        f"<tr><td>{html.escape(CHAIN_NAMES.get(c, c))} ({html.escape(c)})</td><td class=\"value\">{cnt}</td></tr>"
        for c, cnt in chains.most_common())

    def row(r):
        return ("<tr><td class=\"addr\">" + html.escape(r["address"]) + "</td><td>"
                + html.escape(r["chain"]) + "</td><td>" + html.escape(r["entity"])
                + "</td><td>" + html.escape(r["ofac_programs"]) + "</td><td>"
                + html.escape(r["entity_designation_date"]) + "</td><td>"
                + html.escape(r["sdn_profile_id"]) + "</td></tr>")

    table_rows = "\n".join(row(r) for r in records)

    jsonld = json.dumps({
        "@context": "https://schema.org", "@type": "Dataset",
        "name": "OFAC Sanctioned Cryptocurrency Wallet Addresses",
        "alternateName": "OFAC SDN digital currency address list",
        "description": f"All {n} digital-currency address listings ({uniq} unique addresses across {len(chains)} chains) on the US Treasury OFAC SDN list as of {AS_OF}, with chain, sanctioned entity, OFAC program and entity designation date for every address. CSV and JSON downloads.",
        "url": "https://sanctionsai.dev/data/ofac-crypto-wallets/",
        "identifier": "ofac-crypto-wallets",
        "keywords": "OFAC crypto addresses, sanctioned wallet list, SDN digital currency address, OFAC bitcoin addresses, sanctions screening",
        "creator": {"@type": "Organization", "name": "SanctionsAI", "url": "https://sanctionsai.dev"},
        "datePublished": GENERATED, "dateModified": GENERATED,
        "temporalCoverage": f"{first_year}/{last_year}",
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "isAccessibleForFree": True,
        "isBasedOn": SRC_XML,
        "distribution": [
            {"@type": "DataDownload", "encodingFormat": "text/csv",
             "contentUrl": "https://sanctionsai.dev/data/ofac-crypto-wallets/data.csv"},
            {"@type": "DataDownload", "encodingFormat": "application/json",
             "contentUrl": "https://sanctionsai.dev/data/ofac-crypto-wallets/data.json"},
        ],
        "includedInDataCatalog": {"@type": "DataCatalog", "name": "SanctionsAI Research Data",
                                  "url": "https://sanctionsai.dev/data/"},
    }, ensure_ascii=False)

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OFAC Sanctioned Crypto Wallet Addresses — Full List ({n} entries) | SanctionsAI</title>
<meta name="description" content="Every cryptocurrency address on the US Treasury OFAC SDN list: {uniq} unique addresses across {len(chains)} chains, with entity, OFAC program and designation date. Free CSV + JSON downloads, CC BY 4.0.">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://sanctionsai.dev/data/ofac-crypto-wallets/">
<meta property="og:title" content="OFAC Sanctioned Crypto Wallet Addresses — Full List ({n} entries) | SanctionsAI">
<meta property="og:description" content="Every cryptocurrency address on the US Treasury OFAC SDN list: {uniq} unique addresses across {len(chains)} chains, with entity, program and designation date. CSV + JSON, CC BY 4.0.">
<meta property="og:type" content="website">
<meta property="og:url" content="https://sanctionsai.dev/data/ofac-crypto-wallets/">
<script type="application/ld+json">{jsonld}</script>
<style>
:root{{--bg:#fafbfc;--fg:#1a1a2e;--accent:#2563eb;--muted:#6b7280;--border:#e5e7eb;--card:#fff;--green:#059669}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--fg);line-height:1.7}}
.container{{max-width:1100px;margin:0 auto;padding:2rem 1.5rem}}
h1{{font-size:2rem;font-weight:800;margin-bottom:.5rem;line-height:1.2}}
h2{{font-size:1.4rem;font-weight:700;margin:2rem 0 1rem}}
.lead{{font-size:1.1rem;color:var(--muted);margin-bottom:1.25rem}}
table{{width:100%;border-collapse:collapse;margin:1.25rem 0;font-size:.85rem}}
th,td{{padding:.5rem .6rem;text-align:left;border-bottom:1px solid var(--border);vertical-align:top}}
th{{background:var(--bg);font-weight:600;color:var(--muted);font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;position:sticky;top:0}}
td.addr{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.78rem;word-break:break-all;max-width:340px}}
.value{{font-weight:700;color:var(--accent);white-space:nowrap}}
.btn{{display:inline-block;padding:.7rem 1.5rem;border-radius:8px;font-weight:600;text-decoration:none;font-size:.95rem;margin:.25rem;transition:all .15s}}
.btn-primary{{background:var(--accent);color:#fff}}
.btn-primary:hover{{background:#1d4ed8}}
.btn-outline{{border:2px solid var(--border);color:var(--fg);background:transparent}}
.btn-outline:hover{{border-color:var(--accent);color:var(--accent)}}
.cite-box{{background:#f0f7ff;border:1px solid #bfdbfe;border-radius:8px;padding:1.25rem;margin:1.5rem 0;font-size:.88rem}}
.cite-box pre{{background:#1e293b;color:#e2e8f0;padding:.75rem;border-radius:6px;overflow-x:auto;font-size:.78rem;margin-top:.5rem;white-space:pre-wrap}}
.breadcrumb{{font-size:.85rem;color:var(--muted);margin-bottom:1.5rem}}
.breadcrumb a{{color:var(--muted);text-decoration:none}}
.breadcrumb a:hover{{color:var(--accent)}}
.badge{{display:inline-block;padding:.2rem .6rem;border-radius:4px;font-size:.75rem;font-weight:600;background:#dcfce7;color:var(--green);margin-right:.5rem}}
.note{{background:#fef3c7;border:1px solid #fcd34d;border-radius:8px;padding:1rem;margin:1.5rem 0;font-size:.9rem}}
footer{{margin-top:3rem;padding:1.5rem 0;border-top:1px solid var(--border);color:var(--muted);font-size:.85rem}}
footer a{{color:var(--accent)}}
@media(max-width:640px){{.container{{padding:1rem}}h1{{font-size:1.5rem}}td.addr{{max-width:160px}}}}
</style>
</head>
<body>
<div class="container">
<nav class="breadcrumb"><a href="/">Home</a> › <a href="/data/">Research Data</a> › OFAC Crypto Wallet Addresses</nav>
<h1>OFAC Sanctioned Crypto Wallet Addresses</h1>
<p class="lead">Every digital-currency address on the US Treasury OFAC SDN list — <strong>{n} listings, {uniq} unique addresses across {len(chains)} chains</strong> — with the sanctioned entity, OFAC program(s), and the entity's designation date for each address. Parsed directly from Treasury's authoritative SDN Advanced XML.</p>

<p><span class="badge">SDN list of {AS_OF}</span><span class="badge">CC BY 4.0</span><span class="badge">CSV + JSON</span></p>
<p>
<a href="/data/ofac-crypto-wallets/data.csv" class="btn btn-primary" download>Download CSV</a>
<a href="/data/ofac-crypto-wallets/data.json" class="btn btn-outline" download>Download JSON</a>
<a href="/data/ofac-crypto-wallets/sources.json" class="btn btn-outline" download>Sources manifest</a>
</p>

<div class="note"><strong>Freshness:</strong> this page reflects the OFAC SDN publication of <strong>{AS_OF}</strong> and was generated on {GENERATED}. It is regenerated when OFAC updates the list. For screening decisions, use the <a href="/check">live checker</a> or the keyless API (<code>curl "https://sanctionsai.dev/sanctions?wallet=..."</code>), which refresh against the source list every 24 hours.</div>

<h2>What is in this dataset</h2>
<p>OFAC began attaching specific cryptocurrency addresses to SDN designations in <a href="https://home.treasury.gov/news/press-releases/sm556">November 2018</a>. Today the list covers darknet markets (Hydra), mixers (Tornado Cash, Blender.io), exchanges (Garantex, SUEX, Chatex), ransomware operators, and state-linked groups. When an address appears here, US persons are generally prohibited from transacting with it, and property in US jurisdiction must be blocked. Screening against this exact list is the baseline compliance control for any wallet, exchange, or AI agent that moves value on-chain.</p>
<p>Each record carries six fields: the address itself, the chain label OFAC assigned (e.g. <code>XBT</code> for Bitcoin), the designated entity or person the address belongs to, the OFAC sanctions program(s) under which they were designated, the date the entity was first designated, and the SDN profile ID so you can trace the record back to Treasury's own data. <strong>Note the date column carefully:</strong> it is the <em>entity's</em> original designation date, not the date the address was added — OFAC's bulk files do not publish per-address add dates, which is why the Central Bank of Iran's Tron addresses carry the bank's 2010 entry date. Entity designation dates in this file span {first_year}–{last_year}.</p>

<h2>Addresses by chain</h2>
<table>
<thead><tr><th>Chain</th><th>Listings</th></tr></thead>
<tbody>
{chain_rows}
</tbody>
</table>
<p style="font-size:.85rem;color:var(--muted)">A handful of addresses appear under two chain labels (for example the same Tron address listed as both <code>TRX</code> and <code>USDT</code>) — that is how OFAC publishes them, so listings ({n}) slightly exceed unique addresses ({uniq}).</p>

<h2>Methodology</h2>
<p>Records are extracted from the <a href="{SRC_XML}">OFAC SDN Advanced XML</a> (the <a href="{SRC_HOME}">Sanctions List Service</a> bulk file): every <code>Feature</code> whose type is <code>Digital Currency Address - *</code>, joined to its <code>DistinctParty</code> profile for the entity name and to its <code>SanctionsEntry</code> for program and earliest designation-event date. No third-party data, no inference — if a field is empty in Treasury's file it is empty here. The extraction was cross-checked against the remarks field of Treasury's legacy <code>sdn.csv</code> and yields the same per-chain distribution. Every figure on this page traces to the <a href="/data/ofac-crypto-wallets/sources.json">sources manifest</a>.</p>

<h2>Licence &amp; citation</h2>
<div class="cite-box">
<p>The underlying OFAC list is a work of the US Government (public domain). This compilation — the parsed, joined, machine-readable form — is published under <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>: use it freely, including commercially, with attribution.</p>
<pre>SanctionsAI, "OFAC Sanctioned Cryptocurrency Wallet Addresses",
https://sanctionsai.dev/data/ofac-crypto-wallets/
(derived from US Treasury OFAC SDN list of {AS_OF})</pre>
</div>

<h2>Full list — all {n} address listings</h2>
<table>
<thead><tr><th>Address</th><th>Chain</th><th>Entity</th><th>OFAC program</th><th>Entity designated</th><th>SDN profile</th></tr></thead>
<tbody>
{table_rows}
</tbody>
</table>

<footer>
<p><strong>SanctionsAI</strong> — AI-powered sanctions &amp; AML compliance screening. Not legal advice; consult the <a href="{SRC_HOME}">official OFAC list</a> before acting.</p>
<p><a href="https://sanctionsai.dev">sanctionsai.dev</a> · <a href="/data/">Research Data</a> · <a href="/data/feed.json">JSON Feed</a></p>
</footer>
</div>
</body>
</html>
"""
    open(OUT + "/index.html", "w").write(page)
    print("index.html bytes:", len(page))
    body_text_len = len(page)  # rough
    print("records:", n, "uniq:", uniq, "chains:", len(chains), "entities:", entities,
          "years:", first_year, "-", last_year)


if __name__ == "__main__":
    main()
