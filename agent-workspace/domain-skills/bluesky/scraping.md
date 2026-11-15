# Bluesky - Profiles, Author Feeds, People Search and Threads (public AppView API)

Field-tested against bsky.app and public.api.bsky.app on 2026-10-31 using a Browser Use cloud browser (logged out; API calls made with `fetch()` from a bsky.app tab) and plain Python urllib.

robots.txt (fetched 2026-10-31): bsky.app has `User-Agent: *`, `Disallow: /intent/compose`, `Allow: /`; public.api.bsky.app has `User-agent: *`, `Allow: /` and says "Crawling the public parts of the API is allowed. HTTP 429 ("backoff") status codes are used for rate-limiting." This skill only calls public.api.bsky.app `/xrpc/...` methods from a bsky.app tab.

## Quick summary

- **No scraping needed.** Logged out, bsky.app itself loads profiles and feeds from `https://public.api.bsky.app/xrpc/<method>` (seen in the tab's resource list: `app.bsky.actor.getProfile`, `app.bsky.feed.getAuthorFeed`, `com.atproto.identity.resolveHandle`, ...). The endpoint answers JSON with `access-control-allow-origin: *`, no key, no cookies.
- **Profiles** (`app.bsky.actor.getProfiles`, max 25 actors per call): followers, follows, posts, bio, created date, verification, labels, pinned post. Unknown actors are silently left out; block 1 reports them as `missing`.
- **Author feed** (`app.bsky.feed.getAuthorFeed`, max 100 per page, `cursor` pagination): bsky.app's whole feed with replies ran to its end in 11 pages, 1090 items. Posts, replies, quotes and the pin add up to `postsCount` (907); reposts (183) come on top.
- **People search** (`app.bsky.actor.searchActors`, max 100 per page, `cursor`): works logged out. "atproto" gave 150+ accounts (stopped at the cap), "pdsadmin" 8 (end of results).
- **Thread for a post URL** (`app.bsky.feed.getPostThread`): the post plus its replies; a handle works inside the `at://` URI.
- **Post search does not work logged out.** `app.bsky.feed.searchPosts` returns HTTP 403 from the CDN (plain HTTP and in the browser), and bsky.app's own search page says "Search is currently unavailable when logged out". This skill does not work around it.
- Bluesky's docs (https://bsky.network/docs/rate-limits, fetched 2026-10-31) ask "public web" use cases to use the cached public.api.bsky.app host and call its limits "generous". The blocks pause 0.5 s between calls; about 100 calls today (0.5-1 s apart) got no 429.

## What works

All browser blocks share the same helpers: `on_bsky_tab()` attaches a bsky.app tab once (later blocks reuse it), and `xrpc()` runs `fetch()` in that tab. It returns parsed JSON on 200, raises `LookupError` on an XRPC 400 (`Profile not found`, `Post not found`, bad params), retries 429/5xx with 15/30/60 s backoff, and otherwise raises. A failed call never comes back as an empty result. Free text (bios, posts) goes through `redact()`, which masks emails and 9+ digit phone-like numbers.

### 1. Profiles for handles or DIDs (browser)

```python
import json, re, time, urllib.parse

ACTORS = ["bsky.app", "atproto.com", "did:plc:ewvi7nxzyoun6zhxrhs64oiz", "zzqx-no-such-handle-9871.bsky.social"]

API = "https://public.api.bsky.app/xrpc/"
PAUSE = 0.5        # seconds between API calls
MAX_WAIT = 120     # longest backoff this code sleeps; a longer one stops the run
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"(?<![\w-])\+?\d[\d\s().-]{7,}\d(?![\w-])")

def redact(s, n=300):
    """Mask emails and 9+ digit phone-like numbers in free text (bios, posts); cut to n chars."""
    if not s:
        return s
    s = EMAIL.sub("[email]", s)
    s = PHONE.sub(lambda m: "[phone]" if sum(c.isdigit() for c in m.group()) >= 9 else m.group(), s)
    return s[:n]

def on_bsky_tab():
    """Fetches run inside a logged-out bsky.app tab; reuse it if the attached tab is already there."""
    try:
        if js("location.origin") == "https://bsky.app":
            return
    except Exception:
        pass
    new_tab("https://bsky.app/")
    wait_for_load()

FETCH_JS = """(async () => {
  try { const r = await fetch(%s, {credentials: 'omit'}); return {status: r.status, body: await r.text()}; }
  catch (e) { return {status: 0, body: String(e)}; }
})()"""

def xrpc(method, params, tries=4):
    """GET public.api.bsky.app/xrpc/<method> from the tab. Returns parsed JSON; raises on anything else."""
    url = API + method + "?" + urllib.parse.urlencode(params, doseq=True)
    for attempt in range(tries):
        r = js(FETCH_JS % json.dumps(url))
        status, body = r["status"], r["body"]
        if status == 200:
            time.sleep(PAUSE)
            return json.loads(body)
        if status == 400:  # XRPC error JSON, e.g. {"error":"InvalidRequest","message":"Profile not found"}
            err = json.loads(body)
            raise LookupError(f"{method}: {err.get('error')}: {err.get('message')}")
        retryable = status in (429, 500, 502, 503, 504) or (status == 0 and attempt == 0)
        if not retryable or attempt == tries - 1:
            hint = " (status 0 = blocked without CORS, e.g. the searchPosts 403, or network down)" if status == 0 else ""
            raise RuntimeError(f"{method} failed with HTTP {status}{hint}: {body[:120]!r}; stopping")
        wait = 15 * 2 ** attempt
        if wait > MAX_WAIT:
            raise RuntimeError(f"{method}: backoff {wait} s > {MAX_WAIT} s; stopping")
        time.sleep(wait)

def hidden_from_logged_out(p):
    """Accounts can ask to be hidden from logged-out viewers (self-label '!no-unauthenticated')."""
    return any(l.get("val") == "!no-unauthenticated" for l in p.get("labels", []))

def profile_row(p):
    base = {"handle": p["handle"], "did": p["did"], "url": f"https://bsky.app/profile/{p['handle']}"}
    if hidden_from_logged_out(p):
        return {**base, "skipped": "account asks not to be shown to logged-out users"}
    return {**base,
        "display_name": p.get("displayName"),
        "bio": redact(p.get("description")),
        "followers": p.get("followersCount"),
        "follows": p.get("followsCount"),
        "posts": p.get("postsCount"),
        "created_at": p.get("createdAt"),
        "verified": (p.get("verification") or {}).get("verifiedStatus") == "valid",
        "trusted_verifier": (p.get("verification") or {}).get("trustedVerifierStatus") == "valid",
        "labels": sorted({l["val"] for l in p.get("labels", [])}),
        "pinned_post": (p.get("pinnedPost") or {}).get("uri"),
        "avatar": p.get("avatar"),
    }

on_bsky_tab()
rows, missing = {}, []
for i in range(0, len(ACTORS), 25):            # getProfiles takes at most 25 actors per call
    chunk = ACTORS[i:i + 25]
    got = xrpc("app.bsky.actor.getProfiles", {"actors": chunk})["profiles"]
    by_key = {p["did"]: p for p in got} | {p["handle"].lower(): p for p in got}
    for a in chunk:                             # unknown actors are silently left out; report them
        p = by_key.get(a.lower())
        if p:
            rows.setdefault(p["did"], profile_row(p))   # a handle and its DID give one row
        else:
            missing.append(a)
rows = list(rows.values())
print(json.dumps({"requested": len(ACTORS), "found": len(rows), "missing": missing}))
print(json.dumps(rows, indent=1, ensure_ascii=False))
```

Real output:

```
{"requested": 4, "found": 2, "missing": ["zzqx-no-such-handle-9871.bsky.social"]}
[
 {
  "handle": "bsky.app",
  "did": "did:plc:z72i7hdynmk6r22z27h6tvur",
  "url": "https://bsky.app/profile/bsky.app",
  "display_name": "Bluesky",
  "bio": "official Bluesky account (check username👆)\n\nBugs, feature requests, feedback: [email]",
  "followers": 35467822,
  "follows": 34,
  "posts": 907,
  "created_at": "2023-04-12T04:53:57.057Z",
  "verified": false,
  "trusted_verifier": true,
  "labels": [],
  "pinned_post": "at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.post/3l6oveex3ii2l",
  "avatar": "https://cdn.bsky.app/img/avatar/plain/did:plc:z72i7hdynmk6r22z27h6tvur/bafkreihwihm6kpd6zuwhhlro75p5qks5qtrcu55jp3gddbfjsieiv7wuka"
 },
 {
  "handle": "atproto.com",
  "did": "did:plc:ewvi7nxzyoun6zhxrhs64oiz",
  "url": "https://bsky.app/profile/atproto.com",
  "display_name": "AT Protocol Developers",
  "bio": "Social networking technology created by Bluesky. \n\nDeveloper-focused account. Follow @bsky.app for general announcements!\n\nBluesky API docs: docs.bsky.app\nAT Protocol specs: atproto.com",
  "followers": 121654,
  "follows": 21,
  "posts": 289,
  "created_at": "2023-04-26T06:19:25.508Z",
  "verified": true,
  "trusted_verifier": false,
  "labels": [],
  "pinned_post": null,
  "avatar": "https://cdn.bsky.app/img/avatar/plain/did:plc:ewvi7nxzyoun6zhxrhs64oiz/bafkreiaihtwfr2d6mjfb6drzaze2gubqtst4ymiwxowqfxpsqxpnz2t33u"
 }
]
```

### 2. An account's posts, many pages (browser)

```python
import json, re, time, urllib.parse

ACTOR = "atproto.com"           # handle or DID
FILTER = "posts_no_replies"     # posts_with_replies (default) | posts_no_replies | posts_with_media | posts_and_author_threads | posts_with_video
INCLUDE_PINS = True             # pinned post comes first, marked kind="pin"
MAX_POSTS = 250                 # cap; the API returns up to 100 items per page

API = "https://public.api.bsky.app/xrpc/"
PAUSE = 0.5        # seconds between API calls
MAX_WAIT = 120     # longest backoff this code sleeps; a longer one stops the run
FILTERS = {"posts_with_replies", "posts_no_replies", "posts_with_media", "posts_and_author_threads", "posts_with_video"}
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"(?<![\w-])\+?\d[\d\s().-]{7,}\d(?![\w-])")

def redact(s, n=300):
    """Mask emails and 9+ digit phone-like numbers in free text (bios, posts); cut to n chars."""
    if not s:
        return s
    s = EMAIL.sub("[email]", s)
    s = PHONE.sub(lambda m: "[phone]" if sum(c.isdigit() for c in m.group()) >= 9 else m.group(), s)
    return s[:n]

def on_bsky_tab():
    """Fetches run inside a logged-out bsky.app tab; reuse it if the attached tab is already there."""
    try:
        if js("location.origin") == "https://bsky.app":
            return
    except Exception:
        pass
    new_tab("https://bsky.app/")
    wait_for_load()

FETCH_JS = """(async () => {
  try { const r = await fetch(%s, {credentials: 'omit'}); return {status: r.status, body: await r.text()}; }
  catch (e) { return {status: 0, body: String(e)}; }
})()"""

def xrpc(method, params, tries=4):
    """GET public.api.bsky.app/xrpc/<method> from the tab. Returns parsed JSON; raises on anything else."""
    url = API + method + "?" + urllib.parse.urlencode(params, doseq=True)
    for attempt in range(tries):
        r = js(FETCH_JS % json.dumps(url))
        status, body = r["status"], r["body"]
        if status == 200:
            time.sleep(PAUSE)
            return json.loads(body)
        if status == 400:  # XRPC error JSON, e.g. {"error":"InvalidRequest","message":"Profile not found"}
            err = json.loads(body)
            raise LookupError(f"{method}: {err.get('error')}: {err.get('message')}")
        retryable = status in (429, 500, 502, 503, 504) or (status == 0 and attempt == 0)
        if not retryable or attempt == tries - 1:
            hint = " (status 0 = blocked without CORS, e.g. the searchPosts 403, or network down)" if status == 0 else ""
            raise RuntimeError(f"{method} failed with HTTP {status}{hint}: {body[:120]!r}; stopping")
        wait = 15 * 2 ** attempt
        if wait > MAX_WAIT:
            raise RuntimeError(f"{method}: backoff {wait} s > {MAX_WAIT} s; stopping")
        time.sleep(wait)

def post_url(uri, handle):
    """at://<did>/app.bsky.feed.post/<rkey> -> https://bsky.app/profile/<handle>/post/<rkey>"""
    return f"https://bsky.app/profile/{handle}/post/{uri.rsplit('/', 1)[-1]}"

def feed_row(item):
    post, rec = item["post"], item["post"]["record"]
    reason = (item.get("reason") or {}).get("$type", "")
    embed = (post.get("embed") or {}).get("$type", "")
    if reason.endswith("#reasonRepost"):
        kind = "repost"
    elif reason.endswith("#reasonPin"):
        kind = "pin"
    elif rec.get("reply"):
        kind = "reply"
    elif embed.startswith("app.bsky.embed.record"):
        kind = "quote"
    else:
        kind = "post"
    return {
        "kind": kind,
        "url": post_url(post["uri"], post["author"]["handle"]),
        "uri": post["uri"],
        "author": post["author"]["handle"],
        "created_at": rec.get("createdAt"),
        "text": redact(rec.get("text")),
        "langs": rec.get("langs"),
        "likes": post.get("likeCount"), "reposts": post.get("repostCount"),
        "replies": post.get("replyCount"), "quotes": post.get("quoteCount"),
        "embed": embed.removeprefix("app.bsky.embed.").removesuffix("#view") or None,
        "reply_to": ((rec.get("reply") or {}).get("parent") or {}).get("uri"),
    }

if FILTER not in FILTERS:   # the API silently ignores an unknown filter and returns everything
    raise SystemExit(f"unknown FILTER {FILTER!r}; use one of {sorted(FILTERS)}")

on_bsky_tab()
prof = xrpc("app.bsky.actor.getProfile", {"actor": ACTOR})   # LookupError "Profile not found" for unknown actors
if any(l.get("val") == "!no-unauthenticated" for l in prof.get("labels", [])):
    raise SystemExit(f"{prof['handle']} asks not to be shown to logged-out users; skipping")

rows, cursor, pages, at_end = {}, None, 0, False
while len(rows) < MAX_POSTS:
    params = {"actor": prof["did"], "limit": min(100, MAX_POSTS - len(rows)), "filter": FILTER,
              "includePins": str(INCLUDE_PINS).lower()}
    if cursor:
        params["cursor"] = cursor
    page = xrpc("app.bsky.feed.getAuthorFeed", params)
    pages += 1
    for it in page["feed"]:
        r = feed_row(it)
        # the pinned post comes first AND again at its date; keep one row (kind "pin")
        rows.setdefault((r["uri"], r["kind"] == "repost"), r)
    cursor = page.get("cursor")
    if not cursor or not page["feed"]:
        at_end = True
        break

rows = list(rows.values())
complete = at_end and len(rows) <= MAX_POSTS
rows = rows[:MAX_POSTS]          # the pin is extra on page 1, so a page can overshoot by one
status = {"actor": prof["handle"], "posts_count": prof.get("postsCount"), "filter": FILTER, "pages": pages,
          "returned": len(rows), "complete": complete}
if not complete:
    print(f"TRUNCATED: stopped at MAX_POSTS={MAX_POSTS}; the feed has more items (next cursor {cursor})")
print(json.dumps(status))
print(json.dumps({k: sum(r["kind"] == k for r in rows) for k in ("post", "reply", "quote", "repost", "pin")}))
print(json.dumps(rows[:3], indent=1, ensure_ascii=False))
```

Real output (trimmed):

```
TRUNCATED: stopped at MAX_POSTS=250; the feed has more items (next cursor 2024-04-19T17:36:17.709Z)
{"actor": "atproto.com", "posts_count": 289, "filter": "posts_no_replies", "pages": 4, "returned": 250, "complete": false}
{"post": 103, "reply": 0, "quote": 28, "repost": 119, "pin": 0}
[
 {
  "kind": "post",
  "url": "https://bsky.app/profile/atproto.com/post/3mz4m677rsc2o",
  "uri": "at://did:plc:ewvi7nxzyoun6zhxrhs64oiz/app.bsky.feed.post/3mz4m677rsc2o",
  "author": "atproto.com",
  "created_at": "2026-10-30T20:20:51.380Z",
  "text": "A serious Linux kernel vulnerability announced yesterday may impact PDS self-hosters.\n\nCVE-2026-98432 involves mptcp connections, which the Caddy HTTP proxy enables by default.\n\nAn updated container disabling this has been publishes and will auto-deploy to PDS instances in coming hours.",
  "langs": [
   "en"
  ],
  "likes": 190,
  "reposts": 62,
  "replies": 7,
  "quotes": 8,
  "embed": "external",
  "reply_to": null
 },
 ...
]
```

Other runs today:

| Settings | Result |
|---|---|
| `bsky.app`, `posts_with_replies`, `MAX_POSTS = 3000` | 11 pages, 1090 items, `complete: true`; post 271, reply 571, quote 64, pin 1 (= `postsCount` 907), repost 183 |
| `bsky.app`, `posts_with_media`, `MAX_POSTS = 5` | `TRUNCATED`, 5 rows: the pin plus 4 media posts |
| `bsky.app`, `posts_and_author_threads`, `INCLUDE_PINS = False`, `MAX_POSTS = 3` | 3 reposts (reposts stay in every filter) |
| `bsky.app`, `posts_with_video`, `INCLUDE_PINS = False`, `MAX_POSTS = 3` | 3 own posts |
| `ACTOR = "zzqx-no-such-handle-9871.bsky.social"` | `LookupError: app.bsky.actor.getProfile: InvalidRequest: Profile not found` |
| `FILTER = "bogus"` | `SystemExit: unknown FILTER 'bogus'; ...` (the API itself would silently ignore it) |

### 3. Search people (browser)

```python
import json, re, time, urllib.parse

QUERY = "atproto"     # matched against handle, display name and bio
MAX_ACTORS = 150      # cap; up to 100 per page

API = "https://public.api.bsky.app/xrpc/"
PAUSE = 0.5        # seconds between API calls
MAX_WAIT = 120     # longest backoff this code sleeps; a longer one stops the run
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"(?<![\w-])\+?\d[\d\s().-]{7,}\d(?![\w-])")

def redact(s, n=300):
    """Mask emails and 9+ digit phone-like numbers in free text (bios, posts); cut to n chars."""
    if not s:
        return s
    s = EMAIL.sub("[email]", s)
    s = PHONE.sub(lambda m: "[phone]" if sum(c.isdigit() for c in m.group()) >= 9 else m.group(), s)
    return s[:n]

def on_bsky_tab():
    """Fetches run inside a logged-out bsky.app tab; reuse it if the attached tab is already there."""
    try:
        if js("location.origin") == "https://bsky.app":
            return
    except Exception:
        pass
    new_tab("https://bsky.app/")
    wait_for_load()

FETCH_JS = """(async () => {
  try { const r = await fetch(%s, {credentials: 'omit'}); return {status: r.status, body: await r.text()}; }
  catch (e) { return {status: 0, body: String(e)}; }
})()"""

def xrpc(method, params, tries=4):
    """GET public.api.bsky.app/xrpc/<method> from the tab. Returns parsed JSON; raises on anything else."""
    url = API + method + "?" + urllib.parse.urlencode(params, doseq=True)
    for attempt in range(tries):
        r = js(FETCH_JS % json.dumps(url))
        status, body = r["status"], r["body"]
        if status == 200:
            time.sleep(PAUSE)
            return json.loads(body)
        if status == 400:  # XRPC error JSON, e.g. {"error":"InvalidRequest","message":"Profile not found"}
            err = json.loads(body)
            raise LookupError(f"{method}: {err.get('error')}: {err.get('message')}")
        retryable = status in (429, 500, 502, 503, 504) or (status == 0 and attempt == 0)
        if not retryable or attempt == tries - 1:
            hint = " (status 0 = blocked without CORS, e.g. the searchPosts 403, or network down)" if status == 0 else ""
            raise RuntimeError(f"{method} failed with HTTP {status}{hint}: {body[:120]!r}; stopping")
        wait = 15 * 2 ** attempt
        if wait > MAX_WAIT:
            raise RuntimeError(f"{method}: backoff {wait} s > {MAX_WAIT} s; stopping")
        time.sleep(wait)

on_bsky_tab()
seen, cursor, pages = {}, None, 0
while len(seen) < MAX_ACTORS:
    params = {"q": QUERY, "limit": 100}
    if cursor:
        params["cursor"] = cursor
    page = xrpc("app.bsky.actor.searchActors", params)
    pages += 1
    for a in page["actors"]:
        if any(l.get("val") == "!no-unauthenticated" for l in a.get("labels", [])):
            continue          # account asks not to be shown to logged-out users
        seen.setdefault(a["did"], {
            "rank": len(seen) + 1,
            "handle": a["handle"],
            "did": a["did"],
            "display_name": a.get("displayName"),
            "bio": redact(a.get("description"), 160),
            "verified": (a.get("verification") or {}).get("verifiedStatus") == "valid",
            "labels": sorted({l["val"] for l in a.get("labels", [])}),
            "url": f"https://bsky.app/profile/{a['handle']}",
        })
    cursor = page.get("cursor")
    if not cursor or not page["actors"]:   # a short page (97 of 100) is NOT the end; only a missing cursor is
        break

rows = list(seen.values())[:MAX_ACTORS]
complete = not cursor
if not complete:
    print(f"TRUNCATED: stopped at MAX_ACTORS={MAX_ACTORS}; more results follow")
print(json.dumps({"query": QUERY, "pages": pages, "returned": len(rows), "complete": complete}))
print(json.dumps(rows[:3], indent=1, ensure_ascii=False))
```

Real output (trimmed):

```
TRUNCATED: stopped at MAX_ACTORS=150; more results follow
{"query": "atproto", "pages": 2, "returned": 150, "complete": false}
[
 {
  "rank": 1,
  "handle": "atproto.com",
  "did": "did:plc:ewvi7nxzyoun6zhxrhs64oiz",
  "display_name": "AT Protocol Developers",
  "bio": "Social networking technology created by Bluesky. \n\nDeveloper-focused account. Follow @bsky.app for general announcements!\n\nBluesky API docs: docs.bsky.app\nAT Pr",
  "verified": true,
  "labels": [],
  "url": "https://bsky.app/profile/atproto.com"
 },
 {
  "rank": 2,
  "handle": "microcosm.blue",
  "did": "did:plc:lulmyldiq4sb2ikags5sfb25",
  "display_name": "microcosm: atproto building blocks",
  "bio": "Open-source APIs to kick-start your next app on ATProto.\nCommunity-supported infrastructure ready for production.\n\nrelay.fire.hose.cam\nconstellation.microcosm.b",
  "verified": false,
  "labels": [],
  "url": "https://bsky.app/profile/microcosm.blue"
 },
 ...
]
```

`QUERY = "pdsadmin"` returned 8 accounts in 1 page with `complete: true`; `QUERY = "zzqxnothing9871"` returned 0 with `complete: true`.

### 4. A post and its replies from a bsky.app URL (browser)

```python
import json, re, time, urllib.parse

POST_URL = "https://bsky.app/profile/atproto.com/post/3mz4m677rsc2o"
DEPTH = 1          # reply levels to load (0 = just the post)
MAX_REPLIES = 5    # printed top-level replies, most liked first

API = "https://public.api.bsky.app/xrpc/"
PAUSE = 0.5        # seconds between API calls
MAX_WAIT = 120     # longest backoff this code sleeps; a longer one stops the run
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"(?<![\w-])\+?\d[\d\s().-]{7,}\d(?![\w-])")

def redact(s, n=300):
    """Mask emails and 9+ digit phone-like numbers in free text (bios, posts); cut to n chars."""
    if not s:
        return s
    s = EMAIL.sub("[email]", s)
    s = PHONE.sub(lambda m: "[phone]" if sum(c.isdigit() for c in m.group()) >= 9 else m.group(), s)
    return s[:n]

def on_bsky_tab():
    """Fetches run inside a logged-out bsky.app tab; reuse it if the attached tab is already there."""
    try:
        if js("location.origin") == "https://bsky.app":
            return
    except Exception:
        pass
    new_tab("https://bsky.app/")
    wait_for_load()

FETCH_JS = """(async () => {
  try { const r = await fetch(%s, {credentials: 'omit'}); return {status: r.status, body: await r.text()}; }
  catch (e) { return {status: 0, body: String(e)}; }
})()"""

def xrpc(method, params, tries=4):
    """GET public.api.bsky.app/xrpc/<method> from the tab. Returns parsed JSON; raises on anything else."""
    url = API + method + "?" + urllib.parse.urlencode(params, doseq=True)
    for attempt in range(tries):
        r = js(FETCH_JS % json.dumps(url))
        status, body = r["status"], r["body"]
        if status == 200:
            time.sleep(PAUSE)
            return json.loads(body)
        if status == 400:  # XRPC error JSON, e.g. {"error":"NotFound","message":"Post not found: ..."}
            err = json.loads(body)
            raise LookupError(f"{method}: {err.get('error')}: {err.get('message')}")
        retryable = status in (429, 500, 502, 503, 504) or (status == 0 and attempt == 0)
        if not retryable or attempt == tries - 1:
            hint = " (status 0 = blocked without CORS, e.g. the searchPosts 403, or network down)" if status == 0 else ""
            raise RuntimeError(f"{method} failed with HTTP {status}{hint}: {body[:120]!r}; stopping")
        wait = 15 * 2 ** attempt
        if wait > MAX_WAIT:
            raise RuntimeError(f"{method}: backoff {wait} s > {MAX_WAIT} s; stopping")
        time.sleep(wait)

def to_at_uri(url):
    """https://bsky.app/profile/<handle-or-did>/post/<rkey> -> at://<handle-or-did>/app.bsky.feed.post/<rkey>
    (the AppView resolves a handle in the URI itself)."""
    m = re.match(r"https://bsky\.app/profile/([^/]+)/post/([^/?#]+)", url)
    if not m:
        raise ValueError(f"not a bsky.app post URL: {url}")
    return f"at://{m.group(1)}/app.bsky.feed.post/{m.group(2)}"

def post_row(post):
    rec = post["record"]
    return {
        "url": f"https://bsky.app/profile/{post['author']['handle']}/post/{post['uri'].rsplit('/', 1)[-1]}",
        "author": post["author"]["handle"],
        "created_at": rec.get("createdAt"),
        "text": redact(rec.get("text")),
        "likes": post.get("likeCount"), "reposts": post.get("repostCount"),
        "replies": post.get("replyCount"), "quotes": post.get("quoteCount"),
    }

on_bsky_tab()
thread = xrpc("app.bsky.feed.getPostThread", {"uri": to_at_uri(POST_URL), "depth": DEPTH, "parentHeight": 0})["thread"]
kind = thread.get("$type", "")
if not kind.endswith("#threadViewPost"):   # notFoundPost / blockedPost come back as 200 with another $type
    raise SystemExit(f"{POST_URL}: thread is {kind}")
author_labels = {l.get("val") for l in thread["post"]["author"].get("labels", [])}
if "!no-unauthenticated" in author_labels:
    raise SystemExit("author asks not to be shown to logged-out users; skipping")

replies = []
for r in thread.get("replies", []):
    t = r.get("$type", "")
    if not t.endswith("#threadViewPost"):
        replies.append({"unavailable": t.rsplit("#", 1)[-1]})
        continue
    if "!no-unauthenticated" in {l.get("val") for l in r["post"]["author"].get("labels", [])}:
        replies.append({"unavailable": "author hides from logged-out users"})
        continue
    replies.append(post_row(r["post"]))
replies.sort(key=lambda x: -(x.get("likes") or 0))
print(json.dumps({"post": post_row(thread["post"]), "loaded_replies": len(replies),
                  "reply_count": thread["post"].get("replyCount"),
                  "replies": replies[:MAX_REPLIES]}, indent=1, ensure_ascii=False))
```

Real output (trimmed; reply authors replaced):

```
{
 "post": {
  "url": "https://bsky.app/profile/atproto.com/post/3mz4m677rsc2o",
  "author": "atproto.com",
  "created_at": "2026-10-30T20:20:51.380Z",
  "text": "A serious Linux kernel vulnerability announced yesterday may impact PDS self-hosters.\n\nCVE-2026-98432 involves mptcp connections, which the Caddy HTTP proxy enables by default.\n\nAn updated container disabling this has been publishes and will auto-deploy to PDS instances in coming hours.",
  "likes": 190,
  "reposts": 62,
  "replies": 7,
  "quotes": 8
 },
 "loaded_replies": 7,
 "reply_count": 7,
 "replies": [
  {
   "url": "https://bsky.app/profile/atproto.com/post/3mz4m67ahbs2o",
   "author": "atproto.com",
   "created_at": "2026-10-30T20:20:51.381Z",
   "text": "Self-hosters can force an immediate Caddy update with:\n\n  sudo pdsadmin update \n\nFor additional confidence, you can disable mptcp system-wide with:\n\n sudo sysctl -w net.mptcp.enabled=0\n\nWe recommend upgrading your system kernel and rebooting as soon as distro packages are available.",
   "likes": 24,
   "reposts": 4,
   "replies": 1,
   "quotes": 3
  },
  {
   "url": "https://bsky.app/profile/<handle>/post/3mz4yxxldg22n",
   "author": "<handle>",
   "created_at": "2026-10-31T00:10:00.685Z",
   "text": "Is it a caddy image update we should be expecting?",
   "likes": 2,
   "reposts": 0,
   "replies": 1,
   "quotes": 0
  },
  {
   "url": "https://bsky.app/profile/<handle>/post/3mz4mei4scs2p",
   "author": "<handle>",
   "created_at": "2026-10-30T20:24:22.047Z",
   "text": "Is this an issue if using Nginx with the pds repo installed manually, without Docker or Caddy?",
   "likes": 1,
   "reposts": 0,
   "replies": 1,
   "quotes": 0
  },
  ...
 ]
}
```

A URL with a DID instead of a handle (`/profile/did:plc:ewvi7nxzyoun6zhxrhs64oiz/post/3mz4m677rsc2o`) returned the same post. A made-up rkey raised `LookupError: app.bsky.feed.getPostThread: NotFound: Post not found: at://did:plc:ewvi7nxzyoun6zhxrhs64oiz/app.bsky.feed.post/3zzzzzzzzzzzz`.

### 5. Same API without a browser (plain HTTP)

The endpoint is a public API, so plain HTTP with a truthful User-Agent works too. Swap this `xrpc()` into blocks 1-4 (and drop `on_bsky_tab()`) to run them with no browser.

```python
import json, time, urllib.error, urllib.parse, urllib.request

API = "https://public.api.bsky.app/xrpc/"
UA = "browser-harness-skill/1.0 (Python urllib)"   # truthful client UA
PAUSE, MAX_WAIT = 0.5, 120

def xrpc(method, params, tries=4):
    """Same contract as the in-tab xrpc(): JSON on 200, LookupError on XRPC 400, raise on anything else."""
    url = API + method + "?" + urllib.parse.urlencode(params, doseq=True)
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
                time.sleep(PAUSE)
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            if e.code == 400:
                err = json.loads(body)
                raise LookupError(f"{method}: {err.get('error')}: {err.get('message')}") from None
            if e.code not in (429, 500, 502, 503, 504) or attempt == tries - 1:
                raise RuntimeError(f"{method} failed with HTTP {e.code}; stopping") from None
            ra = (e.headers.get("Retry-After") or "").strip()
            wait = int(ra) if ra.isdigit() else 15 * 2 ** attempt
        except OSError:          # network error or timeout
            if attempt == tries - 1:
                raise
            wait = 15 * 2 ** attempt
        if wait > MAX_WAIT:
            raise RuntimeError(f"{method}: server asked to wait {wait} s (> {MAX_WAIT} s); stopping")
        time.sleep(wait)

p = xrpc("app.bsky.actor.getProfile", {"actor": "atproto.com"})
feed = xrpc("app.bsky.feed.getAuthorFeed", {"actor": p["did"], "limit": 3, "filter": "posts_no_replies"})
print(p["handle"], p["followersCount"], p["postsCount"])
for it in feed["feed"]:
    print(it["post"]["uri"], it["post"]["record"]["createdAt"], it["post"].get("likeCount"))
print("next cursor:", feed.get("cursor"))
try:
    xrpc("app.bsky.feed.searchPosts", {"q": "atproto", "limit": 5})
except RuntimeError as e:
    print("searchPosts:", e)
```

Real output:

```
atproto.com 121654 289
at://did:plc:ewvi7nxzyoun6zhxrhs64oiz/app.bsky.feed.post/3mz4m677rsc2o 2026-10-30T20:20:51.380Z 190
at://did:plc:ewvi7nxzyoun6zhxrhs64oiz/app.bsky.feed.post/3myzuummxuc2s 2026-10-29T18:18:34.000Z 37
at://did:plc:ewvi7nxzyoun6zhxrhs64oiz/app.bsky.feed.post/3myzq4hil4c2x 2026-10-29T16:53:28.701Z 104
next cursor: 2026-10-29T16:53:28.701Z
searchPosts: app.bsky.feed.searchPosts failed with HTTP 403; stopping
```

## Fields

| Field | Source | Notes |
|---|---|---|
| `handle`, `did` | `profile.handle`, `profile.did` | DID is the stable key; handles can change. Both work as `actor` |
| `followers`, `follows`, `posts` | `followersCount`, `followsCount`, `postsCount` | exact integers; `postsCount` counts own posts and replies, not reposts |
| `bio` | `description` | redacted, first 300 chars |
| `created_at` | `createdAt` | account creation, ISO 8601 |
| `verified` | `verification.verifiedStatus == "valid"` | atproto.com true; bsky.app false |
| `trusted_verifier` | `verification.trustedVerifierStatus == "valid"` | bsky.app true |
| `labels` | `labels[].val` | moderation and self labels, e.g. `porn`, `bot`, `impersonation`, `bridged-from-bridgy-fed-web` (seen in searchActors results) |
| `pinned_post` | `pinnedPost.uri` | `at://` URI or null |
| `kind` (block 2) | `reason.$type` (`#reasonRepost`, `#reasonPin`), `record.reply`, `post.embed.$type` | `post`, `reply`, `quote`, `repost`, `pin` |
| `url` | built from `post.author.handle` + rkey (last part of `post.uri`) | `https://bsky.app/profile/<handle>/post/<rkey>`; for a repost it is the original post |
| `created_at` (posts) | `record.createdAt` | client-set time; `indexedAt` is when the AppView saw it |
| `likes`, `reposts`, `replies`, `quotes` | `likeCount`, `repostCount`, `replyCount`, `quoteCount` | exact integers |
| `embed` | `post.embed.$type` without `app.bsky.embed.` / `#view` | `images`, `external`, `video`, `record`, `recordWithMedia` |
| `reply_to` | `record.reply.parent.uri` | null for top-level posts |
| `cursor` | `getAuthorFeed`: an ISO timestamp; `searchActors`: an opaque base64 string | missing cursor = end of list |

Other raw fields worth knowing: profile `banner`, `associated.lists/feedgens/starterPacks`, `indexedAt`; post `bookmarkCount`, `langs`, `record.facets` (links, mentions, hashtags with byte offsets); feed item `reply.parent/root` (full post views of the thread context).

## Gotchas

- **Page limits are hard.** `limit=101` on getAuthorFeed or searchActors and 26 actors on getProfiles each returned HTTP 400 `InvalidRequest` (`maximum 100`, `maximum 25`).
- **A short page is not the end.** searchActors returned 97 of 100 for "news" with a cursor still present. Only a missing cursor (or an empty page) ends a list; blocks 2 and 3 print `TRUNCATED` when they stop at their cap.
- **The pinned post appears twice** with `includePins=true`: once at the top (`reason.$type = app.bsky.feed.defs#reasonPin`) and again at its date. It also arrives on top of `limit` and ignores `filter` (it led the `posts_with_media` list). Block 2 keeps one row and trims to `MAX_POSTS`.
- **Unknown `filter` values are ignored silently** (`filter=bogus` returned the default feed). Block 2 checks the value first.
- **Reposts are in every filter**, including `posts_no_replies` and `posts_and_author_threads`. Their `post.author` is the original author, not the account you asked for.
- **getProfiles drops unknown actors without an error**; getProfile and getAuthorFeed return HTTP 400 `{"error":"InvalidRequest","message":"Profile not found"}`. A handle and its DID in one request give the same profile twice; block 1 merges them.
- **Handles work inside `at://` URIs** for getPostThread; the error message shows the resolved DID.
- **Logged-out visibility.** Accounts can self-label `!no-unauthenticated` to ask not to be shown to logged-out viewers. The blocks skip those accounts and replies. None turned up in today's runs, so that branch is untested.
- **Failed CORS looks like status 0.** The 403 on searchPosts has no CORS header, so `fetch()` in the tab throws `TypeError: Failed to fetch` instead of showing 403. `xrpc()` retries status 0 once, then raises.
- **Contact data:** bios and posts are free text. bsky.app's own bio has a support email (`[email]` above). The blocks mask emails and 9+ digit phone-like numbers. The phone pattern skips digit runs glued to letters or hyphens, so IDs like `CVE-2026-98432` stay intact.
- **No bot checks** showed up on bsky.app or the API today. On a challenge or an unexplained 403, stop. Do not switch hosts, user agents or sessions to get past it.

## What does not work

- **Post search logged out.** `GET https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?q=atproto&limit=2` returned HTTP 403 with a plain BunnyCDN "403 Forbidden" HTML page (plain HTTP and in-tab `fetch()`; block 5 shows it). `searchActors` on the same host worked in the same minute. bsky.app's `/search?q=atproto` page (allowed by robots.txt) shows "Search is currently unavailable when logged out", and its own `app.bsky.feed.searchPostsV2` calls failed the same way (status 0, retried in a loop). Post search needs a signed-in session, which this skill does not cover.
- **Scraping bsky.app pages** is not needed: the logged-out app renders everything from the same public API calls shown above.
