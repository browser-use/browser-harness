import json
import subprocess
import unittest
from unittest.mock import patch
from safari_harness import Safari, SafariError, _bridge

TAB = dict(window=9, index=0, url='https://example.com', title='Example')

class AdapterTests(unittest.TestCase):
    def test_no_implicit_user_tab(self):
        with self.assertRaises(SafariError):
            Safari().page_info()

    def test_reject_executable_navigation_before_transport(self):
        def transport(*a, **k):
            self.fail('transport should not run')
        with self.assertRaises(ValueError):
            Safari(transport).new_tab('javascript:alert(1)')

    def test_page_script_quotes_are_data(self):
        calls = []
        def transport(action, **kw):
            calls.append((action, kw))
            return TAB.copy() if action == 'info' else {'result': 'true'}
        s = Safari(transport)
        s.switch_tab(TAB)
        value = '"; globalThis.pwned = true; //\n$(touch /tmp/no)'
        s.fill('#name', value)
        self.assertIn(json.dumps(value), calls[-1][1]['code'])
        self.assertEqual(calls[-1][1]['target'], TAB)

    def test_cdp_fails_explicitly(self):
        with self.assertRaises(NotImplementedError):
            Safari().cdp('Page.navigate', url='https://example.com')

    @patch('safari_harness.subprocess.run')
    def test_transport_passes_data_without_shell(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, '{"ok":true}', '')
        self.assertEqual(_bridge('js', code='"; dangerous()'), {'ok': True})
        args, kw = run.call_args
        self.assertNotIn('shell', kw)
        self.assertEqual(args[0], ['/usr/bin/osascript', '-l', 'JavaScript', '-'])
        self.assertNotIn('dangerous()', ' '.join(args[0]))
        self.assertIn(json.dumps('"; dangerous()'), kw['input'])

    @patch('safari_harness.subprocess.run')
    def test_timeout_does_not_retry_mutation(self, run):
        run.side_effect = subprocess.TimeoutExpired('osascript', 30)
        with self.assertRaisesRegex(SafariError, 'do not blindly repeat'):
            _bridge('navigate', url='https://example.com')
        self.assertEqual(run.call_count, 1)

    @patch('safari_harness.subprocess.run')
    def test_permission_failure_is_not_success(self, run):
        run.return_value = subprocess.CompletedProcess([], 1, '', 'Not authorized (-1743)')
        with self.assertRaisesRegex(SafariError, '-1743'):
            _bridge('list')


class SelectionSafetyTests(unittest.TestCase):
    """D1: selection failures must never leave an old tab usable for writes."""

    recovery_tab = dict(window=77, index=1, url='https://recovery.invalid/form', title='Recovery')

    def harness(self, failure_action=None, failure_target=None, error=None):
        calls = []

        def transport(action, **kw):
            # Retain only synthetic action/target metadata, never page code/content.
            calls.append((action, kw.get('target')))
            if action == failure_action and (failure_target is None or kw.get('target') == failure_target):
                raise error
            if action == 'info':
                return kw['target'].copy()
            if action == 'new':
                return self.recovery_tab.copy()
            if action == 'navigate':
                return dict(kw['target'], url=kw['url'])
            if action == 'js':
                return {'result': 'true'}
            self.fail(f'unexpected transport action: {action}')

        return Safari(transport), calls

    def mutations(self, safari):
        return (
            ('fill', lambda: safari.fill('#name', 'SYNTHETIC_D1_VALUE')),
            ('click', lambda: safari.click('#submit')),
            ('js', lambda: safari.js("document.body.dataset.d1 = 'SYNTHETIC_D1_VALUE'")),
            ('navigation', lambda: safari.goto_url('https://recovery.invalid/next')),
        )

    def assert_locked_until_selection(self, safari, calls, *, create=False):
        calls.clear()
        with self.subTest(operation='current_tab'):
            with self.assertRaisesRegex(SafariError, 'No tab selected'):
                safari.current_tab()
        for name, mutate in self.mutations(safari):
            with self.subTest(operation=name):
                before = len(calls)
                with self.assertRaisesRegex(SafariError, 'No tab selected'):
                    mutate()
                self.assertEqual(len(calls), before, 'blocked mutation reached transport')
        self.assertEqual(calls, [], 'transport must receive zero mutations before explicit selection')

        # Recovery itself must be explicit and successful. Once selected, all four
        # operations must use that new reference instead of the prior target.
        if create:
            selected = safari.new_tab(self.recovery_tab['url'])
        else:
            selected = safari.switch_tab(self.recovery_tab)
        self.assertEqual(selected, self.recovery_tab)
        calls.clear()
        for _, mutate in self.mutations(safari):
            mutate()
        self.assertEqual([action for action, _ in calls], ['js', 'js', 'js', 'navigate'])
        self.assertEqual([target for _, target in calls], [self.recovery_tab] * 4)

    def test_no_selection_rejects_page_mutations_until_explicit_selection(self):
        safari, calls = self.harness()
        self.assert_locked_until_selection(safari, calls)

    def test_failed_selection_clears_previous_target(self):
        variants = (
            (TAB, dict(TAB, window=10), SafariError('selected window closed')),
            # Distinct URL/title and a reordered tab reference, not merely another
            # copy of the original window-closure fixture.
            (dict(window=31, index=2, url='http://variant.invalid/a', title='Variant β'),
             dict(window=31, index=0, url='http://variant.invalid/b', title='Intended β'),
             SafariError('tab reference changed after reorder')),
        )
        for old, intended, error in variants:
            with self.subTest(intended=intended):
                safari, calls = self.harness('info', intended, error)
                safari.switch_tab(old)
                calls.clear()
                with self.assertRaisesRegex(SafariError, str(error)):
                    safari.switch_tab(intended)
                self.assertEqual(calls, [('info', intended)])
                self.assert_locked_until_selection(safari, calls)

    def test_local_selection_validation_failure_clears_previous_target(self):
        invalid_targets = (None, {}, dict(TAB, index=-1), dict(TAB, window=True), dict(TAB, url=None))
        for intended in invalid_targets:
            with self.subTest(intended=intended):
                safari, calls = self.harness()
                safari.switch_tab(TAB)
                calls.clear()
                with self.assertRaises(ValueError):
                    safari.switch_tab(intended)
                self.assertEqual(calls, [], 'local validation must precede transport')
                self.assert_locked_until_selection(safari, calls)

    def test_failed_creation_clears_previous_target(self):
        for message in ('Not authorized (-1743)', 'creation timed out; action outcome unknown'):
            with self.subTest(failure=message):
                safari, calls = self.harness('new', error=SafariError(message))
                safari.switch_tab(TAB)
                calls.clear()
                with self.assertRaises(SafariError):
                    safari.new_tab('https://intended.invalid/new')
                self.assertEqual(calls, [('new', None)], 'creation must not be retried')
                self.assert_locked_until_selection(safari, calls)

    def test_local_creation_validation_failure_clears_previous_target(self):
        for url in ('javascript:alert(1)', 'ftp://variant.invalid/new', None):
            with self.subTest(url=url):
                safari, calls = self.harness()
                safari.switch_tab(TAB)
                calls.clear()
                with self.assertRaises(ValueError):
                    safari.new_tab(url)
                self.assertEqual(calls, [], 'local validation must precede transport')
                self.assert_locked_until_selection(safari, calls, create=True)

if __name__ == '__main__':
    unittest.main()
