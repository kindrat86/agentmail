from __future__ import annotations

import ast
import pathlib
import unittest


class X402UpgradePayloadTest(unittest.TestCase):
    def test_payment_required_payload_offers_card_upgrade(self) -> None:
        source_path = pathlib.Path(__file__).parents[1] / "api.py"
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        function = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_x402_or_key_gate"
        )
        function_source = ast.get_source_segment(source, function) or ""
        payment_required_start = function_source.index('"error": "payment_required"')
        payment_required_end = function_source.index("self.send_header", payment_required_start)
        payload_source = function_source[payment_required_start:payment_required_end]

        self.assertIn('"upgrade_url"', payload_source)
        self.assertIn('_PUBLIC_URL + "/pricing"', payload_source)
        self.assertIn('"upgrade_note"', payload_source)


if __name__ == "__main__":
    unittest.main()
