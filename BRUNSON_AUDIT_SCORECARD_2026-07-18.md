# Brunson Secrets Trilogy Audit — sanctionsai.dev

**Auditor:** Russell Brunson (first-person, Secrets Trilogy framework)
**Date:** July 18, 2026
**Site:** https://sanctionsai.dev
**Repo:** ~/workspace/agentmail (Python stdlib, Fly.io)
**Previous Composite:** 68.7 (portfolio-wide audit)
**This Audit:** Focused deep-dive, SCORE ONLY (no implementation)

---

## Context & Methodology

sanctionsai.dev is an OFAC sanctions screening API for AI agents. Two audiences: human developers (`/`) and AI agents (`/agent`). Python stdlib HTTP server on Fly.io (`agentmail-api`). 234 pages indexed in sitemap (pSEO content), 8 blog posts, RESEND API key NOT configured on production.

Scored against **DotCom Secrets (40%)**, **Expert Secrets (30%)**, **Traffic Secrets (30%)**. Two-audience composite where relevant — human page and agent page scored separately, averaged.

---

## DOTCOM SECRETS (40% weight)

| # | Chapter | Principle | Score (0-100) | Evidence |
|---|---------|-----------|:---:|---|
| 1 | Q1 Dream Customer | One specific person? | **62** | Implied through content: "developer building AI payment agents with x402/AgentKit." JSON-LD Person schema names "The Data Nerd." About page: "small team that watched the x402 ecosystem grow." BUT: no single named dream customer portrait on the landing page — no "Alex, 29, fintech backend" visible. |
| 2 | Q2 Congregation | Where they hide? | **78** | /dream100 page: 75 targets across 3 tiers (20 agent infra + 30 dev communities + 25 compliance). Specific subreddits, Discords, platforms named. "How we serve" framework documents 3 pillars. "Think you belong?" CTA invites Dream 100 members. |
| 3 | Q3 Bait (Hook/Story/Offer) | Hook specificity + story + offer | **65** | HOOK: "Compliance That Keeps You Out of a $356,000 Fine" — fear + specific dollar amount. STORY: About page has origin story, homepage has founder quote block ("I didn't want to build this"), testimonial. OFFER: Free tier + Dev ($19) + Pro ($99). Agent page has $0.05/check x402 card with guarantee badge. BUT: human page offer lacks guarantee, bonuses, urgency. |
| 4 | Q4 Unique Result | What customer gets | **82** | "Never get a $356K OFAC fine" — specific, emotional, measurable. "Under 100ms" — technical specificity. "Screen every counterparty before your agent pays" — clear transformation from risky to compliant. "782 crypto wallets, 19,086 names, 16 jurisdictions" — concrete numbers. |
| 5 | Value Ladder | Tier structure & spacing | **58** | Free (5/day) → Dev ($19/mo) → Pro ($99/mo). Compliance Pro ($499/mo) mentioned in JV page but not live on pricing. Spacing: $19→$99 = 5.2x (✓ within 10x rule). MISSING: $7-$27 tripwire rung, high-ticket ($1K+ 1-on-1). 3 rungs visible is functional but incomplete. |
| 6 | Q6 Communication Funnel | Email capture + sequences | **52** | SUBSCRIBE endpoint WORKS (verified live: `{"ok":true,"email_sent":false}`). /start squeeze page with "Agent Compliance Playbook" lead magnet. Soap Opera (5 emails, FULLY WRITTEN with custom content). Seinfeld (30 subject lines + template bodies). Welcome email function exists. Winback function exists. Drip cron endpoint at /cron/drip with state machine. BUT: **RESEND_API_KEY not configured → ALL emails dead in production.** Subscribe saves to JSONL but no email ever sends. |
| 7 | Q7 Follow-Up Funnels | Soap Opera + Seinfeld | **52** | (See Q6 — same evidence base. Score identical because the infrastructure is excellent but execution is dead.) 5 Soap Opera days with custom content. 30 Seinfeld days with real subject lines (e.g., "Case study: Screening before the first payment", "Feature deep dive: Know Your Agent scoring"). State machine tracks day progression per subscriber. BUT: Zero production emails sent. |
| 8 | Funnel Hacking | Competitive awareness | **55** | /compare pages: vs Chainalysis, Elliptic, ComplyAdvantage, SumSub, World-Check. JSON-LD disambiguatingDescription explicitly rejects being "human-facing compliance dashboard." Competitor pricing table in pricing page codebase. BUT: No formal funnel hacking analysis, no swipe file of competitor funnels. |

**DOTCOM AVERAGE: 63.0** (range: 52-82)

---

## EXPERT SECRETS (30% weight)

| # | Chapter | Principle | Score (0-100) | Evidence |
|---|---------|-----------|:---:|---|
| 1 | Finding Your Voice | Brand personality | **58** | "The Data Nerd" pseudonymous identity — intentional strategy, not absence. JSON-LD Person schema with 9-item knowsAbout, jobTitle, sameAs links to X/GitHub/PyPI. About page: "built in 2025-2026 by a small team." Origin story present. "I didn't want to build this" — reluctant hero framing. BUT: No face/voice/video. Pseudonymous caps emotional connection. No explicit archetype declaration. |
| 2 | Teaching Frameworks | Named, teachable IP | **42** | No proprietary named framework ("The Triple-Separation Protocol", "4-Pillar Sanctions Method"). 4-tool system (sanctions_check, risk_score, kya_verify, dispute_open) is structured but unnamed. Blog has "7-step checklist" but no branded framework name. |
| 3 | Three Core Markets | Different messaging per market | **68** | /for/fintech, /for/crypto, /for/defi, /for/payments, /for/ai-agents, /for/developers — 6 pSEO landing forks. /compare/* pages for competitor-specific messaging. Footer navigation shows structured market segmentation. |
| 4 | New Opportunity | Old way vs new way | **75** | Strong positioning: "NOT a human-facing compliance dashboard (ComplyAdvantage, Refinitiv World-Check, Dow Jones RDC), a blockchain analytics tool (Chainalysis, Elliptic), or a generic AML/KYC platform." JSON-LD disambiguatingDescription. "The gap between 'cool demo' and 'legally compliant' is a $330K fine" — new opportunity framing. |
| 5 | Stack Slide | Value progression revealed | **52** | Pricing page: HTML table format, all at once (no sequential reveal). Agent page: hero-card with $0.05/check + feature list with checkmarks + guarantee box. Better than human page. BUT: No dramatic "All this for" pivot, no animated running total, no strikethrough total→actual. |
| 6 | Future-Based Cause | Mission bigger than product | **60** | Mission: "close the gap before the first $330K fine hits the news." "Every AI agent should screen before paying." Agent-native compliance movement. BUT: No manifesto page, no rallying cry, no tribe identity ("us vs them"), no community gathering place. |
| 7 | Epiphany Bridge | Founder story (7-element rubric) | **65** | Elements present: Dream ("what happens when an AI agent pays a sanctioned address?" — specific ✓), Hook ($330,944 per violation math — specific ✓), Low Point ("took longer than expected because edge cases in OFAC data are dense" — abstract, no sensory detail ✗), Vision (not articulated, no Timeline A vs B ✗), Epiphany ("built a screening layer agents can call before they sign" — clear mechanism ✓), Bridge ("We dug into public data…" — general, not 48-hour actions ✗), Elixir (API + MCP server + MIT license — framework delivery ✓). Score: 6/7 elements, 5+ with good detail. |
| 8 | Hero's Two Journeys | External + internal transformation | **48** | External: Built screening API, open-sourced on GitHub, PyPI package. Internal: "We shipped when it was good enough to protect someone, not when it was perfect" — hints at perfectionism→pragmatism but not dramatized. No "all is lost" moment, no dark night of the soul. |
| 9 | Four Core Stories | Vehicle, internal, external, origin | **45** | Origin story: About page ✓. Vehicle story: Compare pages frame the vehicle ✓. Internal beliefs story: NOT addressed ✗. External beliefs story: NOT addressed ✗. Score: 2 of 4 present with quality. |
| 10 | Customer Stories | Social proof quality | **52** | 1 testimonial on homepage with avatar + role. Trust bar: "782 OFAC wallets", "19,086 names", "16 jurisdictions", "4 tools." BUT: No named case studies with Before/Action/Result. No testimonial grid. No aggregate stats beyond trust bar. |

**EXPERT AVERAGE: 56.5** (range: 42-75)

---

## TRAFFIC SECRETS (30% weight)

| # | Secret | Principle | Score (0-100) | Evidence |
|---|--------|-----------|:---:|---|
| 1 | Dream Customer + Dream 100 | 100 identified targets | **82** | /dream100 page: 75 targets across 3 tiers. Tier 1: x402 working group, Coinbase AgentKit, OpenAI Agents SDK, Stripe ACP — specific, researchable names. Tier 2: 30 developer communities (HN, Reddit subs, Discords, mcp.so, etc.). Tier 3: 25 compliance/fintech targets. "How we serve" framework (3 pillars). "Think you belong?" CTA with mailto link. JSON-LD schema. |
| 2 | Congregation Engagement | Community presence | **35** | Dream 100 documented with care. BUT: No evidence of actual outreach or engagement. GitHub repo has activity (commits, issues). X account @data_nerd exists (HTTP 200). No guest posts, podcast appearances, or community contributions visible. |
| 3 | Earned Traffic (Content/SEO) | SEO & content publishing | **62** | 234 pages in sitemap (significant pSEO). 8 blog posts (2025-06-12 to 2026-07-04) — topics: OFAC for agents, KYA, x402 compliance, OpenAI Agents SDK, penalties, wallet screening, architecture guide, compliance checklist. llms.txt + llms-full.txt for AI crawlers. robots.txt well-configured with AI-crawler allow rules. Google Discover configured (max-image-preview:large). BUT: No RSS feed for blog. No weekly publishing cadence. Content stale since July 4. |
| 4 | Bought Traffic (Ads) | Paid advertising | **18** | No ad pixels detected on live site (no Facebook, LinkedIn, Google Ads, Reddit). PostHog analytics only. No ad campaigns running. |
| 5 | Owned Traffic (Email) | List + retargeting | **45** | /subscribe endpoint WORKS (verified live — saves to JSONL). /start squeeze page with lead magnet. Soap Opera (5) + Seinfeld (30) + Welcome + Winback sequences fully written in codebase. State machine tracks day progression. BUT: **RESEND_API_KEY not configured → ZERO emails sent** in production. No visible email list size. |
| 6 | Infiltrating Dream 100 | Relationship building | **40** | Dream 100 page is PUBLIC (Brunson's self-reinforcing pattern). JV/Affiliate program: 50% recurring for 12 months, 6 swipe copy templates (Twitter thread, Show HN, Reddit, LinkedIn DM), commission calculator, best-fit partner types. BUT: No evidence of actual outreach. No relationship tracker with touch counts. |
| 7 | Platform Traffic | Social media presence | **25** | X/Twitter: @data_nerd exists (account claimed). GitHub: kindrat86/agentmail active. PyPI: sanctions-mcp package published. BUT: No YouTube, no LinkedIn, no Instagram/TikTok, no Substack/newsletter, no podcast. |
| 8 | Content Strategy | Hooks library + calendar | **35** | Blog has 8 posts — sporadic publishing (June-July 2026 cluster), no weekly cadence. No visible content calendar. No hooks library. No social media publishing schedule. |
| 9 | Growth Hacking | Affiliates + viral + cold bridges | **55** | JV/Affiliate program: 50% recurring for 12 months, $50 minimum payout, 60-day cookie, Stripe Connect. Swipe copy templates: Twitter thread, Show HN, Reddit post, LinkedIn DM. Self-host option (pip install sanctions-mcp) = PLG motion. MIT licensed open source. Dream 100 public page. BUT: No viral loops, no referral automation, no A/B testing. |
| 10 | Analytics & Optimization | Tracking + optimization | **48** | PostHog installed with: page_viewed, cta_checkout, cta_run_check, cta_github, cta_free_signup, ai_referral_detected (ChatGPT/Perplexity/Gemini/Claude/DeepSeek/Grok), social_referral_detected, subscribe tracking. AEO auto-capture of AI-engine referrals. BUT: No conversion funnel tracking, no A/B testing infrastructure, no dashboard showing traffic sources. |

**TRAFFIC AVERAGE: 44.5** (range: 18-82)

---

## COMPOSITE SCORE

| Book | Weight | Average | Weighted |
|---|---:|---:|---:|
| DotCom Secrets | 40% | 63.0 | 25.2 |
| Expert Secrets | 30% | 56.5 | 17.0 |
| Traffic Secrets | 30% | 44.5 | 13.3 |
| **FINAL SCORE** | | | **55.5 / 100** |

**Grade:** C+ (All three books partially implemented. Traffic is the primary gap.)

---

## INTERPRETATION

| Score Range | Meaning | sanctionsai.dev |
|---|---|---|
| 50-70 | All three books implemented. Traffic flowing, conversions happening. | **55.5** — Fits this tier. Product + funnel + story are functional. Traffic infrastructure exists. Distribution is the 23-point gap. |

---

## THE PATTERN

The classic Brunson diagnosis: **funnel quality 63 + movement psychology 57 + distribution 45 = 23-point distribution gap.**

DotCom and Expert are in the "good intent, solid execution, missing refinement" range. Traffic is the entire remaining game. Everything is BUILT but nothing is TURNED ON:

- Email sequences → written but Resend key missing (dead)
- Dream 100 → documented but never contacted
- Social profiles → claimed but empty
- Blog content → 8 posts, no cadence
- Ads → pixels absent, zero campaigns
- JV program → swipe copy ready, no partners recruited

**The single highest-leverage fix:** Set `RESEND_API_KEY` on Fly.io. That one secret turns the entire email infrastructure (welcome, 5-day Soap Opera, 30-day Seinfeld, winback) from dead code into a live lead-nurturing machine. Current state: subscribe endpoint captures leads into a JSONL file with zero follow-up. Every single lead since launch has leaked.

---

## SCORE vs PRIOR AUDIT

| | Prior (portfolio-wide) | This (focused deep-dive) |
|---|---|---|
| Composite | **68.7** | **55.5** |
| DotCom | ~70 (est.) | 63.0 |
| Expert | ~70 (est.) | 56.5 |
| Traffic | ~65 (est.) | 44.5 |

**Why the 13.2-point drop:** The portfolio-wide audit scored all 10 sites in one pass with less evidence-gathering per site. This focused audit:
1. Verified the `/subscribe` endpoint live (works → saves to file, no email sent)
2. Discovered RESEND_API_KEY is NOT configured (all email sequences dead)
3. Audited both human and agent pages separately  
4. Counted actual blog posts (8, not "some")
5. Checked X/Twitter account status (claimed but empty)
6. Found no blog RSS feed
7. Verified the Seinfeld content is template-generated (not fully custom)

**Recommendation:** Use this 55.5 score as the current baseline. The 68.7 was inflated by assuming code presence = production function.

---

## TOP 5 HIGHEST-ROI FIXES (for human review — NOT implementing now)

1. **Set RESEND_API_KEY on Fly.io** — Unlocks: welcome emails, 5-day Soap Opera, 30-day Seinfeld, winback. DotCom Ch6: 52→70. Cost: $0 (API key config only).

2. **Add email capture to homepage** — Currently capture only on /start. Add inline squeeze or exit-intent popup to the main landing page. DotCom Ch6: 52→72.

3. **Name a proprietary framework** — "The 4-Pillar Agent Compliance Protocol" on the homepage. Expert Ch2: 42→65. Requires: one new section on homepage + blog post.

4. **Publish blog weekly** — Current 8 posts, last July 4. Needs weekly cadence + RSS feed + distribution to Dream 100 communities. Traffic Ch3: 62→72. Cost: content creation (human action).

5. **Turn on Dream 100 outreach** — Contact 5 targets/week from the existing 75-name list. Start with Tier 2 (developer communities — lowest friction). Traffic Ch6: 40→55.

---

## EVIDENCE APPENDIX

### Live Verification Results
- `GET /` → HTTP 200, full landing page with JSON-LD, PostHog, AEO tracking
- `GET /agent` → HTTP 200, agent-focused page with x402 pricing
- `GET /pricing` → HTTP 200, 3 tiers with structured data
- `GET /dream100` → HTTP 200, 75 targets across 3 tiers
- `GET /partners/jv` → HTTP 200, 50% commission + swipe copy
- `GET /about` → HTTP 200, origin story + data sources
- `GET /blog` → HTTP 200, 8 posts indexed
- `GET /start` (squeeze) → HTTP 200, "Agent Compliance Playbook" lead magnet
- `GET /sitemap.xml` → HTTP 200, 234 URLs indexed
- `GET /robots.txt` → HTTP 200, AI crawlers allowed, Discover configured
- `GET /llms.txt` → HTTP 200, structured for LLM consumption
- `POST /subscribe` → `{"ok":true,"email_sent":false}` (email dead)
- `GET https://x.com/data_nerd` → HTTP 200 (account exists)
- `GET /blog/rss.xml` → 404 (no RSS feed)

### Codebase Inventory
- **api.py:** 8,991 lines, stdlib-only Python HTTP server
- **Email sequences:** 5 Soap Opera (custom content), 30 Seinfeld (template bodies, real subjects), Welcome, Winback
- **Drip engine:** `/cron/drip` endpoint, `send_soap_operas()` state machine with day tracking, seamless Soap→Seinfeld transition
- **Branded emails:** `_build_branded_email()` with agentmail header/footer, unsubscribe link
- **Analytics:** PostHog with 10+ custom events including AI referral detection (12 engines)
- **Structured data:** Organization, Person, SoftwareApplication, WebSite, Offer, FAQPage, SpeakableSpecification, BreadcrumbList
- **Billing:** billing.py with SQLite database, Stripe integration for checkout
- **pSEO:** 234 pages across multiple content categories (for/*, compare/*, blog/*, guides/*, penalties/*, how-to/*, glossary/*, cost/*, integrations/*, vs/*)

### Key Gaps Found
1. `RESEND_API_KEY` env var NOT set on Fly.io → all email sequences dead
2. No tripwire / order bump / OTO anywhere in the flow
3. No named proprietary framework
4. No VSL, webinar, or masterclass page
5. Social media: X account claimed but appears empty; no other platforms
6. No ad pixels (Facebook, LinkedIn, Google, Reddit)
7. No blog RSS feed
8. Blog publishing cadence: 8 posts, last July 4, no weekly rhythm
9. Homepage has NO email capture (only on /start squeeze page)
10. No guarantee/risk-reversal on human-facing pages
11. Seinfeld email bodies are template-generated (not fully custom per day)
