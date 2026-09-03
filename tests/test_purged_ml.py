import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from prepare_purged_ml import split_rows

def row(m):
    return dict(BRAND='KIA',MODEL='TEST',YEAR='2020',CAT='TEST',MONTH=m,
        COMPLAINTS=5,SERIOUS=0,INVESTIGATIONS=0,C3=5,P3=0,S3=0,I3=0,Y12=1)

class PurgedTests(unittest.TestCase):
    def test_boundaries(self):
        rs=[row(m) for m in ['2021-12-01','2022-01-01','2023-01-01','2023-12-01','2024-01-01','2025-01-01','2025-06-01','2025-07-01']]
        s=split_rows(rs)
        self.assertEqual([r['MONTH'] for r in s['train']],['2021-12-01'])
        self.assertEqual([r['MONTH'] for r in s['validation']],['2023-01-01','2023-12-01'])
        self.assertEqual([r['MONTH'] for r in s['test']],['2025-01-01','2025-06-01'])
    def test_no_future_activation(self):
        r=row('2021-12-01');r.update(COMPLAINTS=0,C3=0)
        self.assertEqual(split_rows([r,row('2023-01-01')])['train'],[])
