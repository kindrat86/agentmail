"""SMS provider package — factory selects backend by env AGENTMAIL_SMS_PROVIDER."""
from .base import SMSProvider
from .mock import MockSMSProvider


def get_provider(name: str | None = None) -> SMSProvider:
    name = name or "mock"
    if name == "mock":
        return MockSMSProvider()
    if name == "fivesim":
        from .fivesim import FiveSimProvider
        return FiveSimProvider()
    if name == "twilio":
        from .twilio import TwilioProvider
        return TwilioProvider()
    raise ValueError(f"unknown SMS provider: {name}")


__all__ = ["SMSProvider", "get_provider", "MockSMSProvider"]
