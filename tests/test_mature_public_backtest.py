import sys, unittest
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from mature_public_backtest import classify, label_end, month_end

def row(month,c=0,y=0):
    return dict(BRAND='KIA',MODEL='TEST',YEAR='2020',CAT='BRAKES',MONTH=month,
                COMPLAINTS=c,SERIOUS=0,INVESTIGATIONS=0,C3=c,P3=0,S3=0,I3=0,Y12=y)

class MatureTests(unittest.TestCase):
    def test_boundary(self):
        rs=classify([row('2025-06-01',5),row('2025-07-01',5,1)],date(2026,6,30))
        self.assertEqual(rs[0]['evaluation_status'],'EVALUABLE')
        self.assertEqual(rs[1]['evaluation_status'],'PENDING_FOLLOWUP')
        self.assertIsNone(rs[1]['evaluation_label'])
    def test_future_signal_does_not_activate_past(self):
        rs=classify([row('2024-01-01',0,1),row('2024-02-01',5)],date(2026,6,30))
        self.assertEqual(rs[0]['evaluation_status'],'UNOBSERVED_COHORT')
        self.assertEqual(rs[1]['evaluation_status'],'EVALUABLE')
    def test_unsorted_same(self):
        rs=[row('2024-01-01'),row('2024-02-01',5)]
        self.assertEqual(classify(rs,date(2026,6,30)),classify(rs[::-1],date(2026,6,30)))
    def test_labels_do_not_affect_status(self):
        a=classify([row('2025-07-01',5,0)],date(2026,6,30))[0]
        b=classify([row('2025-07-01',5,1)],date(2026,6,30))[0]
        self.assertEqual(a['evaluation_status'],b['evaluation_status'])
        self.assertEqual(a['prediction'],b['prediction'])
    def test_calendar(self):
        self.assertEqual(month_end('2024-02-01'),date(2024,2,29))
        self.assertEqual(label_end('2023-02-01'),date(2024,2,29))
