"""Fixed S-EDU login adapter for a bound Browser Harness CDP session."""
import asyncio
import struct
import time
from urllib.parse import urlparse


ADAPTER = "sedu-v1"
INITIAL_LOGIN_URL = "https://s-edu.cloud/accounts/login/"
FINAL_LOGIN_PATH = "/npms/accounts/login/"
FORM_ACTION = "https://s-edu.cloud/npms/accounts/login/"
PROTECTED_PATH = "/npms/"
PROTECTED_INDICATORS = (
    'a[href="/npms/schools/list/?tab=list"]',
    'a[href="/npms/accounts/profile/"]',
    'a[href="/npms/accounts/logout/"]',
)
HUMAN_MARKERS = (
    "captcha", "recaptcha", "hcaptcha", "otp", "mfa", "인증번호",
    "2단계", "보안문자", "새 기기",
)
_SECRET_HEADER = struct.Struct("!II")
_MAX_PAYLOAD_BYTES = 16 * 1024
_MAX_FIELD_BYTES = _MAX_PAYLOAD_BYTES - _SECRET_HEADER.size - 1
_POST_SUBMIT_SECONDS = 15
_FORM_WAIT_SECONDS = 15
ADAPTER_TIMEOUT_SECONDS = 35
_TRANSIENT_NAVIGATION_ERRORS = (
    "execution context was destroyed",
    "cannot find context with specified id",
    "inspected target navigated or closed",
)


def _result(state):
    """Return the exact versioned ``sedu-v1`` adapter result schema."""
    return {"status": "success" if state == "active" else "failed", "state": state}


# Fixed expressions contain no caller-controlled or secret text.
_VALIDATE_FORM = r"""(() => {
 const u=document.querySelector('input[name="username"]');
 const p=document.querySelector('input[name="password"]');
 const s=document.querySelector('button[type="submit"],input[type="submit"]');
 const f=u && p && u.form && u.form===p.form && s && s.form===u.form ? u.form : null;
 return {href:location.href,title:document.title||'',body:(document.body&&document.body.innerText||'').slice(0,8192),
         ready:document.readyState,user:!!u,password:!!p,submit:!!s,
         action:f ? f.action : '',method:f ? (f.method||'get').toLowerCase() : ''};
})()"""
_DOCUMENT = "document"
_FILL_FUNCTION = r"""function(u,p){
 const a=this.querySelector('input[name="username"]');
 const b=this.querySelector('input[name="password"]');
 if(!a||!b||!a.form||a.form!==b.form)return false;
 a.value=u;a.dispatchEvent(new Event('input',{bubbles:true}));a.dispatchEvent(new Event('change',{bubbles:true}));
 b.value=p;b.dispatchEvent(new Event('input',{bubbles:true}));b.dispatchEvent(new Event('change',{bubbles:true}));
 return true;
}"""
_SUBMIT_FUNCTION = r"""function(){
 const a=this.querySelector('input[name="username"]');
 const b=this.querySelector('input[name="password"]');
 const s=this.querySelector('button[type="submit"],input[type="submit"]');
 if(!a||!b||!s||!a.form||a.form!==b.form||s.form!==a.form)return false;
 s.click();return true;
}"""
_SNAPSHOT = f"""(() => ({{href:location.href,title:document.title||'',
 body:(document.body&&document.body.innerText||'').slice(0,8192),
 protected:[{','.join(f'!!document.querySelector({value!r})' for value in PROTECTED_INDICATORS)}],
 ready:document.readyState,identity:performance.timeOrigin}}))()"""


def encode_payload(username, password):
    """Encode credentials for trusted callers without placing them in JSON."""
    if not isinstance(username, bytes) or not isinstance(password, bytes):
        raise TypeError("S-EDU fields must be bytes")
    if (not (1 <= len(username) <= _MAX_FIELD_BYTES and 1 <= len(password) <= _MAX_FIELD_BYTES)
            or _SECRET_HEADER.size + len(username) + len(password) > _MAX_PAYLOAD_BYTES):
        raise ValueError("invalid S-EDU credential lengths")
    return _SECRET_HEADER.pack(len(username), len(password)) + username + password


def _parse_payload(payload):
    if not isinstance(payload, (bytes, bytearray, memoryview)) or len(payload) < _SECRET_HEADER.size:
        raise ValueError("invalid_sedu_secret")
    user_len, password_len = _SECRET_HEADER.unpack_from(payload)
    if (not (1 <= user_len <= _MAX_FIELD_BYTES and 1 <= password_len <= _MAX_FIELD_BYTES)
            or _SECRET_HEADER.size + user_len + password_len > _MAX_PAYLOAD_BYTES):
        raise ValueError("invalid_sedu_secret")
    if len(payload) != _SECRET_HEADER.size + user_len + password_len:
        raise ValueError("invalid_sedu_secret")
    mutable = bytearray(payload)
    user_start = _SECRET_HEADER.size
    password_start = user_start + user_len
    try:
        username = mutable[user_start:password_start].decode("utf-8", "strict")
        password = mutable[password_start:].decode("utf-8", "strict")
    except UnicodeDecodeError:
        for index in range(len(mutable)):
            mutable[index] = 0
        raise ValueError("invalid_sedu_secret") from None
    if not username or not password or "\x00" in username or "\x00" in password:
        for index in range(len(mutable)):
            mutable[index] = 0
        raise ValueError("invalid_sedu_secret")
    return username, password, mutable


def _is_bound(daemon, tx):
    return (daemon.target_id == tx.target_id and daemon.session == tx.session_id
            and daemon._session_generation == tx.generation)


async def _call(daemon, tx, method, params, deadline=None):
    if not _is_bound(daemon, tx):
        raise RuntimeError("stale_binding")
    remaining = min(tx.deadline, deadline or tx.deadline) - time.monotonic()
    if remaining <= 0:
        raise asyncio.TimeoutError
    result = await asyncio.wait_for(
        daemon.cdp.send_raw(method, params, session_id=tx.session_id), remaining
    )
    if not _is_bound(daemon, tx):
        raise RuntimeError("stale_binding")
    return result


async def _wait_for_form(daemon, tx, loader_id, adapter_deadline):
    """Wait for the redirected document and its complete, exact login form."""
    deadline = min(adapter_deadline, time.monotonic() + _FORM_WAIT_SECONDS)
    while time.monotonic() < deadline:
        frame = (await _call(daemon, tx, "Page.getFrameTree", {}, deadline)) \
            .get("frameTree", {}).get("frame", {})
        if frame.get("loaderId") != loader_id:
            await asyncio.sleep(0.05)
            continue
        form = _remote_value(await _call(daemon, tx, "Runtime.evaluate", {
            "expression": _VALIDATE_FORM, "returnByValue": True,
        }, deadline))
        if not isinstance(form, dict):
            raise RuntimeError("invalid_login_document")
        if _limited(form) or _challenge(form):
            return form
        parsed = urlparse(form.get("href") or "")
        if parsed.scheme != "https" or parsed.netloc != "s-edu.cloud":
            raise RuntimeError("invalid_login_origin")
        if form.get("ready") == "complete" and _valid_login_url(form.get("href")):
            return form
        await asyncio.sleep(0.05)
    raise asyncio.TimeoutError


async def _post_submit_snapshot(daemon, tx, deadline):
    """Read through the short window where navigation destroys the old context."""
    while time.monotonic() < deadline:
        try:
            return _remote_value(await _call(daemon, tx, "Runtime.evaluate", {
                "expression": _SNAPSHOT, "returnByValue": True,
            }, deadline))
        except RuntimeError as exc:
            if not any(marker in str(exc).casefold() for marker in _TRANSIENT_NAVIGATION_ERRORS):
                raise
            await asyncio.sleep(0.05)
    raise asyncio.TimeoutError


def _remote_value(response):
    if response.get("exceptionDetails"):
        raise RuntimeError("javascript_failure")
    return response.get("result", {}).get("value")


def _limited(snapshot):
    text = f"{snapshot.get('title', '')}\n{snapshot.get('body', '')}".casefold()
    return "429 too many requests" in text or ("too many requests" in text and "429" in text)


def _challenge(snapshot):
    text = f"{snapshot.get('title', '')}\n{snapshot.get('body', '')}".casefold()
    return any(marker in text for marker in HUMAN_MARKERS)


def _valid_login_url(value):
    parsed = urlparse(value or "")
    return parsed.scheme == "https" and parsed.netloc == "s-edu.cloud" and parsed.path == FINAL_LOGIN_PATH


async def run(daemon, tx, payload):
    """Consume one payload and perform the single fixed S-EDU login journey."""
    adapter_deadline = min(tx.deadline, time.monotonic() + ADAPTER_TIMEOUT_SECONDS)
    username = password = None
    mutable = None
    try:
        username, password, mutable = _parse_payload(payload)
        navigation = await _call(daemon, tx, "Page.navigate", {"url": INITIAL_LOGIN_URL}, adapter_deadline)
        if navigation.get("errorText"):
            return _result("failed")
        loader_id = navigation.get("loaderId")
        if not isinstance(loader_id, str) or not loader_id:
            return _result("failed")

        form = await _wait_for_form(daemon, tx, loader_id, adapter_deadline)
        if _limited(form):
            return _result("locked")
        if _challenge(form):
            return _result("human_challenge")
        if (form.get("ready") != "complete" or not _valid_login_url(form.get("href"))
                or form.get("action") != FORM_ACTION or form.get("method") != "post"
                or not all(form.get(key) is True for key in ("user", "password", "submit"))):
            return _result("failed")

        document = (await _call(daemon, tx, "Runtime.evaluate", {"expression": _DOCUMENT}, adapter_deadline)) \
            .get("result", {}).get("objectId")
        if not document:
            return _result("failed")
        # Page listeners can synchronously echo either input event through any
        # enabled CDP domain, so suppression starts before the first fill.
        daemon.suppress_sensitive_events(tx.session_id)
        filled = await _call(daemon, tx, "Runtime.callFunctionOn", {
            "objectId": document, "functionDeclaration": _FILL_FUNCTION,
            "arguments": [{"value": username}, {"value": password}], "returnByValue": True,
        }, adapter_deadline)
        if filled.get("exceptionDetails") or filled.get("result", {}).get("value") is not True:
            return _result("failed")
        post_deadline = min(adapter_deadline, time.monotonic() + _POST_SUBMIT_SECONDS)
        pre_submit = _remote_value(await _call(daemon, tx, "Runtime.evaluate", {
            "expression": _SNAPSHOT, "returnByValue": True,
        }, post_deadline))
        if not isinstance(pre_submit, dict):
            return _result("failed")
        submitted = await _call(daemon, tx, "Runtime.callFunctionOn", {
            "objectId": document, "functionDeclaration": _SUBMIT_FUNCTION, "returnByValue": True,
        }, post_deadline)
        if submitted.get("exceptionDetails") or submitted.get("result", {}).get("value") is not True:
            return _result("failed")

        while time.monotonic() < post_deadline:
            snapshot = await _post_submit_snapshot(daemon, tx, post_deadline)
            if not isinstance(snapshot, dict):
                return _result("failed")
            parsed = urlparse(snapshot.get("href") or "")
            if parsed.scheme != "https" or parsed.netloc != "s-edu.cloud":
                return _result("failed")
            if _limited(snapshot):
                return _result("locked")
            if _challenge(snapshot):
                return _result("human_challenge")
            if (parsed.path == PROTECTED_PATH and snapshot.get("ready") == "complete"
                    and snapshot.get("protected") == [True] * len(PROTECTED_INDICATORS)):
                return _result("active")
            transitioned = any((
                snapshot.get("href") != pre_submit.get("href"),
                snapshot.get("ready") != pre_submit.get("ready"),
                snapshot.get("identity") != pre_submit.get("identity"),
            ))
            if transitioned and parsed.path == FINAL_LOGIN_PATH and snapshot.get("ready") == "complete":
                return _result("reauth_required")
            if snapshot.get("ready") == "complete" and parsed.path != FINAL_LOGIN_PATH:
                return _result("failed")
            await asyncio.sleep(0.05)
        return _result("timeout")
    except asyncio.CancelledError:
        raise
    except asyncio.TimeoutError:
        return _result("timeout")
    except (RuntimeError, ValueError, TypeError):
        return _result("failed")
    finally:
        daemon.release_sensitive_events(tx.session_id)
        username = password = None
        if mutable is not None:
            for index in range(len(mutable)):
                mutable[index] = 0
        if isinstance(payload, bytearray):
            for index in range(len(payload)):
                payload[index] = 0
        elif isinstance(payload, memoryview) and not payload.readonly:
            payload[:] = b"\0" * len(payload)
