import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from capacity_break_even import simulate

def rows():
    return [dict(BRAND='KIA',MODEL=str(i),YEAR='2020',CAT='TEST',MONTH='2025-01-01',Y12=i%2,fixed_rule=1) for i in range(10)]
def run(rs,cap=5,success=0.5,overlap=0.3):
    return simulate(rs,'fixed_rule',cap,50,500,300,20,success,overlap)

class CapacityTests(unittest.TestCase):
    def test_capacity(self):
        s=run(rows());self.assertEqual(s['reviewed'],5)
        self.assertEqual(s['unreviewed'],5)
        self.assertEqual(s['expected_reviewed_positive_rows'],2.5)
    def test_zero_capacity(self):self.assertIsNone(run(rows(),0)['break_even_avoided_loss_krw_per_positive_row_unit'])
    def test_no_increment(self):self.assertIsNone(run(rows(),overlap=1)['break_even_avoided_loss_krw_per_positive_row_unit'])
    def test_duplicates(self):
        rs=rows()
        with self.assertRaises(ValueError):run(rs+[rs[0]])
    def test_bad_rate(self):
        with self.assertRaises(ValueError):run(rows(),success=1.1)
    def test_no_oracle(self):
        self.assertEqual(run(rows())['expected_reviewed_positive_rows'],run(rows()[::-1])['expected_reviewed_positive_rows'])
