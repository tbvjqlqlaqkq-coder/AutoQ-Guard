import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from watch_review_queue import build_queue,priority_score

class WatchReviewQueueTests(unittest.TestCase):
    def test_partial_signal_is_ranked_first_without_using_label(self):
        with tempfile.TemporaryDirectory() as temp:
            r=Path(temp);(r/"truth.csv").write_text("lot_id,is_injected_risk\nA,1\nB,0\n",encoding="utf-8");(r/"risk.csv").write_text("lot_id,safety_class,risk_score\nA,SAFETY,40\nB,SAFETY,40\n",encoding="utf-8");(r/"signals.csv").write_text("lot_id,repeat_anomaly_count,early_claim_count,failure_code_concentration,supplier_repeat_count\nA,1,1,0.55,1\nB,0,0,0.1,0\n",encoding="utf-8")
            result=build_queue(r/"truth.csv",r/"risk.csv",r/"signals.csv",1);self.assertEqual(result["queue"][0]["lot_id"],"A");self.assertEqual(result["day1_true_defects_found"],1)
    def test_capacity_must_be_positive(self):
        with self.assertRaises(ValueError):build_queue(Path("x"),Path("y"),Path("z"),0)
    def test_priority_is_continuous(self):
        self.assertGreater(priority_score({"repeat_anomaly_count":"1","early_claim_count":"1","failure_code_concentration":"0.5","supplier_repeat_count":"1"}),priority_score({"repeat_anomaly_count":"0","early_claim_count":"0","failure_code_concentration":"0.1","supplier_repeat_count":"0"}))
if __name__=="__main__":unittest.main()
