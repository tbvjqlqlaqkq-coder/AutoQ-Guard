import csv
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from public_data_adapter import adapt_public_data
from enterprise_pipeline import run_pipeline


class PublicDataAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.public = self.base / "public"
        shutil.copytree(ROOT / "data" / "public", self.public)

    def tearDown(self):
        self.temp.cleanup()

    def test_public_data_is_normalized_with_traceable_manifest(self):
        output = self.base / "out"
        result = adapt_public_data(self.public, output)
        self.assertEqual(result["status"], "READY")
        self.assertGreater(result["normalized_rows"], 0)
        self.assertEqual(result["linkage_policy"], "AGGREGATE_ONLY_NO_LOT_VIN_JOIN")
        self.assertTrue((output / "normalized_public_signals.csv").exists())
        self.assertTrue(result["files"]["monthly_panel.csv"]["sha256"])

    def test_invalid_public_value_blocks_output(self):
        target = self.public / "recall_detection_12m.csv"
        text = target.read_text(encoding="utf-8-sig").replace("미탐지", "판정오류", 1)
        target.write_text(text, encoding="utf-8-sig")
        output = self.base / "bad"
        result = adapt_public_data(self.public, output)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse((output / "normalized_public_signals.csv").exists())

    def test_pipeline_accepts_public_and_enterprise_inputs_together(self):
        result = run_pipeline(
            ROOT / "enterprise_data" / "demo_company_raw",
            ROOT / "enterprise_data" / "demo_company_mapping.json",
            ROOT / "enterprise_data" / "enterprise_analysis_rules.json",
            self.base / "pipeline",
            self.public,
        )
        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["stages"][0]["status"], "READY")
        self.assertTrue((self.base / "pipeline" / "current" / "00_public_evidence" / "public_data_manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
