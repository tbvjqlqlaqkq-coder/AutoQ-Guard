import unittest
from src.build_alert_review import render


class AlertReviewTests(unittest.TestCase):
    def row(self, month='2025-01-01', model='TEST'):
        return dict(BRAND='A', MODEL=model, YEAR='2020', CAT='B', MONTH=month, Y12='1', fixed_rule='1')

    def test_all_rows_preserved(self):
        text = render([self.row(), self.row('2025-02-01')])
        self.assertEqual(text.count('data-alert-row'), 2)
        self.assertEqual(text.count('<details class="group">'), 1)

    def test_escaping(self):
        text = render([self.row(model='<img src=x onerror=alert(1)>')])
        self.assertNotIn('<img', text)
        self.assertIn('&lt;img', text)

    def test_duplicates_fail(self):
        with self.assertRaises(ValueError):
            render([self.row(), self.row()])

    def test_negative_not_alert(self):
        row = self.row()
        row['fixed_rule'] = '0'
        self.assertNotIn('data-alert-row', render([row]))
