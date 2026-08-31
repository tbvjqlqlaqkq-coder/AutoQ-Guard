import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from enterprise_concurrency_test import percentile


class EnterpriseConcurrencyHelpersTests(unittest.TestCase):
    def test_percentile(self):
        self.assertEqual(percentile([1, 2, 3, 4, 5], 0.50), 3)
        self.assertEqual(percentile([1, 2, 3, 4, 5], 0.95), 5)
        self.assertEqual(percentile([], 0.95), 0)


if __name__ == "__main__":
    unittest.main()
