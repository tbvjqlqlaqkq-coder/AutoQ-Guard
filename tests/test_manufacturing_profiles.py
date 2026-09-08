import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from manufacturing_profiles import PROFILES, profile_catalog


class ManufacturingProfileTests(unittest.TestCase):
    def test_three_profiles_are_available_without_changing_core_keys(self):
        self.assertEqual(set(PROFILES), {"automotive", "medical_device", "general_manufacturing"})
        for profile_id, profile in PROFILES.items():
            self.assertEqual(profile["id"], profile_id)
            self.assertTrue(profile["trace_label"])
            self.assertEqual(len(profile["process_examples"]), 4)

    def test_standalone_is_the_safe_default(self):
        with patch.dict(os.environ, {}, clear=True):
            result = profile_catalog()
        self.assertEqual(result["default_profile"], "automotive")
        self.assertFalse(result["n8n_integration"])
        self.assertEqual(result["integration_mode"], "STANDALONE")

    def test_n8n_and_profile_can_be_enabled_independently(self):
        with patch.dict(os.environ, {"AUTOQ_DEFAULT_PROFILE": "medical_device", "AUTOQ_N8N_INTEGRATION": "true"}, clear=True):
            result = profile_catalog()
        self.assertEqual(result["default_profile"], "medical_device")
        self.assertTrue(result["n8n_integration"])

    def test_unknown_profile_falls_back_to_automotive(self):
        self.assertEqual(profile_catalog("unknown", False)["default_profile"], "automotive")

    def test_dashboard_contains_profile_selector_and_safe_mode_badge(self):
        html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="profileSelect"', html)
        self.assertIn('id="integrationMode"', html)
        self.assertIn("/api/profiles", html)
        self.assertIn("N8N ON", html)
        self.assertIn('id="n8nStart"', html)
        self.assertIn('id="n8nStop"', html)
        self.assertIn("/api/integration/control", html)


if __name__ == "__main__":
    unittest.main()
