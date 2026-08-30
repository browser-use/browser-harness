# X (Twitter) — Followers & profile scraping

Companion to `posting.md`. Covers reading other users' followers/following lists and profile data via DOM. The private GraphQL endpoints work too, but DOM extraction is more robust and avoids hammering APIs.

## Auth check (do this first)

`auth_token` is HttpOnly so it never appears in `document.cookie`. Check for `ct0` + `twid` instead, and confirm `https://x.com/home` does not redirect to `https://x.com/`:

```python
js(r'''
  var cookies = document.cookie.split(";").map(s => s.trim().split("=")[0]);
  var has_auth = cookies.includes("ct0") && cookies.includes("twid");
  var profile_link = document.querySelector('[data-testid="AppTabBar_Profile_Link"]');
  return JSON.stringify({has_auth, handle: profile_link ? profile_link.getAttribute("href") : null});
''')
```

If unauthenticated, X redirects follower URLs to `/i/jf/onboarding/web?redirect_after_login=...&mode=login`. Stop and ask the user — do not type credentials.

## Public follower list cap (important)

For users you do not own, the public `/<user>/followers` list stops paginating after a bounded slice — there is no "Load more" button, no spinner, the scroll height simply stops growing. This is an X-imposed per-request limit, not a soft-block on your account. The exact size is not fixed at the often-quoted ~50–60: on a large account (Ridd, ~May 2026) the main tab yielded **73 unique** before it stopped.

The separate **`/<user>/verified_followers`** tab returns another ~20 entries with partial overlap, so harvesting both yields **~85–90 unique** users on a big account. `following` behaves similarly.

If you need the full follower graph, you need owner access or a third-party data source. Do **not** retry from a fresh tab hoping for more — the cap is on the request, not the session.

## DOM extraction (preferred over GraphQL)

Every follower row is `article[data-testid="UserCell"]`. Inside:

- 3 anchors with `href="/<handle>"` (avatar, name, handle) — first one is the canonical
- 1 anchor with `href="https://t.co/..."` for the bio URL (if user has one)
- `innerText` is `"<name>\n@<handle>\n<Follow|Following|Follow back>\n<bio lines>"`

```python
js(r'''
  var cells = document.querySelectorAll('[data-testid="UserCell"]');
  var out = [];
  cells.forEach(c => {
    var anchors = c.querySelectorAll('a[role="link"]');
    var handle_href = null, ext_url = null;
    anchors.forEach(a => {
      var h = a.getAttribute("href") || "";
      if (h.startsWith("/") && !handle_href) handle_href = h;
      if (h.startsWith("http") && !ext_url) ext_url = h;
    });
    var lines = (c.innerText||"").split("\n").map(s=>s.trim()).filter(Boolean);
    var bio_lines = lines.filter(l => l !== "Follow" && l !== "Following" && l !== "Follow back");
    out.push({handle: handle_href, name: bio_lines[0], at: bio_lines[1],
              bio: bio_lines.slice(2).join(" | "), ext_url});
  });
  return JSON.stringify(out);
''')
```

X virtualizes the list — old rows unmount as you scroll. **Use small scroll steps (≈800px) with a 1.4s wait** so freshly-rendered rows are captured before they recycle. Bigger steps (2000px) skip past entire batches.

```python
import time
seen = {}
no_growth = 0
while no_growth < 4 and len(seen) < 100:
    for c in json.loads(js(EXTRACT)):
        if c.get("at") and c["at"] not in seen:
            seen[c["at"]] = c
    new = len(seen) - prev; prev = len(seen)
    no_growth = no_growth + 1 if new == 0 else 0
    js("window.scrollBy(0, 800)")
    time.sleep(1.4)
```

## Profile page selectors

Stable as of late 2025:

| What | Selector |
|---|---|
| Bio | `[data-testid="UserDescription"]` |
| URL field | `[data-testid="UserUrl"]` (text only; full URL needs `.title` or hover) |
| Location | `[data-testid="UserLocation"]` |
| Join date | `[data-testid="UserJoinDate"]` |
| Followers / Following counts | `a[href$="/followers"]`, `a[href$="/following"]`, `a[href$="/verified_followers"]` — read `.innerText` |
| DM button (open DMs) | `[data-testid="sendDMFromProfile"]` — present only when DMs are open |
| Tweet article | `article[data-testid="tweet"]` |
| Tweet body | `[data-testid="tweetText"]` (inside the article) |
| Pinned indicator | `[data-testid="socialContext"]` inside the article ("Pinned" label) |

## GraphQL capture (when you actually need it)

`drain_events()` returns at most ~500 events, so a long page load can flush the Followers GraphQL request out of the buffer before you read it. Two workarounds:

- Call `cdp("Network.enable")` and `drain_events()` immediately after a small scroll (just a few hundred px) so only a handful of new requests fire.
- Or use `Network.getResponseBody` against a known requestId captured the moment after a single user-initiated scroll.

When you do see them, the relevant endpoints are GET requests to `https://x.com/i/api/graphql/<queryId>/Followers` / `FollowersYouKnow` / `VerifiedFollowers`. The query is encoded in `?variables=...&features=...&fieldToggles=...` (URL-encoded JSON). `userId` lives inside `variables`, and `cursor` is in `variables.cursor` after the first page. Required headers when replaying: `authorization` (the static Bearer), `x-csrf-token` (= `ct0` cookie value), `x-twitter-active-user: yes`, `x-twitter-auth-type: OAuth2Session`, `cookie`. The same ~50–60 cap applies — replaying with cursors does not bypass it.

## Gotchas

- **`/home` vs `/`** — logged-in users see `x.com/home`; the redirect to `x.com/` is a fast auth check.
- **Profile loads but no tweet rows** — usually still rendering. `wait_for_load` + 2.5s `time.sleep` is enough; bigger waits don't help.
- **Account that exists but shows zero info** — could be suspended, locked, or shadow-protected. `current_tab().get("title")` will say "Profile" or contain the handle even when content is hidden.
- **t.co wrapping** — every external URL on X is wrapped in `https://t.co/<id>`. The visible domain text (e.g. "jhey.dev") is the real target; the `href` is the t.co redirect. Either is fine to record; use `http_get(t_co_url)` and follow redirects when you need the canonical.
- **Don't collect avatars.** Profile photos are bait for face-based filtering. Bio + bio URL + tweets are sufficient signal for evaluating a designer.
- **Shared daemon → tab stealing.** If a second agent (or the user) is driving the same daemon, `new_tab()` / `js()` operate on the daemon's "current tab", which the other actor keeps re-activating — your followers page silently becomes their tweet thread mid-scroll. Symptom: `location.href` flips to an unrelated URL between calls. Fix: own a dedicated target and pin every call to it. `tid = cdp("Target.createTarget", url="https://x.com/<user>/followers")["targetId"]` (pass the URL directly so you never touch the current tab), poll readiness with `js("document.readyState", target_id=tid)`, then run all extraction/scroll as `js(expr, target_id=tid)`. To navigate that same pinned tab later, `Page.navigate` over its attached `sessionId` rather than `goto_url`.
