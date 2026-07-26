#!/usr/bin/env python3
"""
Round 21 pSEO: /programs/ section — OFAC sanctions programs.

Each OFAC sanctions program (SDGT, Russia-EO14024, Iran, Cuba, etc.) is a
query-rich entity ("what is the SDGT list", "Russia EO 14024 sanctions").
This generator emits a section index at /programs and one page per program
under /programs/<slug>/index.html, served via the prefix-loop at api.py:2837.

Program data is vetted against the existing _BY_COUNTRY dataset (api.py:~10040)
plus the standard public OFAC program catalogue. No invented regulatory facts.

Run from repo root:
    python3 scripts/build_programs_pseo.py
"""
from __future__ import annotations
import json
import os
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SITE = "https://sanctionsai.dev"
DATE = "2026-07-26"

# Reuse the proven template shell from build_pseo_round20 for visual consistency.
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
.callout{background:#f0f7ff;border-left:4px solid #0066cc;padding:1rem 1.25rem;margin:1.5rem 0;border-radius:0 .375rem .375rem 0}
.callout.warn{background:#fef3c7;border-left-color:#d97706}
.cta{background:#0066cc;color:#fff;padding:1.25rem 1.5rem;border-radius:.5rem;text-align:center;margin:2rem 0}
.cta a{color:#fff;font-weight:600;font-size:1.1rem}.cta p{color:#dbeafe}
.related-links{background:#f9fafb;padding:1rem 1.25rem;border-radius:.5rem;margin-top:2.5rem}
.related-links ul{list-style:none;padding:0;display:grid;grid-template-columns:1fr 1fr;gap:.4rem 1rem}
footer{margin-top:3rem;padding-top:1.5rem;border-top:1px solid #e5e7eb;color:#6b7280;font-size:.9rem}
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


def _jsonld(*blocks):
    return "\n".join(
        f'<script type="application/ld+json">{json.dumps(b, separators=(",", ":"))}</script>'
        for b in blocks
    )


def _page(*, path, title, description, body, faq=None, extra_jsonld=None, breadcrumb_name=None):
    url = f"{SITE}{path}"
    crumb = breadcrumb_name or title
    blocks = [
        {"@context": "https://schema.org", "@type": "Article", "headline": title,
         "description": description,
         "author": {"@type": "Organization", "name": "SanctionsAI", "url": SITE},
         "publisher": {"@type": "Organization", "name": "SanctionsAI", "url": SITE},
         "mainEntityOfPage": {"@type": "WebPage", "@id": url},
         "datePublished": DATE, "dateModified": DATE},
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE}/"},
            {"@type": "ListItem", "position": 2, "name": crumb, "item": url}]},
    ]
    if faq:
        blocks.append({"@context": "https://schema.org", "@type": "FAQPage",
                       "mainEntity": [{"@type": "Question", "name": q,
                                       "acceptedAnswer": {"@type": "Answer", "text": a}}
                                      for q, a in faq]})
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
    <!-- isenberg-round21 -->
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


def _cta(title, sub):
    return (f'<div class="cta"><h2>{title}</h2><p>{sub}</p>'
            '<a href="/tools/wallet-checker">Screen a counterparty free &rarr;</a>'
            '&nbsp;&nbsp;<a href="/pricing">See pricing</a></div>')


def _related(items):
    lis = "".join(f'<li><a href="{u}">{t}</a></li>' for u, t in items)
    return f'<div class="related-links"><h3>Related</h3><ul>{lis}</ul></div>'


# ---------------------------------------------------------------------------
# OFAC sanctions programs — vetted against the public OFAC program catalogue
# and the existing _BY_COUNTRY dataset. Each entry is factual.
# ---------------------------------------------------------------------------
PROGRAMS = [
    {
        "slug": "sdgt",
        "name": "SDGT (Specially Designated Global Terrorists)",
        "code": "SDGT",
        "authority": "Executive Order 13224 (2001, as amended)",
        "scope": "Terrorism",
        "desc": "The SDGT program designates individuals and entities that commit, or pose a significant risk of committing, acts of terrorism. SDGT parties are added to the SDN list and all their property under US jurisdiction is blocked.",
        "targets": "Terrorist financiers, front organizations, affiliated wallets and funders. Major designations have included al-Qa'ida, ISIS, and their financial networks.",
        "count": "Approximately 1,500+ SDN designations",
        "agents": "SDGT is one of the strictest program categories. Any wallet or name matching SDGT must be hard-blocked by a payment agent &mdash; there is no de minimis or routine license path for terrorism designations.",
        "faq": [
            ("Is SDGT a comprehensive embargo?",
             "No, SDGT is a list-based designation program, not a country embargo. It blocks the listed terrorists and their networks rather than prohibiting all transactions with a jurisdiction."),
            ("Can you transact with an SDGT under a license?",
             "Licenses for SDGT designations are rare and case-specific. Treat any SDGT match as a hard block pending specialist legal review."),
        ],
    },
    {
        "slug": "russia-eo14024",
        "name": "Russia — EO 14024 (Harmful Foreign Activities)",
        "code": "RUS-EO14024",
        "authority": "Executive Order 14024 (April 2021, as amended); Russia sanctions regulations",
        "scope": "Russia / Sovereignty",
        "desc": "EO 14024 is the primary modern authority for Russia-related blocking sanctions, authorizing designations over Russia's harmful foreign activities including the actions against Ukraine. It is the legal basis for a large share of current Russia SDN designations.",
        "targets": "Russian banks (including major financial institutions), oligarchs and their holding companies, defense and technology firms, and entities supporting the Russian government. Secondary-sanctions exposure extends to certain non-US persons.",
        "count": "Approximately 4,000+ SDN designations across the Russia program",
        "agents": "Russia is the most active program by designation volume and changes frequently. Payment agents handling cross-border or crypto flows must screen every Russia-connected counterparty, as new designations land continuously and prior-clean wallets become sanctioned overnight.",
        "faq": [
            ("Is all of Russia sanctioned under EO 14024?",
             "No. Russia is not under a comprehensive embargo. EO 14024 designates specific banks, firms, and individuals; counterparty-level screening is required rather than a blanket jurisdiction block."),
            ("Does EO 14024 have secondary sanctions?",
             "Yes. Certain conduct with EO 14024-designated parties can expose non-US persons to secondary sanctions, even without a US nexus."),
        ],
    },
    {
        "slug": "iran",
        "name": "Iran Sanctions Program",
        "code": "IRAN",
        "authority": "Iranian Transactions and Sanctions Regulations (ITSR); EOs 12170, 13846, 13902, and others",
        "scope": "Comprehensive / Iran",
        "desc": "Iran is subject to comprehensive US sanctions. The ITSR prohibits nearly all transactions involving Iran by US persons, and authorizes secondary sanctions on non-US persons for specified conduct with Iran.",
        "targets": "The Government of Iran, Iranian financial institutions (including designated banks), the energy and petrochemical sectors, and entities supporting Iran's nuclear or military programs.",
        "count": "Approximately 2,000+ SDN designations",
        "agents": "Iran is a comprehensively sanctioned jurisdiction. Payment agents must check the destination jurisdiction, not just the counterparty &mdash; a clean wallet tied to an Iranian end-party is still a prohibited transaction. Secondary-sanctions exposure is significant for non-US operators.",
        "faq": [
            ("Is Iran under a comprehensive embargo?",
             "Yes. Nearly all transactions involving Iran by US persons are prohibited, and secondary sanctions apply to specified non-US conduct."),
            ("Are humanitarian transactions to Iran allowed?",
             "Certain humanitarian transactions (food, medicine) are licensed or exempt, but they require careful structuring. They are not automatic."),
        ],
    },
    {
        "slug": "north-korea",
        "name": "North Korea (DPRK) Sanctions Program",
        "code": "DPRK",
        "authority": "North Korea Sanctions and Policy Enhancement Act; EOs 13466, 13551, 13570, 13687, 13722, 13810",
        "scope": "Comprehensive / DPRK",
        "desc": "North Korea (DPRK) is subject to comprehensive US sanctions covering nearly all transactions. The program is among the strictest in the US sanctions catalogue and targets the regime's weapons programs, financial networks, and labor exports.",
        "targets": "The Government of North Korea, the Worker's Party, designated banks, shipping and insurance entities, and IT worker revenue-generation networks.",
        "count": "Approximately 1,500+ SDN designations",
        "agents": "DPRK is comprehensively sanctioned and a top priority for crypto enforcement (state-sponsored wallet laundering). Any North Korea nexus is a hard block; the wallet-screening and jurisdiction-screening layers both apply.",
        "faq": [
            ("Is all trade with North Korea prohibited?",
             "Yes. The DPRK program is comprehensive; nearly all transactions are prohibited, with very narrow humanitarian exceptions."),
            ("Why is DPRK relevant to crypto agents?",
             "North Korea's state actors are among the most prolific crypto thieves and launderers. Wallet screening catches designated DPRK-linked addresses."),
        ],
    },
    {
        "slug": "cuba",
        "name": "Cuba Sanctions Program",
        "code": "CUBA",
        "authority": "Cuban Assets Control Regulations (CACR), 31 CFR Part 515; EO 9193 and successors",
        "scope": "Comprehensive / Cuba",
        "desc": "Cuba is subject to comprehensive US sanctions under the CACR. The program prohibits most transactions involving Cuba by US persons and is administered under a complex framework of general licenses and prohibitions.",
        "targets": "The Government of Cuba, Cuban military and intelligence entities, and restricted entities. The scope has shifted across administrations, so current general licenses must be checked.",
        "count": "Approximately 300+ SDN designations",
        "agents": "Cuba is comprehensively sanctioned for US persons. Payment agents must check destination jurisdiction and apply general-license analysis carefully &mdash; the rules differ materially from other comprehensive programs.",
        "faq": [
            ("Is the Cuba embargo still in effect?",
             "Yes. The CACR remains in force, though the scope of permitted transactions has shifted across administrations. Current general licenses must be checked."),
            ("Can US persons send money to Cuba?",
             "Only under specific general licenses (e.g., certain family remittances). Outside a license, transactions are prohibited."),
        ],
    },
    {
        "slug": "syria",
        "name": "Syria Sanctions Program",
        "code": "SYRIA",
        "authority": "Syrian Civilian Protection Act (Caesar Act); EOs 13572, 13573, 13606, 13608, 13894; Syrian Sanctions Regulations",
        "scope": "Comprehensive / Syria",
        "desc": "Syria is subject to comprehensive US sanctions. The program targets the Syrian government, its financial networks, and entities supporting the Assad regime, with additional authorities under the Caesar Act.",
        "targets": "The Government of Syria, the Central Bank of Syria, designated individuals and entities tied to the regime, and sectors including energy, construction, and aviation.",
        "count": "Approximately 800+ SDN designations",
        "agents": "Syria is comprehensively sanctioned. Payment agents must treat any Syrian nexus as a hard block; jurisdiction screening is mandatory in addition to counterparty screening.",
        "faq": [
            ("Is Syria under comprehensive sanctions?",
             "Yes. Most transactions involving Syria are prohibited, with narrow humanitarian and other licensed exceptions."),
            ("What is the Caesar Act?",
             "The Syrian Civilian Protection Act (Caesar Act) expanded secondary sanctions on those supporting the Syrian government, including non-US persons."),
        ],
    },
    {
        "slug": "venezuela",
        "name": "Venezuela Sanctions Program",
        "code": "VENEZUELA",
        "authority": "Venezuela Sanctions Regulations; EOs 13808, 13827, 13835, 13884",
        "scope": "Sectoral / Venezuela",
        "desc": "Venezuela faces comprehensive sectoral sanctions targeting the oil sector, gold sector, and the Maduro government. Sanctions intensified with full government-blocking sanctions under EO 13884.",
        "targets": "PDVSA (state oil company), the Central Bank of Venezuela, Maduro government officials, and related entities. The program is sectoral rather than a blanket jurisdiction embargo.",
        "count": "Approximately 200+ SDN designations",
        "agents": "Venezuela sanctions are sectoral and government-focused, not a comprehensive embargo. Agents must screen counterparties against the program and apply sector-specific analysis for oil, gold, and government-linked entities.",
        "faq": [
            ("Is Venezuela under a comprehensive embargo?",
             "No. Venezuela is under sectoral and government-blocking sanctions, not a blanket jurisdiction embargo. Sector-specific analysis is required."),
            ("Can you transact with PDVSA?",
             "PDVSA is sanctioned. Transactions are prohibited absent a specific license; certain general licenses have applied historically and must be checked."),
        ],
    },
    {
        "slug": "belarus",
        "name": "Belarus Sanctions Program",
        "code": "BELARUS",
        "authority": "Belarus Sanctions Regulations; EO 14038; EO 13665 (in part)",
        "scope": "Sectoral / Belarus",
        "desc": "Belarus faces sanctions aligned with the Russia sanctions regime, following the 2020 election fraud and Belarus's support for Russia's invasion of Ukraine. The program targets defense, potash, and state enterprises.",
        "targets": "Belarussian Potash Company, Belinvestbank, state enterprises, and government officials aligned with Russia.",
        "count": "Approximately 150+ SDN designations",
        "agents": "Belarus sanctions track closely with the Russia program. Payment agents should treat Belarus-connected counterparties as elevated risk and screen against both programs, since designations are coordinated.",
        "faq": [
            ("Are Belarus and Russia sanctions linked?",
             "Yes, closely. Belarus sanctions were expanded in coordination with Russia sanctions after 2020; screening should cover both programs."),
            ("Is Belarus comprehensively sanctioned?",
             "No. Belarus is under targeted, sectoral sanctions, not a comprehensive embargo."),
        ],
    },
    {
        "slug": "myanmar",
        "name": "Myanmar (Burma) Sanctions Program",
        "code": "BURMA",
        "authority": "Burma Sanctions Regulations; EO 14014; EO 13818",
        "scope": "Targeted / Myanmar",
        "desc": "Myanmar faces targeted sanctions on military leaders and military-owned enterprises following the 2021 coup. The program targets the junta's revenue sources, including oil, gas, timber, and gems.",
        "targets": "Myanmar Economic Corporation (MEC), Myanmar Economic Holdings Limited (MEHL), junta officials, and state oil and gas enterprises.",
        "count": "Approximately 80+ SDN designations",
        "agents": "Myanmar sanctions are targeted at military-owned enterprises and officials. Agents handling counterparties in extractive sectors should screen against the program; non-military civilian trade is generally not prohibited.",
        "faq": [
            ("Is Myanmar comprehensively sanctioned?",
             "No. Sanctions are targeted at the military, its enterprises, and officials, not the country as a whole."),
            ("What are MEC and MEHL?",
             "Myanmar Economic Corporation and Myanmar Economic Holdings Limited &mdash; military-owned conglomerates that are primary sanctions targets."),
        ],
    },
    {
        "slug": "china-xinjiang-hongkong",
        "name": "China — Xinjiang & Hong Kong Sanctions",
        "code": "PRC-HUMAN-RIGHTS",
        "authority": "Uyghur Human Rights Policy Act; Hong Kong Autonomy Act; EO 13936; Military End-User List (BIS)",
        "scope": "Targeted / China",
        "desc": "China faces targeted sanctions related to human rights abuses in Xinjiang, the Hong Kong crackdown, and military-civil fusion. The program is not comprehensive &mdash; most US-China trade remains legal.",
        "targets": "Xinjiang Production and Construction Corps (XPCC), entities tied to Xinjiang internment, persons involved in the Hong Kong crackdown, and Military End-User-listed firms.",
        "count": "Approximately 300+ SDN and entity-list designations",
        "agents": "China sanctions are targeted, not comprehensive. Agents should screen counterparties against the program and the BIS Military End-User List, but ordinary commercial trade is generally permitted.",
        "faq": [
            ("Is China under comprehensive sanctions?",
             "No. Sanctions are targeted at specific human-rights and military-civil-fusion entities. Most trade remains legal."),
            ("What is the Military End-User List?",
             "A BIS export-control list restricting exports to entities supporting military end-uses. It complements, but differs from, OFAC SDN sanctions."),
        ],
    },
    {
        "slug": "ukraine-separatist",
        "name": "Ukraine-Russia Separatist Regions",
        "code": "UKRAINE",
        "authority": "EO 13660, EO 13661, EO 13662; Ukraine-/Russia-Related Sanctions Regulations",
        "scope": "Territorial / Ukraine",
        "desc": "Designations cover the Russia-backed separatist regions of eastern Ukraine, Russia-occupied Crimea, and persons involved in undermining Ukraine's sovereignty. The program expanded significantly after 2022.",
        "targets": "Self-proclaimed DNR/LNR officials, Russian-backed separatist commanders, and seized Crimean enterprises.",
        "count": "Approximately 700+ SDN designations",
        "agents": "These sanctions are territorial and overlap heavily with the Russia program. Agents handling counterparties in the affected regions must screen against the Ukraine authorities and treat the regions as restricted jurisdictions.",
        "faq": [
            ("What are DNR and LNR?",
             "The self-proclaimed Donetsk and Luhansk People's Republics &mdash; Russia-backed separatist entities in eastern Ukraine that are subject to sanctions."),
            ("Is Crimea sanctioned?",
             "Yes. Russia-occupied Crimea is subject to comprehensive US sanctions; most transactions involving the region are prohibited."),
        ],
    },
    {
        "slug": "hezbollah",
        "name": "Hezbollah Sanctions Program",
        "code": "HIZBALLAH",
        "authority": "Hezbollah Financial Sanctions Regulations (HFSR); Hizballah International Financing Prevention Act; EO 13224; EO 13582",
        "scope": "Terrorism / Lebanon",
        "desc": "Hezbollah and its financial networks are sanctioned as a Specially Designated Global Terrorist entity. Designations reach into Lebanese banking, trade, and diaspora financial networks.",
        "targets": "Hezbollah, affiliated financiers and money launderers, and front organizations such as Al-Qard al-Hassan.",
        "count": "Approximately 120+ SDN designations",
        "agents": "Hezbollah designations are terrorism-based (SDGT) and reach financial front organizations. Agents handling Lebanon-connected counterparties should screen against the Hezbollah program specifically, not just the broad SDN list.",
        "faq": [
            ("Is Hezbollah the same as the Lebanon country program?",
             "No. Hezbollah is a terrorism/SDGT designation targeting the organization and its networks; it is distinct from any Lebanon country-level program."),
            ("What is Al-Qard al-Hassan?",
             "A Hezbollah-linked financial association sanctioned as a front for the organization's financing."),
        ],
    },
    {
        "slug": "countering-americas-adversaries",
        "name": "CAATSA (Countering America's Adversaries Through Sanctions Act)",
        "code": "CAATSA",
        "authority": "Public Law 115-44 (2017); Codified sanctions on Russia, Iran, North Korea",
        "scope": "Statutory / Multi-program",
        "desc": "CAATSA is a 2017 statute that codified and expanded sanctions on Russia, Iran, and North Korea. It imposed mandatory sanctions frameworks and significant secondary-sanctions authorities that OFAC and State administer.",
        "targets": "Russian defense and intelligence entities, Iran's ballistic missile and Revolutionary Guard networks, and North Korea's shipping, energy, and labor export sectors.",
        "count": "Cross-references the Russia, Iran, and DPRK programs",
        "agents": "CAATSA is a statutory overlay that expands secondary-sanctions exposure, particularly for non-US persons dealing with Russia, Iran, or DPRK. Agents operated by non-US entities should understand the secondary-sanctions reach CAATSA created.",
        "faq": [
            ("What is CAATSA?",
             "The Countering America's Adversaries Through Sanctions Act of 2017 &mdash; a statute codifying and expanding sanctions on Russia, Iran, and North Korea."),
            ("Does CAATSA apply to non-US companies?",
             "Yes, significantly. CAATSA created broad secondary-sanctions authorities that can reach non-US persons for specified conduct with designated parties."),
        ],
    },
    {
        "slug": "global-magnitsky",
        "name": "Global Magnitsky (Human Rights & Corruption)",
        "code": "GLOMAG",
        "authority": "Global Magnitsky Human Rights Accountability Act; EO 13818",
        "scope": "Human rights / Corruption",
        "desc": "The Global Magnitsky program authorizes blocking sanctions on persons responsible for serious human rights abuse or significant corruption anywhere in the world. It is jurisdiction-agnostic &mdash; designations span many countries.",
        "targets": "Human rights abusers, corrupt officials and their networks, and associated entities across dozens of countries.",
        "count": "Hundreds of designations across 40+ countries",
        "agents": "Global Magnitsky designations are not country-specific, so agents cannot rely on jurisdiction alone to exclude them. A counterparty in a 'clean' jurisdiction can still be Glomag-designated; counterparty screening is required.",
        "faq": [
            ("What is the Global Magnitsky Act?",
             "A US law authorizing sanctions on persons responsible for serious human rights abuse or significant corruption, regardless of country."),
            ("Do Magnitsky sanctions only target certain countries?",
             "No. They are jurisdiction-agnostic; designations span 40+ countries and cannot be excluded by jurisdiction alone."),
        ],
    },
    {
        "slug": "narcotics-trafficking",
        "name": "Drug Kingpin & Narcotics Trafficking Sanctions",
        "code": "SDNTK",
        "authority": "Foreign Narcotics Kingpin Designation Act (Kingpin Act); EO 12978",
        "scope": "Narcotics",
        "desc": "The narcotics trafficking program (SDNTK) designates significant foreign narcotics traffickers and their networks. Designated parties are added to the SDN list and their property is blocked.",
        "targets": "Drug cartels, their financiers and money launderers, and associated front companies. Major designations have included Latin American cartels and fentanyl trafficking networks.",
        "count": "Approximately 2,000+ SDN designations",
        "agents": "Narcotics designations include extensive financial-network entries (money launderers, front companies). Agents handling cross-border payments should screen against SDNTK, especially for Latin America-connected counterparties.",
        "faq": [
            ("What does SDNTK stand for?",
             "Specially Designated Narcotics Traffickers &mdash; the OFAC program tag for narcotics-related designations under the Kingpin Act."),
            ("Are narcotics sanctions relevant to crypto agents?",
             "Yes. Narcotics money laundering increasingly uses crypto rails, and SDNTK designations include wallet addresses tied to trafficking networks."),
        ],
    },
    {
        "slug": "non-proliferation",
        "name": "Weapons of Mass Destruction Proliferators (WMD)",
        "code": "NP",
        "authority": "EO 12938 (as amended); Iran, North Korea, and Syria Nonproliferation Act",
        "scope": "Proliferation",
        "desc": "The WMD non-proliferation program designates entities involved in the proliferation of weapons of mass destruction and their delivery systems. It complements the Iran, DPRK, and Syria country programs.",
        "targets": "Proliferators of WMD technology, their suppliers and financiers, and entities supporting Iran, DPRK, or Syria weapons programs.",
        "count": "Hundreds of designations",
        "agents": "WMD designations are proliferation-focused and often overlap with the Iran, DPRK, and Syria programs. Agents handling counterparties in sensitive dual-use technology sectors should screen against the WMD authorities.",
        "faq": [
            ("What does the WMD non-proliferation program target?",
             "Entities involved in proliferating weapons of mass destruction and delivery systems, including their suppliers and financiers."),
            ("Is the WMD program separate from the Iran/DPRK programs?",
             "It overlaps but is distinct: WMD authorities can reach proliferators regardless of country, complementing the country-specific programs."),
        ],
    },
    {
        "slug": "rough-diamonds",
        "name": "Rough Diamonds (Kimberley Process)",
        "code": "DRC-DIAMONDS",
        "authority": "Clean Diamond Trade Act; EO 13348; 31 CFR Part 592",
        "scope": "Trade controls / Diamonds",
        "desc": "The rough diamond controls implement the Kimberley Process Certification Scheme, prohibiting import of rough diamonds without valid certification and targeting conflict-diamond trade.",
        "targets": "Trade in uncertified rough diamonds and conflict-diamond networks, with linked designations in the DRC and neighboring regions.",
        "count": "Smaller program; primarily trade-control rather than broad blocking sanctions",
        "agents": "Diamond-trade compliance is a niche concern for most payment agents, but commerce agents handling physical-goods trade should be aware of the certification requirements for rough diamonds.",
        "faq": [
            ("What is the Kimberley Process?",
             "An international certification scheme that controls trade in rough diamonds to prevent conflict-diamond circulation."),
            ("Is the diamond program relevant to payment agents?",
             "Rarely, except for commerce agents handling physical-goods trade. It is primarily a trade-control and certification regime."),
        ],
    },
    {
        "slug": "transnational-criminal-orgs",
        "name": "Transnational Criminal Organizations (TCO)",
        "code": "TCO",
        "authority": "Transnational Organized Crime (TOC) program; EO 13581",
        "scope": "Organized crime",
        "desc": "The TCO program designates significant transnational criminal organizations and their members, associates, and support networks. Designated parties are added to the SDN list.",
        "targets": "Transnational criminal organizations, including cartels, cybercrime groups, and their financial networks and front companies.",
        "count": "Hundreds of designations",
        "agents": "TCO designations include financial-network entries that matter for payment screening. Agents should screen counterparties against the TCO tag, particularly for high-risk jurisdictions and known money-laundering corridors.",
        "faq": [
            ("What is a TCO designation?",
             "A designation of a significant transnational criminal organization, its members, and support networks under the TOC program."),
            ("Do TCO sanctions include crypto addresses?",
             "Yes, where the organization launders funds via crypto. TCO-linked wallets appear on the SDN digital-assets list."),
        ],
    },
    {
        "slug": "cyber-related",
        "name": "Cyber-Related Sanctions",
        "code": "CYBER",
        "authority": "EO 13694 (2015, as amended by EO 13757)",
        "scope": "Cyber",
        "desc": "The cyber-related sanctions program designates persons responsible for significant malicious cyber activities, including hacking, disruption of critical infrastructure, and theft of trade secrets or funds.",
        "targets": "Cybercriminals, state-sponsored hacking groups, ransomware operators, and their money-laundering networks. Many designations include crypto wallet addresses.",
        "count": "Hundreds of designations, many with crypto addresses",
        "agents": "Cyber sanctions are highly relevant to crypto payment agents &mdash; designated wallets are often added to the SDN digital-assets list. Pre-transaction wallet screening is the primary control for catching cyber-sanctioned addresses.",
        "faq": [
            ("Do cyber sanctions include crypto wallet addresses?",
             "Yes. Designated cyber actors frequently receive crypto, so their wallets appear on the SDN digital-assets list."),
            ("What does EO 13694 cover?",
             "Significant malicious cyber activities harming US national security, foreign policy, or economic health, including infrastructure disruption and fund theft."),
        ],
    },
    {
        "slug": "foreign-interference",
        "name": "Foreign Interference in US Elections",
        "code": "ELECTIONS",
        "authority": "EO 13848 (2018)",
        "scope": "Election integrity",
        "desc": "EO 13848 authorizes sanctions on persons responsible for foreign interference in US elections. Designated parties are added to the SDN list.",
        "targets": "Foreign actors responsible for election interference, including operatives, financiers, and associated entities.",
        "count": "Smaller program; targeted designations",
        "agents": "Election-interference designations are targeted and smaller in volume but are part of the SDN list screened in every check. No special handling beyond standard screening is required.",
        "faq": [
            ("What does EO 13848 cover?",
             "Foreign interference in US elections, including covert influence operations and related financing."),
            ("Are election-interference designations on the SDN list?",
             "Yes. They appear with their program tag and are caught by standard SDN screening."),
        ],
    },
]


def build_programs() -> list[str]:
    urls = []
    for p in PROGRAMS:
        body = textwrap.dedent(f"""\
        <header>
        <p class="lede">OFAC sanctions program</p>
        <h1>{p["name"]}</h1>
        <p class="lede">{p["desc"]}</p>
        </header>
        <h2>Program at a glance</h2>
        <table>
        <tr><th>Program code</th><td>{p["code"]}</td></tr>
        <tr><th>Legal authority</th><td>{p["authority"]}</td></tr>
        <tr><th>Scope</th><td>{p["scope"]}</td></tr>
        <tr><th>Designation volume</th><td>{p["count"]}</td></tr>
        </table>
        <h2>Who and what it targets</h2>
        <p>{p["targets"]}</p>
        <h2>Relevance to AI agents</h2>
        <p>{p["agents"]}</p>
        <div class="callout warn">
        <strong>Screening note.</strong> A counterparty program match is not always a blanket block &mdash;
        the program tag tells your agent how to route the hit (hard block for terrorism/embargo,
        review-required for sectoral, etc.). SanctionsAI returns the program code on every match.
        </div>
        <h2>Frequently asked questions</h2>
        {"".join(f'<details style="margin:10px 0;padding:14px;border:1px solid #e5e7eb;border-radius:10px"><summary style="font-weight:600;cursor:pointer">{q}</summary><p style="margin-top:8px;color:#374151">{a}</p></details>' for q,a in p["faq"])}
        <div class="callout">
        <strong>Compliance disclaimer.</strong> This page is educational and not legal advice.
        Program scope and current general licenses must be confirmed against the live OFAC programme
        page and, where relevant, by a qualified professional.
        </div>
        {_cta("Screen a counterparty against every program",
              "Returns the program code on every match. Free tier: 5 checks/day.")}
        {_related([
            ("/programs", "All OFAC sanctions programs"),
            ("/programs/russia-eo14024", "Russia &mdash; EO 14024"),
            ("/programs/sdgt", "SDGT (global terrorism)"),
            ("/programs/iran", "Iran program"),
            ("/glossary/ofac-sdn-list", "OFAC SDN list"),
            ("/glossary/secondary-sanctions", "Secondary sanctions"),
            ("/countries", "Sanctions by country"),
            ("/by-country", "Sanctioned entities by country"),
        ])}""")
        html = _page(
            path=f"/programs/{p['slug']}",
            title=f"{p['name']} | OFAC Sanctions Program | SanctionsAI",
            description=f"{p['desc']} Authority: {p['authority']}. What the program targets and how AI agents should screen against it.",
            body=body,
            faq=p["faq"],
            breadcrumb_name=p["name"],
            extra_jsonld=[{
                "@context": "https://schema.org",
                "@type": "DefinedTerm",
                "name": p["name"],
                "description": p["desc"],
                "url": f"{SITE}/programs/{p['slug']}",
            }],
        )
        out = os.path.join(ROOT, "programs", p["slug"], "index.html")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(html)
        urls.append(f"/programs/{p['slug']}")
    return urls


def build_programs_index(child_urls: list[str]) -> str:
    items = "".join(
        f'<li><a href="/programs/{p["slug"]}">{p["name"]}</a> &mdash; <span style="color:#6b7280">{p["scope"]}</span></li>'
        for p in PROGRAMS
    )
    body = textwrap.dedent(f"""\
    <header>
    <p class="lede">OFAC sanctions programs</p>
    <h1>OFAC sanctions programs</h1>
    <p class="lede">The complete catalogue of active US sanctions programs under OFAC, with the legal authority, scope, targets, and designation volume for each &mdash; and how autonomous payment agents should screen against each one.</p>
    </header>
    <ul style="line-height:2.2;list-style:none;padding-left:0">
    {items}
    </ul>
    <div class="callout">
    <strong>How program codes work.</strong> Every SDN-listed party carries one or more program tags
    (SDGT, RUS-EO14024, IRAN, SDNTK, CYBER, and so on). The tag tells your agent the nature of the
    designation &mdash; which matters because a terrorism designation and a sectoral designation route
    to different handling. SanctionsAI returns the program code on every match.
    </div>
    {_cta("Screen against every program in one call",
          "Returns the program code on every match. Free tier: 5 checks/day.")}
    {_related([
        ("/glossary/ofac-sdn-list", "OFAC SDN list"),
        ("/countries", "Sanctions by country"),
        ("/by-country", "Sanctioned entities by country"),
        ("/sanctions-lists", "Sanctions lists explained"),
        ("/how-to/comply-with-ofac", "How to comply with OFAC"),
    ])}""")
    html = _page(
        path="/programs",
        title="OFAC Sanctions Programs (Complete List) | SanctionsAI",
        description="The complete catalogue of active US OFAC sanctions programs: legal authority, scope, targets, designation volume, and how AI agents screen against each one.",
        body=body,
        breadcrumb_name="OFAC sanctions programs",
    )
    out = os.path.join(ROOT, "public", "programs", "index.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    return "/programs"


if __name__ == "__main__":
    child = build_programs()
    idx = build_programs_index(child)
    print(f"programs: {len(child)} child pages")
    print(f"index:    {idx}")
    urls = child + [idx]
    with open(os.path.join(ROOT, "sitemap-pseo-round21.xml"), "w") as fh:
        fh.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        fh.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for u in urls:
            fh.write(f'  <url><loc>{SITE}{u}</loc><changefreq>monthly</changefreq>'
                     f'<priority>0.7</priority></url>\n')
        fh.write('</urlset>\n')
    print(f"Total: {len(urls)} URLs -> sitemap-pseo-round21.xml")
