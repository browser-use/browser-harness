"""library_judgement and library_feedback: the calling agent's verdict on its run, and what went wrong with
browser-harness itself, sent to the Browser Use library PostHog project (not the harness project in telemetry.py).

Consent: feedback is for everyone, run reports only with telemetry on.
- library_feedback (report_issue(), `browser-harness feedback`, the MCP browser_feedback tool) sends even when usage
  telemetry is off: someone chose to write it. At most 3 per hour per BU_NAME from the CLI, 3 per MCP server process.
- library_judgement (report_run(), the MCP browser_report_run tool) sends only when usage telemetry is on (BH_TELEMETRY,
  BROWSER_HARNESS_TELEMETRY, ANONYMIZED_TELEMETRY and `browser-harness telemetry disable` all off it). Same caps.
- BROWSER_USE_OFFLINE=1 sends nothing at all. BROWSER_USE_ZDR=1 sends both events without their texts.
Every text is scrubbed (scrub) before it leaves: secrets, credentials, emails, URL queries, home folders. With telemetry
off an event goes under a random per-process id, never the stored install id. Neither event is ever routed through
telemetry.set_sink(): they go to the library project with its own key."""

from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone

from . import paths, telemetry
from .naming import named

LIBRARY_POSTHOG_KEY = "phc_F8JMNjW1i2KbGUTaW1unnDdLSPCoyc52SGRU0JecaUh"  # browser_use/telemetry/service.py
LIBRARY_POSTHOG_HOST = "https://eu.i.posthog.com"
CATEGORIES = ("bug", "docs", "missing", "other")
MAX_TEXT = 300  # failure_reason, description, each gotcha
MAX_MESSAGE = 2000  # feedback message
MAX_GOTCHAS = 5
MAX_PER_HOUR = 3  # report_run / report_issue per daemon name per hour (each CLI call is its own process)
MAX_PER_PROCESS = 3  # per MCP server process
WINDOW_S = 3600

SENT_RUN = "Run reported to the Browser Use team. Thanks."
SENT_ISSUE = "Reported to the Browser Use team. Thanks; carry on."
OFF = "Telemetry is off (BH_TELEMETRY=0, ANONYMIZED_TELEMETRY=false or `browser-harness telemetry disable`): the run report was not sent. Feedback still sends."
OFFLINE = "BROWSER_USE_OFFLINE=1: nothing was sent."
CAPPED = "Already reported 3 times (the limit): nothing more was sent."

_PROCESS_ID = uuid.uuid4().hex  # telemetry off: the user's own feedback goes under this, never the stored install id

# --- scrub: a minimal port of browser_use/telemetry/stats.py scrub() (no task or typed text: the harness has neither) ---

EMAIL = re.compile(r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+(?:@|%40)[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
KEYS = re.compile(
    r"(?<![A-Za-z0-9])(?:sk-ant-|sk-|sk_|rk_|bu_|gsk_|xai-|hf_|ghp_|gho_|ghs_|ghu_|github_pat_|glpat-|xox[abpr]-|nvapi-"
    r"|pplx-|r8_|phc_)[A-Za-z0-9_-]{8,}"
    r"|(?<![A-Za-z0-9])(?:AKIA|ASIA)[0-9A-Z]{16}(?![A-Za-z0-9])"
    r"|AIza[A-Za-z0-9_-]{20,}|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]*)?"
    r"|(?<![A-Za-z0-9])(?=[A-Za-z]*[0-9])(?=[0-9]*[A-Za-z])[A-Za-z0-9]{32,}"
)
BEARER = re.compile(r"\b([Bb]earer|[Bb]asic|BEARER|BASIC)(\s+)(?=\S*(?:\d|[a-z]\S*[A-Z]))[A-Za-z0-9._~+/=-]{8,}")
AUTHORIZATION = re.compile(r"(?i)(?<![a-z])(authorization[\"']?\s*[=:]\s*[\"']?(?:bearer|basic)\s+)[^\s\"'<>,;]+")
ASSIGNED = re.compile(
    r"(?i)(?<![a-z<])(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|authorization)"
    r"([\"']?\s*[=:]\s*)(?!(?:bearer|basic)\s)(\"[^\"]*\"|'[^']*'|[^\s&,;]+(?:&(?![A-Za-z_][\w.-]*=)[^\s&,;]*)*)"
)
COOKIE = re.compile(r"(?im)(?<![a-z])((?:set-)?cookie[\"']?\s*[=:]\s*)[^\r\n]+")
TAG = r"<[a-z]+(?::[^\s<>]*)?>"
URL = re.compile(
    rf"(?i)\b([a-z][a-z0-9+.-]{{0,30}}://)((?:[^\s/?#@<>\"'`]|{TAG})*@)?((?:[^\s;?#<>\"'`]|{TAG})*)"
    rf"(?:[;?#](?:[^\s<>\"'`]|{TAG})*)?"
)
QUERY = re.compile(r"(/[^\s?#<>\"'`]*)\?[^\s<>\"'`]+")
UUID = re.compile(r"(?i)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
TOKEN = re.compile(r"(?<![A-Za-z0-9])(?=[A-Za-z]*[0-9])(?=[0-9]*[A-Za-z])[A-Za-z0-9]{12,}")
GRANTS = re.compile(
    r"(?i)(?<![a-z])(?:reset|invite|invitation|magic|confirm|confirmation|verify|verification|token|tokens|activate"
    r"|activation|unsubscribe|password)(?![a-z])"
)
NUMBER = re.compile(r"(?<!\d)\+?\d(?:[ ()-]{0,2}\d){5,}(?!\d)")
EXPRESSION = re.compile(r"; expression: .*", re.S)  # js() errors quote the agent's code
HOME = re.compile(r"(?i)((?:(?<=file://)|(?<![\w./-]))(?:/Users/|/home/)|(?<!\w)[a-z]:\\{1,2}Users\\{1,2})[^/\\\s'\"<>`:]+")
ENV_SECRET = re.compile(r"(?i)(?:key|token|secret|password|passwd|credentials?)$")


HOSTNAME = re.compile(r"(?:[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?\.)*[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?")
HOST_SCHEMES = ("http://", "https://", "ws://", "wss://")
# Hostnames that alone open something private (a tunnel to the developer's machine, a cloud IDE's port, a Lambda function
# URL, a preview deploy): sent as '*.' + their provider, as stats.capability_host. A production myapp.vercel.app is kept.
CAPABILITY_SUFFIXES = (
    "trycloudflare.com",
    "ngrok-free.app",
    "ngrok-free.dev",
    "ngrok.io",
    "ngrok.app",
    "ngrok.dev",
    "loca.lt",
    "devtunnels.ms",
    "app.github.dev",
    "github.dev",
    "gitpod.io",
    "repl.co",
    "replit.dev",
    "csb.app",
)
PREVIEW_HOSTS = {"vercel.app": re.compile(r".+-(?:git-|[a-z0-9]{9}-).+"), "netlify.app": re.compile(r".+--.+")}
LAMBDA_URL = re.compile(r".+\.lambda-url\.([a-z0-9-]+)\.on\.aws")


def capability_host(hostname: str) -> str:
    """A hostname as sent: a tunnel, cloud IDE, Lambda function URL or preview deploy as '*.' + its provider's domain."""
    for suffix in CAPABILITY_SUFFIXES:
        if hostname.endswith("." + suffix):
            return "*." + suffix
    if m := LAMBDA_URL.fullmatch(hostname):
        return f"*.lambda-url.{m[1]}.on.aws"
    label, _, rest = hostname.partition(".")
    if (preview := PREVIEW_HOSTS.get(rest)) and preview.fullmatch(label):
        return "*." + rest
    return hostname


def _url(m: re.Match) -> str:
    """A URL without its user:password@ (as <credential>@), port, query and fragment; an http(s)/ws(s) hostname
    lowercased, a tunnel or preview deploy as its provider (capability_host); its path's tokens as <token>."""
    authority, sep, path = m[3].partition("/")
    authority = re.sub(r":\d+$", "", authority)
    if m[1].lower() in HOST_SCHEMES and HOSTNAME.fullmatch(authority.lower().rstrip(".")):
        authority = capability_host(authority.lower().rstrip("."))
    segments, granted = path.split("/"), False
    for i, segment in enumerate(segments):
        if not segment or "<" in segment:
            continue
        if granted or UUID.search(segment) or TOKEN.search(segment):
            segments[i] = "<token>"
        granted = granted or bool(GRANTS.search(segment))
    return m[1] + ("<credential>@" if m[2] else "") + authority + sep + "/".join(segments)


def scrub(text, limit: int) -> str:
    """Text as sent: this process's *_KEY/*_TOKEN/... env values, API keys, bearer tokens, cookies and password=...
    as <credential>; URLs without credentials, port, query or fragment, path tokens as <token>; home folders' user as
    <user>; emails as <email>; runs of 6+ digits as <number>; js() expressions as <code>; then cut to limit."""
    if text is None:
        return ""
    out = str(text)[: 64 * limit + 64]  # what is cut here ends far past what is sent
    for value in sorted(
        {v for k, v in os.environ.items() if ENV_SECRET.search(k) and len(v) >= 12 and k not in ("PWD", "OLDPWD")},
        key=len,
        reverse=True,
    ):
        out = out.replace(value, "<credential>")
    out = EXPRESSION.sub("; expression: <code>", out)
    out = URL.sub(_url, out)
    out = QUERY.sub(r"\1", out)
    home = os.path.expanduser("~").rstrip("/\\")
    if len(home) > 1 and not HOME.fullmatch(home):
        out = re.sub(rf"(?:(?<=file://)|(?<![\w./-])){re.escape(home)}(?![^/\\\s'\"<>`:])", "~", out)
    out = HOME.sub(lambda m: m[1] + "<user>", out)
    out = BEARER.sub(lambda m: m[1] + m[2] + "<credential>", out)
    out = AUTHORIZATION.sub(lambda m: m[1] + "<credential>", out)
    out = COOKIE.sub(lambda m: m[1] + "<credential>", out)
    out = ASSIGNED.sub(lambda m: m[1] + m[2] + "<credential>", out)
    out = NUMBER.sub("<number>", EMAIL.sub("<email>", KEYS.sub("<credential>", out)))
    return out.strip()[:limit]


# --- switches, caps, sending ---


def _on(name: str) -> bool:
    """As browser-use's config reads BROWSER_USE_OFFLINE/ZDR: 1, t..., y... (and on)."""
    value = (os.environ.get(name) or "").strip().lower()
    return value[:1] in ("t", "y", "1") or value == "on"


def _stats_on() -> bool:
    """browser-harness telemetry on, and ANONYMIZED_TELEMETRY on as browser-use reads it (set: on only for 1, t..., y...;
    browser-harness alone keeps 'false ', 'n' or '' on)."""
    raw = os.environ.get("ANONYMIZED_TELEMETRY")
    if raw is not None and raw.strip().lower()[:1] not in ("t", "y", "1"):
        return False
    return telemetry.is_enabled()


def _blocked(event: str) -> str | None:
    """Why `event` may not be sent, or None: OFFLINE stops both; telemetry off stops only library_judgement."""
    if _on("BROWSER_USE_OFFLINE"):
        return named(OFFLINE)
    if event == "library_judgement" and not _stats_on():
        return named(OFF)
    return None


def _counts_path():
    return paths.runtime_dir() / "reports.json"


def _hour_cap(kind: str) -> bool:
    """True when this daemon name may send one more `kind` this hour; records it. Best effort: the file is shared by
    the CLI's processes; when it cannot be read or written, this process's own count still holds."""
    key = f"{os.environ.get('BU_NAME', 'default')}:{kind}"
    now = time.time()
    try:
        data = json.loads(_counts_path().read_text(encoding="utf-8"))
        data = data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        data = {}
    stored = data.get(key) if isinstance(data.get(key), list) else []
    seen = {t for t in [*stored, *_process_sent.get(key, [])] if isinstance(t, int | float) and 0 <= now - t < WINDOW_S}
    if len(seen) >= MAX_PER_HOUR:
        return False
    data[key] = sorted(seen | {now})
    _process_sent.setdefault(key, []).append(now)
    try:
        _counts_path().write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass
    return True


_process_sent: dict[str, list[float]] = {}


def _send(event: str, properties: dict) -> None:
    """One event to the library project, handed to telemetry's detached sender (the caller never blocks)."""
    payload = {
        "api_key": LIBRARY_POSTHOG_KEY,
        "event": event,
        "distinct_id": telemetry._install_id() if _stats_on() else _PROCESS_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "properties": {
            **properties,
            "$lib": "browser-harness",
            "$lib_version": telemetry._version() or "unknown",
            "$process_person_profile": False,
        },
    }
    try:
        telemetry.post_detached(payload, LIBRARY_POSTHOG_HOST)
    except Exception:
        pass


def _client() -> dict:
    """The CLI or server that embeds the harness (BH_CLIENT, as cli_event): browser-use's CLI and --cli-mcp set
    browser-use-cli / browser-use-mcp, so their events are not counted as plain harness ones."""
    return {
        "client": (os.environ.get("BH_CLIENT") or "")[:80] or None,
        "client_version": (os.environ.get("BH_CLIENT_VERSION") or "")[:80] or None,
    }


def judgement_properties(surface, success, failure_reason=None, gotchas=(), bot_block=False, description="") -> dict:
    """library_judgement's properties (judgement-event-spec.md), texts scrubbed, or empty under BROWSER_USE_ZDR=1."""
    if isinstance(gotchas, str):
        gotchas = [gotchas]
    withheld = _on("BROWSER_USE_ZDR")
    clean = [g for g in (scrub(g, MAX_TEXT) for g in list(gotchas or ())[:MAX_GOTCHAS]) if g]
    return {
        "surface": surface,
        "judge_source": "self",
        "version": telemetry._version() or "unknown",
        "run_id": None,
        "model": None,
        "success": success,
        "failure_reason": None if withheld else (scrub(failure_reason, MAX_TEXT) or None),
        "description": "" if withheld else scrub(description, MAX_TEXT),
        "prompt_injection_detected": False,
        "bot_block_or_captcha_detected": bool(bot_block),
        "gotchas": [] if withheld else clean,
        "hosts": [],  # the daemon keeps no visited-host list
        "cost_usd": None,
        "texts_withheld": withheld,
        "is_internal": _on("BROWSER_USE_TELEMETRY_INTERNAL"),  # as browser-use's LibraryJudgementEvent
        "schema_version": 1,
        **_client(),
    }


def feedback_properties(source, message, category="bug") -> dict:
    """library_feedback's properties, the message scrubbed, or withheld under BROWSER_USE_ZDR=1."""
    withheld = _on("BROWSER_USE_ZDR")
    return {
        "version": telemetry._version() or "unknown",
        "source": source,
        "message": "" if withheld else scrub(message, MAX_MESSAGE),
        "texts_withheld": withheld,
        "category": category if category in CATEGORIES else "other",
        "is_internal": _on("BROWSER_USE_TELEMETRY_INTERNAL"),
        "model": None,
        "run_id": None,
        "step": None,
        "last_error_type": None,
        **_client(),
    }


def send_judgement(surface, success, failure_reason=None, gotchas=(), bot_block=False, description="", cap=None) -> str:
    """Validate, gate and send one library_judgement; cap(): False when over the caller's limit. Returns what happened."""
    if not isinstance(success, bool):
        return "Error: success must be True or False: nothing was sent."
    if blocked := _blocked("library_judgement"):
        return blocked
    if cap is not None and not cap():
        return CAPPED
    _send("library_judgement", judgement_properties(surface, success, failure_reason, gotchas, bot_block, description))
    return SENT_RUN


def send_feedback(source, message, category="bug", cap=None) -> str:
    """Validate, gate and send one library_feedback (also with telemetry off). Returns what happened."""
    if not isinstance(message, str) or not message.strip():
        return "Error: message must be a non-empty string: nothing was sent."
    if blocked := _blocked("library_feedback"):
        return blocked
    if cap is not None and not cap():
        return CAPPED
    _send("library_feedback", feedback_properties(source, message, category))
    return SENT_ISSUE


# --- helpers (pre-imported in the CLI's scripts) ---


def report_run(success: bool, failure_reason: str | None = None, gotchas=(), bot_block: bool = False, description: str = "") -> str:
    """Report your own run once, at the end (or when you give up): honest success, the failure reason, up to 5 gotchas
    about the sites (what you observed, not guesses; no emails, names, account data, credentials or the task's
    values), bot_block=True if a bot wall or captcha blocked you. Sends nothing when telemetry is off; at most 3 per
    hour per BU_NAME. Returns what happened."""
    return send_judgement("harness-cli", success, failure_reason, gotchas, bot_block, description, cap=lambda: _hour_cap("run"))


def report_issue(message: str, category: str = "bug") -> str:
    """Tell the Browser Use team what went wrong with browser-harness itself (a helper that failed, wrong docs, a
    missing helper), not ordinary website problems. category: bug, docs, missing or other. Never include secrets or
    personal data. Sends also when telemetry is off (only BROWSER_USE_OFFLINE=1 stops it); at most 3 per hour per
    BU_NAME, shared with `browser-harness feedback`."""
    return send_feedback("harness-cli", message, category, cap=lambda: _hour_cap("feedback"))


# --- `browser-harness feedback "<msg>"`: sent even with telemetry off ---

FEEDBACK_USAGE = 'usage: browser-harness feedback "what happened" [--category bug|docs|missing|other]'


def run_feedback_cli(argv: list[str]) -> int:
    words, category, i = [], "bug", 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--category" and i + 1 < len(argv):
            category, i = argv[i + 1], i + 2
            continue
        if arg.startswith("--category="):
            category, i = arg.split("=", 1)[1], i + 1
            continue
        if arg in {"-h", "--help"}:
            print(named(FEEDBACK_USAGE))
            return 0
        words.append(arg)
        i += 1
    if category not in CATEGORIES:
        print(named(FEEDBACK_USAGE), file=sys.stderr)
        return 2
    text = " ".join(words) or ("" if sys.stdin.isatty() else sys.stdin.read())
    if not text.strip():
        print(named(FEEDBACK_USAGE), file=sys.stderr)
        return 2
    result = send_feedback("harness-cli", text, category, cap=lambda: _hour_cap("feedback"))
    if result != SENT_ISSUE:
        print(result, file=sys.stderr)
        return 1
    print("Sending your feedback to the Browser Use team in the background. Thanks!")
    return 0
