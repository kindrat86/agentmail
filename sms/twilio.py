"""Twilio provider — owned numbers, enterprise/KYC'd tier. Premium backend.

Docs: https://www.twilio.com/docs/sms
Env: AGENTMAIL_TWILIO_SID, AGENTMAIL_TWILIO_TOKEN, AGENTMAIL_TWILIO_NUMBER (optional owned number)

Two modes:
  1. OWNED (recommended): you buy one number, it receives many OTPs. Set
     AGENTMAIL_TWILIO_NUMBER. create_number() returns that same number; SMS
     are pulled from the message list.
  2. BUY: no number set -> create_number() buys a new number (~$1/mo). More
     expensive; only for always-on enterprise use.

For disposable agent OTP, use the 5sim provider instead — Twilio trial mode
also requires verified recipient numbers, which breaks autonomy.
"""
from __future__ import annotations
import os
import time
import requests
from requests.auth import HTTPBasicAuth
from .base import SMSProvider
from ..otp import extract_code

BASE = "https://api.twilio.com/2010-04-01"


class TwilioProvider(SMSProvider):
    name = "twilio"

    def __init__(self):
        self.sid = os.environ.get("AGENTMAIL_TWILIO_SID")
        self.token = os.environ.get("AGENTMAIL_TWILIO_TOKEN")
        self.owned = os.environ.get("AGENTMAIL_TWILIO_NUMBER")  # e.g. +15551234567
        if not (self.sid and self.token):
            raise RuntimeError("set AGENTMAIL_TWILIO_SID and AGENTMAIL_TWILIO_TOKEN")
        self.auth = HTTPBasicAuth(self.sid, self.token)

    def status(self) -> dict:
        try:
            r = requests.get(f"{BASE}/Accounts/{self.sid}.json", auth=self.auth, timeout=15)
            return {"provider": self.name, "ready": r.status_code == 200,
                    "owned_number": self.owned, "mode": "owned" if self.owned else "buy"}
        except Exception as e:
            return {"provider": self.name, "ready": False, "detail": str(e)}

    def create_number(self, country: str = "any", service: str = "any") -> dict:
        if self.owned:
            return {"id": self.owned, "number": self.owned, "country": "owned",
                    "service": service, "provider": self.name}
        # buy a number
        r = requests.get(f"{BASE}/AvailablePhoneNumbers/US/Local.json", auth=self.auth,
                         params={"SmsEnabled": "true", "Limit": 1}, timeout=20)
        r.raise_for_status()
        cand = r.json().get("available_phone_numbers", [])
        if not cand:
            raise RuntimeError("no available Twilio number")
        num = cand[0]["phone_number"]
        b = requests.post(f"{BASE}/Accounts/{self.sid}/IncomingPhoneNumbers.json", auth=self.auth,
                          data={"PhoneNumber": num, "SmsUrl": ""}, timeout=20)
        b.raise_for_status()
        return {"id": num, "number": num, "country": "US", "service": service, "provider": self.name}

    def get_sms(self, number_id: str, wait: float = 90.0) -> dict | None:
        deadline = time.time() + wait
        seen: set[str] = set()
        while time.time() < deadline:
            r = requests.get(f"{BASE}/Accounts/{self.sid}/Messages.json", auth=self.auth,
                             params={"To": number_id, "PageSize": 5}, timeout=20)
            if r.status_code == 200:
                for m in r.json().get("messages", []):
                    if m["sid"] in seen:
                        continue
                    seen.add(m["sid"])
                    if m.get("direction", "").startswith("inbound"):
                        return {"from": m.get("from"), "text": m.get("body"),
                                "code": extract_code(m.get("body") or ""),
                                "received_at": m.get("date_created")}
            time.sleep(4.0)
        return None

    def release_number(self, number_id: str) -> None:
        if self.owned:
            return  # don't release a number you own
        # find the IncomingPhoneNumber sid and delete
        try:
            r = requests.get(f"{BASE}/Accounts/{self.sid}/IncomingPhoneNumbers.json",
                             auth=self.auth, params={"PhoneNumber": number_id}, timeout=20)
            nums = r.json().get("incoming_phone_numbers", [])
            for n in nums:
                requests.delete(f"{BASE}/Accounts/{self.sid}/IncomingPhoneNumbers/{n['sid']}.json",
                                auth=self.auth, timeout=20)
        except Exception:
            pass
