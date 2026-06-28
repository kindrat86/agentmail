# agentmail — compliance & verification toolkit for AI agents

> Your agent is about to send USDC to a stranger. **Is that stranger sanctioned?**
> 782 OFAC crypto wallets · 19,086 sanctioned names · 16 embargoed jurisdictions.
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
pip install sanctions-mcp
```

### Option A — use it from an MCP client (Claude Code / Cursor)

```jsonc
// .mcp.json or your client's MCP config
{
  "mcpServers": {
    "agentmail": {
      "command": "python",
      "args": ["-m", "agentmail.mcp_server"]
    }
  }
}
```

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
# → OFAC SDN: 782 wallets, 19086 names; source=vile/ofac-sdn-list@...
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
| **vile/ofac-sdn-list** (GitHub releases) | 782 multi-chain crypto addresses (ETH/USDT/TRX/XBT/...) | daily |
| **US Treasury OFAC `sdn.csv`** | 19,086 sanctioned individuals & entities | as published |
| Embargoed jurisdictions set | 16 ISO-2 codes under comprehensive OFAC/UN/EU sanctions | tracked manually |

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

**Hosted API** (roadmap) is for when you don't want to keep a server up, keep lists fresh, or keep a 24/7 uptime: a managed endpoint with API-key auth, rate limits, and an audit log of every screen (the thing regulators/investors ask for). Dev tier ~$19/mo. This README updates when it ships.

---

## Roadmap

- [x] Email inbox (Mail.tm) + SMS/OTP (mock/5sim/twilio) + OTP extraction
- [x] **Compliance layer — real OFAC data** (osint provider): 782 wallets + 19,086 names
- [x] MCP server (10 tools) + HTTP API + CLI
- [ ] Hosted API with API-key auth + rate limiting (Fly.io)
- [ ] Audit log (tamper-evident screen history — the enterprise wedge)
- [ ] EU + UN consolidated lists (osint provider, phase 2)
- [ ] Paid provider: ComplyAdvantage passthrough (enterprise)
- [ ] x402 per-call billing (when agents pay themselves)

## Design notes (honest)

- **The compliance layer has the real moat.** Email/SMS are plumbing a platform could swallow. Sanctions screening tied to agent-transaction history builds a dataset nobody else has, and per-jurisdiction rules are something the big infra players explicitly avoid.
- **Self-host is the free tier, not a trap.** The value you pay for (eventually) is not the data — it's uptime, freshness, and the audit trail. The data is and will stay public.
- **5sim numbers are shared-after-release.** Fine for receiving an OTP, never for 2FA on accounts you intend to keep.

## License

MIT — see [LICENSE](LICENSE).

## Contributing

Issues and PRs welcome. If you're using agentmail in production, I'd love to hear what for.
