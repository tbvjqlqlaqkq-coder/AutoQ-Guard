import csv
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from enterprise_import import import_and_validate
from enterprise_risk_analyzer import analyze


class EnterpriseRiskAnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.raw = self.base / "raw"
        self.mapping = self.base / "mapping.json"
        self.import_work = self.base / "import"
        self.analysis = self.base / "analysis"
        shutil.copytree(ROOT / "enterprise_data" / "demo_company_raw", self.raw)
        shutil.copy2(ROOT / "enterprise_data" / "demo_company_mapping.json", self.mapping)
        imported = import_and_validate(self.raw, self.mapping, self.import_work)
        self.assertEqual(imported["status"], "READY")

    def tearDown(self):
        self.temp.cleanup()

    def test_ready_data_produces_high_risk_lot_and_affected_vin(self):
        summary = analyze(
            self.import_work / "standardized", self.analysis,
            ROOT / "enterprise_data" / "enterprise_analysis_rules.json",
        )
        self.assertEqual(summary["status"], "READY")
        self.assertEqual(summary["high_risk_lots"], 1)
        self.assertEqual(summary["affected_vehicle_links"], 1)
        self.assertEqual(summary["data_sufficiency"], "INSUFFICIENT")
        self.assertFalse(summary["decision_gate_passed"])
        with (self.analysis / "lot_risk_results.csv").open("r", encoding="utf-8-sig") as handle:
            row = next(csv.DictReader(handle))
        self.assertEqual(row["risk_level"], "HIGH")
        self.assertEqual(row["action_code"], "URGENT_SAFETY_REVIEW")

    def test_corrupted_standard_data_is_blocked_before_analysis(self):
        path = self.import_work / "standardized" / "process_inspection.csv"
        text = path.read_text(encoding="utf-8-sig").replace("0.08", "확인불가")
        path.write_text(text, encoding="utf-8-sig")
        summary = analyze(
            self.import_work / "standardized", self.analysis,
            ROOT / "enterprise_data" / "enterprise_analysis_rules.json",
        )
        self.assertEqual(summary["status"], "BLOCKED")
        self.assertFalse(summary["analysis_allowed"])


if __name__ == "__main__":
    unittest.main()
