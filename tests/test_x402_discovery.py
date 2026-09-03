from __future__ import annotations

import base64
import importlib.util
import json
import os
import pathlib
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).parents[1]
X402_PATH = ROOT / "x402.py"
API_SOURCE = (ROOT / "api.py").read_text()


def load_x402(**env):
    spec = importlib.util.spec_from_file_location("agentmail_x402_test", X402_PATH)
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(os.environ, env, clear=True):
        spec.loader.exec_module(module)
    return module


class X402V2ContractTests(unittest.TestCase):
    def setUp(self):
        self.x402 = load_x402(
            AGENTMAIL_X402_ENABLED="true",
            AGENTMAIL_PAY_TO_WALLET="0x1111111111111111111111111111111111111111",
            AGENTMAIL_X402_PRICE_USDC="5",
            AGENTMAIL_PUBLIC_URL="https://sanctionsai.dev",
        )

    def test_payment_required_uses_v2_atomic_usdc_contract(self):
        required = self.x402.build_payment_required(
            "https://sanctionsai.dev/x402/sanctions",
            "OFAC sanctions screen",
        )
        self.assertEqual(2, required["x402Version"])
        self.assertEqual("https://sanctionsai.dev/x402/sanctions", required["resource"]["url"])
        self.assertEqual("Sanctions AI", required["resource"]["serviceName"])
        accepted = required["accepts"][0]
        self.assertEqual("50000", accepted["amount"])
        self.assertEqual("eip155:8453", accepted["network"])
        self.assertEqual("exact", accepted["scheme"])
        self.assertEqual("USD Coin", accepted["extra"]["name"])
        self.assertEqual("2", accepted["extra"]["version"])
        self.assertGreater(accepted["maxTimeoutSeconds"], 0)
        bazaar = required["extensions"]["bazaar"]
        self.assertEqual("GET", bazaar["info"]["input"]["method"])
        self.assertIn("wallet", bazaar["info"]["input"]["queryParams"])
        self.assertIn("input", bazaar["schema"]["required"])
        schema_properties = bazaar["schema"]["properties"]
        query_schema = schema_properties["input"]["properties"]["queryParams"]
        self.assertIn("wallet", query_schema["properties"])
        output_example = schema_properties["output"]["properties"]["example"]
        self.assertIsInstance(output_example, dict)
        self.assertIn("clean", output_example)
        self.assertIn("matches", output_example)

    def test_payment_required_header_round_trips(self):
        required = self.x402.build_payment_required(
            "https://sanctionsai.dev/x402/sanctions",
            "OFAC sanctions screen",
        )
        header = self.x402.encode_payment_header(required)
        decoded = json.loads(base64.b64decode(header).decode("utf-8"))
        self.assertEqual(required, decoded)

    def test_verify_and_settle_calls_both_facilitator_endpoints(self):
        required = self.x402.build_payment_required(
            "https://sanctionsai.dev/x402/sanctions",
            "OFAC sanctions screen",
        )
        responses = [
            {"isValid": True, "payer": "0x2222222222222222222222222222222222222222"},
            {
                "success": True,
                "payer": "0x2222222222222222222222222222222222222222",
                "transaction": "0xabc",
                "network": "eip155:8453",
                "amount": "50000",
            },
        ]
        requested_urls = []

        class Response:
            def __init__(self, payload):
                self.payload = payload

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def read(self):
                return json.dumps(self.payload).encode("utf-8")

        def fake_urlopen(request, timeout=10):
            requested_urls.append(request.full_url)
            return Response(responses.pop(0))

        with mock.patch.object(self.x402.urllib.request, "urlopen", side_effect=fake_urlopen):
            ok, settlement = self.x402.verify_and_settle("eyJ4NDAyVmVyc2lvbiI6Mn0=", required)

        self.assertTrue(ok)
        self.assertEqual("0xabc", settlement["transaction"])
        self.assertEqual(
            ["https://facilitator.payai.network/verify", "https://facilitator.payai.network/settle"],
            requested_urls,
        )

    def test_settlement_failure_fails_closed(self):
        required = self.x402.build_payment_required(
            "https://sanctionsai.dev/x402/sanctions",
            "OFAC sanctions screen",
        )
        responses = [
            {"isValid": True},
            {"success": False, "errorReason": "settlement_failed", "transaction": "", "network": "eip155:8453"},
        ]

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def read(self):
                return json.dumps(responses.pop(0)).encode("utf-8")

        with mock.patch.object(self.x402.urllib.request, "urlopen", return_value=Response()):
            ok, settlement = self.x402.verify_and_settle("eyJ4NDAyVmVyc2lvbiI6Mn0=", required)

        self.assertFalse(ok)
        self.assertEqual("settlement_failed", settlement["error"])


class X402ApiDiscoveryWiringTests(unittest.TestCase):
    def test_dedicated_route_and_well_known_manifest_are_wired(self):
        self.assertIn('if p.path == "/.well-known/x402":', API_SOURCE)
        self.assertIn('if p.path == "/x402/sanctions":', API_SOURCE)
        self.assertIn('"/x402/sanctions": {', API_SOURCE)
        self.assertIn('"x-payment-info"', API_SOURCE)
        self.assertIn('"Payment-Required"', API_SOURCE)
        self.assertIn('"Payment-Response"', API_SOURCE)

    def test_openapi_operations_declare_auth_modes_truthfully(self):
        risk_spec = API_SOURCE.split('"/risk": {', 1)[1].split('"/kya": {', 1)[0]
        kya_spec = API_SOURCE.split('"/kya": {', 1)[1].split('"/health": {', 1)[0]
        health_spec = API_SOURCE.split('"/health": {', 1)[1].split('"/dashboard/logs": {', 1)[0]
        dashboard_spec = API_SOURCE.split('"/dashboard/logs": {', 1)[1].split('"components": {', 1)[0]
        self.assertIn('"security": [{"ApiKeyAuth": []}]', risk_spec)
        self.assertIn('"security": [{"ApiKeyAuth": []}]', kya_spec)
        self.assertIn('"security": []', health_spec)
        self.assertIn('"security": [{"AdminDashboardAuth": []}]', dashboard_spec)
        self.assertIn('"AdminDashboardAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"}', API_SOURCE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
