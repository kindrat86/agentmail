"""Billing module — API-key-as-product with Stripe Checkout.

Architecture: dev pays via Stripe Checkout → webhook auto-issues an API key
with a tier (dev/team) → key stored in SQLite → existing _authorize() checks
tier + monthly usage limit on each call.

Tiers (env-configurable price IDs):
  Free  — $0,   50 checks/day by IP (no key, enforced in api.py)
  Dev   — $19/mo, 10,000 checks/mo, API key, full tools, audit log
  Team  — $99/mo, 100,000 checks/mo, API key, priority

Backward-compat: AGENTMAIL_API_KEYS env (admin keys) bypass tier limits.

Database: SQLite at $AGENTMAIL_HOME/billing.db (same volume as OFAC cache).
"""
from __future__ import annotations
import os
import secrets
import sqlite3
import time
import threading
from pathlib import Path

_HOME = Path(os.environ.get("AGENTMAIL_HOME", str(Path.home() / ".agentmail")))
_DB_PATH = _HOME / "billing.db"
_HOME.mkdir(parents=True, exist_ok=True)
_lock = threading.Lock()

# ─── Tier configuration ──────────────────────────────────────────────────
# Price IDs are set via env (you create products in Stripe dashboard, paste IDs).
TIERS = {
    "dev": {
        "price_id_env": "STRIPE_PRICE_DEV",
        "monthly_limit": int(os.environ.get("AGENTMAIL_DEV_MONTHLY_LIMIT", "10000")),
        "rate_limit": int(os.environ.get("AGENTMAIL_DEV_RATE_LIMIT", "1000")),  # per hour
        "label": "Dev",
        "price": "$19/mo",
    },
    "team": {
        "price_id_env": "STRIPE_PRICE_TEAM",
        "monthly_limit": int(os.environ.get("AGENTMAIL_TEAM_MONTHLY_LIMIT", "100000")),
        "rate_limit": int(os.environ.get("AGENTMAIL_TEAM_RATE_LIMIT", "5000")),
        "label": "Team",
        "price": "$99/mo",
    },
    # NOTE: "pro" tier ($499/mo) is disabled — STRIPE_PRICE_PRO was never set.
    # To re-enable: create the product in Stripe, set STRIPE_PRICE_PRO via
    # `flyctl secrets set STRIPE_PRICE_PRO=price_... --app agentmail-api`,
    # then uncomment the block below.
    # "pro": {
    #     "price_id_env": "STRIPE_PRICE_PRO",
    #     "monthly_limit": 0,
    #     "rate_limit": 0,
    #     "label": "Pro",
    #     "price": "$499/mo",
    # },
}

_STRIPE_SECRET = os.environ.get("STRIPE_SECRET_KEY", "")
_STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
_PUBLIC_URL = os.environ.get("AGENTMAIL_PUBLIC_URL", "https://agentmail-api.fly.dev")

_MONTH_SECONDS = 30 * 86400


# ─── Database ────────────────────────────────────────────────────────────
def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if not exist. Call once at startup."""
    with _db() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                key TEXT PRIMARY KEY,
                tier TEXT NOT NULL,
                email TEXT,
                stripe_customer_id TEXT,
                stripe_subscription_id TEXT,
                stripe_checkout_session TEXT,
                created_at REAL NOT NULL,
                active INTEGER DEFAULT 1,
                usage_count INTEGER DEFAULT 0,
                usage_window_start REAL NOT NULL,
                last_used_at REAL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS pending_sessions (
                session_id TEXT PRIMARY KEY,
                plan TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                email TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        c.commit()


# ─── Key generation + lookup ────────────────────────────────────────────
def generate_key() -> str:
    return "sk_live_" + secrets.token_hex(24)


def lookup_key(key: str) -> dict | None:
    """Return key record with tier info, or None if invalid/inactive."""
    if not key:
        return None
    with _db() as c:
        row = c.execute(
            "SELECT * FROM api_keys WHERE key = ? AND active = 1", (key,)
        ).fetchone()
    if not row:
        return None
    return dict(row)


def record_usage(key: str) -> dict:
    """Increment usage counter, reset monthly window if expired.
    Returns updated record {tier, usage_count, monthly_limit, remaining, blocked}."""
    now = time.time()
    with _lock, _db() as c:
        row = c.execute(
            "SELECT * FROM api_keys WHERE key = ? AND active = 1", (key,)
        ).fetchone()
        if not row:
            return {"blocked": True, "reason": "invalid_key"}
        record = dict(row)
        # Reset monthly window if expired
        if now - record["usage_window_start"] > _MONTH_SECONDS:
            c.execute(
                "UPDATE api_keys SET usage_count = 0, usage_window_start = ? WHERE key = ?",
                (now, key),
            )
            record["usage_count"] = 0
            record["usage_window_start"] = now
        tier_cfg = TIERS.get(record["tier"], {})
        limit = tier_cfg.get("monthly_limit", 10000)
        # Unlimited tiers set limit to 0 and bypass rate limiting.
        if limit == 0:
            c.execute(
                "UPDATE api_keys SET usage_count = usage_count + 1, last_used_at = ? WHERE key = ?",
                (now, key),
            )
            c.commit()
            return {
                "blocked": False,
                "tier": record["tier"],
                "usage": record["usage_count"] + 1,
                "limit": 0,
                "remaining": 0,
            }
        if record["usage_count"] >= limit:
            return {"blocked": True, "reason": "monthly_limit_exceeded",
                    "tier": record["tier"], "usage": record["usage_count"], "limit": limit}
        c.execute(
            "UPDATE api_keys SET usage_count = usage_count + 1, last_used_at = ? WHERE key = ?",
            (now, key),
        )
        c.commit()
        return {
            "blocked": False,
            "tier": record["tier"],
            "usage": record["usage_count"] + 1,
            "limit": limit,
            "remaining": limit - record["usage_count"] - 1,
        }


def deactivate_key(key: str, reason: str = "subscription_cancelled"):
    """Mark a key inactive (e.g. when subscription is cancelled)."""
    with _db() as c:
        c.execute(
            "UPDATE api_keys SET active = 0 WHERE key = ?", (key,)
        )
        c.commit()


# ─── Order bump configuration ───────────────────────────────────────────
# Brunson Ch 14: an order bump is a default-checked add-on offered AT the
# checkout — not on the pricing page. The bump must be cheap enough to be
# an impulse yes (under 50% of the main price), relevant to the purchase,
# and add real value. Here: extended audit log retention + webhook alerts,
# priced at $9/mo on top of the $19 Dev plan.
BUMP_TIERS = {
    "audit_plus": {
        "price_id_env": "STRIPE_PRICE_BUMP_AUDIT",
        "label": "Extended Audit Log",
        "price": "$9/mo",
        "desc": "180-day audit log retention (vs 30-day) + real-time webhook alerts on any BLOCK",
    },
}


# ─── Stripe Checkout ────────────────────────────────────────────────────
def create_checkout_session(plan: str, bump: str | None = None) -> dict:
    """Create a Stripe Checkout Session for a plan. Returns {url, session_id}.

    If bump is set (e.g. "audit_plus"), adds an order-bump line item — a
    Brunson-style default-checked add-on at checkout. The bump's price_id
    must be set via the BUMP_TIERS env var. If the env is missing, the bump
    is silently skipped (graceful degradation — checkout still works).
    """
    if not _STRIPE_SECRET:
        raise RuntimeError("STRIPE_SECRET_KEY not set — billing disabled")
    if plan not in TIERS:
        raise ValueError(f"unknown plan: {plan}")
    import stripe
    stripe.api_key = _STRIPE_SECRET

    price_id = os.environ.get(TIERS[plan]["price_id_env"], "")
    if not price_id:
        raise RuntimeError(f"{TIERS[plan]['price_id_env']} env not set")

    line_items = [{"price": price_id, "quantity": 1}]

    # Order bump: append as a second line item if configured
    bump_added = False
    if bump and bump in BUMP_TIERS:
        bump_price_id = os.environ.get(BUMP_TIERS[bump]["price_id_env"], "")
        if bump_price_id:
            line_items.append({"price": bump_price_id, "quantity": 1})
            bump_added = True

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=line_items,
        success_url=f"{_PUBLIC_URL}/keys/{{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{_PUBLIC_URL}/pricing?cancelled=1",
        metadata={"plan": plan, "bump": bump if bump_added else ""},
    )
    # Record pending session so webhook can associate it
    now = time.time()
    with _lock, _db() as c:
        c.execute(
            "INSERT OR REPLACE INTO pending_sessions (session_id, plan, created_at) VALUES (?, ?, ?)",
            (session.id, plan, now),
        )
        c.commit()
    return {"url": session.url, "session_id": session.id}


def handle_webhook(payload: bytes, signature: str) -> dict:
    """Process a Stripe webhook. Returns {handled: bool, event_type, detail}."""
    if not _STRIPE_WEBHOOK_SECRET:
        return {"handled": False, "error": "STRIPE_WEBHOOK_SECRET not set"}
    import stripe
    stripe.api_key = _STRIPE_SECRET

    try:
        event = stripe.Webhook.construct_event(
            payload, signature, _STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        return {"handled": False, "error": "invalid_signature"}
    except Exception as e:
        return {"handled": False, "error": str(e)}

    etype = event["type"]

    if etype == "checkout.session.completed":
        return _on_checkout_completed(event["data"]["object"])
    elif etype == "customer.subscription.deleted":
        return _on_subscription_deleted(event["data"]["object"])
    elif etype == "customer.subscription.updated":
        return _on_subscription_updated(event["data"]["object"])
    else:
        return {"handled": False, "event_type": etype, "detail": "ignored"}


def _on_checkout_completed(session_obj: dict) -> dict:
    """Issue an API key when a checkout completes."""
    session_id = session_obj["id"]
    plan = session_obj.get("metadata", {}).get("plan", "dev")
    customer_id = session_obj.get("customer", "")
    email = session_obj.get("customer_email", "") or session_obj.get("customer_details", {}).get("email", "")

    # Look up subscription from pending session
    with _db() as c:
        pending = c.execute(
            "SELECT plan FROM pending_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
    if pending:
        plan = pending["plan"]

    key = generate_key()
    now = time.time()
    with _lock, _db() as c:
        c.execute(
            """INSERT INTO api_keys
               (key, tier, email, stripe_customer_id, stripe_subscription_id,
                stripe_checkout_session, created_at, active, usage_count, usage_window_start)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0, ?)""",
            (key, plan, email, customer_id,
             session_obj.get("subscription", ""), session_id, now, now),
        )
        c.execute("DELETE FROM pending_sessions WHERE session_id = ?", (session_id,))
        c.commit()
    return {"handled": True, "event_type": "checkout.session.completed",
            "key_prefix": key[:12] + "...", "plan": plan, "email": email}


def _on_subscription_deleted(sub_obj: dict) -> dict:
    """Deactivate the key when a subscription is cancelled."""
    sub_id = sub_obj.get("id", "")
    with _lock, _db() as c:
        rows = c.execute(
            "SELECT key, email FROM api_keys WHERE stripe_subscription_id = ?", (sub_id,)
        ).fetchall()
        for row in rows:
            c.execute("UPDATE api_keys SET active = 0 WHERE key = ?", (row["key"],))
        c.commit()
    return {"handled": True, "event_type": "subscription.deleted",
            "deactivated": len(rows), "emails": [r["email"] for r in rows if r["email"]]}


def _on_subscription_updated(sub_obj: dict) -> dict:
    """Handle plan upgrades/downgrades (change tier)."""
    sub_id = sub_obj.get("id", "")
    status = sub_obj.get("status", "")
    if status in ("canceled", "unpaid", "incomplete_expired"):
        return _on_subscription_deleted(sub_obj)
    return {"handled": False, "event_type": "subscription.updated",
            "detail": f"status={status} (no action)"}


def add_lead(email: str, source: str, created_at: float) -> dict:
    """Upsert a lead by email. Returns ok=False if email is missing."""
    email = (email or "").strip()
    if not email or "@" not in email:
        return {"ok": False}
    with _db() as c:
        c.execute(
            "INSERT OR IGNORE INTO leads(email, source, created_at) VALUES(?,?,?)",
            (email.lower(), source or "teardown", created_at),
        )
        c.commit()
    return {"ok": True}


def get_key_by_session(session_id: str) -> dict | None:
    """Return the key issued for a checkout session (for success page)."""
    with _db() as c:
        row = c.execute(
            "SELECT key, tier, email, created_at FROM api_keys WHERE stripe_checkout_session = ?",
            (session_id,),
        ).fetchone()
    return dict(row) if row else None


def billing_status() -> dict:
    """Health check for the billing subsystem."""
    try:
        with _db() as c:
            total = c.execute("SELECT COUNT(*) as n FROM api_keys WHERE active=1").fetchone()["n"]
            by_tier = {}
            for t in TIERS:
                r = c.execute(
                    "SELECT COUNT(*) as n FROM api_keys WHERE tier=? AND active=1", (t,)
                ).fetchone()
                by_tier[t] = r["n"]
            total_usage = c.execute(
                "SELECT SUM(usage_count) as n FROM api_keys WHERE active=1"
            ).fetchone()["n"] or 0
    except Exception:
        return {"ready": False, "db": str(_DB_PATH)}
    return {
        "ready": True,
        "stripe_configured": bool(_STRIPE_SECRET),
        "webhook_configured": bool(_STRIPE_WEBHOOK_SECRET),
        "tiers": {t: {"price": cfg["price"], "monthly_limit": cfg["monthly_limit"]}
                  for t, cfg in TIERS.items()},
        "active_keys": total,
        "keys_by_tier": by_tier,
        "total_usage_this_window": total_usage,
    }
