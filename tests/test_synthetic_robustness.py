import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from run_synthetic_robustness import run


class SyntheticRobustnessTests(unittest.TestCase):
    def test_noisy_scenario_exposes_false_positives_and_false_negatives(self):
        project_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            result = run(Path(temp) / "robustness", project_root)
            metrics = result["metrics"]
            self.assertEqual(metrics["true_positive"], 20)
            self.assertEqual(metrics["false_positive"], 10)
            self.assertEqual(metrics["false_negative"], 10)
            self.assertEqual(metrics["true_negative"], 960)
            self.assertAlmostEqual(metrics["precision"], 2 / 3, places=5)
            self.assertAlmostEqual(metrics["recall"], 2 / 3, places=5)


if __name__ == "__main__":
    unittest.main()
