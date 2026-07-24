#!/usr/bin/env python3
"""build_glossary.py — render the compliance glossary from glossary.json into
static pages under learn/ (served by api.py's pSEO fallback). Verbatim only."""
import json, os, html

ROOT = os.getcwd()
BASE = "https://sanctionsai.dev"
G = json.load(open(os.path.join(ROOT, "glossary.json"), encoding="utf-8"))
DISC = G["disclaimer"]
SRC = G["source"]
TERMS = G["terms"]
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
    scripts = "".join(
        f'<script type="application/ld+json">{json.dumps(j, separators=(",", ":"))}</script>'
        for j in jsonld
    )
    return (
        f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{e(title)}</title><meta name="description" content="{e(desc)}">'
        f'<link rel="canonical" href="{canonical}">'
        f'<meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large">'
        f'{CSS}{scripts}</head><body>{body}'
        f'<p class="disc">{e(DISC)} {e(SRC)}</p></body></html>'
    )


os.makedirs(os.path.join(ROOT, "learn"), exist_ok=True)
term_set_id = f"{BASE}/learn/sanctions-glossary#termset"

# Per-term pages
for t in TERMS:
    slug, term, d = t["slug"], t["term"], t["def"]
    canonical = f"{BASE}/learn/{slug}"
    aka = ", ".join(t.get("aka", []))

    # DefinedTerm JSON-LD
    defined = {
        "@context": "https://schema.org",
        "@type": "DefinedTerm",
        "@id": canonical + "#term",
        "name": term,
        "description": d,
        "inDefinedTermSet": term_set_id,
    }
    if t.get("aka"):
        defined["alternateName"] = t["aka"]

    # FAQPage JSON-LD
    faq = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": f"What is {term}?",
                "acceptedAnswer": {"@type": "Answer", "text": d + " " + DISC},
            }
        ],
    }

    # Related terms (up to 10)
    others = [x for x in TERMS if x["slug"] != slug][:10]
    rel = " · ".join(
        f'<a href="/learn/{x["slug"]}">{e(x["term"])}</a>' for x in others
    )

    body = (
        f'<p style="font-size:.85rem"><a href="/">SanctionsAI</a> › '
        f'<a href="/learn/sanctions-glossary">Glossary</a> › {e(term)}</p>'
        f'<h1>What is {e(term)}?</h1>'
        + (f'<p style="color:#64748b">Also known as: {e(aka)}</p>' if aka else "")
        + f'<div class="def">{e(d)}</div>'
        f'<p>Screening for {e(term)}-related risk is exactly what <a href="/">SanctionsAI</a> automates — '
        f'a single API (HTTP, CLI, or MCP) that screens names and wallets against OFAC lists before your agent pays. '
        f'Free tier, no key: <a href="/docs">see the docs →</a></p>'
        f'<h2>Related terms</h2><p>{rel}</p>'
    )

    os.makedirs(os.path.join(ROOT, "learn", slug), exist_ok=True)
    with open(
        os.path.join(ROOT, "learn", slug, "index.html"), "w", encoding="utf-8"
    ) as f:
        f.write(
            page(
                f"What is {term}? — Sanctions & AI-Agent Compliance Glossary | SanctionsAI",
                f"{term}: {d[:150]}",
                canonical,
                [defined, faq],
                body,
            )
        )

# Hub page (DefinedTermSet)
term_set = {
    "@context": "https://schema.org",
    "@type": "DefinedTermSet",
    "@id": term_set_id,
    "name": "Sanctions & AI-Agent Compliance Glossary",
    "url": f"{BASE}/learn/sanctions-glossary",
    "hasDefinedTerm": [
        {
            "@type": "DefinedTerm",
            "name": t["term"],
            "url": f"{BASE}/learn/{t['slug']}",
            "description": t["def"][:200],
        }
        for t in TERMS
    ],
}

items = "".join(
    f'<li><a href="/learn/{t["slug"]}"><strong>{e(t["term"])}</strong></a> — {e(t["def"][:90])}…</li>'
    for t in TERMS
)

hub_body = (
    f'<p style="font-size:.85rem"><a href="/">SanctionsAI</a> › Glossary</p>'
    f'<h1>Sanctions &amp; AI-Agent Compliance Glossary</h1>'
    f'<p>Plain-English definitions of the sanctions, OFAC, and agentic-payment terms every compliance-aware '
    f"builder needs — from the SDN List and the 50% Rule to KYA and x402.</p><ul>{items}</ul>"
)

os.makedirs(os.path.join(ROOT, "learn", "sanctions-glossary"), exist_ok=True)
with open(
    os.path.join(ROOT, "learn", "sanctions-glossary", "index.html"), "w", encoding="utf-8"
) as f:
    f.write(
        page(
            "Sanctions & AI-Agent Compliance Glossary — OFAC, SDN, 50% Rule, KYA, x402 | SanctionsAI",
            "Plain-English glossary of sanctions and AI-agent compliance terms: OFAC, SDN List, 50% Rule, secondary sanctions, facilitation, KYA, wallet screening, x402, and more.",
            f"{BASE}/learn/sanctions-glossary",
            [term_set],
            hub_body,
        )
    )

print(f"✓ glossary: {len(TERMS)} term pages + hub written under learn/")
