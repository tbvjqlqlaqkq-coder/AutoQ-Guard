import csv, sys, tempfile, unittest
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from run_stratified_safety_validation import prepare

class StratifiedSafetyValidationTests(unittest.TestCase):
    def test_weak_and_false_cases_are_balanced_by_class(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); scenario = prepare(root)
            self.assertEqual(scenario["weak_true_by_class"], {"SAFETY": 5, "POWERTRAIN": 5, "CONVENIENCE": 5, "SOFTWARE": 5})
            self.assertEqual(scenario["strong_false_by_class"], {"SAFETY": 5, "POWERTRAIN": 5, "CONVENIENCE": 5, "SOFTWARE": 5})
            with (root / "synthetic_ground_truth.csv").open(encoding="utf-8-sig") as handle:
                reasons = Counter(r["injected_reason"] for r in csv.DictReader(handle))
            self.assertEqual(reasons["STRATIFIED_WEAK_DEFECT"], 20); self.assertEqual(reasons["STRATIFIED_PROCESS_ANOMALY_WITHOUT_DEFECT"], 20)
if __name__ == "__main__": unittest.main()
