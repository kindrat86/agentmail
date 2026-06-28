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
from . import billing
from . import x402

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
_PUBLIC_URL = os.environ.get("AGENTMAIL_PUBLIC_URL", "https://agentmail-api.fly.dev")

# ─── Rate-limit + free-tier counters (in-memory, process-local) ─────────────
_rl_window: dict[str, deque] = defaultdict(deque)   # identity -> [timestamps] within 1h
_free_used: dict[str, deque] = defaultdict(deque)   # ip -> [timestamps] within 24h
_rl_lock = __import__("threading").Lock()

_SERVER_CARD = {
    "version": "1.0",
    "name": "agentmail",
    "description": "Compliance & verification toolkit for AI agents — OFAC sanctions screen, KYA, transaction risk, plus disposable email/SMS verification inboxes.",
    "schema_version": "1.0",
    "tools": [
        {
            "name": "sanctions_check",
            "description": "Screen a counterparty against OFAC/EU/UN/UK sanctions lists. Cheapest check, call first. At least one of name / wallet / country required. Returns matches with list, match_type, and confidence, plus a clean boolean.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name to screen"},
                    "wallet": {"type": "string", "description": "Crypto wallet address"},
                    "country": {"type": "string", "description": "ISO-2 country code"}
                }
            }
        },
        {
            "name": "risk_score",
            "description": "Score a transaction's fraud risk BEFORE authorizing payment. Recommendation is one of allow/review/decline. rail in: x402, ap2, acp, tap. category in: digital_goods, services, physical.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "counterparty_id": {"type": "string"},
                    "amount": {"type": "string"},
                    "currency": {"type": "string", "default": "USDC"},
                    "rail": {"type": "string", "default": "x402"},
                    "category": {"type": "string", "default": "digital_goods"}
                },
                "required": ["counterparty_id", "amount"]
            }
        },
        {
            "name": "kya_verify",
            "description": "Verify an AI agent's identity before transacting with it (Know Your Agent). evidence keys: wallet_address, wallet_age_days, domain, pubkey, owner_email, declared_country.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string"},
                    "evidence": {"type": "object"}
                },
                "required": ["agent_id"]
            }
        },
        {
            "name": "dispute_open",
            "description": "Open a dispute when an agent-paid transaction went bad (non-delivery, fraud). Records with a 7-day auto-escalation window.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "transaction_id": {"type": "string"},
                    "reason": {"type": "string"},
                    "evidence": {"type": "object"}
                },
                "required": ["transaction_id", "reason"]
            }
        },
    ],
}

# provider active in this server process (resolved once)
try:
    _SMS = core.sms_status()
except Exception as _e:
    _SMS = {"provider": core.SMS_PROVIDER_NAME, "ready": False, "detail": str(_e)}
try:
    _COMPLIANCE = core.compliance_status()
except Exception as _e:
    _COMPLIANCE = {"provider": core.COMPLIANCE_PROVIDER_NAME, "ready": False, "detail": str(_e)}

# Initialize billing database (SQLite) — safe no-op if already exists
try:
    billing.init_db()
except Exception:
    pass


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
        """Return (ok, identity, error). identity = api-key or 'anon:<ip>'.
        Keys from AGENTMAIL_API_KEYS (admin) bypass tier limits.
        Keys from billing DB are checked for tier + monthly usage."""
        ip = self._client_ip()
        # Authenticated path: Bearer token or X-API-Key header.
        key = self.headers.get("X-API-Key", "") or ""
        if not key:
            auth = self.headers.get("Authorization", "") or ""
            if auth.lower().startswith("bearer "):
                key = auth[7:].strip()
        if key:
            # Admin keys (env) — unlimited
            if key in _API_KEYS:
                return True, key, ""
            # Billing DB keys — check tier + usage
            usage = billing.record_usage(key)
            if usage.get("blocked"):
                reason = usage.get("reason", "invalid_key")
                if reason == "invalid_key":
                    return False, "", "invalid_api_key"
                return False, "", reason  # monthly_limit_exceeded
            return True, key, ""
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

    def _x402_or_key_gate(self, audit_action: str, audit_subject: dict | None = None,
                         x402_description: str = "") -> str | None:
        """Gate for paid endpoints: accept API key, x402 payment, or free tier.
        Returns identity on success, or None (writes error/402 response) on failure.

        Order of precedence:
          1. Valid API key (admin or billing) → proceed
          2. x402 payment header (if x402 enabled) → verify, proceed
          3. Free tier (if no auth required) → proceed
          4. Otherwise → 402 Payment Required (if x402) or 401"""
        # First, try normal auth (key-based)
        ok, identity, err = self._authorize()
        if ok:
            ok2, err2 = _check_rate(identity)
            if not ok2:
                _json(self, 429, {"error": err2})
                return None
            if audit_action:
                _audit({"action": audit_action, "caller": identity, "subject": audit_subject or {}})
            return identity
        # Auth failed. If x402 is enabled, offer per-call payment instead.
        if x402.is_enabled() and err in ("invalid_api_key", "free_tier_exhausted", ""):
            payment_header = self.headers.get("X-PAYMENT", "")
            req = x402.build_payment_requirements(self.command, self.path, x402_description)
            if payment_header:
                valid, reason = x402.verify_payment(payment_header, req)
                if valid:
                    if audit_action:
                        _audit({"action": audit_action, "caller": "x402:" + x402._PAY_TO[:10],
                                "subject": audit_subject or {}, "paid": True})
                    return "x402:" + x402._PAY_TO[:10]
                _json(self, 402, {"error": "payment_invalid", "reason": reason,
                                  "payment_requirements": req})
                return None
            # No payment + no key → 402 with requirements
            self.send_response(402)
            body = json.dumps({"error": "payment_required",
                               "payment_requirements": req}).encode()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return None
        # x402 disabled, auth failed — return the original error
        code = 401 if err == "invalid_api_key" else 429
        hint = (f" — upgrade at {_PUBLIC_URL}/pricing"
                if err in ("free_tier_exhausted", "monthly_limit_exceeded") else "")
        _json(self, code, {"error": err, "upgrade_url": _PUBLIC_URL + "/pricing"} if hint else {"error": err})
        return None

    def _gate(self, audit_action: str | None = None,
              audit_subject: dict | None = None) -> str | None:
        """Auth + rate-limit gate. Returns identity on success, or None (and
        writes the error response) on failure. /health bypasses this."""
        ok, identity, err = self._authorize()
        if not ok:
            code = 401 if err == "invalid_api_key" else 429
            # Point exhausted users at the upgrade page.
            hint = (f" — upgrade at {_PUBLIC_URL}/pricing"
                    if err in ("free_tier_exhausted", "monthly_limit_exceeded")
                    else "")
            _json(self, code, {"error": err, "upgrade_url": _PUBLIC_URL + "/pricing"} if hint else {"error": err})
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
                                     "sms": _SMS, "compliance": _COMPLIANCE,
                                     "x402": x402.status()})
        # Root — landing for devs who hit the base URL. Points to everything.
        if p.path == "/" or p.path == "":
            return _json(self, 200, {
                "service": "agentmail",
                "tagline": "OFAC sanctions screening for AI agents",
                "endpoints": {
                    "screen": "/sanctions?name=&wallet=&country=",
                    "risk": "POST /risk",
                    "kya": "POST /kya",
                    "health": "/health",
                },
                "self_host": "pip install sanctions-mcp",
                "hosted_pricing": f"{_PUBLIC_URL}/pricing",
                "github": "https://github.com/kindrat86/agentmail",
                "free_tier": "50 checks/day by IP, no key needed",
            })
        # MCP server card — lets MCP registries (Smithery) skip auto-scan
        if p.path == "/.well-known/mcp/server-card.json":
            return _json(self, 200, _SERVER_CARD)
        # Pricing page (public)
        if p.path == "/pricing":
            return self._pricing_page()
        # Billing status (public, for monitoring)
        if p.path == "/billing/status":
            return _json(self, 200, billing.billing_status())
        # Stripe webhook (no auth, verified by signature)
        if p.path == "/webhooks/stripe":
            return self._stripe_webhook()
        # Success page — shows the API key after checkout
        if p.path.startswith("/keys/"):
            session_id = p.path.split("/keys/", 1)[1]
            return self._key_success_page(session_id)
        # Checkout redirects from pricing page (/checkout/dev, /checkout/team)
        if p.path.startswith("/checkout/"):
            plan = p.path.split("/checkout/", 1)[1].split("?")[0]
            try:
                result = billing.create_checkout_session(plan)
                self.send_response(302)
                self.send_header("Location", result["url"])
                self.end_headers()
            except Exception as e:
                _json(self, 500, {"error": str(e)})
            return
        # sanctions GET — paid endpoint (accepts API key OR x402 payment)
        if p.path == "/sanctions" or p.path.startswith("/sanctions?"):
            q = parse_qs(p.query)
            subject = {"name": q.get("name", [""])[0], "wallet": q.get("wallet", [""])[0],
                       "country": q.get("country", [""])[0]}
            if self._x402_or_key_gate("sanctions_check", subject, "OFAC sanctions screen") is None:
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
        # Checkout start — public, no auth gate (billing is self-serve)
        if p.path == "/checkout/start":
            b = self._body()
            plan = b.get("plan", "dev")
            try:
                result = billing.create_checkout_session(plan)
                _json(self, 200, result)
            except Exception as e:
                _json(self, 500, {"error": str(e)})
            return
        # Stripe webhook — public, verified by signature
        if p.path == "/webhooks/stripe":
            return self._stripe_webhook()
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

    # ─── Billing pages ──────────────────────────────────────────────────
    def _send_html(self, status: int, html: str):
        body = html.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _pricing_page(self):
        """Minimal pricing page — the only web surface an agentmail dev sees."""
        st = billing.billing_status()
        html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>agentmail — Pricing</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 720px;
         margin: 60px auto; padding: 0 20px; color: #1a1a1a; line-height: 1.6; }}
  h1 {{ font-size: 1.8em; }}
  .tiers {{ display: flex; gap: 20px; margin: 32px 0; flex-wrap: wrap; }}
  .tier {{ border: 1px solid #e0e0e0; border-radius: 12px; padding: 24px; flex: 1; min-width: 200px; }}
  .tier h3 {{ margin: 0 0 8px; font-size: 1.1em; }}
  .price {{ font-size: 2em; font-weight: 700; margin: 8px 0; }}
  .price small {{ font-size: 0.5em; font-weight: 400; color: #666; }}
  ul {{ padding-left: 18px; color: #444; }}
  li {{ margin: 4px 0; }}
  a.btn {{ display: inline-block; margin-top: 12px; padding: 10px 20px;
          background: #635bff; color: #fff !important; text-decoration: none;
          border-radius: 8px; font-weight: 600; }}
  code {{ background: #f5f5f5; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }}
  .free {{ background: #f9fafb; }}
</style></head><body>
<h1>agentmail — Pricing</h1>
<p>OFAC sanctions screening for AI agents. Free to start, paid tiers for production volume.</p>
<div class="tiers">
  <div class="tier free">
    <h3>Free</h3>
    <div class="price">$0<small>/mo</small></div>
    <ul>
      <li>50 checks/day (by IP)</li>
      <li>No signup required</li>
      <li>sanctions_check only</li>
    </ul>
  </div>
  <div class="tier">
    <h3>Dev</h3>
    <div class="price">$19<small>/mo</small></div>
    <ul>
      <li>10,000 checks/month</li>
      <li>API key + all tools</li>
      <li>risk_score + kya_verify</li>
      <li>Audit log access</li>
    </ul>
    <a class="btn" href="/checkout/dev">Get Dev key →</a>
  </div>
  <div class="tier">
    <h3>Team</h3>
    <div class="price">$99<small>/mo</small></div>
    <ul>
      <li>100,000 checks/month</li>
      <li>API key + all tools</li>
      <li>Priority support</li>
      <li>Custom risk rules</li>
    </ul>
    <a class="btn" href="/checkout/team">Get Team key →</a>
  </div>
</div>
<p style="color:#666;font-size:0.9em;margin-top:32px">
  Self-host is free forever: <code>pip install sanctions-mcp</code> ·
  <a href="https://github.com/kindrat86/agentmail">GitHub</a> ·
  <a href="https://agentmail-api.fly.dev/health">API status</a>
</p>
</body></html>"""
        self._send_html(200, html)

    def _key_success_page(self, session_id: str):
        """Shows the API key after successful Stripe checkout."""
        record = billing.get_key_by_session(session_id)
        if not record:
            html = """<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="font-family:system-ui;max-width:600px;margin:80px auto;padding:20px;text-align:center">
<h2>⏳ Processing your payment...</h2>
<p>If you just completed checkout, your API key is being generated. 
Refresh this page in a few seconds.</p>
<p style="color:#888">If this persists, contact via <a href="https://github.com/kindrat86/agentmail/issues">GitHub Issues</a>.</p>
</body></html>"""
            return self._send_html(200, html)
        key = record["key"]
        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="font-family:system-ui;max-width:600px;margin:60px auto;padding:20px">
<h1>✅ Your API key is ready</h1>
<p>Tier: <strong>{record["tier"].title()}</strong></p>
<div style="background:#f5f5f5;padding:16px;border-radius:8px;font-family:monospace;
font-size:1.1em;word-break:break-all;margin:16px 0;border:2px solid #635bff">
{key}
</div>
<p>Copy this key. Use it as the <code>X-API-Key</code> header:</p>
<pre style="background:#1a1a1a;color:#0f0;padding:16px;border-radius:8px;overflow-x:auto">
curl -H "X-API-Key: {key}" \\
  "https://agentmail-api.fly.dev/sanctions?wallet=0x098B716B8Aaf21512996dC57EB0615e2383E2f96"</pre>
<p style="color:#888;font-size:0.9em">
  ⚠️ Save this key now — it won't be shown again.<br>
  Manage billing at <a href="https://billing.stripe.com">Stripe Customer Portal</a>
</p>
</body></html>"""
        self._send_html(200, html)

    def _stripe_webhook(self):
        """Receive and process Stripe webhook events."""
        n = int(self.headers.get("Content-Length", 0) or 0)
        payload = self.rfile.read(n) if n else b""
        sig = self.headers.get("Stripe-Signature", "")
        try:
            result = billing.handle_webhook(payload, sig)
            status = 200 if result.get("handled") else 400
            _json(self, status, result)
        except Exception as e:
            _json(self, 500, {"error": str(e)})


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
