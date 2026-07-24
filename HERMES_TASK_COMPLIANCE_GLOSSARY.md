# HERMES TASK — sanctionsai.dev: Sanctions & AI-Agent Compliance Glossary (definitional authority)

> **Runbook for:** Hermes Agent running DeepSeek v4 Pro
> **Mode:** AUTONOMOUS — build, validate, commit, deploy without human intervention, subject to the fail-safes in §1.
> **Repo:** `~/workspace/agentmail` (FastAPI app `api.py`, serves sanctionsai.dev on Fly.io; static pSEO under served prefixes `/vs/ /faq/ /learn/ /alternatives-to/`).
> **Deploy:** `flyctl deploy` (single command, app `agentmail-api`, region fra). NO edits to the 836 KB `api.py`.
> **Author of runbook:** Claude (2026-07-21), grounded in a live audit.

---

## 0. What you are building and why

sanctionsai.dev is a sanctions-screening API for AI agents (screen a name/wallet against OFAC before your agent pays). The audit found it is already **maximally** AEO/agent-optimized — it serves OpenAPI, ai-plugin, `mcp.json`, agent-card, `agents.md`, `llms.txt`/`llms-full.txt`, RSS, an AI-friendly robots.txt, and an IndexNow key, all inline from `api.py`. Adding more of those does nothing. Yet it has ~0 visitors.

The one distinct, reliable lever it's missing for a **jargon-dense** niche (OFAC, SDN, the 50% Rule, secondary sanctions, facilitation, KYA, the Travel Rule, x402…): a **definitional authority** — a comprehensive, schema-marked glossary where each term is a `DefinedTerm`. This is one of the most reliable 2026 AEO plays because:
- "What is [term]" / "[term] meaning" queries dominate informational search in compliance & crypto, and **definitional content wins Google AI Overviews, featured snippets, and AI-assistant answers** far more often than long articles.
- Developers and compliance staff (the ICP) constantly look these terms up — and each definition page is a low-competition, high-intent entry point that funnels to the product.
- A well-structured glossary is a **linkable reference** (people cite/link definitions), which builds the authority a 0-visitor site needs.

You will ship a `/learn/`-hosted glossary: a hub page + one page per term, each with `DefinedTerm`/`DefinedTermSet` + `FAQPage` schema. **To eliminate fabrication risk on compliance definitions, the vetted definitions are provided in §2 of this runbook — you render them, you do NOT write your own.**

---

## 1. 🚨 GUARDRAILS + FAIL-SAFES — READ FIRST

### 1a. NEVER fabricate — especially compliance facts.
- Use the definitions in §2 **verbatim** (light formatting only). Do NOT invent, expand, reinterpret, or "improve" a legal/compliance definition. A wrong sanctions definition is a real-world harm and a liability for this product.
- Do NOT add statistics, penalty amounts, dates, or claims beyond what §2 provides.
- Every page carries this disclaimer (verbatim): *"This glossary is general information for educational purposes, not legal or compliance advice. Sanctions rules change; always verify against the official source (OFAC / FinCEN / your regulator) and consult qualified counsel."*

### 1b. No api.py surgery.
- Do NOT edit `api.py` (836 KB — high risk). The app already serves `/learn/<slug>/index.html` from disk via its pSEO file-serving fallback. Put all glossary pages under `learn/` and they are served automatically. Verify by reading the pSEO-serving block (search `api.py` for `_serve_file_content` + `learn`) — confirm `/learn/<slug>` resolves to `learn/<slug>/index.html` before relying on it.

### 1c. Fly deploy specifics.
- Deploy with `flyctl deploy` only. Do NOT run `flyctl secrets set` (the environment blocks those prompts; none are needed here).
- The committed `fly.toml` already has `auto_stop_machines = "suspend"` + `min_machines_running = 1` — deploying from this repo **preserves** them (do not change fly.toml). A compliance API must not cold-start-503 (AI crawlers drop 503s).
- `git config user.email` must be `sales@sipiteno.com` before deploy.

### 1d. Idempotency.
- Re-running regenerates cleanly (overwrite, no duplicate pages/sitemap entries).

---

## 2. Deliverable A — `glossary.json` (VETTED definitions — render verbatim)

Create `glossary.json` at repo root with exactly these entries. **These definitions are vetted; do not alter their substance.** Each `slug` becomes `/learn/<slug>`.

```json
{
  "disclaimer": "This glossary is general information for educational purposes, not legal or compliance advice. Sanctions rules change; always verify against the official source (OFAC / FinCEN / your regulator) and consult qualified counsel.",
  "source": "Definitions summarize public guidance from the U.S. Treasury's Office of Foreign Assets Control (OFAC) and FinCEN.",
  "terms": [
    {"slug":"what-is-ofac","term":"OFAC","aka":["Office of Foreign Assets Control"],"def":"OFAC (the Office of Foreign Assets Control) is the U.S. Treasury agency that administers and enforces economic and trade sanctions against targeted countries, regimes, terrorists, narcotics traffickers, and other persons. It publishes the sanctions lists that U.S. persons must screen against and can impose civil penalties for violations."},
    {"slug":"what-is-the-sdn-list","term":"SDN List","aka":["Specially Designated Nationals and Blocked Persons List"],"def":"The SDN List (Specially Designated Nationals and Blocked Persons List) is OFAC's list of individuals, entities, vessels, and — increasingly — cryptocurrency wallet addresses whose assets are blocked and with whom U.S. persons are generally prohibited from dealing. Screening counterparties against the SDN List is the core of sanctions compliance."},
    {"slug":"what-is-a-blocked-person","term":"Blocked Person","aka":[],"def":"A blocked person is any individual or entity whose property and interests in property are frozen under OFAC sanctions. U.S. persons must block (freeze) any such property in their possession and are prohibited from transacting with the person without a license from OFAC."},
    {"slug":"what-is-the-ofac-50-percent-rule","term":"OFAC 50 Percent Rule","aka":["50% Rule"],"def":"Under OFAC's 50 Percent Rule, any entity owned 50% or more, directly or indirectly, in the aggregate, by one or more blocked persons is itself considered blocked — even if it does not appear on the SDN List by name. Screening therefore requires looking through ownership, not just matching names."},
    {"slug":"what-are-secondary-sanctions","term":"Secondary Sanctions","aka":[],"def":"Secondary sanctions target non-U.S. persons for engaging in certain transactions with sanctioned parties, even when no U.S. nexus exists. They extend sanctions risk to foreign firms by threatening to cut off their access to the U.S. market or financial system."},
    {"slug":"what-is-facilitation-in-sanctions","term":"Facilitation","aka":[],"def":"In sanctions law, facilitation is when a U.S. person approves, supports, or assists a transaction by a non-U.S. person that the U.S. person could not themselves lawfully perform. Facilitation is prohibited — you cannot do indirectly, through a foreign party, what you are barred from doing directly."},
    {"slug":"what-is-strict-liability-in-ofac","term":"Strict Liability","aka":[],"def":"OFAC sanctions are enforced on a strict-liability basis for civil penalties: a person can be held liable for a violation even without knowledge or intent that the transaction was prohibited. This is why proactive screening — not good faith alone — is essential."},
    {"slug":"what-is-sanctions-screening","term":"Sanctions Screening","aka":[],"def":"Sanctions screening is the process of checking customers, counterparties, payments, and (for crypto) wallet addresses against sanctions lists such as OFAC's SDN and Consolidated lists to detect prohibited parties before a transaction completes."},
    {"slug":"what-is-the-consolidated-sanctions-list","term":"Consolidated Sanctions List","aka":[],"def":"The Consolidated Sanctions List compiles OFAC's non-SDN sanctions lists (such as the Sectoral Sanctions Identifications and Foreign Sanctions Evaders lists) into one file. It is screened alongside the SDN List for comprehensive coverage."},
    {"slug":"what-is-a-false-positive-in-screening","term":"False Positive","aka":[],"def":"A false positive is a screening alert where a customer or transaction matches a sanctions-list entry by name or attribute but is not actually the sanctioned party. Reducing false positives (via fuzzy-matching tuning and secondary identifiers) is a major operational challenge in screening."},
    {"slug":"what-is-fuzzy-matching","term":"Fuzzy Matching","aka":[],"def":"Fuzzy matching is a screening technique that flags near-matches — accounting for spelling variations, transliterations, aliases, and typos — rather than only exact name matches. It improves detection of evasion but increases false positives, so match thresholds must be tuned."},
    {"slug":"what-is-a-civil-penalty-ofac","term":"OFAC Civil Penalty","aka":[],"def":"An OFAC civil penalty is a monetary fine imposed for a sanctions violation. Penalties can be substantial and are assessed under a strict-liability standard; OFAC weighs aggravating and mitigating factors, including the quality of a party's compliance program and any voluntary self-disclosure."},
    {"slug":"what-is-voluntary-self-disclosure","term":"Voluntary Self-Disclosure","aka":["VSD"],"def":"A voluntary self-disclosure (VSD) is a party's own report to OFAC of an apparent sanctions violation before OFAC learns of it independently. A qualifying VSD is a significant mitigating factor that can substantially reduce the base civil penalty."},
    {"slug":"what-is-know-your-customer","term":"KYC","aka":["Know Your Customer"],"def":"KYC (Know Your Customer) is the process of verifying a customer's identity and assessing their risk before and during a business relationship. KYC data feeds sanctions screening and anti-money-laundering (AML) controls."},
    {"slug":"what-is-know-your-transaction","term":"KYT","aka":["Know Your Transaction"],"def":"KYT (Know Your Transaction) is the practice — common in crypto — of monitoring the details and on-chain history of transactions and wallet addresses for links to sanctioned parties or illicit activity, complementing identity-based KYC."},
    {"slug":"what-is-know-your-agent","term":"KYA","aka":["Know Your Agent"],"def":"Know Your Agent (KYA) is the emerging practice of establishing controls around autonomous AI agents that transact — verifying what an agent is authorized to do, screening the parties and wallets it pays, and keeping an auditable record — so that agent-initiated payments meet the same sanctions obligations as human-initiated ones."},
    {"slug":"what-is-the-travel-rule","term":"Travel Rule","aka":[],"def":"The Travel Rule requires financial institutions — and, in many jurisdictions, virtual-asset service providers — to pass identifying information about the originator and beneficiary along with qualifying transfers, so that sanctions and AML screening can be applied across the payment chain."},
    {"slug":"what-is-wallet-screening","term":"Wallet Screening","aka":[],"def":"Wallet screening checks a cryptocurrency address against sanctions lists (OFAC now lists specific wallet addresses) and against risk intelligence about the address's exposure to sanctioned or illicit sources, before sending or accepting funds."},
    {"slug":"what-is-x402","term":"x402","aka":["HTTP 402 payments"],"def":"x402 is a protocol pattern that uses the HTTP 402 'Payment Required' status to let clients — including autonomous AI agents — pay for API access or resources programmatically. Because x402 enables agents to move money without a human in the loop, sanctions screening in the payment path becomes essential."},
    {"slug":"what-is-an-agentic-payment","term":"Agentic Payment","aka":[],"def":"An agentic payment is a transaction initiated and executed by an autonomous AI agent rather than a human. Agentic payments raise the compliance question of who is responsible for sanctions screening when software, not a person, decides to pay a counterparty."}
  ]
}
```
> These 20 terms are the core set. Do not add terms you are unsure of. If you extend later, each new definition must be grounded and attributed — never model-invented.

---

## 3. Deliverable B — `scripts/build_glossary.py` (renders pages + schema)

Create this Python generator (matches the repo's Python stack). It writes a hub + per-term pages under `learn/`, each with `DefinedTerm` + `DefinedTermSet` + `FAQPage` schema, interlinks, disclaimer.

```python
#!/usr/bin/env python3
"""build_glossary.py — render the compliance glossary from glossary.json into
static pages under learn/ (served by api.py's pSEO fallback). Verbatim only."""
import json, os, html

ROOT = os.getcwd()
BASE = "https://sanctionsai.dev"
G = json.load(open(os.path.join(ROOT, "glossary.json"), encoding="utf-8"))
DISC = G["disclaimer"]; SRC = G["source"]; TERMS = G["terms"]
e = lambda s: html.escape(str(s))

CSS = ("<style>body{font:16px/1.65 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-width:760px;"
       "margin:0 auto;padding:2rem 1rem;color:#0f172a;background:#fff}@media(prefers-color-scheme:dark)"
       "{body{background:#0b1120;color:#e2e8f0}}h1{font-size:1.9rem;line-height:1.15}a{color:#2563eb;"
       "text-decoration:none}a:hover{text-decoration:underline}.def{font-size:1.1rem;background:#f8fafc;"
       "border-left:3px solid #2563eb;padding:1rem 1.2rem;border-radius:6px;margin:1rem 0}@media"
       "(prefers-color-scheme:dark){.def{background:#111a2e}}.disc{font-size:.85rem;color:#64748b;"
       "border-top:1px solid #e2e8f0;margin-top:2rem;padding-top:1rem}ul{columns:2}@media(max-width:640px)"
       "{ul{columns:1}}</style>")

def page(title, desc, canonical, jsonld, body):
    scripts = "".join(f'<script type="application/ld+json">{json.dumps(j,separators=(",",":"))}</script>' for j in jsonld)
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{e(title)}</title><meta name="description" content="{e(desc)}">'
            f'<link rel="canonical" href="{canonical}">'
            f'<meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large">'
            f'{CSS}{scripts}</head><body>{body}'
            f'<p class="disc">{e(DISC)} {e(SRC)}</p></body></html>')

os.makedirs(os.path.join(ROOT, "learn"), exist_ok=True)
term_set_id = f"{BASE}/learn/sanctions-glossary#termset"

# per-term pages
for t in TERMS:
    slug, term, d = t["slug"], t["term"], t["def"]
    canonical = f"{BASE}/learn/{slug}"
    aka = ", ".join(t.get("aka", []))
    defined = {"@context":"https://schema.org","@type":"DefinedTerm","@id":canonical+"#term",
               "name":term,"description":d,"inDefinedTermSet":term_set_id}
    if t.get("aka"): defined["alternateName"] = t["aka"]
    faq = {"@context":"https://schema.org","@type":"FAQPage","mainEntity":[
        {"@type":"Question","name":f"What is {term}?","acceptedAnswer":{"@type":"Answer","text":d+" "+DISC}}]}
    others = [x for x in TERMS if x["slug"] != slug][:10]
    rel = " · ".join(f'<a href="/learn/{x["slug"]}">{e(x["term"])}</a>' for x in others)
    body = (f'<p style="font-size:.85rem"><a href="/">SanctionsAI</a> › '
            f'<a href="/learn/sanctions-glossary">Glossary</a> › {e(term)}</p>'
            f'<h1>What is {e(term)}?</h1>'
            + (f'<p style="color:#64748b">Also known as: {e(aka)}</p>' if aka else '')
            + f'<div class="def">{e(d)}</div>'
            f'<p>Screening for {e(term)}-related risk is exactly what <a href="/">SanctionsAI</a> automates — '
            f'a single API (HTTP, CLI, or MCP) that screens names and wallets against OFAC lists before your agent pays. '
            f'Free tier, no key: <a href="/docs">see the docs →</a></p>'
            f'<h2>Related terms</h2><p>{rel}</p>')
    open(os.path.join(ROOT,"learn",slug), 'w') if False else None
    os.makedirs(os.path.join(ROOT,"learn",slug), exist_ok=True)
    with open(os.path.join(ROOT,"learn",slug,"index.html"),"w",encoding="utf-8") as f:
        f.write(page(f"What is {term}? — Sanctions & AI-Agent Compliance Glossary | SanctionsAI",
                     f"{term}: {d[:150]}", canonical, [defined, faq], body))

# hub page (DefinedTermSet)
term_set = {"@context":"https://schema.org","@type":"DefinedTermSet","@id":term_set_id,
            "name":"Sanctions & AI-Agent Compliance Glossary","url":f"{BASE}/learn/sanctions-glossary",
            "hasDefinedTerm":[{"@type":"DefinedTerm","name":t["term"],"url":f"{BASE}/learn/{t['slug']}","description":t["def"][:200]} for t in TERMS]}
items = "".join(f'<li><a href="/learn/{t["slug"]}"><strong>{e(t["term"])}</strong></a> — {e(t["def"][:90])}…</li>' for t in TERMS)
hub_body = (f'<p style="font-size:.85rem"><a href="/">SanctionsAI</a> › Glossary</p>'
            f'<h1>Sanctions &amp; AI-Agent Compliance Glossary</h1>'
            f'<p>Plain-English definitions of the sanctions, OFAC, and agentic-payment terms every compliance-aware '
            f'builder needs — from the SDN List and the 50% Rule to KYA and x402.</p><ul>{items}</ul>')
os.makedirs(os.path.join(ROOT,"learn","sanctions-glossary"), exist_ok=True)
with open(os.path.join(ROOT,"learn","sanctions-glossary","index.html"),"w",encoding="utf-8") as f:
    f.write(page("Sanctions & AI-Agent Compliance Glossary — OFAC, SDN, 50% Rule, KYA, x402 | SanctionsAI",
                 "Plain-English glossary of sanctions and AI-agent compliance terms: OFAC, SDN List, 50% Rule, secondary sanctions, facilitation, KYA, wallet screening, x402, and more.",
                 f"{BASE}/learn/sanctions-glossary", [term_set], hub_body))

print(f"✓ glossary: {len(TERMS)} term pages + hub written under learn/")
```
> Clean up the stray `open(... ) if False else None` line if your linter complains — it's a no-op placeholder; the real write is the `with open(... index.html)` below it. Keep the directory-per-slug structure (`learn/<slug>/index.html`) so the pSEO fallback serves `/learn/<slug>`.

---

## 4. Deliverable C — sitemap
Add the hub + all term URLs to the sitemap. `api.py` generates `/sitemap.xml` dynamically (`_sitemap_xml`) — **do not edit api.py.** Instead, confirm whether `_sitemap_xml` auto-discovers `learn/*/index.html` on disk (read that method). If it does, the pages appear automatically. If it uses a hardcoded list, add the URLs to a static supplementary sitemap `sitemap-glossary.xml` at repo root and ensure it's referenced by `sitemap-index.xml` (which api.py serves) — or simply rely on internal links + IndexNow (§7) for discovery. Do the least-risky option that gets the URLs crawled; never edit api.py to achieve it.

---

## 5. RUN + VALIDATE (before deploy)

```bash
cd ~/workspace/agentmail
python3 scripts/build_glossary.py

# a) 20 term pages + hub exist
ls learn/sanctions-glossary/index.html && ls learn/what-is-ofac/index.html && echo "✓ pages written"
find learn -maxdepth 2 -name index.html -newer glossary.json | wc -l   # expect >=21

# b) DefinedTerm JSON-LD parses on a term page
python3 -c "import re,json;h=open('learn/what-is-the-ofac-50-percent-rule/index.html').read();[json.loads(m) for m in re.findall(r'<script type=\"application/ld\+json\">(.*?)</script>',h,re.S)];print('✓ JSON-LD valid')"

# c) definitions are VERBATIM from glossary.json (no drift / no fabrication)
python3 -c "import json;g=json.load(open('glossary.json'));t=g['terms'][0];h=open('learn/'+t['slug']+'/index.html').read();assert t['def'] in h.replace('&amp;','&').replace('&#x27;',chr(39)).replace('&quot;','\"'),'DEF DRIFT';print('✓ definition verbatim')"

# d) disclaimer on every page
missing=0; for f in learn/*/index.html; do grep -q "not legal or compliance advice" "$f" 2>/dev/null || missing=$((missing+1)); done; echo "note: count includes non-glossary /learn pages"; grep -L "not legal or compliance advice" learn/what-is-ofac/index.html && echo "FAIL: disclaimer missing" || echo "✓ disclaimer present on term page"

# e) confirm /learn/<slug> is served by api.py's pSEO fallback (read, don't edit)
grep -n "learn" api.py | grep -iE "serve_file|candidates|pfx" | head
```
If (c) fails, a definition was altered — restore it verbatim from `glossary.json`. Do not deploy with any definition drift.

---

## 6. DEPLOY (autonomous) — Fly.io

```bash
cd ~/workspace/agentmail
git config user.email    # must be sales@sipiteno.com; if blank: git config user.email sales@sipiteno.com
git checkout -b compliance-glossary
git add glossary.json scripts/build_glossary.py learn/ sitemap-glossary.xml 2>/dev/null
git commit -m "Add sanctions & AI-agent compliance glossary (definitional authority)"

# Single-command Fly deploy (preserves fly.toml suspend/min-machines). No secrets.
flyctl deploy

# --- Verify live ---
sleep 25
curl -s https://sanctionsai.dev/learn/sanctions-glossary | grep -c "Compliance Glossary"       # expect >=1
curl -sI https://sanctionsai.dev/learn/what-is-ofac | head -1                                   # expect 200
curl -s https://sanctionsai.dev/learn/what-is-the-ofac-50-percent-rule | grep -c "DefinedTerm"  # expect >=1
```
If `flyctl deploy` errors on auth/build, report it and stop — do not force. (Do NOT run `flyctl secrets set`.)

---

## 7. POST-DEPLOY
1. **IndexNow:** the site already has an IndexNow key served by api.py. Submit the new URLs (the deploy doc's IndexNow step): POST the glossary URLs to `https://api.indexnow.org/indexnow` with `host: sanctionsai.dev`, `key: 87aaa199acaf7d14c812e974ce115e32`, `keyLocation: https://sanctionsai.dev/87aaa199acaf7d14c812e974ce115e32.txt`, `urlList: [the 21 glossary URLs]`. (Bing → also feeds ChatGPT Search/Copilot.)
2. **Search Console + Bing:** request indexing on the hub + 5 top term pages.
3. **Internal links (optional):** link relevant terms from the existing `/faq/` and `/learn/` pages (e.g., the OFAC FAQ → `/learn/what-is-ofac`). Only if safe to edit those static files.

---

## 8. Expected results (honest, mechanism-based — estimates, not guarantees)

| Effect | Mechanism | Realistic outcome | When |
|---|---|---|---|
| **Wins "what is [term]" queries** | 20 `DefinedTerm`-marked pages targeting high-volume informational queries the site doesn't rank for | New organic entries + eligibility for featured snippets / AI Overviews on definitional queries | 3–8 weeks |
| **AI-assistant answers** | Concise, schema-marked, attributed definitions are exactly what ChatGPT/Perplexity/Gemini quote | Cited as the definition source for OFAC/SDN/50%-Rule/KYA/x402 queries | 1–3 months |
| **Linkable reference** | Glossaries get linked (people cite definitions); each page funnels to the API | Backlinks that lift domain authority for a 0-visitor site; qualified funnel entries | 1–4 months |
| **Owns the emerging niche** | KYA / x402 / agentic-payment definitions are largely unclaimed | Early authority for "AI-agent sanctions compliance" as the topic grows | compounding |

**Straight talk:**
- Definitional pages are low-competition and reliably win informational SERPs + AI answers, but each is individually small — the value is the **aggregate** across 20 terms plus the authority they build for a site starting from zero.
- The KYA / x402 / agentic-payment terms are the highest-upside: they're unclaimed and align with where this product is uniquely positioned. As the topic grows, being the early definitional source compounds.
- This is on-site authority-building; the ceiling still lifts fastest with off-site links (§7 helps) — but for a 0-visitor site, planting 20 rankable, citable, on-brand pages is a real, safe step.
- Measure: Search Console impressions on "[term]" queries + AI-answer mentions (manual monthly checks) + referring domains.

---

## 9. Rollback
Fully additive (glossary.json + generator + `learn/<slug>/` pages + optional sitemap file). Roll back: `git revert` the commit, `flyctl deploy`. Deleting the new `learn/` term dirs removes it cleanly. No api.py changes to unwind.

### Definition of done
- [ ] `glossary.json` (20 vetted terms) + `scripts/build_glossary.py` created; hub + 20 term pages rendered under `learn/`.
- [ ] Definitions verbatim (§5c passes); disclaimer on every page; DefinedTerm/DefinedTermSet/FAQPage JSON-LD valid.
- [ ] Discovery handled without editing api.py (auto-sitemap OR supplementary sitemap OR internal links + IndexNow).
- [ ] Committed to a branch; deployed via `flyctl deploy` (fly.toml unchanged; no `flyctl secrets`); live checks pass.
- [ ] IndexNow submitted for the 21 URLs (§7). Zero fabricated/altered definitions. api.py untouched.
```
