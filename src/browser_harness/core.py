"""Bridge to browser-harness-core, the Go binary that owns everything except the snippet language."""
import json, os, platform, shutil, subprocess, sys, tempfile
from pathlib import Path

_PACKAGE = Path(__file__).resolve().parent
_EXE = "browser-harness-core.exe" if sys.platform == "win32" else "browser-harness-core"


def binary():
    """BH_CORE, then the binary shipped in the package, then PATH."""
    explicit = os.environ.get("BH_CORE")
    if explicit:
        return explicit
    bundled = _PACKAGE / "bin" / _EXE
    if bundled.is_file():
        return str(bundled)
    found = shutil.which(_EXE)
    if found:
        return found
    raise RuntimeError(f"{_EXE} not found -- reinstall browser-harness or set BH_CORE")


def _version():
    try:
        from importlib.metadata import PackageNotFoundError, version
        try:
            return version("browser-harness")
        except PackageNotFoundError:
            return ""
    except Exception:
        return ""


def _repo_root():
    # Only the package's own parent (flat) or grandparent (src layout) counts, so an
    # enclosing repository that merely contains a venv is never mistaken for ours.
    for candidate in (_PACKAGE.parent, _PACKAGE.parent.parent):
        if (candidate / ".git").is_dir():
            return candidate
    return None


def env():
    """Process environment plus what the Go core needs to know about this Python install."""
    e = dict(os.environ)
    e.setdefault("BH_PYTHON", sys.executable)
    e.setdefault("BH_PYTHON_VERSION", platform.python_version())
    e.setdefault("BH_PACKAGE_DIR", str(_PACKAGE))
    e.setdefault("BH_VERSION", _version())
    repo = _repo_root()
    if repo is not None:
        e.setdefault("BH_REPO_ROOT", str(repo))
    return e


def call(fn, **args):
    """Run one core function. stdout/stderr stay the user's; errors raise RuntimeError with the same text as before."""
    fd, result_path = tempfile.mkstemp(prefix="bh-call-", suffix=".json")
    os.close(fd)
    try:
        subprocess.run([binary(), "call", fn, result_path, json.dumps(args, default=str)], env=env(), check=False)
        try:
            with open(result_path, encoding="utf-8") as f:
                reply = json.load(f)
        except (OSError, ValueError):
            raise RuntimeError(f"browser-harness-core call {fn} produced no result") from None
    finally:
        try: os.unlink(result_path)
        except OSError: pass
    if "error" in reply:
        raise RuntimeError(reply["error"])
    return reply.get("result")
