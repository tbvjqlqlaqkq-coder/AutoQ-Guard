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

    def test_chart_recalculates(self):
        text = render([self.row(), self.row('2025-02-01')])
        self.assertIn('모두 검토 · 2건', text)
        self.assertIn('연속 경보 첫 회만 · 1건 (50.0% 감소)', text)
        self.assertNotIn('389건', text)

    def test_period_changes(self):
        text = render([self.row('2024-05-01')])
        self.assertIn('2024-05 ~ 2024-05', text)
        self.assertNotIn('2025년 1~6월', text)

    def test_empty_fails(self):
        with self.assertRaises(ValueError):
            render([])

    def test_bad_date_fails(self):
        for month in ('2025-02-30', '2025-02-02'):
            with self.assertRaises(ValueError):
                render([self.row(month)])

    def test_missing_key_fails(self):
        with self.assertRaises(ValueError):
            render([self.row(model=' ')])

    def test_zero_alert_chart(self):
        row = self.row()
        row['fixed_rule'] = '0'
        self.assertIn('모두 검토 · 0건', render([row]))
