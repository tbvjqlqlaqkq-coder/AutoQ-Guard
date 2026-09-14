import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from threshold_cost_tradeoff import sweep


class ThresholdCostTradeoffTests(unittest.TestCase):
    def test_tradeoff_uses_explicit_cost_assumptions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "truth.csv").write_text(
                "lot_id,is_injected_risk\nA,1\nB,1\nC,0\nD,0\n", encoding="utf-8")
            (root / "risk.csv").write_text(
                "lot_id,risk_score\nA,70\nB,45\nC,50\nD,10\n", encoding="utf-8")
            result = sweep(root / "truth.csv", root / "risk.csv", [40, 60],
                           defect_loss_krw=1000, review_cost_krw=100)
            low, high = result["results"]
            self.assertEqual((low["tp"], low["fp"], low["fn"]), (2, 1, 0))
            self.assertEqual((high["tp"], high["fp"], high["fn"]), (1, 0, 1))
            self.assertEqual(result["net_benefit_leaders"], [40])

    def test_mismatched_lots_are_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "truth.csv").write_text("lot_id,is_injected_risk\nA,1\n", encoding="utf-8")
            (root / "risk.csv").write_text("lot_id,risk_score\nB,70\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                sweep(root / "truth.csv", root / "risk.csv")


if __name__ == "__main__":
    unittest.main()
