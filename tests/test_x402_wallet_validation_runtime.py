"""Loopback-only paid-route coverage. All facilitator and screening replies are synthetic."""
from __future__ import annotations

import base64
import http.client
import importlib
import json
import os
import pathlib
import socket
import sys
import tempfile
import threading
import unittest
from urllib.parse import urlencode
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE_PARENT = ROOT.parent
ORIGINAL_CONNECT = socket.socket.connect
ORIGINAL_GETADDRINFO = socket.getaddrinfo
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def loopback_only_connect(sock, address):
    host = address[0] if isinstance(address, tuple) else address
    if host not in LOOPBACK_HOSTS:
        raise AssertionError(f"external network is forbidden: {host}")
    return ORIGINAL_CONNECT(sock, address)


def loopback_only_getaddrinfo(host, *args, **kwargs):
    if host not in LOOPBACK_HOSTS:
        raise AssertionError(f"external DNS is forbidden: {host}")
    return ORIGINAL_GETADDRINFO(host, *args, **kwargs)


class X402WalletValidationRuntimeTests(unittest.TestCase):
    valid_evm = "0x1111111111111111111111111111111111111111"
    valid_btc_legacy = "1BoatSLRHtKNngkdXEeobR76b53LETtpyT"
    valid_tron = "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb"
    valid_bech32 = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
    valid_bech32m = "bc1pqqqsyqcyq5rqwzqfpg9scrgwpugpzysnzs23v9ccrydpk8qarc0sg5tmnz"

    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.network_patch = mock.patch.object(socket.socket, "connect", loopback_only_connect)
        cls.dns_patch = mock.patch("socket.getaddrinfo", loopback_only_getaddrinfo)
        cls.network_patch.start()
        cls.dns_patch.start()
        cls.env_patch = mock.patch.dict(os.environ, {
            "AGENTMAIL_X402_ENABLED": "true",
            "AGENTMAIL_PAY_TO_WALLET": cls.valid_evm,
            "AGENTMAIL_X402_PRICE_USDC": "5",
            "AGENTMAIL_PUBLIC_URL": "http://127.0.0.1",
            "AGENTMAIL_AUDIT_LOG": str(pathlib.Path(cls.tempdir.name) / "audit.jsonl"),
            "AGENTMAIL_HOME": cls.tempdir.name,
            "AGENTMAIL_REQUIRE_AUTH": "true",
            "AGENTMAIL_API_KEYS": "",
            "AGENTMAIL_RATE_LIMIT": "0",
            "AGENTMAIL_FREE_TIER_DAILY": "0",
            "POSTHOG_API_KEY": "",
        }, clear=True)
        cls.env_patch.start()
        sys.path.insert(0, str(SOURCE_PARENT))
        for name in tuple(sys.modules):
            if name == ROOT.name or name.startswith(ROOT.name + "."):
                sys.modules.pop(name, None)
        cls.api = importlib.import_module(ROOT.name + ".api")
        cls.server = cls.api.ThreadingHTTPServer(("127.0.0.1", 0), cls.api.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        sys.path.remove(str(SOURCE_PARENT))
        cls.env_patch.stop()
        cls.dns_patch.stop()
        cls.network_patch.stop()
        cls.tempdir.cleanup()

    @classmethod
    def request(cls, query, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", cls.server.server_port, timeout=2)
        conn.request("GET", "/x402/sanctions?" + urlencode(query), headers=headers or {})
        response = conn.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        status = response.status
        response_headers = dict(response.getheaders())
        conn.close()
        return status, payload, response_headers

    @staticmethod
    def signed_header():
        return base64.b64encode(b'{"x402Version":2,"payload":{"synthetic":true}}').decode("ascii")

    @staticmethod
    def response(payload):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def read(self): return json.dumps(payload).encode("utf-8")
        return Response()

    def assert_rejected_before_facilitator(self, wallet):
        calls, responses = [], [{"isValid": True}, {"success": True, "transaction": "synthetic"}]
        def unexpected_facilitator(request, timeout=15):
            calls.append(request.full_url)
            return self.response(responses.pop(0))
        with mock.patch.object(self.api.x402.urllib.request, "urlopen", side_effect=unexpected_facilitator), \
             mock.patch.object(self.api.core, "sanctions_check", return_value={"clean": True, "matches": []}) as screen:
            status, body, _ = self.request({"wallet": wallet}, {"Payment-Signature": self.signed_header()})
        self.assertEqual(400, status, body)
        self.assertEqual("invalid_wallet", body["error"])
        self.assertEqual([], calls)
        screen.assert_not_called()

    def test_no_header_keeps_discovery_402_before_validation(self):
        status, body, headers = self.request({"wallet": "not-a-wallet"})
        self.assertEqual(402, status)
        self.assertEqual(2, body["x402Version"])
        self.assertIn("Payment-Required", headers)

    def test_missing_and_malformed_wallets_are_rejected_before_facilitator(self):
        for wallet in ("", "not-a-wallet", "So11111111111111111111111111111111111111112"):
            with self.subTest(wallet=wallet):
                self.assert_rejected_before_facilitator(wallet)

    def test_checksum_and_bech32_rule_failures_are_rejected_before_facilitator(self):
        invalid_wallets = (
            "1BoatSLRHtKNngkdXEeobR76b53LETtpyU",  # synthetic bad Base58Check checksum
            self.valid_tron[:-1] + "c",  # synthetic bad Tron Base58Check checksum
            self.valid_bech32[:-1] + "q",  # synthetic bad BIP173 checksum
            self.valid_bech32m[:-1] + "q",  # synthetic bad BIP350 checksum
            "BC1Qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",  # mixed case
            "bc1notbitcoin1pqqqsyqcyq5rqwzqfpg9scrgwpugpzysnzs23v9ccrydpk8qarc0symkztz",  # valid Bech32m checksum, foreign HRP
            "bc1pw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",  # v1 with Bech32 checksum
            "bc1qqqqsyqcyq5rqwzqfpg9scrgwpugpzysnzs23v9ccrydpk8qarc0jqgfzyvjz2f389q8mypc8",  # valid checksum, 41-byte v0 program
        )
        for wallet in invalid_wallets:
            with self.subTest(wallet=wallet):
                self.assert_rejected_before_facilitator(wallet)

    def test_valid_documented_wallets_verify_settle_then_screen_with_other_subject_fields(self):
        for wallet in (self.valid_evm, self.valid_btc_legacy, self.valid_tron, self.valid_bech32, self.valid_bech32m):
            with self.subTest(wallet=wallet):
                calls, responses = [], [
                    {"isValid": True},
                    {"success": True, "payer": "synthetic", "transaction": "synthetic", "network": "eip155:8453"},
                ]
                def facilitator(request, timeout=15):
                    calls.append(request.full_url)
                    return self.response(responses.pop(0))
                with mock.patch.object(self.api.x402.urllib.request, "urlopen", side_effect=facilitator), \
                     mock.patch.object(self.api.core, "sanctions_check", return_value={"clean": True, "matches": []}) as screen:
                    status, body, _ = self.request(
                        {"wallet": wallet, "name": "Synthetic Test Name", "country": "US"},
                        {"Payment-Signature": self.signed_header()},
                    )
                self.assertEqual(200, status, body)
                self.assertEqual(["https://facilitator.payai.network/verify", "https://facilitator.payai.network/settle"], calls)
                screen.assert_called_once_with(name="Synthetic Test Name", wallet=wallet, country="US")

    def test_facilitator_failure_stays_402_after_valid_wallet_validation(self):
        calls = []
        def unavailable(request, timeout=15):
            calls.append(request.full_url)
            raise OSError("synthetic facilitator offline")
        with mock.patch.object(self.api.x402.urllib.request, "urlopen", side_effect=unavailable):
            status, body, _ = self.request({"wallet": self.valid_evm}, {"Payment-Signature": self.signed_header()})
        self.assertEqual(402, status)
        self.assertEqual("facilitator_unavailable", body["error"])
        self.assertEqual(["https://facilitator.payai.network/verify"], calls)


if __name__ == "__main__":
    unittest.main(verbosity=2)
