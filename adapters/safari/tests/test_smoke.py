"""Live-runner regressions: window stacking is not tab identity."""
import unittest

from scripts.smoke_safari import reference_state


class FixtureReferenceTests(unittest.TestCase):
    def setUp(self):
        self.before = [
            dict(window=9, index=0, url='http://fixture.invalid/a', title='Fixture A'),
            dict(window=9, index=1, url='http://fixture.invalid/b', title='Fixture B'),
            dict(window=4, index=0, url='http://fixture.invalid/c', title='Fixture C'),
        ]

    def test_window_stacking_order_does_not_report_changed_tabs(self):
        # Reproduced in live Safari: the references matched by window/index,
        # but Safari enumerated the windows in a different order after JS calls.
        after = [self.before[2], self.before[0], self.before[1]]
        self.assertNotEqual(self.before, after)
        self.assertEqual(reference_state(self.before), reference_state(after))
        self.assertEqual(self.before[0]['window'], 9, 'comparison must not sort the input in place')

    def test_real_reference_changes_are_still_rejected(self):
        for field, value in [('window', 15), ('index', 7),
                             ('url', 'https://changed.invalid/'), ('title', 'Changed')]:
            with self.subTest(field=field):
                after = [dict(tab) for tab in self.before]
                after[0][field] = value
                self.assertNotEqual(reference_state(self.before), reference_state(after))
        # Swapping actual tab indices is a tab move, unlike window stacking.
        after = [dict(tab) for tab in self.before]
        after[0]['index'], after[1]['index'] = 1, 0
        self.assertNotEqual(reference_state(self.before), reference_state(after))

    def test_added_missing_and_duplicate_references_are_not_hidden(self):
        for after in [self.before[:-1], self.before + [self.before[0]],
                      self.before + [dict(self.before[0], window=55)]]:
            with self.subTest(tab_count=len(after)):
                self.assertNotEqual(reference_state(self.before), reference_state(after))


if __name__ == '__main__':
    unittest.main()
