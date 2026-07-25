#!/usr/bin/env python3
"""Build the /cost-of/ competitor-pricing cluster and its hub.

Why this cluster and not another: Search Console shows sanctionsai.dev already
sitting at positions 3-5 for "world check cost", "world check pricing" and
"world check price", and position 11 for the one /cost-of/ page aimed at them —
while every page aimed at head terms ("chainalysis sanctions screening",
"ofac screening") sits past position 50. Vendor-pricing queries are the only
shape this domain currently wins, and only three of them were built.

Honesty rule, enforced by hand and worth stating because it is the whole risk
of a page like this: none of these vendors publish list prices, so this script
does NOT invent dollar ranges for them. It states the verifiable fact (pricing
is quote-gated), explains what drives the number, and compares against
SanctionsAI's own published prices, which are checkable on /pricing. Inventing
a "$30K-$150K/yr" for a vendor that has never published a figure would be a
fabrication dressed as research, and it is exactly what a competitor would
screenshot.

Re-runnable: rewrites every page from the data below, so fixing a fact here
fixes it everywhere. Writes both `<slug>/index.html` and `<slug>.html` because
api.py's static-prefix loop resolves the directory form while some older
internal links point at the flat form.
"""
import html
import json
import os

SITE = "https://sanctionsai.dev"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "cost-of")
PUBLISHED = "2026-07-25"

# SanctionsAI's own prices — verifiable at /pricing. Kept in one place so a
# price change cannot leave half the cluster quoting a stale number.
OWN = {
    "free": "5 checks/day, no API key, no signup",
    "dev": "$19/mo for 10,000 checks/month",
    "pro": "$99/mo for 100,000 checks/month",
    "x402": "$0.05 per check, pay-per-call over x402",
    "self": "MIT-licensed self-host: pip install sanctions-mcp",
}

VENDORS = [
    {
        "slug": "sumsub-pricing",
        "name": "Sumsub",
        "url": "https://sumsub.com",
        "what": "a full KYC/KYB identity-verification platform with sanctions and PEP screening as one module among many",
        "drivers": [
            ("Verification volume", "Priced per completed verification, not per screen. If you only need a sanctions check, you are still buying the identity-verification unit around it."),
            ("Module selection", "Sanctions/PEP screening, liveness, document checks, KYB and travel-rule are separate line items. The sanctions module rarely sells standalone."),
            ("Applicant retention", "Ongoing monitoring of an existing applicant is usually billed separately from the initial verification."),
            ("Region coverage", "Document coverage for additional countries changes the per-verification rate."),
        ],
        "fit": "Sumsub is the right tool when you are onboarding human users and need identity documents verified. It is the wrong shape when an autonomous agent needs a yes/no on a counterparty name or wallet before it releases a payment — there is no applicant to onboard.",
        "faqs": [
            ("Does Sumsub publish its pricing?", "No. Sumsub quotes per deployment based on verification volume and which modules you enable. There is no public price list to compare against."),
            ("Can I buy only Sumsub's sanctions screening?", "Sanctions and PEP screening is sold as a module of the verification platform rather than as a standalone screening API. Ask explicitly whether a screening-only contract is available before you scope the rest."),
            ("What is the cheapest way to screen a name against OFAC?", "The free tier of an OFAC-specific API. SanctionsAI allows 5 checks/day with no API key and no signup; paid plans start at $19/month for 10,000 checks."),
        ],
    },
    {
        "slug": "elliptic-pricing",
        "name": "Elliptic",
        "url": "https://www.elliptic.co",
        "what": "an enterprise blockchain-analytics platform: wallet risk scoring, transaction tracing and typology detection across chains",
        "drivers": [
            ("Chain coverage", "Priced by which blockchains and asset classes you need traced, not by how many addresses you screen."),
            ("Product line", "Lens (wallet screening), Navigator (transaction monitoring) and Investigator (forensics) are separate products with separate contracts."),
            ("Seats", "Investigator is seat-priced for analysts; an API-only deployment and a team-of-analysts deployment are very different numbers."),
            ("Contract term", "Annual minimums are standard; there is no month-to-month entry point."),
        ],
        "fit": "Elliptic answers \"how risky is this address, and what is it connected to\" — a forensic question. An OFAC screen answers \"is this counterparty on a sanctions list right now\" — a compliance question with a binary answer. If you only need the second one, an analytics contract is a large amount of capability you will not call.",
        "faqs": [
            ("Does Elliptic publish pricing?", "No. Elliptic is quote-based with annual contracts and no public price list or free tier."),
            ("Is Elliptic the same as sanctions screening?", "No. Elliptic scores blockchain risk, including exposure to sanctioned entities several hops away. A sanctions screen is a direct list match against the OFAC SDN list. They answer different questions and many teams need only the second."),
            ("What does OFAC wallet screening cost without an analytics contract?", "SanctionsAI screens wallet addresses against the OFAC SDN list on a free tier of 5 checks/day, $19/month for 10,000 checks, or $0.05 per call over x402."),
        ],
    },
    {
        "slug": "trm-labs-pricing",
        "name": "TRM Labs",
        "url": "https://www.trmlabs.com",
        "what": "a blockchain intelligence platform used by exchanges, banks and government agencies for risk scoring and investigations",
        "drivers": [
            ("Deployment scope", "Screening, monitoring and forensics are packaged differently; a screening-only scope and a full intelligence deployment are separate conversations."),
            ("API call volume", "Wallet-screening calls are metered, usually with an annual committed volume rather than pay-as-you-go."),
            ("Seats and training", "Analyst seats for the investigations UI, plus onboarding, are commonly priced on top of the data contract."),
            ("Implementation", "Enterprise blockchain-intelligence rollouts routinely run months, and that engineering time is a real part of the cost even when the vendor does not bill for it."),
        ],
        "fit": "TRM is built for a compliance team with analysts in the loop. An agent that has to decide in under a second whether to release a payment has no analyst and no time for a case queue — it needs a list match and an audit record.",
        "faqs": [
            ("Does TRM Labs publish pricing?", "No. TRM Labs quotes per deployment and does not list prices publicly or offer a self-serve free tier."),
            ("Is there a free tier for TRM Labs?", "There is no public self-serve free tier. Evaluation is handled through their sales process."),
            ("What is the cheapest wallet-screening API?", "For OFAC-list screening specifically, SanctionsAI is free for 5 checks/day with no API key, and $0.05 per check over x402 with no contract."),
        ],
    },
    {
        "slug": "dow-jones-rdc-pricing",
        "name": "Dow Jones Risk & Compliance",
        "url": "https://www.dowjones.com/professional/risk/",
        "what": "a risk-data business: sanctions, PEP, adverse-media and state-ownership data licensed as feeds and through an API",
        "drivers": [
            ("Data scope", "Sanctions lists, PEP data, adverse media and state-ownership research are licensed separately. Sanctions alone is the cheapest slice and rarely the one that is quoted."),
            ("Delivery method", "A bulk data feed you host, and a hosted screening API, are priced on different models."),
            ("Named users", "Research-database access is licensed per named user, so headcount moves the number independently of screening volume."),
            ("Redistribution rights", "If you screen on behalf of your own customers, redistribution terms apply and change the contract materially."),
        ],
        "fit": "Dow Jones sells research depth — the state-ownership data behind the OFAC 50% Rule is genuinely hard to replicate. If your obligation is direct SDN list matching before a payment, you are licensing a research library to answer a lookup.",
        "faqs": [
            ("Does Dow Jones Risk & Compliance publish pricing?", "No. It is licensed by data scope, delivery method and named users, quoted per organisation."),
            ("Do I need Dow Jones data for OFAC compliance?", "Not for direct SDN list matching — the OFAC SDN list is published by the US Treasury and is free to use. Licensed data becomes relevant for PEP screening, adverse media, and 50% Rule ownership research."),
            ("Is the OFAC SDN list free?", "Yes. The US Treasury publishes it. SanctionsAI serves it through an API with a free tier of 5 checks/day; you are paying for the interface, freshness and audit trail, not for the list."),
        ],
    },
    {
        "slug": "scorechain-pricing",
        "name": "Scorechain",
        "url": "https://www.scorechain.com",
        "what": "a crypto compliance platform for wallet risk scoring and transaction monitoring, aimed at European VASPs",
        "drivers": [
            ("Address volume", "Priced against how many addresses you score per period."),
            ("Chain modules", "Bitcoin, Ethereum and other chains are enabled as separate modules."),
            ("Seats", "Dashboard access for compliance staff is seat-priced alongside API access."),
            ("Travel Rule", "Travel Rule messaging, if you need it, is a separate product from risk scoring."),
        ],
        "fit": "Scorechain is a reasonable mid-market fit for a VASP with a compliance function. It is still a platform subscription, which is a poor match for a single pre-payment list check embedded in an agent's code path.",
        "faqs": [
            ("Does Scorechain publish pricing?", "No. Scorechain quotes based on address volume, chain modules and seats."),
            ("Is Scorechain cheaper than Chainalysis or Elliptic?", "Scorechain positions itself at the mid-market rather than the enterprise tier, but since none of the three publish list prices, any ranking is a claim about positioning and not a verified price comparison."),
            ("Do I need risk scoring, or just sanctions screening?", "Sanctions screening is the legal obligation: do not transact with a designated party. Risk scoring is a judgement about proximity to illicit activity. Many teams need the first and adopt the second later."),
        ],
    },
]

CATEGORY = {
    "slug": "ofac-screening-api-pricing",
    "title": "What Does an OFAC Screening API Cost in 2026?",
    "desc": "OFAC screening API pricing in 2026: the SDN list itself is free from the US Treasury, so what you pay for is freshness, latency and audit trail. What each pricing model actually costs.",
}

CSS = """
:root{color-scheme:light dark}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;line-height:1.65;color:#0a0a0a;background:#fff;max-width:760px;margin:0 auto;padding:2rem 1.25rem}
h1{font-size:2.1rem;line-height:1.2;margin:.3em 0}
h2{font-size:1.45rem;margin-top:2.2rem;border-bottom:2px solid #e5e7eb;padding-bottom:.3rem}
h3{font-size:1.12rem;margin-top:1.5rem}
a{color:#0066cc;text-decoration:none}a:hover{text-decoration:underline}
.lede{font-size:1.12rem;color:#374151;margin-bottom:1.5rem}
table{border-collapse:collapse;width:100%;margin:1rem 0;font-size:.95rem;display:block;overflow-x:auto}
th,td{border:1px solid #e5e7eb;padding:.6rem .75rem;text-align:left}
th{background:#f9fafb;font-weight:600}
.callout{background:#f0f7ff;border-left:4px solid #0066cc;padding:1rem 1.25rem;margin:1.5rem 0;border-radius:0 .375rem .375rem 0}
.callout.warn{background:#fef3c7;border-left-color:#d97706}
.related-links{background:#f9fafb;padding:1rem 1.25rem;border-radius:.5rem;margin-top:2rem}
.related-links ul{list-style:none;padding-left:0}.related-links li{padding:.25rem 0}
.cta{background:linear-gradient(135deg,#0066cc,#004499);color:#fff;padding:2rem;border-radius:.75rem;margin-top:2rem;text-align:center}
.cta h2{color:#fff;border:none;margin-top:0}.cta a{color:#fff;text-decoration:underline}
footer{margin-top:3rem;padding-top:1.5rem;border-top:1px solid #e5e7eb;color:#6b7280;font-size:.9rem}
@media(prefers-color-scheme:dark){
 body{background:#0a0a0a;color:#e6e6e6}
 h2{border-bottom-color:#262626}
 .lede{color:#a3a3a3}
 a{color:#4da3ff}
 th{background:#141414}th,td{border-color:#262626}
 .callout{background:#0e1a26;border-left-color:#4da3ff}
 .callout.warn{background:#241d05;border-left-color:#d97706}
 .related-links{background:#111}
 footer{border-top-color:#262626;color:#8a8a8a}
}
""".strip()

POSTHOG = ('<script>!function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){'
           'function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e]'
           '.concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",'
           'p.crossOrigin="anonymous",p.async=!0,p.src=s.api_host.replace(".i.posthog.com","-assets.i.posthog.com")'
           '+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;'
           'for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){var e="posthog";'
           'return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)'
           '+".people (stub)"},o="capture identify alias people.set people.set_once set_config register '
           'register_once unregister opt_out_capturing has_opted_out_capturing opt_in_capturing reset '
           'isFeatureEnabled onFeatureFlags getFeatureFlag getFeatureFlagPayload reloadFeatureFlags group '
           'updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures getActiveMatchingSurveys getSurveys"'
           '.split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=!0}(document,window.posthog||[]);'
           'posthog.init("phc_lyZCgvTpicjLzAO3rY2GhxuX5WUc5jQjP8ZVwwJqauX",{api_host:"https://eu.i.posthog.com",'
           'person_profiles:"identified_only"})</script>')

FOOTER = ('<footer><p><a href="/cost-of">All vendor pricing breakdowns</a> · '
          '<a href="/pricing">SanctionsAI pricing</a> · <a href="/vs">Comparisons</a> · '
          '<a href="/">Home</a></p>'
          '<p>&copy; 2026 SanctionsAI · sanctionsai.dev. Vendor pricing is quote-gated and set by the vendor; '
          'figures quoted for SanctionsAI are our own published prices. Not legal or compliance advice.</p></footer>')


def esc(s):
    return html.escape(html.unescape(str(s)), quote=True)


def clip(s, n=157):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0].rstrip(" ,;:—-") + "…"


def page(slug, title, desc, h1, lede, body, faqs, crumb):
    md = clip(desc)
    url = f"{SITE}/cost-of/{slug}" if slug else f"{SITE}/cost-of"
    graph = [
        {"@type": "Article", "headline": h1, "description": md,
         "author": {"@type": "Organization", "name": "SanctionsAI", "url": SITE + "/"},
         "publisher": {"@type": "Organization", "name": "SanctionsAI", "url": SITE + "/",
                       "logo": {"@type": "ImageObject", "url": SITE + "/og.png"}},
         "image": SITE + "/og.png", "inLanguage": "en-US",
         "mainEntityOfPage": {"@type": "WebPage", "@id": url},
         "datePublished": PUBLISHED, "dateModified": PUBLISHED},
        {"@type": "BreadcrumbList", "itemListElement": (
            [{"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
             {"@type": "ListItem", "position": 2, "name": "Vendor pricing", "item": SITE + "/cost-of"}]
            + ([{"@type": "ListItem", "position": 3, "name": crumb, "item": url}] if slug else []))},
    ]
    if faqs:
        graph.append({"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]})
    faq_html = "".join(f"<h3>{esc(q)}</h3><p>{a}</p>" for q, a in faqs)
    return f"""<!DOCTYPE html>
<html lang="en-US">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(md)}">
<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">
<meta name="theme-color" content="#0a0a0a">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="canonical" href="{url}">
<link rel="alternate" hreflang="en-US" href="{url}">
<link rel="alternate" hreflang="x-default" href="{url}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="SanctionsAI">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(md)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE}/og.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(md)}">
<meta name="twitter:image" content="{SITE}/og.png">
<script type="application/ld+json">{json.dumps({"@context": "https://schema.org", "@graph": graph})}</script>
<style>{CSS}</style>
{POSTHOG}
</head>
<body>
<main>
<h1>{esc(h1)}</h1>
<p class="lede">{lede}</p>
{body}
<h2>Frequently asked questions</h2>
{faq_html}
<div class="cta">
<h2>Screen against the OFAC SDN list for free</h2>
<p>5 checks a day, no API key and no signup. Paid plans start at $19/month.
<a href="/pricing">See pricing</a> or <a href="/docs">read the docs</a>.</p>
</div>
</main>
{FOOTER}
</body>
</html>
"""


def vendor_page(v):
    others = [o for o in VENDORS if o["slug"] != v["slug"]][:3]
    drivers = "".join(
        f"<tr><td><strong>{esc(d)}</strong></td><td>{t}</td></tr>" for d, t in v["drivers"])
    related = "".join(
        f'<li><a href="/cost-of/{o["slug"]}">What does {esc(o["name"])} cost?</a></li>' for o in others)
    body = f"""
<div class="callout warn">
<p><strong>{esc(v["name"])} does not publish a price list.</strong> Every figure you will find online is
someone's estimate of someone else's contract. This page does not add another one — it sets out what
actually moves the number, so the quote you receive is one you can read.</p>
</div>

<h2>What you are buying</h2>
<p>{esc(v["name"])} is {v["what"]}. That framing matters more than the number: the cost of a
compliance tool is mostly a function of how much of it you will use.</p>

<h2>What drives the {esc(v["name"])} quote</h2>
<table>
<thead><tr><th>Cost driver</th><th>How it moves the number</th></tr></thead>
<tbody>{drivers}</tbody>
</table>

<h2>Questions to put in writing before you sign</h2>
<ul>
<li>What is the annual minimum, and what is the shortest available term?</li>
<li>What happens on overage — hard stop, or per-unit billing at a higher rate?</li>
<li>Which modules are in the quoted figure and which are add-ons at renewal?</li>
<li>Is sanctions screening available without the surrounding platform?</li>
<li>What is the contractual latency, and is it measured at the API or in the UI?</li>
<li>How many engineering weeks does the vendor expect implementation to take?</li>
</ul>

<h2>Is {esc(v["name"])} the right shape for your problem?</h2>
<p>{v["fit"]}</p>

<h2>What SanctionsAI costs, for comparison</h2>
<p>These are published prices, not estimates — you can check them on
<a href="/pricing">the pricing page</a> before you talk to anyone.</p>
<table>
<thead><tr><th>Plan</th><th>Price</th></tr></thead>
<tbody>
<tr><td>Free</td><td>{esc(OWN["free"])}</td></tr>
<tr><td>Dev</td><td>{esc(OWN["dev"])}</td></tr>
<tr><td>Pro</td><td>{esc(OWN["pro"])}</td></tr>
<tr><td>Pay-per-call</td><td>{esc(OWN["x402"])}</td></tr>
<tr><td>Self-host</td><td>{esc(OWN["self"])}</td></tr>
</tbody>
</table>
<p>SanctionsAI screens names and wallet addresses against the OFAC SDN list and returns a
machine-readable verdict with an audit record. It does not do blockchain forensics, identity
document verification or adverse-media research. Where you need those, the vendors on this page
are the ones that sell them — the comparison is about scope, not about who is better.</p>

<div class="related-links">
<h3>Related</h3>
<ul>
{related}
<li><a href="/cost-of/ofac-screening-api-pricing">What does an OFAC screening API cost?</a></li>
<li><a href="/cost-of">All vendor pricing breakdowns</a></li>
</ul>
</div>
"""
    title = f"How Much Does {v['name']} Cost? [2026 Pricing]"
    desc = (f"{v['name']} pricing is quote-based and not published. Here is what actually drives the "
            f"number, what to ask before you sign, and what OFAC screening costs without a platform contract.")
    lede = (f"{esc(v['name'])} does not publish list prices. What follows is the cost structure behind the "
            f"quote — and the published alternative if all you need is an OFAC list check.")
    return page(v["slug"], title, desc, f"How much does {v['name']} cost?", lede, body,
                v["faqs"], f"{v['name']} pricing")


def category_page():
    body = f"""
<div class="callout">
<p><strong>The OFAC SDN list is free.</strong> The US Treasury publishes it, and republishing it is
permitted. Nothing you pay for an OFAC screening API is payment for the data — it is payment for how
fresh it is, how fast the answer comes back, and whether you can prove afterwards that you checked.</p>
</div>

<h2>The four pricing models, and who each one suits</h2>
<table>
<thead><tr><th>Model</th><th>How it bills</th><th>Suits</th></tr></thead>
<tbody>
<tr><td>Free tier</td><td>A daily allowance, no card</td><td>Evaluation, and low-volume production where a few checks a day is genuinely the whole need</td></tr>
<tr><td>Flat monthly</td><td>A fixed fee for a monthly check allowance</td><td>Predictable volume; the cheapest model once you are past a few hundred checks a month</td></tr>
<tr><td>Per-call</td><td>Metered per screen, often over x402 for agents</td><td>Spiky or agent-driven volume where nobody can forecast the month</td></tr>
<tr><td>Enterprise contract</td><td>Annual, quote-gated, seat and module based</td><td>Regulated institutions that need PEP data, adverse media and analyst tooling alongside screening</td></tr>
</tbody>
</table>

<h2>What actually costs money</h2>
<h3>Freshness</h3>
<p>OFAC updates the SDN list without a schedule. A cached copy that is a week old is a copy that can
clear a party who was designated on Tuesday, and strict liability means the staleness is your problem,
not your vendor's. Ask how often the list is refreshed and what the vendor does when a refresh fails.</p>
<h3>Latency</h3>
<p>If the screen sits in front of a payment, its latency is added to every payment. A batch job that
returns overnight and an API that returns in under 100&nbsp;ms are not the same product, and the second
is what an autonomous agent needs.</p>
<h3>Proof</h3>
<p>The screen is only worth what you can demonstrate about it later. A verdict with no record of which
list version produced it is not evidence. If you ever file a voluntary self-disclosure, the audit trail
is the part that matters — see <a href="/how-to/file-voluntary-disclosure">how to file an OFAC VSD</a>.</p>
<h3>Scope you will not use</h3>
<p>Most of the price difference between an OFAC screening API and an enterprise compliance platform is
capability, not margin. PEP databases, adverse-media research, ownership data behind the
<a href="/learn/what-is-the-ofac-50-percent-rule">50% Rule</a> and blockchain forensics are genuinely
expensive to build. The question is not whether they are worth it in general — it is whether your
transaction flow calls them.</p>

<h2>What SanctionsAI charges</h2>
<table>
<thead><tr><th>Plan</th><th>Price</th></tr></thead>
<tbody>
<tr><td>Free</td><td>{esc(OWN["free"])}</td></tr>
<tr><td>Dev</td><td>{esc(OWN["dev"])}</td></tr>
<tr><td>Pro</td><td>{esc(OWN["pro"])}</td></tr>
<tr><td>Pay-per-call</td><td>{esc(OWN["x402"])}</td></tr>
<tr><td>Self-host</td><td>{esc(OWN["self"])}</td></tr>
</tbody>
</table>
<p>The self-host option is the honest floor on this market: the list is public and the matching logic is
MIT-licensed, so if your volume ever makes a hosted API the wrong trade, you can run it yourself and
pay nothing.</p>

<div class="related-links">
<h3>Vendor pricing breakdowns</h3>
<ul>
<li><a href="/cost-of/refinitiv-worldcheck-pricing">Refinitiv World-Check</a></li>
<li><a href="/cost-of/chainalysis-pricing">Chainalysis</a></li>
<li><a href="/cost-of/complyadvantage-pricing">ComplyAdvantage</a></li>
{"".join(f'<li><a href="/cost-of/{v["slug"]}">{esc(v["name"])}</a></li>' for v in VENDORS)}
</ul>
</div>
"""
    faqs = [
        ("Is the OFAC SDN list free to use?",
         "Yes. The US Treasury publishes the SDN list and it can be used and republished. What screening vendors charge for is refresh frequency, response latency, fuzzy matching quality and the audit record — not the underlying data."),
        ("What is a reasonable price for OFAC screening?",
         "For direct SDN list matching, anything from zero upward. SanctionsAI is free for 5 checks/day and $19/month for 10,000. Enterprise compliance platforms cost far more because they bundle PEP data, adverse media and analyst tooling that direct list matching does not require."),
        ("Why do compliance vendors hide their pricing?",
         "Because the contracts are scoped per customer: data modules, seats, redistribution rights and volume all move the number, so no single list price would be accurate. It also means published estimates you find online describe one deployment and not yours."),
        ("Do I need a paid tool to be OFAC compliant?",
         "OFAC requires that you do not transact with designated parties; it does not require a particular vendor. What matters is that the screen happens before funds move, against a current list, with a record. That obligation can be met with a free tier or self-hosted code — this is not legal advice, and a compliance officer should confirm it against your obligations."),
    ]
    lede = ("The SDN list is free. Everything you pay for an OFAC screening API is freshness, latency and "
            "proof — here is what each pricing model actually costs and which one fits your volume.")
    return page(CATEGORY["slug"], CATEGORY["title"], CATEGORY["desc"],
                "What does an OFAC screening API cost in 2026?", lede, body, faqs,
                "OFAC screening API pricing")


def hub_page():
    existing = [
        ("refinitiv-worldcheck-pricing", "Refinitiv World-Check (LSEG)", "Enterprise PEP, sanctions and adverse-media screening"),
        ("chainalysis-pricing", "Chainalysis", "Blockchain analytics and wallet risk scoring"),
        ("complyadvantage-pricing", "ComplyAdvantage", "AML screening and ongoing monitoring"),
    ]
    rows = "".join(
        f'<tr><td><a href="/cost-of/{s}">{esc(n)}</a></td><td>{esc(d)}</td><td>Not published</td></tr>'
        for s, n, d in existing)
    rows += "".join(
        f'<tr><td><a href="/cost-of/{v["slug"]}">{esc(v["name"])}</a></td>'
        f'<td>{esc(v["what"][:70].rsplit(" ", 1)[0])}…</td><td>Not published</td></tr>'
        for v in VENDORS)
    body = f"""
<div class="callout">
<p>Every vendor below quotes privately. That is not evasiveness — the contracts really are scoped per
customer — but it does mean you cannot compare them without knowing what moves each quote. That is
what these pages are for.</p>
</div>

<h2>Sanctions and compliance vendor pricing</h2>
<table>
<thead><tr><th>Vendor</th><th>What it is</th><th>List price</th></tr></thead>
<tbody>{rows}
<tr><td><a href="/pricing">SanctionsAI</a></td><td>OFAC screening API for agents</td><td><strong>Published</strong> — free tier, $19/mo, $99/mo</td></tr>
</tbody>
</table>

<h2>Start with the category, not the vendor</h2>
<p>If you have not decided what you are buying yet,
<a href="/cost-of/ofac-screening-api-pricing">what an OFAC screening API costs in 2026</a> covers the four
pricing models and what each one is actually charging for. Most teams discover they are scoping an
enterprise platform for a problem a list check solves.</p>

<h2>Related</h2>
<div class="related-links">
<ul>
<li><a href="/vs">SanctionsAI compared with each vendor, feature by feature</a></li>
<li><a href="/best/best-ofac-screening-apis">Best OFAC screening APIs in 2026</a></li>
<li><a href="/alternatives-to/chainalysis">Alternatives to Chainalysis</a></li>
<li><a href="/cost">What OFAC violations cost — penalties and enforcement</a></li>
<li><a href="/pricing">SanctionsAI pricing</a></li>
</ul>
</div>
"""
    faqs = [
        ("Why does no sanctions screening vendor publish pricing?",
         "Because the contracts are scoped per customer across data modules, seats, volume and redistribution rights. A single list price would be wrong for almost everyone, so vendors quote instead. SanctionsAI publishes prices because it sells one thing — OFAC list screening — and the scope does not vary."),
        ("Which sanctions screening vendor is cheapest?",
         "For OFAC list screening specifically, a free tier or self-hosted library is the floor, and SanctionsAI offers both. Among the enterprise platforms, none publish prices, so any ranking by cost would be a guess."),
        ("Do I need an enterprise compliance platform?",
         "It depends on your obligation. Direct SDN list matching before a payment is a narrow requirement. PEP screening, adverse media and ownership research are wider ones, and that is what the enterprise price buys."),
    ]
    lede = ("None of these vendors publish list prices. These breakdowns set out what drives each quote, "
            "what to ask before signing, and what the same screen costs without a platform contract.")
    return page("", "Sanctions Screening Vendor Pricing — What Each One Actually Costs",
                "What sanctions and AML screening vendors cost in 2026. Pricing is quote-gated at every major "
                "vendor — here is what drives each quote and what OFAC screening costs without a contract.",
                "What sanctions screening vendors actually cost", lede, body, faqs, "")


def write(rel, content):
    path = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def main():
    written = [write("index.html", hub_page())]
    for v in VENDORS:
        h = vendor_page(v)
        written.append(write(f"{v['slug']}/index.html", h))
        written.append(write(f"{v['slug']}.html", h))
    c = category_page()
    written.append(write(f"{CATEGORY['slug']}/index.html", c))
    written.append(write(f"{CATEGORY['slug']}.html", c))
    for p in written:
        print("wrote", os.path.relpath(p, ROOT))


if __name__ == "__main__":
    main()
