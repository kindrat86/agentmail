# DotCom Secrets Audit — sanctionsai.dev

**Framework:** DotCom Secrets (Russell Brunson, 2nd ed.) — all 28 Secrets
**Date:** 2026-07-25
**Site:** https://sanctionsai.dev · **Repo:** `~/workspace/agentmail` · **Host:** Fly `agentmail-api`
**Method:** live production pages (not repo source), live endpoint probes, Stripe checkout traversal, Fly secret inventory, local instance for fixes

**Score: 47 / 100** across all 28 Secrets (was ~40 before this session's fixes).
**55 / 100** across the 23 Secrets that apply to a self-serve developer API.

---

## Section One — Ladders and Funnels (avg 58)

| # | Secret | Score | Evidence |
|---|---|:--:|---|
| 1 | The Secret Formula | **78** | Q1 dream customer is unusually sharp: "You are shipping your first x402 payment agent this month." Q2 congregation documented in `/dream100` (75 named targets, 3 tiers). Q3 bait was broken and is now real (`/playbook`). Q4 result is concrete and measurable: no $377,700 fine, <100 ms, 947 wallets. |
| 2 | The Value Ladder | **52** | Free (5/day) → $7 kit → $19 Dev → $99 Pro, then nothing. $19→$99 spacing is fine. Two structural faults: the $7 rung **cannot be bought** (mailto checkout, no Stripe price), and there is no rung above $99 at all — the $499 tier was removed and never replaced. |
| 3 | From a Ladder to a Funnel | **58** | Free tier has a funnel (home → checker → opt-in). Dev has one (pricing → Stripe → key page → ascension, new today). Pro is now reachable from the post-purchase page. The $7 rung has no funnel and no traffic. No downsell exists anywhere on the ladder. |
| 4 | Find Your Dream Customers | **55** | `/dream100` is a genuinely good artifact — 75 researchable targets (x402 working group, Coinbase AgentKit, OpenAI Agents SDK, named subreddits and Discords) plus a JV page at 50% recurring with six swipe templates. But this Secret is about *working your way in*, and there is no evidence of a single outreach touch. A list is step one of ten. |
| 5 | The Three Types of Traffic | **48** | **Owned:** real — list + Soap Opera + Seinfeld, and email genuinely sends (verified `email_sent:true`). **Earned:** substantial — ~250+ pSEO pages, blog, `llms.txt`, AI-crawler rules, real GSC impressions. **Controlled (paid):** zero. No ad spend, no retargeting pixel. The controlled→owned conversion loop that the chapter is built around does not exist. |

## Section Two — Your Communication Funnels (avg 67)

| # | Secret | Score | Evidence |
|---|---|:--:|---|
| 6 | The Attractive Character | **66** | Strong and consistent: "Maryan, founder", the reluctant-hero frame ("I didn't want to build this"), a real parable (test #47 sent USDC to a wallet he didn't recognise), and clear polarity ("Chainalysis and Elliptic exist. They are not for you"). Capped by having no face, no voice, no video, and a single channel. |
| 7 | Soap Opera Sequence | **72** | Five days, fully written, each with a distinct job (epiphany → mechanism → enemy → integration → close). Fires on a real hourly scheduler. Was dead in July (`RESEND_API_KEY` unset); now configured and sending. The homepage now advertises the exact five subjects it delivers. |
| 8 | Daily Seinfeld Sequence | **62** | 30 real subject lines with bodies, on the same drip. Deducted because it terminates: after day 30 the relationship goes silent. Seinfeld is meant to be indefinite. |

## Section Three — Funnelology (avg 54)

| # | Secret | Score | Evidence |
|---|---|:--:|---|
| 9 | Reverse Engineering a Funnel | **40** | `/vs/*` and `/alternatives-to/*` pages cover five competitors, but these are comparison-SEO pages, not funnel hacks. No swipe file, no ad-library research, no evidence that any proven funnel in this niche was bought and modelled. |
| 10 | The Seven Phases of a Funnel | **50** | Temperature is not differentiated — cold search traffic lands on the same page as a warm referral. Pre-frame bridge is absent. Qualify-subscribers and qualify-buyers both work. Hyperactive-buyer identification is built but switched off (bump unconfigured). **Age & ascend now exists** (new today); it did not before. Changing the selling environment (phone/email escalation) does not exist. |
| 11 | The 23 Building Blocks | **52** | Present: squeeze, lead magnet, delivery page, sales page, order form, OTO, membership/access page, affiliate page, onboarding email, win-back. Missing: downsell, cart-abandon recovery (`cancel_url` dumps to `/pricing?cancelled=1` with no follow-up), VSL, webinar, application, survey. Roughly 11–12 of 23. |
| 12 | Frontend vs. Backend | **48** | The subscription itself is legitimate continuity, which counts. But the backend stops at $99 — no services, no audit product, no enterprise tier. For a compliance product sold to fintechs, that is where the money is. |
| 13 | The Best Bait | **80** | The strongest chapter after today. The free tier (5 checks/day, no signup, no key) is near-perfect bait for this market — it is the product, self-serve, instantly. `/playbook` now backs it with content that attracts exactly the person who wires payments. **This scored ~15 this morning**, because the advertised bait did not exist. |

## Section Four — The Funnels and Scripts (avg 38)

| # | Secret | Score | Evidence |
|---|---|:--:|---|
| 14 | Lead / Squeeze Funnels | **55** | `/start` works, single field plus attribution capture, and now delivers instantly. The large miss: ~250 earned-traffic pages carry **no lead capture** beyond a footer newsletter box. No content upgrades, no exit intent. |
| 15 | Unboxing Funnels | **45** | Order bump is coded (`audit_plus`, $9/mo, 180-day retention) but `STRIPE_PRICE_BUMP_AUDIT` is unset, so it cannot be sold. OTO now exists. The $7 tripwire is manual-checkout and orphaned — nothing links to it. |
| 16 | Presentation Funnels | **20** | No webinar, no VSL, no video anywhere on the site. `/teardown` is the closest thing. For a developer tool the natural analogue — a four-minute "watch me wire this in" — does not exist. |
| 17 | Phone Funnels | **12** | No application form, no "book a compliance review", no enterprise path, no way for a fintech with budget to talk to a human. The most obvious unclaimed revenue on the site. |
| 18 | Curiosity-Based Headlines | **78** | Consistently good and specific: "Your agent paid a sanctioned wallet at 3 AM", "One OFAC fine starts at $377,700. Screening starts at $0." Curiosity plus a number, which is the formula. |
| 19 | Who / What / Why / How | **74** | The homepage answers all four cleanly: x402 agent developers / one HTTP call / the liability is yours not the protocol's / four gates. |
| 20 | Star, Story, Solution | **72** | Maryan → test #47 → agentmail, told consistently on the homepage, the About page and in the email sequence. Coherent across surfaces, which is rarer than it sounds. |
| 21 | OTO Script | **58** | Built today; was **absent entirely**. Structurally correct (single decision, real product, stated value gap) but deliberately soft-closed — "you do not need to decide now" — which Brunson would push harder on. Held back on purpose: the buyer has owned the product for eleven seconds. |
| 22 | Perfect Webinar | **8** | Not attempted. |
| 23 | Product Launch | **15** | No launch sequence, no content ramp, no launch event. The site has been continuously live with no launch moment. |
| 24 | Four-Question Close | **10** | No sales conversation exists to close. |
| 25 | Setter / Closer Scripts | **8** | No sales team, no calls. Arguably N/A for self-serve; scored low rather than excluded because Secret 17 shows the phone path is a real gap, not an irrelevance. |

## Section Five — Building Your Funnels (avg 34)

| # | Secret | Score | Evidence |
|---|---|:--:|---|
| 26 | One Offer, One Funnel | **35** | The clearest failure on the site. ~250+ pages across a dozen families (`/for`, `/vs`, `/best`, `/alternatives-to`, `/countries`, `/checklists`, `/glossary`, `/penalties`, `/guides`, `/programs`, `/designations`, `/sanctioned-addresses`), plus a leaderboard, a teardown, a research paper, a Dream 100 page, a JV page, a tripwire and a squeeze page — supporting **one $19 product with no customers**. This chapter says get one funnel to work before building the second. |
| 27 | Fill Your Funnel | **30** | Real GSC impressions but very low clicks; no paid traffic; Dream 100 unworked; no partner activated. The funnel is better built than it is fed. |
| 28 | The Funnel Audit | **38** | PostHog is installed with CTA events, and periodic audit documents exist in-repo. But no funnel-level conversion rate is measured anywhere — visitor → opt-in → checkout → paid is not instrumented end to end, and there is no A/B test infrastructure. You cannot audit what you do not count. |

---

## What was fixed and deployed today (Fly v382)

1. **The bait did not exist.** `/start` traded email addresses for a "Free PDF: 7 patterns" that was never written; the welcome email delivered none, and its subject line ("Your agentmail API key is ready") went to free opt-ins who have no key. Built `/playbook` — seven patterns with runnable code — delivered instantly on submit and linked from the email. Also removed a privacy leak: the opt-in redirect carried the subscriber's address in the query string.
2. **The value stack was fabricated.** $499/$299/$199/$99 per tool → "$1,096 total monthly value", anchors nobody was ever charged. Replaced with the site's own published price: 10,000 checks at the $0.05 x402 rate is $500; Dev bundles the same 10,000 for $19. Both verifiable on the site. Also fixed in two dormant email generators.
3. **The post-purchase page was a dead end.** An unbranded white page with a key on it, at the highest-intent moment in the funnel. Rebuilt with a one-paste first check, the playbook handoff, the guarantee, and a real Dev→Pro ascension. Also fixed a tier-label mismatch that showed buyers "Team" for a plan sold as "Pro".
4. **The money page had no conversion blocks.** Added risk reversal, five objection answers, and a path for readers who are not buying. The order bump now renders only when Stripe can actually charge for it.
5. **`/tripwire` honesty defects.** An orphaned testimonial attribution left behind when a fabricated quote was removed, a 15:00 countdown that reset on every page load, and a "$115 total value" of invented anchors. All removed.
6. **The guarantee was void on its own terms.** The headline $10,000 legal-fee promise was cancelled by Terms §5, which disclaimed liability for "legal fees". Published `/guarantee` with scope, exclusions and claim process, and carved it out in Terms §5a.

## Owner actions — cannot be done autonomously

| Action | Why it is yours | Unblocks |
|---|---|---|
| Create a Stripe price for the $7 kit, set it in `TIERS` | Financial action | Secret 2 — the missing tripwire rung |
| `flyctl secrets set STRIPE_PRICE_BUMP_AUDIT=price_...` | Financial action | Secret 15 — the bump is built and gated, it appears by itself once set |
| Legal review of `/guarantee` and Terms §5a | Commits the business to a capped payout | Secret 11 — the risk reversal |
| Decide on a high-ticket rung and a phone/application path | Business model decision | Secrets 12, 17 — the largest unclaimed revenue |
| Authorise any paid traffic budget | Spend decision | Secret 5 — controlled traffic |

## Deliberately not done

No testimonials were invented, no value anchors fabricated, no Stripe prices created, and no rating schema added. The site's own line — "No invented quotes. These numbers are live right now" — is the correct policy and was applied to every change above.

## The three things that would move the score most

1. **Stop building pages** (Secret 26). One funnel, fed properly, until it converts one customer.
2. **Put lead capture on the 250 pages that already get traffic** (Secret 14). The earned traffic exists and is currently converting into nothing.
3. **Build the rung above $99** (Secrets 2, 12, 17). A "we audit your agent's payment path" engagement, sold by application, is the natural top of this ladder and does not exist.
