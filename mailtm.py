"""Mail.tm backend client — real disposable inboxes via mail.tm free API."""
from __future__ import annotations
import secrets
import string
import time
import requests

BASE = "https://api.mail.tm"
UA = "agentmail-mvp/0.1"


def _rand(n: int = 10) -> str:
    return "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(n))


class MailTmClient:
    def __init__(self, session: requests.Session | None = None):
        self.s = session or requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept": "application/json"})
        self.token: str | None = None
        self.account_id: str | None = None
        self.address: str | None = None

    def _domains(self) -> list[str]:
        r = self.s.get(f"{BASE}/domains?page=1", timeout=15)
        r.raise_for_status()
        data = r.json()
        # API may return a hydra:Collection dict OR a plain list depending on path/version
        members = data.get("hydra:member", []) if isinstance(data, dict) else data
        return [d["domain"] for d in members if isinstance(d, dict) and d.get("isActive")]

    def create_inbox(self, prefix: str | None = None, domain: str | None = None) -> dict:
        domains = self._domains()
        if not domains:
            raise RuntimeError("no active mail.tm domain")
        domain = domain or domains[0]
        local = (prefix or "agent") + "-" + _rand(8)
        address = f"{local}@{domain}"
        self.password = secrets.token_urlsafe(16)

        r = self.s.post(f"{BASE}/accounts", json={"address": address, "password": self.password}, timeout=20)
        if r.status_code not in (200, 201):
            raise RuntimeError(f"create account failed: {r.status_code} {r.text[:200]}")
        acct = r.json()
        self.account_id = acct["id"]
        self.address = address

        t = self.s.post(f"{BASE}/token", json={"address": address, "password": self.password}, timeout=20)
        t.raise_for_status()
        self.token = t.json()["token"]
        self.s.headers["Authorization"] = f"Bearer {self.token}"
        return {"address": address, "id": acct["id"], "created_at": acct.get("createdAt")}

    def list_messages(self, page: int = 1) -> list[dict]:
        if not self.token:
            raise RuntimeError("no inbox; call create_inbox first")
        r = self.s.get(f"{BASE}/messages?page={page}", timeout=20)
        r.raise_for_status()
        data = r.json()
        return data.get("hydra:member", []) if isinstance(data, dict) else data

    def get_message(self, msg_id: str) -> dict:
        r = self.s.get(f"{BASE}/messages/{msg_id}", timeout=20)
        r.raise_for_status()
        return r.json()

    def wait_for_message(self, timeout: float = 90.0, poll: float = 3.0,
                         match_from: str | None = None, match_subject: str | None = None) -> dict | None:
        """Poll until a message arrives. Optional filters on from/subject (substring)."""
        deadline = time.time() + timeout
        seen: set[str] = set()
        while time.time() < deadline:
            for m in self.list_messages():
                if m["id"] in seen:
                    continue
                seen.add(m["id"])
                if match_from and match_from.lower() not in m.get("from", {}).get("address", "").lower():
                    continue
                if match_subject and match_subject.lower() not in (m.get("subject") or "").lower():
                    continue
                full = self.get_message(m["id"])
                return {
                    "id": m["id"],
                    "from": m.get("from", {}).get("address"),
                    "subject": m.get("subject"),
                    "intro": m.get("intro"),
                    "text": full.get("text") or "",
                    "html": bool(full.get("html")),
                    "seen_at": m.get("createdAt"),
                }
            time.sleep(poll)
        return None
