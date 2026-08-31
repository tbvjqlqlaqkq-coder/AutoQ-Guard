import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from enterprise_dashboard import (
    dashboard_summary, mapping_preview, save_approved_staging,
    validate_staging_payload, validated_search,
)
from enterprise_pipeline import run_pipeline


class EnterpriseDashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        raw = self.base / "raw"
        shutil.copytree(ROOT / "enterprise_data" / "demo_company_raw", raw)
        result = run_pipeline(raw, ROOT / "enterprise_data" / "demo_company_mapping.json", ROOT / "enterprise_data" / "enterprise_analysis_rules.json", self.base / "pipeline")
        self.assertEqual(result["status"], "READY")
        self.current = self.base / "pipeline" / "current"
        self.db = self.current / "03_database" / "automotive_quality.db"

    def tearDown(self):
        self.temp.cleanup()

    def test_summary_exposes_gate_and_counts(self):
        result = dashboard_summary(self.db, self.current / "pipeline_summary.json")
        self.assertEqual(result["high_risk_lots"], 1)
        self.assertFalse(result["decision_gate_passed"])

    def test_search_and_input_limit(self):
        rows = validated_search(self.db, {"lot_id": ["LOT-DEMO-001"]})
        self.assertEqual(rows[0]["risk_level"], "HIGH")
        with self.assertRaises(ValueError):
            validated_search(self.db, {"lot_id": ["X" * 101]})

    def test_unknown_parameters_are_ignored(self):
        rows = validated_search(self.db, {"sql": ["DROP TABLE part_lot"]})
        self.assertEqual(len(rows), 1)

    def test_company_csv_headers_are_mapped_and_duplicates_blocked(self):
        result = mapping_preview(
            "part_lot.csv",
            ["부품LOT번호", "협력사코드", "부품번호", "안전등급", "입고일시", "입고수량"],
            "company.csv",
        )
        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["suggestions"]["lot_id"], "부품LOT번호")
        with self.assertRaises(ValueError):
            mapping_preview("part_lot.csv", ["LOT", "lot"], "duplicate.csv")

    def test_staging_requires_valid_data_and_matching_approval_token(self):
        payload = {
            "table": "part_lot.csv", "filename": "company.csv",
            "mapping": {"lot_id":"LOT", "supplier_id":"SUP", "part_number":"PART", "safety_class":"SAFETY", "received_at":"DATE", "quantity":"QTY"},
            "rows": [{"LOT":"lot-1", "SUP":"sup-1", "PART":"part-1", "SAFETY":"safety", "DATE":"2026-08-05", "QTY":"10"}],
        }
        checked = validate_staging_payload(payload)
        self.assertEqual(checked["status"], "READY_FOR_APPROVAL")
        self.assertEqual(checked["preview"][0]["lot_id"], "LOT-1")
        staged = save_approved_staging(checked, checked["approval_token"], self.base / "staging")
        self.assertEqual(staged["status"], "STAGED_NOT_LOADED")
        with self.assertRaises(ValueError):
            save_approved_staging(checked, "wrong-token", self.base / "staging")
        payload["rows"][0]["QTY"] = "10.5"
        self.assertEqual(validate_staging_payload(payload)["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
