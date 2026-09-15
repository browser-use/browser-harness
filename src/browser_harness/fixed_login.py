"""Fixed GitLab and Proxmox login adapters for bound Harness sessions."""
import asyncio
import struct
import time
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class LoginSite:
    adapter: str
    origin: str
    login_url: str
    login_path: str
    user_selector: str
    password_selector: str
    submit_selector: str
    container_selector: str
    submit_text: str
    success_kind: str


GITLAB = LoginSite(
    "gitlab-local-v1", "https://gitlab.local-properties.org",
    "https://gitlab.local-properties.org/users/sign_in", "/users/sign_in",
    "#user_login", "#user_password", "button[type=submit],input[type=submit]",
    "form", "Sign in", "gitlab",
)
PROXMOX = LoginSite(
    "proxmox-local-v1", "https://proxmox.local-properties.org:8006",
    "https://proxmox.local-properties.org:8006/", "/",
    'input[name="username"]', 'input[name="password"]', 'a[role="button"]',
    '.x-window', "Login", "proxmox",
)
SITES = {site.adapter: site for site in (GITLAB, PROXMOX)}

_SECRET_HEADER = struct.Struct("!II")
_MAX_PAYLOAD_BYTES = 16 * 1024
_MAX_FIELD_BYTES = _MAX_PAYLOAD_BYTES - _SECRET_HEADER.size - 1
_FORM_WAIT_SECONDS = 15
_POST_SUBMIT_SECONDS = 15
ADAPTER_TIMEOUT_SECONDS = 35
_TRANSIENT_NAVIGATION_ERRORS = (
    "execution context was destroyed", "cannot find context with specified id",
    "inspected target navigated or closed",
)
HUMAN_MARKERS = (
    "captcha", "recaptcha", "hcaptcha", "otp", "mfa", "two-factor", "2fa",
    "verification code", "인증번호", "2단계", "보안문자", "새 기기",
)


def _result(state):
    return {"status": "success" if state == "active" else "failed", "state": state}


def _expressions(site):
    validate = f"""(() => {{
 const u=document.querySelector({site.user_selector!r});
 const p=document.querySelector({site.password_selector!r});
 const c=[...document.querySelectorAll({site.container_selector!r})].find(e=>e.contains(u)&&e.contains(p));
 const s=[...(c||document).querySelectorAll({site.submit_selector!r})].find(e=>(e.innerText||e.value||'').trim()==={site.submit_text!r});
 const f=u&&p&&u.form&&u.form===p.form?u.form:null;
 return {{href:location.href,title:document.title||'',body:(document.body&&document.body.innerText||'').slice(0,8192),
 ready:document.readyState,user:!!u,password:!!p,submit:!!s,bound:!!c,
 action:f?f.action:'',method:f?(f.method||'get').toLowerCase():''}};
}})()"""
    if site is PROXMOX:
        fill = f"""function(u,p){{
 const a=this.querySelector({site.user_selector!r}),b=this.querySelector({site.password_selector!r}),r=this.querySelector('input[name="realm"]');
 const c=[...this.querySelectorAll({site.container_selector!r})].find(e=>e.contains(a)&&e.contains(b));
 const component=e=>{{const id=e&&e.id||'';return globalThis.Ext&&id.endsWith('-inputEl')?Ext.getCmp(id.slice(0,-8)):null;}};
 const ac=component(a),bc=component(b),rc=component(r);
 if(!c||!ac||!bc||!rc||typeof ac.setValue!=='function'||typeof bc.setValue!=='function'||typeof rc.setValue!=='function')return false;
 ac.setValue(u);bc.setValue(p);rc.setValue('pam');
 return ac.getValue()===u&&bc.getValue()===p&&rc.getValue()==='pam';
}}"""
    else:
        fill = f"""function(u,p){{
 const a=this.querySelector({site.user_selector!r});const b=this.querySelector({site.password_selector!r});
 const c=[...this.querySelectorAll({site.container_selector!r})].find(e=>e.contains(a)&&e.contains(b));
 if(!a||!b||!c)return false;a.value=u;a.dispatchEvent(new Event('input',{{bubbles:true}}));a.dispatchEvent(new Event('change',{{bubbles:true}}));
 b.value=p;b.dispatchEvent(new Event('input',{{bubbles:true}}));b.dispatchEvent(new Event('change',{{bubbles:true}}));return true;
}}"""
    if site is PROXMOX:
        submit = f"""function(){{const a=this.querySelector({site.user_selector!r}),b=this.querySelector({site.password_selector!r});const c=[...this.querySelectorAll({site.container_selector!r})].find(e=>e.contains(a)&&e.contains(b));const s=[...(c||this).querySelectorAll({site.submit_selector!r})].find(e=>(e.innerText||e.value||'').trim()==={site.submit_text!r});const button=globalThis.Ext&&s?Ext.getCmp(s.id):null;if(!c||!button||typeof button.click!=='function')return false;button.click();return true;}}"""
    else:
        submit = f"""function(){{const a=this.querySelector({site.user_selector!r}),b=this.querySelector({site.password_selector!r});const c=[...this.querySelectorAll({site.container_selector!r})].find(e=>e.contains(a)&&e.contains(b));const s=[...(c||this).querySelectorAll({site.submit_selector!r})].find(e=>(e.innerText||e.value||'').trim()==={site.submit_text!r});if(!c||!s)return false;s.click();return true;}}"""
    if site.success_kind == "gitlab":
        proof = "!!document.querySelector('meta[name=\"csrf-token\"]')&&!!document.querySelector('[data-testid=\"user-menu-toggle\"],a[href=\"/-/profile\"]')"
    else:
        proof = "![...document.querySelectorAll('.x-window')].some(e=>(e.offsetWidth||e.offsetHeight||e.getClientRects().length)&&(e.innerText||'').includes('Proxmox VE Login'))&&(()=>{const e=document.querySelector('#userinfo');return !!e&&!!(e.offsetWidth||e.offsetHeight||e.getClientRects().length)&&!!(e.innerText||e.textContent||'').trim()})()"
    snapshot = f"""(() => ({{href:location.href,title:document.title||'',body:(document.body&&document.body.innerText||'').slice(0,8192),
 protected:!!({proof}),ready:document.readyState,identity:performance.timeOrigin}}))()"""
    return validate, fill, submit, snapshot


def encode_payload(username, password):
    if not isinstance(username, bytes) or not isinstance(password, bytes):
        raise TypeError("login fields must be bytes")
    if (not (1 <= len(username) <= _MAX_FIELD_BYTES and 1 <= len(password) <= _MAX_FIELD_BYTES)
            or _SECRET_HEADER.size + len(username) + len(password) > _MAX_PAYLOAD_BYTES):
        raise ValueError("invalid login credential lengths")
    return _SECRET_HEADER.pack(len(username), len(password)) + username + password


def _parse_payload(payload):
    if not isinstance(payload, (bytes, bytearray, memoryview)) or len(payload) < _SECRET_HEADER.size:
        raise ValueError("invalid_login_secret")
    user_len, password_len = _SECRET_HEADER.unpack_from(payload)
    if (not (1 <= user_len <= _MAX_FIELD_BYTES and 1 <= password_len <= _MAX_FIELD_BYTES)
            or len(payload) != _SECRET_HEADER.size + user_len + password_len
            or len(payload) > _MAX_PAYLOAD_BYTES):
        raise ValueError("invalid_login_secret")
    mutable = bytearray(payload)
    try:
        username = mutable[8:8 + user_len].decode("utf-8", "strict")
        password = mutable[8 + user_len:].decode("utf-8", "strict")
    except UnicodeDecodeError:
        mutable[:] = b"\0" * len(mutable)
        raise ValueError("invalid_login_secret") from None
    if not username or not password or "\0" in username or "\0" in password:
        mutable[:] = b"\0" * len(mutable)
        raise ValueError("invalid_login_secret")
    return username, password, mutable


def _is_bound(daemon, tx):
    return (daemon.target_id == tx.target_id and daemon.session == tx.session_id
            and daemon._session_generation == tx.generation)


async def _call(daemon, tx, method, params, deadline):
    if not _is_bound(daemon, tx):
        raise RuntimeError("stale_binding")
    remaining = min(tx.deadline, deadline) - time.monotonic()
    if remaining <= 0:
        raise asyncio.TimeoutError
    result = await asyncio.wait_for(daemon.cdp.send_raw(method, params, session_id=tx.session_id), remaining)
    if not _is_bound(daemon, tx):
        raise RuntimeError("stale_binding")
    return result


def _remote_value(response):
    if response.get("exceptionDetails"):
        raise RuntimeError("javascript_failure")
    return response.get("result", {}).get("value")


def _same_origin(site, value):
    wanted, actual = urlparse(site.origin), urlparse(value or "")
    return actual.scheme == wanted.scheme and actual.netloc == wanted.netloc


def _challenge(snapshot):
    text = f"{snapshot.get('title', '')}\n{snapshot.get('body', '')}".casefold()
    return any(marker in text for marker in HUMAN_MARKERS)


def _locked(snapshot):
    text = f"{snapshot.get('title', '')}\n{snapshot.get('body', '')}".casefold()
    return "429 too many requests" in text or ("too many requests" in text and "429" in text)


async def _snapshot(daemon, tx, expression, deadline):
    while time.monotonic() < deadline:
        try:
            return _remote_value(await _call(daemon, tx, "Runtime.evaluate", {
                "expression": expression, "returnByValue": True}, deadline))
        except RuntimeError as exc:
            if not any(marker in str(exc).casefold() for marker in _TRANSIENT_NAVIGATION_ERRORS):
                raise
            await asyncio.sleep(.05)
    raise asyncio.TimeoutError


async def run(daemon, tx, payload, site):
    deadline = min(tx.deadline, time.monotonic() + ADAPTER_TIMEOUT_SECONDS)
    validate, fill_function, submit_function, snapshot_expression = _expressions(site)
    username = password = None
    mutable = None
    try:
        username, password, mutable = _parse_payload(payload)
        navigation = await _call(daemon, tx, "Page.navigate", {"url": site.login_url}, deadline)
        loader_id = navigation.get("loaderId")
        if navigation.get("errorText") or not isinstance(loader_id, str) or not loader_id:
            return _result("failed")
        form_deadline = min(deadline, time.monotonic() + _FORM_WAIT_SECONDS)
        while time.monotonic() < form_deadline:
            frame = (await _call(daemon, tx, "Page.getFrameTree", {}, form_deadline)).get("frameTree", {}).get("frame", {})
            if frame.get("loaderId") != loader_id:
                await asyncio.sleep(.05); continue
            form = _remote_value(await _call(daemon, tx, "Runtime.evaluate", {
                "expression": validate, "returnByValue": True}, form_deadline))
            if not isinstance(form, dict) or not _same_origin(site, form.get("href")):
                return _result("failed")
            if _locked(form): return _result("locked")
            if _challenge(form): return _result("human_challenge")
            control_values = tuple(form.get(key) is True for key in ("user", "password", "submit", "bound"))
            controls_ready = all(control_values)
            gitlab_form_ready = site is not GITLAB or (
                form.get("action") == site.login_url and form.get("method") == "post"
            )
            if controls_ready and not gitlab_form_ready:
                return _result("failed")
            if form.get("ready") == "complete" and controls_ready and gitlab_form_ready:
                break
            await asyncio.sleep(.05)
        else:
            return _result("timeout")
        if (urlparse(form["href"]).path != site.login_path
            or not all(form.get(key) is True for key in ("user", "password", "submit", "bound"))
            or (site is GITLAB and (form.get("action") != site.login_url or form.get("method") != "post"))):
            return _result("failed")
        document = (await _call(daemon, tx, "Runtime.evaluate", {"expression": "document"}, deadline)).get("result", {}).get("objectId")
        if not document: return _result("failed")
        daemon.suppress_sensitive_events(tx.session_id)
        filled = await _call(daemon, tx, "Runtime.callFunctionOn", {
            "objectId": document, "functionDeclaration": fill_function,
            "arguments": [{"value": username}, {"value": password}], "returnByValue": True}, deadline)
        if filled.get("exceptionDetails") or filled.get("result", {}).get("value") is not True:
            return _result("failed")
        post_deadline = min(deadline, time.monotonic() + _POST_SUBMIT_SECONDS)
        before = await _snapshot(daemon, tx, snapshot_expression, post_deadline)
        submitted = await _call(daemon, tx, "Runtime.callFunctionOn", {
            "objectId": document, "functionDeclaration": submit_function, "returnByValue": True}, post_deadline)
        if submitted.get("exceptionDetails") or submitted.get("result", {}).get("value") is not True:
            return _result("failed")
        while time.monotonic() < post_deadline:
            state = await _snapshot(daemon, tx, snapshot_expression, post_deadline)
            if not isinstance(state, dict) or not _same_origin(site, state.get("href")): return _result("failed")
            if _locked(state): return _result("locked")
            if _challenge(state): return _result("human_challenge")
            current_path = urlparse(state.get("href") or "").path
            if (state.get("ready") == "complete" and state.get("protected") is True
                    and (site is PROXMOX or current_path != site.login_path)):
                return _result("active")
            transitioned = any(state.get(k) != before.get(k) for k in ("href", "ready", "identity"))
            if transitioned and current_path == site.login_path and state.get("ready") == "complete":
                return _result("reauth_required")
            await asyncio.sleep(.05)
        return _result("timeout")
    except asyncio.CancelledError:
        raise
    except asyncio.TimeoutError:
        return _result("timeout")
    except (RuntimeError, ValueError, TypeError, KeyError):
        return _result("failed")
    finally:
        daemon.release_sensitive_events(tx.session_id)
        username = password = None
        if mutable is not None: mutable[:] = b"\0" * len(mutable)
        if isinstance(payload, bytearray): payload[:] = b"\0" * len(payload)
        elif isinstance(payload, memoryview) and not payload.readonly: payload[:] = b"\0" * len(payload)
