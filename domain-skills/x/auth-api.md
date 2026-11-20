# X (Twitter) — Internal GraphQL API

`https://x.com` — read personal data (notifications, timelines, profiles) by replaying the Web App's internal GraphQL operations with the browser's own session.

## Do this first: capture, then replay

X doesn't expose a public endpoint for personal data. You capture one of its internal GraphQL operations from a live browser session, then replay it with the same auth. Captured requests stay valid for many minutes.

```python
import json, urllib.request, urllib.parse, time
from helpers import cdp, js

# 1. Install a spy that captures every GraphQL request's URL + headers
SPY = r"""
(() => {
  if (window.__xCache) return;
  window.__xCache = {operations: {}};
  const origOpen = XMLHttpRequest.prototype.open;
  const origSend = XMLHttpRequest.prototype.send;
  const origSet  = XMLHttpRequest.prototype.setRequestHeader;
  XMLHttpRequest.prototype.open = function(method, url, ...rest) {
    this._url = url; this._method = method; this._hdrs = {};
    return origOpen.call(this, method, url, ...rest);
  };
  XMLHttpRequest.prototype.setRequestHeader = function(k, v) {
    this._hdrs[k.toLowerCase()] = v;
    return origSet.call(this, k, v);
  };
  XMLHttpRequest.prototype.send = function(body) {
    if (this._url && /\/i\/api\/graphql\//.test(this._url)) {
      const m = this._url.match(/\/graphql\/[^/]+\/(\w+)/);
      if (m) window.__xCache.operations[m[1]] = {
        method: this._method, url: this._url, headers: this._hdrs
      };
    }
    return origSend.call(this, body);
  };
})();
"""
cdp("Page.enable")
cdp("Page.addScriptToEvaluateOnNewDocument", source=SPY)
js(SPY)   # inject into current page too

# 2. Navigate to trigger the operation you want
js("window.location.href = 'https://x.com/notifications'")
time.sleep(5)

# 3. Pull captured request + cookies
cap = json.loads(js("JSON.stringify(window.__xCache.operations.NotificationsTimeline)"))
cookies = cdp("Network.getCookies", urls=["https://x.com"])["cookies"]
cookie_jar = "; ".join(f"{c['name']}={c['value']}" for c in cookies)

# 4. Replay from Python
headers = {k: v for k, v in cap["headers"].items() if k.lower() not in ("host","content-length")}
headers.update({
    "cookie":     cookie_jar,
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/147.0.0.0",
    "accept":     "*/*",
    "origin":     "https://x.com",
    "referer":    "https://x.com/notifications",
})
req = urllib.request.Request(cap["url"], headers=headers)
with urllib.request.urlopen(req, timeout=15) as r:
    data = json.loads(r.read())
# ~640ms for NotificationsTimeline (50 items, ~250KB)
```

## Auth headers (all required)

Missing any of these on a Python replay → 403:

| Header                         | Source                                           |
|--------------------------------|--------------------------------------------------|
| `authorization: Bearer AAAA…`  | Hardcoded in Web App JS — public constant, same for every user |
| `x-csrf-token`                 | Must equal the `ct0` cookie byte-for-byte       |
| `x-client-transaction-id`      | Per-request signature; captured value reusable for many minutes |
| `x-twitter-auth-type`          | Constant `OAuth2Session`                         |
| `x-twitter-active-user`        | Constant `yes`                                   |
| `x-twitter-client-language`    | User locale, e.g. `en`                           |
| `cookie` (full jar)            | Needs `ct0`, `auth_token`, `twid` at minimum — pull via `cdp("Network.getCookies", urls=["https://x.com"])` |
| `user-agent`                   | A real Chrome UA — Cloudflare rejects default Python UA |

The Bearer is not per-user. User identity is entirely in the cookie jar + `x-csrf-token`.

## Why the spy hooks XHR

X uses `XMLHttpRequest` for GraphQL, not `window.fetch` (~30 XHR calls vs ~4 fetch calls per page load). A `fetch`-only interceptor catches nothing useful. Similarly, calling `fetch(url, {credentials:"include"})` from inside the page returns 403 — X's JS attaches the auth headers via `setRequestHeader` on its own XHR object, not through cookies.

## Pagination

Responses include `cursor-top-<ts>` and `cursor-bottom-<ts>` entries. Feed the value into `variables.cursor` on the next call:

```python
v = {"timeline_type": "All", "count": 50, "cursor": "<value from cursor-bottom entry>"}
url = cap["url"].split("?")[0] + "?variables=" + urllib.parse.quote(json.dumps(v)) + "&features=" + urllib.parse.quote(json.dumps(FEATURES))
```

The `features` query param is **not optional** — dropping a flag returns 400. Copy it verbatim from `cap["url"]`.

## `NotificationsTimeline` response shape

```
data.viewer_v2.user_results.result.notification_timeline.timeline.instructions[]
  .type == "TimelineAddEntries"
  .entries[]
    .entryId           # "cursor-top-..." | "cursor-bottom-..." | "notification-<id>"
    .sortIndex         # ms timestamp string
    .content.__typename == "TimelineTimelineItem" | "TimelineTimelineCursor"
    .content.itemContent
      .__typename == "TimelineNotification"
      .rich_message.text          # display string
      .notification_icon          # heart_icon | retweet_icon | person_icon | recommendation_icon | reply_icon | bird_icon | verified_icon
      .notification_url.url       # target URL
      .template.from_users[].user_results.result.core.{name, screen_name}
```

Parser (iterative — `browser-harness` runs stdin via `exec()`, which breaks self-referencing nested functions, so recursion would raise `NameError`):

```python
def find(obj, key):
    stack = [obj]
    while stack:
        o = stack.pop()
        if isinstance(o, dict):
            if key in o: return o[key]
            stack.extend(o.values())
        elif isinstance(o, list):
            stack.extend(o)
    return None

for ins in find(data, "instructions") or []:
    for e in ins.get("entries", []):
        ic = e.get("content", {}).get("itemContent", {})
        if ic.get("__typename") != "TimelineNotification": continue
        print(ic.get("notification_icon"), "-", ic.get("rich_message",{}).get("text"))
```

## Other operations — same capture/replay pattern

Navigate to the page that loads each operation, let the spy capture it, replay with the recipe above. `queryId` rotates on bundle deploys; always use the one you just captured rather than hardcoding.

| Page                          | Operation captured on load         |
|-------------------------------|------------------------------------|
| `/home`                       | `HomeTimeline`                     |
| `/notifications`              | `NotificationsTimeline`            |
| `/explore`                    | `ExploreSidebar`, `SidebarUserRecommendations` |
| `/<screen_name>`              | `UserByScreenName`                 |
| `/search?q=…`                 | `SearchTimeline`                   |
| `/messages`                   | `XChatDmSettingsQuery`             |

## Gotchas

- **Attaching browser-harness creates a "new device login" entry** at position 0 of the timeline. Not a bug — that notification is your session.
- **`queryId` rotates** on bundle deploys. Capture fresh each session.
- **Captured `x-client-transaction-id` eventually stops working** — if you see 403 after a long idle, re-capture rather than investigating.
- **Cookies expire on logout.** A logout in any Chrome window wipes `auth_token`; captured requests stop working.
