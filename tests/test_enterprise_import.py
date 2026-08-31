import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from enterprise_import import import_and_validate


class EnterpriseImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.raw = self.base / "raw"
        self.mapping = self.base / "mapping.json"
        self.work = self.base / "work"
        shutil.copytree(ROOT / "enterprise_data" / "demo_company_raw", self.raw)
        shutil.copy2(ROOT / "enterprise_data" / "demo_company_mapping.json", self.mapping)

    def tearDown(self):
        self.temp.cleanup()

    def load_mapping(self):
        return json.loads(self.mapping.read_text(encoding="utf-8-sig"))

    def save_mapping(self, mapping):
        self.mapping.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8-sig")

    def test_korean_company_format_converts_and_validates(self):
        result = import_and_validate(self.raw, self.mapping, self.work)
        self.assertEqual(result["status"], "READY")
        self.assertTrue((self.work / "standardized" / "part_lot.csv").exists())
        self.assertTrue((self.work / "validation" / "validation_summary.json").exists())

    def test_missing_source_column_blocks_import(self):
        mapping = self.load_mapping()
        mapping["tables"]["part_lot.csv"]["columns"]["lot_id"] = "존재하지않는열"
        self.save_mapping(mapping)
        result = import_and_validate(self.raw, self.mapping, self.work)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["stage"], "IMPORT")

    def test_bad_percent_blocks_import(self):
        path = self.raw / "공정검사.csv"
        text = path.read_text(encoding="utf-8-sig").replace("8%", "확인불가")
        path.write_text(text, encoding="utf-8-sig")
        result = import_and_validate(self.raw, self.mapping, self.work)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["stage"], "IMPORT")


if __name__ == "__main__":
    unittest.main()
