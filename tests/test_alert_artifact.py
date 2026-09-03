import copy
import json
import unittest
from src.verify_alert_artifact import ROOT, verify


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.doc = (ROOT/'docs/demo/alert-review.html').read_text(encoding='utf-8')
        self.receipt = json.loads((ROOT/'docs/model_validation/alert_review_build.json').read_text(encoding='utf-8'))

    def test_committed_artifact(self):
        self.assertEqual(verify(self.doc, self.receipt)['status'], 'PASS')

    def test_line_endings(self):
        self.assertEqual(verify(self.doc.replace('\n', '\r\n'), self.receipt)['status'], 'PASS')

    def test_modified_html_rejected(self):
        with self.assertRaises(ValueError):
            verify(self.doc + 'modified', self.receipt)

    def test_modified_counts_rejected(self):
        changed = copy.deepcopy(self.receipt)
        changed['rendered_alerts'] += 1
        with self.assertRaises(ValueError):
            verify(self.doc, changed)

    def test_modified_comparison_rejected(self):
        changed = copy.deepcopy(self.receipt)
        changed['comparisons'][1]['review_rows'] = 999999
        with self.assertRaises(ValueError):
            verify(self.doc, changed)
