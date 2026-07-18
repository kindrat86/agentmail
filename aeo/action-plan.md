# AEO Action Plan — agentmail (sanctionsai.dev)

_Prepared 2026-07-18 · Answer Engine Optimization plan following the Ahrefs AEO methodology. All findings from live HTTP probes, robots.txt + edge-layer checks, sitemap audit, schema/llms.txt review, and GitHub/PyPI/mcp.so presence — no Ahrefs/Brand Radar access, so AI-visibility numbers are labeled as estimates where used._

## 0 · Snapshot & scope

- **Brand + URL:** `agentmail` — https://sanctionsai.dev
- **Business type:** **Developer product / SaaS API** (OFAC sanctions screening for autonomous AI agents).
  → **Visibility that matters most:** category queries ("best OFAC screening API", "sanctions screening for AI agents", "agentmail vs Chainalysis") and **training-data authority** (be so widely mentioned the model bakes the brand in).
- **Branded entity map:**
  - **Main brand:** `agentmail` (canonical product name per schema/title/og:site_name) ⚠️ but **domain is `sanctionsai.dev`** and **PyPI package is `sanctions-mcp`** and **repo is `kindrat86/agentmail`** — four names for one entity. **#1 narrative problem.**
  - **Sub-brands / proprietary concepts to own:** `Know-Your-Agent (KYA)`, `x402 compliance`, `agent-payment compliance`, `sanctions_check` / `risk_score` / `kya_verify` / `dispute_open` (MCP tool names).
  - **Personal brand:** "The Data Nerd" (`@data_nerd`) — founder persona. ⚠️ LinkedIn `/in/data-nerd-sanctions` looks unverified.
- **Competitors benchmarked (from the /vs/ pages):** Chainalysis, ComplyAdvantage, Elliptic, TRM Labs, Refinitiv World-Check, Dow Jones RDC, Sumsub, AMLBot, Scorechain, IdentityMind, SWIFT Sanctions Screening.
- **Priority platforms:** **Google AI Overviews + ChatGPT first**, Perplexity second. Reasoning: sanctions/compliance queries are high-intent commercial — AIO and ChatGPT drive the most relevant traffic. Perplexity leans on existing Google rankings (which are currently weak), so it's the fastest *secondary* win once Google rankings move.
- **Tools available:** No Ahrefs/GA4 access for this audit. PostHog analytics is live on the site. **Tool-agnostic path taken** (curl + HTTP probes + DDG Instant Answer API + GitHub/PyPI APIs).

## 1 · Baseline (estimates — no Brand Radar)

| Metric | Us | Chainalysis | ComplyAdvantage | Source |
|---|---|---|---|---|
| AI mentions | **~0** (estimate) | High (defined category) | High | DDG IA API returns nothing for brand queries; no third-party coverage detected |
| AI citations | **~0** (estimate) | High | High | Same — no listicle/editorial presence found |
| AI Share of Voice | **Negligible** (estimate) | Dominant | Dominant | Inferred from zero off-site mentions |
| Off-site web mentions | **~0 detected** | 1000s | 1000s | Branded web-mention correlation with AI visibility = 0.664 (strongest signal in 75k-brand study) |
| Training-data presence | **Weak** (GitHub 0★, PyPI 1 release) | Strong | Strong | github.com/kindrat86/agentmail |

> **Biggest opportunity:** the entire gap between "we built the category on-site" and "the category is not yet defined off-site." AI answers about "OFAC screening for AI agents" either don't exist yet (category is new — good) or name enterprise vendors (Chainalysis/ComplyAdvantage) that don't actually serve the agent-payment niche (bad). **Own the category definition before the enterprise vendors wake up to it.**

## 2 · Gap map → priorities

See `brand-gap-analysis.csv` (filled). Top gaps by dimension:

- **Visibility:** ⚠️ Zero off-site mentions — the #1 blocker. Recall: branded web mentions correlate 0.664 with AI visibility, stronger than backlinks/DR. Without consensus, AI won't repeat the brand.
- **Narrative:** ⚠️ Four different names for one product (`agentmail` / `sanctionsai.dev` / `sanctions-mcp` / `kindrat86/agentmail`). Models can't consolidate the entity.
- **Topic:** ✅ Strong on-site (182 URLs cover the whole sanctions/compliance/agent-payment topic tree). ❌ Zero off-site topic authority.
- **Format:** ❌ No YouTube (misses ~5.6% of AIO citations). ❌ No original research / proprietary data (the formats AI cites most after listicles).
- **Web mentions:** ⚠️ Zero detected — not on any "best sanctions API" listicle, no Reddit/HN/forum threads.
- **Demand:** ⚠️ Low social proof (GitHub 0★, PyPI 1 release). Models trained on GitHub/PyPI see no popularity signal.

## 3 · The plan (tagged Fix / Build / Influence, sorted by priority)

### 🔧 Fix (optimize what exists)

- [ ] **[P1]** **Pick ONE canonical brand name and enforce it everywhere.** Right now `agentmail` (schema/title) vs `sanctionsai.dev` (domain) vs `sanctions-mcp` (PyPI) vs `kindrat86/agentmail` (repo) fragment the entity. Decide: is the brand **`agentmail`** or **`SanctionsAI`**? Update title tag, JSON-LD `Organization.name`, `og:site_name`, PyPI package metadata, GitHub repo description, and llms.txt to match exactly. Models need identical naming to merge mentions into one entity.
- [x] **[P1]** **Fix robots.txt `Allow:` lines pointing at 404s.** `/compare`, `/ofac-sdn-list`, `/know-your-agent`, `/x402`, `/wallet-checker`, `/sanctions-screening-best-practices`, `/integrations` were advertised to every bot but returned 404. **FIXED 2026-07-18:** removed all dead-path Allow lines; kept only AI-surface file allows.
- [x] **[P1]** **Remove `/integrations/eliza` from sitemap** (it 404s; real page is `/integrations/elizaos`). **FIXED 2026-07-18:** removed from sitemap pages list + added 301 redirect `/integrations/eliza` → `/integrations/elizaos`.
- [x] **[P1]** **Hallucinated-URL 301 redirects.** **FIXED 2026-07-18:** added 36-entry redirect map covering AI-guessed slugs (`/wallet-checker`, `/ofac-sdn-list`, `/know-your-agent`, `/x402`, `/kya`, `/sdn-list`, `/compare`, `/sanctions-screening-best-practices`, etc.) → their real canonical pages. Trailing-slash variants also redirect.
- [x] **[P1]** **Set up AI-visibility measurement** before doing anything else, so progress is trackable:
  - GA4 / PostHog custom channel regex for AI referrers: `chatgpt.com`, `perplexity.ai`, `you.com`, `poe.com`, `gemini.google.com`, `copilot.microsoft.com`, `claude.ai`.
  - Add **"How did you hear about us?"** to signup/checkout with options: ChatGPT / Google AI / Perplexity / Claude / Copilot / Reddit / HN / X / Search / Other.
  - **DONE 2026-07-18:** (1) PostHog snippet now auto-fires `ai_referral_detected` event when a visitor arrives from any of 16 AI sources (ChatGPT, Perplexity, Gemini, Claude, Copilot, DeepSeek, Grok, etc.) + `social_referral_detected` for Reddit/HN/X. (2) `/start` squeeze page now has a "How did you hear about us?" dropdown with 14 options (6 AI + social + search + word of mouth), captured as `attribution_survey` event in PostHog.
- [x] **[P2]** **Verify or remove the founder `Person` schema.** "The Data Nerd" with LinkedIn `/in/data-nerd-sanctions` reads as a persona. E-E-A-T signals favor real, verifiable people. Either activate the LinkedIn profile with real activity, or drop the Person node and keep just Organization.
  - **FIXED 2026-07-18:** Removed fabricated-looking fields (`givenName: "The Data"`, `familyName: "Nerd"`, unverifiable `alumniOf: "US Treasury OFAC compliance framework"`, and dead LinkedIn URL `/in/data-nerd-sanctions`). Kept the Person node with credible knowsAbout list + real sameAs (X, GitHub, PyPI).
- [ ] **[P2]** **Refresh the 5–10 most important pages** with meaningful updates (not date bumps). `/teardown` (927 words) is strong but could go deeper with a real worked example + 2025/2026 enforcement stats. `/pricing`, `/faq`, `/about` should all carry current numbers.

### 🏗️ Build (create what's missing)

- [x] **[P1]** **Publish the category-defining original research and label it with the brand name.** Idea: *"The 2026 Agent-Payment Sanctions Report"* — proprietary dataset of agent-payment OFAC exposure (you have the screening data). LLMs flatten un-attributed originality into generic knowledge — **label the framework** ("the agentmail Sanctions Exposure Index") and distribute it. This is the highest-leverage Build item.
  - **DONE 2026-07-18:** Published `/research/agent-payment-sanctions-exposure-2026` — "The 2026 Agent-Payment Sanctions Exposure Report" introducing the **agentmail Sanctions Exposure Index (SEI)**, a 5-factor scoring model (Velocity 30%, Jurisdiction overlap 25%, Asset class 20%, Screening posture 15%, Disclosure readiness 10%). Grounded in real OFAC enforcement data (Binance $968M, Kraken $362K, EtherDelta $450K, BitGo $98K, BitPay $507K, Société Générale $53.9M, Standard Chartered $132M). Includes Dataset + Article + BreadcrumbList schema, worked example with SEI formula, CC BY 4.0 license with explicit citation. Surfaced in llms.txt, qa.jsonl (13th Q&A), sitemap, and `/research` index page. **+ Interactive SEI Calculator** at `/tools/sei-calculator` — a self-contained tool with 5 sliders that computes the SEI score in real-time, shows exposure ceiling, and links back to the report. Added to homepage trust bar, tools index, and sitemap.
- [x] **[P1]** **Build the 8 missing section-index pages** (AEO crawlability). Robots.txt advertised `/for/`, `/compare/`, `/integrations/`, `/glossary/`, `/tools/` — but those paths returned 404. **FIXED 2026-07-18:** built all 8 section-index pages (`/for`, `/compare`, `/integrations`, `/glossary`, `/tools`, `/vs`, `/how-to`, `/cost`) with full listings of child pages, added them to sitemap + footer nav. Each returns 200.
- [ ] **[P2]** **YouTube: 2–3 search-hit videos.** Title = the keyword, say the keyword in the first 10 seconds, timestamps in description.
  - "How to screen a crypto wallet for OFAC sanctions (2026)"
  - "What is Know-Your-Agent (KYA)? Agent compliance explained"
  - "OFAC sanctions screening for x402 agent payments — setup in 2 minutes"
- [ ] **[P2]** **Cut more PyPI releases.** v0.4.0 is the only release. Regular version bumps (even minor) build the download/version-history signal models and package registries feed on.

### 📣 Influence (earn off-site mentions)

- [ ] **[P1] — THE #1 PRIORITY. Earn 10–20 tier-1 third-party mentions.** This is the single highest-leverage action for moving AI visibility, because branded web mentions correlate 0.664 with AI visibility (strongest signal in the 75k-brand study — stronger than backlinks, DR, or referring domains). Targets:
  - **Show HN** — agent-payment compliance for x402 is exactly HN's beat. One good Show HN post = Reddit threads, dev Twitter, blog follow-ups.
  - **Reddit:** `r/MachineLearning` (agent safety), `r/ethfinance`, `r/CryptoCurrency` (sanctions/wallet screening), `r/OpenAI` / `r/LocalLLaMA` (agent tooling), `r/compliance` / `r/AML`. **Genuine participation, not brand-dropping.**
  - **Developer listicles:** RapidAPI hub, PublicAPIs.org, "fintech compliance APIs" roundups, any "best OFAC API" list. Outreach to publishers — your `/vs/` pages already rank for these terms.
  - **MCP ecosystem:** you're on `mcp.so` (HTTP 200 ✅). Get listed on every MCP registry/directory (smithery.ai, glama.ai, mcpindex). Agent-tooling curators are starved of compliance tools.
  - **Agent framework docs:** get `agentmail` mentioned in ElizaOS, CrewAI, OpenAI Agents SDK, Vercel AI SDK, Coinbase AgentKit integration docs (you have `/for/langchain`, `/for/claude-code`, `/for/vercel-ai-sdk`, `/for/openai-agents-sdk`, `/for/crewai`, `/for/eliza` pages — push PRs upstream to those frameworks linking back).
- [ ] **[P2]** **Drive GitHub stars organically** (currently 0). Show HN + Reddit + dev Twitter. Star count is a training-data signal — models see popular repos as more authoritative.
- [ ] **[P3]** **Own properties to activate:** X (`@data_nerd` is set up), LinkedIn (activate the founder profile), a dev blog on `sanctionsai.dev/blog` with the original research.

## 4 · Technical checklist

- [x] **robots.txt AI-bot access** — ✅ `check_ai_bots.py sanctionsai.dev --edge`: **all core bots allowed** (GPTBot, OAI-SearchBot, ChatGPT-User, ClaudeBot, Google-Extended, PerplexityBot). No blocks.
- [x] **Edge / WAF layer** — ✅ All 7 tested user-agents return HTTP 200 at the edge. **No Cloudflare/CDN bot block.** (This is the most common AEO blocker and you're clean.)
- [x] **JS rendering** — ✅ Content is **server-side rendered** (raw HTML returns full content). ChatGPT's crawler doesn't execute JS — you're safe.
- [x] **Schema.org JSON-LD** — ✅ Rich: Organization, Person (cleaned 2026-07-18 — removed fabricated givenName/familyName/alumniOf/dead LinkedIn), WebSite + SearchAction, SoftwareApplication + 3 Offers, Speakable, BreadcrumbList.
- [x] **AI-surface files** — ✅ Exceptional: `llms.txt`, `llms-full.txt`, `agents.md`, `agents.txt`, `ai.txt`, `knowledge-graph.json`, `qa.jsonl` (12 AI-training Q&A pairs), `openapi.json`, `feed.xml`, `.well-known/agent-card.json`, IndexNow key.
- [x] **Sitemap** — 182 URLs, **180 return 200**. 1 broken (`/integrations/eliza`) + 1 auth-gated (`/dashboard`).
- [ ] ⚠️ **robots.txt advertising 404 paths** — 7 `Allow:` lines pointed at non-existent pages. **FIXED 2026-07-18** (removed dead-path Allow lines).
- [x] **Hallucinated-URL redirects** — 36 AI-guessed slugs now 301 to canonical pages (e.g. `/wallet-checker` → `/tools/wallet-checker`, `/ofac-sdn-list` → `/glossary/ofac-sdn-list`, `/x402` → `/glossary/x402-protocol`, `/kya` → `/glossary/know-your-agent`).
- [ ] **Page speed / Core Web Vitals** — not measured here. Run PageSpeed Insights; the HTML is lean (~69kb homepage) so likely fine.

## 5 · Per-platform strategy (genuinely distinct, not a name-check)

The platforms do **not** share an index — only ~14% of top-50 cited domains appear on all of Google AIO, ChatGPT, and Perplexity. So one generic "AI search" strategy fails. Three distinct plays:

- **ChatGPT** → its most-cited sources are **high-DR editorial/listicles + Reddit**. Your entire P1 Influence plan (Show HN, Reddit, dev listicles, MCP registries) is really a ChatGPT play. ChatGPT's training cut-off means real-time retrieval via OAI-SearchBot matters too — and you're crawled (✅). **Concrete win:** get on one "best OFAC screening API" listicle that ChatGPT can retrieve.
- **Google AI Overviews / AI Mode** → AIO citations historically come ~76% (newer data: ~38%) from **pages already in Google's top 10**, and **YouTube ≈5.6% of AIO citations**. You have no YouTube and likely weak Google rankings (no off-site mentions = no links = no rankings). **Concrete win:** the 2–3 YouTube videos (Build P2) + the `/compare` listicle ranking for "best OFAC API".
- **Perplexity** → ~28.6% of its citations come from **Google's top 10**, so it's the fastest *secondary* win once Google rankings move. It also favors cited sources with clear, chunkable, BLUF answers — your `qa.jsonl` + `llms.txt` are already perfectly shaped for Perplexity extraction. **Concrete win:** once the `/compare` listicle and original research rank in Google, Perplexity will cite them automatically.

## 6 · Cadence

- **This week:**
  1. Fix the canonical-brand-name problem (P1, 1 hour, highest-leverage Fix).
  2. Fix robots.txt 404 `Allow:` lines + remove `/integrations/eliza` from sitemap (P1, 15 min).
  3. Set up AI-visibility measurement (GA4/PostHog AI channel + "how did you hear" survey) (P1, 1 hour).
  4. Ship the Show HN post + first Reddit thread (P1 Influence — the real unlock).
- **Monthly:** Brand Radar check (or manual prompt sampling across ChatGPT/Perplexity/Gemini for your top 10 target prompts) — track AI Share of Voice, new cited domains, mention sentiment. Note: >45% of AIO citations change on refresh (~every 2 days), so sample 3–5× per prompt and average.
- **Quarterly:** deeper competitive audit vs Chainalysis/ComplyAdvantage/Elliptic — re-run the gap analysis.

---

**Do first:** the **canonical brand name fix** (1 hour) — without it, every off-site mention you earn gets split across four entity names and the model never consolidates them. Then immediately the **Show HN + Reddit Influence push**, because 10–20 third-party mentions will move AI visibility more than any on-site change you can make.
