#!/usr/bin/env python3
"""JSON-LD lint for static HTML and inline Python HTML templates.

Every <script type="application/ld+json"> block must be valid JSON whose top
level is an object, or an array of objects, with @context and @type/@graph.
Zero dependencies so the check can run inside the production Docker build.

Usage:
  python3 scripts/validate_jsonld.py [root [root ...]]

Exits 1 (and prints every failure) if any block is invalid. Exits 0 on a
clean scan, including the case where zero candidate files are found.
"""
import ast
import json
import os
import re
import sys

SKIP_DIRS = {
    ".git", "node_modules", ".venv", ".testvenv", ".buildvenv",
    ".vercel", ".next", "dist", "build", "__pycache__", ".turbo",
}
PYTHON_SKIP_DIRS = SKIP_DIRS | {"tests"}

BLOCK_RE = re.compile(
    r'<script[^>]*\btype\s*=\s*["\']?application/ld\+json["\']?[^>]*>'
    r'(.*?)</script>',
    re.S | re.I,
)


def iter_files(root, suffix, skip_dirs=SKIP_DIRS):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for filename in filenames:
            if filename.endswith(suffix):
                yield os.path.join(dirpath, filename)


def iter_html_files(root):
    yield from iter_files(root, ".html")


def iter_python_files(root):
    yield from iter_files(root, ".py", PYTHON_SKIP_DIRS)


def _json_kind(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    return type(value).__name__


def check_html(source, html):
    errors = []
    for index, raw in enumerate(BLOCK_RE.findall(html)):
        block = raw.strip()
        if not block:
            continue
        try:
            parsed = json.loads(block)
        except json.JSONDecodeError as error:
            errors.append(f"{source} [block {index}]: invalid JSON - {error}")
            continue

        nodes = parsed if isinstance(parsed, list) else [parsed]
        for node in nodes:
            if not isinstance(node, dict):
                errors.append(
                    f"{source} [block {index}]: invalid top-level element "
                    f"{_json_kind(node)}; expected object or array of objects"
                )
                continue
            if "@context" not in node:
                errors.append(f"{source} [block {index}]: missing @context")
            if "@type" not in node and "@graph" not in node:
                errors.append(
                    f"{source} [block {index}]: missing @type (and no @graph)"
                )
    return errors


def check_file(path):
    try:
        with open(path, encoding="utf-8", errors="strict") as file_handle:
            html = file_handle.read()
    except UnicodeDecodeError as error:
        return [f"{path}: not valid UTF-8 ({error})"]
    return check_html(path, html)


def python_html_strings(path):
    """Yield static Python string literals that contain JSON-LD script tags."""
    try:
        with open(path, encoding="utf-8", errors="strict") as file_handle:
            source = file_handle.read()
    except UnicodeDecodeError:
        return

    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError:
        # Syntax validity is owned by the compiler/test gate. Avoid duplicating it.
        return

    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        if BLOCK_RE.search(node.value):
            yield node.lineno, node.value


def main():
    roots = sys.argv[1:] or ["."]
    all_errors = []
    html_files_scanned = 0
    python_files_scanned = 0
    blocks_seen = 0

    for root in roots:
        for path in iter_html_files(root):
            html_files_scanned += 1
            with open(path, encoding="utf-8", errors="ignore") as file_handle:
                html = file_handle.read()
            blocks_seen += len(BLOCK_RE.findall(html))
            all_errors.extend(check_html(path, html))

        for path in iter_python_files(root):
            python_files_scanned += 1
            for line, html in python_html_strings(path):
                blocks_seen += len(BLOCK_RE.findall(html))
                all_errors.extend(check_html(f"{path}:{line}", html))

    print(
        f"[validate_jsonld] scanned {html_files_scanned} HTML file(s), "
        f"{python_files_scanned} Python source file(s), {blocks_seen} "
        f"JSON-LD block(s) in {', '.join(roots)}"
    )

    if all_errors:
        print(f"[validate_jsonld] {len(all_errors)} error(s):")
        for error in all_errors:
            print(f"  - {error}")
        sys.exit(1)

    print("[validate_jsonld] OK")


if __name__ == "__main__":
    main()
