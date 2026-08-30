import ast
import json
import pathlib
import re
import unittest
from urllib.parse import parse_qs

API_PATH = pathlib.Path(__file__).parents[1] / 'api.py'
SOURCE = API_PATH.read_text()


def load_function(name):
    tree = ast.parse(SOURCE)
    node = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name), None)
    if node is None:
        raise AssertionError(f'missing function: {name}')
    scope = {'json': json, 'parse_qs': parse_qs}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(API_PATH), 'exec'), scope)
    return scope[name]


class RequestBodyComplianceTests(unittest.TestCase):
    def test_form_encoded_one_click_body_is_parsed(self):
        parse_body = load_function('_parse_request_body')
        body = parse_body(
            'application/x-www-form-urlencoded; charset=UTF-8',
            b'email=user%40example.com&List-Unsubscribe=One-Click',
        )
        self.assertEqual('user@example.com', body['email'])
        self.assertEqual('One-Click', body['List-Unsubscribe'])

    def test_json_body_is_still_parsed(self):
        parse_body = load_function('_parse_request_body')
        self.assertEqual({'email': 'user@example.com'}, parse_body('application/json', b'{"email":"user@example.com"}'))

    def test_marketing_consent_is_explicit(self):
        has_consent = load_function('_has_marketing_consent')
        self.assertFalse(has_consent({}))
        self.assertFalse(has_consent({'consent': 'false'}))
        self.assertTrue(has_consent({'consent': 'marketing'}))
        self.assertTrue(has_consent({'consent': 'true'}))


class CaptureSurfaceComplianceTests(unittest.TestCase):
    def test_footer_capture_has_required_consent_and_legal_links(self):
        footer = SOURCE[SOURCE.index('_FOOTER = '):SOURCE.index('_VERTICALS =')]
        self.assertIn('type="checkbox" name="consent" value="marketing" required', footer)
        self.assertIn('href="/privacy"', footer)
        self.assertIn('href="/terms"', footer)

    def test_subscribe_handler_rejects_missing_consent(self):
        self.assertIn('_has_marketing_consent(b)', SOURCE)
        self.assertIn('explicit marketing consent required', SOURCE)

    def test_email_logs_use_recipient_references(self):
        self.assertIsNone(re.search(r'print\(f[^\n]*\{(?:email|to_email)\}', SOURCE))
        self.assertIn('_email_ref(', SOURCE)


if __name__ == '__main__':
    unittest.main(verbosity=2)
