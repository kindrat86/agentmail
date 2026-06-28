"""Compliance provider package — factory selects backend by env AGENTMAIL_COMPLIANCE_PROVIDER."""
from .base import ComplianceProvider
from .mock import MockComplianceProvider


def get_provider(name: str | None = None) -> ComplianceProvider:
    # osint is the default: real OFAC SDN data, free, no key. Falls back to a
    # cached/embedded list if the network is down (see osint.status()).
    name = name or "osint"
    if name == "mock":
        return MockComplianceProvider()
    if name == "osint":
        from .osint import OsintComplianceProvider
        return OsintComplianceProvider()
    if name == "paid":
        # Phase 2: ComplyAdvantage / SumSub / Sift passthrough
        raise NotImplementedError(
            "paid provider not yet implemented. Use 'osint' (default, real OFAC "
            "data) for now, or implement compliance/paid.py wrapping the "
            "ComplyAdvantage API."
        )
    raise ValueError(f"unknown compliance provider: {name}")


__all__ = ["ComplianceProvider", "get_provider", "MockComplianceProvider"]
