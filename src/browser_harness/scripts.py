"""Saved scripts: rerun a working browser-harness script by name, no LLM.

A saved script is the agent's own stdin script with a comment header:

    <BH_AGENT_WORKSPACE>/scripts/<host>/<name>.py

    # browser-harness saved script
    # host: news.ycombinator.com
    # url: https://news.ycombinator.com/
    # params: {"page": "1"}
    # verified_at: never
    ...script body; reads PARAMS["page"], ends with an assert...

`scripts run` executes it like stdin code with PARAMS injected. Exit 0 stamps
verified_at; an exception prints `drifted: <error>` and exits 1 so the agent
fixes that file instead of redoing the task from zero.
"""
import json, os, re, sys, time, traceback
from pathlib import Path
from urllib.parse import urlparse

from . import paths
from .recorder import _scrub_url

REPLAY_IPC_TIMEOUT_SECONDS = 30.0
MARKER = "# browser-harness saved script"
_NAME_RE = re.compile(r"\A[A-Za-z0-9_-]{1,64}\Z")
_HOST_RE = re.compile(r"\A[a-z0-9-]+(\.[a-z0-9-]+)*\Z")
_HEADER_RE = re.compile(r"\A# ([a-z_]+): (.*)\Z")
_URL_RE = re.compile(r"""https?://[^\s'"{}]+""")
# Typed text on a line that smells like a credential gets swapped for a param.
_SECRET_LINE_RE = re.compile(r"\b(type_text|fill_input)\(.*(pass|secret|token|otp|api_?key)", re.I)
_LAST_LITERAL_RE = re.compile(r"""(?<!\w)("[^"\\\n]*"|'[^'\\\n]*')(\s*\)\s*)$""")

USAGE = """usage:
  browser-harness scripts save <name> [--from-last | --file PATH] [--host HOST] [--param k=v ...]
  browser-harness scripts run <name|host/name> [--param k=v ...]
  browser-harness scripts list [--host HOST]"""


def scripts_dir():
    return paths.workspace_dir() / "scripts"


def journal_path():
    """Last successful stdin script for this BU_NAME; `scripts save --from-last` reads it."""
    name = os.environ.get("BU_NAME", "default")
    return paths.runtime_dir() / f"last-script-{name if _NAME_RE.match(name) else 'default'}.py"


def journal(code):
    try:
        journal_path().write_text(code, encoding="utf-8")
    except OSError:
        pass


def host_of(url):
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def env_params():
    try:
        params = json.loads(os.environ.get("BH_PARAMS") or "{}")
    except ValueError:
        raise SystemExit("browser-harness: BH_PARAMS must be a JSON object")
    if not isinstance(params, dict):
        raise SystemExit("browser-harness: BH_PARAMS must be a JSON object")
    return params


def read_header(text):
    """(meta, body). meta is {} when the text has no saved-script header."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip() != MARKER:
        return {}, text
    meta, i = {}, 1
    while i < len(lines) and (m := _HEADER_RE.match(lines[i].rstrip("\n"))):
        meta[m[1]] = m[2]
        i += 1
    if i < len(lines) and not lines[i].strip():
        i += 1
    meta["params"] = json.loads(meta.get("params") or "{}")
    return meta, "".join(lines[i:])


def _header(host, url, params, verified_at="never"):
    return (
        f"{MARKER}\n# host: {host}\n# url: {url}\n"
        f"# params: {json.dumps(params, ensure_ascii=False)}\n# verified_at: {verified_at}\n\n"
    )


def _parse_params(items):
    params = {}
    for item in items:
        k, sep, v = item.partition("=")
        if not sep or not k.isidentifier():
            raise SystemExit(f"browser-harness: bad --param {item!r}, expected key=value")
        params[k] = v
    return params


def _parse(args, flags):
    """Tiny argv parser: positional name plus repeatable --param and single-value flags."""
    pos, opts, params = [], {}, []
    it = iter(args)
    for a in it:
        if a == "--param":
            params.append(next(it, ""))
        elif a in flags:
            opts[a] = True if flags[a] is bool else next(it, None)
            if opts[a] is None:
                raise SystemExit(f"browser-harness: {a} needs a value\n{USAGE}")
        elif a.startswith("--"):
            raise SystemExit(f"browser-harness: unknown option {a}\n{USAGE}")
        else:
            pos.append(a)
    return pos, opts, _parse_params(params)


def _redact(code, params):
    """Turn literal param values into PARAMS[...] and typed secrets into required params."""
    notes = []
    for k, v in params.items():
        pat = re.compile(r"""(?<!\w)(["'])""" + re.escape(v) + r"\1")
        code, n = pat.subn(lambda _m, k=k: f"PARAMS[{k!r}]", code)
        if not n:
            notes.append(f"param {k}: literal {v!r} not found; read PARAMS[{k!r}] in the script")
    lines, secrets = code.splitlines(keepends=True), 0
    for i, line in enumerate(lines):
        if _SECRET_LINE_RE.search(line) and (m := _LAST_LITERAL_RE.search(line.rstrip("\n"))):
            secrets += 1
            key = f"secret_{secrets}"
            params[key] = None
            lines[i] = line[: m.start(1)] + f"PARAMS[{key!r}]" + line[m.end(1):]
            notes.append(f"redacted typed secret on line {i + 1}; pass --param {key}=... when running")
    code = "".join(lines)
    scrubbed = _URL_RE.sub(lambda m: _scrub_url(m[0]), code)
    if scrubbed != code:
        notes.append("redacted credential query params in URLs")
    return scrubbed, notes


def save(args):
    pos, opts, params = _parse(args, {"--from-last": bool, "--file": str, "--host": str})
    if len(pos) != 1 or not _NAME_RE.match(pos[0]) or ("--from-last" in opts) == ("--file" in opts):
        raise SystemExit(USAGE)
    src = journal_path() if "--from-last" in opts else Path(opts["--file"]).expanduser()
    if not src.is_file():
        raise SystemExit(f"browser-harness: no script at {src}" + (" (run a script first)" if "--from-last" in opts else ""))
    old, code = read_header(src.read_text(encoding="utf-8"))
    params = {**old.get("params", {}), **params}
    url = old.get("url") or next(iter(_URL_RE.findall(code)), "")
    host = (opts.get("--host") or old.get("host") or host_of(url)).lower().removeprefix("www.")
    if not _HOST_RE.match(host):
        raise SystemExit("browser-harness: cannot infer the site from the script; pass --host example.com")
    code, notes = _redact(code, params)
    path = scripts_dir() / host / f"{pos[0]}.py"
    paths.ensure_private_dir(path.parent)
    path.write_text(_header(host, _scrub_url(url), params) + code, encoding="utf-8")
    for note in notes:
        print(f"note: {note}", file=sys.stderr)
    print(f"saved {path}")
    return 0


def resolve(ref):
    host, _, name = ref.rpartition("/")
    if not _NAME_RE.match(name) or (host and not _HOST_RE.match(host)):
        raise SystemExit(f"browser-harness: bad script name {ref!r}")
    found = [scripts_dir() / host / f"{name}.py"] if host else sorted(scripts_dir().glob(f"*/{name}.py"))
    found = [p for p in found if p.is_file()]
    if not found:
        raise SystemExit(f"browser-harness: no saved script {ref!r} (see: browser-harness scripts list)")
    if len(found) > 1:
        raise SystemExit("browser-harness: ambiguous; use one of: " + ", ".join(f"{p.parent.name}/{name}" for p in found))
    return found[0]


def prepare_run(args):
    """(path, code, params) for `scripts run`, or SystemExit on bad input."""
    pos, _, params = _parse(args, {})
    if len(pos) != 1:
        raise SystemExit(USAGE)
    path = resolve(pos[0])
    code = path.read_text(encoding="utf-8")
    params = {**read_header(code)[0].get("params", {}), **env_params(), **params}
    missing = [k for k, v in params.items() if v is None]
    if missing:
        raise SystemExit("browser-harness: missing " + " ".join(f"--param {k}=..." for k in missing))
    os.environ["BH_PARAMS"] = json.dumps(params)
    return path, code, params


def replay(path, code, g):
    """exec a saved script; 0 stamps verified_at, any failure prints `drifted:`."""
    try:
        exec(compile(code, str(path), "exec"), g)
    except SystemExit as e:
        if e.code not in (None, 0):
            return _drifted(path, f"SystemExit: {e.code}")
    except Exception as e:
        traceback.print_exc()
        return _drifted(path, f"{type(e).__name__}: {e}")
    stamp(path)
    return 0


def _drifted(path, error):
    print(f"drifted: {error}", file=sys.stderr)
    print(f"fix {path} and rerun: browser-harness scripts run {path.parent.name}/{path.stem}", file=sys.stderr)
    return 1


def stamp(path):
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    text = path.read_text(encoding="utf-8")
    path.write_text(re.sub(r"(?m)^# verified_at: .*$", f"# verified_at: {now}", text, count=1), encoding="utf-8")


def list_scripts(args):
    pos, opts, _ = _parse(args, {"--host": str})
    if pos:
        raise SystemExit(USAGE)
    host = (opts.get("--host") or "").lower().removeprefix("www.")
    rows = sorted(scripts_dir().glob(f"{host or '*'}/*.py")) if not host or _HOST_RE.match(host) else []
    for p in rows:
        meta, _ = read_header(p.read_text(encoding="utf-8"))
        print(f"{p.parent.name}/{p.stem}  params={json.dumps(meta.get('params', {}))}  verified_at={meta.get('verified_at', '?')}")
    if not rows:
        print("no saved scripts")
    return 0


def run_cli(args):
    """save/list. `scripts run` is executed by run.py so it shares the daemon + exec path."""
    if args[:1] == ["save"]:
        return save(args[1:])
    if args[:1] == ["list"]:
        return list_scripts(args[1:])
    print(USAGE, file=sys.stderr)
    return 2
