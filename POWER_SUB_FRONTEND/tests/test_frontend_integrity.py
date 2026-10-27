"""
Automated Python test suite to verify POWER-SUB frontend security,
integrity, absence of innerHTML with untrusted data, CSP adherence,
and API contract alignment.
"""

import os
import re
import json
import unittest

FRONTEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(FRONTEND_DIR)


class TestFrontendIntegrity(unittest.TestCase):

    def test_vendor_chartjs_present(self):
        """Verify Chart.js is locally vendored and VERSIONS.md documents it."""
        chart_path = os.path.join(FRONTEND_DIR, "vendor", "chart.umd.min.js")
        versions_path = os.path.join(FRONTEND_DIR, "vendor", "VERSIONS.md")

        self.assertTrue(os.path.exists(chart_path), "chart.umd.min.js must be vendored locally")
        self.assertGreater(os.path.getsize(chart_path), 50000, "chart.umd.min.js must not be empty")

        self.assertTrue(os.path.exists(versions_path), "vendor/VERSIONS.md must exist")
        with open(versions_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Chart.js", content)
        self.assertIn("4.4.2", content)

    def test_strict_csp_in_index_html(self):
        """Verify strict CSP meta tag in index.html without unsafe-inline or unsafe-eval in scripts."""
        index_path = os.path.join(FRONTEND_DIR, "index.html")
        self.assertTrue(os.path.exists(index_path))

        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()

        self.assertIn("http-equiv=\"Content-Security-Policy\"", html)
        self.assertIn("default-src 'self'", html)
        self.assertIn("script-src 'self'", html)
        self.assertNotIn("'unsafe-eval'", html)
        self.assertNotIn("script-src 'unsafe-inline'", html)
        self.assertIn("http://127.0.0.1:8000", html)

    def test_no_forbidden_certainty_wording(self):
        """Verify forbidden certainties like 'confirmed waste' or 'waste detected' are absent."""
        forbidden_terms = [
            "confirmed waste",
            "waste detected",
            "definite waste",
            "proven waste"
        ]

        js_dir = os.path.join(FRONTEND_DIR, "js")
        for root, _, files in os.walk(js_dir):
            for file in files:
                if file.endswith(".js"):
                    file_path = os.path.join(root, file)
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read().lower()
                    for term in forbidden_terms:
                        self.assertNotIn(
                            term,
                            content,
                            f"Forbidden phrase '{term}' found in {file_path}. Use 'Flagged anomaly' / 'Possible waste'."
                        )

    def test_xss_innerhtml_audit(self):
        """Audit all JS files to ensure no dynamic data interpolation via innerHTML."""
        js_dir = os.path.join(FRONTEND_DIR, "js")
        dynamic_inner_html_pattern = re.compile(r"\.innerHTML\s*=\s*[^;`]*[+`$]")

        for root, _, files in os.walk(js_dir):
            for file in files:
                if file.endswith(".js"):
                    file_path = os.path.join(root, file)
                    with open(file_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    for idx, line in enumerate(lines, 1):
                        # innerHTML = '' is allowed to clear, but dynamic interpolation is forbidden
                        if ".innerHTML" in line:
                            is_clear_only = bool(re.search(r"\.innerHTML\s*=\s*['\"]\s*['\"]", line))
                            self.assertTrue(
                                is_clear_only,
                                f"Dynamic innerHTML usage found in {file_path}:{idx}: {line.strip()}"
                            )

    def test_no_eval_or_document_write(self):
        """Verify absence of eval(), new Function(), or document.write()."""
        js_dir = os.path.join(FRONTEND_DIR, "js")
        for root, _, files in os.walk(js_dir):
            for file in files:
                if file.endswith(".js"):
                    file_path = os.path.join(root, file)
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    self.assertNotIn("document.write", content, f"document.write found in {file_path}")
                    self.assertNotIn("eval(", content, f"eval found in {file_path}")
                    self.assertNotIn("new Function(", content, f"new Function found in {file_path}")

    def test_storage_key_namespacing(self):
        """Verify localStorage uses namespaced key powersub.prefs.v1."""
        config_path = os.path.join(FRONTEND_DIR, "js", "config.js")
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("powersub.prefs.v1", content)


if __name__ == "__main__":
    unittest.main()
