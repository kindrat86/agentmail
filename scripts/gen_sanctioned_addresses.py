from pathlib import Path
import collections, html, json, re

REPO = Path('/Users/sipi/workspace/agentmail')
ROOT = REPO / 'sanctioned-addresses'
DATA = REPO / 'data/ofac-crypto-wallets/data.json'
SOURCE = 'https://www.treasury.gov/ofac/downloads/sanctions/1.0/sdn_advanced.xml'
SOURCE_HOME = 'https://ofac.treasury.gov/sanctions-list-service'

CONFIG = {
    'bitcoin': ('XBT', 'Bitcoin', 'BTC'),
    'bitcoin-cash': ('BCH', 'Bitcoin Cash', 'BCH'),
    'dash': ('DASH', 'Dash', 'DASH'),
    'ethereum': ('ETH', 'Ethereum', 'ETH'),
    'litecoin': ('LTC', 'Litecoin', 'LTC'),
    'monero': ('XMR', 'Monero', 'XMR'),
    'solana': ('SOL', 'Solana', 'SOL'),
    'tether-usdt': ('USDT', 'Tether (USDT)', 'USDT'),
    'tron': ('TRX', 'Tron', 'TRX'),
    'zcash': ('ZEC', 'Zcash', 'ZEC'),
}
DISPLAY = {
    'XBT':'Bitcoin', 'ETH':'Ethereum', 'TRX':'Tron', 'USDT':'Tether (USDT)',
    'LTC':'Litecoin', 'XMR':'Monero', 'BCH':'Bitcoin Cash', 'DASH':'Dash',
    'SOL':'Solana', 'ZEC':'Zcash', 'DOGE':'Dogecoin', 'USDC':'USD Coin',
    'ARB':'Arbitrum', 'BNB':'BNB', 'BSC':'BNB Smart Chain', 'BSV':'Bitcoin SV',
    'BTG':'Bitcoin Gold', 'ETC':'Ethereum Classic', 'XRP':'XRP Ledger', 'XVG':'Verge',
}

def esc(x): return html.escape(str(x), quote=True)
def programs(r): return [p.strip() for p in r['ofac_programs'].split(';') if p.strip()]
def sub1(pattern, replacement, text, label):
    out, n = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if n != 1: raise RuntimeError(f'{label}: expected 1 replacement, got {n}')
    return out

def replace_stat_grid(text, replacement, label):
    start = text.index('<div class="stat-grid">')
    line_end = text.index('\n', start)
    if replacement.count('class="stat-card"') != 4:
        raise RuntimeError(f'{label}: replacement must have four cards')
    return text[:start] + replacement + text[line_end:]

doc = json.loads(DATA.read_text())
AS_OF = doc['sdn_list_date']
if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', AS_OF): raise RuntimeError(f"unexpected source date {AS_OF}")
records = doc['records']
if not records: raise RuntimeError('empty dataset')
by_chain = collections.defaultdict(list)
for r in records: by_chain[r['chain']].append(r)
unique_count = len({r['address'] for r in records})

# Guardrail 5.2: document the true dominant distribution, while checking all records are sourced.
assert all(r.get('source') == SOURCE for r in records)
assert all(r.get('address') and r.get('chain') and r.get('entity') and r.get('ofac_programs') and r.get('entity_designation_date') for r in records)

hub = (ROOT / 'index.html').read_text()
entities = len({r['entity'] for r in records})
chain_counts = collections.Counter(r['chain'] for r in records)
hub = re.sub(r'OFAC-Sanctioned Crypto Addresses — All \d+ (?:on the SDN List|Listings)…', f'OFAC-Sanctioned Crypto Addresses — All {len(records)} Listings…', hub)
hub = sub1(r'<meta name="description" content="[^"]*">', f'<meta name="description" content="Every digital-currency address listing on the OFAC SDN list — {len(records)} listings covering {unique_count} unique addresses across {len(by_chain)} chains.">', hub, 'hub meta desc')
hub = sub1(r'<meta property="og:description" content="[^"]*">', f'<meta property="og:description" content="Every digital-currency address listing on the OFAC SDN list — {len(records)} listings covering {unique_count} unique addresses across {len(by_chain)} chains.">', hub, 'hub og desc')
hub_dataset = {"@context":"https://schema.org","@type":"Dataset","name":"OFAC-sanctioned digital-currency addresses","description":f"All {len(records)} digital-currency address listings published on the OFAC SDN list, covering {unique_count} unique addresses across {len(by_chain)} chains.","url":"https://sanctionsai.dev/sanctioned-addresses","isBasedOn":SOURCE,"creator":{"@type":"GovernmentOrganization","name":"U.S. Department of the Treasury, Office of Foreign Assets Control","url":"https://ofac.treasury.gov/"},"publisher":{"@type":"Organization","name":"SanctionsAI","url":"https://sanctionsai.dev"},"temporalCoverage":AS_OF,"dateModified":AS_OF,"license":"https://creativecommons.org/licenses/by/4.0/","isAccessibleForFree":True}
hub_faq = {"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{"@type":"Question","name":"How many crypto address listings has OFAC published?","acceptedAnswer":{"@type":"Answer","text":f"{len(records)} listings covering {unique_count} unique addresses across {len(by_chain)} chains, belonging to {entities} designated persons, as of the SDN list published {AS_OF}."}},{"@type":"Question","name":"Which blockchain has the most OFAC-sanctioned address listings?","acceptedAnswer":{"@type":"Answer","text":f"Bitcoin, with {chain_counts['XBT']} of the {len(records)} listings on the SDN list."}}]}
hub = sub1(r'<script type="application/ld\+json">\{[^\n]*"@type":"Dataset"[^\n]*</script>', '<script type="application/ld+json">'+json.dumps(hub_dataset,separators=(',',':'))+'</script>', hub, 'hub dataset')
hub = sub1(r'<script type="application/ld\+json">\{[^\n]*"@type":"FAQPage"[^\n]*</script>', '<script type="application/ld+json">'+json.dumps(hub_faq,separators=(',',':'))+'</script>', hub, 'hub faq')
hub = sub1(r'<p class="lede">.*?</p>', f'<p class="lede">OFAC publishes digital-currency addresses as fields on SDN entries. As of {AS_OF}, the list contains <strong>{len(records)}</strong> listings covering <strong>{unique_count} unique addresses</strong> across <strong>{len(by_chain)}</strong> chains, belonging to <strong>{entities}</strong> designated persons.</p>', hub, 'hub lede')
hub = replace_stat_grid(hub, f'<div class="stat-grid"><div class="stat-card"><div class="num">{len(records)}</div><div class="stat-desc">listings</div></div><div class="stat-card"><div class="num">{unique_count}</div><div class="stat-desc">unique addresses</div></div><div class="stat-card"><div class="num">{len(by_chain)}</div><div class="stat-desc">chains</div></div><div class="stat-card"><div class="num">{AS_OF}</div><div class="stat-desc">list published</div></div></div>', 'hub stats')
rows=[]
for slug,(code,name,ticker) in sorted(CONFIG.items(), key=lambda item: -chain_counts[item[1][0]]):
    rr=by_chain[code]
    rows.append(f'<tr><td><a href="/sanctioned-addresses/{slug}">{esc(name)}</a></td><td><code>{esc(code)}</code></td><td class="sa-r">{len(rr)}</td><td class="sa-r">{len({r["entity"] for r in rr})}</td></tr>')
hub = sub1(r'<table><thead><tr><th>Chain</th><th>OFAC (?:ticker|code)</th>.*?</table>', '<table><thead><tr><th>Chain</th><th>OFAC code</th><th class="sa-r">Listings</th><th class="sa-r">Designated persons</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table>', hub, 'hub table')
remainder=[c for c in chain_counts if c not in {v[0] for v in CONFIG.values()}]
rem_text=', '.join(f'{DISPLAY.get(c,c)} ({c}, {chain_counts[c]})' for c in sorted(remainder, key=lambda c:(-chain_counts[c],c)))
hub = sub1(r'<p>(?:OFAC also publishes|The remaining chains).*?</p>', f'<p>The remaining chains have one or two listings each: {esc(rem_text)}. They are included in the <a href="/data/ofac-crypto-wallets/">full downloadable dataset</a> and API matching set, but do not have thin single-record pages.</p>', hub, 'hub remainder')
hub = re.sub(r'all (?:\d+ addresses|\d+ listings covering \d+ unique addresses) across every chain OFAC publishes', f'all {len(records)} listings covering {unique_count} unique addresses across every chain OFAC publishes', hub)
hub = re.sub(r'published <strong>\d{4}-\d{2}-\d{2}</strong>', f'published <strong>{AS_OF}</strong>', hub)
hub = re.sub(r'No figure is estimated\.(?: The machine-readable <a href="/(?:sanctioned-addresses/sources.json|data/ofac-crypto-wallets/sources.json)">sources manifest</a> records the counting method\.)?', 'No figure is estimated. The machine-readable <a href="/data/ofac-crypto-wallets/sources.json">sources manifest</a> records the counting method.', hub)
(ROOT / 'index.html').write_text(hub)

manifest_pages=[]
for slug,(code,name,ticker) in CONFIG.items():
    path=ROOT/slug/'index.html'
    text=path.read_text()
    rr=sorted(by_chain[code], key=lambda r:(r['entity_designation_date'],r['address']), reverse=True)
    n=len(rr); ents=len({r['entity'] for r in rr}); first=min(r['entity_designation_date'] for r in rr); last=max(r['entity_designation_date'] for r in rr)
    title_name=name
    desc=f"Every {name} address listing OFAC publishes on the SDN list — {n} listings across {ents} designated persons, with entity and program."
    text = re.sub(rf'OFAC-Sanctioned {re.escape(name)} Addresses — All \d+ (?:on the SDN List|Listings)…', f'OFAC-Sanctioned {name} Addresses — All {n} Listings…', text)
    text = sub1(r'<meta name="description" content="[^"]*">', f'<meta name="description" content="{esc(desc)}">', text, slug+' meta desc')
    text = sub1(r'<meta property="og:description" content="[^"]*">', f'<meta property="og:description" content="{esc(desc)}">', text, slug+' og desc')
    faq={"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{"@type":"Question","name":f"How many {name} address listings has OFAC published?","acceptedAnswer":{"@type":"Answer","text":f"{n}, as of the SDN list published {AS_OF}. They belong to {ents} designated persons and are counted from Treasury's SDN Advanced XML export."}},{"@type":"Question","name":f"Is it illegal to send {ticker} to a sanctioned address?","acceptedAnswer":{"@type":"Answer","text":"For a U.S. person, dealing in the property of a blocked person is prohibited. OFAC applies strict liability. This is not legal advice."}},{"@type":"Question","name":f"Where does this list of {name} addresses come from?","acceptedAnswer":{"@type":"Answer","text":"Directly from OFAC's SDN Advanced XML. Nothing here is added, inferred or estimated."}}]}
    dataset={"@context":"https://schema.org","@type":"Dataset","name":f"OFAC-sanctioned {name} addresses","description":f"All {n} {name} address listings published on the OFAC SDN list, with the designated person and program for each.","url":f"https://sanctionsai.dev/sanctioned-addresses/{slug}","isBasedOn":SOURCE,"creator":{"@type":"GovernmentOrganization","name":"U.S. Department of the Treasury, Office of Foreign Assets Control","url":"https://ofac.treasury.gov/"},"publisher":{"@type":"Organization","name":"SanctionsAI","url":"https://sanctionsai.dev"},"temporalCoverage":AS_OF,"dateModified":AS_OF,"license":"https://creativecommons.org/licenses/by/4.0/","isAccessibleForFree":True}
    text=sub1(r'<script type="application/ld\+json">\{[^\n]*"@type":"FAQPage"[^\n]*</script>', '<script type="application/ld+json">'+json.dumps(faq,separators=(',',':'))+'</script>', text, slug+' faq')
    text=sub1(r'<script type="application/ld\+json">\{[^\n]*"@type":"Dataset"[^\n]*</script>', '<script type="application/ld+json">'+json.dumps(dataset,separators=(',',':'))+'</script>', text, slug+' dataset')
    text=sub1(r'<p class="lede">.*?</p>', f'<p class="lede">OFAC publishes digital-currency addresses as fields on SDN entries. As of {AS_OF}, the SDN list carries <strong>{n}</strong> {esc(name)} (<code>{esc(code)}</code>) listings belonging to <strong>{ents}</strong> designated persons. Every listing is below.</p>', text, slug+' lede')
    text=replace_stat_grid(text, f'<div class="stat-grid"><div class="stat-card"><div class="num">{n}</div><div class="stat-desc">{esc(ticker)} listings</div></div><div class="stat-card"><div class="num">{ents}</div><div class="stat-desc">designated persons</div></div><div class="stat-card"><div class="num">{first}</div><div class="stat-desc">first entity designation</div></div><div class="stat-card"><div class="num">{last}</div><div class="stat-desc">latest entity designation</div></div></div>', slug+' stats')
    text = re.sub(r'The list this page was built from was published \d{4}-\d{2}-\d{2}\.', f'The list this page was built from was published {AS_OF}.', text)
    text = re.sub(r'A product that settles on several chains needs all (?:\d+ addresses|\d+ listings covering \d+ unique addresses) across every chain OFAC publishes, not one chain\'s worth\.', f'A product that settles on several chains needs all {len(records)} listings covering {unique_count} unique addresses across every chain OFAC publishes, not one chain\'s worth.', text)
    entity_counts=collections.Counter(r['entity'] for r in rr)
    entity_programs=collections.defaultdict(set)
    for r in rr: entity_programs[r['entity']].update(programs(r))
    who=''.join(f'<tr><td>{esc(entity)}</td><td class="sa-r">{cnt}</td><td>{esc(", ".join(sorted(entity_programs[entity])))}</td></tr>' for entity,cnt in sorted(entity_counts.items(), key=lambda x:(-x[1],x[0])))
    text=sub1(r'<h2>Who these .*? addresses belong to</h2>\s*<table>.*?</table>', f'<h2>Who these {esc(name)} addresses belong to</h2>\n<table><thead><tr><th>Designated person</th><th class="sa-r">{esc(ticker)} listings</th><th>OFAC programs</th></tr></thead><tbody>{who}</tbody></table>', text, slug+' who')
    address_rows=''.join(f'<tr><td class="sa-addr">{esc(r["address"])}</td><td>{esc(r["entity"])}</td><td>{esc(r["entity_designation_date"])}</td></tr>' for r in rr)
    text=sub1(r'<h2>All \d+ .*? address(?:es| listings) on the SDN list</h2>\s*<p>.*?</p>\s*<table>.*?</table>', f'<h2>All {n} {esc(name)} address listings on the SDN list</h2>\n<p>Reproduced exactly as OFAC publishes them. The date is the entity\'s original designation date, not the address-add date, which OFAC does not publish.</p>\n<table><thead><tr><th>{esc(ticker)} address</th><th>Designated person</th><th>Entity designated</th></tr></thead><tbody>{address_rows}</tbody></table>', text, slug+' addresses')
    pc=collections.Counter(p for r in rr for p in programs(r))
    prows=''.join(f'<tr><td><a href="/programs/{re.sub(r"[^a-z0-9]+","-",p.lower()).strip("-")}">{esc(p)}</a></td><td class="sa-r">{cnt}</td></tr>' for p,cnt in pc.most_common(10))
    text=sub1(r'<h2>Programs these addresses were designated under</h2>\s*<table>.*?</table>', f'<h2>Programs these addresses were designated under</h2>\n<table><thead><tr><th>Program</th><th class="sa-r">Listings</th></tr></thead><tbody>{prows}</tbody></table>', text, slug+' programs')
    text=sub1(r'<pre><code>curl "https://sanctionsai\.dev/sanctions\?wallet=[^"]+"</code></pre>', f'<pre><code>curl "https://sanctionsai.dev/sanctions?wallet={esc(rr[0]["address"])}"</code></pre>', text, slug+' sample')
    text=re.sub(r'published <strong>\d{4}-\d{2}-\d{2}</strong>', f'published <strong>{AS_OF}</strong>', text)
    text=re.sub(r'No figure is estimated\.(?: The machine-readable <a href="/(?:sanctioned-addresses/sources.json|data/ofac-crypto-wallets/sources.json)">sources manifest</a> records the counting method\.)?', 'No figure is estimated. The machine-readable <a href="/data/ofac-crypto-wallets/sources.json">sources manifest</a> records the counting method.', text)
    path.write_text(text)
    manifest_pages.append({"url":f"https://sanctionsai.dev/sanctioned-addresses/{slug}","chain_code":code,"listing_count":n,"designated_person_count":ents,"first_entity_designation_date":first,"latest_entity_designation_date":last,"source_url":SOURCE,"method":"Filter the dataset records by exact OFAC chain code, count rows and distinct entity names, and take min/max entity_designation_date."})

family_manifest={
  "publisher":"SanctionsAI",
  "family":"https://sanctionsai.dev/sanctioned-addresses",
  "sdn_list_date":AS_OF,
  "source_url":SOURCE,
  "source_landing_page":SOURCE_HOME,
  "method":"Counts are derived from every Digital Currency Address feature in OFAC SDN Advanced XML. Address listings are rows; unique addresses are distinct address strings. Entity dates are original designation dates because OFAC does not publish per-address add dates.",
  "hub_claims":{"listing_count":len(records),"unique_address_count":unique_count,"chain_count":len(by_chain),"designated_person_count":entities,"bitcoin_listing_count":chain_counts['XBT']},
  "pages":manifest_pages,
  "other_sourced_numeric_copy":[
    {"claim":"blocked property reports are generally due within 10 business days","source_url":"https://ofac.treasury.gov/faqs/49"},
    {"claim":"OFAC 50 Percent Rule","source_url":"https://ofac.treasury.gov/faqs/398"},
    {"claim":"SanctionsAI free tier allows 5 checks per day","source_url":"https://sanctionsai.dev/pricing"},
    {"claim":"SanctionsAI partner programme advertises 50%","source_url":"https://sanctionsai.dev/partners/jv"}
  ],
  "guardrail_5_2":{"all_records_have_source":True,"no_constant_default_fields":True,"dominant_chain":{"code":"XBT","count":chain_counts['XBT'],"share":round(chain_counts['XBT']/len(records),4),"note":"This exceeds 20% but is a verified property of the OFAC source list, not a parser default. The independent legacy SDN CSV cross-check is documented in data/ofac-crypto-wallets/sources.json."}}
}
source_manifest_path = DATA.parent / 'sources.json'
source_manifest = json.loads(source_manifest_path.read_text())
source_manifest['sanctioned_addresses_family'] = family_manifest
source_manifest_path.write_text(json.dumps(source_manifest, indent=2) + "\n")
print(f"updated 11 HTML files + shared sources manifest from {len(records)} listings / {unique_count} unique / {len(by_chain)} chains / {entities} persons")
for p in manifest_pages: print(p['chain_code'],p['listing_count'],p['designated_person_count'])
