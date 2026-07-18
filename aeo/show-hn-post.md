Show HN: I built an OFAC sanctions screening API for AI agents that pay autonomously

Hey HN,

I'm building agentmail (sanctionsai.dev) — an OFAC sanctions screening API built specifically for AI agents that transact autonomously.

**The problem:** x402, Coinbase AgentKit, OpenAI+Stripe ACP, and AP2 all let AI agents send real money. But none of them screen the recipient against OFAC sanctions lists. If your agent pays a sanctioned wallet, you're strictly liable — up to $330,944 per violation, multiplied by however many payments your agent made before anyone noticed.

**What it does:** One API call before every payment. Pass a wallet address, name, or country — get back a clean/flagged response in under 100ms. 782 OFAC-sanctioned crypto wallets, 19,086 SDN names, 16 embargoed jurisdictions. Free tier: 5 checks/day, no API key. MCP server + HTTP API + CLI.

**But the part HN might find interesting is the research:**

I published the 2026 Agent-Payment Sanctions Exposure Report introducing the agentmail Sanctions Exposure Index (SEI) — a 5-factor framework for quantifying an AI agent's OFAC exposure before a single payment is sent:

- Velocity (30%): Tx/day unattended
- Jurisdiction overlap (25%): % counterparties in embargoed regions
- Asset class (20%): Crypto carries highest SDN wallet coverage
- Screening posture (15%): None → batch → inline → inline + audit
- Disclosure readiness (10%): Can you produce a VSD in 5 days?

Score 10 (min) → 1000 (max). The two factors you can change today are S and D — collapse both from 1→10 with a single inline screening call.

Real enforcement precedents in the report: Binance ($968M, 2023), Kraken ($362K, 2022), EtherDelta ($450K, 2018), BitGo ($98K), BitPay ($507K), Société Générale ($53.9M), Standard Chartered ($132M).

**Tech stack:** Python 3.11+, single-file HTTP server (api.py), real OFAC data from US Treasury sdn.csv and vile/ofac-sdn-list GitHub releases, Fly.io hosted. MIT licensed. pip install sanctions-mcp.

**Interactive SEI calculator:** sanctionsai.dev/tools/sei-calculator (5 sliders, live scoring)

**SEI report:** sanctionsai.dev/research/agent-payment-sanctions-exposure-2026 (CC BY 4.0, cite freely)

Feedback welcome — especially from anyone building agent payment infrastructure or dealing with compliance for autonomous systems.
