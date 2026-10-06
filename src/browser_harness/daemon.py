"""CDP WS holder + IPC relay (Unix socket on POSIX, TCP loopback on Windows). One daemon per BU_NAME."""
import asyncio, json, os, platform, socket, sys, time, urllib.error, urllib.request
from urllib.parse import urlparse
from collections import deque
from pathlib import Path

from . import _ipc as ipc
from . import auth
from . import paths
from cdp_use.client import CDPClient


def _load_env():
    repo_root = Path(__file__).resolve().parents[2]
    workspace = paths.workspace_dir()
    for p in (repo_root / ".env", workspace / ".env"):
        if not p.exists():
            continue
        _load_env_file(p)


def _load_env_file(p):
    for line in p.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

NAME = os.environ.get("BU_NAME", "default")
SOCK = ipc.sock_addr(NAME)
LOG = str(ipc.log_path(NAME))
PID = str(ipc.pid_path(NAME))
BUF = 500
MAX_OVERFLOW_CLEANUP_RETRIES = 256
_MAC_PROFILES = (
    "Library/Application Support/Google/Chrome",
    "Library/Application Support/Google/Chrome Canary",
    "Library/Application Support/Comet",
    "Library/Application Support/Arc/User Data",
    "Library/Application Support/Dia/User Data",
    "Library/Application Support/Microsoft Edge",
    "Library/Application Support/Microsoft Edge Beta",
    "Library/Application Support/Microsoft Edge Dev",
    "Library/Application Support/Microsoft Edge Canary",
    "Library/Application Support/BraveSoftware/Brave-Browser",
    "Library/Application Support/BraveSoftware/Brave-Origin",
)
_LINUX_PROFILES = (
    ".config/google-chrome",
    ".config/chromium",
    ".config/chromium-browser",
    ".config/microsoft-edge",
    ".config/microsoft-edge-beta",
    ".config/microsoft-edge-dev",
    ".var/app/org.chromium.Chromium/config/chromium",
    ".var/app/com.google.Chrome/config/google-chrome",
    ".var/app/com.brave.Browser/config/BraveSoftware/Brave-Browser",
    ".var/app/com.microsoft.Edge/config/microsoft-edge",
)
_WINDOWS_PROFILES = (  # relative to %LOCALAPPDATA%; SxS = Canary channel
    "Google/Chrome/User Data",
    "Google/Chrome SxS/User Data",
    "Google/Chrome Beta/User Data",
    "Google/Chrome Dev/User Data",
    "Chromium/User Data",
    "Microsoft/Edge/User Data",
    "Microsoft/Edge Beta/User Data",
    "Microsoft/Edge Dev/User Data",
    "Microsoft/Edge SxS/User Data",
    "BraveSoftware/Brave-Browser/User Data",
)


def _publish_own_pid(path=PID, pid=None):
    """Atomically retain or publish this daemon's PID record.

    The parent may already have published a process-start fingerprint while
    holding the spawn lock. Never truncate that record: another cold caller
    must not observe an empty PID file and start a sibling daemon.
    """
    pid = pid or os.getpid()
    target = Path(path)
    try:
        published = target.read_text()
        try:
            published_pid = int(json.loads(published)["pid"])
        except (json.JSONDecodeError, TypeError, KeyError):
            published_pid = int(published.split()[0])
    except (FileNotFoundError, OSError, ValueError, IndexError):
        published = str(pid)
        published_pid = pid
    if published_pid != pid:
        published = str(pid)
    tmp = target.with_name(f"{target.name}.{pid}.tmp")
    tmp.write_text(published)
    os.replace(tmp, target)


def profile_dirs(system=None):
    system = system or platform.system()
    if system == "Windows":
        local = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local")
        return [local / p for p in _WINDOWS_PROFILES]
    if system == "Darwin":
        return [Path.home() / p for p in _MAC_PROFILES]
    return [Path.home() / p for p in _LINUX_PROFILES]


PROFILES = profile_dirs()
INTERNAL = ("chrome://", "chrome-untrusted://", "devtools://", "chrome-extension://", "about:")
BU_API = "https://api.browser-use.com/api/v3"
REMOTE_ID = os.environ.get("BU_BROWSER_ID")
_REMOTE_STOPPED = False
BROWSER_KIND = "cloud" if REMOTE_ID else ("cdp" if (os.environ.get("BU_CDP_WS") or os.environ.get("BU_CDP_URL")) else "local")
# Chrome 144+ shows a per-connection popup, and the connection that raised it is
# the only thing keeping it on screen. There is deliberately no approval
# deadline: expiry would drop the sheet and make a later attempt create another
# connection and another prompt. Chrome/process death and explicit cancellation
# still terminate the pending connection.
LOCAL_HANDSHAKE_TIMEOUT = None
# How long get_ws_url() keeps waiting for DevToolsActivePort before giving up
NO_TOGGLE_GRACE = 3
TOGGLE_BOOT_GRACE = 12
# Cancellation should make an in-flight CDP call finish immediately. Keep the
# drain bounded anyway so shutdown fails closed if a client ignores cancellation.
RECOVERY_CANCEL_DRAIN_TIMEOUT = 2
TAB_MARKER_JS = "if(!document.title.startsWith('\U0001F434'))document.title='\U0001F434 '+document.title"
_NETWORK_REQUEST_METHOD = "Network.requestWillBeSent"
_NETWORK_REQUEST_CORRELATED_METHODS = frozenset({
    "Network.requestWillBeSentExtraInfo",
    "Network.responseReceived",
    "Network.responseReceivedExtraInfo",
    "Network.dataReceived",
    "Network.loadingFinished",
    "Network.loadingFailed",
    "Network.requestServedFromCache",
    "Network.resourceChangedPriority",
    "Network.signedExchangeReceived",
    "Network.webSocketCreated",
    "Network.webSocketWillSendHandshakeRequest",
    "Network.webSocketHandshakeResponseReceived",
    "Network.webSocketFrameSent",
    "Network.webSocketFrameReceived",
    "Network.webSocketFrameError",
    "Network.webSocketClosed",
    "Network.eventSourceMessageReceived",
})
_GUARDED_PAGE_EVENT_METHODS = frozenset({
    "Page.frameNavigated",
    "Page.navigatedWithinDocument",
    "Page.loadEventFired",
    "Page.domContentEventFired",
    "Page.javascriptDialogOpening",
    "Page.javascriptDialogClosed",
})
_GUARDED_RESPONSE_METHOD = "Target.receivedMessageFromTarget"
_GUARDED_SESSION_METHODS = frozenset({
    "DOM.getDocument", "DOM.querySelector", "DOM.querySelectorAll", "DOM.setFileInputFiles",
    "Emulation.setEmulatedMedia", "Emulation.setFocusEmulationEnabled",
    "Input.dispatchKeyEvent", "Input.dispatchMouseEvent", "Input.insertText",
    "Network.disable", "Network.enable", "Network.setBlockedURLs",
    "Network.setBypassServiceWorker", "Network.setCacheDisabled",
    "Network.setExtraHTTPHeaders", "Network.setUserAgentOverride",
    "Page.bringToFront", "Page.reload", "Page.captureScreenshot", "Page.getFrameTree",
    "Page.handleJavaScriptDialog", "Page.navigate", "Page.setDocumentContent",
    "Runtime.evaluate",
})
_GUARDED_TARGET_METHODS = frozenset({
    "Target.getTargets", "Target.createTarget", "Target.getTargetInfo",
    "Target.attachToTarget", "Target.detachFromTarget", "Target.sendMessageToTarget",
    "Target.closeTarget", "Target.activateTarget", "Target.createBrowserContext",
})


def _guard_refusal(reason, **details):
    """Machine-readable daemon refusal; helpers expose this as TabGuardRefused."""
    return {"tab_guard": "refused", "error": reason, **details}


def tab_marker_enabled():
    """Whether the cosmetic controlled-tab title marker should be added."""
    return os.environ.get("BH_TAB_MARKER", "").strip().lower() not in {"0", "false", "no", "off"}


def _devtools_port_live(base):
    """True when something is listening on the profile's DevToolsActivePort port.

    A stale file left behind by a closed browser must not count as a running
    instance — it would route recovery to "click Allow" on a popup that can't
    exist."""
    try:
        port = int((base / "DevToolsActivePort").read_text(encoding="utf-8", errors="replace").splitlines()[0].strip())
    except (OSError, ValueError, IndexError):
        return False
    try:
        socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
        return True
    except OSError:
        return False


def remote_debugging_user_enabled():
    """chrome://inspect's "Allow remote debugging" toggle

    True only when a toggle-on profile also has a live DevTools port.
    False if a profile records it off, None when no profile records it."""
    seen = None
    for base in PROFILES:
        try:
            state = json.loads((base / "Local State").read_text(encoding="utf-8", errors="replace"))
            enabled = ((state.get("devtools") or {}).get("remote_debugging") or {}).get("user-enabled")
        except (OSError, ValueError, AttributeError):
            continue
        if enabled is True and _devtools_port_live(base):
            return True
        if enabled is False:
            seen = False
    return seen


def remote_debugging_toggle_profiles():
    """Profile dirs whose chrome://inspect toggle is recorded on in Local State"""
    out = []
    for base in PROFILES:
        try:
            state = json.loads((base / "Local State").read_text(encoding="utf-8", errors="replace"))
            if ((state.get("devtools") or {}).get("remote_debugging") or {}).get("user-enabled") is True:
                out.append(base)
        except (OSError, ValueError, AttributeError):
            continue
    return out


def browser_running_for_profile(base):
    """True when a running browser instance holds this user-data-dir (POSIX)"""
    try:
        target = os.readlink(str(base / "SingletonLock"))
    except OSError:
        return False
    try:
        pid = int(target.rsplit("-", 1)[-1])
    except ValueError:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except OSError:
        return True  # pid exists but belongs to another user


def supported_browser_running():
    """Is any browser whose profile we scan actually running?"""
    if platform.system() == "Windows":
        # Chromium on Windows uses a named mutex instead of SingletonLock —
        import subprocess
        try:
            out = subprocess.check_output(["tasklist"], text=True, errors="replace", timeout=5).lower()
        except Exception:
            return True  # can't tell — assume running so recovery stays on the popup/toggle path
        return any(n in out for n in ("chrome.exe", "msedge.exe", "chromium.exe", "brave.exe", "helium.exe"))
    return any(browser_running_for_profile(base) for base in PROFILES)


def log(msg):
    with open(LOG, "a", encoding="utf-8", errors="replace") as stream:
        stream.write(f"{msg}\n")


def _safe_connection_label(url):
    """Log only endpoint topology, never CDP credentials or provider session paths."""
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.hostname:
            return "<redacted-cdp-endpoint>"
        host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
        port = f":{parsed.port}" if parsed.port else ""
        return f"{parsed.scheme}://{host}{port}"
    except (TypeError, ValueError):
        return "<redacted-cdp-endpoint>"


async def _silent(coro):
    try:
        await coro
    except Exception:
        pass


def _ws_from_devtools_active_port(http_url: str) -> str | None:
    """When /json/version returns 404 (Chrome 147+ default profile), match DevToolsActivePort by port."""
    p = urlparse(http_url)
    want_port = str(p.port) if p.port else ""
    if not want_port:
        return None
    host = p.hostname or "127.0.0.1"
    if ":" in host:  # urlparse strips IPv6 brackets; restore them for the ws:// URL
        host = f"[{host}]"
    for base in PROFILES:
        try:
            active = (base / "DevToolsActivePort").read_text(encoding="utf-8", errors="replace").splitlines()
        except (FileNotFoundError, NotADirectoryError):
            continue
        port = active[0].strip() if active else ""
        ws_path = active[1].strip() if len(active) > 1 else ""
        if port == want_port and ws_path:
            return f"ws://{host}:{port}{ws_path}"
    return None


def get_ws_url():
    if url := os.environ.get("BU_CDP_WS"):
        return url
    if url := os.environ.get("BU_CDP_URL"):
        # HTTP DevTools endpoint (e.g. http://127.0.0.1:9333) — resolve to ws via /json/version.
        # Use this for a dedicated automation Chrome on a non-default profile, which avoids the
        # M144 "Allow remote debugging" dialog and the M136 default-profile lockdown.
        deadline = time.time() + 30
        last_err = None
        base_url = url.rstrip("/")
        while time.time() < deadline:
            try:
                return json.loads(urllib.request.urlopen(f"{base_url}/json/version", timeout=5).read())["webSocketDebuggerUrl"]
            except urllib.error.HTTPError as e:
                last_err = e
                if e.code == 403:
                    raise RuntimeError("permission-blocked: Chrome is reachable, but the per-session Allow remote debugging popup has not been accepted")
                if e.code == 404 and (ws := _ws_from_devtools_active_port(url)):
                    return ws
                time.sleep(1)
            except Exception as e:
                last_err = e
                time.sleep(1)
        hint = "is the dedicated automation Chrome running? Launch it with --remote-debugging-port=<port> --user-data-dir=<dedicated dir>"
        if platform.system() == "Windows":
            hint += "; on Windows also check that a firewall/antivirus isn't blocking localhost connections"
        raise RuntimeError(f"BU_CDP_URL={url} unreachable after 30s: {last_err} -- {hint}")
    deadline = time.time() + 30
    next_liveness_check = 0.0
    while time.time() < deadline:
        for base in PROFILES:
            try:
                active = (base / "DevToolsActivePort").read_text(encoding="utf-8", errors="replace").splitlines()
            except (FileNotFoundError, NotADirectoryError):
                continue
            port = active[0].strip() if active else ""
            ws_path = active[1].strip() if len(active) > 1 else ""
            if not port:
                continue
            # Resolve the live WS URL via /json/version instead of trusting the path stored
            # alongside the port in DevToolsActivePort: if Chrome was previously launched
            # with a different --user-data-dir on the same port, that file is left behind
            # with a stale browser UUID and the WS upgrade returns 404.
            try:
                return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1).read())["webSocketDebuggerUrl"]
            except urllib.error.HTTPError as e:
                if e.code == 403:
                    raise RuntimeError("permission-blocked: Chrome is reachable, but the per-session Allow remote debugging popup has not been accepted")
                # Chrome 147+ disables /json/* HTTP discovery on the default user-data-dir;
                # the ws path Chrome wrote to DevToolsActivePort still works.
                if e.code == 404 and ws_path:
                    return f"ws://127.0.0.1:{port}{ws_path}"
            except (OSError, KeyError, ValueError):
                pass
        # Closed browser leaves stale DevToolsActivePort files
        now = time.time()
        if now >= next_liveness_check:
            if not supported_browser_running():
                raise RuntimeError(
                    "chrome-not-running: no supported Chromium-family browser is running -- start Chrome, then retry"
                )
            next_liveness_check = now + 2
        # The browser is running but the port isn't up; waiting 30s
        grace = TOGGLE_BOOT_GRACE if remote_debugging_toggle_profiles() else NO_TOGGLE_GRACE
        if now > deadline - 30 + grace:
            break
        time.sleep(0.2)
    for probe_port in (9222, 9223):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{probe_port}/json/version", timeout=1) as r:
                return json.loads(r.read())["webSocketDebuggerUrl"]
        except urllib.error.HTTPError as e:
            if e.code == 403:
                raise RuntimeError("permission-blocked: Chrome is reachable, but the per-session Allow remote debugging popup has not been accepted")
        except (OSError, KeyError, ValueError):
            continue
    if remote_debugging_user_enabled() is False:
        raise RuntimeError('remote debugging is turned off for this browser instance — enable chrome://inspect/#remote-debugging (tick "Allow remote debugging for this browser instance")')
    raise RuntimeError(f"DevToolsActivePort not found in {[str(p) for p in PROFILES]} — enable chrome://inspect/#remote-debugging, or set BU_CDP_WS for a remote browser")


def stop_remote(strict=False):
    global _REMOTE_STOPPED
    if not REMOTE_ID:
        return True
    if _REMOTE_STOPPED:
        return True
    last_error = None
    for attempt in range(3):
        try:
            key = auth.get_browser_use_api_key()
            req = urllib.request.Request(
                f"{BU_API}/browsers/{REMOTE_ID}",
                data=json.dumps({"action": "stop"}).encode(),
                method="PATCH",
                headers={"X-Browser-Use-API-Key": key, "Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=15).read()
            _REMOTE_STOPPED = True
            log(f"stopped remote browser {REMOTE_ID}")
            return True
        except Exception as e:
            last_error = e
            log(f"stop_remote attempt {attempt + 1}/3 failed ({REMOTE_ID}): {e}")
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
    if strict:
        raise RuntimeError(f"failed to stop remote browser {REMOTE_ID}: {last_error}")
    return False


def is_real_page(t):
    return t["type"] == "page" and not t.get("url", "").startswith(INTERNAL)


def _guard_url_allowed(url):
    """Whether a guarded read or marker may touch this page URL."""
    if not isinstance(url, str) or not url:
        return False
    lowered = url.lower()
    if lowered == "about:blank" or lowered.startswith("about:blank#"):
        return True
    parsed = urlparse(url)
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)


def is_reusable_blank_page(t):
    """A plain about:blank tab that is safe to attach to and navigate"""
    url = t.get("url", "")
    return (
        t["type"] == "page"
        and (url == "about:blank" or url.startswith("about:blank#"))
        and not t.get("title", "").startswith("Starting agent ")
    )


def is_inspect_tab(t):
    """A chrome://inspect tab — normally the one the permission flow opened"""
    return t["type"] == "page" and t.get("url", "").startswith("chrome://inspect")


def harness_opened_inspect():
    """True when admin's recovery flow opened a chrome://inspect tab that is
    still awaiting cleanup (the marker survives until the next connect)."""
    try:
        return paths.inspect_marker().exists()
    except OSError:
        return False


def is_reusable_new_tab_page(t):
    """The browser's own New Tab Page, ex: from a fresh launch"""
    return t["type"] == "page" and t.get("url", "").startswith(
        ("chrome://newtab", "chrome://new-tab-page", "edge://newtab", "about:newtab")
    )


class _PatientCDPClient(CDPClient):
    """CDPClient whose local Chrome approval handshake has no deadline."""

    async def start(self):
        import websockets
        if self.ws is not None:
            raise RuntimeError("Client is already started")
        connect_kwargs = {"max_size": self.max_ws_frame_size, "open_timeout": LOCAL_HANDSHAKE_TIMEOUT}
        if self.additional_headers:
            connect_kwargs["additional_headers"] = self.additional_headers
        self.ws = await websockets.connect(self.url, **connect_kwargs)
        self._message_handler_task = asyncio.create_task(self._handle_messages())


class Daemon:
    def __init__(self):
        self.cdp = None
        self.session = None
        self.target_id = None
        self.dedicated_target_id = None
        self._dedicated_target_lock = asyncio.Lock()
        self._session_state_lock = asyncio.Lock()
        self._overflow_attach_lock = asyncio.Lock()
        self._guarded_attach_slots = asyncio.Semaphore(MAX_OVERFLOW_CLEANUP_RETRIES)
        self._active_recoveries = 0
        self._recovery_tasks = set()
        self._recoveries_idle = asyncio.Event()
        self._recoveries_idle.set()
        self._shutting_down = False
        self._session_replacements = {}
        self._session_targets = {}
        self._guarded_sessions = set()
        self._guarded_targets = set()
        self._guarded_contexts = set()
        self._guard_policy_active = os.environ.get("BH_TAB_GUARD") == "1"
        self._guarded_run_id = None
        self._authorization_epoch = 0
        self._legacy_commands = {}
        self._legacy_wire_id = 0
        self._revoked_sessions = set()
        # Ordered map gives duplicate suppression plus bounded oldest-first pruning.
        self._pending_detached_sessions = {}
        self._pending_detached_sessions_overflowed = False
        # Failed cleanup must remain retryable. Keep this separate from event
        # history, and stop creating sessions when the bounded record is full.
        self._overflow_cleanup_sessions = {}
        self._marker_tasks = set()
        self.events = deque(maxlen=BUF)
        self._event_provenance = deque(maxlen=BUF)
        self._document_state = {}
        self._request_provenance = {}
        self._request_index = {}
        self._ambiguous_request_ids = set()
        self._execution_contexts = {}
        self.dialog_session = None
        self.dialog = None
        self.dialog_generation = None
        self.dialog_document_url = None
        self.stop = None  # asyncio.Event, set inside start()

    async def attach_first_page(self, replaces_session=None, enable_domains=True):
        """Attach to a real page (or any page). Sets self.session. Returns attached target or None."""
        if self._guard_policy_active or os.environ.get("BH_TAB_GUARD") == "1":
            # Startup and automatic recovery have no helper-side ownership
            # proof for a fresh session, so they must not attach to the
            # focused user's tab. Use switch_tab() to reattach explicitly.
            return None
        targets = (await self.cdp.send_raw("Target.getTargets"))["targetInfos"]
        # Named daemons (BU_NAME != "default") share one browser with other
        # daemons — attaching to the first page makes parallel daemons fight
        # over a single tab (navigations clobber each other). Give each named
        # daemon its own dedicated tab instead. REMOTE_ID (cloud) browsers are
        # already exclusive to this daemon, so first-page attach stays.
        if NAME != "default" and not REMOTE_ID:
            # The permission recovery flow can leave chrome://inspect open.
            # Clean it up before returning from this early path as well.
            if BROWSER_KIND == "local":
                await self._close_inspect_tabs(targets)
            pages_by_id = {t["targetId"]: t for t in targets if t["type"] == "page"}
            # A stale CDP session does not necessarily mean its tab disappeared.
            # Reattach to the current tab first, then the daemon's dedicated tab.
            page = pages_by_id.get(self.target_id) or pages_by_id.get(self.dedicated_target_id)
            if page is None:
                # Two stale IPC requests can recover concurrently. Recheck
                # inside a narrow lock so they share one replacement tab.
                async with self._dedicated_target_lock:
                    refreshed = (await self.cdp.send_raw("Target.getTargets"))["targetInfos"]
                    pages_by_id = {t["targetId"]: t for t in refreshed if t["type"] == "page"}
                    page = pages_by_id.get(self.target_id) or pages_by_id.get(self.dedicated_target_id)
                    if page is None:
                        tid = (await self.cdp.send_raw(
                            "Target.createTarget", {"url": "about:blank", "background": True}
                        ))["targetId"]
                        self.dedicated_target_id = tid
                        log(f"named daemon {NAME}: created dedicated tab ({tid})")
                        page = {"targetId": tid, "url": "about:blank", "type": "page"}
            tid = page["targetId"]
            self.session = (await self.cdp.send_raw(
                "Target.attachToTarget", {"targetId": tid, "flatten": True}
            ))["sessionId"]
            self._record_session_replacement(replaces_session, self.session)
            self.target_id = tid
            self._session_targets[self.session] = tid
            log(f"attached {tid} ({page.get('url','')[:80]}) session={self.session}")
            if enable_domains:
                await self._enable_default_domains(self.session)
            return page

        pages = [t for t in targets if is_real_page(t)]
        if not pages:
            # Fresh browser (ex: BU cloud) starts w about:blank; reuse it
            pages = [t for t in targets if is_reusable_blank_page(t)]
        if not pages:
            # Freshly launched browser (ex: harness relaunching closed Chrome)
            # starts with just the New Tab Page. Reuse it — creating about:blank
            pages = [t for t in targets if is_reusable_new_tab_page(t)]
        take_over = None
        if not pages and harness_opened_inspect():
            # After perms granted, only tab is often chrome://inspect
            # Attach to it instead of creating a new about:blank
            inspect_tabs = [t for t in targets if is_inspect_tab(t)]
            if inspect_tabs:
                pages = [inspect_tabs[0]]
                take_over = inspect_tabs[0]["targetId"]
        if not pages:
            # No usable pages - create one instead of attaching to omnibox popup.
            tid = (await self.cdp.send_raw(
                "Target.createTarget", {"url": "about:blank", "background": True}
            ))["targetId"]
            log(f"no real pages found, created about:blank ({tid})")
            pages = [{"targetId": tid, "url": "about:blank", "type": "page"}]
        self.session = (await self.cdp.send_raw(
            "Target.attachToTarget", {"targetId": pages[0]["targetId"], "flatten": True}
        ))["sessionId"]
        self._record_session_replacement(replaces_session, self.session)
        self.target_id = pages[0]["targetId"]
        self._session_targets[self.session] = self.target_id
        log(f"attached {pages[0]['targetId']} ({pages[0].get('url','')[:80]}) session={self.session}")
        if take_over:
            try:
                await self.cdp.send_raw("Page.navigate", {"url": "about:blank"}, session_id=self.session)
                log(f"took over inspect tab {take_over} -> about:blank")
            except Exception as e:
                log(f"take over inspect tab {take_over}: {e}")
        if BROWSER_KIND == "local":
            await self._close_inspect_tabs(targets)
        if enable_domains:
            await self._enable_default_domains(self.session)
        return pages[0]

    async def _close_inspect_tabs(self, targets):
        """Close chrome://inspect tabs left open by the permission recovery flow"""
        if not harness_opened_inspect():
            return
        for t in targets:
            if t["targetId"] != self.target_id and is_inspect_tab(t):
                try:
                    await self.cdp.send_raw("Target.closeTarget", {"targetId": t["targetId"]})
                    log(f"closed leftover chrome://inspect tab {t['targetId']}")
                except Exception as e:
                    log(f"close inspect tab {t['targetId']}: {e}")
        try:
            paths.inspect_marker().unlink()
        except OSError:
            pass

    async def _enable_default_domains(self, session_id):
        """Enable Page/DOM/Runtime/Network on a CDP session.

        Used by both initial attach and set_session (called after switch_tab/
        new_tab). Without this, helpers that depend on Network.* events —
        notably wait_for_network_idle() — silently stop receiving events
        after a tab switch, because each fresh CDP session starts with all
        domains disabled.

        Runs the four enables in parallel via gather so the worst-case time is
        bounded by a single CDP round trip rather than four sequential ones —
        important on the set_session path, where the helper's IPC socket has
        a 5s read timeout.
        """
        if self._guard_policy_active and session_id not in self._guarded_sessions:
            return
        async def enable_one(d):
            try:
                await asyncio.wait_for(
                    self.cdp.send_raw(f"{d}.enable", session_id=session_id),
                    timeout=4,
                )
            except Exception as e:
                log(f"enable {d} on {session_id}: {e}")
        await asyncio.gather(*(enable_one(d) for d in ("Page", "DOM", "Runtime", "Network")))

    async def _seed_document_frame(self, session_id):
        """Restore top-frame correlation after attaching to an existing page."""
        try:
            tree = (await self.cdp.send_raw(
                "Page.getFrameTree", session_id=session_id
            )).get("frameTree", {})
        except Exception:
            return
        frame = tree.get("frame") if isinstance(tree, dict) else None
        state = self._document_state.get(session_id)
        if (not isinstance(frame, dict) or not isinstance(state, dict)
                or frame.get("url") != state.get("document_url")):
            return
        state["frame_id"] = frame.get("id")
        state["loader_id"] = frame.get("loaderId")

    def _record_session_replacement(self, stale_session, replacement_session):
        """Remember which recovered session still controls the same tab."""
        if not stale_session or not replacement_session or stale_session == replacement_session:
            return
        # Preserve chains so requests delayed across multiple recoveries still
        # land on their original tab, never whichever tab is current now.
        for source, replacement in list(self._session_replacements.items()):
            if replacement == stale_session:
                self._session_replacements[source] = replacement_session
        self._session_replacements[stale_session] = replacement_session
        while len(self._session_replacements) > 32:
            self._session_replacements.pop(next(iter(self._session_replacements)))

    def _begin_recovery(self):
        """Register the current IPC handler unless shutdown has started."""
        if self._shutting_down:
            return None
        task = asyncio.current_task()
        if task is None:
            return None
        self._recovery_tasks.add(task)
        self._active_recoveries += 1
        self._recoveries_idle.clear()
        return task

    def _finish_recovery(self, task):
        self._recovery_tasks.discard(task)
        self._active_recoveries -= 1
        if self._active_recoveries == 0:
            self._recoveries_idle.set()

    async def _cancel_and_drain_recoveries(self):
        """Cancel active stale-session handlers and wait a bounded time."""
        current = asyncio.current_task()
        tasks = [
            task for task in self._recovery_tasks
            if task is not current and not task.done()
        ]
        for task in tasks:
            task.cancel()
        if tasks:
            _done, pending = await asyncio.wait(
                tasks, timeout=RECOVERY_CANCEL_DRAIN_TIMEOUT
            )
            if pending:
                return False
        return self._recoveries_idle.is_set()

    def _schedule_tab_marker(self, session_id):
        """Mark the controlled tab without extending the synchronous IPC path."""
        if not tab_marker_enabled():
            return None
        target_id = self._session_targets.get(session_id)
        guarded = self._guard_policy_active
        epoch = self._authorization_epoch
        state = self._document_state.get(session_id)
        generation = state.get("generation") if isinstance(state, dict) else None
        document_url = state.get("document_url") if isinstance(state, dict) else None

        async def mark():
            if session_id in self._revoked_sessions:
                return
            if guarded:
                if (session_id not in self._guarded_sessions
                        or not target_id or target_id not in self._guarded_targets
                        or epoch != self._authorization_epoch
                        or not isinstance(generation, int)
                        or not isinstance(self._document_state.get(session_id), dict)
                        or self._document_state[session_id].get("generation") != generation
                        or self._document_state[session_id].get("document_url") != document_url):
                    return
                try:
                    info = (await self.cdp.send_raw(
                        "Target.getTargetInfo", {"targetId": target_id}
                    )).get("targetInfo", {})
                except Exception:
                    return
                if not _guard_url_allowed(info.get("url")):
                    return
                if (not self._guard_policy_active
                        or session_id not in self._guarded_sessions
                        or target_id not in self._guarded_targets
                        or epoch != self._authorization_epoch
                        or not isinstance(self._document_state.get(session_id), dict)
                        or self._document_state[session_id].get("generation") != generation
                        or self._document_state[session_id].get("document_url") != document_url):
                    return
            elif self._guard_policy_active or os.environ.get("BH_TAB_GUARD") == "1":
                # Guarded startup has no explicit session policy yet. Stay
                # inert until a guarded request registers one.
                return
            await self.cdp.send_raw(
                "Runtime.evaluate",
                {"expression": TAB_MARKER_JS},
                session_id=session_id,
            )

        async def run_marker():
            try:
                await asyncio.wait_for(mark(), timeout=2)
            except BaseException:
                return

        task = asyncio.create_task(run_marker())
        self._marker_tasks.add(task)
        task.add_done_callback(self._marker_tasks.discard)
        return task

    async def start(self):
        self.stop = asyncio.Event()
        url = get_ws_url()
        log(f"connecting to {_safe_connection_label(url)}")
        self.cdp = _PatientCDPClient(url) if BROWSER_KIND == "local" else CDPClient(url)
        if BROWSER_KIND == "local":
            # Allow while this handshake is still parked on the popup
            log("handshake-wait: if Chrome shows an 'Allow remote debugging?' popup, click Allow")
        try:
            await self.cdp.start()
        except Exception as e:
            if os.environ.get("BU_CDP_WS"):
                raise RuntimeError(
                    f"CDP WS handshake failed: {e} -- remote browser WebSocket connection failed. "
                    "This can happen when network policy blocks the connection, the WS URL is wrong or expired, or the remote endpoint is down. "
                    "If you use Browser Use cloud, verify auth and get a fresh URL via start_remote_daemon()."
                )
            if BROWSER_KIND == "local" and ("timed out" in str(e).lower() or "403" in str(e)) and remote_debugging_user_enabled():
                raise RuntimeError(
                    "permission-blocked: Chrome did not approve the remote debugging connection; "
                    "browser-harness did not retry or create another connection"
                )
            raise RuntimeError(f"CDP WS handshake failed: {e} -- click Allow in Chrome if prompted, then retry")
        await self.attach_first_page()
        orig = self.cdp._event_registry.handle_event
        async def tap(method, params, session_id=None):
            self._record_event(method, params, session_id)
            return await orig(method, params, session_id)
        self.cdp._event_registry.handle_event = tap

    @staticmethod
    def _event_details(event):
        """Return source, inner method, params, and payload from one envelope."""
        if event.get("method") != "Target.receivedMessageFromTarget":
            session_id = event.get("session_id")
            if not isinstance(session_id, str) or not session_id:
                return None, event.get("method"), event.get("params"), None
            return session_id, event.get("method"), event.get("params"), None
        params = event.get("params")
        if not isinstance(params, dict):
            return None, None, None, None
        session_id, message = params.get("sessionId"), params.get("message")
        if not isinstance(session_id, str) or not session_id or not isinstance(message, str):
            return None, None, None, None
        try:
            payload = json.loads(message)
        except (TypeError, ValueError):
            return None, None, None, None
        if not isinstance(payload, dict):
            return None, None, None, None
        nested_session = payload.get("sessionId")
        if nested_session is not None and nested_session != session_id:
            return None, None, None, None
        return session_id, payload.get("method"), payload.get("params"), payload

    @classmethod
    def _event_source_session(cls, event):
        """Extract the transport source, never an untrusted outer carrier."""
        return cls._event_details(event)[0]

    @staticmethod
    def _is_top_level_navigation(method, params):
        if method != "Page.frameNavigated":
            return False
        frame = params.get("frame") if isinstance(params, dict) else None
        return isinstance(frame, dict) and frame.get("parentId") is None

    @classmethod
    def _navigation_url(cls, method, params):
        if not cls._is_top_level_navigation(method, params):
            return None
        return params["frame"].get("url")

    @staticmethod
    def _context_origin_allowed(context, document_url):
        if not isinstance(context, dict) or not isinstance(document_url, str):
            return False
        origin = context.get("origin")
        if not isinstance(origin, str):
            return False
        parsed = urlparse(document_url)
        if parsed.scheme == "about" and parsed.path == "blank":
            return origin in {"", "null"}
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return False
        return origin.rstrip("/") == f"{parsed.scheme}://{parsed.netloc}"

    def _remember_request(self, source, target_id, request_id, loader_id,
                          document_url, frame_id, generation, allowed):
        base_key = (source, target_id, request_id)
        full_key = (source, target_id, request_id, loader_id, document_url, frame_id)
        previous_key = self._request_index.get(base_key)
        previous = self._request_provenance.get(previous_key) if previous_key else None
        if previous_key and (
            previous_key != full_key
            or not isinstance(previous, dict)
            or previous.get("allowed") is not allowed
        ):
            self._ambiguous_request_ids.add(base_key)
        if full_key not in self._request_provenance:
            self._request_provenance[full_key] = {
                "session_id": source,
                "target_id": target_id,
                "request_id": request_id,
                "generation": generation,
                "loader_id": loader_id,
                "document_url": document_url,
                "frame_id": frame_id,
                "allowed": allowed,
            }
        self._request_index[base_key] = full_key
        while len(self._request_provenance) > BUF:
            evicted_key = next(iter(self._request_provenance))
            self._request_provenance.pop(evicted_key)
            evicted_base = evicted_key[:3]
            if self._request_index.get(evicted_base) == evicted_key:
                remaining = [key for key in self._request_provenance if key[:3] == evicted_base]
                if remaining:
                    self._request_index[evicted_base] = remaining[-1]
                else:
                    self._request_index.pop(evicted_base, None)
                    self._ambiguous_request_ids.discard(evicted_base)

    def _authorized_request(self, source, target_id, request_id):
        base_key = (source, target_id, request_id)
        if base_key in self._ambiguous_request_ids:
            return None
        record = self._request_provenance.get(self._request_index.get(base_key))
        if (
            not isinstance(record, dict)
            or record.get("allowed") is not True
            or record.get("session_id") != source
            or record.get("target_id") != target_id
            or record.get("request_id") != request_id
        ):
            return None
        return record

    def _revoke_event_ownership(self, sessions=(), targets=()):
        """Revoke target state and buffered authorization tied to destroyed CDP objects."""
        sessions, targets = set(sessions), set(targets)
        for sid, target in self._session_targets.items():
            if target in targets:
                sessions.add(sid)
        for sid in sessions:
            self._pending_detached_sessions.pop(sid, None)
        if not self._guard_policy_active:
            return

        self._guarded_sessions.difference_update(sessions)
        self._guarded_targets.difference_update(targets)
        self._revoked_sessions.update(sessions)
        for sid in sessions:
            self._session_targets.pop(sid, None)
            self._document_state.pop(sid, None)
        self._session_targets = {
            sid: target for sid, target in self._session_targets.items()
            if target not in targets
        }
        self._session_replacements = {
            stale: replacement for stale, replacement in self._session_replacements.items()
            if stale not in sessions and replacement not in sessions
        }
        self._legacy_commands = {
            key: value for key, value in self._legacy_commands.items()
            if value.get("session_id") not in sessions
            and value.get("target_id") not in targets
        }
        self._request_provenance = {
            key: value for key, value in self._request_provenance.items()
            if key[0] not in sessions and key[1] not in targets
        }
        self._request_index = {
            key: value for key, value in self._request_index.items()
            if key[0] not in sessions and key[1] not in targets
        }
        self._ambiguous_request_ids = {
            key for key in self._ambiguous_request_ids
            if key[0] not in sessions and key[1] not in targets
        }
        self._execution_contexts = {
            key: value for key, value in self._execution_contexts.items()
            if key[0] not in sessions and key[1] not in targets
        }
        if self.session in sessions or self.target_id in targets:
            self.session = None
            self.target_id = None
        if self.dialog_session in sessions:
            self.dialog = None
            self.dialog_session = None
            self.dialog_generation = None
            self.dialog_document_url = None

        retained_events, retained_provenance = deque(maxlen=BUF), deque(maxlen=BUF)
        for event, provenance in zip(self.events, self._event_provenance):
            if (isinstance(provenance, dict)
                    and provenance.get("session_id") not in sessions
                    and provenance.get("target_id") not in targets):
                retained_events.append(event)
                retained_provenance.append(provenance)
        self.events = retained_events
        self._event_provenance = retained_provenance

    def _record_browser_lifecycle_event(self, method, params):
        """Handle browser-level lifecycle notifications with no source session."""
        if not self._guard_policy_active or not isinstance(params, dict):
            return
        if method == "Target.detachedFromTarget":
            sid = params.get("sessionId")
            if isinstance(sid, str):
                if sid in self._session_targets or sid in self._guarded_sessions:
                    self._revoke_event_ownership({sid})
                else:
                    if (sid not in self._pending_detached_sessions
                            and len(self._pending_detached_sessions) >= 256):
                        self._pending_detached_sessions_overflowed = True
                        self._pending_detached_sessions.pop(
                            next(iter(self._pending_detached_sessions))
                        )
                    self._pending_detached_sessions.pop(sid, None)
                    self._pending_detached_sessions[sid] = None
        elif method == "Target.targetDestroyed":
            target = params.get("targetId")
            if isinstance(target, str) and target in self._guarded_targets:
                self._revoke_event_ownership(targets={target})

    def _record_event(self, method, params, session_id=None):
        event = {"method": method, "params": params, "session_id": session_id}
        if session_id is None:
            self._record_browser_lifecycle_event(method, params)
        source_session, inner_method, inner_params, payload = self._event_details(event)
        provenance = None
        if self._guard_policy_active:
            source = source_session
            target_id = self._session_targets.get(source)
            state = self._document_state.get(source)
            if (source not in self._guarded_sessions
                    or target_id not in self._guarded_targets
                    or not isinstance(state, dict)
                    or state.get("target_id") != target_id):
                return
            if self._is_top_level_navigation(inner_method, inner_params):
                navigation_url = self._navigation_url(inner_method, inner_params)
                state["generation"] += 1
                state["url"] = navigation_url
                frame = inner_params["frame"]
                state["document_url"] = navigation_url
                state["frame_id"] = frame.get("id")
                state["loader_id"] = frame.get("loaderId")
                state["allowed"] = _guard_url_allowed(navigation_url)
                if self.dialog_session == source:
                    self.dialog = None
                    self.dialog_session = None
                    self.dialog_generation = None
                    self.dialog_document_url = None
                # Anything correlated with the prior document is stale now.
                self._legacy_commands = {
                    key: value for key, value in self._legacy_commands.items()
                    if value.get("session_id") != source
                    or value.get("generation") == state["generation"]
                    or (value.get("method") == "Page.navigate"
                        and isinstance(value.get("generation"), int)
                        and value.get("generation") + 1 == state["generation"])
                }
            elif inner_method == "Page.navigatedWithinDocument":
                frame_id = inner_params.get("frameId") if isinstance(inner_params, dict) else None
                navigation_url = inner_params.get("url") if isinstance(inner_params, dict) else None
                if (not isinstance(state.get("frame_id"), str)
                        or frame_id != state.get("frame_id")
                        or not isinstance(navigation_url, str)):
                    return
                # This changes the active URL, not the document. Keep the
                # generation and document-bound authorization provenance intact.
                state["url"] = navigation_url
                state["document_url"] = navigation_url
                state["allowed"] = _guard_url_allowed(navigation_url)
            request_id = None
            if inner_method == _NETWORK_REQUEST_METHOD:
                request_id = inner_params.get("requestId") if isinstance(inner_params, dict) else None
                request_url = inner_params.get("documentURL") if isinstance(inner_params, dict) else None
                loader_id = inner_params.get("loaderId") if isinstance(inner_params, dict) else None
                frame_id = inner_params.get("frameId") if isinstance(inner_params, dict) else None
                if not isinstance(request_id, str) or not request_id:
                    return
                request_allowed = bool(
                    state.get("allowed")
                    and isinstance(request_url, str)
                    and _guard_url_allowed(request_url)
                    and request_url == state.get("document_url")
                    and isinstance(loader_id, str)
                    and loader_id == state.get("loader_id")
                    and isinstance(frame_id, str)
                    and frame_id == state.get("frame_id")
                )
                self._remember_request(
                    source, target_id, request_id, loader_id if isinstance(loader_id, str) else None,
                    request_url if isinstance(request_url, str) else None,
                    frame_id if isinstance(frame_id, str) else None,
                    state["generation"], request_allowed,
                )
                if not request_allowed:
                    return
            if not state.get("allowed"):
                return
            if inner_method == "Page.javascriptDialogOpening":
                dialog_url = inner_params.get("url") if isinstance(inner_params, dict) else None
                dialog_frame_id = inner_params.get("frameId") if isinstance(inner_params, dict) else None
                if (not isinstance(dialog_url, str)
                        or dialog_url != state.get("document_url")
                        or not isinstance(state.get("frame_id"), str)
                        or dialog_frame_id != state.get("frame_id")
                        or not _guard_url_allowed(dialog_url)):
                    return
            elif inner_method == "Page.javascriptDialogClosed":
                dialog_frame_id = inner_params.get("frameId") if isinstance(inner_params, dict) else None
                if (not isinstance(state.get("frame_id"), str)
                        or dialog_frame_id != state.get("frame_id")):
                    return
            if inner_method == "Page.frameNavigated":
                frame = inner_params.get("frame") if isinstance(inner_params, dict) else None
                if (not isinstance(frame, dict)
                        or frame.get("parentId") is not None
                        or frame.get("id") != state.get("frame_id")
                        or frame.get("url") != state.get("document_url")):
                    return
            elif inner_method == "Page.navigatedWithinDocument":
                frame_id = inner_params.get("frameId") if isinstance(inner_params, dict) else None
                if (frame_id != state.get("frame_id")
                        or inner_params.get("url") != state.get("document_url")):
                    return
            elif inner_method in {"Page.loadEventFired", "Page.domContentEventFired"}:
                # These CDP events carry a timestamp, not a frameId. Their
                # transport session is already bound to an owned target above;
                # bind them to that session's current allowed document here.
                if (not isinstance(state.get("document_url"), str)
                        or not isinstance(state.get("frame_id"), str)):
                    return
            elif inner_method in _NETWORK_REQUEST_CORRELATED_METHODS:
                request_id = inner_params.get("requestId") if isinstance(inner_params, dict) else None
                record = self._authorized_request(source, target_id, request_id)
                if (
                    not isinstance(request_id, str) or not request_id
                    or record is None
                ):
                    return
            elif inner_method == "Runtime.executionContextCreated":
                context = inner_params.get("context") if isinstance(inner_params, dict) else None
                context_id = context.get("id") if isinstance(context, dict) else None
                aux_data = context.get("auxData") if isinstance(context, dict) else None
                context_frame_id = aux_data.get("frameId") if isinstance(aux_data, dict) else None
                if (
                    not isinstance(context_id, (int, str))
                    or context_frame_id != state.get("frame_id")
                    or not self._context_origin_allowed(context, state.get("document_url"))
                ):
                    return
                context_key = (source, target_id, str(context_id))
                self._execution_contexts[context_key] = {
                    "session_id": source,
                    "target_id": target_id,
                    "context_id": str(context_id),
                    "generation": state["generation"],
                    "frame_id": context_frame_id,
                    "document_url": state.get("document_url"),
                    "allowed": True,
                }
            elif inner_method in {"Runtime.consoleAPICalled", "Runtime.executionContextDestroyed"}:
                context_id = inner_params.get("executionContextId") if isinstance(inner_params, dict) else None
                context_key = (source, target_id, str(context_id))
                context_record = self._execution_contexts.get(context_key)
                if (
                    not isinstance(context_id, (int, str))
                    or not isinstance(context_record, dict)
                    or context_record.get("generation") != state.get("generation")
                    or context_record.get("document_url") != state.get("document_url")
                    or context_record.get("frame_id") != state.get("frame_id")
                    or context_record.get("allowed") is not True
                ):
                    return
            elif inner_method not in _GUARDED_PAGE_EVENT_METHODS | {_NETWORK_REQUEST_METHOD}:
                is_response = (
                    method == _GUARDED_RESPONSE_METHOD
                    and isinstance(payload, dict)
                    and isinstance(payload.get("id"), (int, str))
                    and not isinstance(payload.get("id"), bool)
                    and payload.get("id") != ""
                    and "method" not in payload
                    and ((isinstance(payload.get("result"), dict)
                          and "error" not in payload)
                         or (isinstance(payload.get("error"), dict)
                             and isinstance(payload["error"].get("code"), int)
                             and isinstance(payload["error"].get("message"), str)
                             and "result" not in payload))
                )
                command_key = (source, payload.get("id")) if is_response else None
                command = self._legacy_commands.get(command_key)
                same_document = (
                    isinstance(command, dict)
                    and command.get("generation") == state.get("generation")
                    and command.get("document_url") == state.get("document_url")
                )
                completed_navigation = (
                    isinstance(command, dict)
                    and command.get("method") == "Page.navigate"
                    and isinstance(command.get("generation"), int)
                    and state.get("generation") in {
                        command.get("generation"), command.get("generation") + 1,
                    }
                    and state.get("allowed") is True
                    and _guard_url_allowed(state.get("document_url"))
                )
                if (not is_response or not isinstance(command, dict)
                        or command.get("run_id") != self._guarded_run_id
                        or command.get("epoch") != self._authorization_epoch
                        or not (same_document or completed_navigation)
                        or command.get("target_id") != target_id):
                    return
                self._legacy_commands.pop(command_key, None)
                payload["id"] = command["caller_id"]
                params["message"] = json.dumps(payload, separators=(",", ":"))
            provenance = {
                "session_id": source,
                "target_id": target_id,
                "generation": state["generation"],
                "url": state.get("url"),
                "allowed": True,
            }
            if request_id is not None:
                provenance["request_id"] = request_id
            if inner_method in {"Runtime.consoleAPICalled", "Runtime.executionContextDestroyed"}:
                provenance["execution_context_id"] = str(context_id)
        self.events.append(event)
        self._event_provenance.append(provenance)
        event_session = source_session if self._guard_policy_active else session_id
        if inner_method == "Page.javascriptDialogOpening":
            self.dialog = inner_params
            self.dialog_session = event_session
            if self._guard_policy_active:
                current_state = self._document_state.get(source_session)
                self.dialog_generation = current_state.get("generation") if isinstance(current_state, dict) else None
                self.dialog_document_url = current_state.get("document_url") if isinstance(current_state, dict) else None
        elif inner_method == "Page.javascriptDialogClosed":
            current_state = self._document_state.get(source_session)
            if (event_session == self.dialog_session
                    and (not self._guard_policy_active
                         or (isinstance(current_state, dict)
                             and self.dialog_generation == current_state.get("generation")
                             and self.dialog_document_url == current_state.get("document_url")))):
                self.dialog = None
                self.dialog_session = None
                self.dialog_generation = None
                self.dialog_document_url = None
        elif inner_method in ("Page.loadEventFired", "Page.domContentEventFired"):
            self._schedule_tab_marker(event_session)
        if self._guard_policy_active and inner_method == "Runtime.executionContextDestroyed":
            self._execution_contexts.pop(context_key, None)

    async def _tab_guard_reset(self, req):
        run_id = req.get("tab_guard_run")
        expected_epoch = req.get("tab_guard_epoch")
        if (not isinstance(run_id, str) or not run_id
                or not isinstance(expected_epoch, int)):
            return {"tab_guard": "refused"}
        async with self._session_state_lock:
            # A reset may have waited behind registration of a newer run.
            # Compare both tokens after acquiring the mutation lock.
            if (run_id != self._guarded_run_id
                    or expected_epoch != self._authorization_epoch):
                return {"tab_guard": "refused", "tab_guard_run": self._guarded_run_id,
                        "tab_guard_epoch": self._authorization_epoch}
        # This cleanup awaits CDP. Keep it outside the authorization lock so a
        # slow transport cannot hold up session registration or recovery.
        await self._retry_overflow_cleanup_sessions()
        async with self._session_state_lock:
            if (run_id != self._guarded_run_id
                    or expected_epoch != self._authorization_epoch):
                return {"tab_guard": "refused", "tab_guard_run": self._guarded_run_id,
                        "tab_guard_epoch": self._authorization_epoch}
            revoked_sessions = set(self._guarded_sessions)
            revoked_targets = set(self._guarded_targets)
            # Enforcement stays latched for this daemon's lifetime. A caller
            # cannot escape the guard by resetting and omitting guard fields.
            self._authorization_epoch += 1
            self._guarded_run_id = None
            self._legacy_commands.clear()
            self._revoked_sessions.update(revoked_sessions)
            self._guarded_sessions.clear()
            self._guarded_targets.clear()
            self._guarded_contexts.clear()
            self._pending_detached_sessions.clear()
            self._pending_detached_sessions_overflowed = False
            self._session_targets = {
                sid: target for sid, target in self._session_targets.items()
                if sid not in revoked_sessions and target not in revoked_targets
            }
            self._session_replacements = {
                stale: replacement for stale, replacement in self._session_replacements.items()
                if stale not in revoked_sessions and replacement not in revoked_sessions
            }
            self._request_provenance = {
                key: value for key, value in self._request_provenance.items()
                if key[0] not in revoked_sessions and key[1] not in revoked_targets
            }
            self._request_index = {
                key: value for key, value in self._request_index.items()
                if key[0] not in revoked_sessions and key[1] not in revoked_targets
            }
            self._ambiguous_request_ids = {
                key for key in self._ambiguous_request_ids
                if key[0] not in revoked_sessions and key[1] not in revoked_targets
            }
            self._execution_contexts = {
                key: value for key, value in self._execution_contexts.items()
                if key[0] not in revoked_sessions and key[1] not in revoked_targets
            }
            if self.session in revoked_sessions or self.target_id in revoked_targets:
                self.session = None
                self.target_id = None
            remaining = deque(maxlen=BUF)
            remaining_provenance = deque(maxlen=BUF)
            # Guarded buffers are authorization results; reset revokes all of
            # them, including entries already drained into daemon state.
            self.events = remaining
            self._event_provenance = remaining_provenance
            if self.dialog_session in revoked_sessions:
                self.dialog = None
                self.dialog_session = None
                self.dialog_generation = None
                self.dialog_document_url = None
            marker_tasks = list(self._marker_tasks)
            for task in marker_tasks:
                task.cancel()
            for sid in revoked_sessions:
                self._document_state.pop(sid, None)
        if marker_tasks:
            await asyncio.gather(*marker_tasks, return_exceptions=True)
            self._marker_tasks.difference_update(marker_tasks)
        return {"tab_guard": "ok", "tab_guard_run": run_id}

    async def _retry_overflow_cleanup_sessions(self):
        """Retry detaching refused sessions, retaining failures for later cleanup."""
        for sid in list(self._overflow_cleanup_sessions):
            try:
                await self.cdp.send_raw("Target.detachFromTarget", {"sessionId": sid})
            except Exception as exc:
                log(f"tab guard failed to retry overflow session cleanup {sid}: {exc}")
            else:
                self._overflow_cleanup_sessions.pop(sid, None)

    async def _guarded_read(self, req):
        """Validate and snapshot before yielding; never expose other sessions."""
        meta, owned = req["meta"], req["tab_guard"]
        tabs, sessions = set(owned.get("tabs", [])), set(owned.get("sessions", []))
        run_id, epoch = req.get("tab_guard_run"), req.get("tab_guard_epoch")
        if (not self._guard_policy_active or run_id != self._guarded_run_id
                or epoch != self._authorization_epoch):
            return {"tab_guard": "refused"}
        # Ownership files can retain sessions revoked by Chrome lifecycle
        # events. Ignore stale entries, while requiring the active identity
        # below to be present in both the caller snapshot and daemon state.
        tabs.intersection_update(self._guarded_targets)
        sessions.intersection_update(self._guarded_sessions)
        if not tabs or not sessions:
            return {"tab_guard": "refused"}
        target_id, sid = self.target_id, self.session
        if meta == "drain_events":
            out, remaining = [], deque(maxlen=BUF)
            remaining_provenance = deque(maxlen=BUF)
            for event, provenance in zip(self.events, self._event_provenance):
                allowed = (
                    isinstance(provenance, dict)
                    and provenance.get("allowed") is True
                    and provenance.get("session_id") in sessions
                    and provenance.get("target_id") in tabs
                    and self._session_targets.get(provenance.get("session_id"))
                    == provenance.get("target_id")
                )
                if allowed:
                    out.append(event)
                else:
                    remaining.append(event)
                    remaining_provenance.append(provenance)
            self.events = remaining
            self._event_provenance = remaining_provenance
            return {"events": out, "tab_guard": "ok"}
        if not target_id or target_id not in tabs or not sid or sid not in sessions:
            return {"tab_guard": "refused", "target_id": target_id}
        state = self._document_state.get(sid)
        generation = state.get("generation") if isinstance(state, dict) else None
        document_url = state.get("document_url") if isinstance(state, dict) else None
        if (sid not in sessions or self._session_targets.get(sid) != target_id
                or target_id not in tabs or not isinstance(state, dict)
                or state.get("allowed") is not True):
            return {"tab_guard": "refused", "target_id": target_id}
        try:
            info = (await self.cdp.send_raw(
                "Target.getTargetInfo", {"targetId": target_id}
            ))["targetInfo"]
        except Exception:
            return {"tab_guard": "refused", "target_id": target_id}
        current = self._document_state.get(sid)
        if (not self._guard_policy_active or run_id != self._guarded_run_id
                or epoch != self._authorization_epoch or sid not in self._guarded_sessions
                or target_id not in self._guarded_targets
                or self._session_targets.get(sid) != target_id
                or not isinstance(current, dict)
                or current.get("generation") != generation
                or current.get("document_url") != document_url
                or info.get("url") != document_url):
            return {"tab_guard": "refused", "target_id": target_id}
        if not _guard_url_allowed(info.get("url")):
            return {"tab_guard": "refused", "target_id": target_id, "url": info.get("url", "")}
        if meta == "session":
            return {"session_id": sid, "url": info.get("url", ""), "tab_guard": "ok"}
        if meta == "pending_dialog":
            return {"dialog": self.dialog if self.dialog_session == sid else None,
                    "url": info.get("url", ""), "tab_guard": "ok"}
        if meta in {"current_tab", "connection_status"}:
            page = {"targetId": target_id, "url": info.get("url", ""), "title": info.get("title", "")}
            if meta == "current_tab":
                return {**page, "tab_guard": "ok"}
            return {"target_id": target_id, "session_id": sid,
                    "page": page if is_real_page(info) else None, "tab_guard": "ok"}
        return {"tab_guard": "refused", "target_id": target_id}

    async def handle(self, req):
        # A guardless request may already be awaiting CDP when a guarded
        # bootstrap activates policy. Do not let that earlier request return
        # data after the daemon has crossed into guarded operation.
        policy_was_active = self._guard_policy_active
        response = await self._handle(req)
        if (not policy_was_active and self._guard_policy_active
                and "tab_guard_run" not in req):
            return _guard_refusal("tab guard authorization was revoked during dispatch")
        return response

    async def _handle(self, req):
        # Token guard for Windows TCP loopback: any local process can otherwise
        # connect and issue CDP commands. expected_token() is None on POSIX so
        # this check is a no-op there (AF_UNIX + chmod 600 is the boundary).
        expected = ipc.expected_token()
        if expected is not None and req.get("token") != expected:
            return {"error": "unauthorized"}
        meta = req.get("meta")
        if meta == "guard_epoch":
            return {"tab_guard": "ok", "tab_guard_epoch": self._authorization_epoch,
                    "tab_guard_run": self._guarded_run_id}
        if meta == "guard_context":
            # Return the current target URL with the session snapshot so guarded
            # clients can reject privileged targets before their next dispatch.
            requested_session = req.get("session_id")
            requested_target = req.get("target_id")
            if self._guard_policy_active and (
                    req.get("tab_guard_run") != self._guarded_run_id
                    or req.get("tab_guard_epoch") != self._authorization_epoch):
                return {"tab_guard": "refused", "tab_guard_epoch": self._authorization_epoch}
            if requested_session is not None:
                target_id = self._session_targets.get(requested_session)
                if requested_target is not None and requested_target != target_id:
                    target_id = None
                session_id = requested_session
            elif requested_target is not None:
                target_id = requested_target
                session_id = next((sid for sid, target in self._session_targets.items()
                                   if target == requested_target), None)
            else:
                target_id, session_id = self.target_id, self.session
            state = self._document_state.get(session_id)
            epoch = self._authorization_epoch
            run_id = self._guarded_run_id
            generation = state.get("generation") if isinstance(state, dict) else None
            document_url = state.get("document_url") if isinstance(state, dict) else None
            if self._guard_policy_active and session_id is not None and (
                    session_id not in self._guarded_sessions
                    or target_id not in self._guarded_targets
                    or self._session_targets.get(session_id) != target_id):
                return {"target_id": None, "session_id": session_id,
                        "tab_guard": "refused", "tab_guard_epoch": epoch}
            context = {
                "target_id": target_id,
                "session_id": session_id,
                "tab_guard": "ok",
                "tab_guard_epoch": self._authorization_epoch,
                "document_generation": generation,
                "document_url": document_url,
            }
            if target_id and self.cdp:
                try:
                    info = (await self.cdp.send_raw(
                        "Target.getTargetInfo", {"targetId": target_id}
                    )).get("targetInfo", {})
                    context["url"] = info.get("url", "")
                except Exception:
                    context["url"] = None
                current_state = self._document_state.get(session_id)
                if run_id is not None and session_id is not None and (
                        epoch != self._authorization_epoch or run_id != self._guarded_run_id
                        or session_id not in self._guarded_sessions
                        or target_id not in self._guarded_targets
                        or self._session_targets.get(session_id) != target_id
                        or not isinstance(current_state, dict)
                        or current_state.get("generation") != generation
                        or current_state.get("document_url") != document_url
                        or context.get("url") != document_url):
                    context["tab_guard"] = "refused"
                    context["target_id"] = None
                    context["session_id"] = None
            return context
        if meta == "guard_iframe":
            owned = req.get("tab_guard")
            target_id = req.get("target_id")
            sid, parent_id = self.session, self.target_id
            state = self._document_state.get(sid)
            generation = state.get("generation") if isinstance(state, dict) else None
            document_url = state.get("document_url") if isinstance(state, dict) else None
            if (not self._guard_policy_active or not isinstance(owned, dict)
                    or req.get("tab_guard_run") != self._guarded_run_id
                    or req.get("tab_guard_epoch") != self._authorization_epoch
                    or not isinstance(target_id, str) or target_id in self._guarded_targets
                    or not isinstance(state, dict) or state.get("allowed") is not True
                    or sid not in owned.get("sessions", [])
                    or parent_id not in owned.get("tabs", [])
                    or sid not in self._guarded_sessions
                    or parent_id not in self._guarded_targets
                    or self._session_targets.get(sid) != parent_id):
                return {"tab_guard": "refused"}
            try:
                info = (await self.cdp.send_raw(
                    "Target.getTargetInfo", {"targetId": target_id}
                )).get("targetInfo", {})
                tree = (await self.cdp.send_raw(
                    "Page.getFrameTree", session_id=sid
                )).get("frameTree", {})
            except Exception:
                return {"tab_guard": "refused"}
            pending = [tree]
            frame = None
            while pending:
                node = pending.pop()
                candidate = node.get("frame", {}) if isinstance(node, dict) else {}
                if candidate.get("id") == target_id:
                    frame = candidate
                    break
                pending.extend(node.get("childFrames", []))
            current = self._document_state.get(sid)
            if (not isinstance(frame, dict) or info.get("type") != "iframe"
                    or not _guard_url_allowed(info.get("url"))
                    or frame.get("url") != info.get("url")
                    or not isinstance(current, dict)
                    or req.get("tab_guard_epoch") != self._authorization_epoch
                    or req.get("tab_guard_run") != self._guarded_run_id
                    or sid not in self._guarded_sessions
                    or self._session_targets.get(sid) != parent_id
                    or current.get("generation") != generation
                    or current.get("document_url") != document_url):
                return {"tab_guard": "refused"}
            self._guarded_targets.add(target_id)
            return {"tab_guard": "ok", "target_id": target_id}
        if meta == "tab_guard_reset":
            return await self._tab_guard_reset(req)
        if (self._guard_policy_active and meta is not None
                and meta not in {"ping", "guard_epoch", "guard_context", "shutdown"}
                and not isinstance(req.get("tab_guard"), dict)):
            return {"tab_guard": "refused"}
        protected_metadata = {
            "drain_events", "session", "current_tab", "connection_status",
            "pending_dialog",
        }
        if (meta in protected_metadata
                and (self._guard_policy_active or "tab_guard" in req)):
            if not isinstance(req.get("tab_guard"), dict):
                return {"tab_guard": "refused"}
            return await self._guarded_read(req)
        # Liveness probe — lets clients confirm the listener is actually this
        # daemon and not an unrelated process that reused our port post-crash.
        # `pid` lets restart_daemon() verify the live daemon's identity before
        # signaling — protects against SIGTERM-by-stale-pid-file after PID reuse.
        if meta == "ping":        return {"pong": True, "pid": os.getpid(), "browser_kind": BROWSER_KIND}
        if meta == "drain_events":
            out = list(self.events)
            self.events.clear()
            self._event_provenance.clear()
            return {"events": out}
        if meta == "session":     return {"session_id": self.session}
        if meta == "current_tab":
            # Resolve the attached page's target info server-side. Helpers can't
            # send Target.getTargetInfo themselves: daemon strips session_id for
            # any Target.* method (browser-level call), and without a targetId
            # Chrome silently returns the *browser* target.
            if not self.target_id:
                return {"error": "not_attached"}
            try:
                info = (await self.cdp.send_raw("Target.getTargetInfo", {"targetId": self.target_id}))["targetInfo"]
            except Exception:
                return {"error": "cdp_disconnected"}
            return {"targetId": info.get("targetId"), "url": info.get("url", ""), "title": info.get("title", "")}
        if meta == "connection_status":
            if not self.target_id:
                return {"error": "not_attached"}
            try:
                info = (await self.cdp.send_raw("Target.getTargetInfo", {"targetId": self.target_id}))["targetInfo"]
            except Exception:
                return {"error": "cdp_disconnected"}
            page = None
            if is_real_page(info):
                page = {
                    "targetId": info.get("targetId"),
                    "title": info.get("title") or "(untitled)",
                    "url": info.get("url") or "",
                }
            return {"target_id": self.target_id, "session_id": self.session, "page": page}
        if meta == "set_session":
            registration_generation = None
            registration_url = None
            async with self._session_state_lock:
                owned = req.get("tab_guard")
                guard_run = req.get("tab_guard_run")
                if owned is not None and (
                    not req.get("session_id") or req["session_id"] not in owned.get("sessions", [])
                    or not req.get("target_id") or req["target_id"] not in owned.get("tabs", [])
                    or not isinstance(guard_run, str) or not guard_run
                    or guard_run != self._guarded_run_id
                    or req.get("tab_guard_epoch") != self._authorization_epoch
                    or req["session_id"] not in self._guarded_sessions
                    or req["target_id"] not in self._guarded_targets
                    or self._session_targets.get(req["session_id"]) != req["target_id"]
                ):
                    return {"tab_guard": "refused", "target_id": req.get("target_id")}
                if owned is not None:
                    state = self._document_state.get(req["session_id"])
                    if not isinstance(state, dict):
                        return {"tab_guard": "refused", "target_id": req.get("target_id")}
                    registration_generation = state.get("generation")
                    registration_url = state.get("document_url")
                    # Once an owned switch is accepted, every concurrent
                    # request must be subject to the guard, including while
                    # the live target check below is waiting on CDP.
                    self._guard_policy_active = True
                    try:
                        info = (await self.cdp.send_raw(
                            "Target.getTargetInfo", {"targetId": req["target_id"]}
                        ))["targetInfo"]
                    except Exception:
                        return {"tab_guard": "refused", "target_id": req.get("target_id")}
                    if not _guard_url_allowed(info.get("url")):
                        return {"tab_guard": "refused", "target_id": req.get("target_id"),
                                "url": info.get("url", "")}
                    state = self._document_state.get(req["session_id"])
                    if (guard_run != self._guarded_run_id
                            or req.get("tab_guard_epoch") != self._authorization_epoch
                            or req["session_id"] not in self._guarded_sessions
                            or req["target_id"] not in self._guarded_targets
                            or self._session_targets.get(req["session_id"]) != req["target_id"]
                            or not isinstance(state, dict)
                            or state.get("generation") != registration_generation
                            or state.get("document_url") != registration_url
                            or info.get("url") != state.get("document_url")):
                        return {"tab_guard": "refused", "target_id": req.get("target_id")}
                    self._guard_policy_active = True
                    self._authorization_epoch += 1
                    self._guarded_run_id = guard_run
                old_session = self.session
                self.session = req.get("session_id")
                self.target_id = req.get("target_id") or self.target_id
                new_session = self.session
                if new_session and self.target_id:
                    self._session_targets[new_session] = self.target_id
                if owned is not None:
                    self._document_state[new_session] = {
                            "target_id": self.target_id,
                            "generation": 0,
                            "url": info.get("url"),
                            "document_url": info.get("url"),
                            "frame_id": None,
                            "loader_id": None,
                        "allowed": True,
                    }
                    registration_generation = 0
                    registration_url = info.get("url")
                    await self._seed_document_frame(new_session)
            # Run the old-session Network.disable (defense in depth — keeps
            # background-tab traffic out of the global event buffer; the
            # consumer-side filter in wait_for_network_idle is the actual
            # correctness gate) in parallel with the four enables on the new
            # session. Different sessions, independent CDP requests. Keeps
            # the synchronous reply under the helper's 5s IPC read timeout
            # even on a remote daemon — sequentially these would have stacked
            # to ~22s worst case.
            tasks = []
            if old_session and old_session != new_session and (owned is None or old_session in owned.get("sessions", [])):
                async def disable_old():
                    try:
                        await asyncio.wait_for(
                            self.cdp.send_raw("Network.disable", session_id=old_session),
                            timeout=2,
                        )
                    except Exception: pass
                tasks.append(disable_old())
            tasks.append(self._enable_default_domains(new_session))
            await asyncio.gather(*tasks)
            if owned is not None:
                state = self._document_state.get(new_session)
                try:
                    live = (await self.cdp.send_raw(
                        "Target.getTargetInfo", {"targetId": self.target_id}
                    )).get("targetInfo", {})
                except Exception:
                    return {"tab_guard": "refused", "target_id": self.target_id}
                if (not self._guard_policy_active or guard_run != self._guarded_run_id
                        or self._authorization_epoch != req["tab_guard_epoch"] + 1
                        or new_session not in self._guarded_sessions
                        or self.target_id not in self._guarded_targets
                        or self._session_targets.get(new_session) != self.target_id
                        or not isinstance(state, dict) or state.get("allowed") is not True
                        or state.get("generation") != registration_generation
                        or state.get("document_url") != registration_url
                        or live.get("url") != state.get("document_url")
                        or not _guard_url_allowed(live.get("url"))):
                    return {"tab_guard": "refused", "target_id": self.target_id}
            # 🐴 tab-marker title prefix is purely cosmetic — fire-and-forget so
            # it doesn't add to the synchronous IPC budget.
            self._schedule_tab_marker(new_session)
            return {"session_id": new_session, **({"tab_guard": "ok"} if owned is not None else {})}
        if meta == "pending_dialog": return {"dialog": self.dialog}
        if meta == "shutdown":
            # Flip the barrier synchronously with recovery registration, then
            # cancel/drain existing handlers. In particular, a CDP replay that
            # never answers must not prevent Cloud cleanup from being attempted.
            if self._shutting_down:
                return {"error": "shutdown already in progress"}
            self._shutting_down = True
            if not await self._cancel_and_drain_recoveries():
                # Preserve the daemon as a retryable cleanup authority. The
                # strict caller will leave its endpoint and PID file intact.
                self._shutting_down = False
                return {"error": "stale-session recovery did not stop"}
            await self._retry_overflow_cleanup_sessions()
            try:
                stop_remote(strict=True)
            except Exception as e:
                # A failed Cloud stop must leave the daemon usable so a later
                # shutdown request can retry the billable-browser cleanup.
                async with self._session_state_lock:
                    self._shutting_down = False
                return {"error": str(e)}
            self.stop.set()
            return {"ok": True}

        method = req["method"]
        params = req.get("params") or {}
        # Browser-level Target.* calls must not use a session (stale or otherwise).
        # For everything else, explicit session in req wins; else default.
        sid = None if method.startswith("Target.") else (req.get("session_id") or self.session)
        try:
            guard_identity = None
            if self._guard_policy_active or "tab_guard_run" in req:
                guard_identity = await self._validate_dispatch_identity(req, sid, method, params)
                if guard_identity is None:
                    return _guard_refusal("tab guard authorization is stale or invalid")
                if method == "Target.sendMessageToTarget":
                    params = self._remember_legacy_command(guard_identity, params)
                    if params is None:
                        return _guard_refusal("tab guard authorization is stale or invalid")
                if guard_identity is not None and not self._dispatch_identity_state_current(guard_identity):
                    return _guard_refusal("tab guard authorization is stale or invalid")
            overflow_attach_lock_held = False
            guarded_attach_slot_held = False
            if method == "Target.attachToTarget" and guard_identity is not None:
                # Bound in-flight guarded attaches so a history overflow that
                # occurs during dispatch still has one cleanup slot per reply.
                await self._guarded_attach_slots.acquire()
                guarded_attach_slot_held = True
                if not await self._dispatch_identity_current(guard_identity):
                    self._guarded_attach_slots.release()
                    guarded_attach_slot_held = False
                    return _guard_refusal("tab guard authorization is stale or invalid")
            if (method == "Target.attachToTarget" and guard_identity is not None
                    and (self._overflow_cleanup_sessions
                         or self._pending_detached_sessions_overflowed)):
                # Serialize overflow-time attach preflight through cleanup so
                # concurrent requests cannot all pass an empty-capacity check.
                await self._overflow_attach_lock.acquire()
                overflow_attach_lock_held = True
                await self._retry_overflow_cleanup_sessions()
                if self._overflow_cleanup_sessions:
                    self._overflow_attach_lock.release()
                    overflow_attach_lock_held = False
                    self._guarded_attach_slots.release()
                    guarded_attach_slot_held = False
                    return _guard_refusal(
                        "pending overflow session cleanup; refusing attach registration"
                    )
            if (method == "Target.attachToTarget" and guard_identity is not None
                    and self._pending_detached_sessions_overflowed
                    and len(self._overflow_cleanup_sessions) >= MAX_OVERFLOW_CLEANUP_RETRIES):
                if overflow_attach_lock_held:
                    self._overflow_attach_lock.release()
                    overflow_attach_lock_held = False
                if guarded_attach_slot_held:
                    self._guarded_attach_slots.release()
                    guarded_attach_slot_held = False
                return _guard_refusal(
                    "pending detach history overflow; cleanup capacity exhausted"
                )
            result = await self.cdp.send_raw(method, params, session_id=sid)
            navigation_dispatch = (
                guard_identity is not None and guard_identity.get("method") == "Page.navigate"
            )
            if (guard_identity is not None
                    and not await (self._navigation_identity_current(guard_identity)
                                   if navigation_dispatch
                                   else self._dispatch_identity_current(guard_identity))):
                if overflow_attach_lock_held:
                    self._overflow_attach_lock.release()
                    overflow_attach_lock_held = False
                if guarded_attach_slot_held:
                    self._guarded_attach_slots.release()
                    guarded_attach_slot_held = False
                return _guard_refusal("tab guard authorization was revoked during dispatch")
            if method == "Target.createBrowserContext" and guard_identity is not None:
                context_id = result.get("browserContextId")
                if context_id:
                    self._guarded_contexts.add(context_id)
            elif method == "Target.attachToTarget":
                attached_session = result.get("sessionId")
                target_id = params.get("targetId")
                if attached_session and target_id:
                    if self._pending_detached_sessions_overflowed:
                        if attached_session in self._pending_detached_sessions:
                            self._pending_detached_sessions.pop(attached_session, None)
                            self._revoked_sessions.add(attached_session)
                            if overflow_attach_lock_held:
                                self._overflow_attach_lock.release()
                                overflow_attach_lock_held = False
                            if guarded_attach_slot_held:
                                self._guarded_attach_slots.release()
                                guarded_attach_slot_held = False
                            return _guard_refusal(
                                "Target.attachToTarget session was detached before registration"
                            )
                        # Record the session before awaiting detach so cancellation
                        # cannot lose the only retry handle for a known attachment.
                        if len(self._overflow_cleanup_sessions) < MAX_OVERFLOW_CLEANUP_RETRIES:
                            self._overflow_cleanup_sessions[attached_session] = None
                        try:
                            await self.cdp.send_raw(
                                "Target.detachFromTarget", {"sessionId": attached_session}
                            )
                        except Exception as exc:
                            log(
                                "tab guard failed to detach overflow-refused session "
                                f"{attached_session}: {exc}"
                            )
                        else:
                            self._overflow_cleanup_sessions.pop(attached_session, None)
                        if overflow_attach_lock_held:
                            self._overflow_attach_lock.release()
                            overflow_attach_lock_held = False
                        if guarded_attach_slot_held:
                            self._guarded_attach_slots.release()
                            guarded_attach_slot_held = False
                        return _guard_refusal(
                            "pending detach history overflow; refusing attach registration"
                        )
                    if attached_session in self._pending_detached_sessions:
                        self._pending_detached_sessions.pop(attached_session, None)
                        self._revoked_sessions.add(attached_session)
                        if overflow_attach_lock_held:
                            self._overflow_attach_lock.release()
                            overflow_attach_lock_held = False
                        if guarded_attach_slot_held:
                            self._guarded_attach_slots.release()
                            guarded_attach_slot_held = False
                        return _guard_refusal(
                            "Target.attachToTarget session was detached before registration"
                        )
                    self._revoked_sessions.discard(attached_session)
                    self._session_targets[attached_session] = target_id
                    if guard_identity is not None:
                        self._guarded_targets.add(target_id)
                        self._guarded_sessions.add(attached_session)
                        self._guard_policy_active = True
                        self._document_state[attached_session] = {
                            "target_id": target_id,
                            "generation": 0,
                            "url": req.get("tab_guard_url"),
                            "document_url": req.get("tab_guard_url"),
                            "frame_id": None,
                            "loader_id": None,
                            "allowed": _guard_url_allowed(req.get("tab_guard_url")),
                        }
                        await self._seed_document_frame(attached_session)
                        dispatch_current = await self._dispatch_identity_current(guard_identity)
                        attached_state = self._document_state.get(attached_session)
                        if (not dispatch_current or not self._guard_policy_active
                                or guard_identity.get("run_id") != self._guarded_run_id
                                or guard_identity.get("epoch") != self._authorization_epoch
                                or attached_session not in self._guarded_sessions
                                or self._session_targets.get(attached_session) != target_id
                                or target_id not in self._guarded_targets
                                or not isinstance(attached_state, dict)
                                or attached_state.get("allowed") is not True):
                            try:
                                await self.cdp.send_raw(
                                    "Target.detachFromTarget", {"sessionId": attached_session}
                                )
                            except Exception as exc:
                                log(f"tab guard failed to detach stale session {attached_session}: {exc}")
                            self._session_targets.pop(attached_session, None)
                            self._guarded_sessions.discard(attached_session)
                            self._document_state.pop(attached_session, None)
                            if overflow_attach_lock_held:
                                self._overflow_attach_lock.release()
                                overflow_attach_lock_held = False
                            if guarded_attach_slot_held:
                                self._guarded_attach_slots.release()
                                guarded_attach_slot_held = False
                            return _guard_refusal("tab guard authorization was revoked during attach")
            elif method == "Target.detachFromTarget":
                detached_session = params.get("sessionId")
                self._session_targets.pop(detached_session, None)
                if guard_identity is not None:
                    self._guarded_sessions.discard(detached_session)
                    self._document_state.pop(detached_session, None)
            elif method == "Target.closeTarget" and result.get("success"):
                closed_target = params.get("targetId")
                self._guarded_targets.discard(closed_target)
                for attached, target in list(self._session_targets.items()):
                    if target == closed_target:
                        self._session_targets.pop(attached, None)
                        self._guarded_sessions.discard(attached)
                        self._document_state.pop(attached, None)
            elif method == "Target.createTarget" and guard_identity is not None:
                created_target = result.get("targetId")
                if created_target:
                    self._guarded_targets.add(created_target)
            if overflow_attach_lock_held:
                self._overflow_attach_lock.release()
                overflow_attach_lock_held = False
            if guarded_attach_slot_held:
                self._guarded_attach_slots.release()
                guarded_attach_slot_held = False
            return {"result": result}
        except asyncio.CancelledError:
            if locals().get("overflow_attach_lock_held", False):
                self._overflow_attach_lock.release()
            if locals().get("guarded_attach_slot_held", False):
                self._guarded_attach_slots.release()
            raise
        except Exception as e:
            if locals().get("overflow_attach_lock_held", False):
                self._overflow_attach_lock.release()
            if locals().get("guarded_attach_slot_held", False):
                self._guarded_attach_slots.release()
            if method == "Target.sendMessageToTarget" and guard_identity is not None:
                try:
                    nested = json.loads(params.get("message", ""))
                    self._legacy_commands.pop((guard_identity["session_id"], nested.get("id")), None)
                except (TypeError, ValueError, AttributeError):
                    pass
            msg = str(e)
            if guard_identity is not None:
                return {"error": msg}
            if "Session with given id not found" in msg and sid:
                # Explicit session callers asked for that exact session; do not
                # silently redirect them to the daemon's current tab.
                if req.get("session_id"):
                    return {"error": msg}
                recovery_task = self._begin_recovery()
                if recovery_task is None:
                    return {"error": "daemon is shutting down"}
                try:
                    recovered_here = False
                    async with self._session_state_lock:
                        if self._shutting_down:
                            return {"error": "daemon is shutting down"}
                        replacement_session = self._session_replacements.get(sid)
                        if replacement_session is None and sid == self.session:
                            log(f"stale session {sid}, re-attaching")
                            if not await self.attach_first_page(
                                replaces_session=sid, enable_domains=False
                            ):
                                return {"error": msg}
                            replacement_session = self._session_replacements.get(sid)
                            recovered_here = replacement_session is not None
                    if recovered_here:
                        await self._enable_default_domains(replacement_session)
                    # Retry only on a session known to replace this exact stale
                    # session. self.session may instead have changed because the
                    # user deliberately switched tabs while this request waited.
                    if replacement_session:
                        try:
                            return {"result": await self.cdp.send_raw(
                                method, params, session_id=replacement_session
                            )}
                        except Exception as retry_error:
                            return {"error": str(retry_error)}
                finally:
                    self._finish_recovery(recovery_task)
            return {"error": msg}

    async def _validate_dispatch_identity(self, req, session_id, method, params):
        """Recheck a helper-pinned identity at the daemon boundary."""
        owned = req.get("tab_guard")
        identity = {
            "method": method,
            "run_id": req.get("tab_guard_run"),
            "session_id": req.get("tab_guard_session_id"),
            "target_id": req.get("tab_guard_target_id"),
            "epoch": req.get("tab_guard_epoch"),
            "generation": req.get("tab_guard_document_generation"),
            "document_url": req.get("tab_guard_url"),
        }
        sid = (params.get("sessionId")
               if method in {"Target.detachFromTarget", "Target.sendMessageToTarget"}
               else session_id)
        target_id = (self._session_targets.get(sid) if sid else
                     params.get("targetId") or identity["target_id"])
        bootstrap = {"Target.createBrowserContext", "Target.createTarget", "Target.getTargets"}
        if not isinstance(owned, dict) or not isinstance(identity["run_id"], str):
            return None
        if self._guarded_run_id is None:
            if method not in bootstrap or identity["epoch"] != self._authorization_epoch:
                return None
        elif (identity["run_id"] != self._guarded_run_id
                or identity["epoch"] != self._authorization_epoch):
            return None
        if method.startswith("Target."):
            if method not in _GUARDED_TARGET_METHODS:
                return None
        elif method not in _GUARDED_SESSION_METHODS:
            return None
        if method == "Page.navigate" and not _guard_url_allowed(params.get("url")):
            return None
        if (method == "Target.createTarget"
                and (not isinstance(params.get("url", "about:blank"), str)
                     or not _guard_url_allowed(params.get("url", "about:blank")))):
            return None
        if method == "Target.sendMessageToTarget":
            try:
                nested = json.loads(params.get("message", ""))
            except (TypeError, ValueError):
                return None
            if not isinstance(nested, dict) or not isinstance(nested.get("method"), str):
                return None
            identity["method"] = nested["method"]
            nested_params = nested.get("params") or {}
            if (not isinstance(nested_params, dict)
                    or nested["method"] not in _GUARDED_SESSION_METHODS
                    or "sessionId" in nested):
                return None
            if (nested["method"] == "Page.navigate"
                    and not _guard_url_allowed(nested_params.get("url"))):
                return None
        if method in {"Target.createBrowserContext", "Target.getTargets"}:
            # Bootstrap is accepted. Latch policy before handle() awaits the
            # CDP operation, so concurrent guardless requests fail closed.
            self._guarded_run_id = identity["run_id"]
            self._guard_policy_active = True
            return {**identity, "target_id": None, "session_id": None, "generation": None}
        if method == "Target.createTarget":
            context_id = params.get("browserContextId")
            if (not isinstance(context_id, str)
                    or context_id not in set(owned.get("contexts", []))
                    or context_id not in self._guarded_contexts):
                return None
            # createTarget bootstrap is accepted; latch before CDP dispatch.
            self._guarded_run_id = identity["run_id"]
            self._guard_policy_active = True
            return {**identity, "target_id": None, "session_id": None, "generation": None}
        if identity["target_id"] != target_id:
            return None
        if (identity["target_id"] not in set(owned.get("tabs", []))
                or identity["target_id"] not in self._guarded_targets):
            return None
        target_document_methods = {
            "Target.closeTarget", "Target.activateTarget", "Target.attachToTarget",
        }
        if sid is None and method in target_document_methods:
            sid = next((mapped for mapped, target in self._session_targets.items()
                        if target == target_id), None)
            if sid is None and method == "Target.attachToTarget":
                # A run-created target is owned before its first session exists.
                # Permit that initial attach only from the daemon's ownership
                # record, with an empty caller snapshot. There is no document
                # snapshot yet, so bind authorization to the helper's URL and
                # establish it against live target info below.
                if (identity["session_id"] is not None
                        or identity["generation"] is not None
                        or not _guard_url_allowed(req.get("tab_guard_url"))):
                    return None
                identity["document_url"] = req.get("tab_guard_url")
            else:
                mapped_state = self._document_state.get(sid)
                if (not sid or identity["session_id"] != sid
                        or not isinstance(mapped_state, dict)
                        or identity["generation"] != mapped_state.get("generation")
                        or identity["document_url"] != mapped_state.get("document_url")
                        or mapped_state.get("allowed") is not True):
                    return None
                identity["session_id"] = sid
                identity["generation"] = mapped_state["generation"]
                identity["document_url"] = mapped_state.get("document_url")
        # Resolve the session first, then read its current document snapshot.
        # The mapping may have been found by targetId above.
        state = self._document_state.get(sid)
        if sid:
            if (identity["session_id"] != sid or sid not in self._guarded_sessions
                    or not isinstance(state, dict)
                    or identity["generation"] != state.get("generation")
                    or identity["document_url"] != state.get("document_url")
                    or not state.get("allowed")):
                return None
            identity["document_url"] = state.get("document_url")
        elif method == "Target.attachToTarget":
            identity["session_id"] = None
            identity["generation"] = None
        elif method in {"Target.closeTarget", "Target.activateTarget", "Target.getTargetInfo"}:
            identity["session_id"] = None
            identity["generation"] = None
            identity["document_url"] = req.get("tab_guard_url")
        else:
            mapped = next((session for session, target in self._session_targets.items()
                           if target == target_id), None)
            mapped_state = self._document_state.get(mapped)
            if (not mapped or identity["session_id"] != mapped
                    or not isinstance(mapped_state, dict)
                    or identity["generation"] != mapped_state.get("generation")
                    or identity["document_url"] != mapped_state.get("document_url")
                    or not mapped_state.get("allowed")):
                return None
            identity["session_id"] = mapped
            identity["generation"] = mapped_state["generation"]
            identity["document_url"] = mapped_state.get("document_url")
        if identity["target_id"] is not None:
            try:
                info = (await self.cdp.send_raw(
                    "Target.getTargetInfo", {"targetId": identity["target_id"]}
                )).get("targetInfo", {})
            except Exception:
                return None
            snapshot_url = identity.get("document_url")
            if not isinstance(snapshot_url, str):
                snapshot_url = req.get("tab_guard_url")
            if (not isinstance(snapshot_url, str)
                    or info.get("url") != snapshot_url
                    or not _guard_url_allowed(info.get("url"))):
                return None
            identity["live_url"] = snapshot_url
        return identity

    def _dispatch_identity_state_current(self, identity):
        """Synchronous last check immediately before entering CDP transport."""
        if identity["session_id"] is None:
            target_id = identity["target_id"]
            mapped_sessions = [sid for sid, target in self._session_targets.items()
                               if target == target_id] if target_id else []
            return bool(
                identity["run_id"] == self._guarded_run_id
                and identity["epoch"] == self._authorization_epoch
                and (target_id is None or target_id in self._guarded_targets)
                and all(sid in self._guarded_sessions for sid in mapped_sessions)
            )
        state = self._document_state.get(identity["session_id"])
        return bool(
            self._guard_policy_active
            and identity["run_id"] == self._guarded_run_id
            and identity["epoch"] == self._authorization_epoch
            and identity["session_id"] in self._guarded_sessions
            and self._session_targets.get(identity["session_id"]) == identity["target_id"]
            and isinstance(state, dict)
            and state.get("generation") == identity["generation"]
            and state.get("document_url") == identity["document_url"]
            and state.get("allowed") is True
        )

    async def _dispatch_identity_current(self, identity):
        if not self._dispatch_identity_state_current(identity):
            return False
        if identity["target_id"] is None or identity["method"] == "Target.closeTarget":
            return self._dispatch_identity_state_current(identity)
        try:
            info = (await self.cdp.send_raw(
                "Target.getTargetInfo", {"targetId": identity["target_id"]}
            )).get("targetInfo", {})
        except Exception:
            return False
        # The metadata lookup yields to reset, detach, navigation and target
        # replacement. Recheck every authorization component after that await.
        return bool(
            self._dispatch_identity_state_current(identity)
            and info.get("url") == identity.get("live_url")
            and _guard_url_allowed(info.get("url"))
        )

    async def _navigation_identity_current(self, identity):
        """Accept a successful guarded navigation after its own document event."""
        sid, target_id = identity.get("session_id"), identity.get("target_id")
        generation = identity.get("generation")
        if not isinstance(generation, int):
            return False
        state = self._document_state.get(sid)
        if (not self._guard_policy_active or identity.get("run_id") != self._guarded_run_id
                or identity.get("epoch") != self._authorization_epoch
                or sid not in self._guarded_sessions or target_id not in self._guarded_targets
                or self._session_targets.get(sid) != target_id or not isinstance(state, dict)
                or state.get("allowed") is not True
                or state.get("generation") not in {generation, generation + 1}):
            return False
        try:
            info = (await self.cdp.send_raw(
                "Target.getTargetInfo", {"targetId": target_id}
            )).get("targetInfo", {})
        except Exception:
            return False
        state = self._document_state.get(sid)
        return bool(
            self._guard_policy_active and identity.get("run_id") == self._guarded_run_id
            and identity.get("epoch") == self._authorization_epoch
            and sid in self._guarded_sessions and target_id in self._guarded_targets
            and self._session_targets.get(sid) == target_id and isinstance(state, dict)
            and state.get("allowed") is True
            and state.get("generation") in {generation, generation + 1}
            and info.get("url") == state.get("document_url")
            and _guard_url_allowed(info.get("url"))
        )

    def _remember_legacy_command(self, identity, params):
        try:
            message = json.loads(params.get("message", ""))
        except (TypeError, ValueError):
            return
        command_id = message.get("id") if isinstance(message, dict) else None
        if (not isinstance(command_id, (int, str)) or isinstance(command_id, bool)
                or command_id == ""):
            return
        self._legacy_wire_id += 1
        wire_id = self._legacy_wire_id
        message["id"] = wire_id
        params["message"] = json.dumps(message, separators=(",", ":"))
        key = (identity["session_id"], wire_id)
        self._legacy_commands[key] = {
            **identity,
            "caller_id": command_id,
            "document_url": identity["document_url"],
        }
        while len(self._legacy_commands) > BUF:
            self._legacy_commands.pop(next(iter(self._legacy_commands)))
        return params


async def serve(d):
    async def handler(reader, writer):
        try:
            line = await reader.readline()
            if not line: return
            resp = await d.handle(json.loads(line))
            writer.write((json.dumps(resp, default=str) + "\n").encode())
            await writer.drain()
        except Exception as e:
            log(f"conn: {e}")
            try:
                writer.write((json.dumps({"error": str(e)}) + "\n").encode())
                await writer.drain()
            except Exception:
                pass
        finally:
            writer.close()

    serve_task = asyncio.create_task(ipc.serve(NAME, handler))
    stop_task = asyncio.create_task(d.stop.wait())
    await asyncio.sleep(0.05)  # let serve() bind so sock_addr() resolves to the live endpoint
    log(f"listening on {ipc.sock_addr(NAME)} (name={NAME}, remote={REMOTE_ID or 'local'})")
    try:
        await asyncio.wait({serve_task, stop_task}, return_when=asyncio.FIRST_COMPLETED)
        if serve_task.done(): await serve_task  # surfaces a serve crash
    finally:
        for t in (serve_task, stop_task):
            t.cancel()
            try: await t
            except (asyncio.CancelledError, Exception): pass
        # A server crash/cancellation does not pass through meta=shutdown.
        # Establish the same recovery barrier before touching owned targets.
        d._shutting_down = True
        recoveries_drained = await d._cancel_and_drain_recoveries()
        # Named non-cloud daemons create one dedicated background tab. Shutdown
        # has blocked new recovery and drained active recovery before setting
        # d.stop (or finalization established the barrier after a server crash).
        # Take the same locks, in the same order as recovery, so cleanup closes
        # exactly the final daemon-owned target and never races creation.
        if recoveries_drained:
            async with d._session_state_lock:
                async with d._dedicated_target_lock:
                    if d.dedicated_target_id and d.cdp:
                        try:
                            await d.cdp.send_raw(
                                "Target.closeTarget", {"targetId": d.dedicated_target_id}
                            )
                            d.dedicated_target_id = None
                        except Exception as e:
                            log(f"close dedicated tab on shutdown: {e}")
        else:
            log("skip dedicated-tab cleanup: stale-session recovery did not stop")
        ipc.cleanup_endpoint(NAME)


async def main():
    d = Daemon()
    await d.start()
    await serve(d)


def already_running():
    # Ping handshake (not a bare connect) so a stale .port file + port reuse
    # after a daemon crash doesn't make us mistake an unrelated listener for ours.
    return ipc.ping(NAME, timeout=1.0)


if __name__ == "__main__":
    if already_running():
        print(f"daemon already running on {SOCK}", file=sys.stderr)
        sys.exit(0)
    open(LOG, "w").close()
    _publish_own_pid()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        log(f"fatal: {e}")
        sys.exit(1)
    finally:
        stop_remote()
        try: os.unlink(PID)
        except FileNotFoundError: pass
