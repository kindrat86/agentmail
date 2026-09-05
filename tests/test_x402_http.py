"""Real HTTP handler controls. All payer/screen fixtures are synthetic; no network payments."""
import base64
import importlib.util
import json
import pathlib
import os
os.environ['AGENTMAIL_COMPLIANCE_PROVIDER'] = 'mock'
import sys
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('agentmail', ROOT / '__init__.py', submodule_search_locations=[str(ROOT)])
pkg = importlib.util.module_from_spec(spec)
sys.modules['agentmail'] = pkg
spec.loader.exec_module(pkg)
from agentmail import api

class BuyerPathHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), api.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, path, headers=None):
        conn = HTTPConnection(*self.server.server_address, timeout=5)
        conn.request('GET', path, headers=headers or {})
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return result

    def test_quickstart_is_public(self):
        status, headers, body = self.request('/x402-quickstart')
        self.assertEqual(status, 200)
        self.assertIn(b'Payment-Signature', body)
        self.assertIn(b'/x402/sanctions', body)

    def test_unsigned_returns_real_challenge_without_screening(self):
        with patch.object(api.x402, '_PAY_TO', '0x1111111111111111111111111111111111111111'), patch.object(api.x402, '_ENABLED', True), patch.object(api.core, 'sanctions_check') as screen:
            status, headers, body = self.request('/x402/sanctions?name=ACME')
            self.assertEqual(status, 402)
            challenge = json.loads(body)
            self.assertEqual(json.loads(base64.b64decode(headers['Payment-Required'])), challenge)
            self.assertEqual(challenge['accepts'][0]['amount'], '50000')
            self.assertEqual(challenge['accepts'][0]['network'], 'eip155:8453')
            screen.assert_not_called()

    def test_disabled_fails_closed(self):
        with patch.object(api.x402, 'is_enabled', return_value=False):
            self.assertEqual(self.request('/x402/sanctions?name=ACME')[0], 503)

    def test_invalid_signature_does_not_screen_or_call_facilitator(self):
        with patch.object(api.x402, 'is_enabled', return_value=True), patch.object(api.x402, '_post_facilitator') as facilitator, patch.object(api.core, 'sanctions_check') as screen:
            status, _, body = self.request('/x402/sanctions?name=ACME', {'Payment-Signature':'not-base64'})
            self.assertEqual(status, 402)
            self.assertEqual(json.loads(body)['error'], 'invalid_payment_signature')
            facilitator.assert_not_called()
            screen.assert_not_called()

    def test_missing_subject_rejected_before_settlement(self):
        with patch.object(api.x402, 'is_enabled', return_value=True), patch.object(api.x402, 'verify_and_settle') as settle:
            self.assertEqual(self.request('/x402/sanctions', {'Payment-Signature':'synthetic'})[0], 400)
            settle.assert_not_called()

    def test_settlement_failure_never_returns_screen(self):
        with patch.object(api.x402, 'is_enabled', return_value=True), patch.object(api.x402, '_post_facilitator', side_effect=[{'isValid':True}, {'success':False}]), patch.object(api.core, 'sanctions_check') as screen:
            self.assertEqual(self.request('/x402/sanctions?name=ACME', {'Payment-Signature':'{"synthetic":true}'})[0], 402)
            screen.assert_not_called()

    def test_synthetic_verified_settlement_returns_result_and_receipt(self):
        settlement = {'success':True, 'payer':'synthetic-payer', 'transaction':'synthetic-transaction', 'network':'eip155:8453'}
        with patch.object(api.x402, 'is_enabled', return_value=True), patch.object(api.x402, '_post_facilitator', side_effect=[{'isValid':True}, settlement]) as facilitator, patch.object(api.core, 'sanctions_check', return_value={'clean':False,'matches':[{'name':'SYNTHETIC MATCH'}]}) as screen, patch.object(api, '_audit'):
            status, headers, body = self.request('/x402/sanctions?name=ACME', {'Payment-Signature':'{"synthetic":true}'})
            self.assertEqual(status, 200)
            self.assertEqual(facilitator.call_count, 2)
            screen.assert_called_once_with(name='ACME',wallet='',country='')
            self.assertFalse(json.loads(body)['clean'])
            self.assertEqual(json.loads(base64.b64decode(headers['Payment-Response'])), settlement)

if __name__ == '__main__':
    unittest.main(verbosity=2)
