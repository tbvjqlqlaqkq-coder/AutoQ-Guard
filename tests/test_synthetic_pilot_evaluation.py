import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from evaluate_synthetic_pilot import evaluate


class SyntheticPilotEvaluationTests(unittest.TestCase):
    def test_metrics_are_calculated_from_lot_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with (root / "truth.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["lot_id", "is_injected_risk"])
                writer.writeheader()
                writer.writerows([{"lot_id": "L1", "is_injected_risk": "1"},
                                  {"lot_id": "L2", "is_injected_risk": "0"},
                                  {"lot_id": "L3", "is_injected_risk": "1"},
                                  {"lot_id": "L4", "is_injected_risk": "0"}])
            with (root / "risk.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["lot_id", "risk_level"])
                writer.writeheader()
                writer.writerows([{"lot_id": "L1", "risk_level": "HIGH"},
                                  {"lot_id": "L2", "risk_level": "HIGH"},
                                  {"lot_id": "L3", "risk_level": "NORMAL"},
                                  {"lot_id": "L4", "risk_level": "NORMAL"}])
            result = evaluate(root / "truth.csv", root / "risk.csv")
            self.assertEqual((result["true_positive"], result["false_positive"],
                              result["false_negative"], result["true_negative"]), (1, 1, 1, 1))
            self.assertEqual(result["f1"], 0.5)

    def test_mismatched_lot_set_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "truth.csv").write_text("lot_id,is_injected_risk\nL1,1\n", encoding="utf-8")
            (root / "risk.csv").write_text("lot_id,risk_level\nL2,HIGH\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                evaluate(root / "truth.csv", root / "risk.csv")


if __name__ == "__main__":
    unittest.main()
