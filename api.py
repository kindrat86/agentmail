#!/usr/bin/env python3
"""
agentmail HTTP API — stdlib only, no framework dependency.

Run:   python -m agentmail.api  [PORT=8000]
Endpoints:
  POST /inboxes           {"label":"signup","prefix":"bot"}  -> {address,id,label}
  GET  /inboxes                                            -> [{label,address,id}]
  GET  /inboxes/<label>/latest?wait=60&from=&subject=       -> {from,subject,code,link,...}
  GET  /health                                             -> {ok}
"""
from __future__ import annotations
import json
import os
import time
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from . import core

# ─── Hosted-mode config (env-driven; all optional, off by default) ──────────
# Self-host default: no auth, no rate limit, no audit log — identical behaviour
# to before. Flip these on for the hosted deployment.
_REQUIRE_AUTH = os.environ.get("AGENTMAIL_REQUIRE_AUTH", "").lower() in ("1", "true", "yes")
_API_KEYS = {k.strip() for k in os.environ.get("AGENTMAIL_API_KEYS", "").split(",") if k.strip()}
# requests per hour per identity (key, or IP in free tier)
_RATE_LIMIT = int(os.environ.get("AGENTMAIL_RATE_LIMIT", "0") or 0)
# free-tier daily cap for unauthenticated callers (by IP). 0 = no anon access when auth required.
_FREE_TIER_DAILY = int(os.environ.get("AGENTMAIL_FREE_TIER_DAILY", "100") or 100)
_AUDIT_LOG = os.environ.get("AGENTMAIL_AUDIT_LOG", "")  # path to append-only JSONL

# ─── Rate-limit + free-tier counters (in-memory, process-local) ─────────────
_rl_window: dict[str, deque] = defaultdict(deque)   # identity -> [timestamps] within 1h
_free_used: dict[str, deque] = defaultdict(deque)   # ip -> [timestamps] within 24h
_rl_lock = __import__("threading").Lock()

# provider active in this server process (resolved once)
try:
    _SMS = core.sms_status()
except Exception as _e:
    _SMS = {"provider": core.SMS_PROVIDER_NAME, "ready": False, "detail": str(_e)}
try:
    _COMPLIANCE = core.compliance_status()
except Exception as _e:
    _COMPLIANCE = {"provider": core.COMPLIANCE_PROVIDER_NAME, "ready": False, "detail": str(_e)}


def _audit(event: dict) -> None:
    """Append a screen event to the audit log (tamper-evident-ish JSONL append)."""
    if not _AUDIT_LOG:
        return
    try:
        line = json.dumps({"ts": time.time(), **event}, separators=(",", ":"))
        with open(_AUDIT_LOG, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass  # never break a request over logging


def _check_rate(identity: str) -> tuple[bool, str]:
    """Return (allowed, reason). Sliding 1h window."""
    if not _RATE_LIMIT:
        return True, ""
    now = time.time()
    with _rl_lock:
        w = _rl_window[identity]
        while w and now - w[0] > 3600:
            w.popleft()
        if len(w) >= _RATE_LIMIT:
            return False, "rate_limited:hourly"
        w.append(now)
    return True, ""


def _check_free_tier(ip: str) -> tuple[bool, str]:
    """Unauthenticated daily cap (by IP)."""
    if not _REQUIRE_AUTH:
        return True, ""
    now = time.time()
    with _rl_lock:
        w = _free_used[ip]
        while w and now - w[0] > 86400:
            w.popleft()
        if len(w) >= _FREE_TIER_DAILY:
            return False, "free_tier_exhausted"
        w.append(now)
    return True, ""


def _json(handler, status, obj):
    body = json.dumps(obj).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass  # quiet

    def _client_ip(self):
        # honour X-Forwarded-For when behind a proxy/load balancer (Fly/Railway)
        xff = self.headers.get("X-Forwarded-For", "")
        return xff.split(",")[0].strip() if xff else self.client_address[0]

    def _authorize(self) -> tuple[bool, str, str]:
        """Return (ok, identity, error). identity = api-key or 'anon:<ip>'."""
        ip = self._client_ip()
        # Authenticated path: Bearer token or X-API-Key header.
        key = self.headers.get("X-API-Key", "") or ""
        if not key:
            auth = self.headers.get("Authorization", "") or ""
            if auth.lower().startswith("bearer "):
                key = auth[7:].strip()
        if key:
            if key in _API_KEYS:
                return True, key, ""
            return False, "", "invalid_api_key"
        # Anonymous path: only allowed if auth not required, within free-tier cap.
        if _REQUIRE_AUTH:
            ok, reason = _check_free_tier(ip)
            if not ok:
                return False, "", reason
            return True, f"anon:{ip}", ""
        return True, f"anon:{ip}", ""

    def _body(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        return json.loads(self.rfile.read(n)) if n else {}

    def _gate(self, audit_action: str | None = None,
              audit_subject: dict | None = None) -> str | None:
        """Auth + rate-limit gate. Returns identity on success, or None (and
        writes the error response) on failure. /health bypasses this."""
        ok, identity, err = self._authorize()
        if not ok:
            code = 401 if err == "invalid_api_key" else 429
            _json(self, code, {"error": err})
            return None
        ok, err = _check_rate(identity)
        if not ok:
            _json(self, 429, {"error": err})
            return None
        if audit_action:
            _audit({"action": audit_action, "caller": identity,
                    "subject": audit_subject or {}})
        return identity

    def do_GET(self):
        p = urlparse(self.path)
        if p.path == "/health":
            return _json(self, 200, {"ok": True, "service": "agentmail",
                                     "sms": _SMS, "compliance": _COMPLIANCE})
        # sanctions GET has its own audit-gated path (must come BEFORE the
        # generic gate below, otherwise it would double-count rate credits).
        if p.path == "/sanctions" or p.path.startswith("/sanctions?"):
            q = parse_qs(p.query)
            subject = {"name": q.get("name", [""])[0], "wallet": q.get("wallet", [""])[0],
                       "country": q.get("country", [""])[0]}
            if self._gate("sanctions_check", subject) is None:
                return
            return _json(self, 200, core.sanctions_check(
                name=subject["name"], wallet=subject["wallet"], country=subject["country"]))
        # everything below is gated (no-op when auth disabled)
        if self._gate() is None:
            return
        if p.path == "/inboxes":
            return _json(self, 200, core.list_inboxes())
        if p.path == "/numbers":
            return _json(self, 200, core.list_inboxes())  # SMS numbers share the registry
        if p.path == "/sms/status":
            return _json(self, 200, core.sms_status())
        if p.path == "/compliance/status":
            return _json(self, 200, core.compliance_status())
        parts = p.path.strip("/").split("/")
        # email: /inboxes/<label>/latest
        if len(parts) == 3 and parts[0] == "inboxes" and parts[2] == "latest":
            label = parts[1]
            q = parse_qs(p.query)
            try:
                msg = core.fetch_latest(label, wait=float(q.get("wait", ["0"])[0]),
                                        match_from=q.get("from", [None])[0],
                                        match_subject=q.get("subject", [None])[0])
            except KeyError as e:
                return _json(self, 404, {"error": str(e)})
            return _json(self, 200, msg or {"empty": True})
        # sms: /numbers/<label>/sms?wait=90
        if len(parts) == 3 and parts[0] == "numbers" and parts[2] == "sms":
            label = parts[1]
            q = parse_qs(p.query)
            try:
                msg = core.fetch_sms(label, wait=float(q.get("wait", ["0"])[0]))
            except KeyError as e:
                return _json(self, 404, {"error": str(e)})
            return _json(self, 200, msg or {"empty": True})
        return _json(self, 404, {"error": "not found"})

    def do_POST(self):
        p = urlparse(self.path)
        # generic gate first (no-op when auth disabled); inbox/number creation
        # and compliance screens all live behind the same gate.
        b: dict = {}
        if p.path in ("/kya", "/risk", "/disputes"):
            # compliance endpoints — read body once, gate with audit
            b = self._body()
            if self._gate(p.path.lstrip("/"), b) is None:
                return
        else:
            if self._gate() is None:
                return
            b = self._body()
        if p.path == "/inboxes":
            try:
                return _json(self, 201, core.create_inbox(label=b.get("label", "default"), prefix=b.get("prefix")))
            except Exception as e:
                return _json(self, 500, {"error": str(e)})
        if p.path == "/numbers":
            try:
                return _json(self, 201, core.create_number(
                    label=b.get("label", "default"),
                    country=b.get("country", "any"),
                    service=b.get("service", "any")))
            except Exception as e:
                return _json(self, 500, {"error": str(e)})
        if p.path == "/kya":
            try:
                return _json(self, 200, core.kya_verify(
                    agent_id=b.get("agent_id", ""), evidence=b.get("evidence", {})))
            except Exception as e:
                return _json(self, 500, {"error": str(e)})
        if p.path == "/risk":
            try:
                return _json(self, 200, core.risk_score(
                    counterparty_id=b.get("counterparty_id", ""),
                    amount=b.get("amount", "0"),
                    currency=b.get("currency", "USDC"),
                    rail=b.get("rail", "x402"),
                    category=b.get("category", "digital_goods")))
            except Exception as e:
                return _json(self, 500, {"error": str(e)})
        if p.path == "/disputes":
            try:
                return _json(self, 201, core.dispute_open(
                    transaction_id=b.get("transaction_id", ""),
                    reason=b.get("reason", ""),
                    evidence=b.get("evidence")))
            except Exception as e:
                return _json(self, 500, {"error": str(e)})
        return _json(self, 404, {"error": "not found"})

    def do_DELETE(self):
        p = urlparse(self.path)
        parts = p.path.strip("/").split("/")
        if len(parts) == 2 and parts[0] == "numbers":
            try:
                return _json(self, 200, core.release_number(parts[1]))
            except KeyError as e:
                return _json(self, 404, {"error": str(e)})
        return _json(self, 404, {"error": "not found"})


def main():
    import os
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "127.0.0.1")  # set HOST=0.0.0.0 for deployment
    srv = ThreadingHTTPServer((host, port), Handler)
    mode = "hosted" if _REQUIRE_AUTH else "open"
    print(f"agentmail API on http://{host}:{port}  (mode: {mode}, health: GET /health)")
    srv.serve_forever()


if __name__ == "__main__":
    main()
