"""Regression tests for Google-invalid top-level JSON-LD values."""

import importlib.util
import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_jsonld.py"
SPEC = importlib.util.spec_from_file_location("validate_jsonld", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class JsonLdValidatorTests(unittest.TestCase):
    def _write_string_schema(self, directory: pathlib.Path) -> pathlib.Path:
        page = directory / "index.html"
        page.write_text(
            '<script type="application/ld+json">'
            '"{\\"@context\\":\\"https://schema.org\\",'
            '\\"@type\\":\\"WebSite\\"}"'
            "</script>",
            encoding="utf-8",
        )
        return page

    def test_python_validator_rejects_top_level_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = self._write_string_schema(pathlib.Path(tmp))
            errors = VALIDATOR.check_file(str(page))

        self.assertTrue(
            any("invalid top-level element string" in error for error in errors),
            errors,
        )

    def test_python_validator_rejects_inline_python_html_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = pathlib.Path(tmp) / "page.py"
            source.write_text(
                "HTML = r'''<script type=\"application/ld+json\">"
                "\"{\\\"@context\\\":\\\"https://schema.org\\\","
                "\\\"@type\\\":\\\"WebSite\\\"}\""
                "</script>'''\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(VALIDATOR_PATH), tmp],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(
            "invalid top-level element string", result.stdout + result.stderr
        )

    def test_node_validator_rejects_top_level_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_string_schema(pathlib.Path(tmp))
            result = subprocess.run(
                ["node", str(ROOT / "scripts" / "verify-jsonld.mjs"), tmp],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(
            "invalid top-level element string", result.stdout + result.stderr
        )


if __name__ == "__main__":
    unittest.main()
