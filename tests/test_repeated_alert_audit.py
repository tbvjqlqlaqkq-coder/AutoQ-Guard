import unittest
from src.repeated_alert_audit import audit


def row(month, label='1', alarm='1'):
    return dict(BRAND='A', MODEL='B', YEAR='2020', CAT='C', MONTH=f'2025-{month:02}-01', Y12=label, fixed_rule=alarm)


class RepeatAuditTests(unittest.TestCase):
    def test_consecutive(self):
        r = audit([row(1), row(2), row(4)], 'fixed_rule', 'consecutive')
        self.assertEqual(r['review_rows'], 2)
        self.assertEqual(r['consecutive_episodes'], 2)

    def test_new_positive_after_negative(self):
        r = audit([row(1, '0'), row(2)], 'fixed_rule', 'consecutive')
        self.assertEqual(r['positive_episodes_without_retained_positive'], 1)

    def test_cooldown(self):
        r = audit([row(i) for i in range(1, 7)], 'fixed_rule', 'cooldown_3m')
        self.assertEqual(r['review_rows'], 2)

    def test_no_label_leakage(self):
        for policy in ('monthly', 'consecutive', 'cooldown_3m'):
            a = audit([row(i, '0') for i in range(1, 7)], 'fixed_rule', policy)
            b = audit([row(i, '1') for i in range(1, 7)], 'fixed_rule', policy)
            self.assertEqual(a['monthly'], b['monthly'])

    def test_duplicate(self):
        with self.assertRaises(ValueError):
            audit([row(1), row(1)], 'fixed_rule', 'monthly')

    def test_order(self):
        rows = [row(1), row(3), row(4)]
        self.assertEqual(audit(rows, 'fixed_rule', 'consecutive'), audit(rows[::-1], 'fixed_rule', 'consecutive'))

    def test_no_alerts(self):
        self.assertEqual(audit([row(1, alarm='0')], 'fixed_rule', 'monthly')['review_rows'], 0)
