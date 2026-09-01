from __future__ import annotations

import importlib.util
import json
import pathlib
import tempfile
import unittest
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
                        "customer": "cus_test" if subscription else None,
                        "customer_details": {"email": email},
                        "customer_email": email,
                        "metadata": metadata,
                    }
                },
            }
        ).encode("utf-8")

    def add_pending(self, session_id: str, plan: str = "dev") -> None:
        with self.billing._db() as conn:
            conn.execute(
                "INSERT INTO pending_sessions (session_id, plan, created_at) VALUES (?, ?, ?)",
                (session_id, plan, 1.0),
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

    def test_foreign_one_time_checkout_is_ignored(self):
        session_id = "cs_gitdealflow_offer1"
        payload = self.checkout_event(
            session_id=session_id,
            mode="payment",
            subscription=None,
            metadata={"source": "gf_offer1", "tier": "founder_teardown"},
            email="claudius@example.com",
        )

        result = self.process_checkout(payload)

        self.assertFalse(result["handled"])
        self.assertEqual("foreign_checkout_ignored", result["detail"])
        self.assertEqual(0, self.key_count(session_id))

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


if __name__ == "__main__":
    unittest.main()
