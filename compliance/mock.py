"""Mock compliance provider — fully testable locally, no key, deterministic risk.

Simulates a real compliance screen with rule-based scoring so the full MCP /
HTTP / CLI loop works end-to-end without any external API or key.

Determinism knobs via env:
  AGENTMAIL_MOCK_KYA_FORCE   -> force a trust_score (0-100) for all kya_verify
  AGENTMAIL_MOCK_RISK_FORCE  -> force a risk score (0-100) for all risk_score
  AGENTMAIL_MOCK_SANCTIONED  -> comma-separated names always flagged on sanctions

This is the "brain" you swap out for osint.py (real sanctions data) or paid.py
(ComplyAdvantage). The interface stays identical.
"""
from __future__ import annotations
import os
import re
import secrets
import threading
import time
from .base import ComplianceProvider

# Tiny embedded test list — simulates what osint.py pulls from OFAC/EU/UN.
# Real provider replaces this with the live lists.
_EMBEDDED_FLAGGED = {
    "names": {"john doe sanctions", "test sanctioned entity", "acme blocked ltd"},
    "wallets": {"0xdead000000000000000000000000000000000000",
                "0xbadbadbadbadbadbadbadbadbadbadbadbadbad0"},
    "countries_high_risk": {"kp", "ir", "sy", "cu"},  # ISO-2 high-risk
}

# Recommendations bucket the score so callers get an actionable verdict.
def _bucket(score: int) -> str:
    if score >= 75:
        return "allow"
    if score >= 40:
        return "review"
    return "decline"


class MockComplianceProvider(ComplianceProvider):
    name = "mock"

    def __init__(self):
        self._disputes: dict[str, dict] = {}
        self._lock = threading.Lock()

    # ─── Know Your Agent ───
    def kya_verify(self, agent_id: str, evidence: dict) -> dict:
        """Trust score = how many attributes the agent can prove + sanctions clean."""
        evidence = evidence or {}
        verified: list[str] = []
        flags: list[str] = []
        score = 10  # baseline: unknown but present

        # Each verifiable attribute adds trust
        if evidence.get("wallet_address") and re.match(r"^0x[a-fA-F0-9]{40}$", evidence["wallet_address"]):
            verified.append("wallet_address_format")
            score += 15
            # wallet age heuristic — mock assumes older = safer
            age_days = int(evidence.get("wallet_age_days", 0) or 0)
            if age_days > 365:
                verified.append("wallet_age_>1y")
                score += 10
            elif age_days < 7:
                flags.append("wallet_age_<7d")
                score -= 5
        if evidence.get("domain"):
            verified.append("domain_declared")
            score += 10
            if not str(evidence["domain"]).startswith("temp"):
                verified.append("domain_not_disposable")
                score += 5
        if evidence.get("pubkey"):
            verified.append("pubkey_present")
            score += 10
        if evidence.get("owner_email"):
            verified.append("owner_email_declared")
            score += 5
        # declared country — if high-risk, big penalty
        country = (evidence.get("declared_country") or "").lower()
        if country:
            verified.append(f"country_declared:{country}")
            if country in _EMBEDDED_FLAGGED["countries_high_risk"]:
                flags.append(f"high_risk_jurisdiction:{country}")
                score -= 25

        force = os.environ.get("AGENTMAIL_MOCK_KYA_FORCE")
        if force is not None:
            score = int(force)

        score = max(0, min(100, score))
        return {
            "agent_id": agent_id,
            "trust_score": score,
            "verified": verified,
            "flags": flags,
            "recommendation": _bucket(score),
            "provider": self.name,
        }

    # ─── Transaction risk score ───
    def risk_score(self, counterparty_id: str, amount: str,
                   currency: str = "USDC", rail: str = "x402",
                   category: str = "digital_goods") -> dict:
        """Combined score: amount anomalies + rail/category heuristics + sanctions."""
        reasons: list[str] = []
        score = 70  # start neutral-good, deduct for red flags

        try:
            amt = float(amount)
        except (TypeError, ValueError):
            amt = 0.0
            reasons.append("amount_unparseable")
            score -= 20

        # Amount bands — large single tx is the classic fraud signal
        if amt >= 10000:
            score -= 35; reasons.append(f"very_large_amount:{amount}")
        elif amt >= 1000:
            score -= 15; reasons.append(f"large_amount:{amount}")
        elif amt > 0 and amt < 0.01:
            score -= 10; reasons.append("dust_amount_suspicious")

        # Rail — newer rails are higher variance
        rail_penalties = {"tap": 0, "acp": -5, "ap2": -5, "x402": -10}
        rail_p = rail_penalties.get((rail or "").lower(), -10)
        score += rail_p
        if rail_p:
            reasons.append(f"rail_risk:{rail}")

        # Category — physical goods have chargeback exposure
        if category == "physical":
            score -= 10; reasons.append("physical_chargeback_risk")
        elif category == "services":
            score -= 5; reasons.append("services_delivery_risk")

        # Currency — non-stablecoin fiat adds AML exposure (mock heuristic)
        if currency.upper() not in ("USDC", "USDT", "DAI", "EURC"):
            score -= 5; reasons.append(f"non_stable_currency:{currency}")

        # Reuse sanctions check — counterparty_id treated as name-or-wallet
        screen = self.sanctions_check(name=counterparty_id, wallet=counterparty_id)
        if not screen["clean"]:
            score -= 50
            for m in screen["matches"]:
                reasons.append(f"sanctions_match:{m['list']}")

        force = os.environ.get("AGENTMAIL_MOCK_RISK_FORCE")
        if force is not None:
            score = int(force)

        score = max(0, min(100, score))
        screen_id = "scr_" + secrets.token_hex(8)
        return {
            "counterparty_id": counterparty_id,
            "score": score,
            "recommendation": _bucket(score),
            "reasons": reasons,
            "screen_id": screen_id,
            "provider": self.name,
        }

    # ─── Sanctions screen ───
    def sanctions_check(self, name: str = "", wallet: str = "",
                        country: str = "") -> dict:
        matches: list[dict] = []
        nl = (name or "").strip().lower()
        wl = (wallet or "").strip().lower()
        cl = (country or "").strip().lower()

        # Forced-flag override (for deterministic tests)
        forced = os.environ.get("AGENTMAIL_MOCK_SANCTIONED", "")
        if forced and nl in [f.strip().lower() for f in forced.split(",") if f.strip()]:
            matches.append({"list": "MOCK_FORCED", "entity": name,
                            "match_type": "name_exact", "confidence": 1.0})

        if nl and nl in _EMBEDDED_FLAGGED["names"]:
            matches.append({"list": "OFAC_SDN", "entity": name,
                            "match_type": "name_exact", "confidence": 0.98})
        if wl and wl.lower() in _EMBEDDED_FLAGGED["wallets"]:
            matches.append({"list": "OFAC_SDN", "entity": wallet,
                            "match_type": "wallet_exact", "confidence": 1.0})
        if cl and cl in _EMBEDDED_FLAGGED["countries_high_risk"]:
            matches.append({"list": "OFAC_COUNTRY", "entity": country,
                            "match_type": "country_embargoed", "confidence": 1.0})

        return {"matches": matches, "clean": len(matches) == 0,
                "checked": {"name": name, "wallet": wallet, "country": country},
                "provider": self.name}

    # ─── Dispute registry (Phase 1: record + notify; Phase 2: arbitration) ───
    def dispute_open(self, transaction_id: str, reason: str,
                     evidence: dict | None = None) -> dict:
        did = "dsp_" + secrets.token_hex(6)
        now = time.time()
        escalation_at = now + 7 * 86400  # 7-day auto-escalation window
        record = {
            "dispute_id": did,
            "transaction_id": transaction_id,
            "reason": reason,
            "evidence": evidence or {},
            "status": "open",
            "opened_at": now,
            "escalation_at": escalation_at,
        }
        with self._lock:
            self._disputes[did] = record
        # In production this would fire a webhook to both parties.
        return {k: v for k, v in record.items()
                if k != "evidence"} | {"evidence_stored": bool(evidence),
                                       "provider": self.name}

    def status(self) -> dict:
        with self._lock:
            open_count = sum(1 for d in self._disputes.values() if d["status"] == "open")
        return {"provider": self.name, "ready": True,
                "detail": "local mock, no key needed — rule-based scoring",
                "disputes_open": open_count}
