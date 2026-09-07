from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class UiImportFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
        cls.server = (ROOT / "src" / "enterprise_dashboard.py").read_text(encoding="utf-8")

    def test_ui_calls_all_staging_endpoints(self):
        for endpoint in ("/api/mapping-preview", "/api/staging-preview", "/api/staging-approve", "/api/staging-run", "/api/staging-compare", "/api/staging-promote"):
            self.assertIn(endpoint, self.html)

    def test_approval_is_disabled_until_preview_passes(self):
        self.assertIn('id="mappingApprove" class="secondary" disabled', self.html)
        self.assertIn("checked.status!=='READY_FOR_APPROVAL'", self.html)
        self.assertIn("currentUser?.permissions?.includes('IMPORT_APPROVE')", self.html)

    def test_public_page_does_not_gain_server_import_api(self):
        public = (ROOT / "docs" / "demo" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("/api/staging-approve", public)

    def test_server_audits_import_actions(self):
        self.assertIn('"/api/staging-approve"', self.server)
        self.assertIn('security.audit(user["username"]', self.server)

    def test_promotion_requires_explicit_confirmation(self):
        self.assertIn("value==='PROMOTE'", self.html)
        self.assertIn('id="stagingPromote" disabled', self.html)


if __name__ == "__main__":
    unittest.main()
