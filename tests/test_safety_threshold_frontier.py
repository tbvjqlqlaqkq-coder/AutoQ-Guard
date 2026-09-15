import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from safety_threshold_frontier import analyze

class SafetyThresholdFrontierTests(unittest.TestCase):
    def test_detects_score_overlap_and_best_zero_miss(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/"truth.csv").write_text("lot_id,is_injected_risk\nA,1\nB,0\nC,1\n",encoding="utf-8"); (root/"risk.csv").write_text("lot_id,safety_class,risk_score\nA,SAFETY,40\nB,SAFETY,40\nC,SAFETY,100\n",encoding="utf-8")
            result=analyze(root/"truth.csv",root/"risk.csv",[35,45])
            self.assertFalse(result["threshold_alone_is_sufficient"]); self.assertEqual(result["best_zero_miss"]["threshold"],35); self.assertEqual(result["best_zero_miss"]["fp"],1)
    def test_requires_safety_rows(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/"truth.csv").write_text("lot_id,is_injected_risk\nA,1\n",encoding="utf-8"); (root/"risk.csv").write_text("lot_id,safety_class,risk_score\nA,SOFTWARE,40\n",encoding="utf-8")
            with self.assertRaises(ValueError): analyze(root/"truth.csv",root/"risk.csv")
    def test_highest_threshold_wins_when_zero_miss_results_are_equal(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/"truth.csv").write_text("lot_id,is_injected_risk\nA,1\n",encoding="utf-8"); (root/"risk.csv").write_text("lot_id,safety_class,risk_score\nA,SAFETY,40\n",encoding="utf-8")
            result=analyze(root/"truth.csv",root/"risk.csv",[20,35,40,45])
            self.assertEqual(result["best_zero_miss"]["threshold"],40)
if __name__=="__main__": unittest.main()
