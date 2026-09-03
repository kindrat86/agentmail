"""Unit tests for the sanctionsai MCP server (no network access).

Run:  python3 -m unittest tests.test_sanctionsai_mcp -v
"""
from __future__ import annotations

import base64
import io
import json
import sys
import unittest

sys.path.insert(0, ".")  # repo root

from sanctionsai_mcp import client  # noqa: E402
from sanctionsai_mcp import server  # noqa: E402


class _RecordingTransport:
    """Wrap a transport fn and record every (method, url, headers) call."""

    def __init__(self, fn):
        self.fn = fn
        self.calls = []

    def __call__(self, method, url, headers):
        self.calls.append((method, url, dict(headers)))
        return self.fn(method, url, headers)


def make_402_transport(url_contains="/x402/sanctions", amount="50000"):
    """Fake transport mimicking production: 402 + base64 Payment-Required."""
    payment_required = {
        "x402Version": 2,
        "error": "Payment required",
        "resource": {"url": "https://sanctionsai.dev/x402/sanctions",
                     "description": "OFAC wallet sanctions screen"},
        "accepts": [{
            "scheme": "exact",
            "network": "eip155:8453",
            "amount": amount,
            "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "payTo": "0xPayToWallet",
            "maxTimeoutSeconds": 60,
        }],
    }
    header = base64.b64encode(json.dumps(payment_required).encode()).decode()

    def fn(method, url, headers):
        assert url_contains in url, f"unexpected url {url}"
        return 402, {"payment-required": header}, b'{"error": "Payment required"}'

    return _RecordingTransport(fn)


def make_200_transport(body=None):
    body = body or {"clean": True, "matches": [],
                    "x402": {"paid": True, "amount": "0.05", "currency": "USDC"}}

    def transport(method, url, headers):
        assert "Payment-Signature" in headers or True
        return 200, {"content-type": "application/json"}, json.dumps(body).encode()

    return transport


def rpc(method, msg_id=1, **params):
    msg = {"jsonrpc": "2.0", "id": msg_id, "method": method}
    if params:
        msg["params"] = params
    return msg


def run_stdio(messages):
    """Feed messages through serve(); return list of parsed responses."""
    out = io.StringIO()
    server.serve(stdin=io.StringIO("\n".join(json.dumps(m) for m in messages) + "\n"),
                 stdout=out, transport=make_402_transport())
    return [json.loads(line) for line in out.getvalue().splitlines() if line.strip()]


def tool_call_text(responses, tool, arguments):
    r = next(x for x in responses
             if x.get("id") == 99 and "result" in x)
    return json.loads(r["result"]["content"][0]["text"])


class TestHandshakeAndListing(unittest.TestCase):
    def test_initialize(self):
        responses = run_stdio([rpc("initialize", 1)])
        result = responses[0]["result"]
        self.assertEqual(result["protocolVersion"], "2024-11-05")
        self.assertEqual(result["serverInfo"]["name"], "sanctionsai-mcp")
        self.assertIn("tools", result["capabilities"])

    def test_tools_list_has_three_tools_with_schemas(self):
        responses = run_stdio([rpc("tools/list", 2)])
        tools = {t["name"]: t for t in responses[0]["result"]["tools"]}
        self.assertEqual(set(tools), {"screen_name", "screen_company", "x402_info"})
        self.assertEqual(tools["screen_name"]["inputSchema"]["required"], ["name"])
        self.assertEqual(tools["screen_company"]["inputSchema"]["required"], ["name"])

    def test_unknown_method_returns_32601(self):
        responses = run_stdio([rpc("resources/list", 3)])
        self.assertEqual(responses[0]["error"]["code"], -32601)

    def test_notification_gets_no_response(self):
        responses = run_stdio([
            rpc("initialize", 1),
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            rpc("ping", 2),
        ])
        self.assertEqual([r["id"] for r in responses], [1, 2])

    def test_ping(self):
        responses = run_stdio([rpc("ping", 7)])
        self.assertEqual(responses[0]["result"], {})


class TestPaidTools(unittest.TestCase):
    def test_screen_name_unpaid_returns_402_challenge(self):
        responses = run_stdio([rpc("tools/call", 99, name="screen_name",
                                   arguments={"name": "Sergey Mironov"})])
        payload = tool_call_text(responses, "screen_name", {})
        self.assertTrue(payload["requires_payment"])
        accepts = payload["payment_required"]["accepts"]
        self.assertEqual(accepts[0]["amount"], "50000")  # $0.05 = 5 * 10^4 atomic USDC
        self.assertEqual(accepts[0]["network"], "eip155:8453")
        self.assertIn("x402-quickstart", payload["how_to_pay"])

    def test_screen_company_hits_same_paid_endpoint(self):
        t = make_402_transport()
        server.call_tool("screen_company", {"name": "Novatek"}, transport=t)
        self.assertEqual(len(t.calls), 1)
        method, url, headers = t.calls[0]
        self.assertEqual(method, "GET")
        self.assertIn("/x402/sanctions?name=Novatek", url)

    def test_paid_200_passthrough(self):
        result = server.call_tool("screen_name", {"name": "Jane Doe"},
                                  transport=make_200_transport())
        self.assertFalse(result["isError"])
        payload = json.loads(result["content"][0]["text"])
        self.assertTrue(payload["paid"])
        self.assertTrue(payload["result"]["clean"])

    def test_empty_name_is_client_side_error_no_network(self):
        def boom(*a, **k):  # transport must never be touched
            raise AssertionError("transport called for empty name")
        result = server.call_tool("screen_name", {"name": "  "}, transport=boom)
        self.assertTrue(result["isError"])
        self.assertIn("required", json.loads(result["content"][0]["text"])["error"])

    def test_unknown_tool_is_error(self):
        result = server.call_tool("nope", {}, transport=make_402_transport())
        self.assertTrue(result["isError"])


class TestFreeTool(unittest.TestCase):
    def test_x402_info_needs_no_network(self):
        def boom(*a, **k):
            raise AssertionError("x402_info must not touch the network")
        result = server.call_tool("x402_info", {}, transport=boom)
        payload = json.loads(result["content"][0]["text"])
        self.assertEqual(payload["price"], client.PRICE_DESCRIPTION)
        self.assertEqual(payload["quickstart"], "https://sanctionsai.dev/x402-quickstart")

    def test_country_param_forwarded(self):
        t = make_402_transport()
        server.call_tool("screen_name", {"name": "Ivan Ivanov", "country": "RU"},
                         transport=t)
        url = t.calls[0][1]
        self.assertIn("name=Ivan%20Ivanov", url)
        self.assertIn("country=RU", url)


class TestClient(unittest.TestCase):
    def test_decode_payment_required_roundtrip(self):
        pr = {"accepts": [{"amount": "50000"}]}
        enc = base64.b64encode(json.dumps(pr).encode()).decode()
        self.assertEqual(client.decode_payment_required(enc)["accepts"][0]["amount"],
                         "50000")

    def test_screen_requires_a_subject(self):
        out = client.screen("person", transport=make_402_transport())
        self.assertFalse(out["ok"])
        self.assertIn("required", out["error"])

    def test_transport_failure_is_soft_error(self):
        def broken(method, url, headers):
            raise OSError("dns gone")
        out = client.screen("person", name="x", transport=broken)
        self.assertFalse(out["ok"])
        self.assertIn("transport failure", out["error"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
