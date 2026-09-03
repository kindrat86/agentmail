"""HTTP client for the sanctionsai.dev x402-gated screening endpoint.

The endpoint implements the x402 v2 flow: an unpaid GET returns
402 with a base64-encoded Payment-Required header containing the
payment requirements (asset, amount, network, payTo). A paid GET
repeats the request with a Payment-Signature header.

This module is transport-injected for testability: pass any callable
``transport(method, url, headers) -> (status, headers, body_bytes)``.
The default transport uses urllib (stdlib).
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BASE_URL = os.environ.get("SANCTIONSAI_BASE_URL", "https://sanctionsai.dev").rstrip("/")
X402_SCREEN_PATH = "/x402/sanctions"
QUICKSTART_URL = "https://sanctionsai.dev/x402-quickstart"
PRICE_USD = "0.05"
PRICE_DESCRIPTION = "$0.05 per call, USDC on Base (eip155:8453), via the x402 protocol"


def default_transport(method: str, url: str, headers: dict) -> tuple[int, dict, bytes]:
    """Real network transport. Returns (status, headers-lowercased, body)."""
    req = urllib.request.Request(url, method=method)
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read()
    except urllib.error.HTTPError as e:  # 402 arrives here, not as a response
        return e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, e.read()


def decode_payment_required(header_value: str) -> dict:
    """Decode the base64 Payment-Required header into its x402 JSON object."""
    return json.loads(base64.b64decode(header_value).decode("utf-8"))


def screen(subject_type: str, name: str = "", country: str = "",
           wallet: str = "", transport=None) -> dict:
    """Call the x402 screening endpoint once and normalize the outcome.

    subject_type: "name" | "company" | "wallet" (labels the call, both name
      and company hit the same ?name= parameter).
    Returns one of:
      {"ok": True, "paid": True, "result": <server JSON>}          - paid 200
      {"ok": True, "requires_payment": True, "payment_required": {...},
       "how_to_pay": "..."}                                         - 402 challenge
      {"ok": False, "error": "..."}                                 - failure
    """
    transport = transport or default_transport
    params = {}
    if name:
        params["name"] = name
    if country:
        params["country"] = country
    if wallet:
        params["wallet"] = wallet
    if not params:
        return {"ok": False, "error": "name, company, or wallet is required"}
    query = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    url = f"{DEFAULT_BASE_URL}{X402_SCREEN_PATH}?{query}"
    try:
        status, headers, body = transport("GET", url, {"Accept": "application/json"})
    except Exception as e:  # network down, DNS, timeout
        return {"ok": False, "error": f"transport failure: {e}"}

    if status == 402:
        pr_header = headers.get("payment-required", "")
        try:
            payment_required = decode_payment_required(pr_header)
        except Exception:
            payment_required = {"raw": pr_header[:200]} if pr_header else {}
        accepts = payment_required.get("accepts", [])
        price_hint = ""
        if accepts:
            a = accepts[0]
            price_hint = (f" {a.get('asset', 'asset')}-{a.get('network', '')}"
                          f" amount {a.get('amount', '?')} atomic units")
        return {
            "ok": True,
            "requires_payment": True,
            "subject_type": subject_type,
            "payment_required": payment_required,
            "how_to_pay": (
                "This screening call is x402-gated at " + PRICE_DESCRIPTION + "."
                " Pay the challenge in payment_required (retry this request with a"
                " Payment-Signature header) or follow the 60-second quickstart: "
                + QUICKSTART_URL
            ) + price_hint,
        }

    if status == 200:
        try:
            return {"ok": True, "paid": True, "result": json.loads(body.decode("utf-8"))}
        except Exception as e:
            return {"ok": False, "error": f"unparseable 200 body: {e}"}

    return {"ok": False, "error": f"unexpected status {status}: {body[:200]!r}"}
