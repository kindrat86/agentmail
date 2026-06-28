# Launch posts — agentmail

Ready-to-paste drafts for Show HN and Reddit. Post these AFTER the
awesome-mcp-servers PR merges and ideally after the hosted API is live
(so early visitors who want a hosted option find one). Adjust wording to
your voice.

---

## Show HN (https://news.ycombinator.com/submit)

**Title:**
```
Show HN: agentmail – OFAC sanctions screen for AI agents (free, no API key)
```

**Body:**
```
Hi HN. I built a tool that lets any AI agent check whether a counterparty
(wallet, name, or country) is on the OFAC Specially Designated Nationals list
before paying them — and it runs on real, free, public data with no API key.

Why: agents are starting to pay for things autonomously (x402, AP2, OpenAI+
Stripe ACP, Coinbase AgentKit). But if your agent sends USDC to a wallet that
turns out to be on the OFAC SDN list, that's *your* legal problem — and the big
payment infra players explicitly don't handle per-jurisdiction sanctions
screening or agent-transaction risk. So I built the missing piece.

What it does (4 tools):
- sanctions_check(name, wallet, country) — exact + token-subset match
- risk_score(counterparty, amount, ...) — 0-100 allow/review/decline
- kya_verify(agent_id, evidence) — Know-Your-Agent trust score
- dispute_open — record a bad transaction

Where the data comes from (all public, no key):
- 782 crypto addresses from vile/ofac-sdn-list (multi-chain, daily refresh)
- 19,086 names from the US Treasury sdn.csv
- 16 embargoed jurisdictions

Lists are cached locally (24h TTL) and the provider degrades gracefully — if
the network is down it screens against a stale cache and flags itself as
degraded rather than silently passing everything.

Three surfaces, same core: MCP server (10 tools, for Claude Code / Cursor /
Hermes), HTTP API, CLI. Free and open source (MIT). Self-host in 30 seconds:

    pip install sanctions-mcp
    python -m agentmail.cli sanctions --wallet 0x098B716B8Aaf21512996dC57EB0615e2383E2f96
    → flagged: OFAC_SDN wallet_exact, confidence 1.0

Or try the hosted API with no signup (50 free checks/day):
    curl "https://agentmail-api.fly.dev/sanctions?wallet=0x098B716B8Aaf21512996dC57EB0615e2383E2f96"

Repo: https://github.com/kindrat86/agentmail

The thing I want to be honest about: agents paying agents is still early, and
the self-host version is free — so the business model is the hosted API
(uptime, freshness, audit log) rather than the data itself. I'm more
interested in whether this is useful to people building agentic-commerce stuff
right now. Happy to answer questions.
```

---

## Reddit r/LocalLLaMA (https://www.reddit.com/r/LocalLLaMA/submit)

**Title:**
```
Built an OFAC sanctions-screen MCP tool for AI agents — real data, no API key
```

**Body:**
```
If you're building agents that transact (x402 / AP2 / agentic commerce), you
probably want to check whether the counterparty is sanctioned before the agent
sends money. I couldn't find a focused tool for this, so I built one.

agentmail — MCP server + HTTP API + CLI. Screens against real OFAC data:
- 782 crypto wallets (multi-chain, daily-refreshed)
- 19,086 sanctioned individuals/entities (US Treasury sdn.csv)
- 16 embargoed jurisdictions

4 tools: sanctions_check, risk_score (allow/review/decline), kya_verify, dispute_open.

No API key, no signup, MIT-licensed, self-host. 24h disk cache, degrades
gracefully if offline.

    pip install sanctions-mcp
    # add to your MCP client config, done

Or try the hosted API (50 free checks/day, no signup):
    curl "https://agentmail-api.fly.dev/sanctions?wallet=0x098B716B8Aaf21512996dC57EB0615e2383E2f96"

Repo: https://github.com/kindrat86/agentmail

Curious if anyone here is working on agent payments and how you're handling the
compliance side today. The big rails (OpenAI+Stripe ACP, Coinbase x402) don't
touch per-jurisdiction KYA or sanctions freshness — that's the gap.
```

---

## r/MCP (smaller, but on-target)

Same body as r/LocalLLaMA, title:
```
agentmail — OFAC sanctions + KYA compliance as an MCP server (free, no key)
```

---

## When to post (timing matters)

1. **Not yet** — wait for the awesome-mcp-servers PR to merge so curious
   visitors who search find the listing.
2. **Best** — after the hosted API is live, so the "is there a hosted version?"
   question has an answer instead of "coming soon".
3. **Time of day** — HN front-page odds favor posting Tue–Thu, ~8–10am ET.
4. **Be present** — reply to every comment within the first 2 hours. The
   comment thread is where the trust is built; a silent OP kills momentum.

## After posting

- Star/reply on GitHub issues that come in from the thread.
- If someone finds a real bug, fix it fast and reply with the commit — that
  signals "maintained" more than any marketing.
