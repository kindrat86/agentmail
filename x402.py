"""x402 v2 per-call USDC payments for Sanctions AI.

A dedicated paid route can be called by any x402-capable agent without an API
key. The server returns a protocol-standard 402 challenge, verifies the signed
payment, settles it through a facilitator, and only then returns the resource.

Environment:
  AGENTMAIL_X402_ENABLED       "1" / "true" to enable
  AGENTMAIL_PAY_TO_WALLET      Base wallet receiving USDC
  AGENTMAIL_X402_PRICE_USDC    integer cents per call (default 5 = $0.05)
  AGENTMAIL_X402_FACILITATOR   optional facilitator base URL
  AGENTMAIL_PUBLIC_URL         canonical public origin
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request

_ENABLED = os.environ.get("AGENTMAIL_X402_ENABLED", "").lower() in ("1", "true", "yes")
_PAY_TO = os.environ.get("AGENTMAIL_PAY_TO_WALLET", "").strip()
_PRICE_CENTS = int(os.environ.get("AGENTMAIL_X402_PRICE_USDC", "5"))
_PUBLIC_URL = os.environ.get("AGENTMAIL_PUBLIC_URL", "https://sanctionsai.dev").rstrip("/")
_FACILITATOR = os.environ.get(
    "AGENTMAIL_X402_FACILITATOR", "https://facilitator.payai.network"
).rstrip("/")

# Base mainnet and native USDC.
_BASE_CHAIN = "eip155:8453"
_USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
_USDC_ATOMIC_UNITS_PER_CENT = 10_000  # USDC has 6 decimals; $0.01 = 10,000.
_MAX_TIMEOUT_SECONDS = 60


def is_enabled() -> bool:
    return _ENABLED and bool(_PAY_TO) and _PRICE_CENTS > 0


def status() -> dict:
    return {
        "enabled": is_enabled(),
        "configured": bool(_PAY_TO),
        "pay_to": _PAY_TO[:5] + "..." + _PAY_TO[-4:] if len(_PAY_TO) >= 9 else None,
        "price_usd_cents": _PRICE_CENTS if is_enabled() else None,
        "network": _BASE_CHAIN if is_enabled() else None,
        "facilitator": _FACILITATOR if is_enabled() else None,
        "protocol_version": 2 if is_enabled() else None,
    }


def _accepted_payment() -> dict:
    """Return the x402 v2 PaymentRequirements object for one API call."""
    if not is_enabled():
        return {}
    return {
        "scheme": "exact",
        "network": _BASE_CHAIN,
        "amount": str(_PRICE_CENTS * _USDC_ATOMIC_UNITS_PER_CENT),
        "asset": _USDC_BASE,
        "payTo": _PAY_TO,
        "maxTimeoutSeconds": _MAX_TIMEOUT_SECONDS,
        # EIP-712 domain parameters required by standard EVM x402 clients.
        "extra": {"name": "USD Coin", "version": "2"},
    }


def build_payment_required(resource_url: str, description: str = "") -> dict:
    """Build a protocol-standard x402 v2 PaymentRequired envelope."""
    if not is_enabled():
        return {}
    absolute_url = resource_url if resource_url.startswith("http") else _PUBLIC_URL + resource_url
    return {
        "x402Version": 2,
        "error": "Payment required",
        "resource": {
            "url": absolute_url,
            "description": description or "OFAC sanctions screening for an AI agent payment",
            "mimeType": "application/json",
            "serviceName": "Sanctions AI",
            "tags": ["sanctions", "ofac", "compliance", "wallet", "x402"],
        },
        "accepts": [_accepted_payment()],
        "extensions": {
            "bazaar": {
                "info": {
                    "input": {
                        "type": "http",
                        "method": "GET",
                        "queryParams": {
                            "wallet": {
                                "type": "string",
                                "description": "EVM, Bitcoin, or Tron wallet address to screen",
                                "example": "0x098B716B8Aaf21512996dC57EB0615e2383E2f96",
                            }
                        },
                    },
                    "output": {"type": "object", "format": "application/json"},
                },
                "schema": {
                    "type": "object",
                    "properties": {
                        "input": {
                            "type": "object",
                            "properties": {
                                "queryParams": {
                                    "type": "object",
                                    "properties": {
                                        "wallet": {
                                            "type": "string",
                                            "description": "EVM, Bitcoin, or Tron wallet address to screen",
                                            "example": "0x098B716B8Aaf21512996dC57EB0615e2383E2f96",
                                        }
                                    },
                                    "required": ["wallet"],
                                }
                            },
                            "required": ["queryParams"],
                        },
                        "output": {
                            "type": "object",
                            "properties": {
                                "example": {
                                    "clean": True,
                                    "matches": [],
                                    "x402": {
                                        "paid": True,
                                        "amount": "0.05",
                                        "currency": "USDC",
                                        "network": _BASE_CHAIN,
                                    },
                                }
                            },
                        },
                    },
                    "required": ["input", "output"],
                },
            }
        },
    }


def build_payment_requirements(method: str, path: str, description: str = "") -> dict:
    """Compatibility helper for older API gate callers.

    New code should use :func:`build_payment_required`. This returns the accepted
    PaymentRequirements item expected by facilitator verify/settle calls.
    """
    envelope = build_payment_required(path, description)
    return envelope.get("accepts", [{}])[0] if envelope else {}


def encode_payment_header(payload: dict) -> str:
    """Encode an x402 JSON object for Payment-Required/Payment-Response headers."""
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def _decode_payload(header: str) -> dict:
    """Decode Payment-Signature (base64 JSON), while accepting legacy raw JSON."""
    if not header:
        return {}
    if header.lstrip().startswith("{"):
        try:
            return json.loads(header)
        except ValueError:
            return {}
    try:
        return json.loads(base64.b64decode(header, validate=True).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _post_facilitator(endpoint: str, payment_payload: dict, requirements: dict) -> dict:
    request_body = {
        "x402Version": 2,
        "paymentPayload": payment_payload,
        "paymentRequirements": requirements,
    }
    req = urllib.request.Request(
        f"{_FACILITATOR}/{endpoint}",
        data=json.dumps(request_body, separators=(",", ":")).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "sanctionsai-x402/2.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        return {"transportError": f"facilitator_http_{exc.code}", "detail": body}
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"transportError": "facilitator_unavailable", "detail": str(exc)[:500]}


def verify_and_settle(payment_header: str, payment_required: dict) -> tuple[bool, dict]:
    """Verify and settle a signed x402 payment; fail closed on every error."""
    payment_payload = _decode_payload(payment_header)
    if not payment_payload:
        return False, {"error": "invalid_payment_signature"}
    accepts = payment_required.get("accepts") or []
    if not accepts:
        return False, {"error": "payment_not_configured"}
    requirements = accepts[0]

    verified = _post_facilitator("verify", payment_payload, requirements)
    if not verified.get("isValid"):
        return False, {
            "error": verified.get("invalidReason")
            or verified.get("transportError")
            or "payment_verification_failed",
            "detail": verified.get("invalidMessage") or verified.get("detail"),
        }

    settled = _post_facilitator("settle", payment_payload, requirements)
    if not settled.get("success"):
        return False, {
            "error": settled.get("errorReason")
            or settled.get("transportError")
            or "payment_settlement_failed",
            "detail": settled.get("errorMessage") or settled.get("detail"),
        }
    return True, settled


def verify_payment(payment_header: str, requirements: dict) -> tuple[bool, str]:
    """Legacy compatibility wrapper used by the free-tier quota wall.

    It now settles as well as verifies, preventing successful unpaid calls.
    """
    envelope = {
        "x402Version": 2,
        "resource": {"url": _PUBLIC_URL + "/sanctions"},
        "accepts": [requirements],
    }
    ok, result = verify_and_settle(payment_header, envelope)
    return ok, "" if ok else result.get("error", "payment_failed")
