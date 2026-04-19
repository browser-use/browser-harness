# Facebook Groups — mining feeds for posts + external URLs

Field-tested against a logged-in Jay account on 2026-04-18.
**Requires:** Browser Harness driving a real Chrome that is (a) signed into
Facebook and (b) already a member of the target group. Non-member or logged-out
views serve a stripped landing page with no post content.

## What this skill is for

1. Pull the N most recent posts from a named FB group
2. Harvest every external URL that members have shared
3. Hand that URL list to Firecrawl (or `http_get`) for structured scraping at scale
4. Cache post text + author + timestamp for downstream keyword matching

It is NOT for: replying in groups, DMing members, or any write action.

## URL patterns

| What | URL |
|------|-----|
| Group main feed | `https://www.facebook.com/groups/{id_or_slug}` |
| Group "Discussion" tab (canonical feed) | `https://www.facebook.com/groups/{id_or_slug}/?sorting_setting=CHRONOLOGICAL` |
| Single post (permalink) | `https://www.facebook.com/groups/{id_or_slug}/posts/{post_id}/` |
| User's joined-groups feed | `https://www.facebook.com/groups/feed/` |
| List of YOUR groups | `https://www.facebook.com/groups/joins/` |

The `?sorting_setting=CHRONOLOGICAL` flag matters — without it, FB inserts an
algorithmic ranking that hides older posts and shows the same handful of "popular"
items every visit, which kills monitoring use cases.

## DOM anchors (verified 2026-04-18)

FB rewrites class names every few weeks but ARIA roles and stable URL patterns
hold up well. Anchor on those, not on hashed CSS classes.

| Anchor | Selector | Notes |
|--------|----------|-------|
| Each post container | `div[role="article"]` | Stable. One per visible post. |
| Post permalink | `a[href*="/groups/"][href*="/posts/"], a[href*="/groups/"][href*="/permalink/"]` | First match per article = the post link |
| Post body text | `div[data-ad-preview="message"], div[data-ad-comet-preview="message"]` | One of these is the visible body |
| Post author | `h3 a, h4 a` (first inside the article) | Falls back to `strong a` |
| Post timestamp | `a[href*="/posts/"] abbr, a[role="link"] > span > span` (relative time text) | Hover gets the absolute time but the relative string is fine for sorting |
| External link (FB redirector) | `a[href^="https://l.facebook.com/l.php?u="]` | Decode the `u=` param to get the real URL |
| "See more" button on long posts | `div[role="button"]:has(span:contains("See more"))` (use XPath fallback if `:has` is unsupported) | Click before reading body or posts get truncated |

If selectors stop returning results, run the self-inspection block at the bottom
of this file and update this table — that's the workflow, not a fallback.


## Scrolling the feed (lazy load)

FB virtualizes the feed: scrolled-past posts get unmounted from the DOM. So
"scroll then collect" misses old posts. Pattern that works: **collect-as-you-go.**

```python
seen = {}  # post_url -> dict
TARGET = 50  # how many posts to collect
MAX_SCROLLS = 30

for i in range(MAX_SCROLLS):
    new_posts = js("""
      Array.from(document.querySelectorAll('div[role="article"]')).map(el => {
        const link = el.querySelector('a[href*="/groups/"][href*="/posts/"], a[href*="/groups/"][href*="/permalink/"]');
        const body = el.querySelector('div[data-ad-preview="message"], div[data-ad-comet-preview="message"]');
        const author = el.querySelector('h3 a, h4 a, strong a');
        const time = el.querySelector('abbr, a[role="link"] > span > span');
        const externals = Array.from(el.querySelectorAll('a[href^="https://l.facebook.com/l.php?u="]'))
          .map(a => a.href);
        return {
          url: link?.href || null,
          author: author?.innerText || null,
          time: time?.innerText || null,
          body: body?.innerText?.slice(0, 4000) || null,
          externals: externals,
        };
      }).filter(p => p.url)
    """) or []
    for p in new_posts:
        seen.setdefault(p["url"], p)
    if len(seen) >= TARGET:
        break
    scroll(640, 400, dy=900)  # scroll near middle of viewport
    wait(2.5)  # FB needs ~2s to render new batch + a little buffer
```

`wait(2.5)` is the floor. Faster than that and you'll see empty post containers
because React hasn't hydrated them yet.


## Decoding the external-URL redirector

Every external link gets wrapped in `https://l.facebook.com/l.php?u={URL-encoded real URL}&h=...`.
You want the real URL, not the redirector.

```python
from urllib.parse import urlparse, parse_qs, unquote
def decode_fb_link(href):
    if not href.startswith("https://l.facebook.com/l.php"):
        return href
    q = parse_qs(urlparse(href).query)
    return unquote(q["u"][0]) if "u" in q else href
```

## Handoff to Firecrawl (for the public outbound URLs)

Once you have the harvested external list, those URLs are outside FB's walled
garden — public, scrapable by anything. Firecrawl's schema-native extraction
shines here because you want typed results across heterogeneous sources.

```python
# After the scroll loop:
external_urls = []
for p in seen.values():
    for raw in p["externals"]:
        external_urls.append(decode_fb_link(raw))
external_urls = sorted(set(external_urls))
print(f"harvested {len(external_urls)} unique external URLs")

# Hand off to Firecrawl MCP in the calling conversation:
#   firecrawl_extract(
#       urls=external_urls,
#       prompt="Extract product/listing name, price, location, year, and key features.",
#       schema={...}
#   )
```

When Firecrawl isn't available or the pages are simple, `http_get(url)` from
Harness itself is fine — it does a plain HTTP fetch without a browser, works
for static pages, and is the fastest option for bulk.


## Rate-limit discipline

FB notices automation patterns at the account level, not the IP level. Driving
a real logged-in session means Jay's account is the one getting rate-limited if
you get greedy. Keep these floors:

- **≥2 seconds between scrolls** in the collect loop (the `wait(2.5)` above)
- **≥3 seconds between groups** if you're sweeping multiple
- **No more than ~6 groups per hour** for sustained monitoring
- **Don't open the same group more than every 15 minutes** — repeated visits
  within a short window is a heuristic that triggers checkpoints

Symptoms of over-pacing: article containers start rendering with empty bodies,
`/groups/{id}/` redirects to `/checkpoint/`, or the account briefly gets asked
to re-verify a phone or confirm a login from a new device. If that happens,
**stop immediately** and let Jay deal with the UI — don't try to auto-resolve.

## Self-inspection block (run this when selectors stop working)

Paste this into a Harness stdin block to see what anchors currently exist in the
visible feed. Run it on a group you're a member of.

```python
print(js("""
  ({
    articles: document.querySelectorAll('div[role="article"]').length,
    body_preview_a: document.querySelectorAll('div[data-ad-preview="message"]').length,
    body_preview_b: document.querySelectorAll('div[data-ad-comet-preview="message"]').length,
    external_redirectors: document.querySelectorAll('a[href^="https://l.facebook.com/l.php?u="]').length,
    permalink_posts: document.querySelectorAll('a[href*="/groups/"][href*="/posts/"]').length,
    permalink_permalinks: document.querySelectorAll('a[href*="/groups/"][href*="/permalink/"]').length,
  })
"""))
# If any count is 0, the selector drifted. Open DevTools, right-click a visible
# post, inspect, find the new stable attribute (aria-*, data-*), and update the
# DOM anchors table above.
```


## Full example — mine one group, emit JSON for downstream tools

```bash
cd ~/Developer/browser-harness && uv run browser-harness <<'PY'
import json, sys
from urllib.parse import urlparse, parse_qs, unquote

GROUP = "riceLakeBoating"          # slug or numeric id
TARGET = 50                         # how many posts to collect
MAX_SCROLLS = 30

goto(f"https://www.facebook.com/groups/{GROUP}/?sorting_setting=CHRONOLOGICAL")
wait_for_load()
wait(2)

# Abort if FB bounced us
info = page_info()
if "/checkpoint/" in info["url"] or "/login" in info["url"]:
    sys.exit("AUTH_WALL — stop and have Jay re-verify the account.")

seen = {}
for _ in range(MAX_SCROLLS):
    batch = js("""
      Array.from(document.querySelectorAll('div[role="article"]')).map(el => {
        const link = el.querySelector('a[href*="/groups/"][href*="/posts/"], a[href*="/groups/"][href*="/permalink/"]');
        const body = el.querySelector('div[data-ad-preview="message"], div[data-ad-comet-preview="message"]');
        const author = el.querySelector('h3 a, h4 a, strong a');
        const time = el.querySelector('abbr, a[role="link"] > span > span');
        const externals = Array.from(el.querySelectorAll('a[href^="https://l.facebook.com/l.php?u="]')).map(a => a.href);
        return { url: link?.href, author: author?.innerText, time: time?.innerText,
                 body: body?.innerText?.slice(0, 4000), externals };
      }).filter(p => p.url)
    """) or []
    for p in batch:
        seen.setdefault(p["url"], p)
    if len(seen) >= TARGET:
        break
    scroll(640, 400, dy=900)
    wait(2.5)

def decode(u):
    if not u.startswith("https://l.facebook.com/l.php"): return u
    q = parse_qs(urlparse(u).query)
    return unquote(q["u"][0]) if "u" in q else u

posts = list(seen.values())
all_externals = sorted({decode(x) for p in posts for x in p["externals"]})
screenshot(f"/tmp/fb-group-{GROUP}.png", full=True)
print(json.dumps({
    "group": GROUP,
    "post_count": len(posts),
    "posts": posts,
    "external_urls": all_externals,
}, ensure_ascii=False))
PY
```

The JSON on stdout is the handoff payload — parse it in the calling agent and
route `external_urls` into `firecrawl_extract` with whatever schema matches the
downstream task (competitor inventory, pricing intel, boat listings, etc).

## Gotchas log (append when you hit something new)

- **2026-04-18:** Fresh install verified. People-search URL requires login;
  page search `/search/pages/?q=` works the same way. Groups feed defaults to
  algorithmic sort — always append `?sorting_setting=CHRONOLOGICAL`.
