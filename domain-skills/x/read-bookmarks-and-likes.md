# Reading Bookmarks and Likes on x.com

Covers bulk-reading your own bookmarks (`x.com/i/bookmarks`) and likes
(`x.com/<handle>/likes`) via network capture instead of DOM scraping. Both routes
redirect to a combined page, `x.com/i/history`, with `Bookmarks`/`Likes` tabs; the
likes tab's real URL is `x.com/i/history/likes`.

## Prefer CDP Network capture over a `window.fetch` monkey-patch

The standard trick of overriding `window.fetch` via
`Page.addScriptToEvaluateOnNewDocument` to capture GraphQL responses **does not work
here** -- the bookmarks/likes pagination calls go through `XMLHttpRequest`, not
`fetch`. A `fetch` patch will sit at 0 captures forever while the page visibly keeps
loading more tweets.

Use the CDP `Network` domain directly instead:

```python
cdp("Network.enable")
goto("https://x.com/i/bookmarks")   # or https://x.com/<handle>/likes
wait_for_load()
# ... scroll loop (see below) ...
for e in drain_events():
    if e["method"] != "Network.responseReceived":
        continue
    url = e["params"]["response"]["url"]
    if "/graphql/" not in url or "Bookmarks" not in url:  # "Likes" for the likes tab
        continue
    body = cdp("Network.getResponseBody", requestId=e["params"]["requestId"])["body"]
```

GraphQL operation names: the bookmarks timeline call's URL contains
`/graphql/<queryId>/Bookmarks`; the likes timeline call's URL contains
`/graphql/<queryId>/Likes`. Both are plain-text JSON (`base64Encoded: False` in the
`getResponseBody` result), ~50-150KB per page of ~20 tweets.

**Trap: the daemon only enables `Network` on the page it first attaches to.**
`daemon.py`'s `attach_first_page()` enables `Page`/`DOM`/`Runtime`/`Network` once, at
daemon startup, on whatever tab it first attaches to. A tab opened later with
`new_tab()` only gets `Page` re-enabled by `set_session` -- not `Network`. Call
`cdp("Network.enable")` yourself right after `new_tab()`/`switch_tab()` before relying
on `Network.responseReceived` events, or you'll see `drain_events()` return zero
`Network.*` events and wrongly conclude nothing is happening.

**Trap: drain the event buffer every scroll step, not every few.** The daemon's event
buffer is a `deque(maxlen=500)`. A tweet-dense page generates ~15-30 `Network.*`
events per paginated response, but an image/video-heavy page (the Likes tab
especially) can blow past 500 events between two scroll steps if you batch several
scrolls before calling `drain_events()` -- the responses you actually want get evicted
before you ever see them. Drain after *every single* scroll step.

## Trap: pagination silently stops firing on an unfocused tab

This is the big one. X's infinite-scroll fetch is gated on the tab actually being
visible and focused (`document.visibilityState === 'visible'` and
`document.hasFocus() === true`), not just the "active" CDP target. A tab created via
`new_tab()` on a browser window that was never brought to the OS foreground (e.g. a
background Chrome instance started by launchd, never clicked into) sits at
`visibilityState: 'hidden'` / `hasFocus(): false` even though `Target.activateTarget`
already made it the active tab *within* Chrome. Symptom: `window.scrollTo(...)`
genuinely moves `scrollY` and the document visibly grows for the first page or two
(content that was already queued), then growth and all pagination silently stop dead,
with no error and no new `Network.responseReceived` events, no matter how long you
wait or how often you scroll.

Fix -- two CDP calls, no OS-level window-manager calls needed (those can target the
wrong Chrome window/process on a box running more than one Chrome instance, e.g. the
user's real Chrome *and* a separate automation profile):

```python
cdp("Page.bringToFront")
cdp("Emulation.setFocusEmulationEnabled", enabled=True)
```

Do this once, right after navigating (and again after any later navigation in the
same session, as `bringToFront` doesn't need repeating but it doesn't hurt). Verify
with `js("document.visibilityState")` / `js("document.hasFocus()")` if pagination
still looks stuck -- `'visible'` / `True` means the fix took.

## Scrolling

Window-level scroll works directly here -- `js("window.scrollTo(0,
document.documentElement.scrollHeight)")` -- the timeline is not a nested
virtualized-scroll container, unlike some other SPAs. No need to find a specific
scroll container.

## Detecting "reached the end"

`document.documentElement.scrollHeight` stops growing once there's nothing left to
page in. In practice: track unique tweet `rest_id`s extracted from each captured
response body, and stop once several consecutive scroll+drain rounds in a row add zero
new ids (5-8 rounds is a safe margin -- a single round occasionally adds 0 new tweets
even mid-timeline, e.g. a page of already-seen retweets-with-comments).

## Extracting tweets from a captured response body

Each GraphQL response is a deeply nested `instructions` tree. Don't try to parse the
shape -- walk the whole JSON tree and pull out every dict with
`__typename == "Tweet"`:

```python
def extract_tweets(root, out, seen_ids):
    stack = [root]
    while stack:
        o = stack.pop()
        if isinstance(o, dict):
            if o.get("__typename") == "Tweet" and "rest_id" in o:
                rid = o["rest_id"]
                if rid not in seen_ids:
                    seen_ids.add(rid); out.append(o)
            stack.extend(o.values())
        elif isinstance(o, list):
            stack.extend(o)
```

Each matched `Tweet` dict is self-contained: author is at
`core.user_results.result.core.{screen_name,name}`, text at `legacy.full_text` (use
`note_tweet.note_tweet_results.result.text` instead when present -- it's the
untruncated long-form text), external links (not media) at
`legacy.entities.urls[].expanded_url`, quoted tweet at
`quoted_status_result.result` (same shape, recursively), media type list at
`legacy.extended_entities.media[].type` / falls back to `legacy.entities.media`.

## Getting a reply thread's full text

A bookmarked/liked tweet's own payload normally does **not** include its thread
replies. To get a self-thread's full text, visit the tweet's permalink
(`x.com/<handle>/status/<id>`) and capture the `TweetDetail` GraphQL operation the
same way (`"/graphql/" in url and "TweetDetail" in url`). The response includes the
whole visible conversation; filter to tweets whose author `screen_name` matches the
URL's handle and sort by `created_at` to reconstruct the thread, dropping replies to
other people's comments.

## Trap: a CDP `exec()`'d script can't recurse into its own top-level functions

Not X-specific, but bit every run of this: `run.py` executes the piped script via
`exec(sys.stdin.read())` *inside* `main()`, so top-level `def`s land in `main()`'s
locals while the function body's own lookups resolve against module globals --
calling a top-level function from within itself (recursion) raises `NameError: name
'...' is not defined` even though the same name is clearly defined and callable from
outside. Write iterative (stack/worklist) tree-walkers instead of recursive ones in
scripts piped into `browser-harness`, as in `extract_tweets` above.

## Pacing

No rate-limiting observed reading ~1,800 tweets (224 bookmarks + ~1,620 likes) across
~95 paginated requests in two back-to-back sessions, at roughly 1.3-1.8s between
scroll steps.
