import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from safety_class_policy import compare

class SafetyClassPolicyTests(unittest.TestCase):
    def test_lower_safety_threshold_reduces_safety_miss(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / "truth.csv").write_text("lot_id,is_injected_risk\nA,1\nB,0\n", encoding="utf-8"); (root / "risk.csv").write_text("lot_id,safety_class,risk_score\nA,SAFETY,40\nB,CONVENIENCE,30\n", encoding="utf-8")
            result = compare(root / "truth.csv", root / "risk.csv", candidate_policy={"SAFETY": 35, "CONVENIENCE": 55})
            self.assertEqual(result["baseline"]["total"]["fn"], 1); self.assertEqual(result["class_policy"]["total"]["fn"], 0); self.assertFalse(result["governance"]["automatic_recall"])
    def test_policy_must_cover_all_classes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / "truth.csv").write_text("lot_id,is_injected_risk\nA,1\n", encoding="utf-8"); (root / "risk.csv").write_text("lot_id,safety_class,risk_score\nA,SAFETY,40\n", encoding="utf-8")
            with self.assertRaises(ValueError): compare(root / "truth.csv", root / "risk.csv", candidate_policy={"SOFTWARE": 55})
if __name__ == "__main__": unittest.main()
