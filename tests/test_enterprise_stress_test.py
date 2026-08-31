import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from enterprise_stress_test import generate_dataset, vin_for
from enterprise_import import import_and_validate


class EnterpriseStressDatasetTests(unittest.TestCase):
    def test_vin_is_valid_length(self):
        self.assertEqual(len(vin_for(123)), 17)

    def test_generated_enterprise_format_imports(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            counts = generate_dataset(base / "raw", base / "mapping.json", 10, 2)
            result = import_and_validate(base / "raw", base / "mapping.json", base / "import")
            self.assertEqual(result["status"], "READY")
            self.assertEqual(counts["vehicles"], 20)


if __name__ == "__main__":
    unittest.main()
