"""5sim.net provider — disposable SMS number rental. The default agent backend.

Docs: https://docs.5sim.net/  (API key from your profile at 5sim.net)
Auth: Authorization: Bearer <token>  in env AGENTMAIL_FIVESIM_KEY

Flow:
  buy   : GET /v1/user/buy/activation/{country}/{operator}/{product}
          -> {id, phone, ...}        (country e.g. "russia","usa","any"; product e.g. "discord","google","any")
  check : GET /v1/user/check/{id}    -> {sms:[{code,text}], status}
  finish: GET /v1/user/finish/{id}   (mark done, positive review)
  cancel: GET /v1/user/cancel/{id}   (cancel if no SMS within window)
"""
from __future__ import annotations
import os
import time
import requests
from .base import SMSProvider
from ..otp import extract_code

BASE = "https://5sim.net/v1"


class FiveSimProvider(SMSProvider):
    name = "fivesim"

    def __init__(self, key: str | None = None):
        self.key = key or os.environ.get("AGENTMAIL_FIVESIM_KEY")
        if not self.key:
            raise RuntimeError("set AGENTMAIL_FIVESIM_KEY (get one at https://5sim.net)")
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {self.key}", "Accept": "application/json"})

    def status(self) -> dict:
        try:
            r = self.s.get(f"{BASE}/user/profile", timeout=15)
            ok = r.status_code == 200
            bal = r.json().get("balance") if ok else None
            return {"provider": self.name, "ready": ok, "balance": bal}
        except Exception as e:
            return {"provider": self.name, "ready": False, "detail": str(e)}

    def create_number(self, country: str = "any", service: str = "any") -> dict:
        op = "any"
        # 5sim uses "product" names; we accept a generic service, default any
        product = service if service and service != "any" else "any"
        r = self.s.get(f"{BASE}/user/buy/activation/{country}/{op}/{product}", timeout=25)
        body = r.text
        # 5sim sometimes returns 200 with a plain-text error string
        if body in ("no free phones", "no product", "bad country", "bad operator"):
            raise RuntimeError(f"5sim: {body} (try a different country/product)")
        if r.status_code != 200:
            raise RuntimeError(f"5sim buy failed: {r.status_code} {body[:200]}")
        try:
            d = r.json()
        except Exception:
            raise RuntimeError(f"5sim unexpected response: {body[:200]}")
        return {"id": str(d["id"]), "number": d.get("phone"), "country": country,
                "service": product, "provider": self.name, "_raw_status": d.get("status")}

    def get_sms(self, number_id: str, wait: float = 90.0) -> dict | None:
        deadline = time.time() + wait
        while time.time() < deadline:
            r = self.s.get(f"{BASE}/user/check/{number_id}", timeout=20)
            if r.status_code == 200:
                d = r.json()
                sms_list = d.get("sms") or []
                if sms_list:
                    last = sms_list[-1]
                    text = last.get("code") or last.get("text") or ""
                    # 5sim "code" field is often just the digits; "text" is full body
                    full = last.get("text") or last.get("code") or ""
                    return {"from": last.get("from"), "text": full,
                            "code": extract_code(full) or last.get("code"),
                            "received_at": last.get("date")}
            time.sleep(4.0)
        return None

    def release_number(self, number_id: str) -> None:
        # try finish first; if that 4xx (no SMS yet), cancel instead
        try:
            r = self.s.get(f"{BASE}/user/finish/{number_id}", timeout=15)
            if r.status_code >= 400:
                self.s.get(f"{BASE}/user/cancel/{number_id}", timeout=15)
        except Exception:
            pass
