"""agentmail package — compliance & verification toolkit for AI agents."""
from .core import (
    create_inbox, fetch_latest, list_inboxes,
    create_number, fetch_sms, release_number, sms_status,
    kya_verify, risk_score, sanctions_check, dispute_open, compliance_status,
)

__all__ = [
    "create_inbox", "fetch_latest", "list_inboxes",
    "create_number", "fetch_sms", "release_number", "sms_status",
    "kya_verify", "risk_score", "sanctions_check", "dispute_open", "compliance_status",
]
__version__ = "0.4.0"
