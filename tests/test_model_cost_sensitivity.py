import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from model_cost_sensitivity import cost,crossing

class CostTests(unittest.TestCase):
    def test_cost(self):self.assertEqual(cost({'fp':347,'fn':302},10),3367)
    def test_crossing(self):
        a={'fp':347,'fn':302};b={'fp':2483,'fn':215}
        r=crossing(a,b)
        self.assertAlmostEqual(cost(a,r),cost(b,r))
        self.assertLess(cost(a,10),cost(b,10))
        self.assertGreater(cost(a,50),cost(b,50))
    def test_parallel(self):self.assertIsNone(crossing({'fp':1,'fn':2},{'fp':3,'fn':2}))
    def test_invalid(self):
        for r in (-1,float('inf'),float('nan')):
            with self.assertRaises(ValueError):cost({'fp':1,'fn':2},r)
