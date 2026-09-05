import os
from pathlib import Path
import subprocess
import sys

from browser_harness import daemon


def test_restart_retains_error_and_stderr_sink_when_history_is_trimmed(tmp_path, monkeypatch):
    path = tmp_path / "daemon.log"
    monkeypatch.setattr(daemon, "LOG", str(path))
    path.write_bytes(b"old\n" * 300_000 + b"fatal: original browser failure\n")
    # admin opens this descriptor before the child starts. Replacing the file
    # would silently send stderr to the old inode.
    with path.open("ab", buffering=0) as stderr:
        daemon._start_log()
        stderr.write(b"stderr: reconnect failed\n")
        daemon._start_log()
    data = path.read_text()
    assert "fatal: original browser failure" in data
    assert "stderr: reconnect failed" in data
    assert data.count("daemon starting pid=") == 2
    assert len(path.read_bytes()) < 1_050_000


def test_real_entrypoint_preserves_failure_across_repeated_failed_starts(tmp_path):
    # Only a fake CDP client is instantiated. No Chrome, cloud API, user daemon,
    # credentials or real endpoint is accessed.
    code = """
import runpy
from cdp_use.client import CDPClient
from browser_harness import _ipc
async def fail(self):
    raise RuntimeError('local startup sentinel')
CDPClient.start = fail
_ipc.ping = lambda *a, **kw: False
runpy.run_module('browser_harness.daemon', run_name='__main__')
"""
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("BH_", "BU_", "BROWSER_USE_"))}
    env.update(BH_HOME=str(tmp_path / "home"), BH_TMP_DIR=str(tmp_path / "logs"),
               BH_RUNTIME_DIR=str(tmp_path / "ipc"), BH_AGENT_WORKSPACE=str(tmp_path / "workspace"),
               BU_NAME="log-test", BU_CDP_WS="ws://127.0.0.1:1/devtools/browser/fake",
               PYTHONPATH=str(Path(daemon.__file__).parents[1]))
    for _ in range(2):
        result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, timeout=10)
        assert result.returncode == 1, result.stderr.decode()
    logs = list((tmp_path / "logs").glob("*.log"))
    assert len(logs) == 1
    text = logs[0].read_text()
    assert text.count("daemon starting pid=") == 2
    assert text.count("fatal: CDP WS handshake failed: local startup sentinel") == 2
    assert text.count("Traceback (most recent call last)") == 2
