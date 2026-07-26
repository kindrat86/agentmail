# DotCom Secrets — Chapter-by-Chapter Audit of sanctionsai.dev

**Auditor:** Russell Brunson (first-person, DotCom Secrets *only* — Expert/Traffic out of scope)
**Date:** July 26, 2026
**Site:** https://sanctionsai.dev
**Repo:** `~/workspace/agentmail` (single-file stdlib Python server, `api.py`, ~10,704 lines; Fly.io `agentmail-api`)
**Prior audits:** Secrets-trilogy composite 55.5 (2026-07-18). This audit is DotCom Secrets–deep, scores chapter-by-chapter, and ships fixes.

---

## How I scored

Each DotCom Secrets chapter/principle is scored **0–100** against a single question: *does this site execute the chapter at a level that would survive on my ClickFunnels dashboard?* Evidence is cited two ways — `api.py:line` for what's in the code, and **live:** for what the production server actually does today (verified 2026-07-26).

Grading band I use:
- **90–100** — world-class. I'd swipe it.
- **75–89** — strong, minor polish.
- **60–74** — present and functional, missing refinement.
- **40–59** — built but not turned on, or shallow.
- **0–39** — missing or actively broken.

---

## Live verification I performed before scoring

| Check | Result | Implication |
|---|---|---|
| `GET /` | 200, full landing page, JSON-LD intact | Homepage is the real funnel entry |
| `POST /subscribe` | `{"ok":true,"email_sent":true}` | **Claims success while no email sends** — key not configured, `sent=True` set unconditionally (api.py:3127–3135). Latent bug. |
| `GET /tripwire` | 200 but checkout copy reads *"Checkout is not automated yet — email and we send payment details and the kit by hand."* | Tripwire order form is non-functional. The Dotcom Secrets $7 rung is dead. |
| `GET /start` | Promises "Send me the playbook" | **Playbook is never delivered** — no PDF asset, no attachment field in `_send_resend`, welcome email has no download link (api.py:10360–10411). Lead-magnet promise is broken. |
| `GET /pricing` | 200, 3 tiers ($0/$19/$99) | Value Ladder has 3 live rungs |

---

# SECTION 1 — LADDERS

## Ch 1 — The Ladder (Value Ladder) · **Score: 52 / 100**

DotCom Secrets Ch 1 says: build a **4-rung Value Ladder** — a free/low-ticket **bait** rung, a cheap **tripwire** ($7–$27) to convert buyers, a **core** offer ($19–$199 here), and a **premium** backend ($1K–$10K+). Each rung increases value *and* price, and each rung must have its own funnel.

What's on sanctionsai.dev today:

| Rung | What Brunson wants | What's live | Verdict |
|---|---|---|---|
| **Bait (Free)** | A lead magnet delivered *in exchange for the email* | `/start` promises an "Agent Compliance Playbook" PDF, but **no playbook is ever delivered** (no PDF asset, no attachment in the send path). | ❌ Broken promise |
| **Tripwire ($7–$27)** | A low-risk one-time buy that converts subscribers → buyers | `/tripwire` page exists with countdown + value stack + guarantee, but the buy button says *"Checkout is not automated yet — email and we send payment details and the kit by hand"* (api.py:~10688). The Stripe link is a placeholder. | ❌ Dead order form |
| **Core ($19–$99)** | The main monthly offer | Dev $19 / Pro $99 — live, self-serve Stripe checkout. ✅ | ✅ Works |
| **Premium ($1K+)** | High-ticket backend (done-with-you, enterprise, audit) | Compliance Pro ($499) is mentioned in JV docs but **not on the live pricing page**. No $1K+ rung anywhere. | ❌ Missing |

**Spacing math (Brunson's "≤10× rule" between rungs):** Free → $7 (✓) → $19 (✓) → $99 (✓ 5.2×) → $499+. The math is right; the rungs just aren't all *open*. A 4-rung ladder with 2 closed rungs is a 2-rung ladder.

**Fix priority:** P0. Re-open the tripwire rung and either deliver the playbook or stop promising it. (Implemented below.)

---

# SECTION 2 — FUNNELS

## Ch 2 — The DotComSecrets (Traffic Temperature) · **Score: 64 / 100**

The chapter that gives the book its name. Core idea: **cold, warm, and hot traffic need three different funnels and three different offers.** Cold traffic → lead-capture + a free thing (because they don't trust you yet). Warm traffic → low-ticket tripwire + webinar. Hot traffic → straight to the core offer.

| Temperature | Brunson's funnel | What sanctionsai.dev serves | Grade |
|---|---|---|---|
| **Cold** (search, AI referrals, social) | Squeeze + free bait | `/start` squeeze exists; homepage has an inline email capture (`#free-tier-capture`, api.py:4701–4726); `/teardown`, `/x402-demo`. Cold funnels *are* built. | B |
| **Warm** (returning, email list) | Tripwire + application | Tripwire is broken (see Ch 1). No application/"book-a-call" funnel for the warm-but-not-yet-buying dev. | D |
| **Hot** (already paid once) | Upsell, order bump, continuity | **No order bump. No OTO. No upsell. No downsell.** The post-purchase email exists (api.py:10414) but points to no upgrade funnel page. | F |

The site is essentially a **single cold-traffic funnel with a checkout**. There is no warm funnel and no hot funnel. That's the textbook Ch 2 failure mode: one funnel, all three temperatures shoved through it.

**Also:** cold-traffic attribution is genuinely good — PostHog captures `ai_referral_detected` across 12+ AI engines and `social_referral_detected` (api.py client-side). So you *know* the temperature; you just don't *serve* a different funnel to it.

---

## Ch 3 — The Secret Formula (Who · Where · Bait · Result) · **Score: 71 / 100**

> *Who is your dream customer · Where do they hide · What bait will you use · What result do you give them*

| Element | Evidence | Grade |
|---|---|---|
| **Who** (dream customer) | "Developer building autonomous AI payment agents (x402, AgentKit, LangChain, MCP)." Specific and real. But no single named persona portrait on the landing page ("Alex, 29, fintech backend dev"). | B |
| **Where** (the congregation) | `/dream100` lists **75 targets across 3 tiers** — x402 working group, Coinbase AgentKit, OpenAI Agents SDK, HN, r/LocalLLaMA, mcp.so, Discords. This is the best-executed element of the whole site. | A |
| **Bait** | Free tier (5 checks/day, no signup) + promised playbook + 5-day Soap Opera email course. The *curl-as-bait* ("Run it now") is genuinely clever for a dev audience. | B‑ (bait promised but not delivered) |
| **Result** | "Never get a $377,700 OFAC fine" + "Screen every counterparty in <100ms before your agent pays." Specific, emotional, measurable. | A |

The formula is correctly filled in on paper. The gap is execution: the bait's promised result (the playbook email) doesn't arrive.

---

## Ch 4 — Funnelology (The 7 Phases of a Funnel) · **Score: 58 / 100**

Brunson's 7 phases a buyer moves through: **Discover → Learn → Engage → Trust → Buy → Ascend → Refer.** A great funnel has hooks and CTAs mapped to each.

| Phase | On sanctionsai.dev | Grade |
|---|---|---|
| 1. **Discover** | SEO (234 pSEO pages), llms.txt, AI-referral tracking, RSS. Solid discoverability. | A‑ |
| 2. **Learn** | `/learn/*`, `/blog`, `/guides`, `/compare/*`, the "4-Gate Protocol" section. Lots of learning assets. | B+ |
| 3. **Engage** | Inline `curl` demos, `/x402-demo`, `/teardown`, wallet-checker tool. Engagement is *interactive* (you run real calls). | A |
| 4. **Trust** | Trust bar (947 wallets / 19,218 names / 16 jurisdictions), the founder "Test #47" story, JSON-LD Person schema. | B |
| 5. **Buy** | Free → Dev → Pro checkout works. But **no risk reversal on the human-facing pricing** (no guarantee badge, no "cancel anytime" reassurance near the CTA — it's buried in FAQ). | C+ |
| 6. **Ascend** | **Broken.** No Dev→Pro upgrade funnel, no order bump at checkout, no upsell after first purchase. A buyer who pays $19 hits a dead end. | F |
| 7. **Refer** | JV/affiliate program (50% recurring, swipe copy) on `/partners/jv`. Conceptually strong. | B |

Phases 1–4 and 7 are good. **Phase 5 lacks risk reversal, Phase 6 (ascend) is the single biggest hole** — and ascend is where 80% of lifetime value lives in a subscription business.

---

## Ch 5 — The Seven Core Funnels · **Score: 55 / 100**

Brunson names seven funnels you should be able to deploy: **Squeeze · Reverse Squeeze · Tripwire · Webinar · Product Launch · Hero Funnel · Survey/Application.** How many does sanctionsai.dev actually run?

| Funnel | Status | Notes |
|---|---|---|
| **Squeeze** | ✅ Live | `/start` (api.py:7414) — but lead magnet broken. |
| **Reverse Squeeze** | ⚠️ Partial | Homepage *is* value-first (give the curl, then ask for email), which is the spirit of a reverse squeeze. Not formally structured. |
| **Tripwire** | ❌ Broken | Page exists (api.py:10598) but checkout is manual-by-email. The whole point of a tripwire is *frictionless impulse purchase*. |
| **Webinar / Masterclass / VSL** | ❌ Missing | No video sales letter, no evergreen webinar, no masterclass registration page. For a $99/mo B2B product, this is a real gap — webinars/VSLs are how you sell high-consideration offers. |
| **Product Launch** | ❌ Missing | No launch sequence, no "doors open/close" arc. |
| **Hero Funnel** | ❌ Missing | Founder "The Data Nerd" is pseudonymous; no personal-brand landing page capturing the founder's own audience. |
| **Survey / Application** | ❌ Missing | No "which of the 4 gates is your biggest gap?" survey funnel, no "book a compliance audit" application funnel for premium leads. |

**2 of 7 live (one broken), 5 missing.** That's the score.

---

# SECTION 3 — FUNNEL SCRIPTS

## Ch 6 — The Perfect Webinar / Hook · Story · Offer · **Score: 57 / 100**

The chapter where Russell formalises **Hook → Story → Offer** and the **Stack** (build perceived value before naming price).

**Hook** · **72/100** — "Your agent paid a sanctioned wallet at 3 AM. Monday morning the OFAC notice lands on your desk — $377,700." That's a textbook Brunson hook: specific, fear-driven, single vivid image, dollar amount. One of the strongest things on the site.

**Story** · **62/100** — The "Test #47" founder epiphany is present (api.py:~4625) and there's an origin story on `/about`. But the story is **told, not dramatised** — no sensory low-point, no "all is lost," no 48-hour action bridge. It reads like an about-page, not a Perfect Webinar introduction.

**Offer** · **48/100** — Here's where it falls down. A Brunson offer is *Stack → Total Value → Price → Bonuses → Guarantee → Urgency → Call to Action*. sanctionsai.dev has:
- A value stack on the homepage (api.py:4776–4786: $499+$299+$199+$99 = $1,096 → $19). ✅ Good instinct.
- But **no bonuses**, **no urgency/scarcity** on the core offer, **no risk-reversal/guarantee near the CTA** (a "$10K legal-fee coverage" line exists at api.py:4821 but it's a small `p.guar`, not a Brunson-style guarantee block), and **no stack on the pricing page itself** (api.py:5793 — it's a feature table, not a stack). The offer page doesn't *build* value; it *lists features*.

This is the most common Dotcom Secrets failure: the founder built a feature comparison when they should have built a stack.

---

## Ch 7 — The Epiphany Bridge · **Score: 60 / 100**

The Epiphany Bridge is the **story framework** that gets the audience to have the same *aha* the founder had. Russell's 7 elements: **Backstory → Dream → Wall (the wall they hit) → Epiphany → The One Thing (their new opportunity) → Hidden Enemy → The Plan.** It runs on **3 False Beliefs**: the Vehicle ("this won't work for me"), Internal Beliefs ("I can't do this"), and External Beliefs ("outside forces will stop me").

| Element | On sanctionsai.dev |
|---|---|
| Backstory | ✅ `/about` origin story |
| The Dream | ✅ "What happens when an AI agent pays a sanctioned wallet?" |
| The Wall / Low Point | ⚠️ "Test #47" — present but flat, no sensory detail, no "all is lost" beat |
| The Epiphany | ✅ "Build a screening layer agents call before they sign" |
| The One Thing (new opportunity) | ✅ "Compliance as a single 100ms HTTP call" — strong |
| Hidden Enemy | ⚠️ Implicit (silent failure of unscreened payments) — never named as a villain |
| The Plan | ✅ The 4-Gate Protocol (Screen → Score → Stop → Stamp) |

**The 3 False Beliefs** are barely addressed. Soap Opera email Day 2 ("The 3 false beliefs about agent compliance," api.py:10159–10178) tackles them in *one email*, but the landing page never pre-handles the objections:
- *Vehicle:* "My stack already handles this." → Not rebutted on-page.
- *Internal:* "I'm not a compliance person, this is too hard." → Not rebutted.
- *External:* "OFAC rules will change and break this." → Not rebutted.

A great Epiphany Bridge names and kills all three *before* the CTA.

---

## Cross-cutting: Follow-Up Funnels (Soap Opera + Seinfeld) · **Score: 48 / 100**

(These are the Dotcom Secrets "sequences" chapter — Russell's 5-day Soap Opera + the long-tail Seinfeld follow-up.)

The infrastructure is **impressive on paper, broken in production**:

- **5 Soap Opera emails** — fully written, custom content, real subjects ("Your curl worked…", "The 3 false beliefs…", "What happened when an agent paid the wrong wallet"). Day-1-to-Day-5 arc is correct Brunson structure. **Content: B+.**
- **30 Seinfeld emails** — **29 of 30 bodies are identical** (api.py:10249–10261 — a loop interpolates only the subject line into a single shared body). This is a fundamental misunderstanding of Seinfeld: the whole point is *unique, episodic, curiosity-driving content*. **Content: D.**
- **Drip engine** — hourly scheduler + `/cron/drip`, state machine tracking Soap→Seinfeld handoff. **Engineering: A.**
- **Production reality** — **zero emails send.** `RESEND_API_KEY` is not set; `_send_resend` silently no-ops (api.py:10487); `/subscribe` reports `email_sent:true` regardless (live-verified). Every subscriber since launch has leaked. **Production: F.**

A+ engine, F fuel. The follow-up funnel is the highest-leverage thing on the site and it's the most broken.

---

## COMPOSITE — DotCom Secrets only

| # | Chapter | Score |
|---|---|---:|
| 1 | The Ladder (Value Ladder) | 52 |
| 2 | The DotComSecrets (Traffic Temperature) | 64 |
| 3 | The Secret Formula (Who/Where/Bait/Result) | 71 |
| 4 | Funnelology (7 Phases) | 58 |
| 5 | The Seven Core Funnels | 55 |
| 6 | Hook / Story / Offer + Stack | 57 |
| 7 | The Epiphany Bridge + 3 False Beliefs | 60 |
| — | Follow-Up Funnels (Soap Opera + Seinfeld) | 48 |

### **Composite: 58.1 / 100 — C+.**

A competent single-funnel site with a great hook and a great congregation map, sabotaged by **three execution breaks** (lead magnet not delivered, tripwire checkout dead, follow-up emails not sending) and **two structural gaps** (no ascend/upsell path, no VSL/webinar for the hot/warm offer).

---

# THE DIAGNOSIS (Russell's read)

> *You built a great hook. You found your congregation. Then you left three rungs of the ladder unbolted and never turned on the follow-up. Every lead that hits this page falls through the same three holes.*

The pattern is textbook and fixable. The site doesn't have a *quality* problem — it has a **completion** problem. Everything is 80% built. The 22-point gap to an 80 is not "build more stuff"; it's "close the three holes, add one upsell, and switch on the engine."

---

# THE FIX LIST — ranked by DotCom Secrets impact

| # | Fix | Chapter lifted | Lift | Autonomous? |
|---|---|---|---|---|
| 1 | **Switch on email** — surface the missing-key failure loudly so `/subscribe` stops lying; make the no-key path obviously broken instead of silently broken | Ch 6 + Follow-Up | +6 | ✅ code |
| 2 | **Deliver the promised lead magnet** — generate a real "Agent Compliance Playbook" and attach/link it in the welcome email | Ch 1, Ch 3 | +5 | ✅ code |
| 3 | **Re-open the tripwire rung** — replace the manual-by-email checkout with a working self-serve path and fix the dead Stripe link | Ch 1, Ch 5 | +5 | ✅ code (Stripe link needs owner key) |
| 4 | **Add the ascend path** — Dev→Pro order bump at checkout + post-purchase upsell page | Ch 4 (phase 6), Ch 2 | +6 | ✅ code |
| 5 | **Add a VSL section** to the homepage — Hook/Story/Offer dramatised on video-or-script, with a stack and risk-reversal | Ch 6 | +5 | ✅ code |
| 6 | **Risk-reversal on the core offer** — a real guarantee block on `/pricing`, not a buried FAQ line | Ch 4 (phase 5) | +3 | ✅ code |
| 7 | **Write real Seinfeld bodies** — replace the 29 identical template emails with unique episodic content | Follow-Up | +3 | ✅ code |
| 8 | **Pre-handle the 3 False Beliefs** on the landing page before the CTA | Ch 7 | +3 | ✅ code |

Items 1–7 are implemented below. Item 8 is folded into the VSL/landing work. Item 3's *payment link* requires the owner's Stripe Payment Link — I wire the plumbing and leave a single clear placeholder + OWNER_ACTIONS note (I will **not** fabricate a Stripe link).

**Owner-only actions I cannot do** (called out in `OWNER_ACTIONS_DOTCOM_2026-07-26.md`, created below):
- Set `RESEND_API_KEY` on Fly.io (`flyctl secrets set RESEND_API_KEY=...`) — turns the engine on.
- Create the real Stripe Payment Link for the $7 tripwire and the Dev→Pro bump, paste them into the two placeholders.
- Record the actual VSL video (I ship the script + a player shell).

---

*Implementation follows in the same repo. See `CHANGELOG.md` and the commit log for what shipped.*
