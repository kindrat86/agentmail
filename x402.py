"""x402 per-call payment gateway for agentmail.

Lets an AI agent pay USDC on Base for each API call, no API key needed.
Flow (HTTP 402 protocol):
  1. Agent calls an endpoint without payment
  2. Server returns 402 + Payment-Requirements (price, pay_to wallet, network)
  3. Agent pays USDC on Base, retries with X-PAYMENT header (signed payload)
  4. Server verifies via x402.org facilitator → returns the result

Config (env):
  AGENTMAIL_X402_ENABLED    — "1" to enable (default off)
  AGENTMAIL_PAY_TO_WALLET   — your USDC receiving wallet on Base (0x...)
  AGENTMAIL_X402_PRICE_USDC — price per call in USD cents (default "1" = $0.01)

Uses the official x402 Python SDK (pip install x402[evm,requests]) when available,
with a stdlib fallback that talks directly to the facilitator HTTP API so the
server starts even without the full SDK installed.
"""
from __future__ import annotations
import json
import os
import time
import urllib.request

_ENABLED = os.environ.get("AGENTMAIL_X402_ENABLED", "").lower() in ("1", "true", "yes")
_PAY_TO = os.environ.get("AGENTMAIL_PAY_TO_WALLET", "")
_PRICE_CENTS = int(os.environ.get("AGENTMAIL_X402_PRICE_USDC", "1"))  # cents per call
_FACILITATOR = "https://x402.org/facilitator"
# Base mainnet chain id = 8453; USDC proxy on Base = 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913
_BASE_CHAIN = "eip155:8453"
_USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

# Lazy-loaded SDK client
_sdk_server = None


def is_enabled() -> bool:
    return _ENABLED and bool(_PAY_TO)


def status() -> dict:
    return {
        "enabled": is_enabled(),
        "configured": bool(_PAY_TO),
        "pay_to": _PAY_TO[:8] + "..." if _PAY_TO else None,
        "price_usd_cents": _PRICE_CENTS if is_enabled() else None,
        "network": _BASE_CHAIN if is_enabled() else None,
        "facilitator": _FACILITATOR if is_enabled() else None,
    }


def build_payment_requirements(method: str, path: str, description: str = "") -> dict:
    """Build the 402 response body — tells the agent what to pay and where.

    Follows the x402 PaymentRequirements schema (version 1)."""
    if not is_enabled():
        return {}
    price_usd = f"${_PRICE_CENTS / 100:.2f}"
    return {
        "scheme": "exact",
        "network": _BASE_CHAIN,
        "maxAmountRequired": price_usd,
        "resource": path,
        "description": description or f"agentmail {path} call",
        "mime_type": "application/json",
        "pay_to": _PAY_TO,
        "asset": _USDC_BASE,
        "created_at": int(time.time()),
    }


def verify_payment(payment_header: str, requirements: dict) -> tuple[bool, str]:
    """Verify an X-PAYMENT header against requirements via the facilitator.

    payment_header is a base64-encoded JSON PaymentPayload (x402 v1).
    Returns (valid, reason). On success reason is empty."""
    if not payment_header:
        return False, "missing_payment_header"
    # Build the verify request per facilitator API.
    payload = json.dumps({
        "paymentPayload": _decode_payload(payment_header),
        "paymentRequirements": requirements,
    }).encode()
    req = urllib.request.Request(
        f"{_FACILITATOR}/verify",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            resp = json.loads(r.read())
    except Exception as e:
        return False, f"facilitator_error: {e}"
    if resp.get("isValid"):
        return True, ""
    return False, resp.get("invalidReason", "invalid_payment")


def _decode_payload(header: str) -> dict:
    """Decode the X-PAYMENT header. x402 clients send base64-JSON or raw JSON."""
    if header.strip().startswith("{"):
        try:
            return json.loads(header)
        except ValueError:
            pass
    import base64
    try:
        decoded = base64.b64decode(header).decode()
        return json.loads(decoded)
    except Exception:
        return {"raw": header}
