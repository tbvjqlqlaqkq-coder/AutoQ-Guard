import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from enterprise_security import SecurityStore


class EnterpriseSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.store = SecurityStore(base / "security.db", base / "bootstrap.txt")

    def tearDown(self):
        self.temp.cleanup()

    def test_bootstrap_admin_can_login_and_has_admin_permission(self):
        text = self.store.bootstrap_file.read_text(encoding="utf-8-sig")
        password = next(line.split(": ", 1)[1] for line in text.splitlines() if line.startswith("임시 비밀번호:"))
        result = self.store.login("admin", password)
        self.assertIsNotNone(result)
        session = self.store.session(result["token"])
        self.assertIn("MANAGE_USERS", session["permissions"])

    def test_role_permissions_and_account_status(self):
        self.store.create_user("quality1", "품질 담당", "Quality!234", "QUALITY", "admin")
        login = self.store.login("quality1", "Quality!234")
        self.assertNotIn("MANAGE_USERS", self.store.session(login["token"])["permissions"])
        self.store.set_active("quality1", False, "admin")
        self.assertIsNone(self.store.session(login["token"]))

    def test_failed_login_is_audited(self):
        self.assertIsNone(self.store.login("missing", "wrong-password"))
        self.assertEqual(self.store.audit_rows()[0]["outcome"], "DENIED")


if __name__ == "__main__":
    unittest.main()
