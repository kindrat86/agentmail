# agentmail — Dream 100 + Distribution Plan

> **Status:** Internal strategy doc. NOT yet published externally.
> **Goal:** Get eyeballs on a funnel that is already Brunson A-grade on structure.
> **Math:** $19/mo → need 138 customers for $2.6K MRR, 211 for $4K MRR. ~3-4 sales/week.
> **Thesis:** The funnel converts once visited. The only missing variable is *traffic*.

---

## Tier 1 — The Core 25 (highest leverage, do first)

These are the orgs/people whose audience IS our dream customer (devs building
x402 / autonomous-payment agents). Work your way in by building, not asking.

| # | Target | Why | The move |
|---|--------|-----|----------|
| 1 | **x402.org / Coinbase x402 team** | Our value prop is literally "the compliance layer for x402." Their docs should mention us. | Open a PR to their docs/examples adding a sanctions-check step. Get listed as a "companion service." |
| 2 | **Coinbase AgentKit team** | AgentKit is THE agent-wallet SDK. Every AgentKit agent needs OFAC before paying. | Build the `agentmail` AgentKit action. Submit to their registry. |
| 3 | **vile/ofac-sdn-list (GitHub)** | Our data source. 100+ stars, used by compliance devs. | Contribute back, credit them on our site (already done), ask for a reciprocal mention. |
| 4 | **Anthropic MCP registry (mcp.so, Glama)** | Claude Code / Cursor users discover tools here. | Submit `sanctions-mcp`. Optimize listing title/desc for "OFAC / sanctions / agent." |
| 5 | **LangChain** | Biggest agent framework. A `SanctionsCheck` tool in their toolkit = discovery. | PR a community tool/integration to their docs. |
| 6 | **CrewAI** | Agent framework with a marketplace. | Publish a CrewAI tool. List in their marketplace. |
| 7 | **Eliza framework** | Crypto-native agent framework — our exact niche. | Build an Eliza plugin. Their Discord is where Base/agent devs live. |
| 8 | **OpenAI Agents SDK** | We already wrote the blog post. Make it a real integration example in their docs. | PR an example to openai-agents-python showing compliance in a payment flow. |
| 9 | **ETHGlobal / Base hackathons** | Agents that pay get built at hackathons. | Sponsor a "best compliance" bounty, give free credits. Cheap, targeted. |
| 10 | **Base ecosystem (Coinbase L2)** | Our settlement layer + their agent narrative. | Apply to Base Builder program. Get on their ecosystem map. |

## Tier 2 — The Content & Community 40 (infiltrate their ponds)

| Target | Where they gather | The move |
|--------|-------------------|----------|
| r/LocalLLaMA, r/LangChain, r/CryptoCurrency | Reddit | Write the "my agent almost paid a sanctioned wallet" post (Epiphany Bridge, first person). NO link in body — put it in comments. |
| Hacker News | news.ycombinator.com | "Show HN: agentmail — OFAC sanctions screening for AI agents." Lead with the test #47 story + live curl. |
| x402 Discord | discord | Be helpful, not promotional. Answer "how do I stay compliant?" questions. |
| Cursor / Claude Code communities | Discord, Reddit | Share the MCP server. "Add OFAC screening to your coding agent." |
| Dev.to, Hashnode | Blogs | Repurpose the 3 existing posts. Each targets a keyword: "x402 compliance," "OFAC for agents," "Know Your Agent." |
| YouTube (agent-building creators) | — | The YouTuber who demos "build an AI agent that pays invoices" → give them the curl. |

## Tier 3 — Earned / Owned (build the moat)

- **SEO content:** One pillar page per use case (fintech, DeFi, remittance, DEX,
  marketplace). We already have the blog seeds. Expand each into a 1500-word
  guide targeting the long-tail ("OFAC screening for trading bots", etc.).
- **Comparison content:** "agentmail vs TRM Labs / Elliptic / Chainalysis" —
  we're the only one built FOR agents + x402-native. That's the wedge.
- **Build in public:** revenue numbers, the first real fine that happens in the
  industry (newsjacking), each integration shipped.

---

## The 5 integration posts to write (ready to publish when you say go)

1. **"How to add OFAC screening to a Coinbase AgentKit agent"** → Tier 1 #2
2. **"Every x402 payment needs an OFAC check"** (exists as blog draft) → Tier 1 #1
3. **"Add sanctions screening to your Claude Code agent (MCP)"** → Tier 1 #4
4. **"OFAC compliance for LangChain agents — one line"** → Tier 1 #5
5. **"I built a compliance layer for AI agents that pay (the full story)"** → HN/Show

---

## First testimonial strategy (the Customer Stories = 10/100 fix)

- The first 5 devs who run a real check and catch a flagged wallet → ask for a
  quote (anonymous is fine per the agent-economy pattern).
- Replace the honest placeholder ("their words go right here. Not before.")
  with the first real quote the moment it exists.
- Do NOT fabricate testimonials. The trust grid (19,086 names / hourly / MIT /
  $10K guarantee) carries social proof until then.

---

## Metrics to watch (PostHog now wired)

| Event | What it tells you | Target |
|-------|-------------------|--------|
| `page_viewed` | Traffic to / and /agent | Trend up |
| `cta_free_signup` | Email capture conversion | >15% of / views |
| `cta_checkout` | Intent to pay | >3% of / views |
| `cta_run_check` | Agent-page activation | >20% of /agent views |
| `cta_github` | Developer interest | track ratio |
