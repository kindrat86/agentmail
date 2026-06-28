#!/usr/bin/env python3
"""
agentmail MCP server — exposes verification-inbox tools to AI agents.

Tools:
  create_inbox(label?, prefix?)        -> {address, id, label}
  fetch_code(label?, wait?, from?, subject?)  -> {from, subject, code, link}
  list_inboxes()                        -> [{label, address, id}]

Wire into an MCP client (Claude Code / Cursor / Hermes mcp config):
  command: python
  args:    -m agentmail.mcp_server
  (run from the repo root, or pip install -e .)
"""
from __future__ import annotations
import json
from . import core

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as e:
    raise SystemExit(
        "mcp package not installed. Install with:  pip install mcp\n"
        "Then re-run:  python -m agentmail.mcp_server"
    ) from e

mcp = FastMCP("agentmail")


@mcp.tool()
def create_inbox(label: str = "default", prefix: str | None = None) -> str:
    """Create a fresh disposable email inbox (or reuse an existing one by label).

    Use this when an agent needs an email address to sign up / receive a
    verification message. Returns the address. Poll fetch_code to get the OTP.
    """
    return json.dumps(core.create_inbox(label=label, prefix=prefix))


@mcp.tool()
def fetch_code(label: str = "default", wait: float = 60.0,
               match_from: str | None = None, match_subject: str | None = None) -> str:
    """Fetch the latest verification code/link from an inbox.

    `wait` seconds for a message to arrive (polls). Optional `match_from` /
    `match_subject` substrings filter which message counts. Returns extracted
    `code` and any verification `link`, or {"empty": true}.
    """
    return json.dumps(core.fetch_latest(label=label, wait=wait,
                                        match_from=match_from, match_subject=match_subject) or {"empty": True})


@mcp.tool()
def list_inboxes() -> str:
    """List all existing labeled inboxes/numbers."""
    return json.dumps(core.list_inboxes())


# ── SMS / phone OTP ──

@mcp.tool()
def create_number(label: str = "default", country: str = "any", service: str = "any") -> str:
    """Rent a phone number that can receive SMS/OTP codes.

    Use this when an agent must verify via phone (WhatsApp, Telegram, banks,
    apps requiring SMS). Returns the rented `number`. Poll fetch_sms for the
    OTP. `country` e.g. "usa","russia","any"; `service` e.g. "discord",
    "google","any" (provider may use it to pick a suitable number).
    """
    return json.dumps(core.create_number(label=label, country=country, service=service))


@mcp.tool()
def fetch_sms(label: str = "default", wait: float = 90.0) -> str:
    """Fetch the latest SMS (OTP) for a labeled number.

    Polls up to `wait` seconds for a message to arrive. Returns extracted
    `code` and sender `from`, or {"empty": true}.
    """
    return json.dumps(core.fetch_sms(label=label, wait=wait) or {"empty": True})


@mcp.tool()
def release_number(label: str = "default") -> str:
    """Stop renting a phone number and free it. Call when you're done with OTP."""
    return json.dumps(core.release_number(label=label))


# ── Compliance / risk / KYA ──

@mcp.tool()
def kya_verify(agent_id: str, evidence: dict) -> str:
    """Verify an AI agent's identity before transacting with it (Know Your Agent).

    Call BEFORE paying or trusting another agent. Returns a trust score + flags.
    evidence keys (any subset): wallet_address, wallet_age_days, domain, pubkey,
    owner_email, declared_country. Higher trust = more verified attributes and
    a clean sanctions screen. Use the returned recommendation to decide whether
    to proceed with a counterparty agent.
    Returns: {trust_score: 0-100, verified: [...], flags: [...], recommendation}
    """
    return json.dumps(core.kya_verify(agent_id=agent_id, evidence=evidence))


@mcp.tool()
def risk_score(counterparty_id: str, amount: str, currency: str = "USDC",
               rail: str = "x402", category: str = "digital_goods") -> str:
    """Score a transaction's fraud risk BEFORE authorizing payment.

    Call right before an agent pays. Combines counterparty signals + amount
    anomalies + sanctions screen + rail/category heuristics. Recommendation is
    one of: allow / review / decline. 'decline' = abort the payment.
    rail in: x402, ap2, acp, tap. category in: digital_goods, services, physical.
    Returns: {score: 0-100, recommendation, reasons: [...], screen_id}
    """
    return json.dumps(core.risk_score(counterparty_id=counterparty_id, amount=amount,
                                      currency=currency, rail=rail, category=category))


@mcp.tool()
def sanctions_check(name: str = "", wallet: str = "", country: str = "") -> str:
    """Screen a counterparty against OFAC/EU/UN/UK sanctions lists.

    Cheapest check, call first. At least one of name / wallet / country required.
    Free provider uses open sanctions data (no key). Useful as a fast pre-filter
    before the heavier risk_score call.
    Returns: {matches: [{list, entity, match_type, confidence}], clean: bool}
    """
    return json.dumps(core.sanctions_check(name=name, wallet=wallet, country=country))


@mcp.tool()
def dispute_open(transaction_id: str, reason: str, evidence: dict | None = None) -> str:
    """Open a dispute when an agent-paid transaction went bad (non-delivery, fraud).

    Records the dispute with a 7-day auto-escalation window. Phase 1 = registry
    + notification; Phase 2 will integrate agentcourt-api for arbitration.
    Returns: {dispute_id, status, escalation_at}
    """
    return json.dumps(core.dispute_open(transaction_id=transaction_id, reason=reason,
                                        evidence=evidence))


if __name__ == "__main__":
    mcp.run()
