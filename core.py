"""
agentmail — Verification inbox for AI agents.

Two front-ends over the same Mail.tm backend:
  1. HTTP API  (python api.py)        — REST, any agent can call
  2. MCP server (python mcp_server.py) — for Claude Code / Cursor / Hermes

A persistent inbox registry (~/.agentmail/inboxes.json) maps a label -> live client
so an agent can create an inbox, go do something, and come back to fetch the code.
"""
from __future__ import annotations
import json
import os
import threading
from pathlib import Path
from .mailtm import MailTmClient
from .otp import analyze
from .sms import get_provider as _sms_get_provider
from .compliance import get_provider as _compliance_get_provider

REGISTRY_PATH = Path(os.environ.get("AGENTMAIL_HOME", str(Path.home() / ".agentmail"))) / "inboxes.json"
COMPLIANCE_REGISTRY_PATH = Path(os.environ.get("AGENTMAIL_HOME", str(Path.home() / ".agentmail"))) / "compliance.json"
_lock = threading.Lock()
_clients: dict[str, MailTmClient] = {}
# SMS provider is process-wide; provider holds its own number state
_sms_provider = None
SMS_PROVIDER_NAME = os.environ.get("AGENTMAIL_SMS_PROVIDER", "mock")
# Compliance provider is process-wide; provider holds its own dispute state
_compliance_provider = None
COMPLIANCE_PROVIDER_NAME = os.environ.get("AGENTMAIL_COMPLIANCE_PROVIDER", "osint")


def _load() -> dict:
    if REGISTRY_PATH.exists():
        try:
            return json.loads(REGISTRY_PATH.read_text())
        except Exception:
            return {}
    return {}


def _save(data: dict) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(data, indent=2))


def _client_for(label: str, creds: dict | None) -> MailTmClient:
    """Rehydrate a client from stored credentials (address+password) so token can refresh."""
    c = MailTmClient()
    if creds:
        c.address = creds["address"]
        # re-login to get a fresh token
        try:
            t = c.s.post(f"https://api.mail.tm/token",
                         json={"address": creds["address"], "password": creds["password"]}, timeout=20)
            t.raise_for_status()
            c.token = t.json()["token"]
            c.s.headers["Authorization"] = f"Bearer {c.token}"
        except Exception as e:
            raise RuntimeError(f"cannot rehydrate inbox '{label}': {e}")
    return c


def create_inbox(label: str = "default", prefix: str | None = None) -> dict:
    with _lock:
        reg = _load()
        if label in reg:
            return {"address": reg[label]["address"], "id": reg[label]["id"], "label": label, "reused": True}
        c = MailTmClient()
        info = c.create_inbox(prefix=prefix)
        reg[label] = {"address": info["address"], "id": info["id"], "password": c.password}
        _save(reg)
        _clients[label] = c
        return {"address": info["address"], "id": info["id"], "label": label, "reused": False}


def fetch_latest(label: str = "default", wait: float = 0.0,
                 match_from: str | None = None, match_subject: str | None = None) -> dict | None:
    with _lock:
        reg = _load()
        if label not in reg:
            raise KeyError(f"no inbox labeled '{label}'")
        c = _clients.get(label)
        if c is None or c.token is None:
            c = _client_for(label, reg[label])
            _clients[label] = c

    if wait and wait > 0.5:
        msg = c.wait_for_message(timeout=wait, match_from=match_from, match_subject=match_subject)
    else:
        msgs = c.list_messages()
        msg = msgs[0] if msgs else None
        if msg:
            msg = c.get_message(msg["id"])
            msg = {"from": (msg.get("from") or {}).get("address"),
                   "subject": msg.get("subject"), "intro": msg.get("intro"),
                   "text": msg.get("text") or ""}
    if not msg:
        return None
    info = analyze(msg.get("text", ""))
    return {
        "from": msg.get("from"),
        "subject": msg.get("subject"),
        "intro": msg.get("intro"),
        "code": info["code"],
        "link": info["link"],
        "raw_excerpt": (msg.get("text") or "")[:300],
    }


def list_inboxes() -> list[dict]:
    reg = _load()
    return [{"label": k, "address": v["address"], "id": v["id"]} for k, v in reg.items()]


# ───────────────────────── SMS / phone OTP ─────────────────────────

def _sms():
    global _sms_provider
    if _sms_provider is None:
        _sms_provider = _sms_get_provider(SMS_PROVIDER_NAME)
    return _sms_provider


def create_number(label: str = "default", country: str = "any", service: str = "any") -> dict:
    """Rent a phone number that can receive SMS/OTP. Returns {id, number, ...}."""
    p = _sms()
    with _lock:
        reg = _load()
        if label in reg and "number" in reg[label]:
            return {"id": reg[label]["id"], "number": reg[label]["number"],
                    "label": label, "reused": True, "provider": p.name}
    info = p.create_number(country=country, service=service)
    info["label"] = label
    info["reused"] = False
    with _lock:
        reg = _load()
        reg.setdefault(label, {}).update({"number": info["number"], "id": info["id"]})
        _save(reg)
    return info


def fetch_sms(label: str = "default", wait: float = 90.0) -> dict | None:
    """Fetch the latest SMS/OTP for a labeled number. Polls `wait` seconds."""
    with _lock:
        reg = _load()
        if label not in reg or "number" not in reg[label]:
            raise KeyError(f"no number labeled '{label}'")
        nid = reg[label]["id"]
    msg = _sms().get_sms(nid, wait=wait)
    if not msg:
        return None
    return {"from": msg.get("from"), "text": msg.get("text"),
            "code": msg.get("code"), "received_at": msg.get("received_at")}


def release_number(label: str = "default") -> dict:
    """Stop renting a number (free it)."""
    with _lock:
        reg = _load()
        if label not in reg:
            raise KeyError(f"no number labeled '{label}'")
        nid = reg[label].get("id")
        reg.pop(label, None)
        _save(reg)
    if nid:
        try:
            _sms().release_number(nid)
        except Exception:
            pass
    return {"label": label, "released": True}


def sms_status() -> dict:
    """Health/info of the active SMS provider (balance, mode, etc.)."""
    return _sms().status()


# ───────────────────────── COMPLIANCE / risk / KYA ─────────────────────────
#
# Compliance is the third capability layer: where email = identity-via-OTP
# and SMS = phone verification, compliance = transaction verification.
# Use these BEFORE an agent authorizes a payment via x402 / AP2 / ACP / TAP.
# Provider holds its own dispute state; compliance.json persists disputes only.

def _compliance():
    global _compliance_provider
    if _compliance_provider is None:
        _compliance_provider = _compliance_get_provider(COMPLIANCE_PROVIDER_NAME)
    return _compliance_provider


def _load_compliance() -> dict:
    if COMPLIANCE_REGISTRY_PATH.exists():
        try:
            return json.loads(COMPLIANCE_REGISTRY_PATH.read_text())
        except Exception:
            return {}
    return {}


def _save_compliance(data: dict) -> None:
    COMPLIANCE_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    COMPLIANCE_REGISTRY_PATH.write_text(json.dumps(data, indent=2))


def kya_verify(agent_id: str, evidence: dict | None = None) -> dict:
    """Know Your Agent — verify counterparty identity before transacting.

    evidence keys (any subset): wallet_address, wallet_age_days, domain, pubkey,
    owner_email, declared_country. Returns trust_score 0-100, verified attrs,
    flags, and a recommendation: allow / review / decline.
    """
    return _compliance().kya_verify(agent_id, evidence or {})


def risk_score(counterparty_id: str, amount: str, currency: str = "USDC",
               rail: str = "x402", category: str = "digital_goods") -> dict:
    """Pre-payment fraud risk for a transaction. Recommendation: allow/review/decline.

    rail in: x402, ap2, acp, tap. category in: digital_goods, services, physical.
    """
    return _compliance().risk_score(counterparty_id, amount=amount,
                                    currency=currency, rail=rail, category=category)


def sanctions_check(name: str = "", wallet: str = "", country: str = "") -> dict:
    """Screen against OFAC/EU/UN/UK sanctions lists. At least one identifier required."""
    return _compliance().sanctions_check(name=name, wallet=wallet, country=country)


def dispute_open(transaction_id: str, reason: str,
                 evidence: dict | None = None) -> dict:
    """Open a dispute on an agent-paid transaction. Records to compliance.json
    with a 7-day auto-escalation window. Phase 1 = registry + notification;
    Phase 2 will integrate agentcourt-api for policy-driven arbitration.
    """
    result = _compliance().dispute_open(transaction_id, reason, evidence)
    # Persist to compliance.json so disputes survive restarts
    with _lock:
        reg = _load_compliance()
        reg[result["dispute_id"]] = {
            **result,
            "evidence": evidence or {},
            "provider": COMPLIANCE_PROVIDER_NAME,
        }
        _save_compliance(reg)
    return result


def compliance_status() -> dict:
    """Health/info of the active compliance provider."""
    return _compliance().status()
