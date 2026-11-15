import pytest

from browser_harness import scripts


@pytest.fixture(autouse=True)
def _private_script_journal(tmp_path, monkeypatch):
    # Every successful stdin run records itself for `scripts save --from-last`;
    # keep tests from overwriting the real ~/.config/browser-harness/runtime copy.
    monkeypatch.setattr(scripts, "journal_path", lambda: tmp_path / "last-script.py")
