# Manus — Submitting Tasks, Awaiting Completion, Sharing Results

Manus (`manus.im`) is a general-purpose agent that runs long-form tasks in a cloud sandbox. The web UI is a Next.js SPA; the runtime API is a separate host (`api.manus.im`) speaking Connect RPC. You must be signed in before the harness can drive it — hit the auth wall and stop, don't type credentials.

## URL patterns

- App home / new-task composer: `https://manus.im/app`
- Running or completed task: `https://manus.im/app/<taskId>` — `<taskId>` is a 22-char base62-ish opaque id (character set includes letters, digits, and `-`/`_`). The same id is the session id on the API side.
- Public share page: `https://manus.im/share/<taskId>` — only reachable after a `ShareSession` call (clicking *Share*).
- Library / past tasks: listed in the left sidebar; the list is paged via `session.v1.SessionService/ListSessions`.

The title of a task page is auto-summarized from the prompt (it shortens, reflows, and sometimes paraphrases). Do **not** match on the original prompt text when identifying a task in the sidebar — use the taskId in the URL as the durable handle.

## Path 1: Private API — `api.manus.im` Connect RPC

All API calls go to `https://api.manus.im/` with the Connect RPC shape `/<package>.v<N>.<Service>/<Method>`. Requests are POST with `content-type: application/json`; the Connect JS client encodes request JSON as a `Uint8Array` before calling `fetch`, so a naive fetch-hook may log bodies as `<<bytes:N>>` — the wire content is still JSON matching the content-type (both directions). Auth is a session cookie set by `manus.im`, so in-browser calls Just Work if you're logged in — `fetch("/session.v1.SessionService/...")` from the Manus origin is fine, but cross-origin from a scraper is not.

Services observed on the wire:

| Service | Known methods | Purpose |
| --- | --- | --- |
| `session.v1.SessionService` | `ListSessions`, `GetSession`, `ShareSession`, `UpdateReadPosition` | Tasks (called "sessions" on the API). `GetSession` is the poll target for status. `ShareSession` flips public access and returns the share url. |
| `orchestrator.v1.OrchestratorService` | `GetSession` | Runtime/plan state for an in-progress task. |
| `cloud_pc.v1.CloudPCService` | `List` | Attached Cloud PC instances (sandbox VMs). |
| `desktop.v1.DesktopService` | `GetDesktopDevices` | Enumerates desktop agent connections. |
| `user.v1.UserService` | `WebdevUsageInfo`, `SetUserClientConfig`, `GetHelpCenterToken`, `PickEmailUsers` | User settings + quota. |
| `user.v1.UserPublicService` | `GetGlobalSettings` | Public feature flags. |
| `team.v1.TeamService` | `ListTeam` | Team membership. |

To poll a task to completion without scraping the DOM:

```python
# Browser fetch from inside the page — auth cookies are attached automatically
status = js(r"""
(async()=>{
  const r = await fetch('https://api.manus.im/session.v1.SessionService/GetSession', {
    method: 'POST',
    headers: {'content-type': 'application/json'},
    body: JSON.stringify({sessionId: location.pathname.split('/').pop()})
  });
  return {status: r.status, body: await r.text()};
})()
""")
```

(Exact field names in the request payload are not documented publicly — inspect the outgoing request with the fetch-hook snippet below the first time you run against a new Manus build.)

There is **no plain REST/JSON convenience layer** — every method is Connect. `http_get` against API routes will not work; you have to either drive the browser or speak Connect yourself. If you need a pure-HTTP client, open a PR with the Connect wire format once you reverse-engineer the request shapes.

## Path 2: Browser DOM submission

```bash
browser-harness <<'PY'
new_tab("https://manus.im/app")
wait_for_load()
wait(1.5)  # SPA still hydrating; composer is a TipTap editor that mounts late
# Locate the editor and click into it — the ProseMirror div is the contenteditable.
# The composer mounts late; retry briefly if it isn't in the DOM yet.
for _ in range(10):
    rect = js(r"""
    (()=>{const ce=document.querySelector('div.ProseMirror[contenteditable="true"]');
    if(!ce) return null;
    const r=ce.getBoundingClientRect();return {x:r.x+r.width/2|0,y:r.y+r.height/2|0}})()
    """)
    if rect: break
    wait(0.5)
assert rect, "ProseMirror composer never mounted — page probably failed to hydrate"
click(rect["x"], rect["y"])
wait(0.3)
type_text("Research the top 5 espresso machines under $500 and summarize tradeoffs")
wait(0.4)
# Submit via Enter — the editor has enterkeyhint="enter" and binds Enter to submit.
# (Click the send button at the bottom-right of the composer if Enter is being blocked
#  by an autocomplete / slash-menu.)
press_key("Enter")
wait(3)
print(page_info())  # url will be /app/<taskId>
PY
```

### Composer selectors

The input is a **TipTap/ProseMirror** contenteditable, not a `<textarea>`. Setting `.value` does nothing.

| Target | Selector | Notes |
| --- | --- | --- |
| Composer container | `div.flex.flex-col.gap-3.rounded-[22px]` | Tailwind utility cluster; unique on the page. |
| Editor | `div.tiptap.ProseMirror[contenteditable="true"]` | Has `enterkeyhint="enter"`. Focus then type via CDP `Input.insertText` (helpers' `type_text()`). |
| Placeholder `<p>` | `p[data-placeholder="Assign a task or ask anything"]` | Visible only when the editor is empty. Goes away after the first keystroke. |
| Send button | Last `<button>` inside the composer (black round, lucide arrow-up icon with empty class). | Disabled while the editor is empty; `disabled=false` once any text is present. |
| Attach file | `button svg.lucide-plus` inside composer | For file uploads (not covered here). |
| Connect / integrations | `button svg.lucide-cable` inside composer | Opens integrations popover. |
| Computer use toggle | `button svg.lucide-monitor` inside composer | Enables the Cloud PC sandbox for this task. |

Submitting via coordinate click on the send button works and is often more reliable than `press_key("Enter")` — the key-down path occasionally opens the slash-command menu instead of submitting.

### Task page (run + result)

```python
# Wait for a task to complete
def wait_completed(timeout=1800):
    deadline = time.time() + timeout
    while time.time() < deadline:
        done = js(r"""
        [...document.querySelectorAll('*')].some(el =>
            el.childElementCount < 3 &&
            /^\s*task\s+completed\s*$/i.test((el.innerText||'').trim()))
        """)
        if done: return True
        wait(5)
    return False
```

Selectors on a running / completed task page:

| Target | Selector / pattern | Notes |
| --- | --- | --- |
| User message bubble | `div.flex.w-full.flex-col.items-end.justify-end.group` | Right-aligned = user. The innermost `span.whitespace-pre-wrap` carries the text. |
| Assistant message body | `div.max-w-none.p-0.m-0.text-[16px].leading-[1.5]` | Markdown-rendered prose. Code blocks use Shiki (`pre:not(.shiki)` vs `pre.shiki`). |
| Final answer text | first `div.py-[3px].whitespace-pre-wrap.u-break-words` under the assistant body | The first text block of the final message — good enough for short answers. For long reports, read the whole assistant body's `innerText`. |
| "Task completed" marker | any element whose trimmed `innerText` is exactly `"Task completed"` | Paired with a green checkmark SVG (`lucide-check`). Presence = terminal state. |
| Suggested follow-ups | `button` with a leading `svg.lucide-message-circle` | Clickable pills under the final answer; clicking pre-seeds the next prompt. |
| Sidebar task list | left column, `div` nodes with text (they are **not** `<a>` tags) | Active task has a distinct background. Don't query by `nav a` — there are no anchor links. |

### Sharing a completed task

```bash
browser-harness <<'PY'
# On a /app/<id> page — click the "Share" button (top-right header)
rect = js(r"""
(()=>{const b=[...document.querySelectorAll('button,[role=\"button\"]')].find(x=>x.innerText?.trim()==='Share');
if(!b)return null;const r=b.getBoundingClientRect();return {x:r.x+r.width/2|0,y:r.y+r.height/2|0};})()
""")
click(rect['x'], rect['y'])
wait(1)
# Copy link button inside the popover
rect = js(r"""
(()=>{const b=[...document.querySelectorAll('button')].find(x=>x.innerText?.trim()==='Copy link');
if(!b)return null;const r=b.getBoundingClientRect();return {x:r.x+r.width/2|0,y:r.y+r.height/2|0};})()
""")
click(rect['x'], rect['y'])
wait(0.5)
# The share URL is https://manus.im/share/<same-taskId-as-/app/>
print(page_info()['url'].replace('/app/', '/share/'))
PY
```

Notes on the Share flow:

- Clicking **Share** in the top bar opens a floating popover (`div[role="dialog"]` inside a `[data-floating-ui-portal]`). It auto-runs `session.v1.SessionService/ShareSession` on first open and sets the task to **Public access** (the checkmark by default). There is an *Only me* option in the popover if you need to revoke.
- Clicking **Share** a second time **toggles the popover closed** — don't double-click thinking it's a no-op.
- **"Copy link" writes via `document.execCommand('copy')`, not `navigator.clipboard.writeText`.** If you need to capture the URL, hook both or just compute it: it's `https://manus.im/share/<taskId>` where the id comes straight from the URL path.
- `ShareSession` is idempotent — once a task is public, subsequent calls don't create a new link.

## Gotchas

- **The composer is TipTap/ProseMirror.** `document.querySelector('textarea')` returns `null` on `/app` and `/app/<id>`. Use `div.tiptap.ProseMirror[contenteditable="true"]` or just coordinate-click and `type_text()`.
- **`__NEXT_DATA__` is present but empty on `/app/<id>`.** The task state is hydrated via Connect RPC after mount. Don't parse Next's inline JSON for task data — it isn't there.
- **Sidebar nav items are `<div>`, not `<a>`.** Click by finding the element whose `innerText` matches `"New task"` / `"Search"` / `"Library"` and using its bounding rect. `location.href` changes won't be reflected in `<a href>` attributes.
- **Task titles are auto-generated from the prompt.** If the exact prompt text matters for lookup, store the returned `taskId` (from the URL after submit) — do not grep the sidebar by prompt text.
- **Connect RPC request bodies look binary in a naive fetch-hook.** The Connect JS client serializes request JSON into a `Uint8Array` before handing it to `fetch`, so `body instanceof Uint8Array` is `true` even though the wire content is JSON. Decode with `new TextDecoder().decode(body)` if you need to see it; content-type (`application/json`) matches reality.
- **Task submit fires no obvious single "CreateSession" RPC in the page's fetch stream** — the initial create is done in the SPA's state transition that routes you to `/app/<id>`. Follow-on streaming updates arrive through `SessionService/GetSession` polls (and likely a WebSocket — install a WS hook if you need the wire format).
- **"Task completed" is the only DOM marker for terminal state.** Failed / cancelled tasks may surface different text — if you hit one, extend this skill.
- **Cloud PC / Computer Use tasks** (when the monitor icon in the composer is toggled) spawn a sandbox VM and stream a VNC-like view into an iframe. Scraping that iframe is out of scope for this skill — see `interaction-skills/iframes.md` if you need to drive it.
- **Auth wall.** If `https://manus.im/app` redirects to `/login` or a Google OAuth page, stop and ask the user to sign in. Never type credentials from a screenshot.

## Debugging

Install a fetch hook on page load to see what RPC methods fire during a given action:

```python
js(r"""
(()=>{
  if(window.__bu_fetch_hooked) return;
  window.__bu_fetch_hooked = true;
  window.__bu_fetch_log = [];
  const of = window.fetch;
  window.fetch = async function(input, init){
    const url = typeof input === 'string' ? input : input.url;
    const r = await of.apply(this, arguments);
    window.__bu_fetch_log.push({t: Date.now(), url, method: (init?.method||'GET').toUpperCase(), status: r.status});
    return r;
  };
})()
""")
# ...do the action...
print(js("window.__bu_fetch_log.filter(e => e.url.includes('api.manus.im')).slice(-20)"))
```
