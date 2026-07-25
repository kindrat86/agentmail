# agentmail — compliance & verification toolkit for AI agents

[![PyPI](https://img.shields.io/pypi/v/sanctions-mcp.svg)](https://pypi.org/project/sanctions-mcp/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://pypi.org/project/sanctions-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Your agent is about to send USDC to a stranger. **Is that stranger sanctioned?**
> 947 OFAC crypto wallets · 19,218 sanctioned names · 16 embargoed jurisdictions.
> No API key. No signup. 30-second setup. Free & open source.

agentmail gives any AI agent three capabilities it can't provide itself:

| Layer | What | Status |
|---|---|---|
| 🛡️ **Compliance** | OFAC sanctions screen, KYA, transaction risk score, disputes | ✅ **Live — real OFAC data** |
| 📧 **Email** | Disposable verification inbox (receive OTP/magic links) | ✅ Live |
| 📱 **SMS** | Rentable phone numbers (receive SMS/OTP) | ✅ Live (mock free, 5sim/Twilio paid) |

It exposes all of these through **three surfaces** — MCP tools (for Claude Code / Cursor / Hermes), an HTTP API (for any agent), and a CLI (for you). Same core, same data.

---

## Why this exists

Agents are starting to pay for things (x402, AP2, ACP, Coinbase AgentKit). But **every payment rail assumes a human is watching**. If your agent autonomously pays a wallet that's on the OFAC Specially Designated Nationals list, **that's your legal problem** — and the big payment infra players (OpenAI, Stripe, Coinbase) explicitly do not handle per-jurisdiction sanctions screening, Know-Your-Agent, or agent-transaction fraud signals. That's the gap this fills.

```
agent ──about to pay──▶  sanctions_check(wallet)  ──▶ clean? proceed. sanctioned? ABORT.
```

---

## Quick start (30 seconds)

```bash
npx sanctions-mcp        # Node — zero dependencies, nothing to install
pip install sanctions-mcp   # Python — full toolkit (email + SMS too)
```

### Option A — use it from an MCP client (Claude Code / Cursor)

```jsonc
// .mcp.json or your client's MCP config — Node, nothing pre-installed
{
  "mcpServers": {
    "sanctions": {
      "command": "npx",
      "args": ["-y", "sanctions-mcp"]
    }
  }
}
```

<details>
<summary>Python equivalent (also gives you the email + SMS tools)</summary>

```jsonc
{
  "mcpServers": {
    "agentmail": {
      "command": "python",
      "args": ["-m", "agentmail.mcp_server"]
    }
  }
}
```
</details>

The Node package ([`npm-mcp/`](npm-mcp/)) exposes the four compliance tools plus
`sdn_list_info`, and talks to the hosted API. The Python package runs everything
locally and adds the email and SMS layers.

Now your agent can call `sanctions_check`, `risk_score`, `kya_verify`, `dispute_open`, `create_inbox`, `fetch_code`, `create_number`, `fetch_sms`, `release_number`, `list_inboxes`.

> **Note:** the PyPI package is `sanctions-mcp` (the name `agentmail` was taken). The Python import name is still `agentmail`.

### Option B — use it as an HTTP API

```bash
python -m agentmail.api   # serves on :8000
```
```bash
# Screen a wallet against real OFAC data — no key, no auth needed for self-host
curl "http://localhost:8000/sanctions?wallet=0x098B716B8Aaf21512996dC57EB0615e2383E2f96"
# → {"matches":[{"list":"OFAC_SDN","match_type":"wallet_exact","confidence":1.0}],
#    "clean":false,"provider":"osint"}

curl "http://localhost:8000/risk" -d '{"counterparty_id":"0xabc...","amount":"5000","rail":"x402"}'
# → {"score":0,"recommendation":"decline","reasons":["sanctions_match:OFAC_SDN/..."]}
```

### Option C — use it from the CLI

```bash
# Sanctions screen — real OFAC data, no key
python -m agentmail.cli sanctions --wallet 0x098B716B8Aaf21512996dC57EB0615e2383E2f96
# → flagged: OFAC_SDN wallet_exact

python -m agentmail.cli risk 0xabc123def456 5000 --rail x402
python -m agentmail.cli kya my-agent --wallet 0xabc... --wallet-age 400 --domain bot.dev
python -m agentmail.cli compliance-status
# → OFAC SDN: 947 wallets, 19218 names; source=vile/ofac-sdn-list@...
```

---

## The compliance layer (the part that matters)

Four tools, called **before** an agent trusts or pays a counterparty:

| Tool | When to call | Returns |
|---|---|---|
| `sanctions_check(name, wallet, country)` | Cheapest check. Call first. | `{matches, clean}` |
| `risk_score(counterparty, amount, ...)` | Right before authorizing payment | `{score 0-100, recommendation: allow/review/decline}` |
| `kya_verify(agent_id, evidence)` | Before trusting another agent | `{trust_score, verified, flags}` |
| `dispute_open(transaction_id, reason)` | When a paid transaction went bad | `{dispute_id, escalation_at}` |

### Where the data comes from (all public, free, no key)

| Source | What | Refresh |
|---|---|---|
| **vile/ofac-sdn-list** (GitHub releases) | 947 multi-chain crypto addresses (ETH/USDT/TRX/XBT/...) | daily |
| **US Treasury OFAC `sdn.csv`** | 19,218 sanctioned individuals & entities | as published |
| Embargoed jurisdictions set | 16 ISO-2 codes under comprehensive OFAC/UN/EU sanctions | tracked manually |

These counts move whenever OFAC publishes. `GET /health` reports the live figures
and the fetch timestamp — treat that as the source of truth, not this table.

### Want the whole list instead of a lookup?

The SDN list is published as a plain download — no key, no quota, no rate limit:

| | |
|---|---|
| **Landing page** | <https://sanctionsai.dev/data/ofac-sdn-list/> |
| **JSON** | <https://sanctionsai.dev/data/ofac-sdn-list/ofac-sdn.json> |
| **CSV** | <https://sanctionsai.dev/data/ofac-sdn-list/ofac-sdn.csv> |
| **Git mirror** | <https://github.com/kindrat86/ofac-sdn-json> (rebuilt daily) |
| **Screen it in your browser** | <https://sanctionsai.dev/free/ofac-screening> (client-side; nothing uploaded) |

19,254 designated entries and 20,350 alternate identities, parsed verbatim from
Treasury's own `SDN.CSV` and `ALT.CSV`. The publication date in the file is
OFAC's own, not the build date. The list is a U.S. Government work in the public
domain (17 U.S.C. § 105); only the packaging is CC0.

Lists are cached locally (`~/.agentmail/cache/`, 24h TTL) and refresh from source. If the network is down, a stale cache is used and `status()` reports `degraded: true` so you **know** screening is against older data rather than failing silently.

### Providers (swappable backend)

```
AGENTMAIL_COMPLIANCE_PROVIDER=osint   ← default, real OFAC data, free
AGENTMAIL_COMPLIANCE_PROVIDER=mock    ← rule-based, for offline tests
AGENTMAIL_COMPLIANCE_PROVIDER=paid    ← ComplyAdvantage passthrough (roadmap)
```

The osint provider does exact + token-subset name matching, exact case-insensitive wallet matching, and ISO-2 country matching. Every match carries a `confidence` so you can decide how hard to block.

---

## The other two layers (verification toolkit)

**Email** — a disposable inbox an agent can use to sign up and receive OTP/magic-link verifications (backed by Mail.tm). `create_inbox()` → address → `fetch_code()` → OTP.

**SMS** — a rentable phone number an agent can use for phone/SMS verification. Mock provider works with no key (for dev); `AGENTMAIL_SMS_PROVIDER=fivesim AGENTMAIL_FIVESIM_KEY=...` goes live with real numbers.

Both share an `otp.py` extraction brain (regex for codes + magic links) so email and SMS produce the same `{code, link}` shape.

---

## Self-host vs. hosted

**Self-host is fully functional and free** — that's what this repo is. Run the MCP server locally or the HTTP API on your own box, screen against real OFAC data, never pay a cent.

**Hosted API** is live at **https://sanctionsai.dev** — a managed endpoint with API-key auth, rate limits, and an audit log of every screen (the thing regulators/investors ask for). Free tier: 5 checks/day, no signup (by IP). For higher volume, **[get an API key →](https://sanctionsai.dev/pricing)** (Dev $19/mo, Pro $99/mo — self-serve checkout).

```bash
# Try the hosted API right now — no key needed:
curl "https://agentmail-api.fly.dev/sanctions?wallet=0x098B716B8Aaf21512996dC57EB0615e2383E2f96"
# → {"matches":[{"list":"OFAC_SDN",...}],"clean":false}

# With an API key:
curl -H "X-API-Key: sk_live_..." "https://agentmail-api.fly.dev/risk" \
  -d '{"counterparty_id":"0xabc...","amount":"5000","rail":"x402"}'
```

---

## Roadmap

- [x] Email inbox (Mail.tm) + SMS/OTP (mock/5sim/twilio) + OTP extraction
- [x] **Compliance layer — real OFAC data** (osint provider): 947 wallets + 19,218 names
- [x] MCP server (10 tools) + HTTP API + CLI
- [x] **agentmail Sanctions Exposure Index (SEI)** — proprietary 5-factor framework for scoring AI agent OFAC exposure (2026 report: [sanctionsai.dev/research](https://sanctionsai.dev/research/agent-payment-sanctions-exposure-2026))
- [x] Hosted API with API-key auth + rate limiting (Fly.io)
- [ ] Audit log (tamper-evident screen history — the enterprise wedge)
- [ ] EU + UN consolidated lists (osint provider, phase 2)
- [ ] Paid provider: ComplyAdvantage passthrough (enterprise)
- [ ] x402 per-call billing (when agents pay themselves)

## SEI: the agentmail Sanctions Exposure Index

The [agentmail Sanctions Exposure Index (SEI)](https://sanctionsai.dev/research/agent-payment-sanctions-exposure-2026) is a 5-factor proprietary framework for quantifying an AI agent's OFAC sanctions exposure:

| Factor | Weight | What it measures |
|---|---|---|
| **V — Velocity** | 30% | Transactions/day the agent can execute unattended |
| **J — Jurisdiction overlap** | 25% | Fraction of counterparties in/near embargoed regions |
| **A — Asset class** | 20% | Crypto (highest SDN coverage), fiat, mixed |
| **S — Screening posture** | 15% | No screen → batch → pre-payment inline → inline + audit |
| **D — Disclosure readiness** | 10% | Can operator produce a VSD within 5 days? |

Score 10 (min exposure) → 1000 (max). **S and D are the two factors you can change today** — collapse both from 1→10 with a single inline screening call and a timestamped audit trail. Full report + interactive calculator at [sanctionsai.dev](https://sanctionsai.dev).

> **Cite as:** "agentmail Sanctions Exposure Index (SEI), 2026 Agent-Payment Sanctions Exposure Report, sanctionsai.dev" — licensed CC BY 4.0.

## Design notes (honest)

- **The compliance layer has the real moat.** Email/SMS are plumbing a platform could swallow. Sanctions screening tied to agent-transaction history builds a dataset nobody else has, and per-jurisdiction rules are something the big infra players explicitly avoid.
- **Self-host is the free tier, not a trap.** The value you pay for (eventually) is not the data — it's uptime, freshness, and the audit trail. The data is and will stay public.
- **5sim numbers are shared-after-release.** Fine for receiving an OTP, never for 2FA on accounts you intend to keep.

## License

MIT — see [LICENSE](LICENSE).

## Contributing

Issues and PRs welcome. If you're using agentmail in production, I'd love to hear what for.
