"""Client half of the daemon transport: one JSON request line, one JSON reply line.

The daemon (the browser-harness binary) owns the server half; paths and the wire
format must stay in step with go/internal/ipc.
"""
import json, os, re, socket, sys
from pathlib import Path

from . import paths

IS_WINDOWS = sys.platform == "win32"
BH_TMP_DIR = os.environ.get("BH_TMP_DIR")
BH_RUNTIME_DIR = os.environ.get("BH_RUNTIME_DIR") or BH_TMP_DIR
BH_RUNTIME_DIR_SHARED = os.environ.get("BH_RUNTIME_DIR_SHARED") == "1"
_TMP = paths.tmp_dir()
_RUNTIME = paths.ensure_private_dir(Path(BH_RUNTIME_DIR).expanduser().resolve()) if BH_RUNTIME_DIR else paths.runtime_dir()
_NAME_RE = re.compile(r"\A[A-Za-z0-9_-]{1,64}\Z")


def _check(name):  # path-traversal guard for BU_NAME
    if not _NAME_RE.match(name or ""):
        raise ValueError(f"invalid BU_NAME {name!r}: must match [A-Za-z0-9_-]{{1,64}}")
    return name


def _runtime_stem(name):  # "bu" when BH_RUNTIME_DIR isolates us, else "bu-<NAME>"
    _check(name)
    return "bu" if BH_RUNTIME_DIR and not BH_RUNTIME_DIR_SHARED else f"bu-{name}"


def port_path(name):  return _RUNTIME / f"{_runtime_stem(name)}.port"  # Windows-only: {"port","token"}
def _sock_path(name): return _RUNTIME / f"{_runtime_stem(name)}.sock"


def _read_port_file(name):
    try:
        d = json.loads(port_path(name).read_text(encoding="utf-8"))
        return int(d["port"]), d["token"]
    except (FileNotFoundError, ValueError, KeyError, TypeError, OSError):
        return None, None


def sock_addr(name):  # display-only
    if not IS_WINDOWS: return str(_sock_path(name))
    port, _ = _read_port_file(name)
    return f"127.0.0.1:{port}" if port else f"tcp:{_runtime_stem(name)}"


def connect(name, timeout=1.0):
    """Returns (sock, token); token is None on POSIX. Callers include it as req["token"] on Windows."""
    if not IS_WINDOWS:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout); s.connect(str(_sock_path(name))); return s, None
    port, token = _read_port_file(name)
    if port is None: raise FileNotFoundError(str(port_path(name)))
    s = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    s.settimeout(timeout); return s, token


def request(c, token, req):
    """Send one request on an open socket and parse the reply. Caller closes the socket."""
    if token: req = {**req, "token": token}
    c.sendall((json.dumps(req) + "\n").encode())
    data = b""
    while not data.endswith(b"\n"):
        chunk = c.recv(1 << 16)
        if not chunk: break
        data += chunk
    return json.loads(data or b"{}")
