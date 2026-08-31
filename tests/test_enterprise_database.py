import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from enterprise_database import build_database, search_database
from enterprise_import import import_and_validate
from enterprise_risk_analyzer import analyze


class EnterpriseDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        raw = self.base / "raw"
        shutil.copytree(ROOT / "enterprise_data" / "demo_company_raw", raw)
        imported = import_and_validate(raw, ROOT / "enterprise_data" / "demo_company_mapping.json", self.base / "import")
        self.assertEqual(imported["status"], "READY")
        self.standardized = self.base / "import" / "standardized"
        self.analysis = self.base / "analysis"
        summary = analyze(self.standardized, self.analysis, ROOT / "enterprise_data" / "enterprise_analysis_rules.json")
        self.assertEqual(summary["status"], "READY")
        self.database = self.base / "db" / "quality.db"

    def tearDown(self):
        self.temp.cleanup()

    def build(self):
        return build_database(self.standardized, self.analysis, self.database, self.base / "report")

    def test_build_and_counts(self):
        result = self.build()
        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["row_counts"]["part_lot"], 1)
        connection = sqlite3.connect(self.database)
        try:
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        finally:
            connection.close()

    def test_search_by_lot_and_vin(self):
        self.build()
        by_lot = search_database(self.database, lot_id="LOT-DEMO-001")
        self.assertEqual(by_lot[0]["risk_level"], "HIGH")
        by_vin = search_database(self.database, vin="KMHDEMA1234567890")
        self.assertEqual(by_vin[0]["lot_id"], "LOT-DEMO-001")

    def test_parameterized_search_resists_injection(self):
        self.build()
        rows = search_database(self.database, lot_id="' OR 1=1 --")
        self.assertEqual(rows, [])
        connection = sqlite3.connect(self.database)
        try:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM part_lot").fetchone()[0], 1)
        finally:
            connection.close()

    def test_invalid_input_preserves_existing_database(self):
        self.build()
        original = self.database.read_bytes()
        path = self.standardized / "process_inspection.csv"
        path.write_text(path.read_text(encoding="utf-8-sig").replace("0.08", "INVALID"), encoding="utf-8-sig")
        result = self.build()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["database_replaced"])
        self.assertEqual(self.database.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
