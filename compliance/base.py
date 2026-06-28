"""Compliance provider abstraction — swappable backends for agent commerce risk.

Same shape as sms/base.py. A compliance provider screens counterparties,
scores transactions, checks sanctions lists, and records disputes — so an
agent can decide whether to pay before authorizing via x402 / AP2 / ACP / TAP.

Providers:
  - mock  : local, deterministic, no key needed (tests + demos)
  - osint : FREE open sanctions data (OFAC/EU/UN via github), wallet age heuristics (default)
  - paid  : ComplyAdvantage / SumSub / Sift passthrough (Phase 2, B2D enterprise)

A provider implements four capability methods + status():
  kya_verify(agent_id, evidence)                     -> {trust_score, verified, flags, recommendation}
  risk_score(counterparty_id, amount, currency, ...) -> {score, recommendation, reasons, screen_id}
  sanctions_check(name, wallet, country)             -> {matches, clean}
  dispute_open(transaction_id, reason, evidence)     -> {dispute_id, status, escalation_at}
  status()                                           -> {provider, ready, detail}
"""
from __future__ import annotations
from abc import ABC, abstractmethod


class ComplianceProvider(ABC):
    name: str = "base"

    @abstractmethod
    def kya_verify(self, agent_id: str, evidence: dict) -> dict: ...

    @abstractmethod
    def risk_score(self, counterparty_id: str, amount: str,
                   currency: str = "USDC", rail: str = "x402",
                   category: str = "digital_goods") -> dict: ...

    @abstractmethod
    def sanctions_check(self, name: str = "", wallet: str = "",
                        country: str = "") -> dict: ...

    @abstractmethod
    def dispute_open(self, transaction_id: str, reason: str,
                     evidence: dict | None = None) -> dict: ...

    @abstractmethod
    def status(self) -> dict: ...
