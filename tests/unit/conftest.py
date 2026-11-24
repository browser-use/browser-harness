import pytest


@pytest.fixture(autouse=True)
def _private_script_journal(tmp_path, monkeypatch):
    # Every successful stdin run records itself for `scripts save --from-last`;
    # keep tests from overwriting the real ~/.config/browser-harness/runtime copy.
    # setdefault: tests that pick their own BH_RUNTIME_DIR keep it.
    import os

    if "BH_RUNTIME_DIR" not in os.environ:
        monkeypatch.setenv("BH_RUNTIME_DIR", str(tmp_path / "journal-rt"))
