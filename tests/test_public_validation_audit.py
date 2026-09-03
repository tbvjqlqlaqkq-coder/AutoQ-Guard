import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from public_validation_audit import rule, metrics

class PublicAuditTests(unittest.TestCase):
    def row(self,c=0,p=0,s=0,i=0,y=0):
        return dict(C3=c,P3=p,S3=s,I3=i,Y12=y)
    def test_boundaries(self):
        for r,expected in [(self.row(c=4),0),(self.row(c=5),1),(self.row(c=5,p=3),0),(self.row(c=6,p=3),1),(self.row(s=2),1),(self.row(i=1),1)]:
            self.assertEqual(rule(r),expected)
    def test_confusion(self):
        m=metrics([self.row(c=5,y=1),self.row(c=5),self.row(y=1),self.row()])
        self.assertEqual([m[k] for k in ('tp','fp','fn','tn')],[1,1,1,1])
    def test_empty(self):
        self.assertIsNone(metrics([])['recall'])
