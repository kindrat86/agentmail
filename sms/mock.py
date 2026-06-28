"""Mock SMS provider — fully testable locally, no key, deterministic OTPs.

Simulates a number that, after a short delay, receives a realistic
verification SMS. Use AGENTMAIL_MOCK_OTP to force a specific code.
"""
from __future__ import annotations
import os
import re
import secrets
import threading
import time
from .base import SMSProvider
from ..otp import extract_code


class MockSMSProvider(SMSProvider):
    name = "mock"

    def __init__(self):
        self._numbers: dict[str, dict] = {}   # id -> {number, country, service, arrived:[]}
        self._lock = threading.Lock()

    def create_number(self, country: str = "any", service: str = "any") -> dict:
        nid = "mock-" + secrets.token_hex(6)
        num = "+1" + "".join(secrets.choice("0123456789") for _ in range(10))
        with self._lock:
            self._numbers[nid] = {"number": num, "country": country, "service": service, "arrived": []}
        # simulate an inbound OTP after a short delay
        delay = float(os.environ.get("AGENTMAIL_MOCK_DELAY", "2.5"))
        code = os.environ.get("AGENTMAIL_MOCK_OTP") or "".join(secrets.choice("0123456789") for _ in range(6))
        sender = os.environ.get("AGENTMAIL_MOCK_FROM", "VerifyApp")
        threading.Thread(target=self._deliver, args=(nid, sender, code, delay), daemon=True).start()
        return {"id": nid, "number": num, "country": country, "service": service, "provider": self.name}

    def _deliver(self, nid, sender, code, delay):
        time.sleep(delay)
        with self._lock:
            if nid in self._numbers:
                self._numbers[nid]["arrived"].append({
                    "from": sender,
                    "text": f"Your {self._numbers[nid]['service']} code is {code}. Do not share it.",
                    "received_at": time.time(),
                })

    def get_sms(self, number_id: str, wait: float = 60.0) -> dict | None:
        deadline = time.time() + wait
        while time.time() < deadline:
            with self._lock:
                n = self._numbers.get(number_id)
                if n and n["arrived"]:
                    msg = n["arrived"][0]
                    return {"from": msg["from"], "text": msg["text"],
                            "code": extract_code(msg["text"]), "received_at": msg["received_at"]}
            time.sleep(1.0)
        return None

    def release_number(self, number_id: str) -> None:
        with self._lock:
            self._numbers.pop(number_id, None)

    def status(self) -> dict:
        return {"provider": self.name, "ready": True, "detail": "local mock, no key needed"}
