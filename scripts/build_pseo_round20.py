#!/usr/bin/env python3
"""
Round 20 pSEO page generator for sanctionsai.dev.

Produces three classes of programmatic SEO page, each as a static
index.html served by the prefix-loop / glossary fall-through wired into
api.py (see api.py:2837 and the /glossary/ handler).

  1. /redflags/<slug>         — 6 new red-flags pages (problem-first conversion)
  2. /alternatives-to/<slug>  — competitor alternatives (bottom-funnel)
  3. /glossary/<slug>         — AEO citation pages (scaled term set)

Style matches the existing /redflags/ and /alternatives-to/ templates
verbatim so pages are visually consistent and pass the JSON-LD gate
(scripts/validate_jsonld.py runs in the Dockerfile build).

Run from the repo root:
    python3 scripts/build_pseo_round20.py
"""
from __future__ import annotations
import json
import os
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SITE = "https://sanctionsai.dev"
DATE = "2026-07-26"

# ---------------------------------------------------------------------------
# Shared HTML shell — matches the existing pSEO template style (proven,
# JSON-LD-gate-clean). Inline CSS is identical across generated pages so the
# site reads as one design system regardless of who authored the page.
# ---------------------------------------------------------------------------
CSS = textwrap.dedent("""\
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;line-height:1.65;color:#0a0a0a;max-width:760px;margin:0 auto;padding:2rem 1.25rem}
h1{font-size:2.1rem;line-height:1.2;margin:.3em 0}
h2{font-size:1.45rem;margin-top:2rem;border-bottom:2px solid #e5e7eb;padding-bottom:.3rem}
h3{font-size:1.15rem;margin-top:1.5rem}
a{color:#0066cc;text-decoration:none}a:hover{text-decoration:underline}
.lede{font-size:1.1rem;color:#374151;margin-bottom:1.5rem}
table{border-collapse:collapse;width:100%;margin:1rem 0;font-size:.95rem}
th,td{border:1px solid #e5e7eb;padding:.6rem .75rem;text-align:left}
th{background:#f9fafb;font-weight:600}
.callout{background:#f0f7ff;border-left:4px solid #0066cc;padding:1rem 1.25rem;margin:1.5rem 0;border-radius:0 .375rem .375rem .375rem}
.callout.warn{background:#fef3c7;border-left-color:#d97706}
.callout.good{background:#ecfdf5;border-left-color:#059669}
.verdict{background:#0a0a0a;color:#fff;padding:1.25rem 1.5rem;border-radius:.5rem;margin:1.5rem 0}
.verdict h3{margin-top:0;color:#fff}
.cta{background:#0066cc;color:#fff;padding:1.25rem 1.5rem;border-radius:.5rem;text-align:center;margin:2rem 0}
.cta a{color:#fff;font-weight:600;font-size:1.1rem}
.cta p{color:#dbeafe}
.related-links{background:#f9fafb;padding:1rem 1.25rem;border-radius:.5rem;margin-top:2.5rem}
.related-links ul{list-style:none;padding:0;display:grid;grid-template-columns:1fr 1fr;gap:.4rem 1rem}
footer{margin-top:3rem;padding-top:1.5rem;border-top:1px solid #e5e7eb;color:#6b7280;font-size:.9rem}
ul.check{list-style:none;padding-left:0}ul.check li::before{content:"✓  ";color:#059669;font-weight:700}
ul.cross{list-style:none;padding-left:0}ul.cross li::before{content:"✗  ";color:#dc2626;font-weight:700}
""")

POSTHOG = ('<script>!function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],'
'e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),'
't[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}'
'(p=t.createElement("script")).type="text/javascript",p.crossOrigin="anonymous",p.async=!0,'
'p.src=s.api_host.replace(".i.posthog.com","-assets.i.posthog.com")+"/static/array.js",'
'(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;'
'for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],'
'u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),'
't||(e+=" (stub)"),e},'
'u.people.toString=function(){return u.toString(1)+".people (stub)"},'
'o="capture identify alias people.set people.set_once set_config register register_once '
'unregister opt_out_capturing has_opted_out_capturing opt_in_capturing reset '
'isFeatureEnabled onFeatureFlags getFeatureFlag getFeatureFlagPayload reloadFeatureFlags '
'group updateEarlyAccessFeatureFlagEnrollment getEarlyAccessFeatures '
'getActiveMatchingSurveys getSurveys".split(" "),n=0;n<o.length;n++)g(u,o[n]),'
'e._i.push([i,s,a])},e.__SV=!0}(document,window.posthog||[]);'
'posthog.init("phc_lyZCgvTpicjLzAO3rY2GhxuX5WUc5jQjP8ZVwwJqauX",'
'{api_host:"https://eu.i.posthog.com",person_profiles:"identified_only"})</script>')


def _jsonld(*blocks: dict) -> str:
    """Serialize JSON-LD blocks as <script> tags. JSON-safe by construction."""
    return "\n".join(
        f'<script type="application/ld+json">{json.dumps(b, separators=(",", ":"))}</script>'
        for b in blocks
    )


def _page(*, path: str, title: str, description: str, body: str,
          faq: list[tuple[str, str]] | None = None,
          extra_jsonld: list[dict] | None = None,
          breadcrumb_name: str | None = None) -> str:
    """Assemble a full HTML document in the proven template style."""
    url = f"{SITE}{path}"
    crumb = breadcrumb_name or title
    blocks = [
        {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": title,
            "description": description,
            "author": {"@type": "Organization", "name": "SanctionsAI", "url": SITE},
            "publisher": {"@type": "Organization", "name": "SanctionsAI", "url": SITE},
            "mainEntityOfPage": {"@type": "WebPage", "@id": url},
            "datePublished": DATE,
            "dateModified": DATE,
        },
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE}/"},
                {"@type": "ListItem", "position": 2, "name": crumb, "item": url},
            ],
        },
    ]
    if faq:
        blocks.append({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": q,
                 "acceptedAnswer": {"@type": "Answer", "text": a}}
                for q, a in faq
            ],
        })
    if extra_jsonld:
        blocks.extend(extra_jsonld)
    return textwrap.dedent(f"""\
    <!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <meta name="description" content="{description}">
    <link rel="canonical" href="{url}">
    <meta property="og:title" content="{title}">
    <meta property="og:description" content="{description}">
    <meta property="og:type" content="article">
    <meta property="og:url" content="{url}">
    <meta property="og:image" content="{SITE}/og.png">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="robots" content="index, follow, max-image-preview:large">
    {_jsonld(*blocks)}
    <style>
    {CSS}</style>
    <!-- isenberg-round20 -->
    {POSTHOG}
    </head>
    <body>
    <article>
    {body}
    </article>
    <footer>
    <p><strong>SanctionsAI</strong> &mdash; OFAC sanctions screening for AI agents. MIT licensed. Data from the <a href="https://sanctionslist.ofac.treas.gov/" rel="noopener">US Treasury</a> and <a href="https://github.com/vile/ofac-sdn-list" rel="noopener">vile/ofac-sdn-list</a>.</p>
    </footer>
    </body>
    </html>
    """)


def _related(items: list[tuple[str, str]]) -> str:
    """Render a 2-column related-links box."""
    lis = "".join(f'<li><a href="{u}">{t}</a></li>' for u, t in items)
    return (
        '<div class="related-links"><h3>Related</h3>'
        f'<ul>{lis}</ul></div>'
    )


def _cta(title: str, sub: str) -> str:
    return (
        f'<div class="cta"><h2>{title}</h2>'
        f'<p>{sub}</p>'
        '<a href="/tools/wallet-checker">Screen a wallet free &rarr;</a>'
        '&nbsp;&nbsp;<a href="/pricing">See pricing</a></div>'
    )


# ---------------------------------------------------------------------------
# 1. RED-FLAGS PAGES
# ---------------------------------------------------------------------------
# Each entry: slug, h1, title, desc, lede, rows[flag, why, level], faq
RED_FLAGS = [
    {
        "slug": "agent-paying-sanctioned-wallet",
        "h1": "The #1 OFAC Red Flag for AI Agents: Paying a Sanctioned Wallet",
        "title": "AI Agent Paid a Sanctioned Wallet? OFAC Red Flags & Liability",
        "desc": "The single highest-risk pattern for autonomous payment agents: executing a transfer to an OFAC-sanctioned wallet. What triggers it, the liability, and how to block it.",
        "lede": "An AI agent that executes a payment to an OFAC-sanctioned address has, in most readings, already committed a strict-liability violation. This is the red flag that ends companies. Here is what it looks like and how to make it impossible.",
        "rows": [
            ("Direct transfer to a sanctioned address", "The agent sends USDC, ETH, or BTC to a wallet on the SDN list. Under OFAC strict liability the transfer itself is the violation &mdash; intent is not required.", "Critical"),
            ("Agent pays a wallet you previously approved", "A counterparty's wallet is added to the SDN list after you whitelisted it. Without a real-time screen on every payment, the agent keeps paying a now-sanctioned address.", "Critical"),
            ("Paying an address derived from a sanctioned one", "OFAC's 50 Percent Rule can extend to wallets controlled by a sanctioned person even when not individually listed. A clean-looking address can still be a violation.", "High"),
        ],
        "faq": [
            ("Is paying a sanctioned wallet a crime even if I didn't know?",
             "Under OFAC strict liability, yes. Civil penalties reach $377,700 per violation or twice the transaction value, and knowledge is not an element of the offense. This is exactly why pre-transaction screening exists."),
            ("How fast does an agent need to screen?",
             "Inline, before the transaction is signed. SanctionsAI returns a result in under 100ms so the check fits on the payment path without degrading the agent's latency budget."),
        ],
    },
    {
        "slug": "stablecoin-payment-to-sanctioned-entity",
        "h1": "Stablecoin Payments to Sanctioned Entities: The Compliance Red Flag",
        "title": "Stablecoin Payment to Sanctioned Entity? OFAC Red Flags (2026)",
        "desc": "USDC, USDT and other stablecoin transfers to sanctioned entities are an OFAC red flag. Why stablecoin issuers freeze funds and how to screen before sending.",
        "lede": "Stablecoins are not a sanctions loophole. Circle and Tether have frozen hundreds of millions in USDC and USDT at law-enforcement request. A stablecoin payment to a sanctioned entity is both an OFAC violation and a frozen-asset event.",
        "rows": [
            ("Stablecoin transfer to a listed SDN", "Major issuers operate blocklists. A payment to a sanctioned address can be frozen at the issuer level within hours, locking your funds and creating an audit trail.", "Critical"),
            ("Stablecoin rail used to bypass a blocked fiat path", "Using USDC to complete a payment you could not make in fiat because of sanctions is itself a sanctions evasion pattern. OFAC treats the underlying transaction, not the rail.", "Critical"),
            ("Stablecoin payment to a mixer-adjacent address", "Addresses one hop from Tornado Cash and similar mixers are flagged by issuers. Stablecoins sent there are frequently frozen pending review.", "High"),
        ],
        "faq": [
            ("Can stablecoin issuers really freeze my funds?",
             "Yes. USDC and USDT are issued under centrally-controlled smart contracts with a blocklist function. Issuers have frozen addresses at OFAC and law-enforcement request, including addresses added after the funds were sent."),
            ("Does screening the wallet before sending protect me?",
             "Pre-transaction screening is the single most effective control. If the screen returns clean against the current SDN list at execution time, you have a defensible audit trail even if the address is later designated."),
        ],
    },
    {
        "slug": "cross-chain-sanctions-evasion",
        "h1": "Cross-Chain Sanctions Evasion: The Red Flag AI Agents Miss",
        "title": "Cross-Chain Sanctions Evasion Red Flag for Crypto Agents (2026)",
        "desc": "Funds hopping ETH to TRON to BSC to dodge sanctions screening. Why single-chain checks fail and how a multi-chain SDN screen catches it.",
        "lede": "An address can be clean on Ethereum and sanctioned on Tron. Agents that screen only the source chain miss the most common modern evasion pattern: chain-hopping. Here is why it triggers OFAC scrutiny and how to close the gap.",
        "rows": [
            ("Rapid ETH &rarr; BSC &rarr; TRON movement", "Funds that cross three chains in minutes match known evasion playbooks. Banking partners and analytics vendors flag the pattern automatically, even when no individual address is listed.", "High"),
            ("Agent screens source chain only", "If your agent checks the Ethereum address but pays to a bridge that exits on Tron, you have screened the wrong identifier. The destination-chain address is what carries liability.", "Critical"),
            ("Bridging to a chain with thinner screening coverage", "Some chains have fewer sanctioned addresses listed simply because Treasury has published fewer designations there. That is a coverage gap, not safety.", "Medium"),
        ],
        "faq": [
            ("Does SanctionsAI screen across multiple chains?",
             "Yes. The wallet screen covers Ethereum, Bitcoin, Solana, and Tron addresses against the full OFAC SDN digital-assets list, refreshed daily from the US Treasury feed."),
            ("Is chain-hopping itself illegal?",
             "Not inherently, but it is a recognized evasion indicator. When chain-hopping is used to avoid a sanctioned address, the underlying transaction is the violation. Screening the actual destination address on the actual chain is the control."),
        ],
    },
    {
        "slug": "high-risk-jurisdiction-payments",
        "h1": "Payments to High-Risk Jurisdictions: The OFAC Red Flag List",
        "title": "High-Risk Jurisdiction Payments: OFAC Red Flags by Country (2026)",
        "desc": "Payments routed to or through Iran, North Korea, Cuba, Syria, Russia and Crimea are presumptively sanctions violations. The jurisdiction red flag matrix for payment agents.",
        "lede": "Geography still matters in crypto. A payment routed through a comprehensively sanctioned jurisdiction is presumptively a violation regardless of the currency. This is the red flag matrix every payment agent should hard-code.",
        "rows": [
            ("Comprehensive sanctions jurisdictions", "Iran, North Korea, Cuba, Syria, and Crimea/DNR/LNR are subject to comprehensive embargoes. Nearly any transaction involving these jurisdictions is prohibited.", "Critical"),
            ("Russia sectoral and SDN exposure", "Russia is not under a comprehensive embargo, but EO 14024 and dozens of sectoral programs designate banks, oligarchs, and tech firms. Counterparty screening against the Russia program is mandatory.", "High"),
            ("Transshipment through a third country", "Routing a payment through a clean jurisdiction to obscure a sanctioned end-party is itself an evasion pattern and a red flag for both OFAC and your banking partner.", "High"),
        ],
        "faq": [
            ("If I pay in USDC, does the destination country still matter?",
             "Yes. OFAC jurisdiction attaches to the underlying transaction and to US persons and companies, not to the payment rail. A stablecoin payment to a comprehensively sanctioned jurisdiction is treated the same as a wire."),
            ("How do I check a country against OFAC programs?",
             "SanctionsAI exposes a country screen that returns the active programs, designation count, and embargo status for every jurisdiction in under 100ms. See /tools/country-checker."),
        ],
    },
    {
        "slug": "pep-and-adverse-media-screening-red-flags",
        "h1": "PEP & Adverse-Media Red Flags in Autonomous Onboarding",
        "title": "PEP and Adverse-Media Red Flags for AI Onboarding Agents (2026)",
        "desc": "Politically Exposed Persons and adverse-media matches are AML red flags that autonomous onboarding agents skip at their peril. What to screen and when.",
        "lede": "OFAC screening alone is not a compliance program. Politically Exposed Persons (PEP) matches and credible adverse media are standard AML red flags that autonomous onboarding agents routinely skip. Here is the minimum set every onboarding path should check.",
        "rows": [
            ("Counterparty is a PEP", "Domestic or foreign PEPs require enhanced due diligence under FATF-aligned AML rules. Onboarding a PEP without an EDD step is a flagged gap in every regulator's examination manual.", "High"),
            ("Credible adverse media in the last 24 months", "News of sanctions investigations, fraud convictions, or terror financing is an AML red flag even when no list match exists. It is the most common reason a KYC vendor downgrades a risk score.", "High"),
            ("Ownership structure obscures a listed person", "OFAC's 50 Percent Rule means a company owned 50%+ by a sanctioned person is blocked even if unlisted. Onboarding without tracing ownership to natural persons misses this.", "Critical"),
        ],
        "faq": [
            ("Is PEP screening legally required in the US?",
             "For banks and money services businesses under FinCEN AML rules, yes in practice through enhanced due diligence expectations. For non-bank crypto agents it is the standard of care regulators are converging on."),
            ("Does SanctionsAI do PEP screening?",
             "SanctionsAI focuses on OFAC SDN, consolidated list, and digital-asset screening. PEP and adverse-media are complementary layers; we surface the sanctions determination and recommend pairing with a KYC vendor for PEP."),
        ],
    },
    {
        "slug": "agent-bypassing-screening-control",
        "h1": "When Your Own Agent Bypasses the Screening Control",
        "title": "AI Agent Bypassing Sanctions Screening: The Internal Red Flag",
        "desc": "The most expensive OFAC red flag is the one inside your own system: an agent that silently skips or overrides the sanctions screen. How it happens and how to stop it.",
        "lede": "The scariest OFAC red flag is not a sanctioned counterparty &mdash; it is your own agent quietly routing around the screen. Misconfigured retries, fallback paths, and caching are how compliance controls get switched off in production. Here is the failure catalogue.",
        "rows": [
            ("Screen fails &rarr; agent pays anyway", "When the sanctions API times out, a poorly-coded agent falls through to 'allow' instead of 'deny'. This is the single most common way agents create violations in the wild.", "Critical"),
            ("Cached 'clean' result reused after SDN update", "The SDN list changes daily. An agent that caches a clean result for a wallet and reuses it for a week is screening against a stale list &mdash; missing new designations.", "Critical"),
            ("Screen bypassed on retry / fallback path", "The happy path screens; the retry path, the webhook path, or the dispute path do not. Sanctions evaders probe for exactly these unscreened paths.", "High"),
        ],
        "faq": [
            ("What is fail-closed vs fail-open in sanctions screening?",
             "Fail-closed means if the screen cannot return a definitive 'clean', the payment is blocked. Fail-open means the payment proceeds on uncertainty. OFAC examiners expect fail-closed; fail-open is treated as having no control."),
            ("How does SanctionsAI support fail-closed?",
             "The API returns a definitive clean/boolean in under 100ms with the SDN list version. There is no ambiguity to fall through on. The /playbook documents the fail-closed wiring pattern for each integration mode."),
        ],
    },
]


def build_redflags() -> list[str]:
    urls = []
    for r in RED_FLAGS:
        rows = "".join(
            f'<tr><td><strong>{flag}</strong></td><td>{why}</td>'
            f'<td>{level}</td></tr>'
            for flag, why, level in r["rows"]
        )
        body = textwrap.dedent(f"""\
        <header>
        <p class="lede">OFAC red flags</p>
        <h1>{r["h1"]}</h1>
        <p class="lede">{r["lede"]}</p>
        </header>
        <table>
        <thead><tr><th>Red flag</th><th>Why it triggers OFAC scrutiny</th><th>Risk level</th></tr></thead>
        <tbody>
        {rows}
        </tbody>
        </table>
        <div class="callout warn">
        <strong>The control:</strong> every red flag above is caught by pre-transaction OFAC screening.
        SanctionsAI checks the wallet, name, or jurisdiction against the live SDN list in under 100ms,
        before the payment is signed. There is no pattern so clever that it bypasses an address check.
        </div>
        <h2>What to do if you see one of these</h2>
        <ul class="check">
        <li>Stop the transaction. Do not let the agent retry around the screen.</li>
        <li>Log the event with timestamp, subject, and SDN list version (the audit trail is your defense).</li>
        <li>If a payment already executed, preserve evidence and assess voluntary self-disclosure &mdash; it can reduce a penalty by up to 50%.</li>
        <li>Review the agent's control path: was the screen on the actual execution path, or only on the happy path?</li>
        </ul>
        {_cta("Block every red flag before the payment signs",
              "Pre-transaction OFAC screening in under 100ms. Free tier: 5 checks/day, no signup.")}
        {_related([
            ("/redflags/crypto-payment-ofac-red-flags", "5 crypto payment red flags"),
            ("/redflags/ai-agent-sanctions-compliance-red-flags", "AI agent compliance red flags"),
            ("/how-to/avoid-ofac-violations", "How to avoid OFAC violations"),
            ("/penalties/ofac-violation-costs", "OFAC violation costs"),
            ("/how-to/file-voluntary-disclosure", "File a voluntary self-disclosure"),
            ("/playbook", "The Agent Compliance Playbook"),
        ])}""")
        faq = [(q, a) for q, a in r["faq"]]
        html = _page(
            path=f"/redflags/{r['slug']}",
            title=r["title"],
            description=r["desc"],
            body=body,
            faq=faq,
            breadcrumb_name=r["h1"][:60],
        )
        out = os.path.join(ROOT, "redflags", r["slug"], "index.html")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(html)
        urls.append(f"/redflags/{r['slug']}")
    return urls


# ---------------------------------------------------------------------------
# 2. ALTERNATIVES-TO PAGES
# ---------------------------------------------------------------------------
# Competitors already in _COMPETITOR_KEYS but with no /alternatives-to/ page.
# Each entry: slug, name, positioning, strength, weakness, price_note
ALTERNATIVES = [
    {"slug": "trm-labs", "name": "TRM Labs", "pos": "On-chain intelligence for exchanges and banks",
     "strength": "Deep wallet attribution, investigation graph, trusted by major exchanges",
     "weakness": "Enterprise sales motion, no self-serve, no free tier, not built for agent integrations",
     "price": "Quote only (enterprise)"},
    {"slug": "sumsub", "name": "Sumsub", "pos": "KYC / KYB / AML identity verification suite",
     "strength": "Full identity stack: document checks, liveness, PEP/adverse-media, transaction monitoring",
     "weakness": "Identity-first, not sanctions-list-first; heavier integration; per-verification pricing adds up for high-volume agents",
     "price": "Per-verification, from ~$0.50"},
    {"slug": "elliptic", "name": "Elliptic", "pos": "Crypto risk & compliance for institutions",
     "strength": "Wallet risk scoring, investigation tooling, strong exchange coverage",
     "weakness": "Enterprise contracts, no instant public check, agent integration not a first-class use case",
     "price": "Quote only (enterprise)"},
    {"slug": "complyadvantage", "name": "ComplyAdvantage", "pos": "AI-driven sanctions & PEP screening",
     "strength": "Broad sanctions/PEP/adverse-media coverage, fuzzy matching, mature API",
     "weakness": "Built for compliance teams, not autonomous agents; pricing opaque; crypto-wallet coverage is a bolt-on",
     "price": "Quote only"},
    {"slug": "world-check", "name": "World-Check (LSEG)", "pos": "Legacy PEP & sanctions intelligence",
     "strength": "Deep historical PEP coverage, industry-standard for banks",
     "weakness": "Licensed data with seat-based pricing, no wallet screening, no free tier, slow to integrate",
     "price": "Per-seat license"},
    {"slug": "dow-jones-risk", "name": "Dow Jones Risk & Compliance", "pos": "Sanctions & PEP data feeds",
     "strength": "High-quality curated PEP and sanctions data, strong for traditional finance",
     "weakness": "Data-feed model not an API product, no wallet coverage, enterprise contracts",
     "price": "Quote only"},
    {"slug": "scorechain", "name": "Scorechain", "pos": "Blockchain AML & transaction monitoring",
     "strength": "Multi-chain transaction monitoring, EU-focused, risk scoring",
     "weakness": "Compliance-team product, no instant public check, agent integration not a focus",
     "price": "Quote only"},
    {"slug": "amlbot", "name": "AMLBot", "pos": "Crypto AML screening for wallets",
     "strength": "Wallet-focused, pay-per-check, covers multiple chains",
     "weakness": "Per-check pricing, narrower scope than full SDN screening, limited agent/tooling support",
     "price": "Per-check"},
    {"slug": "identitymind", "name": "IdentityMind (LexisNexis)", "pos": "Digital identity & AML",
     "strength": "Identity verification combined with AML, large data graph",
     "weakness": "Enterprise platform, no self-serve wallet check, agent integration not supported",
     "price": "Quote only"},
    {"slug": "charmverse", "name": "CharmVerse", "pos": "Web3 ops & compliance workflows",
     "strength": "DAO operations tooling, workflow builder",
     "weakness": "Not a sanctions screening product; compliance is a secondary feature",
     "price": "SaaS subscription"},
    {"slug": "ciphertrace", "name": "Ciphertrace (Mastercard)", "pos": "Crypto compliance & investigation",
     "strength": "Exchange and bank compliance, investigation tools",
     "weakness": "Enterprise-only, no instant public check, no agent-first integration",
     "price": "Quote only"},
    {"slug": "blockdaemon", "name": "Blockdaemon", "pos": "Blockchain infrastructure",
     "strength": "Node infrastructure and staking",
     "weakness": "Infrastructure product, not a sanctions screening API; not a comparable compliance tool",
     "price": "Infrastructure pricing"},
]


def build_alternatives() -> list[str]:
    urls = []
    for a in ALTERNATIVES:
        body = textwrap.dedent(f"""\
        <header>
        <p class="lede">Alternatives</p>
        <h1>Best {a["name"]} alternative for AI agents in 2026</h1>
        <p class="lede">An honest look at where SanctionsAI is the stronger pick and where {a["name"]} is the right tool. {a["pos"]}.</p>
        </header>
        <h2>Quick comparison</h2>
        <table>
        <thead><tr><th>Dimension</th><th>{a["name"]}</th><th>SanctionsAI</th></tr></thead>
        <tbody>
        <tr><td>Positioning</td><td>{a["pos"]}</td><td>OFAC sanctions screening API built for AI agents</td></tr>
        <tr><td>Pricing</td><td>{a["price"]}</td><td>Free tier + $19/mo Dev + $99/mo Pro + $0.05/check</td></tr>
        <tr><td>Self-serve</td><td>{'Yes' if a['price'].lower().startswith(('per', 'free')) else 'No &mdash; enterprise sales'}</td><td>Yes &mdash; free checks with no signup</td></tr>
        <tr><td>Built for agents</td><td>No</td><td>Yes (MCP, HTTP, CLI, x402)</td></tr>
        <tr><td>Latency</td><td>Varies</td><td>&lt;100ms, fail-closed</td></tr>
        </tbody>
        </table>
        <h2>Where {a["name"]} wins</h2>
        <ul class="check">
        <li>{a["strength"]}</li>
        <li>Mature compliance workflows for large organizations</li>
        <li>Established with regulated enterprises</li>
        </ul>
        <h2>Where SanctionsAI wins</h2>
        <ul class="check">
        <li>Free, instant checks with no API key &mdash; 5 per day</li>
        <li>Sub-100ms response fits inline on the payment path</li>
        <li>First-class agent integrations: MCP server, x402, LangChain, Claude Code, OpenAI Agents SDK, ElizaOS</li>
        <li>Transparent self-serve pricing from $0 to $99/mo</li>
        <li>MIT-licensed and self-hostable &mdash; no vendor lock-in</li>
        </ul>
        <h2>Where {a["name"]} falls short</h2>
        <ul class="cross">
        <li>{a["weakness"]}</li>
        <li>No free public tier for quick checks</li>
        <li>Not designed for autonomous payment agents</li>
        </ul>
        <div class="verdict">
        <h3>The honest verdict</h3>
        <p>{a["name"]} is built for {("compliance teams at scale" if "enterprise" in a["weakness"].lower() or a["price"].lower().startswith(("quote","per-seat")) else "its core use case")}. SanctionsAI is built for developers shipping autonomous agents that move money and need a sanctions gate on the payment path. If you are wiring compliance into an agent, start here &mdash; free, instant, self-serve.</p>
        </div>
        {_cta("Screen a wallet free, no signup",
              "Free tier: 5 checks/day. Sub-100ms. MCP, HTTP, CLI, x402.")}
        {_related([
            (f"/vs/{a['slug']}", f"SanctionsAI vs {a['name']}"),
            ("/alternatives-to/chainalysis", "vs Chainalysis alternative"),
            ("/alternatives-to/elliptic", "vs Elliptic alternative"),
            ("/compare/sumsub", "vs SumSub"),
            ("/best/best-ofac-screening-apis", "Best OFAC screening APIs"),
            ("/pricing", "Pricing"),
        ])}""")
        faq = [
            (f"Is SanctionsAI a real {a['name']} alternative?",
             f"For OFAC sanctions screening of wallets and names in an autonomous agent, yes &mdash; and it's free to start. For {a['name']}'s full enterprise workflow ({a['pos'].lower()}), {a['name']} remains the stronger choice."),
        ]
        html = _page(
            path=f"/alternatives-to/{a['slug']}",
            title=f"Best {a['name']} alternative for AI agents (2026) | SanctionsAI",
            description=f"An honest {a['name']} alternative for developers building AI agents. {a['pos']}. Pricing, strengths, weaknesses, and when to pick each.",
            body=body,
            faq=faq,
            breadcrumb_name=f"{a['name']} alternative",
        )
        out = os.path.join(ROOT, "alternatives-to", a["slug"], "index.html")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(html)
        urls.append(f"/alternatives-to/{a['slug']}")
    return urls


# ---------------------------------------------------------------------------
# 3. GLOSSARY PAGES (AEO citation moat)
# ---------------------------------------------------------------------------
# VETTED, factual sanctions definitions. No invented regulatory claims.
# Each entry: slug, h1, short, what, legal, who, agents, coverage, faq[]
GLOSSARY = [
    {
        "slug": "sdgt",
        "h1": "SDGT (Specially Designated Global Terrorists)",
        "short": "An OFAC sanctions program targeting terrorists who threaten the US, its citizens, and its economy.",
        "what": "SDGT is the OFAC designation category for Specially Designated Global Terrorists &mdash; individuals and entities determined to have committed, or pose a significant risk of committing, acts of terrorism that threaten US national security, foreign policy, or the economy.",
        "legal": "The SDGT program is implemented under Executive Order 13224, issued in 2001 and expanded since. Designated parties are added to the SDN list under the SDGT program tag. All property of an SDGT that comes under US jurisdiction is blocked, and transactions with them are generally prohibited.",
        "who": "Financial institutions, crypto businesses, payment platforms, and any US person or entity subject to US jurisdiction. Designations include terrorist financiers, front organizations, and associated wallets.",
        "agents": "AI agents moving funds must screen counterparties against the SDGT tag on the SDN list. A wallet or name flagged SDGT is a hard block &mdash; payment to such a party is a strict-liability violation under US law.",
        "coverage": "SanctionsAI screens all SDN list entries including the SDGT program tag. A name or wallet match returns the program code in the response, so agents can route SDGT hits to the most restrictive handling path.",
        "faq": [
            ("What does SDGT stand for?",
             "Specially Designated Global Terrorists &mdash; the OFAC program tag for terrorism-related designations under EO 13224."),
            ("Are SDGT designations on the SDN list?",
             "Yes. SDGT-designated parties appear on the SDN list with the program code SDGT."),
        ],
    },
    {
        "slug": "ofac-eo14024",
        "h1": "EO 14024 (Russia Harmful Foreign Activities)",
        "short": "The 2021 Executive Order authorizing sanctions over Russia's harmful foreign activities, including the invasion of Ukraine.",
        "what": "Executive Order 14024, signed in April 2021, authorizes blocking sanctions on individuals and entities associated with the Government of the Russian Federation and over specified harmful foreign activities. It is the primary modern legal authority for a large share of Russia-related OFAC designations.",
        "legal": "EO 14024 establishes the Russia-related sanctions authority used to designate hundreds of Russian banks, oligarchs, tech firms, and entities. Designated parties are added to the SDN list under the RUS-EO14024 program tag. Secondary sanctions exposure extends to certain non-US persons.",
        "who": "Any counterparty with exposure to Russian entities &mdash; banks, payment platforms, crypto exchanges, and agents routing payments to or through Russia or Russian-designated persons.",
        "agents": "Russia sanctions are the most active program by designation volume. Agents handling cross-border or crypto payments should treat any Russia-connected counterparty as elevated risk and screen against the EO 14024 tag specifically, not just the broad SDN list.",
        "coverage": "SanctionsAI screens against the full SDN list including the EO 14024 program tag. Russia is one of the largest country buckets in the dataset by designation count.",
        "faq": [
            ("Is all of Russia sanctioned?",
             "No. Russia is not under a comprehensive embargo, but EO 14024 designates specific banks, firms, and individuals. Counterparty-level screening is required."),
            ("What does EO 14024 cover?",
             "It authorizes blocking sanctions over Russia's harmful foreign activities, including the actions against Ukraine. It is the basis for most modern Russia SDN designations."),
        ],
    },
    {
        "slug": "general-license",
        "h1": "General License (OFAC)",
        "short": "A standing OFAC authorization that permits a category of transactions that would otherwise be prohibited.",
        "what": "A General License is a public authorization issued by OFAC that permits a defined category of transactions that would otherwise be prohibited by sanctions. It applies to anyone whose transaction fits its terms, without requiring a per-transaction application.",
        "legal": "General Licenses are published in the Federal Register and on OFAC's site. They are distinct from Specific Licenses, which are issued to an individual applicant for a particular transaction. Reliance on a General License requires the transaction to fit squarely within its terms.",
        "who": "Any person seeking to transact with a party or jurisdiction subject to US sanctions where a General License authorizes the activity &mdash; for example, certain personal remittances, humanitarian transactions, or wind-down periods after a new designation.",
        "agents": "Agents should not assume a transaction is permitted simply because a General License exists in the area &mdash; the specific facts must fit the license. A sanctions hit that returns clean may still be blocked absent license coverage; conversely a listed party may be transactable under a license.",
        "coverage": "SanctionsAI returns whether a name or wallet matches the SDN list. It does not interpret General License coverage &mdash; license analysis requires a human or specialist legal review.",
        "faq": [
            ("What is the difference between a General License and a Specific License?",
             "A General License authorizes a category of transactions for anyone meeting its terms. A Specific License is issued to a named applicant for a particular transaction."),
            ("Where are OFAC General Licenses published?",
             "They are published in the Federal Register and indexed on OFAC's website under the relevant sanctions program."),
        ],
    },
    {
        "slug": "specific-license",
        "h1": "Specific License (OFAC)",
        "short": "A written OFAC authorization issued to a particular person for a specific transaction or set of transactions.",
        "what": "A Specific License is a written authorization from OFAC issued to a named applicant, permitting a particular transaction or set of transactions that would otherwise be prohibited. It is granted on a case-by-case basis after an application.",
        "legal": "Specific Licenses are issued under 31 CFR 501.801. Applicants must describe the proposed transaction in detail. The license, if granted, binds only the named parties and the described activity; it cannot be transferred or expanded by analogy.",
        "who": "Individuals or entities that need to transact with a sanctioned party or jurisdiction for a purpose not covered by a General License &mdash; for example, releasing blocked funds, humanitarian transfers, or legal-services payments.",
        "agents": "An autonomous agent cannot obtain or interpret a Specific License &mdash; this is a human, legal, application-driven process. Agents should treat any sanctions hit as a hard block unless and until a human confirms license coverage.",
        "coverage": "Out of scope for SanctionsAI. The API returns sanctions status; license analysis is a human workflow.",
        "faq": [
            ("How long does it take to get a Specific License?",
             "It varies and is not guaranteed; OFAC processes applications on a case-by-case basis. Plan for weeks to months and do not execute the prohibited transaction while an application is pending."),
            ("Can a Specific License be shared or reused?",
             "No. It binds only the named applicant and the described transaction."),
        ],
    },
    {
        "slug": "fuzzy-matching",
        "h1": "Fuzzy Matching (Sanctions Screening)",
        "short": "Name-matching that tolerates spelling, transliteration, and formatting differences to catch sanctioned parties.",
        "what": "Fuzzy matching is the use of approximate string-matching algorithms to compare a counterparty name against a sanctions list while tolerating differences in spelling, transliteration, formatting, name order, and missing name components.",
        "legal": "OFAC expects screening to catch matches beyond exact spelling. Names on the SDN list frequently include aliases, transliterations from non-Latin scripts, and 'also known as' entries. Effective screening requires matching across this full surface area.",
        "who": "Anyone screening names (as opposed to wallet hashes). Wallet matching is exact; name matching is inherently approximate and requires a fuzzy layer plus human review of matches.",
        "agents": "Autonomous agents screening names must apply fuzzy matching and route any non-trivial match to a human reviewer before payment. Agents must not auto-pay on 'no exact match' &mdash; that defeats the purpose of name screening.",
        "coverage": "SanctionsAI applies fuzzy matching over the SDN list including aliases and transliterations. The response flags the matched name and confidence so a human can confirm or clear.",
        "faq": [
            ("Why is fuzzy matching needed for sanctions screening?",
             "Because sanctioned parties use aliases, transliterations, and variant spellings. Exact matching alone misses most real-world matches."),
            ("What is a false positive in fuzzy matching?",
             "A match that is mathematically similar but refers to a different person. False positives are why human review of name matches is standard practice."),
        ],
    },
    {
        "slug": "travel-rule",
        "h1": "The Travel Rule (FATF Recommendation 16)",
        "short": "The FATF requirement that originator and beneficiary information travel with virtual-asset transfers.",
        "what": "The Travel Rule, FATF Recommendation 16, requires financial institutions and virtual asset service providers (VASPs) to exchange originator and beneficiary information for transfers above a threshold, so that both sides of a transaction are identifiable.",
        "legal": "For fiat, the threshold is typically any cross-border wire. For virtual assets, FATF set a USD 1,000 threshold below which simplified measures apply. Jurisdictions implement the rule differently (e.g., FinCEN's rule in the US). The rule complements but is distinct from OFAC sanctions screening.",
        "who": "VASPs, crypto exchanges, custodial wallets, and payment platforms handling qualifying transfers. Non-custodial agents moving funds between their own wallets are generally outside Travel Rule scope but still inside OFAC scope.",
        "agents": "Travel Rule is an AML transparency obligation; OFAC sanctions screening is a separate, parallel obligation. An agent must do both: collect and transmit Travel Rule data where applicable, and screen the counterparty against sanctions before payment.",
        "coverage": "SanctionsAI handles the sanctions-screening half. Travel Rule message formatting and counterparty VASP identification is a separate system.",
        "faq": [
            ("Is the Travel Rule the same as sanctions screening?",
             "No. The Travel Rule requires identifying both sides of a transfer; sanctions screening checks them against sanctions lists. They are separate obligations that apply in parallel."),
            ("What is the Travel Rule threshold for crypto?",
             "FATF's simplified-due-diligence threshold for virtual asset transfers is USD 1,000. Above it, full originator and beneficiary information must travel with the transfer."),
        ],
    },
    {
        "slug": "know-your-transaction",
        "h1": "Know Your Transaction (KYT)",
        "short": "The analysis of a transaction's history and counterparties to assess its risk, especially for crypto.",
        "what": "Know Your Transaction (KYT) is the practice of analyzing the source, history, and counterparties of a transaction &mdash; most commonly a crypto transfer &mdash; to assess its risk. KYT traces funds through prior addresses to detect exposure to mixers, sanctioned addresses, or darknet markets.",
        "legal": "KYT is not a single statute but a standard-of-care expectation for VASPs under FATF-aligned AML frameworks. For OFAC, transaction tracing is how compliance teams detect whether funds touched a sanctioned address even when the immediate counterparty is clean.",
        "who": "VASPs, exchanges, and increasingly any platform handling third-party crypto flows. Non-custodial agents benefit from KYT as a risk signal but are not always subject to its AML obligations.",
        "agents": "A wallet can be clean on the SDN list but have received funds from a sanctioned address. KYT surfaces that indirect exposure. Agents should combine a sanctions screen (is this address listed?) with a KYT check (has this address touched listed addresses?) for higher-value transfers.",
        "coverage": "SanctionsAI performs the sanctions screen &mdash; whether the address itself is on the SDN list. Full graph-based KYT (tracing historical exposure) is a complementary layer.",
        "faq": [
            ("Is KYT required by law?",
             "For VASPs under FATF-aligned AML rules, transaction monitoring is effectively required. The specific obligation varies by jurisdiction."),
            ("What is the difference between KYT and sanctions screening?",
             "Sanctions screening checks whether a counterparty is on a list now. KYT traces whether a counterparty has historical exposure to sanctioned or high-risk addresses."),
        ],
    },
    {
        "slug": "know-your-customer",
        "h1": "Know Your Customer (KYC)",
        "short": "The process of verifying a customer's identity as part of onboarding and ongoing AML obligations.",
        "what": "Know Your Customer (KYC) is the set of procedures used to verify a customer's identity, understand the nature of their activity, and assess their risk. KYC is the foundation of anti-money-laundering (AML) compliance.",
        "legal": "KYC is mandated by FATF-aligned AML regimes worldwide (in the US, the Bank Secrecy Act and FinCEN rules). It includes Customer Identification Program (CIP), Customer Due Diligence (CDD), and Enhanced Due Diligence (EDD) for higher-risk customers.",
        "who": "Banks, money services businesses, VASPs, and other regulated financial institutions. The obligation attaches to the regulated entity, not to unregulated individuals building agents for personal use.",
        "agents": "KYC and sanctions screening are distinct. An agent that screens a counterparty against OFAC is performing a sanctions check; verifying the counterparty's identity is KYC. Production payment agents typically need both, often combining an identity vendor with a sanctions API.",
        "coverage": "SanctionsAI performs sanctions screening. KYC verification of identity is a separate process, typically handled by a dedicated KYC vendor.",
        "faq": [
            ("Is KYC the same as sanctions screening?",
             "No. KYC verifies who the customer is; sanctions screening checks whether they are on a sanctions list. They are complementary."),
            ("Do crypto agents need to do KYC?",
             "If the agent's operator is a regulated entity, yes. For non-regulated builders, KYC may not be legally required but sanctions screening still is, under OFAC's strict-liability regime."),
        ],
    },
    {
        "slug": "consolidated-sanctions-list",
        "h1": "Consolidated Sanctions List",
        "short": "A combined OFAC list that aggregates multiple sanctions lists into a single dataset for screening.",
        "what": "The Consolidated Sanctions List (CSL) is OFAC's combined dataset that aggregates non-SDN sanctions lists &mdash; such as the Non-SDN Menu-Based Sanctions List (NS-MBS), the Foreign Sanctions Evaders List (FSE), and others &mdash; into a single machine-readable file.",
        "legal": "Parties on the CSL are subject to varying restrictions depending on the underlying list. CSL entries are not always full blocking sanctions, but transactions with listed parties frequently require review or are subject to specific prohibitions.",
        "who": "Any screener that wants a single dataset covering the broader OFAC restrictions beyond the SDN list. Most production sanctions engines screen both the SDN list and the CSL.",
        "agents": "Screening the SDN list alone misses CSL-only entries. Production-grade agent screening should cover both, and treat any CSL hit as a review-required event rather than an automatic clear.",
        "coverage": "SanctionsAI covers the SDN list including digital-asset addresses. CSL coverage and the distinction between blocking and non-blocking entries should be confirmed for your specific risk model.",
        "faq": [
            ("Is the Consolidated Sanctions List the same as the SDN list?",
             "No. The CSL aggregates non-SDN lists. Screening the SDN list alone misses CSL-only entries."),
            ("Where can I download the Consolidated Sanctions List?",
             "OFAC publishes the CSL as machine-readable files on its site; SanctionsAI exposes the SDN list as JSON and CSV at /data/ofac-sdn-list/."),
        ],
    },
    {
        "slug": "agentic-payment",
        "h1": "Agentic Payment",
        "short": "A payment executed by an autonomous AI agent on behalf of a person or business, without per-transaction human approval.",
        "what": "An agentic payment is a value transfer executed by an autonomous software agent &mdash; typically an LLM-based agent &mdash; that selects the counterparty, amount, and timing without a human approving each transaction. Examples include agents paying for API calls, settling invoices, tipping creators, or moving treasury funds.",
        "legal": "Under OFAC's strict-liability regime, the fact that an agent (rather than a human) executed a prohibited payment does not transfer liability away from the operator. The person or entity that deployed the agent remains responsible for every transaction it executes.",
        "who": "Developers and companies deploying autonomous payment agents &mdash; AI coding agents, treasury agents, commerce agents, and any system using x402, Coinbase AgentKit, LangChain, or similar frameworks to move money.",
        "agents": "Every agentic payment path needs a sanctions gate inline before execution. Without it, the operator inherits strict-liability exposure for every transaction the agent makes. Pre-transaction screening at &lt;100ms is the control that makes agentic payments defensible.",
        "coverage": "SanctionsAI is built specifically for agentic payments: a single API call, sub-100ms, fail-closed, with first-class integrations for the major agent frameworks.",
        "faq": [
            ("Who is liable if an AI agent pays a sanctioned wallet?",
             "The person or entity that deployed the agent. OFAC liability does not transfer to the software."),
            ("How do you screen agentic payments?",
             "Inline, before the transaction is signed, with a sub-100ms sanctions check on the destination wallet or name."),
        ],
    },
    {
        "slug": "false-positive",
        "h1": "False Positive (Sanctions Screening)",
        "short": "A screening match that is mathematically similar but refers to a different person or entity than the counterparty.",
        "what": "A false positive in sanctions screening is a match returned by the screening engine that, on review, does not refer to the same party as the counterparty &mdash; typically because of a common name or similar alias. It is a candidate match, not a confirmed sanctions hit.",
        "legal": "False positives are an expected and accepted part of name-based screening, which is why human review is standard. OFAC expects screening to cast a wide net and for the institution to have a documented process for clearing false positives.",
        "who": "Any institution screening names. Wallet-based screening has near-zero false positives (addresses are exact); name-based screening has materially higher false-positive rates.",
        "agents": "Autonomous agents must not auto-clear or auto-pay around a screening match. Any match &mdash; even a likely false positive &mdash; must route to a human reviewer. Agents that auto-clear matches are effectively running without a screen.",
        "coverage": "SanctionsAI returns matches with confidence and matched-name context so a human reviewer can quickly confirm or clear. Wallet matches are near-exact; name matches carry the false-positive review burden.",
        "faq": [
            ("What is a false positive in sanctions screening?",
             "A match that looks similar but refers to a different party. It must be reviewed and cleared by a human."),
            ("Do wallet matches have false positives?",
             "Almost none. Wallet hashes are exact identifiers; the false-positive problem is concentrated in name screening."),
        ],
    },
    {
        "slug": "secondary-sanctions",
        "h1": "Secondary Sanctions",
        "short": "Sanctions exposure that extends to non-US persons for specified conduct with designated parties, even without US jurisdiction.",
        "what": "Secondary sanctions are measures that can be imposed on non-US persons &mdash; individuals or entities not otherwise subject to US jurisdiction &mdash; for engaging in specified conduct with designated parties. They extend US sanctions pressure beyond US persons.",
        "legal": "Secondary sanctions are program-specific and not automatic. Notable authorities include Iran (IFCA), Russia (CAATSA), and North Korea. A non-US person designated under secondary sanctions can be cut off from the US financial system and from USD transactions.",
        "who": "Non-US crypto exchanges, VASPs, and any non-US business whose counterparties include designated persons under a program with secondary-sanctions authority.",
        "agents": "Agents operated by non-US entities are not immune. If the counterparty is designated under a program with secondary-sanctions authority (Iran, Russia, North Korea), the non-US operator can be exposed even without US nexus.",
        "coverage": "SanctionsAI flags program tags on matches, including Iran, Russia-EO14024, and North Korea designations &mdash; the programs most associated with secondary-sanctions exposure.",
        "faq": [
            ("Do secondary sanctions apply to non-US companies?",
             "Yes, for specified conduct with designated parties under programs that carry secondary-sanctions authority (notably Iran, Russia, North Korea)."),
            ("Are secondary sanctions automatic?",
             "No. They are discretionary and program-specific, but the exposure is real and should be screened for."),
        ],
    },
    {
        "slug": "civil-penalty",
        "h1": "Civil Penalty (OFAC)",
        "short": "The monetary fine OFAC can impose for sanctions violations, calculated under its Enforcement Guidelines.",
        "what": "A civil penalty is the monetary fine OFAC imposes for sanctions violations. OFAC's Enforcement Guidelines set out a framework for calculating the penalty, starting from a statutory base amount per violation and adjusting up or down based on aggravating and mitigating factors.",
        "legal": "The base civil penalty for most sanctions violations can reach the statutory maximum per violation. OFAC publishes a framework for enforcement decisions that considers whether the violation was voluntary self-disclosed, the quality of the compliance program, and other factors.",
        "who": "Any US person or entity, or non-US person where jurisdiction applies, found to have violated sanctions. Penalties apply per violation, so a pattern of un-screened transactions can compound rapidly.",
        "agents": "Each unscreened payment to a sanctioned party is a separate violation with its own penalty exposure. An agent that processes thousands of payments without screening can create thousands of violations &mdash; the multiplication is why pre-transaction screening is non-negotiable.",
        "coverage": "SanctionsAI is the control that prevents the violation in the first place. Once a violation occurs, the penalty framework and any voluntary disclosure decision are legal workflows outside the screening API.",
        "faq": [
            ("How much is an OFAC civil penalty?",
             "Penalties can reach the statutory maximum per violation (up to hundreds of thousands of dollars) or twice the transaction value, and they apply per violation. Multiple unscreened transactions compound."),
            ("Can a civil penalty be reduced?",
             "Yes. OFAC's Enforcement Guidelines consider voluntary self-disclosure and the quality of the compliance program as mitigating factors."),
        ],
    },
    {
        "slug": "facilitation",
        "h1": "Facilitation (Sanctions)",
        "short": "Assisting a sanctioned party in a prohibited transaction, which can itself be a sanctions violation even without direct dealing.",
        "what": "Facilitation occurs when a person assists, supports, or enables a transaction by a sanctioned party that the sanctioned party could not perform themselves. Under OFAC's broad interpretation, the facilitator can be exposed to the same liability as if they had dealt with the sanctioned party directly.",
        "legal": "Facilitation is not a separate statute but an interpretive principle: providing services that enable a sanctioned party to access the US financial system or otherwise do what sanctions prohibit can constitute a violation by the facilitator.",
        "who": "Banks, agents, platforms, and intermediaries &mdash; especially those whose service is moving or holding funds. The risk is highest when the intermediary knows (or should know) that a counterparty is sanctioned.",
        "agents": "An agent that routes funds, holds value, or executes transactions on behalf of a sanctioned counterparty is in facilitation territory. The agent must screen not only the immediate counterparty but understand on whose behalf it is acting.",
        "coverage": "SanctionsAI screens the immediate counterparty. Facilitation analysis &mdash; understanding the ultimate beneficiary &mdash; requires the agent's operator to know their customer, not just the immediate address.",
        "faq": [
            ("Can I be liable for helping a sanctioned person do something they are barred from?",
             "Yes, under OFAC's facilitation principle. Assisting a sanctioned party in a prohibited transaction can expose the facilitator to liability."),
            ("Does facilitation require intent?",
             "Knowledge is an aggravating factor, but the analysis is fact-specific. The safest posture is to screen counterparties and decline to act where a sanctions match is present."),
        ],
    },
    {
        "slug": "blocked-person",
        "h1": "Blocked Person",
        "short": "An individual or entity whose property is frozen under US sanctions and with whom transactions are generally prohibited.",
        "what": "A blocked person is an individual or entity whose property and interests in property are blocked (frozen) under US sanctions. Most SDN designations result in blocking. Property of a blocked person that comes within US jurisdiction must be frozen and reported to OFAC.",
        "legal": "Blocking means the property may not be transferred, paid, withdrawn, or otherwise dealt in. Transactions with blocked persons are generally prohibited, and there are strict reporting requirements for blocked property under 31 CFR 501.",
        "who": "Any US person or entity that holds, receives, or controls property of a blocked person, or that transacts with a blocked person.",
        "agents": "A payment agent that detects a blocked-person match must halt the transaction, freeze any incoming funds, and report. The agent must not auto-refund or auto-return blocked property &mdash; that itself can be a violation.",
        "coverage": "SanctionsAI returns whether a wallet or name matches a blocked (SDN-listed) party. The blocking, holding, and reporting workflow is the operator's responsibility.",
        "faq": [
            ("What does it mean for a person to be blocked?",
             "Their property under US jurisdiction must be frozen, and transactions with them are generally prohibited."),
            ("What do I do with blocked property?",
             "Hold it, do not transfer or return it, and follow OFAC's reporting requirements under 31 CFR 501."),
        ],
    },
    {
        "slug": "embargoed-jurisdiction",
        "h1": "Embargoed Jurisdiction",
        "short": "A country subject to comprehensive US sanctions, under which most transactions are prohibited.",
        "what": "An embargoed jurisdiction is a country subject to comprehensive US sanctions. Comprehensively sanctioned jurisdictions currently include Cuba, Iran, North Korea, and Syria, as well as the Crimea/DNR/LNR regions of Ukraine. Most transactions involving these jurisdictions are prohibited.",
        "legal": "Comprehensive sanctions are country-wide embargoes distinct from the targeted, list-based SDN sanctions. Where a comprehensive embargo applies, the analysis is not 'is this party on the list' but 'is this transaction connected to this jurisdiction at all'.",
        "who": "Any person subject to US jurisdiction, and any non-US person where secondary-sanctions authority applies. The connection to the jurisdiction &mdash; not just a listed party &mdash; is what triggers the prohibition.",
        "agents": "Payment agents must check the destination jurisdiction, not just the counterparty. A clean wallet in a comprehensively sanctioned jurisdiction is still a prohibited transaction. The country screen is mandatory.",
        "coverage": "SanctionsAI exposes a country screen that returns embargo status and active programs for each jurisdiction. Embargoed jurisdictions are flagged as critical-risk.",
        "faq": [
            ("Which countries are comprehensively sanctioned?",
             "Cuba, Iran, North Korea, and Syria, plus the Crimea/DNR/LNR regions of Ukraine."),
            ("If the wallet is not on the SDN list, can I still pay to an embargoed country?",
             "No. Comprehensive sanctions prohibit most transactions with the jurisdiction regardless of whether the specific party is listed."),
        ],
    },
    {
        "slug": "ofac-50-percent-rule",
        "h1": "OFAC 50 Percent Rule",
        "short": "An entity is blocked if one or more sanctioned persons own, directly or indirectly, an aggregate 50% or more of it.",
        "what": "Under OFAC's 50 Percent Rule, an entity is considered blocked even if it does not appear individually on the SDN list, when one or more sanctioned persons own, directly or indirectly, an aggregate of 50% or more of the entity.",
        "legal": "The rule aggregates ownership across multiple sanctioned persons. An entity 30% owned by Sanctioned Person A and 25% owned by Sanctioned Person B is blocked in aggregate, even though no single owner crosses 50%. Indirect ownership through intermediate entities counts.",
        "who": "Anyone transacting with corporate entities that may have sanctioned ownership. The risk is acute for private companies, opaque ownership structures, and entities in jurisdictions with known sanctioned oligarchs.",
        "agents": "A clean name match is not sufficient if the counterparty is an entity with potentially sanctioned ownership. Agents handling higher-value or corporate counterparties should combine the sanctions screen with ownership diligence for 50 Percent Rule exposure.",
        "coverage": "SanctionsAI screens the immediate counterparty against the SDN list. The 50 Percent Rule requires ownership data that is outside the scope of a list screen and should be combined with entity-ownership diligence.",
        "faq": [
            ("Can a company be sanctioned even if it is not on the SDN list?",
             "Yes, under the 50 Percent Rule, if sanctioned persons collectively own 50% or more of it."),
            ("Does the 50 Percent Rule require a single owner above 50%?",
             "No. Ownership is aggregated across all sanctioned owners, direct and indirect."),
        ],
    },
]


def build_glossary() -> list[str]:
    urls = []
    for g in GLOSSARY:
        faq_html = "".join(
            f'<details style="margin:10px 0;padding:14px;border:1px solid #e5e7eb;'
            f'border-radius:10px"><summary style="font-weight:600;cursor:pointer">'
            f'{n}. {q}</summary><p style="margin-top:8px;color:#374151">{a}</p></details>'
            for n, (q, a) in enumerate(g["faq"], 1)
        )
        body = textwrap.dedent(f"""\
        <header style="text-align:center">
        <p class="lede" style="text-transform:uppercase;letter-spacing:.05em;color:#6b7280">Glossary</p>
        <h1>{g["h1"]}</h1>
        <p class="lede">{g["short"]}</p>
        </header>
        <h2>Definition</h2>
        <p>{g["what"]}</p>
        <h2>Regulatory context</h2>
        <p>{g["legal"]}</p>
        <h2>Who it affects</h2>
        <p>{g["who"]}</p>
        <h2>Relevance to AI agents</h2>
        <p>{g["agents"]}</p>
        <h2>SanctionsAI coverage</h2>
        <p>{g["coverage"]}</p>
        <h2>FAQ</h2>
        {faq_html}
        <div class="callout">
        <strong>Compliance disclaimer.</strong> This page is educational and not legal advice.
        Sanctions determinations and license questions require review by a qualified professional.
        Screening data is sourced from the <a href="https://sanctionslist.ofac.treas.gov/" rel="noopener">US Treasury</a>.
        </div>
        {_cta("Screen a counterparty free",
              "OFAC sanctions screening in under 100ms. Free tier: 5 checks/day.")}
        {_related([
            ("/glossary/ofac-sdn-list", "OFAC SDN list"),
            ("/glossary/strict-liability", "Strict liability"),
            ("/glossary/blocked-person", "Blocked person"),
            ("/glossary/consolidated-sanctions-list", "Consolidated Sanctions List"),
            ("/glossary/ofac-50-percent-rule", "OFAC 50 Percent Rule"),
            ("/learn/what-is-ofac", "What is OFAC?"),
        ])}""")
        # DefinedTerm JSON-LD for stronger AEO citation eligibility
        defined_term = {
            "@context": "https://schema.org",
            "@type": "DefinedTerm",
            "name": g["h1"],
            "description": g["short"],
            "inDefinedTermSet": {
                "@type": "DefinedTermSet",
                "name": "Sanctions Glossary",
                "url": f"{SITE}/glossary",
            },
            "url": f"{SITE}/glossary/{g['slug']}",
        }
        html = _page(
            path=f"/glossary/{g['slug']}",
            title=f"{g['h1']} | Sanctions Glossary | SanctionsAI",
            description=g["short"],
            body=body,
            breadcrumb_name=g["h1"],
            extra_jsonld=[defined_term],
        )
        out = os.path.join(ROOT, "glossary", g["slug"], "index.html")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(html)
        urls.append(f"/glossary/{g['slug']}")
    return urls


# ---------------------------------------------------------------------------
# 4. SECTION INDEX PAGES
# ---------------------------------------------------------------------------
def build_redflags_index(child_urls: list[str]) -> str:
    items = "".join(
        f'<li><a href="{u}">{label}</a></li>'
        for u, label in [
            ("/redflags/crypto-payment-ofac-red-flags", "5 crypto payment red flags that trigger OFAC scrutiny"),
            ("/redflags/ai-agent-sanctions-compliance-red-flags", "AI agent sanctions compliance red flags"),
            ("/redflags/agent-paying-sanctioned-wallet", "The #1 red flag: an agent paying a sanctioned wallet"),
            ("/redflags/stablecoin-payment-to-sanctioned-entity", "Stablecoin payments to sanctioned entities"),
            ("/redflags/cross-chain-sanctions-evasion", "Cross-chain sanctions evasion"),
            ("/redflags/high-risk-jurisdiction-payments", "Payments to high-risk jurisdictions"),
            ("/redflags/pep-and-adverse-media-screening-red-flags", "PEP & adverse-media red flags"),
            ("/redflags/agent-bypassing-screening-control", "When your own agent bypasses the screen"),
        ]
    )
    body = textwrap.dedent(f"""\
    <header>
    <p class="lede">Red flags</p>
    <h1>OFAC red flags for AI agents</h1>
    <p class="lede">The transaction patterns that trigger OFAC scrutiny, bank freezes, and enforcement actions &mdash; and the screening control that catches each one before the payment signs.</p>
    </header>
    <ul style="line-height:2;list-style:none;padding-left:0">
    {items}
    </ul>
    {_cta("Block every red flag before payment",
          "Pre-transaction OFAC screening in under 100ms. Free tier: 5 checks/day.")}
    {_related([
        ("/how-to/avoid-ofac-violations", "How to avoid OFAC violations"),
        ("/penalties/ofac-violation-costs", "OFAC violation costs"),
        ("/playbook", "The Agent Compliance Playbook"),
        ("/glossary/strict-liability", "What is strict liability?"),
    ])}""")
    html = _page(
        path="/redflags",
        title="OFAC Red Flags for AI Agents | SanctionsAI",
        description="The transaction patterns that trigger OFAC scrutiny for AI payment agents, and the screening control that catches each one.",
        body=body,
        breadcrumb_name="Red flags",
    )
    out = os.path.join(ROOT, "public", "redflags", "index.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    return "/redflags"


def build_sitemap_index_stub():
    """Index pages for /redflags and /scenarios are served from public/ via
    _serve_file_content, matching the existing /countries, /best, and
    /alternatives-to index pattern. We do not add new api.py routes for them;
    the section roots already fall through cleanly because the prefix loop only
    matches /redflags/<slug>, and the bare /redflags is handled by the existing
    section-index block near api.py:2888 (we extend that block separately).
    """
    pass


def build_scenarios_index() -> str:
    items = "".join(
        f'<li><a href="{u}">{label}</a></li>'
        for u, label in [
            ("/scenarios/ai-agent-sanctions-violation",
             "What happens when an AI agent screens a sanctioned wallet"),
            ("/scenarios/ofac-penalty-crypto-sanctioned-wallet",
             "OFAC penalty for a crypto payment to a sanctioned wallet — real case"),
        ]
    )
    body = textwrap.dedent(f"""\
    <header>
    <p class="lede">Scenarios</p>
    <h1>OFAC sanctions scenarios for AI agents</h1>
    <p class="lede">Real-world walkthroughs of how sanctions violations happen with autonomous payment agents, what the consequences look like, and the screening control that prevents each one.</p>
    </header>
    <ul style="line-height:2;list-style:none;padding-left:0">
    {items}
    </ul>
    {_cta("Prevent the scenario before it executes",
          "Pre-transaction OFAC screening in under 100ms. Free tier: 5 checks/day.")}
    {_related([
        ("/redflags", "OFAC red flags"),
        ("/data/ofac-enforcement", "OFAC enforcement actions"),
        ("/penalties/ofac-violation-costs", "OFAC violation costs"),
        ("/how-to/file-voluntary-disclosure", "File a voluntary self-disclosure"),
    ])}""")
    html = _page(
        path="/scenarios",
        title="OFAC Sanctions Scenarios for AI Agents | SanctionsAI",
        description="Real-world scenarios of sanctions violations with autonomous payment agents, the consequences, and the screening control that prevents each one.",
        body=body,
        breadcrumb_name="Scenarios",
    )
    out = os.path.join(ROOT, "public", "scenarios", "index.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    return "/scenarios"


def write_sitemap(urls: list[str]):
    with open(os.path.join(ROOT, "sitemap-pseo-round20.xml"), "w") as fh:
        fh.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        fh.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for u in urls:
            fh.write(f'  <url><loc>{SITE}{u}</loc><changefreq>weekly</changefreq>'
                     f'<priority>0.7</priority></url>\n')
        fh.write('</urlset>\n')


if __name__ == "__main__":
    rf = build_redflags()
    al = build_alternatives()
    gl = build_glossary()
    rfi = build_redflags_index(rf)
    sci = build_scenarios_index()
    print(f"redflags:       {len(rf)} pages")
    print(f"alternatives:   {len(al)} pages")
    print(f"glossary:       {len(gl)} pages")
    print(f"redflags index:  {rfi}")
    print(f"scenarios index: {sci}")
    # Include the existing orphan scenario pages so they get re-submitted too
    total = rf + al + gl + [rfi, sci,
                            "/scenarios/ai-agent-sanctions-violation",
                            "/scenarios/ofac-penalty-crypto-sanctioned-wallet",
                            "/redflags/ai-agent-sanctions-compliance-red-flags",
                            "/redflags/crypto-payment-ofac-red-flags"]
    write_sitemap(total)
    print(f"\nTotal URLs in sitemap-pseo-round20.xml: {len(total)}")
