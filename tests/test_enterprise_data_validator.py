import csv
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from enterprise_data_validator import validate_directory


class EnterpriseDataValidatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.input_dir = self.base / "input"
        self.output_dir = self.base / "output"
        shutil.copytree(ROOT / "enterprise_data" / "templates", self.input_dir)

    def tearDown(self):
        self.temp.cleanup()

    def rewrite(self, filename, rows):
        path = self.input_dir / filename
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    def read_rows(self, filename):
        with (self.input_dir / filename).open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    def test_valid_templates_are_ready(self):
        result = validate_directory(self.input_dir, self.output_dir)
        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["errors"], 0)
        self.assertTrue((self.output_dir / "validation_summary.json").exists())

    def test_invalid_rate_is_blocked_instead_of_becoming_zero(self):
        rows = self.read_rows("process_inspection.csv")
        rows[0]["recheck_rate"] = "8%"
        self.rewrite("process_inspection.csv", rows)
        result = validate_directory(self.input_dir, self.output_dir)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(any(item.code == "INVALID_VALUE" and item.column == "recheck_rate" for item in result["issues"]))

    def test_unknown_vin_reference_is_blocked(self):
        rows = self.read_rows("warranty_claim.csv")
        rows[0]["vin"] = "KMHUNKNOWN12345678"
        self.rewrite("warranty_claim.csv", rows)
        result = validate_directory(self.input_dir, self.output_dir)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(any(item.code == "FK_VIN_NOT_FOUND" for item in result["issues"]))

    def test_missing_file_is_blocked(self):
        (self.input_dir / "cost_master.csv").unlink()
        result = validate_directory(self.input_dir, self.output_dir)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(any(item.code == "FILE_MISSING" for item in result["issues"]))


if __name__ == "__main__":
    unittest.main()
