"""Opt-in live checks on one synthetic localhost window; leaves the window open."""
import json
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from safari_harness import Safari, SafariError

if not __debug__:
    raise SafariError('Smoke verification requires assertions; run without -O/PYTHONOPTIMIZE.')

FIXTURE_VERSION = 3
CORPUS = [
    'Safari test — "quotes" and \\slashes\nsecond line',
    '\"; globalThis.pwned = true; //\n$(touch /tmp/safari-harness-must-not-run) `id`',
    '日本語 🧪 </textarea><script>globalThis.pwned=true</script>',
]


def reference_state(tabs):
    """Ignore window stacking order; retain every tab's identity and metadata."""
    return sorted(tabs, key=lambda tab: (tab['window'], tab['index']))


def reuse_probe():
    """Run in a separate Python/CLI process against only the named fixture."""
    request = json.load(sys.stdin)
    safari = Safari()
    matches = [t for t in safari.list_tabs()
               if t['url'] == request['target']['url'] and t['title'] == request['target']['title']]
    if len(matches) != 1 or matches[0] != request['target']:
        raise SafariError('Fixture reference changed between CLI invocations')
    safari.switch_tab(matches[0])
    print(json.dumps(safari.js('({marker:document.querySelector("#marker").textContent,session:sessionStorage.getItem("safari-harness-fixture")})')))


def main():
    marker = 'safari-harness-' + uuid.uuid4().hex
    title = 'Safari Harness Smoke ' + marker
    page = ('''<!doctype html><meta charset="utf-8"><title>''' + title + '''</title>
<label>Name <textarea id="name"></textarea></label>
<button id="save" onclick="document.getElementById('result').textContent=document.getElementById('name').value;document.getElementById('count').textContent=Number(document.getElementById('count').textContent)+1">Save</button>
<output id="result"></output><output id="count">0</output><output id="marker">''' + marker + '''</output>
<script>sessionStorage.setItem('safari-harness-fixture', ''' + json.dumps(marker) + ''');</script>''').encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != '/fixture.html':
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(page)))
            self.end_headers()
            self.wfile.write(page)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        safari = Safari()
        before = safari.list_tabs()
        previous_windows = {t['window'] for t in before}
        url = f'http://127.0.0.1:{server.server_port}/fixture.html'
        started = time.monotonic()
        created = safari.new_tab(url)
        while time.monotonic() - started < 30:
            tabs = safari.list_tabs()
            matches = [t for t in tabs if t['window'] == created['window']
                       and t['url'] == url and t['title'] == title]
            if len(matches) == 1:
                safari.switch_tab(matches[0])
                if safari.js('document.readyState') == 'complete':
                    break
            time.sleep(0.25)
        else:
            raise SafariError('Smoke fixture did not finish loading within 30 seconds; inspect existing windows before retrying.')
        target = safari.current_tab()
        if {t['window'] for t in tabs} - previous_windows != {target['window']}:
            raise SafariError('Expected exactly one new window; do not repeat creation.')
        if reference_state([t for t in tabs if t['window'] in previous_windows]) != reference_state(before):
            raise SafariError('Pre-existing tab metadata changed during fixture creation.')
        assert safari.js('document.querySelector("#marker").textContent') == marker
        reused = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), '--reuse-probe'],
            input=json.dumps({'target': target}), capture_output=True, text=True, timeout=30,
        )
        if reused.returncode:
            raise SafariError('Separate CLI fixture probe failed: ' + reused.stderr.strip())
        assert json.loads(reused.stdout) == {'marker': marker, 'session': marker}
        load_seconds = time.monotonic() - started
        assert load_seconds <= 30, f'Create/load/reuse exceeded 30 seconds: {load_seconds:.2f}'

        # Check the selection fix against real bridge rejection, then explicit recovery.
        for fail in (lambda: safari.switch_tab(dict(target, index=1_000_000)),
                     lambda: safari.new_tab('javascript:throw Error("must not run")')):
            try:
                fail()
            except (SafariError, ValueError):
                pass
            else:
                raise AssertionError('Expected selection/creation failure')
            try:
                safari.fill('#name', 'MUST_NOT_BE_INSERTED')
            except SafariError as error:
                assert 'No tab selected' in str(error)
            else:
                raise AssertionError('Mutation was accepted after failed selection')
            matches = [t for t in safari.list_tabs() if t == target]
            assert len(matches) == 1
            safari.switch_tab(matches[0])
            assert safari.js('document.querySelector("#name").value') == ''
            assert safari.js('document.querySelector("#count").textContent') == '0'

        for value in CORPUS:
            safari.fill('#name', value)
            assert safari.js('document.querySelector("#name").value') == value
        safari.click('#save')
        assert safari.js('document.querySelector("#result").textContent') == CORPUS[-1]
        assert safari.js('document.querySelector("#count").textContent') == '1'
        assert safari.js('typeof globalThis.pwned') == 'undefined'
        assert CORPUS[-1] in safari.get_page_content()
        after = safari.list_tabs()
        assert reference_state([t for t in after if t['window'] in previous_windows]) == reference_state(before)
        assert {t['window'] for t in after} - previous_windows == {target['window']}
        print(json.dumps({'result': 'passed', 'fixture_version': FIXTURE_VERSION,
                          'checks': ['new_window', 'load', 'separate_cli_reuse', 'session_marker',
                                     'failed_selection_rejected', 'invalid_creation_url_rejected',
                                     'exact_fill_corpus', 'single_click', 'read'],
                          'load_reuse_seconds': round(load_seconds, 3), 'click_count': 1,
                          'corpus_count': len(CORPUS), 'recordings': 'off'}))
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    if sys.argv[1:] == ['--reuse-probe']:
        reuse_probe()
    elif sys.argv[1:]:
        raise SystemExit('Usage: python scripts/smoke_safari.py')
    else:
        main()
