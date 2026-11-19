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

Output check: the first verified replay that prints JSON records its shape in an
`# expect:` header line (keys, types, and which values were non-empty). Later
replays fail as drifted when a key goes missing, a type changes, or a value that
was non-empty comes back null/empty, so a broken page cannot pass as a quiet
`null`. If the new output is valid, rerun with `--accept`: it keeps the new
output and relaxes the expectation to what both runs share.
"""
import ast, hashlib, io, json, os, re, sys, time, traceback
from pathlib import Path
from urllib.parse import urlparse

from . import paths
from .recorder import _scrub_url

REPLAY_IPC_TIMEOUT_SECONDS = 30.0
EXPECT_DEPTH = 4  # nesting levels recorded in `# expect:`
_CAPTURE_LIMIT = 8 << 20  # stdout bytes kept for the output check
ACCEPT_OUTPUT = False  # set by `scripts run --accept`
MARKER = "# browser-harness saved script"
_NAME_RE = re.compile(r"\A[A-Za-z0-9_-]{1,64}\Z")
_HOST_RE = re.compile(r"\A[a-z0-9-]+(\.[a-z0-9-]+)*\Z")
_HEADER_RE = re.compile(r"\A# ([a-z_]+):(?: (.*))?\Z")
_URL_RE = re.compile(r"""https?://[^\s'"{}]+""")
# Text typed by a call whose source lines smell like a credential gets swapped for a param.
_TYPING_CALLS = {"type_text", "fill_input"}
_SECRET_RE = re.compile(r"pass|secret|token|otp|api_?key", re.I)

USAGE = """usage:
  browser-harness scripts save <name> [--from-last | --file PATH] [--host HOST] [--param k=v ...]
  browser-harness scripts run <name|host/name> [--param k=v ...] [--accept]
  browser-harness scripts list [--host HOST]"""


def scripts_dir():
    return paths.workspace_dir() / "scripts"


def journal_path():
    """Last successful stdin script for this BU_NAME and working directory; `scripts save --from-last` reads it.

    Agents often share the default daemon, so the directory is part of the key: an agent working in
    another folder cannot overwrite (or save) this one's last script.
    """
    name = os.environ.get("BU_NAME", "default")
    where = hashlib.sha256(os.getcwd().encode()).hexdigest()[:12]
    return paths.runtime_dir() / f"last-script-{name if _NAME_RE.match(name) else 'default'}-{where}.py"


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
        meta[m[1]] = m[2] or ""
        i += 1
    if i < len(lines) and not lines[i].strip():
        i += 1
    for key, default in (("params", "{}"), ("expect", "null")):
        try:
            meta[key] = json.loads(meta.get(key) or default)
        except ValueError:
            raise SystemExit(f"browser-harness: bad '# {key}:' header line; it must be JSON")
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
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise SystemExit(f"browser-harness: script does not compile: {e}")
    lines = re.findall(r"[^\n]*\n|[^\n]+", code)
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))

    def span(n):  # ast columns are UTF-8 byte offsets
        at = lambda ln, col: starts[ln - 1] + len(lines[ln - 1].encode()[:col].decode())
        return at(n.lineno, n.col_offset), at(n.end_lineno, n.end_col_offset)

    # Whole string literals only: never rewrite text inside another string or an f-string.
    in_fstring = {id(c) for j in ast.walk(tree) if isinstance(j, ast.JoinedStr) for c in ast.walk(j)}
    strings = [n for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in in_fstring]
    edits, notes = {}, []
    for k, v in params.items():
        if v is None:  # a required secret from an earlier save
            continue
        hits = [n for n in strings if n.value == v]
        edits.update({span(n): f"PARAMS[{k!r}]" for n in hits})
        if not hits:
            notes.append(f"param {k}: its value is not a whole string literal in the script; read PARAMS[{k!r}] there")
    calls = sorted(
        (n for n in ast.walk(tree) if isinstance(n, ast.Call)
         and getattr(n.func, "id", getattr(n.func, "attr", None)) in _TYPING_CALLS),
        key=lambda n: (n.lineno, n.col_offset),
    )
    for call in calls:
        text = call.args[-1] if call.args else next((kw.value for kw in call.keywords if kw.arg == "text"), None)
        source = "".join(lines[call.lineno - 1 : call.end_lineno])  # includes a trailing comment
        if text in strings and _SECRET_RE.search(source):
            key = next(f"secret_{i}" for i in range(1, len(params) + 2) if f"secret_{i}" not in params)
            params[key] = None
            edits[span(text)] = f"PARAMS[{key!r}]"
            notes.append(f"redacted typed secret on line {call.lineno}; pass --param {key}=... when running")
    for (a, b), new in sorted(edits.items(), reverse=True):
        code = code[:a] + new + code[b:]
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
    global ACCEPT_OUTPUT
    pos, opts, params = _parse(args, {"--accept": bool})
    if len(pos) != 1:
        raise SystemExit(USAGE)
    ACCEPT_OUTPUT = "--accept" in opts
    path = resolve(pos[0])
    code = path.read_text(encoding="utf-8")
    params = {**read_header(code)[0].get("params", {}), **env_params(), **params}
    missing = [k for k, v in params.items() if v is None]
    if missing:
        raise SystemExit("browser-harness: missing " + " ".join(f"--param {k}=..." for k in missing))
    os.environ["BH_PARAMS"] = json.dumps(params)
    return path, code, params


class _Tee(io.TextIOBase):
    """Pass stdout through and keep a bounded copy for the output check."""

    def __init__(self, out):
        self.out, self.buf, self.size = out, [], 0

    def write(self, text):
        if self.size < _CAPTURE_LIMIT:
            self.buf.append(text)
            self.size += len(text)
        return self.out.write(text)

    def flush(self):
        self.out.flush()


def json_output(text):
    """The JSON object or array a script printed: all of stdout, else its last JSON line."""
    text = text.strip()
    for chunk in [text, *reversed(text.splitlines())]:
        chunk = chunk.strip()
        if chunk[:1] in ("{", "["):
            try:
                value = json.loads(chunk)
            except ValueError:
                continue
            if isinstance(value, (dict, list)):
                return value
    return None


def _empty(v):
    return v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, (list, dict)) and not v)


def shape(v, depth=0):
    """Compact record of a JSON value: type, whether it was non-empty, and nested keys/items."""
    t = ("null" if v is None else "bool" if isinstance(v, bool) else "num" if isinstance(v, (int, float))
         else "str" if isinstance(v, str) else "list" if isinstance(v, list) else "obj")
    s = {"t": t}
    if t in ("str", "list", "obj") and not _empty(v):
        s["full"] = 1
    if depth < EXPECT_DEPTH:
        if t == "obj":
            s["keys"] = {k: shape(x, depth + 1) for k, x in v.items()}
        elif t == "list" and v:
            s["item"] = shape(v[0], depth + 1)
    return s


def check_output(expect, v, path="output"):
    """Problems where v breaks the recorded shape. New keys and longer/shorter lists are fine."""
    t = expect.get("t")
    if t == "null":  # it was empty when recorded; nothing to hold it to
        return []
    if v is None:
        return [f"{path} is null, was {t}"]
    if shape(v, EXPECT_DEPTH)["t"] != t:
        return [f"{path} is {shape(v, EXPECT_DEPTH)['t']}, was {t}"]
    if expect.get("full") and _empty(v):
        return [f"{path} is empty"]
    problems = []
    if t == "obj":
        for k, sub in expect.get("keys", {}).items():
            problems += [f"{path}.{k} is missing"] if k not in v else check_output(sub, v[k], f"{path}.{k}")
    elif t == "list" and "item" in expect:
        for i, x in enumerate(v[:200]):
            problems += check_output(expect["item"], x, f"{path}[{i}]")
            if len(problems) >= 5:
                break
    return problems


def merge_shapes(old, new):
    """What two accepted outputs share: a value stays required only if both had it non-empty."""
    if old.get("t") == "null":
        return new
    if new.get("t") == "null" or new.get("t") != old.get("t"):
        return {"t": "null"}  # empty or retyped now: accept anything there
    out = {"t": old["t"]}
    if old.get("full") and new.get("full"):
        out["full"] = 1
    if "keys" in old and "keys" in new:
        out["keys"] = {k: merge_shapes(v, new["keys"][k]) for k, v in old["keys"].items() if k in new["keys"]}
    if "item" in old and "item" in new:
        out["item"] = merge_shapes(old["item"], new["item"])
    elif "item" in old and old.get("t") == "list":
        out["item"] = old["item"]
    return out


def replay(path, code, g):
    """exec a saved script; 0 stamps verified_at, any failure prints `drifted:`."""
    tee, real = _Tee(sys.stdout), sys.stdout
    sys.stdout = tee
    try:
        exec(compile(code, str(path), "exec"), g)
    except SystemExit as e:
        if e.code not in (None, 0):
            return _drifted(path, f"SystemExit: {e.code}")
    except Exception as e:
        traceback.print_exc()
        return _drifted(path, f"{type(e).__name__}: {e}")
    finally:
        sys.stdout = real
    expect = read_header(code)[0].get("expect")
    out = json_output("".join(tee.buf))
    record = shape(out) if expect is None and out is not None else None
    if expect is not None:
        problems = check_output(expect, out) if out is not None else ["no JSON output, the script used to print JSON"]
        if problems and not ACCEPT_OUTPUT:
            return _drifted(path, "output changed: " + "; ".join(problems[:5]),
                            "if this output is correct, accept it: browser-harness scripts run ... --accept")
        if problems:
            record = merge_shapes(expect, shape(out)) if out is not None else "drop"
            print("accepted: output check now allows: " + "; ".join(problems[:5]), file=sys.stderr)
    stamp(path, record)
    return 0


def _drifted(path, error, hint=""):
    print(f"drifted: {error}", file=sys.stderr)
    if hint:
        print(hint, file=sys.stderr)
    print(f"fix {path} and rerun: browser-harness scripts run {path.parent.name}/{path.stem}", file=sys.stderr)
    return 1


def stamp(path, expect=None):
    """Mark the script verified now; write or replace `# expect:` when given ("drop" removes it)."""
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    line = f"# verified_at: {now}"
    text = path.read_text(encoding="utf-8")
    if expect is not None:
        text = re.sub(r"(?m)^# expect: .*\n", "", text, count=1)
        if expect != "drop":
            line += "\n# expect: " + json.dumps(expect, separators=(",", ":"), ensure_ascii=False)
    path.write_text(re.sub(r"(?m)^# verified_at: .*$", lambda m: line, text, count=1), encoding="utf-8")


def list_scripts(args):
    pos, opts, _ = _parse(args, {"--host": str})
    if pos:
        raise SystemExit(USAGE)
    host = (opts.get("--host") or "").lower().removeprefix("www.")
    rows = sorted(scripts_dir().glob(f"{host or '*'}/*.py")) if not host or _HOST_RE.match(host) else []
    for p in rows:
        meta, _ = read_header(p.read_text(encoding="utf-8"))
        check = "on" if meta.get("expect") is not None else "after first run"
        print(f"{p.parent.name}/{p.stem}  params={json.dumps(meta.get('params', {}))}  verified_at={meta.get('verified_at', '?')}  output_check={check}")
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
