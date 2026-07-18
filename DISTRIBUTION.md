# agentmail (sanctionsai.dev) — Distribution Playbook (get cited by AI search)

**Why this file exists (AEO logic):** for MCP/agent tools, the pages AI assistants cite are *directories
and awesome-lists*, not your own site. Branded web mentions were the single strongest correlate of AI
visibility in Ahrefs' 75,000-brand study (0.664). agentmail sits in a thin-competition niche (OFAC
sanctions for AI agents) where the agent-payments and MCP directories *are* the sources — so this is the
fastest visibility win in the portfolio after GitDealFlow. Work top-down.

Status legend: ✅ done · ⬜ todo · 🔒 needs browser GitHub OAuth or a publish action (you do it, or approve
me to open the PRs).

## Copy-paste submission fields

| Field | Value |
|---|---|
| Name | `sanctions-mcp` / **agentmail** |
| One-liner | OFAC sanctions screening, risk scoring, and Know-Your-Agent verification for AI agents that pay autonomously. |
| Category | Compliance · Security · Finance · AI Agents |
| Repo | https://github.com/kindrat86/agentmail |
| Homepage | https://sanctionsai.dev |
| PyPI | `sanctions-mcp` (`pip install sanctions-mcp`) |
| MCP registry | https://mcp.so/server/agentmail ✅ |
| License | MIT |
| Tags | ofac, sanctions, sdn, compliance, kyc, kya, aml, ai-agents, x402, agent-payments, mcp |
| Proof | agent-card → https://sanctionsai.dev/.well-known/agent-card.json · openapi → https://sanctionsai.dev/openapi.json |

**Longer blurb:** agentmail lets any AI agent check whether a counterparty (wallet, name, or country) is
on the OFAC SDN list before paying it. Screens against 782 OFAC crypto wallets, 19,086 SDN names, and 16
embargoed jurisdictions. Tools: sanctions_check, risk_score (allow/review/decline), kya_verify. Compatible
with x402, AP2, OpenAI+Stripe ACP, and Coinbase AgentKit. Free tier, no API key. MCP + HTTP + CLI, MIT.

## Tier 1 — MCP registries (highest ROI; these get cited)

| # | Registry | URL | Auth | Status |
|---|---|---|---|---|
| 1 | **mcp.so** | https://mcp.so/server/agentmail | — | ✅ live |
| 2 | **Glama.ai** (generates a score badge for the awesome-mcp PR) | https://glama.ai/mcp/servers/submit | 🔒 GitHub OAuth | ⬜ |
| 3 | **Smithery.ai** (GitHub-import path; needs `sanctions-mcp` on PyPI ✅) | https://smithery.ai/new | 🔒 GitHub | ⬜ |
| 4 | **PulseMCP** | https://www.pulsemcp.com/submit | 🔒 form | ⬜ |
| 5 | **Cursor Directory** (GitDealFlow is listed here — proven channel) | https://cursor.directory/mcp | 🔒 form/PR | ⬜ |
| 6 | **Official MCP registry** | https://github.com/modelcontextprotocol/registry | 🔒 PR | ⬜ |

## Tier 2 — Awesome-list PRs (highest long-term ROI; permanent citable pages)

1. **punkpeye/awesome-mcp-servers** (~90K★). Section: Finance & Fintech (or Security). Needs Glama badge.
   PR title: `Add agentmail OFAC sanctions screening 🤖🤖🤖`
   ```
   - [kindrat86/agentmail](https://github.com/kindrat86/agentmail) 🐍 🏠 ☁️ - OFAC sanctions screening, risk scoring, and Know-Your-Agent verification for AI agents: screen a wallet/name/country against the SDN list before an agent pays. Free tier, MCP + HTTP + CLI.
   ```
2. **e2b-dev/awesome-ai-agents** — GitDealFlow used this exact channel (issue #890). Section: Tools/Infra.
   ```
   - [agentmail](https://sanctionsai.dev) - OFAC sanctions screening + Know-Your-Agent verification for autonomous agents. Screen a counterparty against the SDN list before paying; compatible with x402, AP2, and AgentKit. MIT.
   ```
3. **coinbase/x402 ecosystem + Coinbase AgentKit / awesome-agentkit** — agentmail is the *compliance* layer
   for agent payments. This is its single most on-target ecosystem — an agent paying over x402 needs a
   sanctions check first.
   ```
   - [agentmail](https://sanctionsai.dev) - Pre-payment OFAC sanctions check for x402/AP2 agent payments: sanctions_check(wallet) returns a match/clear decision before money moves. Free tier, MCP tool.
   ```
4. **AP2 ecosystem / agent-payments awesome lists** — reuse the entry above.

## Tier 3 — Compliance / RegTech + AlternativeTo (niche authority)

agentmail already ships `/compare/{chainalysis,elliptic,complyadvantage,sumsub,world-check}` pages — point
these at directories where buyers compare tools:

| Channel | URL | Note | Status |
|---|---|---|---|
| **AlternativeTo** | https://alternativeto.net | List as an alternative to Chainalysis / ComplyAdvantage / Elliptic (you have the compare pages) | ⬜ 🔒 |
| **RegTech / AML tool directories** | (e.g. regtechdirectory.org, AML-focused listicles) | Pitch the "for AI agents / crypto" angle | ⬜ 🔒 |
| **G2 / Capterra** | https://www.g2.com | Compliance-software category profile | ⬜ 🔒 |
| **There's An AI For That** | https://theresanaiforthat.com/submit | Heavily crawled AI directory | ⬜ 🔒 |
| **Crunchbase** | https://www.crunchbase.com | Company profile (strong AI-citation signal) | ⬜ 🔒 |

## Tier 4 — Launches

| Channel | URL | Status |
|---|---|---|
| **Show HN** | https://news.ycombinator.com/submit | ⬜ 🔒 |
| **Product Hunt** | https://www.producthunt.com/posts/new | ⬜ 🔒 |
| **Indie Hackers** | https://www.indiehackers.com/ | ⬜ 🔒 |

## What I can vs. can't do
- ✅ Done for you: on-site agent-discovery parity (added `agents.txt`, `knowledge-graph.json`, `qa.jsonl`
  routes to `api.py`; you already had llms.txt / llms-full.txt / agents.md / .well-known / openapi). Now
  every directory/agent that fetches agentmail gets clean, attributable, citable content.
- 🔒 The submissions need browser GitHub OAuth or are publish actions — you run them, **or** approve me to
  open the awesome-list **PRs** (Tier 2) via `gh`.

**Do first:** Glama → Smithery (PyPI is already live) → awesome-mcp PR → **x402/AgentKit awesome PR** (your
most on-target niche) → awesome-ai-agents PR.
