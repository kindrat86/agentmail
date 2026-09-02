from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import sqlite3
import sys
import tempfile
import types
import unittest
from unittest import mock
from typing import Any


BILLING_PATH = pathlib.Path(__file__).parents[1] / "billing.py"


def load_billing() -> Any:
    spec = importlib.util.spec_from_file_location("billing_webhook_under_test", BILLING_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {BILLING_PATH}")
    module: Any = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BillingWebhookIsolationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.billing = load_billing()
        self.billing._DB_PATH = pathlib.Path(self.tmp.name) / "billing.db"
        self.billing._STRIPE_WEBHOOK_SECRET = ""
        self.billing.init_db()

    def checkout_event(
        self,
        *,
        session_id: str,
        mode: str,
        subscription: str | None,
        metadata: dict[str, str],
        email: str = "buyer@example.com",
        payment_status: str = "paid",
    ) -> bytes:
        return json.dumps(
            {
                "id": f"evt_{session_id}",
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": session_id,
                        "mode": mode,
                        "subscription": subscription,
                        "payment_status": payment_status,
                        "customer": "cus_test" if subscription else None,
                        "customer_details": {"email": email},
                        "customer_email": email,
                        "metadata": metadata,
                    }
                },
            }
        ).encode("utf-8")

    def add_pending(
        self,
        session_id: str,
        plan: str = "dev",
        price_id: str | None = None,
    ) -> None:
        if price_id is None:
            price_id = self.billing.AGENTMAIL_PRICE_IDS[plan]
        with self.billing._db() as conn:
            conn.execute(
                "INSERT INTO pending_sessions (session_id, plan, price_id, created_at) VALUES (?, ?, ?, ?)",
                (session_id, plan, price_id, 1.0),
            )
            conn.commit()

    def process_checkout(self, payload: bytes) -> dict:
        event = json.loads(payload)
        return self.billing._on_checkout_completed(event["data"]["object"])

    def key_count(self, session_id: str) -> int:
        with self.billing._db() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM api_keys WHERE stripe_checkout_session = ?",
                (session_id,),
            ).fetchone()
        return int(row["n"])

    def test_gitdealflow_eur1_foreign_checkout_has_zero_fulfillment_side_effects(self):
        fixture_path = pathlib.Path(__file__).parent / "fixtures" / "gitdealflow_foreign_checkout_session.json"
        payload = fixture_path.read_bytes()
        event = json.loads(payload)
        session_id = event["data"]["object"]["id"]
        db_before = self.billing._DB_PATH.read_bytes()

        def key_issuance_must_not_start() -> str:
            raise AssertionError("foreign checkout reached key issuance")

        self.billing.generate_key = key_issuance_must_not_start
        result = self.process_checkout(payload)

        self.assertFalse(result["handled"])
        self.assertEqual("foreign_checkout_ignored", result["detail"])
        self.assertNotIn("email", result, "email-bearing results trigger post-purchase email")
        self.assertEqual(0, self.key_count(session_id))
        self.assertEqual(db_before, self.billing._DB_PATH.read_bytes(), "foreign checkout wrote to DB")

    def test_subscription_without_local_pending_session_is_ignored(self):
        session_id = "cs_other_product_subscription"
        payload = self.checkout_event(
            session_id=session_id,
            mode="subscription",
            subscription="sub_other",
            metadata={"plan": "dev"},
        )

        result = self.process_checkout(payload)

        self.assertFalse(result["handled"])
        self.assertEqual("foreign_checkout_ignored", result["detail"])
        self.assertEqual(0, self.key_count(session_id))

    def test_pending_checkout_requires_subscription_mode_and_id(self):
        session_id = "cs_pending_but_one_time"
        self.add_pending(session_id, "dev")
        payload = self.checkout_event(
            session_id=session_id,
            mode="payment",
            subscription=None,
            metadata={"plan": "dev"},
        )

        result = self.process_checkout(payload)

        self.assertFalse(result["handled"])
        self.assertEqual("invalid_owned_checkout", result["detail"])
        self.assertEqual(0, self.key_count(session_id))

    def test_owned_pending_checkout_must_be_paid_before_key_issuance(self):
        session_id = "cs_owned_but_unpaid"
        self.add_pending(session_id, "dev")
        payload = self.checkout_event(
            session_id=session_id,
            mode="subscription",
            subscription="sub_owned_but_unpaid",
            metadata={"plan": "dev"},
            email="unpaid@example.test",
            payment_status="unpaid",
        )

        result = self.process_checkout(payload)

        self.assertFalse(result["handled"])
        self.assertEqual("owned_checkout_not_paid", result["detail"])
        self.assertNotIn("email", result, "unpaid results must not trigger post-purchase email")
        self.assertEqual(0, self.key_count(session_id))

    def test_pending_plan_must_match_session_metadata(self):
        session_id = "cs_plan_mismatch"
        self.add_pending(session_id, "dev")
        payload = self.checkout_event(
            session_id=session_id,
            mode="subscription",
            subscription="sub_mismatch",
            metadata={"plan": "team"},
        )

        result = self.process_checkout(payload)

        self.assertFalse(result["handled"])
        self.assertEqual("owned_checkout_plan_mismatch", result["detail"])
        self.assertEqual(0, self.key_count(session_id))

    def test_pending_checkout_requires_an_owned_price_before_plan(self):
        session_id = "cs_pending_foreign_price"
        self.add_pending(session_id, "dev", "price_foreign_gitdealflow")
        payload = self.checkout_event(
            session_id=session_id,
            mode="subscription",
            subscription="sub_foreign_price",
            metadata={"plan": "dev"},
        )

        result = self.process_checkout(payload)

        self.assertFalse(result["handled"])
        self.assertEqual("foreign_checkout_ignored", result["detail"])
        self.assertEqual(0, self.key_count(session_id))

    def test_owned_subscription_issues_one_key_and_replay_is_idempotent(self):
        session_id = "cs_owned_dev"
        self.add_pending(session_id, "dev")
        payload = self.checkout_event(
            session_id=session_id,
            mode="subscription",
            subscription="sub_owned",
            metadata={"plan": "dev"},
        )

        first = self.process_checkout(payload)
        second = self.process_checkout(payload)

        self.assertTrue(first["handled"])
        self.assertEqual("dev", first["plan"])
        self.assertFalse(second["handled"])
        self.assertEqual("checkout_already_processed", second["detail"])
        self.assertEqual(1, self.key_count(session_id))

    def test_owned_team_price_issues_team_key(self):
        session_id = "cs_owned_team"
        self.add_pending(session_id, "team")
        payload = self.checkout_event(
            session_id=session_id,
            mode="subscription",
            subscription="sub_owned_team",
            metadata={"plan": "team"},
        )

        result = self.process_checkout(payload)

        self.assertTrue(result["handled"])
        self.assertEqual("team", result["plan"])
        self.assertEqual(1, self.key_count(session_id))

    def test_server_created_pending_session_survives_price_rotation(self):
        old_price = "price_agentmail_dev_rotating_old"
        new_price = "price_agentmail_dev_rotating_new"
        session_id = "cs_created_before_price_rotation"
        created = types.SimpleNamespace(id=session_id, url="https://checkout.stripe.test/session")
        fake_stripe = types.SimpleNamespace(
            api_key=None,
            checkout=types.SimpleNamespace(
                Session=types.SimpleNamespace(create=lambda **_kwargs: created)
            ),
        )
        self.billing._STRIPE_SECRET = "sk_test_agentmail"

        with mock.patch.dict(os.environ, {"STRIPE_PRICE_DEV": old_price}), \
                mock.patch.dict(sys.modules, {"stripe": fake_stripe}):
            self.billing.create_checkout_session("dev")

        payload = self.checkout_event(
            session_id=session_id,
            mode="subscription",
            subscription="sub_created_before_price_rotation",
            metadata={"plan": "dev"},
        )
        with mock.patch.dict(os.environ, {"STRIPE_PRICE_DEV": new_price}):
            result = self.process_checkout(payload)

        self.assertTrue(result["handled"])
        self.assertEqual("dev", result["plan"])
        self.assertEqual(1, self.key_count(session_id))

    def test_init_db_migrates_existing_pending_sessions_fail_closed(self):
        legacy_db = pathlib.Path(self.tmp.name) / "legacy-billing.db"
        self.billing._DB_PATH = legacy_db
        with sqlite3.connect(legacy_db) as conn:
            conn.execute(
                """CREATE TABLE pending_sessions (
                       session_id TEXT PRIMARY KEY,
                       plan TEXT NOT NULL,
                       created_at REAL NOT NULL
                   )"""
            )
            conn.execute(
                "INSERT INTO pending_sessions (session_id, plan, created_at) VALUES (?, ?, ?)",
                ("cs_preownership", "dev", 1.0),
            )
            conn.commit()

        self.billing.init_db()

        with self.billing._db() as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(pending_sessions)")}
            row = conn.execute(
                "SELECT price_id, owned_at_creation FROM pending_sessions WHERE session_id = ?",
                ("cs_preownership",),
            ).fetchone()
        self.assertIn("price_id", columns)
        self.assertIn("owned_at_creation", columns)
        self.assertEqual("", row["price_id"])
        self.assertEqual(0, row["owned_at_creation"])

    def test_foreign_subscription_deletion_is_ignored_without_email_result(self):
        db_before = self.billing._DB_PATH.read_bytes()

        result = self.billing._on_subscription_deleted({"id": "sub_foreign_product"})

        self.assertFalse(result["handled"])
        self.assertEqual("foreign_subscription_ignored", result["detail"])
        self.assertNotIn("emails", result)
        self.assertEqual(db_before, self.billing._DB_PATH.read_bytes())


if __name__ == "__main__":
    unittest.main()
