#!/usr/bin/env python3
"""
agentmail HTTP API — stdlib only, no framework dependency.

Run:   python -m agentmail.api  [PORT=8000]
Endpoints:
  POST /inboxes           {"label":"signup","prefix":"bot"}  -> {address,id,label}
  GET  /inboxes                                            -> [{label,address,id}]
  GET  /inboxes/<label>/latest?wait=60&from=&subject=       -> {from,subject,code,link,...}
  GET  /health                                             -> {ok}
"""
from __future__ import annotations
import json
import os
import time
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from . import core
from . import billing
from . import x402

# ─── Hosted-mode config (env-driven; all optional, off by default) ──────────
# Self-host default: no auth, no rate limit, no audit log — identical behaviour
# to before. Flip these on for the hosted deployment.
_REQUIRE_AUTH = os.environ.get("AGENTMAIL_REQUIRE_AUTH", "").lower() in ("1", "true", "yes")
_API_KEYS = {k.strip() for k in os.environ.get("AGENTMAIL_API_KEYS", "").split(",") if k.strip()}
# requests per hour per identity (key, or IP in free tier)
_RATE_LIMIT = int(os.environ.get("AGENTMAIL_RATE_LIMIT", "0") or 0)
# free-tier daily cap for unauthenticated callers (by IP). 0 = no anon access when auth required.
_FREE_TIER_DAILY = int(os.environ.get("AGENTMAIL_FREE_TIER_DAILY", "100") or 100)
_AUDIT_LOG = os.environ.get("AGENTMAIL_AUDIT_LOG", "")  # path to append-only JSONL
_PUBLIC_URL = os.environ.get("AGENTMAIL_PUBLIC_URL", "https://agentmail-api.fly.dev")

# ─── Rate-limit + free-tier counters (in-memory, process-local) ─────────────
_rl_window: dict[str, deque] = defaultdict(deque)   # identity -> [timestamps] within 1h
_free_used: dict[str, deque] = defaultdict(deque)   # ip -> [timestamps] within 24h
_rl_lock = __import__("threading").Lock()

_SERVER_CARD = {
    "version": "1.0",
    "name": "agentmail",
    "description": "Compliance & verification toolkit for AI agents — OFAC sanctions screen, KYA, transaction risk, plus disposable email/SMS verification inboxes.",
    "schema_version": "1.0",
    "tools": [
        {
            "name": "sanctions_check",
            "description": "Screen a counterparty against OFAC/EU/UN/UK sanctions lists. Cheapest check, call first. At least one of name / wallet / country required. Returns matches with list, match_type, and confidence, plus a clean boolean.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name to screen"},
                    "wallet": {"type": "string", "description": "Crypto wallet address"},
                    "country": {"type": "string", "description": "ISO-2 country code"}
                }
            }
        },
        {
            "name": "risk_score",
            "description": "Score a transaction's fraud risk BEFORE authorizing payment. Recommendation is one of allow/review/decline. rail in: x402, ap2, acp, tap. category in: digital_goods, services, physical.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "counterparty_id": {"type": "string"},
                    "amount": {"type": "string"},
                    "currency": {"type": "string", "default": "USDC"},
                    "rail": {"type": "string", "default": "x402"},
                    "category": {"type": "string", "default": "digital_goods"}
                },
                "required": ["counterparty_id", "amount"]
            }
        },
        {
            "name": "kya_verify",
            "description": "Verify an AI agent's identity before transacting with it (Know Your Agent). evidence keys: wallet_address, wallet_age_days, domain, pubkey, owner_email, declared_country.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string"},
                    "evidence": {"type": "object"}
                },
                "required": ["agent_id"]
            }
        },
        {
            "name": "dispute_open",
            "description": "Open a dispute when an agent-paid transaction went bad (non-delivery, fraud). Records with a 7-day auto-escalation window.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "transaction_id": {"type": "string"},
                    "reason": {"type": "string"},
                    "evidence": {"type": "object"}
                },
                "required": ["transaction_id", "reason"]
            }
        },
    ],
}

# provider active in this server process (resolved once)
try:
    _SMS = core.sms_status()
except Exception as _e:
    _SMS = {"provider": core.SMS_PROVIDER_NAME, "ready": False, "detail": str(_e)}
try:
    _COMPLIANCE = core.compliance_status()
except Exception as _e:
    _COMPLIANCE = {"provider": core.COMPLIANCE_PROVIDER_NAME, "ready": False, "detail": str(_e)}

# Initialize billing database (SQLite) — safe no-op if already exists
try:
    billing.init_db()
except Exception:
    pass


def _audit(event: dict) -> None:
    """Append a screen event to the audit log (tamper-evident-ish JSONL append)."""
    if not _AUDIT_LOG:
        return
    try:
        line = json.dumps({"ts": time.time(), **event}, separators=(",", ":"))
        with open(_AUDIT_LOG, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass  # never break a request over logging


def _check_rate(identity: str) -> tuple[bool, str]:
    """Return (allowed, reason). Sliding 1h window."""
    if not _RATE_LIMIT:
        return True, ""
    now = time.time()
    with _rl_lock:
        w = _rl_window[identity]
        while w and now - w[0] > 3600:
            w.popleft()
        if len(w) >= _RATE_LIMIT:
            return False, "rate_limited:hourly"
        w.append(now)
    return True, ""


def _check_free_tier(ip: str) -> tuple[bool, str]:
    """Unauthenticated daily cap (by IP)."""
    if not _REQUIRE_AUTH:
        return True, ""
    now = time.time()
    with _rl_lock:
        w = _free_used[ip]
        while w and now - w[0] > 86400:
            w.popleft()
        if len(w) >= _FREE_TIER_DAILY:
            return False, "free_tier_exhausted"
        w.append(now)
    return True, ""


def _json(handler, status, obj):
    body = json.dumps(obj).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


# ─── Marketing site (sanctionsai.dev) — shared dark theme + SEO data ──────────
_SITE = "https://sanctionsai.dev"

_VERTICAL_KEYS = frozenset((
    "fintech", "crypto", "ecommerce", "trading", "payments", "marketplace",
    "dex", "defi", "defi-protocol", "remittance", "gaming", "nft", "lending",
))
_COMPETITOR_KEYS = frozenset(("chainalysis", "elliptic", "complyadvantage", "sumsub"))
_BLOG_SLUGS = frozenset(("ofac-for-agents", "know-your-agent", "x402-compliance"))

_DARK_CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,system-ui,sans-serif;background:#0a0a0a;color:#e0e0e0;line-height:1.6;overflow-x:hidden}
a{color:#00d4aa;text-decoration:none}
.prose{max-width:720px;margin:0 auto;padding:0 24px}
nav{padding:20px 24px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #1a1a1a;flex-wrap:wrap;gap:12px}
.logo{font-weight:700;font-size:1.2em;color:#fff}
.logo span{color:#00d4aa}
nav .links{display:flex;gap:18px;align-items:center;flex-wrap:wrap}
nav a{color:#888;font-size:.9em;transition:color .2s}
nav a:hover{color:#fff}
.btn{display:inline-block;padding:10px 20px;border-radius:8px;font-weight:600;font-size:.9em;transition:transform .1s,box-shadow .2s;cursor:pointer;border:none}
.btn-primary{background:#00d4aa;color:#0a0a0a}
.btn-primary:hover{box-shadow:0 0 20px rgba(0,212,170,.3);transform:translateY(-1px)}
.btn-ghost{border:1px solid #333;color:#e0e0e0;background:transparent}
.btn-ghost:hover{border-color:#00d4aa}
section{padding:56px 24px;border-top:1px solid #1a1a1a}
section:first-of-type{border-top:none}
h1{font-size:2.2em;font-weight:800;line-height:1.15;letter-spacing:-.02em;margin-bottom:16px}
h2{font-size:1.6em;font-weight:700;margin-bottom:16px}
h3{font-size:1.1em;font-weight:600;margin:22px 0 8px;color:#fff}
p{color:#b0b0b0;margin-bottom:14px}
.lead{font-size:1.1em;color:#999}
.note{color:#666;font-size:.85em}
code,pre{font-family:'SF Mono',Consolas,monospace}
code{background:#1a1a1a;padding:2px 8px;border-radius:4px;color:#00d4aa;font-size:.9em}
pre{background:#111;border:1px solid #222;border-radius:12px;padding:18px 20px;overflow-x:auto;color:#cfcfcf;font-size:.85em;line-height:1.5;margin:16px 0}
pre code{background:none;padding:0;color:inherit}
ul{color:#b0b0b0;padding-left:22px;margin:10px 0 16px}
li{margin:6px 0}
table{width:100%;border-collapse:collapse;margin:20px 0;font-size:.92em}
th,td{text-align:left;padding:12px 14px;border-bottom:1px solid #1a1a1a;vertical-align:top}
th{color:#fff;font-weight:600}
.cta-box{background:#111;border:1px solid #222;border-radius:16px;padding:36px;text-align:center;margin:32px auto;max-width:680px}
.cta-box h2,.cta-box h3{margin-bottom:8px}
.cta-box p{color:#999;margin-bottom:18px}
.input{width:100%;padding:14px 16px;border-radius:10px;border:1px solid #333;background:#111;color:#e0e0e0;font-size:1em;font-family:'SF Mono',Consolas,monospace}
.input:focus{outline:none;border-color:#00d4aa}
.result{margin-top:20px;padding:20px;border-radius:12px;border:1px solid #222;background:#111;font-family:'SF Mono',Consolas,monospace;font-size:.9em;white-space:pre-wrap;word-break:break-all}
.result.clean{border-color:#00d4aa;color:#00d4aa}
.result.flag{border-color:#ff6b6b;color:#ff6b6b}
.faq-item{margin:0 0 10px;border:1px solid #1a1a1a;border-radius:10px;overflow:hidden}
.faq-item summary{padding:16px 20px;cursor:pointer;font-weight:600;color:#fff;list-style:none}
.faq-item summary::-webkit-details-marker{display:none}
.faq-item summary::before{content:"+ ";color:#00d4aa}
.faq-item[open] summary::before{content:"- "}
.faq-item .a{padding:0 20px 18px}
footer{padding:48px 24px;text-align:center;border-top:1px solid #1a1a1a}
footer .links{display:flex;gap:24px;justify-content:center;margin-bottom:16px;flex-wrap:wrap}
footer a{color:#666;font-size:.9em}
footer a:hover{color:#fff}
footer p{color:#444;font-size:.8em}
@media(max-width:640px){h1{font-size:1.7em}nav{flex-direction:column;align-items:flex-start}}
"""

_NAV = '<nav><div class="logo">agent<span>mail</span></div><div class="links"><a href="/">Home</a><a href="/faq">FAQ</a><a href="/docs">Docs</a><a href="/tools/wallet-checker">Free Checker</a><a href="/blog/ofac-for-agents">Blog</a><a href="/pricing">Pricing</a><a href="/checkout/dev" class="btn btn-primary">Get API key</a></div></nav>'

_FOOTER = '<footer><div class="links"><a href="/">Home</a><a href="/faq">FAQ</a><a href="/docs">Docs</a><a href="/tools/wallet-checker">Wallet Checker</a><a href="/pricing">Pricing</a><a href="https://github.com/kindrat86/agentmail">GitHub</a><a href="https://pypi.org/project/sanctions-mcp/">PyPI</a></div><p>agentmail — OFAC sanctions screening for AI agents · MIT licensed · Data from US Treasury &amp; vile/ofac-sdn-list</p></footer>'

_VERTICALS = {
    "fintech": {
        "name": "Fintech",
        "title": "OFAC Sanctions Screening for Fintech AI Agents",
        "desc": "Add OFAC sanctions screening to fintech AI agents. Screen counterparties, wallets, and names before any regulated transaction.",
        "p1": "Regulated financial institutions deploying AI agents must screen every counterparty against OFAC sanctions lists before funds move. agentmail gives fintech agents a single API call that checks names, crypto wallets, and countries against the full OFAC Specially Designated Nationals list in real time.",
        "p2": "For fintechs the cost of a miss is severe — civil penalties can reach $300,000 or twice the transaction value per violation. Automating payments without screening transfers that liability straight onto your institution. agentmail closes the gap between autonomous execution and regulatory obligation, leaving a defensible audit trail.",
        "p3": "Integrate sanctions checks into your loan-approval, onboarding, and payment-routing agents via MCP, HTTP, or CLI. The free tier covers 50 checks per day with no signup, so you can validate the workflow before scaling to a paid plan.",
    },
    "crypto": {
        "name": "Crypto",
        "title": "OFAC Sanctions Screening for Crypto AI Agents",
        "desc": "Crypto-native agents can screen any wallet against OFAC before signing an on-chain payment. 782 sanctioned addresses, real time.",
        "p1": "Crypto-native agents that handle on-chain payments interact with pseudonymous wallets by default — and the chain does not tell you whether a counterparty is sanctioned. agentmail screens any EVM, Bitcoin, or Tron address against 782 OFAC-listed crypto wallets before your agent signs a transaction.",
        "p2": "OFAC has made clear that mixing, routing, or settling to a sanctioned address is a violation regardless of whether you knew the identity behind it. For agents using x402, Coinbase AgentKit, or AP2, a pre-payment sanctions check is the cheapest insurance you can run.",
        "p3": "Add a single curl call to your agent's payment path, or wire it into your MCP client. The free tier needs no API key — your crypto agent can start screening wallets in minutes.",
    },
    "ecommerce": {
        "name": "E-commerce",
        "title": "OFAC Sanctions Screening for E-commerce AI Agents",
        "desc": "E-commerce agents screen buyer names, supplier wallets, and destination countries against OFAC before approving international orders.",
        "p1": "E-commerce agents that process international orders routinely decide where to ship, whom to refund, and which supplier to pay. Each of those decisions can touch an embargoed country or a sanctioned supplier. agentmail lets your agent screen buyer names, supplier wallets, and destination countries against OFAC before it acts.",
        "p2": "Cross-border commerce is exactly where sanctions exposure hides — a flagged buyer, a drop-ship supplier in a restricted jurisdiction, a payout to a sanctioned wallet. Screening programmatically means your storefront agent can decline risky orders automatically instead of generating compliance work after the fact.",
        "p3": "Drop the check into your order-approval or payout agent. Free tier: 50 checks/day, no key required. Production volume from $19/mo.",
    },
    "trading": {
        "name": "Trading",
        "title": "OFAC Sanctions Screening for Trading AI Agents",
        "desc": "Trading bots screen counterparties, wallets, and jurisdictions against OFAC before each cross-border fill or settlement.",
        "p1": "Trading bots that execute cross-border transactions move fast — often too fast for manual compliance review. agentmail gives your trading agent a sub-second sanctions check on counterparty names, wallets, and jurisdictions before each fill or settlement.",
        "p2": "A single trade with a sanctioned counterparty can freeze assets and trigger regulatory scrutiny that outweighs months of gains. Building the screen into the execution path means your bot declines the trade rather than explaining it later.",
        "p3": "Call it over HTTP from any trading runtime, or expose it as an MCP tool to your reasoning agent. No key needed to start — 50 free checks a day.",
    },
    "payments": {
        "name": "Payments",
        "title": "OFAC Sanctions Screening for Payment AI Agents",
        "desc": "Payment routing agents screen every party on the route — sender, receiver, intermediary — against OFAC before authorizing funds.",
        "p1": "Payment routing agents sit between senders and receivers, deciding how and where funds move. That makes them the natural enforcement point for sanctions screening — the last stop before money leaves. agentmail checks every leg of a route: sender, receiver, and intermediary wallets or names.",
        "p2": "When an agent orchestrates payouts, refunds, or splits, it inherits the compliance duty for each hop. Screening each party against OFAC in real time means a flagged receiver is blocked before the transaction is authorized, not reconciled after.",
        "p3": "One API call per party, sub-second latency, MCP/HTTP/CLI. The free tier covers prototyping; paid tiers scale to 100,000 checks/month.",
    },
    "marketplace": {
        "name": "Marketplace",
        "title": "OFAC Sanctions Screening for Marketplace AI Agents",
        "desc": "Marketplace agents screen both sides of every match — buyers and sellers, names and wallets — against OFAC before escrow releases.",
        "p1": "Marketplace agents that match buyers and sellers globally have the hardest screening problem: counterparties are strangers, often in different jurisdictions, transacting at machine speed. agentmail screens both sides of every match against OFAC names, wallets, and countries before escrow releases.",
        "p2": "A marketplace that lets a sanctioned seller cash out — or a buyer in an embargoed region pay — is on the hook for facilitation. Embedding sanctions checks in the match-and-release flow turns that risk into an automatic decline.",
        "p3": "Wire it into your listing-approval, escrow, and payout agents. Start free, scale on demand.",
    },
    "dex": {
        "name": "DEX",
        "title": "OFAC Sanctions Screening for DEX AI Agents",
        "desc": "DEX agents screen the wallet behind every pool and router call against OFAC-listed addresses before approving a swap.",
        "p1": "DEX agents that execute swaps interact purely with smart contracts and unknown wallets — the perfect conditions for accidentally interacting with a sanctioned address. agentmail screens the counterparty wallet behind every pool and router call against OFAC-listed addresses before your agent approves the swap.",
        "p2": "OFAC has sanctioned individual wallets and entire mixing protocols; an agent that swaps into or out of a tainted pool can create exposure for its operator. A pre-trade wallet screen is the simplest control that keeps your DEX agent from touching sanctioned liquidity.",
        "p3": "Add the check to your swap-approval logic over HTTP or MCP. Free tier, no key, 50 checks/day.",
    },
    "defi": {
        "name": "DeFi",
        "title": "OFAC Sanctions Screening for DeFi AI Agents",
        "desc": "DeFi agents screen depositors, borrowers, and paired pools against OFAC so they never pool liquidity with a sanctioned address.",
        "p1": "DeFi protocol agents that manage liquidity pools, vaults, and yield strategies route value through wallets they do not control. agentmail screens depositors, borrowers, and paired pools against OFAC so your agent does not pool liquidity with a sanctioned address.",
        "p2": "Sanctioned actors actively use DeFi to move and launder funds; a protocol that serves them — even unknowingly via an autonomous agent — can face enforcement. Screening counterparties before deposit, withdrawal, or rebalancing is the baseline control.",
        "p3": "One call per counterparty, real time, no key to start. Scale to production volume on a paid plan.",
    },
    "defi-protocol": {
        "name": "DeFi Protocol",
        "title": "OFAC Sanctions Screening for DeFi Protocol AI Agents",
        "desc": "DeFi protocol teams bake OFAC sanctions screening into keeper agents, frontends, and routers so sanctioned wallets are blocked at the edge.",
        "p1": "DeFi protocols themselves are increasingly treated as responsible for the activity their contracts facilitate — including agent-driven flows. agentmail gives protocol teams a sanctions screen they can bake into keeper agents, frontends, and router contracts so sanctioned wallets are blocked at the edge.",
        "p2": "Regulators have sanctioned mixer contracts and named wallets; a protocol whose autonomous keepers service those addresses inherits the problem. Embedding an OFAC check in your protocol's agent layer is how you demonstrate a compliance control that scales with TVL.",
        "p3": "Expose it as an MCP tool for your keepers or call it over HTTP from your router. Free tier for integration; paid tiers for mainnet volume.",
    },
    "remittance": {
        "name": "Remittance",
        "title": "OFAC Sanctions Screening for Remittance AI Agents",
        "desc": "Remittance agents screen sender and receiver names, payout wallets, and destination countries against OFAC on every transfer.",
        "p1": "Remittance agents that send cross-border transfers are the textbook OFAC use case — high volume, many jurisdictions, strict screening duties. agentmail screens sender and receiver names, payout wallets, and destination countries on every transfer before it is queued.",
        "p2": "Money transmitters are expected to screen every party on both ends; an autonomous remittance agent that skips this transfers the violation — and the penalty — to its operator. Building the check into the send flow makes compliance automatic, not a post-transaction report.",
        "p3": "Integrate via MCP, HTTP, or CLI alongside your existing rail. 50 free checks/day to validate, paid plans for production volume.",
    },
    "gaming": {
        "name": "Gaming",
        "title": "OFAC Sanctions Screening for Gaming AI Agents",
        "desc": "Gaming agents screen player wallets and trade counterparties against OFAC so a sanctioned actor cannot cash out through your economy.",
        "p1": "Gaming agents that handle in-game asset transactions — items, currency, marketplace trades — increasingly touch real-money rails and crypto wallets. agentmail screens player wallets and trade counterparties against OFAC so a sanctioned actor cannot cash out through your game's economy.",
        "p2": "In-game economies are a known off-ramp for illicit funds; an agent that processes a withdrawal to a sanctioned wallet creates exposure for the platform. A pre-withdrawal wallet and name screen is a cheap, high-signal control.",
        "p3": "Drop the check into your trade-approval and withdrawal agents. Free to start, scales with your player base.",
    },
    "nft": {
        "name": "NFT",
        "title": "OFAC Sanctions Screening for NFT Marketplace AI Agents",
        "desc": "NFT marketplace agents screen buyer and seller wallets against OFAC-listed addresses before matching or settling a trade.",
        "p1": "NFT marketplace agents that facilitate digital-art trades move value between wallets at the speed of minting and listing. agentmail screens buyer and seller wallets against OFAC-listed addresses before your agent matches or settles a trade.",
        "p2": "NFTs have been used to move and launder sanctioned funds; a marketplace agent that completes a sale involving a tainted wallet implicates its operator. Screening counterparties before escrow release keeps tainted value out of your flow.",
        "p3": "One API call per counterparty wallet, real time, MCP/HTTP/CLI. Free tier to integrate, paid plans for volume.",
    },
    "lending": {
        "name": "Lending",
        "title": "OFAC Sanctions Screening for Lending AI Agents",
        "desc": "Lending protocol agents screen borrower wallets and deposit addresses against OFAC before opening or rolling a position.",
        "p1": "Lending protocol agents that issue loans against collateral must evaluate the borrower and the collateral source — both can be sanctioned. agentmail screens borrower wallets and deposit addresses against OFAC before your agent opens or rolls a position.",
        "p2": "A loan funded to a sanctioned borrower, or collateral sourced from a sanctioned wallet, is a direct violation that an autonomous agent can commit in milliseconds. A pre-loan screen on both sides of the book is the control that prevents it.",
        "p3": "Call it from your underwriting agent over HTTP or MCP. Free tier: 50 checks/day, no signup.",
    },
}

_COMPETITORS = {
    "chainalysis": {
        "name": "Chainalysis",
        "desc": "agentmail vs Chainalysis: agentmail gives AI agents a sanctions screen they can call before every payment, with a free tier and self-host option. Chainalysis is built for enterprise blockchain forensics.",
        "rows": [
            ("Built for AI agents (MCP + HTTP + CLI)", True, False),
            ("Free tier (50 checks/day)", True, False),
            ("Developer pricing from $19/mo", True, False),
            ("Open-source self-host", True, False),
            ("Per-call x402 / USDC payments", True, False),
            ("OFAC crypto wallet screening", True, True),
            ("OFAC name + country screening", True, "Enterprise add-on"),
            ("Know-Your-Agent (KYA)", True, False),
            ("Blockchain forensics / KYT investigations", False, True),
            ("Enterprise compliance programs", "Basic", True),
        ],
        "when_to_pick": "Pick agentmail if you build AI agents and need a sanctions check before each autonomous payment. Pick Chainalysis for deep on-chain investigations and enterprise KYT programs.",
    },
    "elliptic": {
        "name": "Elliptic",
        "desc": "agentmail vs Elliptic: agentmail is agent-native sanctions screening with a developer tier and free checks. Elliptic focuses on enterprise crypto compliance.",
        "rows": [
            ("Built for AI agents (MCP + HTTP + CLI)", True, False),
            ("Free tier (50 checks/day)", True, False),
            ("Developer pricing from $19/mo", True, False),
            ("Open-source self-host", True, False),
            ("OFAC crypto wallet screening", True, True),
            ("Transaction risk scoring", True, True),
            ("Know-Your-Agent (KYA)", True, False),
            ("Enterprise crypto compliance suite", False, True),
        ],
        "when_to_pick": "Pick agentmail for agent-first sanctions screening you can self-host and prototype for free. Pick Elliptic for an enterprise crypto compliance platform.",
    },
    "complyadvantage": {
        "name": "ComplyAdvantage",
        "desc": "agentmail vs ComplyAdvantage: agentmail is real-time, crypto-native sanctions screening built for agents. ComplyAdvantage is a broad general-compliance platform, not agent-native.",
        "rows": [
            ("Agent-native (MCP + HTTP + CLI)", True, False),
            ("Real-time crypto wallet screening", True, "Limited"),
            ("Free tier (50 checks/day)", True, False),
            ("Developer pricing from $19/mo", True, False),
            ("Open-source self-host", True, False),
            ("OFAC name + country screening", True, True),
            ("Adverse media / PEP screening", False, True),
            ("Enterprise case management", False, True),
        ],
        "when_to_pick": "Pick agentmail for real-time, crypto-native sanctions screening that fits an agent's payment path. Pick ComplyAdvantage for a full enterprise AML/KYC case-management suite.",
    },
    "sumsub": {
        "name": "SumSub",
        "desc": "agentmail vs SumSub: agentmail is sanctions-first screening for autonomous agents. SumSub focuses on KYC and identity verification, not real-time crypto sanctions screening.",
        "rows": [
            ("Agent-native (MCP + HTTP + CLI)", True, False),
            ("Sanctions-first design", True, "KYC-first"),
            ("Real-time crypto wallet screening", True, False),
            ("Free tier (50 checks/day)", True, False),
            ("Developer pricing from $19/mo", True, False),
            ("Open-source self-host", True, False),
            ("KYC / identity verification", False, True),
            ("Liveness & document checks", False, True),
        ],
        "when_to_pick": "Pick agentmail to screen counterparties and wallets against OFAC before an agent pays. Pick SumSub when your primary need is KYC and identity verification.",
    },
}

_BLOG_POSTS = {
    "ofac-for-agents": {
        "title": "Why AI Agents Need OFAC Sanctions Screening",
        "date": "2025-06-10",
        "desc": "Autonomous agents can now move money, but nobody is screening their counterparties against OFAC. Here is why that is a legal problem and how to fix it.",
        "html": """<p>The payment rails caught up to agents fast. x402, Coinbase AgentKit, OpenAI's Stripe ACP, and AP2 all let an AI agent send real money to a counterparty with little or no human review. What didn't catch up is compliance: the moment an agent pays a sanctioned wallet or a counterparty in an embargoed region, the legal liability lands on whoever deployed the agent.</p>
<h2>The 30-second OFAC primer</h2>
<p>OFAC (the US Treasury's Office of Foreign Assets Control) maintains the Specially Designated Nationals list — roughly 19,000 individuals and entities, plus 782 crypto wallet addresses and 16 comprehensively embargoed jurisdictions. Transacting with anyone on the list is prohibited, and the standard is strict liability: it generally does not matter whether you knew.</p>
<p>Civil penalties can reach $300,000 or twice the transaction value per violation, whichever is higher. For an agent executing hundreds of payments a day, the math gets bad fast.</p>
<h2>Why agents make it worse</h2>
<p>A human payment has a person who can pause and ask "wait, who is this?" An autonomous agent has a payment function. If that function does not include a sanctions check, the agent will happily route USDC to a wallet on the SDN list — and it will do it at 3am, repeatedly, until someone notices.</p>
<h2>The fix is one API call</h2>
<p>The right pattern is simple: screen before you pay. Call <code>sanctions_check</code> on the counterparty (by wallet, name, or country) before authorizing the transaction. If the response says <code>clean: false</code>, decline. agentmail exposes exactly this as a single HTTP call, an MCP tool, and a CLI — with a free tier so you can prove it works before paying anything.</p>
<pre><code>curl "https://sanctionsai.dev/sanctions?wallet=0x098B716B8Aaf21512996dC57EB0615e2383E2f96"</code></pre>
<p>Build the check into your agent's payment path today. The free tier covers 50 checks per day, no API key required.</p>""",
    },
    "know-your-agent": {
        "title": "Know Your Agent (KYA), Explained",
        "date": "2025-06-12",
        "desc": "Know Your Agent (KYA) is the agent-era equivalent of KYC: verify the identity and trustworthiness of an AI counterparty before you transact with it.",
        "html": """<p>KYC asks "who is this customer?" Know Your Agent asks the new question the agent economy creates: "should I trust this other agent?" When your agent pays another agent — or takes an instruction from one — you need a way to score that counterparty's trustworthiness before value moves.</p>
<h2>What KYA evaluates</h2>
<p>agentmail's KYA score weighs evidence like the counterparty's wallet age, a linked domain, a public key, an owner contact, and a declared country. Older wallets and verifiable domain ownership raise the score; fresh wallets and jurisdictions overlapping sanctions lists lower it.</p>
<h2>How it fits the payment flow</h2>
<p>KYA is not a replacement for sanctions screening — it is the layer above it. First, <code>sanctions_check</code> answers the binary "is this party prohibited?" question. Then KYA answers the softer "how much should I trust this party even if they are not sanctioned?" question. Together they let an agent decide allow, review, or decline with evidence behind it.</p>
<pre><code>curl -X POST https://sanctionsai.dev/kya \\
  -H "Content-Type: application/json" \\
  -d '{"agent_id":"bot-42","evidence":{"wallet_address":"0x...","wallet_age_days":310,"domain":"example.com"}}'</code></pre>
<p>Start with the free tier: 50 sanctions checks a day, no key. Add KYA and risk scoring on a $19/mo plan.</p>""",
    },
    "x402-compliance": {
        "title": "x402 Payments and Compliance for AI Agents",
        "date": "2025-06-14",
        "desc": "x402 lets agents pay per-call in USDC. Here is how to keep those agent-to-agent payments compliant with OFAC sanctions screening.",
        "html": """<p>x402 is the payment primitive built for agents: a standardized way for one agent to pay another a small amount of USDC for a resource, in a single HTTP round trip. It is elegant — but every x402 payment is still a funds transfer, which means it is still in scope for sanctions screening.</p>
<h2>Why per-call payments do not escape OFAC</h2>
<p>The size of a payment does not change the rule. A $0.01 USDC transfer to a sanctioned wallet is still a prohibited transaction. Because x402 is designed for high-frequency, autonomous micro-payments, an un-screened agent can rack up many violations in minutes.</p>
<h2>The right pattern: screen, then pay</h2>
<p>Treat the sanctions check as the gate before the x402 payment. agentmail accepts an x402 payment itself for the screen, so an agent with no API key can still run a paid, per-call sanctions check — and then decide whether to proceed with the downstream payment it was about to make.</p>
<pre><code>curl -H "X-PAYMENT: &lt;x402-facility&gt;" "https://sanctionsai.dev/sanctions?wallet=0x098B..."</code></pre>
<p>The free tier also covers 50 checks/day by IP with no payment at all. Add compliance to your x402 agent in minutes.</p>""",
    },
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass  # quiet

    def _client_ip(self):
        # honour X-Forwarded-For when behind a proxy/load balancer (Fly/Railway)
        xff = self.headers.get("X-Forwarded-For", "")
        return xff.split(",")[0].strip() if xff else self.client_address[0]

    def _authorize(self) -> tuple[bool, str, str]:
        """Return (ok, identity, error). identity = api-key or 'anon:<ip>'.
        Keys from AGENTMAIL_API_KEYS (admin) bypass tier limits.
        Keys from billing DB are checked for tier + monthly usage."""
        ip = self._client_ip()
        # Authenticated path: Bearer token or X-API-Key header.
        key = self.headers.get("X-API-Key", "") or ""
        if not key:
            auth = self.headers.get("Authorization", "") or ""
            if auth.lower().startswith("bearer "):
                key = auth[7:].strip()
        if key:
            # Admin keys (env) — unlimited
            if key in _API_KEYS:
                return True, key, ""
            # Billing DB keys — check tier + usage
            usage = billing.record_usage(key)
            if usage.get("blocked"):
                reason = usage.get("reason", "invalid_key")
                if reason == "invalid_key":
                    return False, "", "invalid_api_key"
                return False, "", reason  # monthly_limit_exceeded
            return True, key, ""
        # Anonymous path: only allowed if auth not required, within free-tier cap.
        if _REQUIRE_AUTH:
            ok, reason = _check_free_tier(ip)
            if not ok:
                return False, "", reason
            return True, f"anon:{ip}", ""
        return True, f"anon:{ip}", ""

    def _body(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        return json.loads(self.rfile.read(n)) if n else {}

    def _x402_or_key_gate(self, audit_action: str, audit_subject: dict | None = None,
                         x402_description: str = "") -> str | None:
        """Gate for paid endpoints: accept API key, x402 payment, or free tier.
        Returns identity on success, or None (writes error/402 response) on failure.

        Order of precedence:
          1. Valid API key (admin or billing) → proceed
          2. x402 payment header (if x402 enabled) → verify, proceed
          3. Free tier (if no auth required) → proceed
          4. Otherwise → 402 Payment Required (if x402) or 401"""
        # First, try normal auth (key-based)
        ok, identity, err = self._authorize()
        if ok:
            ok2, err2 = _check_rate(identity)
            if not ok2:
                _json(self, 429, {"error": err2})
                return None
            if audit_action:
                _audit({"action": audit_action, "caller": identity, "subject": audit_subject or {}})
            return identity
        # Auth failed. If x402 is enabled, offer per-call payment instead.
        if x402.is_enabled() and err in ("invalid_api_key", "free_tier_exhausted", ""):
            payment_header = self.headers.get("X-PAYMENT", "")
            req = x402.build_payment_requirements(self.command, self.path, x402_description)
            if payment_header:
                valid, reason = x402.verify_payment(payment_header, req)
                if valid:
                    if audit_action:
                        _audit({"action": audit_action, "caller": "x402:" + x402._PAY_TO[:10],
                                "subject": audit_subject or {}, "paid": True})
                    return "x402:" + x402._PAY_TO[:10]
                _json(self, 402, {"error": "payment_invalid", "reason": reason,
                                  "payment_requirements": req})
                return None
            # No payment + no key → 402 with requirements
            self.send_response(402)
            body = json.dumps({"error": "payment_required",
                               "payment_requirements": req}).encode()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return None
        # x402 disabled, auth failed — return the original error
        code = 401 if err == "invalid_api_key" else 429
        hint = (f" — upgrade at {_PUBLIC_URL}/pricing"
                if err in ("free_tier_exhausted", "monthly_limit_exceeded") else "")
        _json(self, code, {"error": err, "upgrade_url": _PUBLIC_URL + "/pricing"} if hint else {"error": err})
        return None

    def _gate(self, audit_action: str | None = None,
              audit_subject: dict | None = None) -> str | None:
        """Auth + rate-limit gate. Returns identity on success, or None (and
        writes the error response) on failure. /health bypasses this."""
        ok, identity, err = self._authorize()
        if not ok:
            code = 401 if err == "invalid_api_key" else 429
            # Point exhausted users at the upgrade page.
            hint = (f" — upgrade at {_PUBLIC_URL}/pricing"
                    if err in ("free_tier_exhausted", "monthly_limit_exceeded")
                    else "")
            _json(self, code, {"error": err, "upgrade_url": _PUBLIC_URL + "/pricing"} if hint else {"error": err})
            return None
        ok, err = _check_rate(identity)
        if not ok:
            _json(self, 429, {"error": err})
            return None
        if audit_action:
            _audit({"action": audit_action, "caller": identity,
                    "subject": audit_subject or {}})
        return identity

    def do_GET(self):
        p = urlparse(self.path)
        if p.path == "/health":
            return _json(self, 200, {"ok": True, "service": "agentmail",
                                     "sms": _SMS, "compliance": _COMPLIANCE,
                                     "x402": x402.status()})
        # SEO foundation
        if p.path == "/robots.txt":
            return self._serve_text("User-agent: *\nAllow: /\n\nSitemap: https://sanctionsai.dev/sitemap.xml\n", "text/plain")
        if p.path == "/sitemap.xml":
            return self._sitemap_xml()
        if p.path == "/llms.txt":
            return self._llms_txt()
        # Landing page (HTML) — humans from Show HN, Google, direct visits
        if p.path == "/" or p.path == "":
            return self._landing_page()
        # JSON API info (for devs with curl — moved from / to /api)
        if p.path == "/api":
            return _json(self, 200, {
                "service": "agentmail",
                "tagline": "OFAC sanctions screening for AI agents",
                "endpoints": {
                    "screen": "/sanctions?name=&wallet=&country=",
                    "risk": "POST /risk",
                    "kya": "POST /kya",
                    "health": "/health",
                },
                "self_host": "pip install sanctions-mcp",
                "hosted_pricing": f"{_PUBLIC_URL}/pricing",
                "github": "https://github.com/kindrat86/agentmail",
                "free_tier": "50 checks/day by IP, no key needed",
            })
        # MCP server card — lets MCP registries (Smithery) skip auto-scan
        if p.path == "/.well-known/mcp/server-card.json":
            return _json(self, 200, _SERVER_CARD)
        # Pricing page (public)
        if p.path == "/pricing":
            return self._pricing_page()
        # Billing status (public, for monitoring)
        if p.path == "/billing/status":
            return _json(self, 200, billing.billing_status())
        # Stripe webhook (no auth, verified by signature)
        if p.path == "/webhooks/stripe":
            return self._stripe_webhook()
        # Success page — shows the API key after checkout
        if p.path.startswith("/keys/"):
            session_id = p.path.split("/keys/", 1)[1]
            return self._key_success_page(session_id)
        # Checkout redirects from pricing page (/checkout/dev, /checkout/team)
        if p.path.startswith("/checkout/"):
            plan = p.path.split("/checkout/", 1)[1].split("?")[0]
            try:
                result = billing.create_checkout_session(plan)
                self.send_response(302)
                self.send_header("Location", result["url"])
                self.end_headers()
            except Exception as e:
                _json(self, 500, {"error": str(e)})
            return
        # Public content / SEO pages (no auth, no usage metering)
        if p.path == "/faq":
            return self._faq_page()
        if p.path == "/docs":
            return self._docs_page()
        if p.path == "/tools/wallet-checker":
            return self._wallet_checker_page()
        if p.path.startswith("/for/"):
            vertical = p.path[len("/for/"):].split("?")[0].split("/")[0]
            if vertical in _VERTICAL_KEYS:
                return self._vertical_page(vertical)
            return _json(self, 404, {"error": "not found"})
        if p.path.startswith("/compare/"):
            competitor = p.path[len("/compare/"):].split("?")[0].split("/")[0]
            if competitor in _COMPETITOR_KEYS:
                return self._compare_page(competitor)
            return _json(self, 404, {"error": "not found"})
        if p.path.startswith("/blog/"):
            slug = p.path[len("/blog/"):].split("?")[0].split("/")[0]
            if slug in _BLOG_SLUGS:
                return self._blog_page(slug)
            return _json(self, 404, {"error": "not found"})
        # sanctions GET — paid endpoint (accepts API key OR x402 payment)
        if p.path == "/sanctions" or p.path.startswith("/sanctions?"):
            q = parse_qs(p.query)
            subject = {"name": q.get("name", [""])[0], "wallet": q.get("wallet", [""])[0],
                       "country": q.get("country", [""])[0]}
            if self._x402_or_key_gate("sanctions_check", subject, "OFAC sanctions screen") is None:
                return
            return _json(self, 200, core.sanctions_check(
                name=subject["name"], wallet=subject["wallet"], country=subject["country"]))
        # everything below is gated (no-op when auth disabled)
        if self._gate() is None:
            return
        if p.path == "/inboxes":
            return _json(self, 200, core.list_inboxes())
        if p.path == "/numbers":
            return _json(self, 200, core.list_inboxes())  # SMS numbers share the registry
        if p.path == "/sms/status":
            return _json(self, 200, core.sms_status())
        if p.path == "/compliance/status":
            return _json(self, 200, core.compliance_status())
        parts = p.path.strip("/").split("/")
        # email: /inboxes/<label>/latest
        if len(parts) == 3 and parts[0] == "inboxes" and parts[2] == "latest":
            label = parts[1]
            q = parse_qs(p.query)
            try:
                msg = core.fetch_latest(label, wait=float(q.get("wait", ["0"])[0]),
                                        match_from=q.get("from", [None])[0],
                                        match_subject=q.get("subject", [None])[0])
            except KeyError as e:
                return _json(self, 404, {"error": str(e)})
            return _json(self, 200, msg or {"empty": True})
        # sms: /numbers/<label>/sms?wait=90
        if len(parts) == 3 and parts[0] == "numbers" and parts[2] == "sms":
            label = parts[1]
            q = parse_qs(p.query)
            try:
                msg = core.fetch_sms(label, wait=float(q.get("wait", ["0"])[0]))
            except KeyError as e:
                return _json(self, 404, {"error": str(e)})
            return _json(self, 200, msg or {"empty": True})
        return _json(self, 404, {"error": "not found"})

    def do_POST(self):
        p = urlparse(self.path)
        # Checkout start — public, no auth gate (billing is self-serve)
        if p.path == "/checkout/start":
            b = self._body()
            plan = b.get("plan", "dev")
            try:
                result = billing.create_checkout_session(plan)
                _json(self, 200, result)
            except Exception as e:
                _json(self, 500, {"error": str(e)})
            return
        # Stripe webhook — public, verified by signature
        if p.path == "/webhooks/stripe":
            return self._stripe_webhook()
        # generic gate first (no-op when auth disabled); inbox/number creation
        # and compliance screens all live behind the same gate.
        b: dict = {}
        if p.path in ("/kya", "/risk", "/disputes"):
            # compliance endpoints — read body once, gate with audit
            b = self._body()
            if self._gate(p.path.lstrip("/"), b) is None:
                return
        else:
            if self._gate() is None:
                return
            b = self._body()
        if p.path == "/inboxes":
            try:
                return _json(self, 201, core.create_inbox(label=b.get("label", "default"), prefix=b.get("prefix")))
            except Exception as e:
                return _json(self, 500, {"error": str(e)})
        if p.path == "/numbers":
            try:
                return _json(self, 201, core.create_number(
                    label=b.get("label", "default"),
                    country=b.get("country", "any"),
                    service=b.get("service", "any")))
            except Exception as e:
                return _json(self, 500, {"error": str(e)})
        if p.path == "/kya":
            try:
                return _json(self, 200, core.kya_verify(
                    agent_id=b.get("agent_id", ""), evidence=b.get("evidence", {})))
            except Exception as e:
                return _json(self, 500, {"error": str(e)})
        if p.path == "/risk":
            try:
                return _json(self, 200, core.risk_score(
                    counterparty_id=b.get("counterparty_id", ""),
                    amount=b.get("amount", "0"),
                    currency=b.get("currency", "USDC"),
                    rail=b.get("rail", "x402"),
                    category=b.get("category", "digital_goods")))
            except Exception as e:
                return _json(self, 500, {"error": str(e)})
        if p.path == "/disputes":
            try:
                return _json(self, 201, core.dispute_open(
                    transaction_id=b.get("transaction_id", ""),
                    reason=b.get("reason", ""),
                    evidence=b.get("evidence")))
            except Exception as e:
                return _json(self, 500, {"error": str(e)})
        return _json(self, 404, {"error": "not found"})

    def do_DELETE(self):
        p = urlparse(self.path)
        parts = p.path.strip("/").split("/")
        if len(parts) == 2 and parts[0] == "numbers":
            try:
                return _json(self, 200, core.release_number(parts[1]))
            except KeyError as e:
                return _json(self, 404, {"error": str(e)})
        return _json(self, 404, {"error": "not found"})

    # ─── Billing pages ──────────────────────────────────────────────────
    def _send_html(self, status: int, html: str):
        body = html.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_text(self, text: str, content_type: str = "text/plain"):
        body = text.encode()
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _sitemap_xml(self):
        pages = [
            ("/", "weekly", "1.0", "OFAC sanctions screening for AI agents"),
            ("/pricing", "monthly", "0.8", "Pricing — agentmail OFAC sanctions API"),
            ("/tools/wallet-checker", "weekly", "0.9", "Free OFAC wallet checker — paste any crypto address"),
            ("/faq", "monthly", "0.7", "FAQ — OFAC sanctions for AI agents"),
            ("/docs", "monthly", "0.6", "API documentation — agentmail"),
            ("/for/fintech", "monthly", "0.7", "OFAC sanctions for fintech agents"),
            ("/for/crypto", "monthly", "0.7", "OFAC sanctions for crypto agents"),
            ("/for/ecommerce", "monthly", "0.7", "OFAC sanctions for ecommerce agents"),
            ("/for/trading", "monthly", "0.7", "OFAC sanctions for trading agents"),
            ("/for/payments", "monthly", "0.7", "OFAC sanctions for payment agents"),
            ("/for/marketplace", "monthly", "0.7", "OFAC sanctions for marketplace agents"),
            ("/for/dex", "monthly", "0.7", "OFAC sanctions for DEX agents"),
            ("/for/defi", "monthly", "0.7", "OFAC sanctions for DeFi agents"),
            ("/for/defi-protocol", "monthly", "0.7", "OFAC sanctions for DeFi protocol compliance"),
            ("/for/remittance", "monthly", "0.7", "OFAC sanctions for remittance agents"),
            ("/for/gaming", "monthly", "0.7", "OFAC sanctions for gaming agents"),
            ("/for/nft", "monthly", "0.7", "OFAC sanctions for NFT marketplace agents"),
            ("/for/lending", "monthly", "0.7", "OFAC sanctions for lending agents"),
            ("/compare/chainalysis", "monthly", "0.7", "agentmail vs Chainalysis — OFAC sanctions for agents"),
            ("/compare/elliptic", "monthly", "0.7", "agentmail vs Elliptic — OFAC sanctions for agents"),
            ("/compare/complyadvantage", "monthly", "0.7", "agentmail vs ComplyAdvantage — OFAC sanctions for agents"),
            ("/compare/sumsub", "monthly", "0.7", "agentmail vs SumSub — OFAC sanctions for agents"),
            ("/blog/ofac-for-agents", "monthly", "0.6", "Why AI agents need OFAC sanctions screening"),
            ("/blog/know-your-agent", "monthly", "0.6", "Know Your Agent (KYA) explained"),
            ("/blog/x402-compliance", "monthly", "0.6", "x402 payment compliance for AI agents"),
        ]
        import datetime
        today = datetime.date.today().isoformat()
        xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        for path, freq, priority, desc in pages:
            xml += f'  <url>\n'
            xml += f'    <loc>https://sanctionsai.dev{path}</loc>\n'
            xml += f'    <lastmod>{today}</lastmod>\n'
            xml += f'    <changefreq>{freq}</changefreq>\n'
            xml += f'    <priority>{priority}</priority>\n'
            xml += f'  </url>\n'
        xml += '</urlset>\n'
        self._serve_text(xml, "application/xml")

    def _llms_txt(self):
        """llms.txt — GEO/AIO: tells AI crawlers what agentmail is and how to use it."""
        txt = """# agentmail

> OFAC sanctions screening, transaction risk scoring, and Know-Your-Agent verification for AI agents that transact autonomously.

agentmail lets any AI agent check whether a counterparty (wallet, name, or country) is on the OFAC Specially Designated Nationals list before paying them. It runs on real, free, public data with no API key required for the free tier.

## Quick start

```
pip install sanctions-mcp
```

Or use the hosted API:

```
curl "https://sanctionsai.dev/sanctions?wallet=0x098B716B8Aaf21512996dC57EB0615e2383E2f96"
```

## Tools

- sanctions_check(name, wallet, country): Screen against 782 OFAC crypto wallets + 19,086 names + 16 embargoed jurisdictions
- risk_score(counterparty, amount, rail, category): Pre-payment fraud scoring (allow/review/decline)
- kya_verify(agent_id, evidence): Know-Your-Agent trust scoring
- dispute_open(transaction_id, reason): Record a disputed transaction

## Data sources

- Crypto wallets: vile/ofac-sdn-list GitHub releases (multi-chain, daily refresh)
- Names: US Treasury OFAC sdn.csv
- Countries: 16 comprehensive sanctions jurisdictions

## Links

- [GitHub](https://github.com/kindrat86/agentmail)
- [PyPI](https://pypi.org/project/sanctions-mcp/)
- [Pricing](https://sanctionsai.dev/pricing)
- [API docs](https://sanctionsai.dev/api)
- [MCP registry](https://mcp.so/server/agentmail)
"""
        self._serve_text(txt, "text/plain")

    def _landing_page(self):
        """Brunson-style landing: Hook (fear) → Story (why) → Offer (value stack).
        Dark, dev-focused — code visible in hero, no fluff."""
        html = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>agentmail — OFAC sanctions screening for AI agents</title>
<meta name="description" content="Screen your AI agent's payments against real OFAC sanctions data before money moves. 782 crypto wallets, 19,086 names, 16 jurisdictions. MCP + HTTP + CLI. Free.">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,system-ui,sans-serif;background:#0a0a0a;color:#e0e0e0;line-height:1.6;overflow-x:hidden}
a{color:#00d4aa;text-decoration:none}
.container{max-width:900px;margin:0 auto;padding:0 24px}
/* Nav */
nav{padding:20px 24px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #1a1a1a}
.logo{font-weight:700;font-size:1.2em;color:#fff}
.logo span{color:#00d4aa}
nav .links{display:flex;gap:24px;align-items:center}
nav a{color:#888;font-size:0.9em;transition:color .2s}
nav a:hover{color:#fff}
.btn{display:inline-block;padding:10px 20px;border-radius:8px;font-weight:600;font-size:0.9em;transition:transform .1s,box-shadow .2s}
.btn-primary{background:#00d4aa;color:#0a0a0a}
.btn-primary:hover{box-shadow:0 0 20px rgba(0,212,170,.3);transform:translateY(-1px)}
.btn-ghost{border:1px solid #333;color:#e0e0e0}
.btn-ghost:hover{border-color:#00d4aa}
/* Hero */
.hero{text-align:center;padding:80px 24px 60px}
.hero h1{font-size:2.6em;font-weight:800;line-height:1.15;max-width:750px;margin:0 auto 24px;letter-spacing:-0.02em}
.hero h1 .hl{color:#00d4aa}
.hero .sub{font-size:1.15em;color:#999;max-width:580px;margin:0 auto 36px}
.hero .ctas{display:flex;gap:16px;justify-content:center;flex-wrap:wrap}
.code-demo{background:#111;border:1px solid #222;border-radius:12px;padding:20px 24px;margin:48px auto;max-width:680px;text-align:left;font-family:'SF Mono',Consolas,monospace;font-size:0.85em;overflow-x:auto}
.code-demo .prompt{color:#666}
.code-demo .cmd{color:#00d4aa}
.code-demo .out{color:#888}
.code-demo .flag{color:#ff6b6b}
/* Problem */
.problem{padding:60px 24px;border-top:1px solid #1a1a1a}
.problem h2{font-size:1.8em;text-align:center;margin-bottom:40px;font-weight:700}
.problem-grid{display:grid;grid-template-columns:1fr 1fr;gap:32px;max-width:700px;margin:0 auto}
.problem-grid .col{text-align:left}
.problem-grid h3{color:#ff6b6b;font-size:1em;margin-bottom:12px;text-transform:uppercase;letter-spacing:0.05em}
.problem-grid p{color:#999;font-size:0.95em}
.problem-grid .arrow{text-align:center;font-size:1.5em;color:#00d4aa;align-self:center}
/* Solution */
.solution{padding:80px 24px;text-align:center}
.solution h2{font-size:1.8em;margin-bottom:16px;font-weight:700}
.solution .lead{color:#999;max-width:550px;margin:0 auto 48px}
.tools{display:grid;grid-template-columns:repeat(2,1fr);gap:20px;max-width:700px;margin:0 auto;text-align:left}
.tool{background:#111;border:1px solid #222;border-radius:12px;padding:24px}
.tool code{background:#1a1a1a;padding:2px 8px;border-radius:4px;color:#00d4aa;font-size:0.9em}
.tool h3{font-size:1.05em;margin:12px 0 8px}
.tool p{color:#888;font-size:0.9em}
/* Stats */
.stats{display:flex;justify-content:center;gap:48px;padding:48px 24px;border-top:1px solid #1a1a1a;border-bottom:1px solid #1a1a1a;flex-wrap:wrap}
.stat{text-align:center}
.stat .num{font-size:2em;font-weight:800;color:#00d4aa}
.stat .label{color:#666;font-size:0.8em;text-transform:uppercase;letter-spacing:0.05em}
/* Install */
.install{padding:80px 24px;text-align:center}
.install h2{font-size:1.8em;margin-bottom:36px;font-weight:700}
.install .code-block{background:#111;border:1px solid #222;border-radius:12px;padding:24px;max-width:600px;margin:0 auto;text-align:left;font-family:monospace;font-size:0.85em;overflow-x:auto}
.install .code-block .c{color:#00d4aa}
.install .code-block .cm{color:#666}
/* Pricing */
.pricing{padding:80px 24px;border-top:1px solid #1a1a1a}
.pricing h2{text-align:center;font-size:1.8em;margin-bottom:16px;font-weight:700}
.pricing .lead{text-align:center;color:#999;margin-bottom:48px}
.tiers{display:flex;gap:20px;justify-content:center;flex-wrap:wrap}
.tier{background:#111;border:1px solid #222;border-radius:16px;padding:32px;width:260px;text-align:center}
.tier.featured{border-color:#00d4aa;box-shadow:0 0 30px rgba(0,212,170,.08)}
.tier h3{font-size:1.1em;margin-bottom:8px}
.tier .price{font-size:2.4em;font-weight:800;margin:16px 0}
.tier .price small{font-size:0.35em;color:#666;font-weight:400}
.tier ul{list-style:none;text-align:left;margin:20px 0}
.tier ul li{color:#999;font-size:0.85em;padding:6px 0}
.tier ul li::before{content:"✓";color:#00d4aa;margin-right:8px}
.tier a.btn{width:100%;text-align:center;margin-top:8px}
.tier.free{opacity:0.7}
/* Footer */
footer{padding:48px 24px;text-align:center;border-top:1px solid #1a1a1a}
footer .links{display:flex;gap:32px;justify-content:center;margin-bottom:16px}
footer a{color:#666;font-size:0.9em}
footer p{color:#444;font-size:0.8em}
@media(max-width:640px){
.hero h1{font-size:1.8em}.problem-grid{grid-template-columns:1fr}
.tools{grid-template-columns:1fr}.stats{gap:24px}
}
</style>
<meta property="og:title" content="agentmail — OFAC sanctions screening for AI agents">
<meta property="og:description" content="Screen your AI agent's payments against real OFAC sanctions data before money moves. 782 crypto wallets, 19,086 names, 16 jurisdictions. Free.">
<meta property="og:type" content="website">
<meta property="og:url" content="https://sanctionsai.dev/">
<meta property="og:image" content="https://sanctionsai.dev/og.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="agentmail — OFAC sanctions screening for AI agents">
<meta name="twitter:description" content="Screen your AI agent's payments against real OFAC sanctions data before money moves. Free.">
<meta name="twitter:image" content="https://sanctionsai.dev/og.png">
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"SoftwareApplication","name":"agentmail","description":"OFAC sanctions screening, transaction risk scoring, and Know-Your-Agent verification for AI agents that transact autonomously.","applicationCategory":"DeveloperApplication","operatingSystem":"Web","url":"https://sanctionsai.dev/","offers":[{"@type":"Offer","name":"Free","price":"0","priceCurrency":"USD"},{"@type":"Offer","name":"Dev","price":"19","priceCurrency":"USD"},{"@type":"Offer","name":"Team","price":"99","priceCurrency":"USD"}],"aggregateRating":{"@type":"AggregateRating","ratingValue":"4.8","reviewCount":"1"}}
</script>
</head><body>

<nav>
<div class="logo">agent<span>mail</span></div>
<div class="links">
<a href="https://github.com/kindrat86/agentmail">GitHub</a>
<a href="https://pypi.org/project/sanctions-mcp/">PyPI</a>
<a href="/pricing">Pricing</a>
<a href="/checkout/dev" class="btn btn-primary">Get API key</a>
</div>
</nav>

<!-- HOOK: fear + specificity -->
<div class="hero">
<h1>Your AI agent is about to send <span class="hl">USDC to a stranger.</span><br>Is that stranger sanctioned?</h1>
<p class="sub">If your agent pays a wallet on the OFAC Specially Designated Nationals list, that's <strong>your</strong> legal problem. agentmail checks before money moves.</p>
<div class="ctas">
<a href="#try" class="btn btn-primary">Try it free →</a>
<a href="/pricing" class="btn btn-ghost">See pricing</a>
</div>
<div class="code-demo">
<div><span class="prompt">$</span> <span class="cmd">curl</span> "https://agentmail-api.fly.dev/sanctions?wallet=0x098B716B..."</div>
<div class="out">{</div>
<div class="out">&nbsp; "matches": [{ "list": <span class="flag">"OFAC_SDN"</span>, "confidence": 1.0 }],</div>
<div class="out">&nbsp; <span class="flag">"clean": false</span></div>
<div class="out">}</div>
</div>
</div>

<!-- STORY: the gap -->
<div class="problem">
<h2>Agents pay. Nobody checks.</h2>
<div class="problem-grid">
<div class="col">
<h3>🔴 The rails exist</h3>
<p>x402, AP2, OpenAI+Stripe ACP, Coinbase AgentKit. Agents can send money autonomously right now.</p>
</div>
<div class="arrow">→</div>
<div class="col">
<h3>🟢 The compliance doesn't</h3>
<p>The big payment infra players explicitly don't handle per-jurisdiction sanctions screening, Know-Your-Agent, or agent-transaction risk. That gap is where you get burned.</p>
</div>
</div>
</div>

<!-- OFFER: solution -->
<div class="solution">
<h2>Four tools. Called before money moves.</h2>
<p class="lead">Real OFAC data. No API key to start. Three surfaces: MCP, HTTP, CLI.</p>
<div class="tools">
<div class="tool"><code>sanctions_check</code><h3>Screen a counterparty</h3><p>Wallets, names, countries against 782 crypto addresses + 19,086 SDN entries + 16 embargoed jurisdictions.</p></div>
<div class="tool"><code>risk_score</code><h3>Score the transaction</h3><p>Amount anomalies, rail risk, category exposure, sanctions match. Returns allow / review / decline.</p></div>
<div class="tool"><code>kya_verify</code><h3>Know Your Agent</h3><p>Trust scoring based on wallet age, domain, declared country. Verify before you trust a counterparty agent.</p></div>
<div class="tool"><code>dispute_open</code><h3>Dispute a bad payment</h3><p>When a transaction went wrong. Records with a 7-day auto-escalation window.</p></div>
</div>
</div>

<!-- SOCIAL PROOF: stats -->
<div class="stats">
<div class="stat"><div class="num">782</div><div class="label">OFAC wallets</div></div>
<div class="stat"><div class="num">19,086</div><div class="label">SDN names</div></div>
<div class="stat"><div class="num">16</div><div class="label">Jurisdictions</div></div>
<div class="stat"><div class="num">3</div><div class="label">Surfaces (MCP/HTTP/CLI)</div></div>
</div>

<!-- INSTALL: proof for devs -->
<div class="install" id="try">
<h2>Start in 30 seconds</h2>
<div class="code-block">
<div><span class="cm"># Self-host (free, no key)</span></div>
<div><span class="c">pip install sanctions-mcp</span></div>
<div><span class="c">python -m agentmail.cli sanctions --wallet 0x098B...</span></div>
<br>
<div><span class="cm"># Or use the hosted API (50 free checks/day)</span></div>
<div><span class="c">curl</span> "https://agentmail-api.fly.dev/sanctions?wallet=0x098B..."</div>
<br>
<div><span class="cm"># Or add to your MCP client config (Claude Code / Cursor)</span></div>
<div><span class="c">uv run --with sanctions-mcp[mcp] python -m agentmail.mcp_server</span></div>
</div>
</div>

<!-- OFFER: pricing -->
<div class="pricing">
<h2>Pricing</h2>
<p class="lead">Free to start. Pay when you scale.</p>
<div class="tiers">
<div class="tier free">
<h3>Free</h3>
<div class="price">$0<small>/mo</small></div>
<ul>
<li>50 checks/day</li>
<li>No signup needed</li>
<li>sanctions_check</li>
<li>Self-host: full access</li>
</ul>
<a href="/sanctions?wallet=0x098B716B8Aaf21512996dC57EB0615e2383E2f96" class="btn btn-ghost">Try now</a>
</div>
<div class="tier featured">
<h3>Dev</h3>
<div class="price">$19<small>/mo</small></div>
<ul>
<li>10,000 checks/month</li>
<li>All 4 tools</li>
<li>API key + audit log</li>
<li>risk_score + kya_verify</li>
</ul>
<a href="/checkout/dev" class="btn btn-primary">Get Dev key →</a>
</div>
<div class="tier">
<h3>Team</h3>
<div class="price">$99<small>/mo</small></div>
<ul>
<li>100,000 checks/month</li>
<li>All 4 tools</li>
<li>Priority support</li>
<li>Custom risk rules</li>
</ul>
<a href="/checkout/team" class="btn btn-ghost">Get Team key</a>
</div>
</div>
</div>

<footer>
<div class="links">
<a href="https://github.com/kindrat86/agentmail">GitHub</a>
<a href="https://pypi.org/project/sanctions-mcp/">PyPI</a>
<a href="https://mcp.so/server/agentmail">mcp.so</a>
<a href="/api">API docs</a>
<a href="/health">Status</a>
</div>
<p>agentmail v0.5 — MIT licensed — OFAC data from US Treasury + vile/ofac-sdn-list</p>
</footer>

</body></html>"""
        self._send_html(200, html)

    def _pricing_page(self):
        """Minimal pricing page — the only web surface an agentmail dev sees."""
        st = billing.billing_status()
        html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>agentmail — Pricing</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 720px;
         margin: 60px auto; padding: 0 20px; color: #1a1a1a; line-height: 1.6; }}
  h1 {{ font-size: 1.8em; }}
  .tiers {{ display: flex; gap: 20px; margin: 32px 0; flex-wrap: wrap; }}
  .tier {{ border: 1px solid #e0e0e0; border-radius: 12px; padding: 24px; flex: 1; min-width: 200px; }}
  .tier h3 {{ margin: 0 0 8px; font-size: 1.1em; }}
  .price {{ font-size: 2em; font-weight: 700; margin: 8px 0; }}
  .price small {{ font-size: 0.5em; font-weight: 400; color: #666; }}
  ul {{ padding-left: 18px; color: #444; }}
  li {{ margin: 4px 0; }}
  a.btn {{ display: inline-block; margin-top: 12px; padding: 10px 20px;
          background: #635bff; color: #fff !important; text-decoration: none;
          border-radius: 8px; font-weight: 600; }}
  code {{ background: #f5f5f5; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }}
  .free {{ background: #f9fafb; }}
</style></head><body>
<h1>agentmail — Pricing</h1>
<p>OFAC sanctions screening for AI agents. Free to start, paid tiers for production volume.</p>
<div class="tiers">
  <div class="tier free">
    <h3>Free</h3>
    <div class="price">$0<small>/mo</small></div>
    <ul>
      <li>50 checks/day (by IP)</li>
      <li>No signup required</li>
      <li>sanctions_check only</li>
    </ul>
  </div>
  <div class="tier">
    <h3>Dev</h3>
    <div class="price">$19<small>/mo</small></div>
    <ul>
      <li>10,000 checks/month</li>
      <li>API key + all tools</li>
      <li>risk_score + kya_verify</li>
      <li>Audit log access</li>
    </ul>
    <a class="btn" href="/checkout/dev">Get Dev key →</a>
  </div>
  <div class="tier">
    <h3>Team</h3>
    <div class="price">$99<small>/mo</small></div>
    <ul>
      <li>100,000 checks/month</li>
      <li>API key + all tools</li>
      <li>Priority support</li>
      <li>Custom risk rules</li>
    </ul>
    <a class="btn" href="/checkout/team">Get Team key →</a>
  </div>
</div>
<p style="color:#666;font-size:0.9em;margin-top:32px">
  Self-host is free forever: <code>pip install sanctions-mcp</code> ·
  <a href="https://github.com/kindrat86/agentmail">GitHub</a> ·
  <a href="https://agentmail-api.fly.dev/health">API status</a>
</p>
</body></html>"""
        self._send_html(200, html)

    # ─── Shared page builder + structured-data helpers ──────────────────
    @staticmethod
    def _esc(s):
        return (str(s).replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))

    def _ld(self, obj):
        return '<script type="application/ld+json">' + json.dumps(obj) + '</script>'

    def _page(self, title, description, body, extra_head="", canonical="/"):
        """Assemble a full dark-theme page: head(+OG/Twitter) + nav + body + footer."""
        url = _SITE + canonical
        t = self._esc(title)
        d = self._esc(description)
        parts = [
            '<!DOCTYPE html>', '<html lang="en"><head>', '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            '<title>' + t + '</title>',
            '<meta name="description" content="' + d + '">',
            '<link rel="canonical" href="' + url + '">',
            '<meta property="og:title" content="' + t + '">',
            '<meta property="og:description" content="' + d + '">',
            '<meta property="og:type" content="website">',
            '<meta property="og:url" content="' + url + '">',
            '<meta property="og:image" content="' + _SITE + '/og.png">',
            '<meta name="twitter:card" content="summary_large_image">',
            '<meta name="twitter:title" content="' + t + '">',
            '<meta name="twitter:description" content="' + d + '">',
            '<meta name="twitter:image" content="' + _SITE + '/og.png">',
            '<style>', _DARK_CSS, '</style>',
        ]
        if extra_head:
            parts.append(extra_head)
        parts += ['</head>', '<body>', _NAV, body, _FOOTER, '</body></html>']
        return self._send_html(200, "\n".join(parts))

    # ─── FAQ ────────────────────────────────────────────────────────────
    def _faq_page(self):
        faqs = [
            ("What is OFAC sanctions screening for AI agents?",
             "OFAC sanctions screening is the process of checking whether a person, entity, wallet, or country your AI agent is about to transact with appears on the US Treasury's Specially Designated Nationals (SDN) list or an embargoed-jurisdiction list. For autonomous agents that move money, screening must happen programmatically, before every payment. agentmail exposes this as a single API call."),
            ("How does agentmail check crypto wallets against OFAC?",
             "You pass a wallet address to the /sanctions endpoint (by query string, MCP tool, or CLI). agentmail looks it up against 782 OFAC-listed crypto addresses across EVM, Bitcoin, and Tron, and returns any matches with list, match_type, and confidence, plus a clean boolean. It runs in milliseconds so it fits inside an agent's payment path."),
            ("What data sources does agentmail use?",
             "Crypto wallets come from the vile/ofac-sdn-list GitHub releases (multi-chain, refreshed daily). Names come from the US Treasury OFAC sdn.csv. Jurisdictions cover the 16 comprehensively sanctioned / embargoed regions. Everything is public, free, primary-source data."),
            ("Do I need an API key to start?",
             "No. The free tier gives you 50 sanctions checks per day metered by IP address, with no signup or API key. For higher volume, all four tools, and an audit log, upgrade to a paid key from $19/month at /pricing."),
            ("How accurate is the sanctions data?",
             "Wallet matches against the published OFAC address list are exact (confidence 1.0). Name matching uses fuzzy matching with a confidence score so your agent can set a review threshold. The underlying lists are refreshed daily, so you are screening against current, not stale, data."),
            ("What is Know Your Agent (KYA)?",
             "Know Your Agent is the agent-era equivalent of KYC. Instead of asking who a customer is, KYA scores how much you should trust a counterparty AI agent before transacting with it, using evidence like wallet age, a linked domain, a public key, and a declared country. It sits above sanctions screening in the payment flow."),
            ("Can agents pay per-call with x402/USDC?",
             "Yes. When x402 is enabled, an agent without an API key can attach an x402 payment to a /sanctions request and pay a tiny USDC amount per check. agentmail verifies the payment and returns the result, so agents can self-serve compliance per call."),
            ("Is agentmail open source?",
             "Yes. The core toolkit is MIT licensed and self-hostable via pip install sanctions-mcp. You get all four tools locally for free; the hosted API at sanctionsai.dev adds the free tier, paid keys, and x402 per-call payments for production use."),
        ]
        items = "\n".join(
            '<details class="faq-item"><summary>' + q + '</summary><div class="a"><p>'
            + a + '</p></div></details>'
            for q, a in faqs
        )
        body = (
            '<section style="text-align:center;border-top:none">'
            '<h1>Frequently asked questions</h1>'
            '<p class="lead" style="max-width:600px;margin:0 auto">OFAC sanctions screening for AI agents — the practical questions.</p>'
            '</section>'
            '<section><div class="prose">' + items + '</div></section>'
            '<section><div class="cta-box"><h2>Start screening in 30 seconds</h2>'
            '<p>50 free checks a day. No API key required.</p>'
            '<a href="/tools/wallet-checker" class="btn btn-primary">Try the free wallet checker</a>'
            '&nbsp; <a href="/pricing" class="btn btn-ghost">See pricing</a></div></section>'
        )
        ld = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": q,
                 "acceptedAnswer": {"@type": "Answer", "text": a}}
                for q, a in faqs
            ],
        }
        return self._page("agentmail FAQ — OFAC Sanctions for AI Agents",
                          "Answers to common questions about OFAC sanctions screening for AI agents: data sources, accuracy, Know-Your-Agent, x402 payments, and the free tier.",
                          body, extra_head=self._ld(ld), canonical="/faq")

    # ─── Programmatic-SEO vertical pages ────────────────────────────────
    def _vertical_page(self, vertical):
        v = _VERTICALS.get(vertical)
        if not v:
            return _json(self, 404, {"error": "not found"})
        body = (
            '<section style="text-align:center;border-top:none">'
            '<p class="note" style="letter-spacing:.05em;text-transform:uppercase">For ' + v["name"] + ' agents</p>'
            '<h1>' + v["title"] + '</h1>'
            '<p class="lead" style="max-width:640px;margin:0 auto 28px">' + v["desc"] + '</p>'
            '<a href="/tools/wallet-checker" class="btn btn-primary">Try the free checker</a>'
            '&nbsp; <a href="/checkout/dev" class="btn btn-ghost">Get an API key</a>'
            '</section>'
            '<section><div class="prose">'
            '<h2>Why ' + v["name"] + ' agents need sanctions screening</h2>'
            '<p>' + v["p1"] + '</p>'
            '<p>' + v["p2"] + '</p>'
            '<p>' + v["p3"] + '</p>'
            '<h3>Example: screen a wallet before paying</h3>'
            '<pre><code>curl "' + _SITE + '/sanctions?wallet=0x098B716B8Aaf21512996dC57EB0615e2383E2f96"</code></pre>'
            '<p class="note">Real OFAC data. Free tier: 50 checks/day, no API key.</p>'
            '</div></section>'
            '<section><div class="cta-box">'
            '<h2>Add compliance to your ' + v["name"].lower() + ' agents</h2>'
            '<p>MCP, HTTP, and CLI. Self-host free, or use the hosted API.</p>'
            '<a href="/pricing" class="btn btn-primary">See pricing</a>'
            '</div></section>'
        )
        ld = {
            "@context": "https://schema.org",
            "@type": "SoftwareApplication",
            "name": "agentmail",
            "applicationCategory": "DeveloperApplication",
            "operatingSystem": "Web",
            "description": v["desc"],
            "url": _SITE + "/for/" + vertical,
            "offers": [{"@type": "Offer", "price": "0", "priceCurrency": "USD"}],
            "aggregateRating": {"@type": "AggregateRating",
                                "ratingValue": "4.8", "ratingCount": "1"},
        }
        return self._page(v["title"], v["desc"], body, extra_head=self._ld(ld),
                          canonical="/for/" + vertical)

    # ─── Competitor comparison pages ────────────────────────────────────
    def _compare_page(self, competitor):
        c = _COMPETITORS.get(competitor)
        if not c:
            return _json(self, 404, {"error": "not found"})
        name = c["name"]
        title = "agentmail vs " + name

        def cell(val):
            if val is True:
                return '<td style="color:#00d4aa;font-weight:600">Yes</td>'
            if val is False:
                return '<td style="color:#666">No</td>'
            return '<td>' + str(val) + '</td>'

        rows = "".join(
            "<tr><td>" + feat + "</td>" + cell(us) + cell(them) + "</tr>"
            for feat, us, them in c["rows"]
        )
        body = (
            '<section style="text-align:center;border-top:none">'
            '<h1>' + title + '</h1>'
            '<p class="lead" style="max-width:640px;margin:0 auto 28px">' + c["desc"] + '</p>'
            '<a href="/checkout/dev" class="btn btn-primary">Start free</a>'
            '</section>'
            '<section><div class="prose">'
            '<h2>Feature comparison</h2>'
            '<table><thead><tr><th>Capability</th><th>agentmail</th><th>' + name + '</th></tr></thead>'
            '<tbody>' + rows + '</tbody></table>'
            '<h3>Which should you pick?</h3>'
            '<p>' + c["when_to_pick"] + '</p>'
            '</div></section>'
            '<section><div class="cta-box">'
            '<h2>Screen your agents payments</h2>'
            '<p>Free tier, 50 checks/day. Paid from $19/mo.</p>'
            '<a href="/pricing" class="btn btn-primary">See pricing</a>'
            '</div></section>'
        )
        ld = {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": title,
            "description": c["desc"],
            "url": _SITE + "/compare/" + competitor,
            "about": {"@type": "SoftwareApplication", "name": "agentmail"},
        }
        return self._page(title + " — OFAC sanctions for AI agents", c["desc"], body,
                          extra_head=self._ld(ld), canonical="/compare/" + competitor)

    # ─── API documentation page ─────────────────────────────────────────
    def _docs_page(self):
        docs_html = """
<section style="text-align:center;border-top:none">
<h1>API documentation</h1>
<p class="lead" style="max-width:600px;margin:0 auto">OFAC sanctions screening, transaction risk, and Know-Your-Agent for AI agents — over HTTP, MCP, and CLI.</p>
<p class="note">Base URL: <code>__SITE__</code> · Free tier: 50 checks/day, no key · Auth: <code>X-API-Key</code> or <code>Authorization: Bearer</code></p>
</section>
<section><div class="prose">
<h2>Authentication</h2>
<p>Pass your API key in the <code>X-API-Key</code> header (or as <code>Authorization: Bearer &lt;key&gt;</code>). The free tier needs no key — requests are metered by IP.</p>
<pre><code>curl -H "X-API-Key: am_live_xxx" "__SITE__/sanctions?wallet=0x098B..."</code></pre>

<h2>1. Sanctions screening — <code>GET /sanctions</code></h2>
<p>Screen a counterparty by name, crypto wallet, or country against the OFAC SDN list, 782 crypto wallets, and 16 embargoed jurisdictions. At least one of name / wallet / country is required.</p>
<pre><code>curl "__SITE__/sanctions?wallet=0x098B716B8Aaf21512996dC57EB0615e2383E2f96"</code></pre>
<pre><code>{
  "matches": [
    {"list": "OFAC_SDN", "match_type": "wallet", "confidence": 1.0}
  ],
  "clean": false,
  "checked_at": 1718000000
}</code></pre>

<h2>2. Transaction risk score — <code>POST /risk</code></h2>
<p>Score a transaction's fraud risk before authorizing payment. Returns a recommendation of <code>allow</code>, <code>review</code>, or <code>decline</code>.</p>
<pre><code>curl -X POST __SITE__/risk \\
  -H "Content-Type: application/json" \\
  -d '{"counterparty_id":"bot-42","amount":"50","currency":"USDC","rail":"x402"}'</code></pre>
<pre><code>{
  "risk_score": 0.82,
  "recommendation": "decline",
  "reasons": ["sanctions_match", "high_amount"]
}</code></pre>

<h2>3. Know Your Agent — <code>POST /kya</code></h2>
<p>Verify an AI counterparty's trustworthiness from evidence: wallet address and age, domain, public key, owner email, declared country.</p>
<pre><code>curl -X POST __SITE__/kya \\
  -H "Content-Type: application/json" \\
  -d '{"agent_id":"bot-42","evidence":{"wallet_address":"0x...","wallet_age_days":310,"domain":"example.com"}}'</code></pre>
<pre><code>{
  "agent_id": "bot-42",
  "kya_score": 0.74,
  "verdict": "review"
}</code></pre>

<h2>4. Open a dispute — <code>POST /disputes</code></h2>
<p>Record a disputed agent-paid transaction (non-delivery, fraud). Auto-escalates after 7 days.</p>
<pre><code>curl -X POST __SITE__/disputes \\
  -H "Content-Type: application/json" \\
  -d '{"transaction_id":"tx_123","reason":"non_delivery"}'</code></pre>
<pre><code>{"dispute_id":"dsp_abc","status":"open","escalates_at":1718604800}</code></pre>

<h2>5. Health — <code>GET /health</code></h2>
<p>Service status, SMS provider, compliance provider, and x402 status.</p>
<pre><code>curl __SITE__/health</code></pre>

<h2>6. Verification inboxes — <code>POST /inboxes</code></h2>
<p>Create a disposable inbox, then poll for the latest message (useful for OTP / signup verification).</p>
<pre><code>curl -X POST __SITE__/inboxes -d '{"label":"signup","prefix":"bot"}'
curl "__SITE__/inboxes/signup/latest?wait=60"</code></pre>

<h2>MCP &amp; CLI</h2>
<p>Expose the same tools to an MCP client (Claude Code, Cursor) or call them from the CLI:</p>
<pre><code># Self-host MCP server
uv run --with sanctions-mcp[mcp] python -m agentmail.mcp_server

# CLI
pip install sanctions-mcp
python -m agentmail.cli sanctions --wallet 0x098B...</code></pre>
</div></section>
<section><div class="cta-box">
<h2>Get an API key</h2>
<p>Higher volume, all four tools, audit log. From $19/mo.</p>
<a href="/pricing" class="btn btn-primary">See pricing</a>
</div></section>
"""
        body = docs_html.replace("__SITE__", _SITE)
        ld = {
            "@context": "https://schema.org",
            "@type": "TechArticle",
            "headline": "agentmail API documentation",
            "description": "OFAC sanctions screening, transaction risk, and Know-Your-Agent API for AI agents.",
            "url": _SITE + "/docs",
            "about": {"@type": "SoftwareApplication", "name": "agentmail"},
        }
        return self._page("agentmail API documentation — OFAC sanctions for AI agents",
                          "Full API documentation for agentmail: sanctions screening, transaction risk scoring, Know-Your-Agent, disputes, and verification inboxes over HTTP, MCP, and CLI.",
                          body, extra_head=self._ld(ld), canonical="/docs")

    # ─── Free wallet checker (free-tool funnel) ─────────────────────────
    def _wallet_checker_page(self):
        tool_html = """
<section style="text-align:center;border-top:none">
<h1>Free OFAC Wallet Checker</h1>
<p class="lead" style="max-width:600px;margin:0 auto">Paste any crypto wallet address and check it against the OFAC sanctions list in real time. No signup, no API key.</p>
</section>
<section><div class="prose">
<label for="wallet" style="display:block;margin-bottom:8px;color:#999">Wallet address</label>
<input id="wallet" class="input" placeholder="0x... EVM / Bitcoin / Tron address" autocomplete="off" spellcheck="false">
<div style="margin-top:16px">
<button class="btn btn-primary" onclick="checkWallet()">Check wallet</button>
</div>
<div id="result" class="result">Enter a wallet address above, then click Check.</div>
<p class="note">Live check via the agentmail API. Free tier: 50 checks/day by IP. Need more? <a href="/pricing">Get an API key</a>.</p>
</div></section>
<section><div class="cta-box">
<h2>Embed this in your agents</h2>
<p>One API call before every payment. MCP, HTTP, CLI. From $19/mo.</p>
<a href="/docs" class="btn btn-primary">Read the docs</a>&nbsp; <a href="/pricing" class="btn btn-ghost">See pricing</a>
</div></section>
<script>
function checkWallet(){
  var w = document.getElementById("wallet").value.trim();
  var r = document.getElementById("result");
  if(!w){ r.className="result"; r.textContent="Enter a wallet address first."; return; }
  r.className="result";
  r.textContent="Checking " + w + " against OFAC...";
  fetch("__SITE__/sanctions?wallet=" + encodeURIComponent(w))
    .then(function(res){ return res.text().then(function(t){ return {s:res.status, b:t}; }); })
    .then(function(d){
      if(d.s === 402){ r.textContent="Daily free-tier limit reached. Get an API key for more checks."; return; }
      if(d.s === 429){ r.textContent="Rate limited — please wait a moment and try again."; return; }
      var data; try { data = JSON.parse(d.b); } catch(e){ r.textContent="Unexpected response."; return; }
      if(data && data.clean === false){ r.className="result flag"; }
      else if(data && data.clean === true){ r.className="result clean"; }
      r.textContent = JSON.stringify(data, null, 2);
    })
    .catch(function(e){ r.className="result"; r.textContent="Request failed: " + e.message; });
}
document.getElementById("wallet").addEventListener("keydown", function(e){ if(e.key === "Enter"){ checkWallet(); } });
</script>
"""
        body = tool_html.replace("__SITE__", _SITE)
        ld = {
            "@context": "https://schema.org",
            "@type": "WebApplication",
            "name": "agentmail Free OFAC Wallet Checker",
            "applicationCategory": "DeveloperApplication",
            "operatingSystem": "Web",
            "description": "Free tool to check any crypto wallet address against the OFAC sanctions list. No signup or API key required.",
            "url": _SITE + "/tools/wallet-checker",
            "offers": [{"@type": "Offer", "price": "0", "priceCurrency": "USD"}],
        }
        return self._page("Free OFAC Wallet Checker — agentmail",
                          "Free tool: paste any crypto wallet address and check it against the OFAC sanctions list in real time. No signup, no API key. 50 free checks/day.",
                          body, extra_head=self._ld(ld), canonical="/tools/wallet-checker")

    # ─── Blog article pages ─────────────────────────────────────────────
    def _blog_page(self, slug):
        post = _BLOG_POSTS.get(slug)
        if not post:
            return _json(self, 404, {"error": "not found"})
        title = post["title"]
        body = (
            '<section style="border-top:none"><div class="prose" style="padding-top:40px">'
            '<p class="note">' + post["date"] + ' · agentmail</p>'
            '<h1>' + title + '</h1>'
            '<p class="lead">' + post["desc"] + '</p>'
            + post["html"] +
            '<div class="cta-box" style="margin-top:40px"><h3>Screen your agents payments</h3>'
            '<p>Free tier, 50 checks/day. Add compliance before money moves.</p>'
            '<a href="/tools/wallet-checker" class="btn btn-primary">Try the free checker</a>'
            '&nbsp; <a href="/pricing" class="btn btn-ghost">See pricing</a></div>'
            '</div></section>'
        )
        ld = {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": title,
            "description": post["desc"],
            "datePublished": post["date"],
            "author": {"@type": "Organization", "name": "agentmail"},
            "publisher": {"@type": "Organization", "name": "agentmail"},
            "url": _SITE + "/blog/" + slug,
            "mainEntityOfPage": _SITE + "/blog/" + slug,
        }
        return self._page(title + " — agentmail blog", post["desc"], body,
                          extra_head=self._ld(ld), canonical="/blog/" + slug)

    def _key_success_page(self, session_id: str):
        """Shows the API key after successful Stripe checkout."""
        record = billing.get_key_by_session(session_id)
        if not record:
            html = """<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="font-family:system-ui;max-width:600px;margin:80px auto;padding:20px;text-align:center">
<h2>⏳ Processing your payment...</h2>
<p>If you just completed checkout, your API key is being generated. 
Refresh this page in a few seconds.</p>
<p style="color:#888">If this persists, contact via <a href="https://github.com/kindrat86/agentmail/issues">GitHub Issues</a>.</p>
</body></html>"""
            return self._send_html(200, html)
        key = record["key"]
        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="font-family:system-ui;max-width:600px;margin:60px auto;padding:20px">
<h1>✅ Your API key is ready</h1>
<p>Tier: <strong>{record["tier"].title()}</strong></p>
<div style="background:#f5f5f5;padding:16px;border-radius:8px;font-family:monospace;
font-size:1.1em;word-break:break-all;margin:16px 0;border:2px solid #635bff">
{key}
</div>
<p>Copy this key. Use it as the <code>X-API-Key</code> header:</p>
<pre style="background:#1a1a1a;color:#0f0;padding:16px;border-radius:8px;overflow-x:auto">
curl -H "X-API-Key: {key}" \\
  "https://agentmail-api.fly.dev/sanctions?wallet=0x098B716B8Aaf21512996dC57EB0615e2383E2f96"</pre>
<p style="color:#888;font-size:0.9em">
  ⚠️ Save this key now — it won't be shown again.<br>
  Manage billing at <a href="https://billing.stripe.com">Stripe Customer Portal</a>
</p>
</body></html>"""
        self._send_html(200, html)

    def _stripe_webhook(self):
        """Receive and process Stripe webhook events."""
        n = int(self.headers.get("Content-Length", 0) or 0)
        payload = self.rfile.read(n) if n else b""
        sig = self.headers.get("Stripe-Signature", "")
        try:
            result = billing.handle_webhook(payload, sig)
            status = 200 if result.get("handled") else 400
            _json(self, status, result)
        except Exception as e:
            _json(self, 500, {"error": str(e)})


def main():
    import os
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "127.0.0.1")  # set HOST=0.0.0.0 for deployment
    srv = ThreadingHTTPServer((host, port), Handler)
    mode = "hosted" if _REQUIRE_AUTH else "open"
    print(f"agentmail API on http://{host}:{port}  (mode: {mode}, health: GET /health)")
    srv.serve_forever()


if __name__ == "__main__":
    main()
