# Brunson Secrets Trilogy Audit — sanctionsai.dev

**Auditor:** Russell Brunson persona, chapter-by-chapter across DotCom Secrets, Expert Secrets, Traffic Secrets
**Date:** 2026-07-25
**Site:** https://sanctionsai.dev · **Repo:** `~/workspace/agentmail` (Fly app `agentmail-api`)
**Prior audit:** `BRUNSON_AUDIT_SCORECARD_2026-07-18.md` — composite **55.5**
**This audit:** **59.2** (+3.7)

Weighting: DotCom 40% / Expert 30% / Traffic 30%. Every score is tied to evidence
pulled from the live site or the source on 2026-07-25.

---

## Composite

| Book | Weight | Avg | Weighted |
|---|---:|---:|---:|
| DotCom Secrets | 40% | 61.3 | 24.5 |
| Expert Secrets | 30% | 66.4 | 19.9 |
| Traffic Secrets | 30% | 49.1 | 14.7 |
| **COMPOSITE** | | | **59.2 / 100** |

**Grade: C+.** The on-page work since 07-18 is real and it moved the needle —
a named framework, a genuine epiphany bridge, a named founder, and a live email
engine. What holds the score down is no longer "nothing is built." It is that
**the site's single most important number is wrong in four different ways**, and
that 246 pages produce 3 clicks a month.

---

## What genuinely improved since 2026-07-18

| Area | Then | Now |
|---|---|---|
| Email engine | `RESEND_API_KEY` unset — every lead leaked | **Deployed**; `/subscribe` returns `email_sent: true` |
| Teachable framework | none (42) | **The 4-Gate Agent Payment Protocol™** — SCREEN → SCORE → STOP → STAMP (85) |
| Attractive Character | pseudonymous "The Data Nerd" (58) | **Named founder "Maryan"** with a first-person story (70) |
| Epiphany Bridge | abstract, no sensory detail (65) | **"test #47"** — specific, dated, concrete (82) |
| Tripwire rung | missing | `/tripwire` $7 Quick-Start Kit exists |
| Future-based cause | no manifesto (60) | **"The Bigger Fight"** section (80) |

---

## DOTCOM SECRETS — 61.3

| Chapter / Secret | Score | Evidence |
|---|:---:|---|
| Secret Formula Q1 — Dream Customer | 78 | Homepage names the exact person and moment: "You are shipping your first x402 payment agent this month. It pays invoices in USDC while you sleep." |
| Secret Formula Q2 — Where they congregate | 80 | `/dream100`: 75 named targets in 3 tiers (agent infra, dev communities, compliance). |
| Secret Formula Q3 — Bait | 74 | Strong hook + `/start` Playbook lead magnet. Docked: hook number is stale and inconsistent (see Defect 1). |
| Secret Formula Q4 — Unique result | 84 | "Screen every counterparty before your agent pays." <100 ms. Concrete counts. |
| Secret #2 — Value Ladder | 66 | Free → $7 → $19 → $99. Tripwire now exists. No rung above $99. |
| Secret #3 — Ladder → Funnel | 62 | Rungs exist; ascension is not wired. `/tripwire` is a dead end — "Checkout is not automated yet." |
| Secret #5 — Three types of traffic | 55 | Owned now live. Earned weak. Paid zero. |
| Secret #6 — Attractive Character | 70 | Named founder, reluctant-hero framing, first-person. No face or video. |
| Secret #7 — Soap Opera Sequence | 78 | 5 days written, day-by-day preview on the homepage, and it actually sends. |
| Secret #8 — Seinfeld Sequence | 68 | 30 subjects + `/cron/drip` state machine. |
| Phases of a funnel | 60 | Pre-frame good; no hyperactive-buyer identification. |
| Front-end lead funnel | 66 | `/start` with an attribution dropdown (smart AEO instrumentation). |
| Unboxing / tripwire funnel | 45 | Manual checkout, fake countdown, empty testimonial (Defects 4 & 5). |
| Presentation funnel | 30 | No webinar or VSL. |
| Phone / high-ticket funnel | 15 | None. Nothing above $99/mo. |
| Funnel metrics | 50 | PostHog events wired; no funnel-stage conversion view. |

## EXPERT SECRETS — 66.4

| Chapter / Secret | Score | Evidence |
|---|:---:|---|
| Charismatic leader | 70 | Named founder with a real origin moment. |
| The Cause | 80 | "We're not building a sanctions API. We're building the compliance layer for autonomous commerce." |
| New Opportunity | 82 | Explicit old-way/new-way: banks, six-figure contracts, procurement cycles vs one curl. |
| Opportunity Switch | 76 | "Doesn't my payment provider handle this?" answered head-on. |
| Epiphany Bridge | 82 | test #47 — dated, specific, sensory. |
| Hero's Two Journeys | 58 | External journey strong; internal transformation thin. |
| Epiphany Bridge Script | 74 | Most beats present; "all is lost" underplayed. |
| Four Core Stories | 62 | Origin ✓, vehicle ✓, external-belief ✓, internal-belief thin. |
| **Big Domino** | **55** | The domino is "agents must screen before they pay" — but the number carrying it is stated **seven ways** and is **stale by two adjustments** (Defect 1). A domino resting on a wrong number falls over. |
| Stack Slide | 72 | Present on the homepage with a running total. |
| Three Secrets | 45 | Content is not structured as three secrets. |
| Trial / mini closes | 50 | Some micro-commitments; no yes-ladder. |
| **Teachable framework** | **85** | The 4-Gate Agent Payment Protocol™. Named, ownable, memorable, four steps, alliterative. This is the strongest single Brunson asset on the site. |
| Customer stories | 38 | Deliberately zero testimonials, stated honestly ("No invented quotes... their words go right here. Not before."). That is a defensible frame — but `/tripwire` breaks the promise with a dangling attribution and no quote. |

## TRAFFIC SECRETS — 49.1

| Chapter / Secret | Score | Evidence |
|---|:---:|---|
| Secret #1 — Dream customer | 80 | Well specified. |
| Secret #2 — Dream 100 (identified) | 78 | 75 targets documented. |
| Secret #3 — Hook, Story, Offer | 72 | Strong on-page; undermined by the number inconsistency. |
| Secret #4 — Work your way in | 22 | No evidence of outreach, guest posts, or podcast appearances. |
| Secret #4 — Buy your way in | 10 | Zero ad pixels, zero campaigns. |
| Secret #5 — Funnel Hub | 72 | The site is a proper hub. |
| Secret #6 — Follow the white rabbit | 30 | No omnipresence; single channel. |
| Secret #7 / #8 — Earned & organic | 45 | **246 sitemap pages → 3 clicks / 527 impressions / 28 days, avg position 41.2.** Blog stale since 2026-07-04. |
| Instagram / Facebook / Google / YouTube | 15 | Absent. |
| Podcast / conversation domination | 10 | Absent. |
| Affiliate army | 48 | `/partners/jv` — 50% recurring, swipe copy ready, zero partners recruited. |
| Cold traffic bridges | 35 | Some `/for/*` forks; no cold-traffic-specific bridge pages. |
| Owned / email | 70 | Now genuinely live. |
| Analytics | 62 | PostHog + AI-referral auto-capture. |
| **AEO / AI-search visibility** | **88** | llms.txt, llms-full.txt, agents.md, agent-card.json, mcp.json, openapi.json, `/agent`. Best in the portfolio. |

---

## Confirmed defects (evidence-backed)

### 1. The Big Domino number is stale and stated seven different ways — CRITICAL

The flagship fear-number appears in the source as:

| Figure | Occurrences |
|---|---:|
| `$356,000` | 24 |
| `$330,944` | 23 |
| `$356,571` | 14 |
| `$300,000` | 3 |
| `$330,000` | 1 |

(`$362,158` / `$362,000` are Kraken settlement figures — legitimately different, not part of this defect.)

The authoritative figure: OFAC's **Inflation Adjustment of Civil Monetary Penalties**,
90 FR (doc. 2025-00786), published 2025-01-15, Table 1 — the **IEEPA maximum civil
monetary penalty is $377,700** per violation, effective 2025-01-15. This is the most
recent OFAC CMP adjustment on the Federal Register as of today.

So every number on the site is not merely inconsistent, it is **understated by
$21,129 to $77,700**. `$330,944` tracks the 2022 adjustment; `$356,571` tracks 2023.

Brunson reading: the Big Domino must be one number, repeated until it is boring.
Seven numbers is zero numbers. Worse, on a *compliance* product, a customer who
quotes your penalty figure to their own counsel and finds it two adjustments out of
date stops trusting the screening too.

Additional inconsistency: `/about` says `$330,944` while the homepage says `$356,000`
— two different figures for the same claim, two clicks apart.

### 2. "Hourly sync" is false — the engine is on a 24-hour TTL

`compliance/osint.py` line 53: `_TTL = 24 * 3600`. `/health` returns
`"cache_ttl_hours": 24`. Yet the homepage trust bar states "**hourly** sync" and the
FAQ states "Synced **hourly** from the official US Treasury SDN list." Elsewhere the
site says "daily" (9 occurrences) — which is the true figure.

This sits in the trust bar, i.e. the one place a skeptical developer looks to decide
whether to believe the rest. Same failure class as the portfolio-wide trust-bar
fabrications already on record.

### 3. "OFAC/EU/UN/UK sanctions lists" — the EU, UN and UK lists are not screened

`compliance/osint.py` fetches exactly three sources, all OFAC:
`vile/ofac-sdn-list` (wallets), `treasury.gov/ofac/downloads/sdn.csv` (names), and the
GitHub release mirror. `/health` confirms: `"OFAC SDN: 947 wallets, 19218 names"`.

But the MCP tool description and `/pricing` both tell buyers the product screens
"against OFAC/EU/UN/UK sanctions lists," and `/pricing` states "All plans include
OFAC/EU/UN/UK data."

This is the most serious item in the audit and it is not really a marketing problem.
A customer relying on that sentence believes they are screened against EU consolidated,
UN consolidated and UK OFSI designations. They are not. (The separate claim of "16
embargoed jurisdictions per OFAC guidance" is fine — that is about country codes, and
it is accurate.)

### 4. `/tripwire` shows an attribution with no testimonial above it

```html
<div class="testimonial">
<div class="attr">- Agent Framework Author, San Francisco</div>
</div>
```

Renders as a bare dash-attribution. Most likely an earlier honesty sweep removed a
fabricated quote and left the byline. It still implies a customer who does not exist —
on a site whose homepage explicitly promises "No invented quotes."

### 5. `/tripwire` runs a fake 15-minute countdown

A `15:00` timer captioned "offer expires — one-time kit at this price" that resets on
every page load. Brunson uses urgency hard, but he uses *real* deadlines. A resetting
evergreen timer on a $7 kit whose checkout is a mailto link is the kind of thing that
costs more credibility than the $7 is worth.

### 6. `/data/*` returned HTTP 200 with the body "not found" — soft-404

Confirmed live on `/data/`, `/data/global-sanctions-statistics/`,
`/data/ofac-sdn-list/`. Genuine 404s elsewhere on the site return a correct 404, so
this was scoped to the `/data` prefix — a 200-status soft-404 is the version Google
indexes as a real page.

**Already being fixed by a concurrent session** (commit `f0bc02d`, plus a `COPY data/`
line added to the Dockerfile). Recorded here for completeness; not mine to fix.

### 7. `/pricing` carries none of the risk reversal the homepage does

The homepage offers a $10K legal-fee guarantee, "first 50 devs locked in at $19/mo
forever," and the value stack. `/pricing` — the page where the decision is actually
made — is a bare feature table with none of it. Brunson's rule is that the close
belongs where the money is, not one page upstream.

---

## Recommended fixes, in priority order

| # | Fix | Book / chapter | Effort |
|---|---|---|---|
| 1 | Unify every statutory-penalty reference to **$377,700**, cite the Federal Register rule, and keep Kraken figures untouched | Expert — Big Domino | M |
| 2 | Change "hourly sync" → "daily", matching the 24h TTL | DotCom — Q4 credibility | S |
| 3 | Cut EU/UN/UK from every screening claim, or ship those lists | Expert — trust | S |
| 4 | Delete the phantom `/tripwire` attribution | Expert — social proof | S |
| 5 | Remove the resetting countdown, or replace it with a real deadline | DotCom — unboxing funnel | S |
| 6 | Port the guarantee + scarcity + stack onto `/pricing` | DotCom — Secret #3 | M |
| 7 | Automate `/tripwire` checkout (it is currently a mailto) | DotCom — unboxing funnel | M |
| 8 | Add a rung above $99 | DotCom — Value Ladder | M |
| 9 | Resume publishing; work the Dream 100 | Traffic — #4 | L |

Items 1–6 are the ones that pay back immediately, because they are all credibility
defects on a product whose entire value proposition is *being trustworthy about
compliance*.

---

## Status at close of audit (2026-07-26, ~00:20)

A second agent session was rewriting this repo throughout the audit and deploying
on a ~90-second cadence (v374 → v392). It independently reached the same
conclusions on most of the above and shipped them live. Verified against the
running site at close:

| # | Defect | Status | Verified by |
|---|---|---|---|
| 1 | Penalty figure stale / 7 variants | **Fixed** — unified to `$377,700` with a Federal Register citation and a "where does this figure come from?" FAQ | 10 occurrences live on `/`, zero stale figures anywhere |
| 2 | "hourly sync" false | **Fixed (this session)** | 0 across 11 sampled live pages; `/health` `ttl=24h` now agrees with the copy |
| 3 | EU/UN/UK screening overclaim | **Fixed** | `OFAC/EU/UN/UK` gone; `/pricing` now says "screen the US Treasury OFAC SDN list, refreshed daily" |
| 4 | Phantom `/tripwire` testimonial | **Fixed** — replaced with an honest FAQ: "Nobody has bought it yet, so there is nothing honest to put here." | live |
| 5 | Fake 15:00 countdown | **Fixed** — timer removed (only dead CSS remains) | live |
| 6 | `/data/*` soft-404 (HTTP 200 "not found") | **Fixed** — `COPY data/` added to the Dockerfile | `/data/` serves real HTML |
| 7 | `/pricing` no risk reversal | **Fixed** — guarantee + objection handling + a path for non-buyers | 3 guarantee mentions live |

Items 8 and 9 from the table above (a rung above $99, and the Traffic work —
resume publishing, work the Dream 100, any paid traffic at all) remain open. They
are the whole of the remaining gap: Traffic scored **49.1** against DotCom's 61.3
and Expert's 66.4, and 246 pages currently return 3 clicks per 28 days.

Fixing every credibility defect on the page does not by itself produce a visitor.
