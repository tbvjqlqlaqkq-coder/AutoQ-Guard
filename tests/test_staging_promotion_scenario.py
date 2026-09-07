import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from staging_promotion_scenario import run_scenario


class StagingPromotionScenarioTests(unittest.TestCase):
    def test_synthetic_scenario_builds_candidate_and_blocks_unsafe_promotion(self):
        with tempfile.TemporaryDirectory() as folder:
            result = run_scenario(ROOT, Path(folder))
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["approved_tables"], 5)
        self.assertEqual(result["promotion_attempt"], "BLOCKED")
        self.assertTrue(result["live_database_unchanged"])


if __name__ == "__main__":
    unittest.main()
