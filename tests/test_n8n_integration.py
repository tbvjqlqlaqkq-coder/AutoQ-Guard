import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from n8n_integration import assess_quality_event, integration_status, save_last_event, validate_token


class N8nIntegrationTests(unittest.TestCase):
    def test_medical_device_event_is_assessed(self):
        result = assess_quality_event({
            "profile": "medical_device", "lot_id": "pu-tube-01", "process_id": "leak-test",
            "process_z": 3.4, "recheck_rate": 0.12, "claim_count": 1,
            "affected_count": 40, "unit_loss_krw": 85000,
        })
        self.assertEqual(result["risk_level"], "HIGH")
        self.assertEqual(result["lot_id"], "PU-TUBE-01")
        self.assertEqual(result["estimated_loss_krw"], 3400000)
        self.assertFalse(result["decision_allowed"])
        self.assertIn("완제품 배치", result["recommended_action"])

    def test_invalid_event_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "lot_id"):
            assess_quality_event({"profile": "automotive", "process_id": "P1"})
        with self.assertRaisesRegex(ValueError, "프로필"):
            assess_quality_event({"profile": "unknown", "lot_id": "L1", "process_id": "P1"})

    def test_token_requires_configured_secret(self):
        with patch.dict(os.environ, {"AUTOQ_INTEGRATION_TOKEN": "short"}, clear=True):
            self.assertFalse(validate_token("short"))
        with patch.dict(os.environ, {"AUTOQ_INTEGRATION_TOKEN": "1234567890abcdef"}, clear=True):
            self.assertTrue(validate_token("1234567890abcdef"))

    def test_last_event_is_saved_and_reported(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {
            "AUTOQ_N8N_INTEGRATION": "true", "AUTOQ_INTEGRATION_TOKEN": "1234567890abcdef"
        }, clear=True):
            target = Path(folder) / "last.json"
            event = {"status": "ANALYZED_PREVIEW", "lot_id": "LOT-1"}
            save_last_event(event, target)
            status = integration_status(target)
            self.assertTrue(status["enabled"])
            self.assertTrue(status["configured"])
            self.assertEqual(status["last_event"]["lot_id"], "LOT-1")

    def test_runtime_override_supports_start_and_stop_without_changing_environment(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {
            "AUTOQ_N8N_INTEGRATION": "false", "AUTOQ_INTEGRATION_TOKEN": "1234567890abcdef"
        }, clear=True):
            target = Path(folder) / "last.json"
            self.assertTrue(integration_status(target, True)["enabled"])
            self.assertFalse(integration_status(target, False)["enabled"])


if __name__ == "__main__":
    unittest.main()
