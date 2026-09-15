import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from secondary_evidence_validation import evidence_score,evaluate

class SecondaryEvidenceTests(unittest.TestCase):
    def test_score_uses_only_operational_signals(self):
        self.assertEqual(evidence_score({"repeat_anomaly_count":"2","early_claim_count":"2","failure_code_concentration":"0.7","supplier_repeat_count":"2"}),100)
    def test_boundary_lot_requires_secondary_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/"truth.csv").write_text("lot_id,is_injected_risk\nA,1\nB,0\n",encoding="utf-8"); (root/"risk.csv").write_text("lot_id,safety_class,risk_score\nA,SAFETY,40\nB,SAFETY,40\n",encoding="utf-8"); (root/"signals.csv").write_text("lot_id,repeat_anomaly_count,early_claim_count,failure_code_concentration,supplier_repeat_count\nA,2,2,0.7,2\nB,0,0,0.1,0\n",encoding="utf-8")
            result=evaluate(root/"truth.csv",root/"risk.csv",root/"signals.csv"); self.assertEqual(result["metrics"]["tp"],1); self.assertEqual(result["metrics"]["fp"],0)
    def test_missing_signal_lot_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/"truth.csv").write_text("lot_id,is_injected_risk\nA,1\n",encoding="utf-8"); (root/"risk.csv").write_text("lot_id,safety_class,risk_score\nA,SAFETY,40\n",encoding="utf-8"); (root/"signals.csv").write_text("lot_id,repeat_anomaly_count,early_claim_count,failure_code_concentration,supplier_repeat_count\n",encoding="utf-8")
            with self.assertRaises(ValueError): evaluate(root/"truth.csv",root/"risk.csv",root/"signals.csv")
if __name__=="__main__": unittest.main()
