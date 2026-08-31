import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from enterprise_pipeline import run_pipeline


class EnterprisePipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.raw = self.base / "raw"
        shutil.copytree(ROOT / "enterprise_data" / "demo_company_raw", self.raw)
        self.mapping = ROOT / "enterprise_data" / "demo_company_mapping.json"
        self.rules = ROOT / "enterprise_data" / "enterprise_analysis_rules.json"
        self.output = self.base / "pipeline"

    def tearDown(self):
        self.temp.cleanup()

    def test_complete_pipeline_publishes_current_only_after_success(self):
        result = run_pipeline(self.raw, self.mapping, self.rules, self.output)
        self.assertEqual(result["status"], "READY")
        self.assertFalse(result["decision_gate_passed"])
        self.assertTrue((self.output / "current" / "03_database" / "automotive_quality.db").exists())
        statuses = [stage["status"] for stage in result["stages"]]
        self.assertEqual(statuses, ["READY", "READY", "READY", "READY"])

    def test_bad_input_stops_following_stages_and_keeps_current(self):
        first = run_pipeline(self.raw, self.mapping, self.rules, self.output)
        self.assertEqual(first["status"], "READY")
        current_before = (self.output / "current" / "pipeline_summary.json").read_bytes()
        target = self.raw / "공정검사.csv"
        target.write_text(target.read_text(encoding="utf-8-sig").replace("8%", "오류값"), encoding="utf-8-sig")
        second = run_pipeline(self.raw, self.mapping, self.rules, self.output)
        self.assertEqual(second["status"], "BLOCKED")
        self.assertEqual(second["failed_stage"], "IMPORT_VALIDATE")
        self.assertEqual(second["stages"][1]["status"], "NOT_RUN")
        self.assertEqual((self.output / "current" / "pipeline_summary.json").read_bytes(), current_before)


if __name__ == "__main__":
    unittest.main()
