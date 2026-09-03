import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
try:
    import numpy as np
    from run_purged_ml import choose_threshold
except ModuleNotFoundError:
    choose_threshold=None

@unittest.skipIf(choose_threshold is None,'Optional ML environment is not installed')
class ThresholdTests(unittest.TestCase):
    def test_no_feasible_candidate(self):
        self.assertIsNone(choose_threshold(np.array([0,1]),np.array([0.01,0.01]),1.0))
    def test_validation_cost(self):
        t=choose_threshold(np.array([0,1]),np.array([0.1,0.9]),1.0)
        self.assertEqual(t,0.11)
