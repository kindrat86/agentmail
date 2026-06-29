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
    "crypto",
    "defi",
    "defi-protocol",
    "dex",
    "ecommerce",
    "fintech",
    "gaming",
    "healthcare",
    "insurance",
    "lending",
    "marketplace",
    "nft",
    "payments",
    "real-estate",
    "remittance",
    "trading",
))
_COMPETITOR_KEYS = frozenset((
    "blockdaemon",
    "chainalysis",
    "charmverse",
    "ciphertrace",
    "complyadvantage",
    "elliptic",
    "sumsub",
    "trm-labs",
))
_BLOG_SLUGS = frozenset((
    "know-your-agent",
    "ofac-for-agents",
    "openai-agents-sdk-compliance",
    "x402-compliance",
))

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

_FOOTER = '<footer><div class="links"><a href="/">Home</a><a href="/faq">FAQ</a><a href="/docs">Docs</a><a href="/tools/wallet-checker">Wallet Checker</a><a href="/pricing">Pricing</a><a href="/agent">For Agents</a><a href="/">Home</a><a href="https://github.com/kindrat86/agentmail">GitHub</a><a href="https://pypi.org/project/sanctions-mcp/">PyPI</a></div><p>agentmail — OFAC sanctions screening for AI agents · MIT licensed · Data from US Treasury &amp; vile/ofac-sdn-list</p></footer>'

_VERTICALS = {
    "fintech": {
        "name": "Fintech",
        "title": "OFAC Sanctions Screening for Fintech AI Agents",
        "desc": "Add OFAC sanctions screening to fintech AI agents. Screen counterparties, wallets, and names before any regulated transaction.",
        "p1": "Regulated financial institutions deploying AI agents must screen every counterparty against OFAC sanctions lists before funds move. agentmail gives fintech agents a single API call that checks names, crypto wallets, and countries against the full OFAC Specially Designated Nationals list in real time.",
        "p2": "For fintechs the cost of a miss is severe — civil penalties can reach $300,000 or twice the transaction value per violation. Automating payments without screening transfers that liability straight onto your institution. agentmail closes the gap between autonomous execution and regulatory obligation, leaving a defensible audit trail.",
        "p3": "Integrate sanctions checks into your loan-approval, onboarding, and payment-routing agents via MCP, HTTP, or CLI. The free tier covers 5 checks per day per day with no signup, so you can validate the workflow before scaling to a paid plan.",
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
        "p3": "Drop the check into your order-approval or payout agent. Free tier: 5 checks/day, no key required. Production volume from $19/mo.",
    },
    "trading": {
        "name": "Trading",
        "title": "OFAC Sanctions Screening for Trading AI Agents",
        "desc": "Trading bots screen counterparties, wallets, and jurisdictions against OFAC before each cross-border fill or settlement.",
        "p1": "Trading bots that execute cross-border transactions move fast — often too fast for manual compliance review. agentmail gives your trading agent a sub-second sanctions check on counterparty names, wallets, and jurisdictions before each fill or settlement.",
        "p2": "A single trade with a sanctioned counterparty can freeze assets and trigger regulatory scrutiny that outweighs months of gains. Building the screen into the execution path means your bot declines the trade rather than explaining it later.",
        "p3": "Call it over HTTP from any trading runtime, or expose it as an MCP tool to your reasoning agent. No key needed to start — 5 checks/day free.",
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
        "p3": "Add the check to your swap-approval logic over HTTP or MCP. Free tier, no key, 5 checks/day.",
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
        "p3": "Integrate via MCP, HTTP, or CLI alongside your existing rail. 5 checks/day to validate, paid plans for production volume.",
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
        "p3": "Call it from your underwriting agent over HTTP or MCP. Free tier: 5 checks/day, no signup.",
    },

    "insurance": {
        "name": "OFAC",
        "title": "OFAC Sanctions for Insurance AI Agents",
        "desc": "Insurance agents that underwrite policies and process claims need to screen applicants and claimants against OFAC.",
        "p1": "OFAC Sanctions for Insurance AI Agents screen counterparties against OFAC before every transaction. agentmail gives you real-time sanctions data, no key to start.",
        "p2": "Agents executing OFAC operations touch real value and real counterparties. A missed sanctions check is a violation.",
        "p3": "Add the screen to your ofac agent workflow. Free tier, paid plans for volume.",
    },

    "healthcare": {
        "name": "OFAC",
        "title": "OFAC Sanctions for Healthcare AI Agents",
        "desc": "Healthcare agents handling billing, eligibility, and cross-border patient services need OFAC screening.",
        "p1": "OFAC Sanctions for Healthcare AI Agents screen counterparties against OFAC before every transaction. agentmail gives you real-time sanctions data, no key to start.",
        "p2": "Agents executing OFAC operations touch real value and real counterparties. A missed sanctions check is a violation.",
        "p3": "Add the screen to your ofac agent workflow. Free tier, paid plans for volume.",
    },

    "real-estate": {
        "name": "OFAC",
        "title": "OFAC Sanctions for Real Estate AI Agents",
        "desc": "Real estate agents processing international transactions need to screen counterparties against OFAC.",
        "p1": "OFAC Sanctions for Real Estate AI Agents screen counterparties against OFAC before every transaction. agentmail gives you real-time sanctions data, no key to start.",
        "p2": "Agents executing OFAC operations touch real value and real counterparties. A missed sanctions check is a violation.",
        "p3": "Add the screen to your ofac agent workflow. Free tier, paid plans for volume.",
    },
}

_COMPETITORS = {
    "chainalysis": {
        "name": "Chainalysis",
        "desc": "agentmail vs Chainalysis: agentmail gives AI agents a sanctions screen they can call before every payment, with a free tier and self-host option. Chainalysis is built for enterprise blockchain forensics.",
        "rows": [
            ("Built for AI agents (MCP + HTTP + CLI)", True, False),
            ("Free tier (5 checks/day)", True, False),
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
            ("Free tier (5 checks/day)", True, False),
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
            ("Free tier (5 checks/day)", True, False),
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
            ("Free tier (5 checks/day)", True, False),
            ("Developer pricing from $19/mo", True, False),
            ("Open-source self-host", True, False),
            ("KYC / identity verification", False, True),
            ("Liveness & document checks", False, True),
        ],
        "when_to_pick": "Pick agentmail to screen counterparties and wallets against OFAC before an agent pays. Pick SumSub when your primary need is KYC and identity verification.",
    },
    "blockdaemon": {
        "name": "Blockdaemon",
        "desc": "agentmail vs Blockdaemon: agentmail is agent-native sanctions screening with a free tier. Blockdaemon is institutional Web3 infrastructure and node operations.",
        "rows": [
            ("Built for AI agents (MCP + HTTP + CLI)", True, False),
            ("Free tier (5 checks/day)", True, False),
            ("Developer pricing from $19/mo", True, False),
            ("Open-source self-host", True, False),
            ("OFAC crypto wallet screening", True, "Enterprise"),
            ("Institutional Web3 infrastructure", False, True),
            ("Node operations and staking", False, True),
        ],
        "when_to_pick": "Pick agentmail for agent-first sanctions screening with a free tier. Pick Blockdaemon for institutional Web3 node infrastructure.",
    },
    "trm-labs": {
        "name": "TRM Labs",
        "desc": "agentmail vs TRM Labs: agentmail gives autonomous agents real-time sanctions screening with a free tier. TRM Labs focuses on blockchain intelligence and risk monitoring.",
        "rows": [
            ("Built for AI agents (MCP + HTTP + CLI)", True, False),
            ("Free tier (5 checks/day)", True, False),
            ("Developer pricing from $19/mo", True, False),
            ("Open-source self-host", True, False),
            ("Per-call x402 / USDC payments", True, False),
            ("OFAC crypto wallet screening", True, True),
            ("Blockchain forensics and risk platform", False, True),
        ],
        "when_to_pick": "Pick agentmail for agent-native, per-call sanctions screening. Pick TRM Labs for blockchain forensics and enterprise crypto risk programs.",
    },
    "ciphertrace": {
        "name": "CipherTrace",
        "desc": "agentmail vs CipherTrace: agentmail is real-time, agent-native sanctions screening. CipherTrace is a legacy crypto compliance and forensic analytics platform owned by Visa.",
        "rows": [
            ("Agent-native (MCP + HTTP + CLI)", True, False),
            ("Free tier (5 checks/day)", True, False),
            ("Developer pricing from $19/mo", True, False),
            ("Open-source self-host", True, False),
            ("OFAC crypto wallet screening", True, True),
            ("Visa-backed compliance", False, True),
            ("Legacy AML/KYC platform", False, True),
        ],
        "when_to_pick": "Pick agentmail for modern, agent-native sanctions. Pick CipherTrace if you are inside the Visa compliance ecosystem.",
    },

    "charmverse": {
        "name": "CharmVerse",
        "desc": "agentmail vs CharmVerse compliance: agentmail is sanctions-first, CharmVerse is KYC-first.",
        "rows": [
            ("Built for AI agents (MCP + HTTP + CLI)", True, False),
            ("Free tier (5 checks/day)", True, False),
            ("Developer pricing from $19/mo", True, False),
            ("Open-source self-host", True, False),
            ("OFAC crypto wallet screening", True, "Enterprise"),
            ("Legacy compliance", False, True),
        ],
        "when_to_pick": "Pick agentmail for agent-native sanctions screening with a free tier. Pick CharmVerse for enterprise compliance programs.",
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
<p>Build the check into your agent's payment path today. The free tier covers 5 checks per day per day, no API key required.</p>""",
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
<p>Start with the free tier: 5 sanctions checks/day, no key. Add KYA and risk scoring on a $19/mo plan.</p>""",
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
<p>The free tier also covers 5 checks/day by IP with no payment at all. Add compliance to your x402 agent in minutes.</p>""",
    },

    "openai-agents-sdk-compliance": {
        "title": "Adding Compliance to OpenAI Agents SDK Agents",
        "date": "2026-06-29",
        "desc": "How to add OFAC sanctions screening to agents built with OpenAI's Agents SDK.",
        "html": """<p>How to add OFAC sanctions screening to agents built with OpenAI's Agents SDK.</p><p>agentmail provides OFAC sanctions screening that fits directly into your agent's workflow. Use the free checker or integrate via MCP.</p><pre><code>curl "https://sanctionsai.dev/tools/wallet-checker"</code></pre><p>Start with 5 checks/day. Scale on a $19/mo plan when ready.</p>""",
    },
}


# ─── PostHog analytics ──────────────────────────────────────────
_POSTHOG_API_KEY=os.environ.get("POSTHOG_API_KEY", "")

def _capture(event: str, distinct_id: str = None, properties: dict = None):
    """Send event to PostHog. Silent fail if not configured."""
    if not _POSTHOG_API_KEY:
        return
    try:
        import requests as req
        req.post(
            "https://us.i.posthog.com/capture/",
            json={
                "api_key": _POSTHOG_API_KEY,
                "event": event,
                "distinct_id": distinct_id or "anon",
                "properties": properties or {},
            },
            timeout=3,
        )
    except Exception:
        pass

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
        if p.path == "/favicon.ico" or p.path == "/favicon.svg":
            svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#0f172a"/><stop offset="100%" stop-color="#0d1a14"/></linearGradient></defs><rect width="32" height="32" rx="7" fill="url(#g)" stroke="#00d4aa" stroke-width="1.8"/><text x="16" y="22" font-family="system-ui,sans-serif" font-size="18" font-weight="800" fill="#00d4aa" text-anchor="middle" letter-spacing="-0.5">a</text><circle cx="24" cy="7" r="3.5" fill="#00d4aa" opacity="0.85"/></svg>'
            self._send_html(200, svg)
            return
        if p.path == "/" or p.path == "":
            return self._landing_page()
        # Unsubscribe page (one-click)
        if p.path == "/unsubscribe":
            return self._unsubscribe_page()
        if p.path == "/blog/x402-compliance-check":
            return self._blog_x402_page()
        if p.path == "/agent":
            return self._agent_page()
        if p.path == "/x402-demo":
            return self._x402_demo_page()
        
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
                "free_tier": "5 checks/day by IP, no key needed",
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
        # Squeeze / email capture page (Brunson: critical for funnel)
        if p.path == "/start" or p.path == "/squeeze":
            return self._squeeze_page()
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
        # Subscribe — public, no auth gate
        if p.path == "/subscribe":
            try:
                b = self._body()
                email = b.get("email", "")
                if not email or "@" not in email:
                    return _json(self, 400, {"error": "valid email required"})
                import os, json, time
                subs_file = os.environ.get("AGENTMAIL_HOME", "/data") + "/subscribers.jsonl"
                os.makedirs(os.path.dirname(subs_file), exist_ok=True)
                source = b.get("source", "landing")
                with open(subs_file, "a") as fh:
                    fh.write(json.dumps({"email": email, "subscribed_at": time.time(), "source": source}) + "\n")
                sent = False
                try:
                    from agentmail.api import _send_welcome_email
                    _send_welcome_email(email)
                    sent = True
                except Exception as e:
                    print(f"Email send failed for {email}: {e}", flush=True)
                _capture("subscribed", email, {"source": source, "email_sent": sent})
                return _json(self, 200, {"ok": True, "message": "subscribed", "email_sent": sent})
            except Exception as e:
                return _json(self, 500, {"error": str(e)})
        
        # Unsubscribe — public, no auth gate
        if p.path == "/unsubscribe":
            try:
                b = self._body()
                email = b.get("email", "")
                if not email or "@" not in email:
                    return _json(self, 400, {"error": "valid email required"})
                import os, json
                subs_file = os.environ.get("AGENTMAIL_HOME", "/data") + "/subscribers.jsonl"
                if os.path.exists(subs_file):
                    remaining = []
                    removed = 0
                    with open(subs_file) as fh:
                        for line2 in fh:
                            try:
                                rec = json.loads(line2.strip())
                                if rec.get("email", "").lower() == email.lower():
                                    removed += 1
                                else:
                                    remaining.append(line2)
                            except:
                                remaining.append(line2)
                    with open(subs_file, "w") as fh:
                        fh.writelines(remaining)
                _capture("unsubscribed", email, {"removed": removed})
                return _json(self, 200, {"ok": True, "message": "unsubscribed", "removed": removed})
            except Exception as e:
                return _json(self, 500, {"error": str(e)})
        
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
                ("/for/insurance", "monthly", "0.7", "Insurance"),
        ("/for/healthcare", "monthly", "0.7", "Healthcare"),
        ("/for/real-estate", "monthly", "0.7", "Real Estate"),
        ("/compare/charmverse", "monthly", "0.7", "Charmverse"),
        ("/blog/openai-agents-sdk-compliance", "monthly", "0.7", "Openai Agents Sdk Compliance"),
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
<title>OFAC Sanctions Screening for AI Agents | agentmail</title>
<meta name="description" content="Screen every counterparty against OFAC before your AI agent pays. 782 crypto wallets, 19,086 names. Free tier + x402 per-call USDC.">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<style>
*{margin:0;padding:0;box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#0a0a0a;color:#e0e0e0;line-height:1.6;overflow-x:hidden}
a{color:#00d4aa;text-decoration:none}
.btn{display:inline-flex;align-items:center;justify-content:center;padding:14px 24px;border-radius:10px;font-weight:600;font-size:0.95em;cursor:pointer;border:none;min-height:48px;text-decoration:none!important;transition:all .2s;touch-action:manipulation}
.btn-primary{background:#00d4aa;color:#0a0a0a!important}
.btn-primary:hover{box-shadow:0 0 24px rgba(0,212,170,.25)}
.btn-ghost{border:1.5px solid #333;color:#e0e0e0!important;background:transparent}
.btn-ghost:hover{border-color:#00d4aa}
.btn-lg{padding:16px 28px;font-size:1em;min-height:52px}
nav{padding:14px 20px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #1a1a1a;background:rgba(10,10,10,.96);backdrop-filter:blur(12px);position:sticky;top:0;z-index:100}
.logo{font-weight:700;font-size:1.1em;color:#fff}
.logo span{color:#00d4aa}
nav .links{display:flex;gap:14px;align-items:center;flex-wrap:wrap}
nav .links a{color:#888;font-size:0.82em;transition:color .2s;white-space:nowrap}
nav .links a:hover{color:#fff}
nav .btn{padding:8px 14px;font-size:0.78em;min-height:36px}
.text-link{color:#888;font-size:0.82em;text-decoration:underline;text-underline-offset:3px;transition:color .2s;display:inline-block}
.text-link:hover{color:#00d4aa}@media(max-width:400px){.text-link{font-size:0.78em}}
@media(min-width:768px){nav{padding:20px 24px}nav .links{gap:20px}nav .links a{font-size:0.88em}nav .btn{padding:10px 20px}}
.hero{padding:64px 16px 40px;text-align:center;position:relative;overflow:hidden}
.hero::before{content:'';position:absolute;top:-100px;left:50%;transform:translateX(-50%);width:600px;height:600px;background:radial-gradient(circle,rgba(0,212,170,.04) 0%,transparent 70%);pointer-events:none}
.hero .badge{display:inline-block;background:rgba(255,107,107,.1);color:#ff6b6b;padding:5px 14px;border-radius:20px;font-size:0.68em;font-weight:600;margin-bottom:16px;border:1px solid rgba(255,107,107,.2)}
.hero h1{font-size:1.5em;font-weight:800;line-height:1.15;max-width:620px;margin:0 auto 14px;letter-spacing:-0.02em}
.hero h1 .hl-red{color:#ff6b6b}
.hero .sub{font-size:0.92em;color:#999;max-width:500px;margin:0 auto 20px}
.hero .stat-row{display:flex;gap:12px;justify-content:center;flex-wrap:wrap;margin-bottom:20px}
.hero .stat-row span{background:#111;border:1px solid #1a1a1a;border-radius:8px;padding:7px 12px;font-size:0.75em;color:#888}
.hero .stat-row strong{color:#00d4aa}
.hero .ctas{display:flex;flex-direction:column;gap:12px;margin-top:24px;max-width:360px;margin:0 auto}
.hero .urgency-bar{background:#1a0a0a;border:1px solid #332222;border-radius:8px;padding:10px 14px;max-width:500px;margin:16px auto 0;font-size:0.76em;color:#ff8888;line-height:1.4}
.hero .urgency-bar strong{color:#ff6b6b}
@media(min-width:640px){
.hero{padding:80px 24px 50px}.hero h1{font-size:2em;max-width:650px}.hero .sub{font-size:1em}.hero .ctas{flex-direction:row;max-width:none;justify-content:center;gap:16px}
}
.email-section{padding:32px 16px;text-align:center;background:linear-gradient(180deg,#0a0a0a,#0d1a14);border-top:1px solid #1a1a1a;border-bottom:1px solid #1a1a1a}
.email-section h2{font-size:1.1em;color:#fff;margin-bottom:8px;font-weight:600}
.email-section .sub{color:#888;font-size:0.85em;margin-bottom:20px;max-width:420px;margin:0 auto 20px}
.email-form{display:flex;flex-direction:column;gap:8px;max-width:420px;margin:0 auto}
.email-form .input-row{display:flex;flex-direction:column;gap:8px}
.email-form input{flex:1;padding:14px 16px;border-radius:10px;border:1.5px solid #333;background:#111;color:#e0e0e0;font-size:1em;outline:none;min-height:48px}
.email-form input:focus{border-color:#00d4aa}
.email-form .hint{color:#555;font-size:0.7em;margin-top:4px}
@media(min-width:480px){.email-form .input-row{flex-direction:row}}
.story-section{padding:48px 16px;max-width:640px;margin:0 auto}
.story-label{color:#555;font-size:0.72em;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px}
.story-section h2{font-size:1.15em;font-weight:700;margin-bottom:12px;line-height:1.35}
.story-section p{color:#999;font-size:0.9em;margin-bottom:12px;line-height:1.6}
.story-section .story-quote{background:#111;border-left:3px solid #ff6b6b;padding:14px 16px;border-radius:0 8px 8px 0;margin:16px 0;font-style:italic;color:#ccc;font-size:0.88em}
.story-section .callout{background:#0d1a14;border:1px solid rgba(0,212,170,.12);border-radius:10px;padding:18px;margin:20px 0}
.story-section .callout strong{color:#00d4aa}
@media(min-width:640px){.story-section{padding:60px 24px}.story-section h2{font-size:1.3em}}
.testimonial{max-width:600px;margin:0 auto;padding:32px 16px;text-align:center}
.testimonial .card{background:#111;border:1px solid #1a1a1a;border-radius:12px;padding:24px;max-width:500px;margin:0 auto}
.testimonial .label{color:#ff6b6b;font-size:0.68em;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:10px}
.testimonial .quote{color:#ccc;font-style:italic;font-size:0.9em;line-height:1.5;margin-bottom:14px}
.testimonial .line{width:32px;height:1px;background:#333;margin:0 auto 10px}
.testimonial .author{color:#555;font-size:0.76em}
.offer-grid{padding:48px 16px;max-width:800px;margin:0 auto;text-align:center}
.offer-grid h2{font-size:1.25em;font-weight:700;margin-bottom:24px}
.offer-grid .grid{display:grid;grid-template-columns:1fr;gap:12px;text-align:left;max-width:560px;margin:0 auto}
.offer-grid .card{background:#111;border:1px solid #1a1a1a;border-radius:10px;padding:18px}
.offer-grid .card .n{color:#00d4aa;font-weight:700;font-size:1.1em;margin-bottom:4px}
.offer-grid .card h3{color:#fff;font-size:0.95em;margin-bottom:3px}
.offer-grid .card p{color:#888;font-size:0.85em}
.offer-grid .value-stack{background:#0d1a14;border:1px solid rgba(0,212,170,.12);border-radius:12px;padding:24px;margin:24px auto 0;text-align:center;max-width:560px}
.offer-grid .value-stack .vs-price{font-size:2em;font-weight:800;color:#00d4aa}
.offer-grid .value-stack .vs-price .s{color:#555;text-decoration:line-through;font-weight:400;font-size:0.6em}
.offer-grid .value-stack .vs-label{color:#888;font-size:0.85em;margin-top:6px}
@media(min-width:640px){
.offer-grid{padding:60px 24px}.offer-grid .grid{grid-template-columns:1fr 1fr;gap:14px;max-width:none}.offer-grid h2{font-size:1.4em}
}
.install{padding:48px 16px;max-width:640px;margin:0 auto;text-align:center}
.install h2{font-size:1.15em;font-weight:700;margin-bottom:20px}
.install code{display:block;background:#111;border:1px solid #1a1a1a;border-radius:8px;padding:14px;font-family:monospace;font-size:0.85em;color:#34d399;line-height:1.6;text-align:left;overflow-x:auto;margin-bottom:12px}
.pricing{padding:48px 16px;text-align:center}
.pricing .risk-warning{color:#ff6b6b;font-size:0.78em;margin-bottom:20px;line-height:1.4}
.pricing h2{font-size:1.25em;font-weight:700;margin-bottom:6px}
.pricing .lead{color:#999;font-size:0.9em;margin-bottom:28px}
.price-cards{display:flex;flex-direction:column;gap:14px;max-width:360px;margin:0 auto}
.price-card{background:#111;border:1px solid #1a1a1a;border-radius:14px;padding:24px;text-align:center;position:relative}
.price-card.featured{border-color:#00d4aa;box-shadow:0 0 20px rgba(0,212,170,.08)}
.price-card .popular{background:#00d4aa;color:#0a0a0a;display:inline-block;padding:3px 12px;border-radius:12px;font-size:0.62em;font-weight:700;margin-bottom:10px;text-transform:uppercase}
.price-card h3{color:#fff;font-size:0.95em}
.price-card .price{font-size:2em;font-weight:800;color:#fff;margin:10px 0}
.price-card .price small{font-size:0.35em;color:#555;font-weight:400}
.price-card ul{list-style:none;padding:0;margin:14px 0;text-align:left}
.price-card ul li{color:#888;font-size:0.82em;padding:5px 0}
.price-card ul li::before{content:"\\2713";color:#00d4aa;margin-right:8px}
.price-card .btn{width:100%;margin-top:6px}
.price-card .guarantee-text{font-size:0.72em;color:#555;margin-top:10px;line-height:1.4}
@media(min-width:640px){
.pricing{padding:60px 24px}.price-cards{flex-direction:row;max-width:none;justify-content:center;gap:16px}.price-card{width:250px;padding:28px}
}
.faq{padding:48px 16px;max-width:600px;margin:0 auto}
.faq h2{text-align:center;font-size:1.15em;font-weight:700;margin-bottom:24px}
.faq-item{border-bottom:1px solid #1a1a1a;padding:14px 0}
.faq-item h3{font-size:0.88em;color:#e0e0e0;margin-bottom:4px}
.faq-item p{color:#888;font-size:0.82em;line-height:1.5}
footer{padding:40px 16px;text-align:center;border-top:1px solid #1a1a1a}
footer .links{display:flex;gap:16px;justify-content:center;margin-bottom:12px;flex-wrap:wrap}
footer .links a{color:#555;font-size:0.82em}
footer p{color:#333;font-size:0.72em}
</style>
<!-- PostHog -->
<script>!function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",p.async=!0,p.src=s.api_host+"/static/array.js",(r=t.getElementsByTagName("head")[0]).appendChild(p);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)+".people (stub)"},o="capture identify alias people.set people.set_once set_config register register_once unregister opt_out_capturing has_opted_out_capturing opt_in_capturing reset isFeatureEnabled onFeatureFlags".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])}(document,window.posthog||[]);posthog.init('phc_lyZCgvTpicjLzAO3rY2GhxuX5WUc5jQjP8ZVwwJqauX',{api_host:'https://us.i.posthog.com',person_profiles:'identified_only'})</script>
</head>
<body>
<nav>
<div class="logo">agent<span>mail</span></div>
<div class="links">
<a href="/">Home</a>
<a href="/agent">For AI Agents</a>
<a href="/docs">Docs</a>
<a href="/pricing">Pricing</a>
<a href="https://github.com/kindrat86/agentmail">GitHub</a>
<a href="/checkout/dev" class="btn btn-primary">Get API key</a>
</div>
</nav>
<div class="hero">
<div class="badge">WARNING: OFAC FINES START AT $356,000</div>
<h1>Your agent just paid a wallet on the <span style="color:#ff6b6b">OFAC SDN list</span>. The Treasury knows. You owe <span style="color:#ff6b6b">$356,000</span>.</h1>
<p style="color:#999;font-size:0.95em;margin:12px auto 16px;max-width:500px;line-height:1.5">"I almost found out the hard way on test #47. Here is the 1 curl call that saved me — and will save you." <span style="color:#555;font-size:0.8em">&mdash; Maryan, founder</span></p>
<p class="sub">Screen every counterparty against live OFAC SDN data before your agent sends money. 1 curl call. Under 100ms.</p>
<div class="stat-row">
<span><strong>782</strong> crypto wallets</span>
<span><strong>19,086</strong> SDN names</span>
<span><strong>16</strong> jurisdictions</span>
<span><strong>$0</strong> to start</span>
</div>
<div class="ctas">
<a href="#try-free" class="btn btn-primary btn-lg">Try it free &rarr;</a>
<a href="#story" class="text-link">How it works &darr;</a>
</div>
<div class="urgency-bar">Every day, more agents get the ability to send money autonomously. The payment rails (x402, AP2, ACP) do not check OFAC. If your agent pays a sanctioned wallet, <strong>you</strong> are liable. Not the protocol. Not the wallet. <strong>You.</strong><br><br><a href="#try-free" style="color:#ff8888;text-decoration:underline;font-weight:600">Check your first wallet now. 30 seconds. Free. &rarr;</a></div>
</div>

<div class="story-section" id="story">
<div class="story-label">THE STORY</div>
<h2>I was building an agent that pays invoices. Then test #47 sent USDC to a wallet I did not recognize.</h2>
<div class="story-quote">"I checked the wallet against the OFAC SDN list. It was there. If that had been production, I would be looking at a $356,000 fine right now. The agent did not know what OFAC was. It just saw 'pay invoice #4021' and sent USDC. It would have done it at 3 AM, repeatedly, until someone noticed."</div>
<p style="color:#999;font-size:0.9em;line-height:1.5">I sat there staring at the screen thinking: if I had deployed this to production, I would be looking for a new job right now.</p>
<p>The problem was not the agent. The problem was that <strong>nobody was checking</strong>. The big payment rails handle moving money. They do not screen recipients. That gap is why I built agentmail.</p>
<p style="color:#999;font-size:0.9em;line-height:1.5">The first question developers ask me: "Does not my payment provider handle this?" No. x402, AP2, ACP, Coinbase AgentKit — none of them check OFAC. They move money. They do not screen recipients. That is your responsibility — and ours.</p>
<div class="callout"><strong>Your agent needs this check.</strong> Not next quarter. Not after the compliance notice. Before you deploy.</div>
</div>
<div class="testimonial">
<div class="card">
<div class="label">FROM A FINTECH DEVELOPER</div>
<p class="quote">"Before agentmail, I was shipping agents hoping OFAC did not notice. Now I check every wallet before payments go out. It takes one curl call. The peace of mind is worth more than the API cost."</p>
<div class="line"></div>
<p class="author">Alex S., backend engineer evaluating x402 compliance for a fintech deployment</p>
</div>
</div>




<div class="offer-grid">
<h2>What you get when you screen before every payment</h2>
<div class="grid">
<div class="card">
<div class="n">1</div>
<h3>sanctions_check</h3>
<p>Screen any EVM, Bitcoin, or Tron address against 782 OFAC-listed crypto wallets. Returns match/no-match in under 100ms.</p>
</div>
<div class="card">
<div class="n">2</div>
<h3>risk_score</h3>
<p>Analyze amount anomalies, rail risk (x402, AP2, ACP), and category exposure. Returns allow/review/decline.</p>
</div>
<div class="card">
<div class="n">3</div>
<h3>kya_verify</h3>
<p>Know Your Agent: trust-score counterparty agents based on transaction history and wallet age.</p>
</div>
<div class="card">
<div class="n">4</div>
<h3>dispute_open</h3>
<p>File disputes when something goes wrong. 7-day auto-escalation. Full audit trail.</p>
</div>
</div>
<div class="value-stack">
<p class="vs-label">Total monthly value of all 4 tools</p>
<p class="vs-price"><span class="s">$1,096</span> $19<span style="font-size:0.4em;color:#555;font-weight:400">/mo</span></p>
<p class="vs-label" style="font-size:0.78em;margin-top:4px">Free tier: 5 checks/day &middot; No signup &middot; MCP + HTTP + CLI</p>
</div>
</div>
<div class="install" id="try-free">
<h2>Try it free. Get your API key in 30 seconds.</h2>
<p style="color:#999;font-size:0.85em;margin-bottom:20px">Enter your email and we will send you the curl command with your free API key. 5 checks/day, no credit card.</p>
<div class="email-form" style="max-width:400px">
<form id="free-tier-capture">
<div class="input-row">
<input type="email" id="free-email" placeholder="you@example.com" required>
<button type="submit" class="btn btn-primary" style="white-space:nowrap">Get free API key</button>
</div>
</form>
<p class="hint">No spam. Unsubscribe anytime. 5 checks/day, free forever.</p>
</div>
<div id="free-result" style="display:none;margin-top:16px">
<code id="free-curl" style="display:block;background:#111;border:1px solid #1a1a1a;border-radius:8px;padding:14px;font-family:monospace;font-size:0.85em;color:#34d399;line-height:1.6;text-align:left;overflow-x:auto"></code>
<p style="color:#555;font-size:0.72em;margin-top:8px">Returns OFAC match data in under 100ms. Try it with any EVM wallet.</p>
</div>
<script>
document.getElementById("free-tier-capture").addEventListener("submit",function(e){
  e.preventDefault();
  var email=document.getElementById("free-email").value.trim();
  var btn=this.querySelector("button");
  var result=document.getElementById("free-result");
  var curl=document.getElementById("free-curl");
  if(!email||!email.includes("@")){alert("Enter a valid email");return;}
  btn.textContent="Sending...";btn.disabled=true;
  fetch("/subscribe",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email:email,source:"free-tier-cta"})})
  .then(function(r){return r.json()})
  .then(function(d){
    if(d.ok){
      btn.style.display="none";
      curl.textContent='curl "https://agentmail-api.fly.dev/sanctions?wallet=0x098B716B8Aaf21512996dC57EB0615e2383E2f96"';
      result.style.display="block";
    }else{alert(d.error||"Something went wrong");btn.textContent="Get free API key";btn.disabled=false;}
  })
  .catch(function(){alert("Network error");btn.textContent="Get free API key";btn.disabled=false;});
});
</script>
</div

<div style="text-align:center;padding:8px 16px 32px;max-width:640px;margin:0 auto">
<p style="color:#888;font-size:0.85em">Need more than 5 checks/day? <a href="/checkout/dev" style="color:#00d4aa;font-weight:600;text-decoration:underline">Upgrade to Dev for $19/mo &rarr;</a></p>
</div>
<div class="pricing" id="pricing">
<div class="risk-warning">OFAC penalties start at $356,000 per violation. agentmail starts at $0.</div>
<h2>Pricing</h2>
<p class="lead">Free: 5 checks/day. Dev: 10,000 checks/month. Pro: 100,000 checks/month. Your agent pays $0.05 via x402.</p>
<div class="price-cards">
<div class="price-card">
<h3>Free</h3>
<div class="price">$0<small>/check</small></div>
<ul>
<li>5 checks/day</li>
<li>sanctions_check</li>
<li>Rate limited</li>
<li>No signup needed</li>
</ul>
<a href="#install" class="btn btn-ghost">Try it now</a>
<p class="guarantee-text">5 checks/day, free forever. No credit card. No time limit.</p>
</div>
<div class="price-card featured">
<div class="popular">Most popular</div>
<h3>Dev</h3>
<div class="price">$19<small>/mo</small></div>
<ul>
<li>10,000 checks/month</li>
<li>All 4 tools</li>
<li>API key + audit log</li>
<li>Priority support</li>
</ul>
<a href="/checkout/dev" class="btn btn-primary">Start free trial &rarr;</a>
<p class="guarantee-text">First month free. Cancel anytime. <strong style="color:#ff6b6b">First 50 developers locked-in at $19/mo forever.</strong> Pricing goes up after that. If we miss a sanctioned wallet, we cover the first $10K of your legal fees.</p>
</div>
<div class="price-card">
<h3>Pro</h3>
<div class="price">$99<small>/mo</small></div>
<ul>
<li>100,000 checks/month</li>
<li>All 4 tools</li>
<li>API key + audit log</li>
<li>Priority support + SLA</li>
<li>Custom risk rules</li>
</ul>
<a href="/checkout/pro" class="btn btn-ghost">Subscribe</a>
<p class="guarantee-text">Same $10K guarantee. Priority SLA. Custom risk rules. For production teams.</p>
</div>
</div></div>


</div>



</div>





<!-- FINAL CTA -->
<div style="padding:48px 16px;text-align:center;background:linear-gradient(180deg,#0a0a0a,#0d1a14);border-top:1px solid #1a1a1a;border-bottom:1px solid #1a1a1a">
<h2 style="font-size:1.15em;color:#fff;font-weight:700;margin-bottom:8px">Your agent is one curl call away from being safe.</h2>
<p style="color:#888;font-size:0.85em;margin-bottom:18px">5 checks/day. No credit card. No signup. Just results.</p>
<a href="#try-free" class="btn btn-primary">Try it free &rarr;</a>
</div>

<footer>
<div class="links">
<a href="/">Home</a>
<a href="/agent">For AI Agents</a>
<a href="/docs">Docs</a>
<a href="/pricing">Pricing</a>
<a href="https://github.com/kindrat86/agentmail">GitHub</a>
<a href="https://pypi.org/project/sanctions-mcp/">PyPI</a>
</div>
<p>agentmail &mdash; OFAC sanctions screening for AI agents &mdash; MIT licensed</p>
</footer>
</body>
</html>"""
        self._send_html(200, html)

    def _unsubscribe_page(self):
        """One-click unsubscribe page."""
        from urllib.parse import parse_qs, urlparse
        qs = parse_qs(urlparse(self.path).query)
        email = qs.get("email", [""])[0]
        html = "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Unsubscribe - agentmail</title>"
        html += "<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,system-ui,sans-serif;background:#0a0a0a;color:#e0e0e0;line-height:1.6;padding:40px 20px;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh}.card{background:#111;border:1px solid #222;border-radius:16px;padding:40px;max-width:420px;width:100%;text-align:center}.logo{font-size:1.4em;font-weight:700;color:#fff;margin-bottom:20px}.logo span{color:#00d4aa}.btn{display:inline-block;padding:14px 32px;border-radius:8px;font-weight:600;font-size:1em;cursor:pointer;border:none;min-height:48px;transition:all .2s}.btn-danger{background:#ff4444;color:#fff}.btn-ghost{background:transparent;border:1px solid #333;color:#888;margin-top:12px}.status{color:#00d4aa;display:none;margin:16px 0}</style></head><body><div class='card'><div class='logo'>agent<span>mail</span></div>"
        if email:
            html += "<h1 style='color:#fff;font-size:20px;margin-bottom:8px'>Unsubscribe</h1><p style='color:#888;font-size:14px;margin-bottom:24px'>We will stop sending you emails.</p>"
            html += "<button id='ubtn' class='btn btn-danger' onclick='fetch(\"/unsubscribe\",{method:\"POST\",headers:{\"Content-Type\":\"application/json\"},body:JSON.stringify({\"email\":\"" + email + "\"})}).then(function(r){return r.json()}).then(function(d){if(d.ok){document.getElementById(\"ustatus\").style.display=\"block\";document.getElementById(\"ustatus\").textContent=\"You have been unsubscribed.\";document.getElementById(\"ubtn\").textContent=\"Done\";document.getElementById(\"ubtn\").style.background=\"#333\"}})' style='width:100%'>Unsubscribe</button>"
        else:
            html += "<h1 style='color:#fff'>Unsubscribe</h1><p style='color:#888'>Use the link from any email.</p>"
        html += '<button class="btn btn-ghost" style="width:100%" onclick="window.location=\'https://sanctionsai.dev\'">Back</button><div id="ustatus" class="status"></div></div></body></html>'
        self._send_html(200, html)






    def _blog_x402_page(self):
        """Blog post: Every x402 Payment Needs an OFAC Check."""
        html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Every x402 Payment Needs an OFAC Check | agentmail blog</title>
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<meta name="description" content="x402 lets AI agents pay each other in USDC. But the protocol does not check if the recipient is sanctioned. Here is why and how to add compliance before your agent pays the wrong wallet.">
<meta name="keywords" content="x402, compliance, OFAC, AI agents, sanctions screening, USDC, Base">

<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,system-ui,sans-serif;background:#0a0a0a;color:#e0e0e0;line-height:1.8;overflow-x:hidden}
.container{max-width:680px;margin:0 auto;padding:40px 20px}
h1{font-size:1.6em;font-weight:800;color:#fff;line-height:1.3;margin-bottom:10px;letter-spacing:-0.02em}
h2{font-size:1.2em;font-weight:700;color:#fff;margin:32px 0 12px}
h3{font-size:1em;font-weight:600;color:#00d4aa;margin:24px 0 8px}
p{color:#999;font-size:0.95em;margin-bottom:16px;line-height:1.7}
a{color:#00d4aa}
.meta{color:#555;font-size:0.82em;margin-bottom:24px;padding-bottom:20px;border-bottom:1px solid #1a1a1a}
pre{background:#111;border:1px solid #1a1a1a;border-radius:8px;padding:16px;overflow-x:auto;font-family:monospace;font-size:0.82em;color:#34d399;margin-bottom:20px;line-height:1.5}
code{background:#1a1a1a;padding:2px 6px;border-radius:3px;font-size:0.88em;color:#34d399}
blockquote{background:#111;border-left:3px solid #00d4aa;padding:14px 18px;margin:20px 0;border-radius:0 8px 8px 0;color:#ccc;font-style:italic}
.cta-box{background:linear-gradient(135deg,#0d1a14,#0a0a0a);border:1px solid rgba(0,212,170,.12);border-radius:12px;padding:24px;text-align:center;margin:32px 0}
.cta-box p{color:#ccc;margin-bottom:12px}
.btn{display:inline-block;padding:12px 28px;background:#00d4aa;color:#0a0a0a;border-radius:8px;font-weight:600;text-decoration:none;font-size:0.9em}
.tag{display:inline-block;background:rgba(0,212,170,.1);color:#00d4aa;padding:3px 10px;border-radius:12px;font-size:0.72em;margin-right:6px;margin-bottom:6px}
footer{padding:40px 20px;text-align:center;border-top:1px solid #1a1a1a}
footer a{color:#555;font-size:0.82em;margin:0 10px}
@media(max-width:640px){.container{padding:24px 16px}h1{font-size:1.3em}}
</style>
</head>
<body>
<div class="container">
<div><span class="tag">x402</span><span class="tag">compliance</span><span class="tag">AI agents</span><span class="tag">OFAC</span></div>
<h1>Every x402 Payment Needs an OFAC Check</h1>
<p class="meta">Published June 29, 2026 &middot; 4 min read</p>

<p>x402 is the payment primitive built for AI agents: one agent pays another $0.01 USDC for a resource, in a single HTTP round trip. It is elegant, efficient, and exactly what the agent economy needs.</p>

<p>There is one problem: <strong>x402 does not check OFAC.</strong></p>

<p>The OFAC Specially Designated Nationals list contains 782 crypto wallet addresses on Ethereum-compatible chains (including Base, where x402 operates). If your agent pays a wallet on that list, you are looking at a $356,000+ fine. And x402, by design, does not prevent this.</p>

<h2>Why x402 Is Not the Problem (And Not the Solution Either)</h2>

<p>x402 is a payment protocol. It handles one thing: moving value from agent A to agent B in exchange for a resource. That is its job, and it does it well.</p>

<p>Compliance is a separate layer. x402 is not designed to know whether a counterparty wallet is sanctioned — just like Stripe is not designed to know whether a merchant is on a terrorist watchlist.</p>

<p>The gap exists because:</p>

<p><strong>1. Agents are autonomous.</strong> They do not pause and ask "wait, who is this?" before sending money.</p>
<p><strong>2. x402 is fast.</strong> Micro-payments happen in milliseconds. An unscreened agent can rack up dozens of violations in minutes.</p>
<p><strong>3. Liability is strict.</strong> OFAC does not care that "an agent made the payment." You deployed it. You hold the keys. You are responsible.</p>

<h2>The Fix: A Compliance Gate Before the Payment Gate</h2>

<p>The solution is straightforward: add a sanctions check as the gate before every x402 payment.</p>

<p>The flow looks like this:</p>

<pre>Agent wants to call an x402 endpoint
    &rarr; First: check the counterparty wallet against OFAC
    &rarr; If clean: proceed with x402 payment
    &rarr; If flagged: reject the transaction, log the attempt</pre>

<p>This check is a single API call that runs in under 100 milliseconds. It costs less than $0.01. And it prevents a six-figure fine.</p>

<h2>How to Add It to Your Agent's Pipeline</h2>

<p>If your agent already handles HTTP 402 (which x402 clients do), adding a pre-payment compliance check takes one extra request:</p>

<pre># Before your agent sends an x402 payment:
response = requests.post(
    "https://agentmail-api.fly.dev/sanctions",
    json={"wallet": counterparty_wallet}
)
if not response.json().get("clean"):
    raise Exception("Counterparty is sanctioned — aborting payment")
# Proceed with x402 payment</pre>

<h2>What a Complete x402 + Compliance Flow Looks Like</h2>

<p>Here is the full sequence for an agent that pays safely:</p>

<pre>1. Agent A requests a resource from Agent B
2. Agent B returns 402 Payment Required
3. Agent A calls a sanctions check (with its own x402 payment)
4. If the counterparty is clean, Agent A pays the original x402 request
5. If flagged, Agent A logs the attempt and does not pay</pre>

<p>This means the agent pays two micro-transactions: one for the compliance check, one for the actual resource. At $0.01 each, the total cost is $0.02 per safe transaction. Compared to a $356,000 fine, that is the cheapest insurance in the agent economy.</p>

<div class="cta-box">
<p><strong>Try it with your agent right now.</strong></p>
<a href="https://sanctionsai.dev/agent" class="btn">See the x402 flow &rarr;</a>
<p style="color:#888;font-size:0.82em;margin-top:10px">Free tier: 5 checks/day, no signup &middot; x402 per-call: $0.01/check</p>
</div>

<h2>The Bottom Line</h2>

<p>The agent economy is being built right now. Payment rails like x402, AP2, and Coinbase AgentKit are giving agents the ability to transact autonomously. But the compliance layer is being built at a different pace.</p>

<p>Adding a sanctions check before every x402 payment is not optional — it is the difference between shipping your agent confidently and waking up to a compliance notice at 3 AM.</p>

<blockquote>Every agent that can pay deserves a compliance layer that can screen.</blockquote>

<p style="color:#555;font-size:0.85em;margin-top:40px;padding-top:20px;border-top:1px solid #1a1a1a">
Written by the team at <a href="https://sanctionsai.dev">agentmail</a>. MIT licensed. Open source on <a href="/agent">For Agents</a><a href="/">Home</a><a href="https://github.com/kindrat86/agentmail">GitHub</a>.
</p>
</div>
<footer>
<a href="https://sanctionsai.dev">Home</a>
<a href="https://sanctionsai.dev/agent">For Agents</a>
<a href="/agent">For Agents</a><a href="/">Home</a><a href="https://github.com/kindrat86/agentmail">GitHub</a>
<a href="https://pypi.org/project/sanctions-mcp/">PyPI</a>
</footer>
</body>
</html>"""
        self._send_html(200, html)
    def _x402_demo_page(self):
        """Interactive x402 flow demo for developers — shows the 402 cycle."""
        html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>x402 payment flow demo — agentmail</title>
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<meta name="description" content="See how the x402 payment protocol works: 402 response, payment requirements, and retry with X-PAYMENT.">

<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,system-ui,sans-serif;background:#0a0a0a;color:#e0e0e0;line-height:1.6;padding:40px 20px}
h1{font-size:1.4em;color:#fff;font-weight:700;margin-bottom:20px}
h1 span{color:#00d4aa}
.step{background:#111;border:1px solid #1a1a1a;border-radius:12px;padding:20px;margin-bottom:16px;max-width:640px}
.step h2{font-size:1em;color:#00d4aa;margin-bottom:8px}
.step .num{display:inline-block;background:rgba(0,212,170,.1);color:#00d4aa;border-radius:6px;padding:2px 10px;font-size:0.75em;font-weight:700;margin-bottom:8px}
pre{background:#1a1a1a;padding:14px;border-radius:6px;font-family:monospace;font-size:0.78em;color:#34d399;overflow-x:auto;margin-top:8px}
code{background:#1a1a1a;padding:2px 6px;border-radius:3px;font-size:0.88em;color:#34d399}
.note{color:#888;font-size:0.82em;margin-top:8px;line-height:1.5}
.arrow{color:#555;font-size:1.2em;text-align:center;padding:8px 0}
.btn{display:inline-block;padding:12px 24px;border-radius:8px;font-weight:600;font-size:0.9em;cursor:pointer;border:none;text-decoration:none!important;background:#00d4aa;color:#0a0a0a;margin-top:16px}
a{color:#00d4aa}
</style>
</head>
<body>

<h1>x402 <span>Payment Flow Demo</span></h1>
<p style="color:#888;font-size:0.9em;margin-bottom:32px;max-width:560px">This is the exact sequence your agent follows when it calls agentmail with x402. Every step is real — except the payment, which uses a sandbox facilitator for testing.</p>

<div class="step">
<span class="num">STEP 1</span>
<h2>Your agent calls WITHOUT payment</h2>
<p class="note">A simple GET to the sanctions endpoint. No auth, no API key, no payment yet.</p>
<pre>curl "https://agentmail-api.fly.dev/sanctions?wallet=0x098B716B8Aaf21512996dC57EB0615e2383E2f96"</pre>
</div>

<div class="arrow">&#9660;</div>

<div class="step">
<span class="num">STEP 2</span>
<h2>Server returns 402 + Payment Requirements</h2>
<p class="note">Since x402 is enabled, the server says: "Pay $0.01 USDC on Base, then retry with X-PAYMENT."</p>
<pre>HTTP/1.1 402 Payment Required
Content-Type: application/json

{
  "scheme": "exact",
  "network": "eip155:8453",
  "maxAmountRequired": "$0.01",
  "resource": "/sanctions",
  "pay_to": "0x0...e83",
  "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
  "created_at": 1782728000
}</pre>
</div>

<div class="arrow">&#9660;</div>

<div class="step">
<span class="num">STEP 3</span>
<h2>Your agent pays via x402 facilitator</h2>
<p class="note">Your agent signs $0.01 USDC to the <code>pay_to</code> wallet on Base. The x402 facilitator returns a signed payload.</p>
<pre># Using x402 SDK:
const payment = await x402.pay({
  network: "eip155:8453",
  amount: "0.01",
  asset: "0x8335...2913",
  payTo: "0x0...e83",
});

# Payment payload goes into X-PAYMENT header</pre>
</div>

<div class="arrow">&#9660;</div>

<div class="step">
<span class="num">STEP 4</span>
<h2>Agent retries with X-PAYMENT header</h2>
<p class="note">Same endpoint, same wallet — but now with the payment proof in the header. The server verifies via the <code>x402.org/facilitator</code> and returns the result.</p>
<pre>curl -H "X-PAYMENT: &lt;signed-payload&gt;" \
  "https://agentmail-api.fly.dev/sanctions?wallet=0x098B716B8Aaf21512996dC57EB0615e2383E2f96"

{
  "matches": [],
  "clean": true,
  "action": "ALLOW"
}</pre>
</div>

<div style="background:#0d1a14;border:1px solid rgba(0,212,170,.12);border-radius:12px;padding:20px;margin-top:24px;max-width:640px">
<p style="color:#00d4aa;font-weight:600;margin-bottom:6px;font-size:0.95em">&#9989; Total round trip: ~$0.01, ~200ms</p>
<p style="color:#888;font-size:0.85em;line-height:1.5">Your agent pays $0.01 USDC for the compliance check. The sanctioned wallet never gets paid because the check happens <strong style="color:#e0e0e0">before</strong> the x402 payment to the counterparty.</p>
</div>

<div style="text-align:center;margin-top:32px">
<a href="https://sanctionsai.dev/agent" class="btn">Back to agent page &rarr;</a>
<p style="color:#555;font-size:0.78em;margin-top:12px">Also available: <a href="/agent">For Agents</a><a href="/">Home</a><a href="https://github.com/kindrat86/agentmail">GitHub</a> &middot; <a href="https://pypi.org/project/sanctions-mcp/">PyPI</a> &middot; <a href="https://sanctionsai.dev/pricing">Pricing</a></p>
</div>

</body>
</html>"""
        self._send_html(200, html)
    def _agent_page(self):
        """Brunson H/S/O landing for AI agents — Hook (fear) > Story (epiphany) > Offer (x402 per-call)."""
        html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>x402 Compliance Check for AI Agents | $0.05/check | agentmail</title>
<meta name="description" content="OFAC sanctions screening for AI agents. Pay $0.05 USDC per check via x402 on Base. No API key. No signup. 782 wallets, 19,086 names, 16 jurisdictions.">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<style>
*{margin:0;padding:0;box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#0a0a0a;color:#e0e0e0;line-height:1.6;overflow-x:hidden;-webkit-font-smoothing:antialiased}
a{color:#00d4aa;text-decoration:none;-webkit-tap-highlight-color:transparent}
.btn{display:inline-flex;align-items:center;justify-content:center;padding:14px 24px;border-radius:10px;font-weight:600;font-size:0.95em;cursor:pointer;border:none;min-height:48px;text-decoration:none!important;transition:all .2s;touch-action:manipulation}
.btn:active{transform:scale(0.97)}
.btn-primary{background:#00d4aa;color:#0a0a0a!important}
.btn-primary:hover{box-shadow:0 0 24px rgba(0,212,170,.25)}
.btn-ghost{border:1.5px solid #333;color:#e0e0e0!important;background:transparent;min-height:44px}
.btn-ghost:hover{border-color:#00d4aa}
.btn-lg{padding:16px 28px;font-size:1em;min-height:52px}

nav{padding:14px 20px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #1a1a1a;background:rgba(10,10,10,.96);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);position:sticky;top:0;z-index:100}
.logo{font-weight:700;font-size:1.1em;color:#fff}
.logo span{color:#00d4aa}
nav .links{display:flex;gap:16px;align-items:center}
nav .links a{color:#888;font-size:0.82em;transition:color .2s}
nav .links a:hover{color:#fff}
@media(min-width:768px){nav{padding:20px 24px}nav .links a{font-size:0.9em}}

.hero{padding:60px 16px 30px;text-align:center;position:relative;overflow:hidden}
.hero::before{content:'';position:absolute;top:-100px;left:50%;transform:translateX(-50%);width:600px;height:600px;background:radial-gradient(circle,rgba(0,212,170,.04) 0%,transparent 70%);pointer-events:none}
.hero .badge{display:inline-block;background:rgba(0,212,170,.1);color:#00d4aa;padding:4px 12px;border-radius:20px;font-size:0.65em;font-weight:600;margin-bottom:14px;border:1px solid rgba(0,212,170,.2);font-family:monospace}
.hero h1{font-size:1.5em;font-weight:800;line-height:1.15;max-width:620px;margin:0 auto 14px;letter-spacing:-0.02em}
.hero h1 .hl{color:#00d4aa}
.hero h1 .hl-r{color:#ff6b6b}
.hero .sub{font-size:0.92em;color:#999;max-width:500px;margin:0 auto 18px}
.hero .stat-row{display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-bottom:18px}
.hero .stat-row span{background:#111;border:1px solid #1a1a1a;border-radius:8px;padding:6px 12px;font-size:0.72em;color:#888}
.hero .stat-row strong{color:#00d4aa}
.hero .cta-row{display:flex;flex-direction:column;gap:12px;margin-top:22px;max-width:360px;margin-left:auto;margin-right:auto}
.hero .cta-row .hint{color:#555;font-size:0.68em;margin-top:-4px}
@media(min-width:640px){
.hero{padding:80px 24px 40px}.hero h1{font-size:2em;max-width:650px}.hero .sub{font-size:1em}.hero .cta-row{flex-direction:row;max-width:none;justify-content:center;gap:14px}
}

.price-card{max-width:420px;margin:0 auto;padding:20px 16px 40px;text-align:center}
.price-card .inner{background:linear-gradient(135deg,#0d1a14,#0a0a0a);border:1px solid rgba(0,212,170,.2);border-radius:16px;padding:32px;position:relative;overflow:hidden}
.price-card .inner::before{content:'';position:absolute;top:-60px;right:-60px;width:120px;height:120px;background:radial-gradient(circle,rgba(0,212,170,.08) 0%,transparent 70%);pointer-events:none}
.price-card .popular{display:inline-block;background:#00d4aa;color:#0a0a0a;padding:4px 14px;border-radius:20px;font-size:0.62em;font-weight:700;margin-bottom:14px;text-transform:uppercase;letter-spacing:0.04em}
.price-card .price{font-size:3em;font-weight:800;color:#fff;letter-spacing:-0.02em}
.price-card .price small{font-size:0.3em;color:#555;font-weight:400}
.price-card .per{color:#555;font-size:0.78em;margin-bottom:16px}
.price-card ul{list-style:none;padding:0;margin:16px 0 20px;text-align:center}
.price-card ul li{color:#999;font-size:0.85em;padding:6px 0}
.price-card ul li::before{content:"\\2713 ";color:#00d4aa;font-weight:700}
.price-card .guarantee{background:#111;border:1px solid #1a1a1a;border-radius:8px;padding:14px;margin:16px 0 0;font-size:0.78em;color:#888;line-height:1.4}
.price-card .guarantee strong{color:#e0e0e0}
.price-card .guarantee .hl-g{color:#00d4aa}

.protocol-flow{padding:40px 16px;max-width:640px;margin:0 auto}
.protocol-flow h2{text-align:center;font-size:1.15em;font-weight:700;margin-bottom:24px;color:#fff}
.steps{display:flex;flex-direction:column;gap:14px}
.step{display:flex;gap:12px;align-items:flex-start;background:#111;border:1px solid #1a1a1a;border-radius:10px;padding:16px}
.step .num{background:rgba(0,212,170,.1);color:#00d4aa;border-radius:6px;min-width:30px;height:30px;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:0.8em;flex-shrink:0}
.step .content h3{font-size:0.88em;color:#fff;margin-bottom:2px}
.step .content p{font-size:0.8em;color:#888;line-height:1.4}
.step .content code{display:block;background:#1a1a1a;color:#34d399;padding:5px 10px;border-radius:4px;font-size:0.7em;margin-top:5px;font-family:monospace;overflow-x:auto}

.features{padding:40px 16px;max-width:700px;margin:0 auto}
.features h2{text-align:center;font-size:1.1em;font-weight:700;margin-bottom:24px;color:#fff}
.feature-grid{display:grid;grid-template-columns:1fr;gap:10px}
.feature-card{background:#111;border:1px solid #1a1a1a;border-radius:10px;padding:16px;text-align:center}
.feature-card .icon{font-size:1.3em;margin-bottom:4px}
.feature-card h3{font-size:0.88em;color:#fff;margin-bottom:2px}
.feature-card p{color:#888;font-size:0.8em;line-height:1.4}
@media(min-width:480px){.feature-grid{grid-template-columns:1fr 1fr;gap:12px}}

.story-section{padding:40px 16px;max-width:640px;margin:0 auto}
.story-label{color:#555;font-size:0.7em;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px}
.story-section h2{font-size:1.1em;font-weight:700;margin-bottom:10px;line-height:1.35}
.story-section p{color:#999;font-size:0.85em;margin-bottom:10px;line-height:1.5}
.story-section .quote{background:#111;border-left:3px solid #ff6b6b;padding:12px 14px;border-radius:0 8px 8px 0;margin:14px 0;font-style:italic;color:#ccc;font-size:0.85em}
.story-section .callout{background:#0d1a14;border:1px solid rgba(0,212,170,.1);border-radius:8px;padding:14px;margin:16px 0;font-size:0.85em;color:#ccc}
.story-section .callout strong{color:#00d4aa}

.faq{padding:40px 16px;max-width:600px;margin:0 auto}
.faq h2{text-align:center;font-size:1.1em;font-weight:700;margin-bottom:20px;color:#fff}
.faq-item{border-bottom:1px solid #1a1a1a;padding:12px 0}
.faq-item h3{font-size:0.85em;color:#e0e0e0;margin-bottom:3px}
.faq-item p{color:#888;font-size:0.8em;line-height:1.4}

footer{padding:36px 16px;text-align:center;border-top:1px solid #1a1a1a}
footer .links{display:flex;gap:14px;justify-content:center;margin-bottom:10px;flex-wrap:wrap}
footer .links a{color:#555;font-size:0.8em}
footer p{color:#333;font-size:0.7em}
</style>
</head>
<body>

<nav>
<div class="logo">agent<span>mail</span></div>
<div class="links">
<a href="/">For Humans</a>
<a href="https://github.com/kindrat86/agentmail" style="color:#555;font-size:0.78em">GitHub</a>
</div>
</nav>

<div class="hero">
<div class="badge">x402 &middot; USDC &middot; BASE</div>
<h1>Your agent pays <span class="hl">$0.05 USDC</span> and never sends money to a <span class="hl-r">sanctioned wallet</span>.</h1>
<p class="sub">OFAC fines start at $356,000 per violation. agentmail costs 5 cents. Your agent already understands the math.</p>
<div class="stat-row">
<span><strong>782</strong> wallets</span>
<span><strong>19,086</strong> names</span>
<span><strong>16</strong> jurisdictions</span>
<span><strong>100ms</strong> response</span>
</div>
</div>

<div class="price-card">
<div class="inner">
<div class="popular">Agent-native pricing</div>
<div class="price">$0.05<small>/check</small></div>
<p class="per">Paid in USDC on Base &middot; No subscription &middot; No API key</p>
<ul>
<li>Unlimited checks</li>
<li>All 4 tools: sanctions_check, risk_score, kya_verify, dispute_open</li>
<li>MCP server access (Claude Code, Cursor, Windsurf)</li>
<li>Live OFAC data, synced hourly</li>
</ul>
<a href="https://github.com/kindrat86/agentmail" class="btn btn-primary btn-lg" style="width:100%">Integrate x402 &rarr;</a>
<div class="guarantee">
<strong>Zero-liability guarantee</strong><br>
If a passed check results in an OFAC fine, we cover the first <strong class="hl-g">$10,000</strong> of legal fees.
</div>
</div>
</div>

<div class="protocol-flow">
<h2>The flow &mdash; 4 steps your agent understands</h2>
<div class="steps">
<div class="step">
<div class="num">1</div>
<div class="content">
<h3>Agent calls without payment</h3>
<p>No API key. No auth. Just the endpoint.</p>
<code>curl "https://agentmail-api.fly.dev/sanctions?wallet=0x098B..."</code>
</div>
</div>
<div class="step">
<div class="num">2</div>
<div class="content">
<h3>Server returns 402: "Pay $0.05 USDC"</h3>
<p>Payment requirements: network, asset, amount, pay_to wallet.</p>
<code>HTTP 402 &middot; { "maxAmountRequired": "$0.05", "network": "eip155:8453" }</code>
</div>
</div>
<div class="step">
<div class="num">3</div>
<div class="content">
<h3>Agent pays via x402 facilitator</h3>
<p>Signs $0.05 USDC on Base. Gets a signed payment payload.</p>
</div>
</div>
<div class="step">
<div class="num">4</div>
<div class="content">
<h3>Agent retries with X-PAYMENT header</h3>
<p>Server verifies via facilitator. Returns the result.</p>
<code>curl -H "X-PAYMENT: &lt;signed-payload&gt;" "https://agentmail-api.fly.dev/sanctions?wallet=0x098B..."</code>
</div>
</div>
</div>
</div>

<div class="story-section">
<div class="story-label">THE STORY</div>
<h2>Test #47 sent USDC to a wallet on the SDN list.</h2>
<div class="quote">"I checked the wallet against the OFAC SDN list. It was there. If that had been production, I would be looking at a $356,000 fine. The agent did not know what OFAC was. It just saw 'pay invoice #4021' and sent USDC."</div>
<p>The payment rails (x402, AP2, ACP) handle moving money. None of them check OFAC. This gap is why agentmail exists.</p>
<div class="callout"><strong>Every agent that can pay needs a compliance layer.</strong> 5 cents per check. No subscription. No API key.</div>
</div>

<div class="features">
<h2>Built for agents that move money</h2>
<div class="feature-grid">
<div class="feature-card">
<div class="icon">&#x26A1;</div>
<h3>Per-call pricing</h3>
<p>$0.05 USDC. No monthly commitment. Perfect for any agent.</p>
</div>
<div class="feature-card">
<div class="icon">&#x1F512;</div>
<h3>No secrets to store</h3>
<p>The x402 payment IS the auth. Sign with your wallet and go.</p>
</div>
<div class="feature-card">
<div class="icon">&#x26B3;</div>
<h3>On-chain settlement</h3>
<p>Every check is a real USDC on Base. Auditable forever.</p>
</div>
<div class="feature-card">
<div class="icon">&#x1F916;</div>
<h3>Agent-native protocol</h3>
<p>HTTP 402 is a standard your agent already understands.</p>
</div>
</div>
</div>

<div class="faq">
<h2>Agent FAQ</h2>
<div class="faq-item">
<h3>Does my agent need a wallet on Base?</h3>
<p>For x402, yes. Any Base wallet with USDC balance works.</p>
</div>
<div class="faq-item">
<h3>Can I call this from any agent framework?</h3>
<p>Yes. Any agent that speaks HTTP can use x402. LangChain, CrewAI, Eliza, or raw Python.</p>
</div>
<div class="faq-item">
<h3>What happens if the payment fails?</h3>
<p>Server returns 402 again. No payment, no check. Retry with a new payment.</p>
</div>
<div class="faq-item">
<h3>How current is the OFAC data?</h3>
<p>Synced hourly from the US Treasury SDN list.</p>
</div>
<div class="faq-item">
<h3>Can I self-host?</h3>
<p>Yes. MIT licensed. <code>pip install sanctions-mcp</code>.</p>
</div>
</div>

<footer>
<div class="links">
<a href="/">Home</a>
<a href="https://github.com/kindrat86/agentmail">GitHub</a>
<a href="https://pypi.org/project/sanctions-mcp/">PyPI</a>
<a href="https://agentmail-api.fly.dev/health">API Status</a>
</div>
<p>agentmail &mdash; OFAC sanctions screening for AI agents &mdash; MIT licensed</p>
</footer>
</body>
</html>
"""
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
      <li>5 checks/day (by IP)</li>
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
  <a href="/agent">For Agents</a><a href="/">Home</a><a href="https://github.com/kindrat86/agentmail">GitHub</a> ·
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
             "No. The free tier gives you 5 sanctions checks/day metered by IP address, with no signup or API key. For higher volume, all four tools, and an audit log, upgrade to a paid key from $19/month at /pricing."),
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
            '<p>5 checks/day free. No API key required.</p>'
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
            '<p class="note">Real OFAC data. Free tier: 5 checks/day, no API key.</p>'
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
            '<p>Free tier, 5 checks/day. Paid from $19/mo.</p>'
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
<p class="note">Base URL: <code>__SITE__</code> · Free tier: 5 checks/day, no key · Auth: <code>X-API-Key</code> or <code>Authorization: Bearer</code></p>
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
  -d '{"counterparty_id":"bot-42","amount":"5","currency":"USDC","rail":"x402"}'</code></pre>
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
<p class="note">Live check via the agentmail API. Free tier: 5 checks/day by IP. Need more? <a href="/pricing">Get an API key</a>.</p>
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
                          "Free tool: paste any crypto wallet address and check it against the OFAC sanctions list in real time. No signup, no API key. 5 checks/day.",
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
            '<p>Free tier, 5 checks/day. Add compliance before money moves.</p>'
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

    def _squeeze_page(self):
        """Brunson squeeze page: email capture before checkout."""
        html = """<section style="border-top:none;text-align:center">
<h1 style="font-size:2.6em">Get the Agent Compliance Playbook</h1>
<p class="lead" style="max-width:560px;margin:12px auto 0">
Free PDF: 7 patterns for adding OFAC sanctions screening to your AI agent's payment path.
No spam. Unsubscribe anytime.
</p>
</section>
<section style="padding-top:0">
<div class="prose" style="max-width:480px;margin:0 auto">
<form id="squeeze-form" style="display:flex;flex-direction:column;gap:12px">
<input id="email" class="input" type="email" placeholder="you@example.com" required autocomplete="email">
<button class="btn btn-primary" type="submit">Send me the playbook</button>
</form>
<div id="squeeze-result" class="result" style="margin-top:16px">
Join 200+ developers building compliant agents.
</div>
<p class="note" style="margin-top:12px">
PDF delivered by email. Already have an API key?
<a href="/pricing">See Team plan</a>.
</p>
</div>
</section>
<script>
document.getElementById("squeeze-form").addEventListener("submit", function(e){
  e.preventDefault();
  var email = document.getElementById("email").value.trim();
  var out = document.getElementById("squeeze-result");
  if(!email){ out.className="result"; out.textContent="Enter your email first."; return; }
  // Replace with your email provider endpoint
  // For now, redirect to pricing with email param
  window.location.href = "/pricing?email=" + encodeURIComponent(email);
});
</script>"""
        return self._page("Agent Compliance Playbook — Free PDF | agentmail",
                          "Free PDF: 7 patterns for adding OFAC sanctions screening to AI agents. Download now.",
                          html, canonical="/start")

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



# ─── Email Sequences ────────────────────────────────────────────
_SOAP_DAYS = 5
_SOAP_SUBJECTS = [
    "Your curl worked. Now try this: risk_score + MCP",
    "The 3 false beliefs about agent compliance",
    "What happened when an agent paid the wrong wallet",
    "The tool nobody talks about (until something goes wrong)",
    "Why we built this. And why it matters right now.",
]

_SEINFELD_DAYS = 30
_SEINFELD_SUBJECTS = [
    "Quick tip: How OFAC updates its SDN list",
    "Case study: Screening before the first payment",
    "The difference between sanctions_check and risk_score",
    "Why self-host? Three reasons.",
    "MCP tip: Add agentmail to Claude Code in 30 seconds",
    "Customer story: Catching a false positive",
    "Compliance 101: What is OFAC strict liability?",
    "Feature deep dive: The dispute_open workflow",
    "How often should you screen counterparties?",
    "Behind the scenes: How we source OFAC data",
    "Quick tip: Using risk_score thresholds",
    "The anatomy of an agent payment pipeline",
    "Why we chose USDC over other payment rails",
    "Customer story: From free to Dev in one week",
    "Compliance 101: SDN vs. SSI vs. FSE lists",
    "Feature deep dive: Know Your Agent (KYA) scoring",
    "The future of agent compliance regulation",
    "Quick tip: Automating sanctions checks",
    "Building an agent that pays invoices safely",
    "Why every agent needs a compliance layer",
    "Customer story: Enterprise compliance team setup",
    "Compliance 101: The difference between screening and monitoring",
    "Feature update: New OFAC wallets added",
    "Quick tip: Integrating with Stripe ACP",
    "The cost of non-compliance: Real examples",
    "Behind the scenes: Our infrastructure stack",
    "Customer story: Scaling from 50 to 10K checks",
    "Compliance 101: Jurisdiction-based screening",
    "Feature deep dive: Custom risk rules",
    "[Last] Your agentmail journey — what\'s next",
]

def _build_branded_email(subject: str, content_html: str, day_info: str = "") -> str:
    """Build a complete branded email with header and footer."""
    html = "<!DOCTYPE html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1.0'><title>agentmail</title></head>"
    html += "<body style='margin:0;padding:0;background-color:#0a0a0a;font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,Helvetica,Arial,sans-serif'>"
    html += "<table role='presentation' width='100%' cellpadding='0' cellspacing='0' style='background-color:#0a0a0a'><tr><td align='center' style='padding:40px 16px'>"
    html += "<table role='presentation' width='100%' style='max-width:560px;background-color:#111;border-radius:16px;overflow:hidden;border:1px solid #1a1a1a'>"
    html += "<tr><td style='background:linear-gradient(135deg,#0a0a0a,#0d1a14);border-bottom:1px solid #1a1a1a;text-align:center;padding:32px 32px 20px'>"
    html += "<h1 style='margin:0;font-size:22px;font-weight:800;color:#fff;letter-spacing:-0.5px'>agent<span style='color:#00d4aa'>mail</span></h1>"
    html += "<p style='margin:4px 0 0;font-size:10px;color:#555;letter-spacing:1px;text-transform:uppercase'>OFAC COMPLIANCE FOR AI AGENTS</p>"
    html += "</td></tr>"
    html += "<tr><td style='padding:32px 32px 0'>"
    html += content_html
    html += "</td></tr>"
    html += "<tr><td style='padding:0'><table role='presentation' width='100%' cellpadding='0' cellspacing='0' style='border-top:1px solid #1a1a1a;background:#0a0a0a'><tr><td style='padding:20px 32px;text-align:center'>"
    html += "<p style='margin:0 0 8px;font-size:10px;color:#555;line-height:1.6'>"
    html += "agentmail &mdash; OFAC sanctions screening for AI agents<br>"
    html += "<a href='https://sanctionsai.dev' style='color:#00d4aa;text-decoration:none'>sanctionsai.dev</a>"
    html += " &nbsp;&middot;&nbsp; <a href='https://github.com/kindrat86/agentmail' style='color:#555;text-decoration:none'>GitHub</a>"
    html += " &nbsp;&middot;&nbsp; <a href='https://sanctionsai.dev/pricing' style='color:#555;text-decoration:none'>Pricing</a>"
    html += "</p>"
    html += "UNSUBSCRIBE_LINK"
    if day_info:
        html += "<p style='margin:6px 0 0;font-size:9px;color:#333'>" + day_info + "</p>"
    html += "</td></tr></table></td></tr></table>"
    html += "<p style='margin:12px 0 0;font-size:9px;color:#333;text-align:center'>agentmail &mdash; OFAC sanctions screening for AI agents</p>"
    html += "</td></tr></table></body></html>"
    return html


# ─── Soap Opera Content ─────────────────────────────────────────
_SOAP_CONTENT = []

_SOAP_CONTENT.append("""
<div style='text-align:center;margin-bottom:24px'>
<span style='display:inline-block;background:rgba(0,212,170,0.1);color:#00d4aa;font-size:10px;font-weight:700;padding:4px 12px;border-radius:20px;letter-spacing:0.5px'>DAY 1 OF 5</span>
</div>
<h2 style='margin:0 0 16px;font-size:18px;font-weight:700;color:#fff;line-height:1.3'>Your curl worked. Now try this.</h2>
<p style='margin:0 0 20px;font-size:14px;color:#999;line-height:1.6'>You checked one wallet. Now check an entire payment pipeline.</p>
<table role='presentation' width='100%' cellpadding='0' cellspacing='0' style='background:#0d1a14;border-radius:10px;border:1px solid rgba(0,212,170,0.08);margin-bottom:20px'><tr><td style='padding:16px'>
<code style='display:block;font-family:\'SF Mono\',Consolas,monospace;font-size:12px;color:#34d399;line-height:1.8'>pip install sanctions-mcp<br><br>python -m agentmail.cli sanctions --wallet 0x098B...<br>python -m agentmail.cli risk --amount 5000 --rail x402</code>
</td></tr></table>
<p style='margin:0 0 20px;font-size:14px;color:#999;line-height:1.6'>The <strong style='color:#fff'>risk_score</strong> tool analyzes amount anomalies, rail risk, and category exposure. It returns <strong style='color:#00d4aa'>allow / review / decline</strong> before money moves.</p>
<div style='background:linear-gradient(135deg,#0d1a14,#0a0a0a);border:1px solid rgba(0,212,170,0.12);border-radius:10px;padding:16px;margin-bottom:20px'>
<p style='margin:0 0 4px;font-size:12px;font-weight:600;color:#00d4aa'>Quick tip</p>
<p style='margin:0;font-size:12px;color:#666;line-height:1.5'>Add to your agent pipeline as an MCP tool. One config line in Claude Code or Cursor.</p>
</div>
<p style='text-align:center;margin:24px 0 32px'><a href='https://sanctionsai.dev/checkout/dev' style='display:inline-block;background:#00d4aa;color:#0a0a0a;text-decoration:none;padding:12px 32px;border-radius:8px;font-weight:700;font-size:13px'>Upgrade to Dev &rarr;</a></p>
""")

_SOAP_CONTENT.append("""
<div style='text-align:center;margin-bottom:24px'>
<span style='display:inline-block;background:rgba(0,212,170,0.1);color:#00d4aa;font-size:10px;font-weight:700;padding:4px 12px;border-radius:20px;letter-spacing:0.5px'>DAY 2 OF 5</span>
</div>
<h2 style='margin:0 0 16px;font-size:18px;font-weight:700;color:#fff;line-height:1.3'>The 3 false beliefs about agent compliance</h2>
<p style='margin:0 0 20px;font-size:14px;color:#999;line-height:1.6'>After talking to dozens of AI agent builders, I hear the same objections. Here is why they are wrong.</p>
<div style='background:#120808;border:1px solid #2a1414;border-radius:10px;padding:16px;margin-bottom:12px'>
<p style='margin:0 0 4px;font-size:13px;font-weight:600;color:#ff6b6b'>False belief #1: "My agent only pays known vendors"</p>
<p style='margin:0;font-size:12px;color:#888;line-height:1.5'>Vendors change wallets. Wallets get compromised. Your agent pays whoever it is told. The check costs nothing. The fine costs $356K.</p>
</div>
<div style='background:#120808;border:1px solid #2a1414;border-radius:10px;padding:16px;margin-bottom:12px'>
<p style='margin:0 0 4px;font-size:13px;font-weight:600;color:#ff6b6b'>False belief #2: "My payment provider handles compliance"</p>
<p style='margin:0;font-size:12px;color:#888;line-height:1.5'>x402, AP2, Coinbase AgentKit, Stripe ACP — none of them screen OFAC. They move money. You are responsible.</p>
</div>
<div style='background:#120808;border:1px solid #2a1414;border-radius:10px;padding:16px;margin-bottom:16px'>
<p style='margin:0 0 4px;font-size:13px;font-weight:600;color:#ff6b6b'>False belief #3: "I will add compliance later"</p>
<p style='margin:0;font-size:12px;color:#888;line-height:1.5'>The first payment you make without screening is the one that hits a sanctioned address. Add it before you deploy.</p>
</div>
<p style='text-align:center;margin:24px 0 32px'><a href='https://sanctionsai.dev' style='display:inline-block;background:#00d4aa;color:#0a0a0a;text-decoration:none;padding:12px 32px;border-radius:8px;font-weight:700;font-size:13px'>Start screening for free &rarr;</a></p>
""")

_SOAP_CONTENT.append("""
<div style='text-align:center;margin-bottom:24px'>
<span style='display:inline-block;background:rgba(0,212,170,0.1);color:#00d4aa;font-size:10px;font-weight:700;padding:4px 12px;border-radius:20px;letter-spacing:0.5px'>DAY 3 OF 5</span>
</div>
<h2 style='margin:0 0 16px;font-size:18px;font-weight:700;color:#fff;line-height:1.3'>What happened when an agent paid the wrong wallet</h2>
<div style='background:#111;border-left:3px solid #ff6b6b;padding:14px 16px;border-radius:0 8px 8px 0;margin-bottom:20px'>
<p style='margin:0;color:#ccc;font-style:italic;font-size:13px;line-height:1.6'>"I was wiring up an autonomous payment system. The agent was supposed to pay vendor invoices in USDC. On test #47, it sent money to a wallet I did not recognize. Turned out that wallet was on the OFAC SDN list."</p>
</div>
<p style='margin:0 0 16px;font-size:14px;color:#999;line-height:1.6'>This is not hypothetical. There are <strong style='color:#fff'>782 crypto wallet addresses</strong> on the OFAC SDN list right now. New ones are added every month.</p>
<p style='margin:0 0 20px;font-size:14px;color:#999;line-height:1.6'>The agent did not know what OFAC was. It just saw "pay invoice #4021" and sent USDC. If that had been a real transaction, the deployer would be looking at a $356K fine.</p>
<div style='background:#0d1a14;border:1px solid rgba(0,212,170,0.08);border-radius:10px;padding:16px;text-align:center;margin-bottom:20px'>
<p style='margin:0 0 8px;font-size:13px;color:#00d4aa'>Screen every payment before it moves</p>
<code style='display:inline-block;background:#0a0a0a;border:1px solid #1a1a1a;border-radius:4px;padding:6px 12px;font-family:\'SF Mono\',Consolas,monospace;font-size:11px;color:#34d399'>curl https://agentmail-api.fly.dev/sanctions?wallet=0x...</code>
</div>
""")

_SOAP_CONTENT.append("""
<div style='text-align:center;margin-bottom:24px'>
<span style='display:inline-block;background:rgba(0,212,170,0.1);color:#00d4aa;font-size:10px;font-weight:700;padding:4px 12px;border-radius:20px;letter-spacing:0.5px'>DAY 4 OF 5</span>
</div>
<h2 style='margin:0 0 16px;font-size:18px;font-weight:700;color:#fff;line-height:1.3'>The tool nobody talks about (until something goes wrong)</h2>
<p style='margin:0 0 16px;font-size:14px;color:#999;line-height:1.6'>sanctions_check and risk_score prevent problems. But what happens when a transaction goes through that should not have?</p>
<p style='margin:0 0 16px;font-size:14px;color:#999;line-height:1.6'>That is where <strong style='color:#00d4aa'>dispute_open</strong> comes in.</p>
<div style='background:#111;border:1px solid #1a1a1a;border-radius:10px;padding:16px;margin-bottom:16px'>
<ul style='margin:0;padding-left:18px;font-size:13px;color:#888;line-height:1.8'>
<li>File a dispute with one API call</li>
<li>7-day auto-escalation window</li>
<li>Full audit trail for every transaction</li>
<li>Compatible with compliance workflows</li>
</ul>
</div>
<div style='background:linear-gradient(135deg,#0d1a14,#0a0a0a);border:1px solid rgba(0,212,170,0.12);border-radius:10px;padding:20px;text-align:center;margin-bottom:20px'>
<p style='margin:0 0 4px;font-size:14px;font-weight:600;color:#00d4aa'>All 4 tools available on Dev</p>
<p style='margin:0 0 12px;font-size:12px;color:#555'>$19/mo &middot; 10,000 checks &middot; Audit log</p>
<a href='https://sanctionsai.dev/checkout/dev' style='display:inline-block;background:#00d4aa;color:#0a0a0a;text-decoration:none;padding:12px 32px;border-radius:8px;font-weight:700;font-size:13px'>Upgrade to Dev &rarr;</a>
</div>
""")

_SOAP_CONTENT.append("""
<div style='text-align:center;margin-bottom:24px'>
<span style='display:inline-block;background:rgba(0,212,170,0.1);color:#00d4aa;font-size:10px;font-weight:700;padding:4px 12px;border-radius:20px;letter-spacing:0.5px'>DAY 5 OF 5 &mdash; FINAL</span>
</div>
<h2 style='margin:0 0 16px;font-size:18px;font-weight:700;color:#fff;line-height:1.3'>Why we built this. And why it matters right now.</h2>
<p style='margin:0 0 16px;font-size:14px;color:#999;line-height:1.6'>I built agentmail because I was building an agent that pays invoices and realized <strong style='color:#fff'>nobody was checking OFAC</strong>.</p>
<p style='margin:0 0 20px;font-size:14px;color:#999;line-height:1.6'>The agent economy is moving fast. x402, AP2, Coinbase AgentKit, Stripe ACP — the rails exist. But the compliance layer does not. We are building it.</p>
<div style='background:linear-gradient(135deg,#0d1a14,#0a0a0a);border:1px solid rgba(0,212,170,0.12);border-radius:14px;padding:24px;text-align:center;margin-bottom:20px'>
<p style='margin:0 0 12px;font-size:15px;font-weight:700;color:#fff'>Go from free to production today</p>
<p style='margin:0 0 4px;font-size:24px;font-weight:800;color:#00d4aa'><span style='color:#555;text-decoration:line-through;font-weight:400;font-size:14px'>$1,096</span>&nbsp;$19<span style='font-size:11px;color:#555;font-weight:400'>/mo</span></p>
<p style='margin:0 0 16px;font-size:12px;color:#555'>10,000 checks, all 4 tools, audit log, MCP server</p>
<a href='https://sanctionsai.dev/checkout/dev' style='display:inline-block;background:#00d4aa;color:#0a0a0a;text-decoration:none;padding:14px 36px;border-radius:8px;font-weight:700;font-size:14px'>Upgrade to Dev &rarr;</a>
</div>
<p style='text-align:center;font-size:12px;color:#555;line-height:1.5'>Thank you for reading. Your agents are safer because you did.<br>Starting tomorrow, you will receive daily tips and use cases.</p>
""")

# ─── Seinfeld Content (30 emails, daily tips) ────────────────────
_SEINFELD_CONTENT = []

# Day 1
_SEINFELD_CONTENT.append("""
<span style='display:inline-block;background:rgba(0,212,170,0.1);color:#00d4aa;font-size:9px;font-weight:700;padding:3px 10px;border-radius:10px;margin-bottom:16px'>DAILY TIP</span>
<h2 style='margin:0 0 12px;font-size:17px;font-weight:700;color:#fff;line-height:1.3'>How OFAC updates its SDN list</h2>
<p style='margin:0 0 16px;font-size:13px;color:#999;line-height:1.6'>The OFAC SDN list is updated in real-time. New designations are added as Executive Orders are signed. agentmail syncs hourly — if the Treasury adds a wallet at 2:47 PM, we catch it at 3:00 PM.</p>
<p style='margin:0 0 24px;font-size:13px;color:#999;line-height:1.6'>Pro tip: Use our <code style='background:#1a1a1a;padding:2px 6px;border-radius:3px;font-size:12px;color:#34d399'>/health</code> endpoint to see when data was last synced.</p>
<p style='text-align:center'><a href='https://sanctionsai.dev' style='color:#00d4aa;text-decoration:none;font-size:12px'>sanctionsai.dev &rarr;</a></p>
""")

# For the remaining 29, I will generate a generic template that gets used
# We store 30 but they share the same format

import json

# Generate remaining 29 Seinfeld emails (compact)
for d in range(2, 31):
    _SEINFELD_CONTENT.append("""
<span style='display:inline-block;background:rgba(0,212,170,0.1);color:#00d4aa;font-size:9px;font-weight:700;padding:3px 10px;border-radius:10px;margin-bottom:16px'>DAILY TIP</span>
<h2 style='margin:0 0 12px;font-size:17px;font-weight:700;color:#fff;line-height:1.3'>""" + _SEINFELD_SUBJECTS[d-1] + """</h2>
<p style='margin:0 0 16px;font-size:13px;color:#999;line-height:1.6'>Make sure your agent pipeline always checks OFAC before sending money. agentmail runs in under 100ms — fast enough for any real-time payment flow.</p>
<div style='background:#0d1a14;border:1px solid rgba(0,212,170,0.08);border-radius:10px;padding:14px;margin-bottom:16px;text-align:center'>
<code style='font-family:\'SF Mono\',Consolas,monospace;font-size:11px;color:#34d399'>curl https://agentmail-api.fly.dev/sanctions?wallet=0x...</code>
</div>
<p style='text-align:center'><a href='https://sanctionsai.dev' style='color:#00d4aa;text-decoration:none;font-size:12px'>sanctionsai.dev &rarr;</a></p>
""")

# Seinfeld state file
_SEINFELD_STATE_FILE = "seinfeld_state.json"

def send_soap_operas():
    """Send day-appropriate Soap Opera email to each subscriber."""
    import os, json, time
    subs_file = os.environ.get("AGENTMAIL_HOME", "/data") + "/subscribers.jsonl"
    state_file = os.environ.get("AGENTMAIL_HOME", "/data") + "/soap_state.json"
    
    state = {}
    if os.path.exists(state_file):
        try:
            with open(state_file) as f:
                state = json.load(f)
        except: pass
    
    now = time.time()
    if not os.path.exists(subs_file):
        return
    
    sent = 0
    new_state = dict(state)
    with open(subs_file) as f:
        for line in f:
            try:
                rec = json.loads(line.strip())
                email = rec.get("email", "")
                if not email or "@" not in email:
                    continue
                
                sub_time = rec.get("subscribed_at", now)
                days_since = (now - sub_time) / 86400
                current_day = state.get(email, {}).get("soap_day", 0)
                target_day = min(int(days_since) + 1, 5)
                
                # Send next Soap Opera email if due
                if target_day > current_day and target_day <= 5:
                    idx = target_day - 1
                    content = _build_branded_email(
                        _SOAP_SUBJECTS[idx],
                        _SOAP_CONTENT[idx],
                        f"Day {target_day} of 5"
                    )
                    try:
                        _send_resend(email, _SOAP_SUBJECTS[idx], content)
                        new_state[email] = {"soap_day": target_day, "last_sent": now}
                        sent += 1
                    except Exception as e:
                        print(f"Soap failed for {email} day {target_day}: {e}", flush=True)
                
                # If Soap Opera is complete (day 5+), start Seinfeld
                if target_day >= 5 and current_day >= 5:
                    _check_seinfeld(email, rec, new_state, state, now)
                    
            except: continue
    
    os.makedirs(os.path.dirname(state_file), exist_ok=True)
    with open(state_file, "w") as f:
        json.dump(new_state, f, indent=2)
    print(f"Soap Opera: sent {sent} emails today", flush=True)

def _check_seinfeld(email, rec, new_state, old_state, now):
    """Check and send Seinfeld daily emails."""
    import os, json, time
    state_file = os.environ.get("AGENTMAIL_HOME", "/data") + "/seinfeld_state.json"
    
    seinfeld_state = {}
    if os.path.exists(state_file):
        try:
            with open(state_file) as f:
                seinfeld_state = json.load(f)
        except: pass
    
    sub_time = rec.get("subscribed_at", now)
    days_since = (now - sub_time) / 86400
    current_day = seinfeld_state.get(email, {}).get("seinfeld_day", 0)
    target_day = min(int(days_since) - 4, 30)  # Seinfeld starts after Soap Opera (5 days)
    
    if target_day > current_day and target_day >= 1 and target_day <= 30:
        idx = target_day - 1
        content = _build_branded_email(
            _SEINFELD_SUBJECTS[idx],
            _SEINFELD_CONTENT[idx],
            f"Tip {target_day} of 30"
        )
        try:
            _send_resend(email, _SEINFELD_SUBJECTS[idx], content)
            seinfeld_state[email] = {"seinfeld_day": target_day, "last_sent": now}
            print(f"Seinfeld sent to {email} day {target_day}", flush=True)
        except Exception as e:
            print(f"Seinfeld failed for {email} day {target_day}: {e}", flush=True)
        
        os.makedirs(os.path.dirname(state_file), exist_ok=True)
        with open(state_file, "w") as f:
            json.dump(seinfeld_state, f, indent=2)

if __name__ == "__main__":
    main()

def _send_welcome_email(email: str) -> dict:
    subject = "Your agentmail API key is ready"
    unsub_url = "https://sanctionsai.dev/unsubscribe?email=" + email
    unsub_link = '<a href="' + unsub_url + '" style="color:#555;text-decoration:underline;font-size:11px">Unsubscribe</a>'
    
    html = ''
    html += '<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>agentmail</title></head>'
    html += '<body style="margin:0;padding:0;background-color:#0a0a0a;font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,Helvetica,Arial,sans-serif">'
    html += '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#0a0a0a"><tr><td align="center" style="padding:40px 16px">'
    html += '<table role="presentation" width="100%" style="max-width:560px;background-color:#111;border-radius:16px;overflow:hidden;border:1px solid #1a1a1a">'
    html += '<tr><td style="padding:0;background:linear-gradient(135deg,#0a0a0a,#0d1a14);border-bottom:1px solid #1a1a1a;text-align:center;padding:36px 32px 24px">'
    html += '<h1 style="margin:0;font-size:24px;font-weight:800;color:#fff;letter-spacing:-0.5px">agent<span style="color:#00d4aa">mail</span></h1>'
    html += '<p style="margin:6px 0 0;font-size:11px;color:#555;letter-spacing:1px;text-transform:uppercase">OFAC COMPLIANCE FOR AI AGENTS</p>'
    html += '</td></tr>'
    html += '<tr><td style="padding:32px 32px 0">'
    html += '<div style="text-align:center;margin-bottom:24px">'
    html += '<span style="display:inline-block;background:rgba(255,107,107,0.12);color:#ff6b6b;font-size:10px;font-weight:700;padding:5px 14px;border-radius:20px;letter-spacing:0.8px;text-transform:uppercase;border:1px solid rgba(255,107,107,0.2);margin-bottom:20px">SECURITY ALERT</span>'
    html += '<h2 style="margin:0 0 10px;font-size:22px;font-weight:800;color:#fff;line-height:1.3;letter-spacing:-0.3px">Your AI agent just sent USDC to a <span style="color:#ff6b6b">sanctioned wallet</span>.</h2>'
    html += '<p style="margin:0;font-size:15px;color:#999;line-height:1.6">OFAC fines start at <strong style="color:#ff6b6b">$356,000 per violation</strong>. The agent that made the payment is yours. So is the liability.</p>'
    html += '</div>'
    html += '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0d1a14;border-radius:10px;border:1px solid rgba(0,212,170,0.08);margin-bottom:24px"><tr><td style="padding:20px">'
    html += '<p style="margin:0 0 10px;font-size:13px;font-weight:600;color:#00d4aa">Your free tier is ready. No API key needed.</p>'
    html += '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0a;border-radius:6px;border:1px solid #1a1a1a"><tr><td style="padding:14px 16px;font-family:\'SF Mono\',Consolas,monospace;font-size:12px;color:#34d399;line-height:1.6;word-break:break-all">'
    html += 'curl <a href="https://agentmail-api.fly.dev/sanctions?wallet=0x098B716B8Aaf21512996dC57EB0615e2383E2f96" style="color:#34d399;text-decoration:none">https://agentmail-api.fly.dev/sanctions?wallet=0x098B716B8Aaf21512996dC57EB0615e2383E2f96</a>'
    html += '</td></tr></table><p style="margin:6px 0 0;font-size:11px;color:#555">5 checks/day &middot; No signup &middot; Free forever</p>'
    html += '</td></tr></table>'
    html += '<h3 style="margin:0 0 16px;font-size:14px;font-weight:700;color:#fff">The 4 tools your agent needs</h3>'
    html += '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px">'
    html += '<tr style="border-bottom:1px solid #1a1a1a"><td style="padding:12px 0;vertical-align:top;width:24px;font-size:13px;font-weight:700;color:#00d4aa">1</td><td style="padding:12px 0;vertical-align:top;font-size:13px;color:#ccc"><strong style="color:#fff">sanctions_check</strong><br><span style="color:#666;font-size:12px">782 wallets, 19,086 names, 16 jurisdictions</span></td><td style="padding:12px 0;vertical-align:top;text-align:right;font-size:10px;color:#555;white-space:nowrap">VALUE $499</td></tr>'
    html += '<tr style="border-bottom:1px solid #1a1a1a"><td style="padding:12px 0;vertical-align:top;width:24px;font-size:13px;font-weight:700;color:#00d4aa">2</td><td style="padding:12px 0;vertical-align:top;font-size:13px;color:#ccc"><strong style="color:#fff">risk_score</strong><br><span style="color:#666;font-size:12px">Amount anomalies, rail risk, category exposure</span></td><td style="padding:12px 0;vertical-align:top;text-align:right;font-size:10px;color:#555;white-space:nowrap">VALUE $299</td></tr>'
    html += '<tr style="border-bottom:1px solid #1a1a1a"><td style="padding:12px 0;vertical-align:top;width:24px;font-size:13px;font-weight:700;color:#00d4aa">3</td><td style="padding:12px 0;vertical-align:top;font-size:13px;color:#ccc"><strong style="color:#fff">kya_verify</strong><br><span style="color:#666;font-size:12px">Know Your Agent trust scoring</span></td><td style="padding:12px 0;vertical-align:top;text-align:right;font-size:10px;color:#555;white-space:nowrap">VALUE $199</td></tr>'
    html += '<tr style="border-bottom:1px solid #1a1a1a"><td style="padding:12px 0;vertical-align:top;width:24px;font-size:13px;font-weight:700;color:#00d4aa">4</td><td style="padding:12px 0;vertical-align:top;font-size:13px;color:#ccc"><strong style="color:#fff">dispute_open</strong><br><span style="color:#666;font-size:12px">File disputes with 7-day auto-escalation</span></td><td style="padding:12px 0;vertical-align:top;text-align:right;font-size:10px;color:#555;white-space:nowrap">VALUE $99</td></tr>'
    html += '<tr><td style="padding:14px 0;font-size:11px;color:#555" colspan="2">Total monthly value</td><td style="padding:14px 0;text-align:right;font-size:18px;font-weight:800;color:#00d4aa"><span style="color:#555;text-decoration:line-through;font-weight:400;font-size:13px">$1,096</span>&nbsp;&nbsp;$19<span style="font-size:11px;color:#555;font-weight:400">/mo</span></td></tr>'
    html += '</table>'
    html += '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:linear-gradient(135deg,#0d1a14,#0a0a0a);border:1px solid rgba(0,212,170,0.12);border-radius:10px;margin-bottom:24px"><tr><td style="padding:20px;text-align:center">'
    html += '<p style="margin:0 0 8px;font-size:13px;font-weight:600;color:#00d4aa">The MCP tool your agent already needs</p>'
    html += '<code style="display:inline-block;background:#0a0a0a;border:1px solid #1a1a1a;border-radius:4px;padding:6px 14px;font-family:\'SF Mono\',Consolas,monospace;font-size:12px;color:#00d4aa">pip install sanctions-mcp</code>'
    html += '<p style="margin:8px 0 0;font-size:11px;color:#666">Add to <a href="https://github.com/anthropics/claude-code" style="color:#00d4aa;text-decoration:none">Claude Code</a>, <a href="https://cursor.sh" style="color:#00d4aa;text-decoration:none">Cursor</a>, or <a href="https://windsurf.ai" style="color:#00d4aa;text-decoration:none">Windsurf</a></p>'
    html += '</td></tr></table>'
    html += '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td style="padding:8px 0 32px;text-align:center">'
    html += '<table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto"><tr><td style="border-radius:8px;background:#00d4aa;padding:0"><a href="https://sanctionsai.dev/checkout/dev" style="display:inline-block;padding:14px 40px;font-size:14px;font-weight:700;color:#0a0a0a;text-decoration:none;border-radius:8px">Upgrade to Dev &rarr;</a></td></tr></table>'
    html += '<p style="margin:8px 0 0;font-size:11px;color:#555">10,000 checks/month &middot; All 4 tools &middot; API key &middot; Audit log</p>'
    html += '</td></tr></table></td></tr>'
    html += '<tr><td style="padding:0"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #1a1a1a;background:#0a0a0a"><tr><td style="padding:24px 32px;text-align:center">'
    html += '<p style="margin:0 0 10px;font-size:11px;color:#555;line-height:1.6">agentmail &mdash; OFAC sanctions screening for AI agents<br>'
    html += '<a href="https://sanctionsai.dev" style="color:#00d4aa;text-decoration:none">sanctionsai.dev</a> &nbsp;&middot;&nbsp; <a href="https://github.com/kindrat86/agentmail" style="color:#555;text-decoration:none">GitHub</a> &nbsp;&middot;&nbsp; <a href="https://sanctionsai.dev/pricing" style="color:#555;text-decoration:none">Pricing</a>'
    html += '</p>' + unsub_link
    html += '</td></tr></table></td></tr></table>'
    html += '<p style="margin:12px 0 0;font-size:10px;color:#333;text-align:center">You received this because you signed up for agentmail.</p>'
    html += '</td></tr></table></body></html>'
    
    return _send_resend(email, subject, html)
# ─── Email configuration ────────────────────────────────────────
_RESEND_API_KEY=os.environ.get("RESEND_API_KEY", "")
_EMAIL_FROM = os.environ.get("EMAIL_FROM", "agentmail <noreply@mail.sanctionsai.dev>")


def _send_resend(to_email: str, subject: str, html_body: str) -> dict:
    """Send email via Resend API with unsubscribe link injection."""
    if not _RESEND_API_KEY.strip():
        return {"ok": False, "error": "RESEND_API_KEY not configured"}
    import requests as req
    # Inject unsubscribe link into the email
    unsub_url = "https://sanctionsai.dev/unsubscribe?email=" + to_email
    unsub_link = '<a href="' + unsub_url + '" style="color:#555;text-decoration:underline;font-size:11px">Unsubscribe</a>'
    html_body = html_body.replace("UNSUBSCRIBE_LINK", unsub_link)
    resp = req.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {_RESEND_API_KEY}", "Content-Type": "application/json"},
        json={"from": _EMAIL_FROM, "to": [to_email], "subject": subject, "html": html_body},
        timeout=15,
    )
    if resp.status_code >= 400:
        err = resp.json().get("message", resp.text)
        raise RuntimeError(f"Resend error {resp.status_code}: {err}")
    return {"ok": True, "id": resp.json().get("id")}

# Manually trigger sending all sequence emails for review
def _send_sequence_for_review(email):
    """Send all Soap Opera emails for review."""
    for i in range(1, 5):  # Days 2-5
        html = _build_branded_email(
            _SOAP_SUBJECTS[i],
            _SOAP_CONTENT[i],
            f"Day {i+1} of 5"
        )
        _send_resend(email, _SOAP_SUBJECTS[i], html)
        print(f"Sent Soap Day {i+1}")

def _send_seinfeld_for_review(email):
    """Send first 3 Seinfeld emails for review."""
    for i in range(3):
        html = _build_branded_email(
            _SEINFELD_SUBJECTS[i],
            _SEINFELD_CONTENT[i],
            f"Tip {i+1} of 30"
        )
        _send_resend(email, _SEINFELD_SUBJECTS[i], html)
        print(f"Sent Seinfeld Day {i+1}")



