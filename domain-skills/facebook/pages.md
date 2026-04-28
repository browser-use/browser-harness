# Facebook Pages — mining a public Page's feed for posts + external URLs

Companion to `groups.md`. Most of the DOM surface is shared because FB renders
post articles from the same React component in both contexts — the differences
are the **URL shapes**, the **sort options**, and the **rate-limit ceiling**
(Pages are public, so FB is a little more forgiving than in member-gated Groups).

**Requires:** a real Chrome driven by Browser Harness. Logged-in is recommended
but not strictly required — FB Pages are public. Logged-out sessions get more
aggressive "see more" gating and an interstitial login prompt that breaks the
scroll loop after ~5 posts. Stay signed in.

## What this skill is for

1. Pull the N most recent posts from a named FB Page (brand, publisher, local business)
2. Harvest every external URL the Page has linked out to
3. Grab Page metadata — follower count, category, website, verified status
4. Hand the outbound URL list to Firecrawl (or `http_get`) for downstream extraction

It is NOT for: leaving comments, reacting, messaging the Page, or any write action.

## URL patterns

Pages can be addressed by either a vanity slug (`/BoatingOntario.ca`) or a
numeric Page ID (`/100064...`). Vanity is more legible; numeric is more stable
(vanities can be changed by the page owner).

| What | URL |
|------|-----|
| Page main feed (default tab) | `https://www.facebook.com/{vanity_or_id}` |
| Page Posts tab (canonical post feed) | `https://www.facebook.com/{vanity_or_id}/posts` |
| Page About | `https://www.facebook.com/{vanity_or_id}/about` |
| Page Reviews | `https://www.facebook.com/{vanity_or_id}/reviews` |
| Page Videos | `https://www.facebook.com/{vanity_or_id}/videos` |
| Page Events | `https://www.facebook.com/{vanity_or_id}/events` |
| Single post (vanity permalink) | `https://www.facebook.com/{vanity_or_id}/posts/pfbid{...}` |
| Single post (legacy permalink) | `https://www.facebook.com/permalink.php?story_fbid={story_id}&id={page_id}` |
| Single post (story permalink) | `https://www.facebook.com/story.php?story_fbid={story_id}&id={page_id}` |
| Page-search (find a Page by name) | `https://www.facebook.com/search/pages/?q={query}` |

Unlike Groups, Pages do **not** support `?sorting_setting=CHRONOLOGICAL` — the
Posts tab is the closest thing to a chronological view, and it's reverse-chrono
by default. Don't rely on perfect ordering: pinned posts always appear first,
and FB occasionally reorders the top few based on engagement.

## DOM anchors

Post-article anchors are **the same as groups.md** because the feed component
is shared. Page-chrome anchors (header, about-rail, tabs) are specific to Pages.

| Anchor | Selector | Notes |
|--------|----------|-------|
| Page display name | `h1` (first on page) | Stable — FB has rendered Page name as the top-level `h1` for years |
| Verified badge | `h1 svg[aria-label*="Verified"]` | Present on verified Pages only |
| Follower/like count | `a[href$="/followers/"], a[href$="/friends_likes/"]` | Text node contains the count — parse with a regex |
| Category line | `div[role="main"] span:has(a[href*="/pages/category/"])` | Sits under the name in the header |
| Website link in header | `a[href^="https://l.facebook.com/l.php"][href*="u="]` inside the About rail | Same redirector wrapper as post links — decode before using |
| Each post container | `div[role="article"]` | Same as groups |
| Post permalink | `a[href*="/posts/"][href*="pfbid"], a[href*="/permalink.php"], a[href*="/story.php"]` | Page posts use `pfbid...` style or the legacy `permalink.php`/`story.php` shapes |
| Post body text | `div[data-ad-preview="message"], div[data-ad-comet-preview="message"]` | Same as groups |
| Post author | `h3 a, h4 a, strong a` | On a Page, this is always the Page itself — useful only for sanity checking you're still on the right Page |
| Post timestamp | `a[href*="/posts/"] abbr, a[role="link"] > span > span` | Hover returns absolute time; relative string is fine for sorting |
| External link (FB redirector) | `a[href^="https://l.facebook.com/l.php?u="]` | Decode the `u=` param |
| "See more" on long posts | `div[role="button"]:has(span:contains("See more"))` | Click before reading body or posts get truncated |

If a selector stops returning results, run the self-inspection block at the
bottom and update this table — that's the workflow, not a fallback.

## Extracting Page metadata (header block)

Unlike a Group, a Page's header carries useful signal on its own — category,
verified, follower count, website. Pull it in one JS call before you start
scrolling the feed.

```python
meta = js("""
  ({
    name: document.querySelector('h1')?.innerText || null,
    verified: !!document.querySelector('h1 svg[aria-label*="Verified"]'),
    followers: (Array.from(document.querySelectorAll('a'))
      .find(a => /followers$/.test(a.getAttribute('href')||''))?.innerText) || null,
    likes: (Array.from(document.querySelectorAll('a'))
      .find(a => /friends_likes$/.test(a.getAttribute('href')||''))?.innerText) || null,
    category: (Array.from(document.querySelectorAll('a[href*="/pages/category/"]'))[0]?.innerText) || null,
    website_redirector: (Array.from(document.querySelectorAll('a[href^="https://l.facebook.com/l.php"]'))
      .find(a => !a.closest('div[role="article"]'))?.href) || null,
  })
""")
```

Decode `website_redirector` with the same helper as post links (see below).

## Scrolling the feed (lazy load)

Same collect-as-you-go pattern as groups. FB virtualizes the Page feed too —
scrolled-past posts unmount, so scroll-then-collect loses them.

```python
seen = {}  # permalink -> dict
TARGET = 50
MAX_SCROLLS = 30

for i in range(MAX_SCROLLS):
    batch = js("""
      Array.from(document.querySelectorAll('div[role="article"]')).map(el => {
        const link = el.querySelector('a[href*="/posts/"][href*="pfbid"], a[href*="/permalink.php"], a[href*="/story.php"]');
        const body = el.querySelector('div[data-ad-preview="message"], div[data-ad-comet-preview="message"]');
        const time = el.querySelector('abbr, a[role="link"] > span > span');
        const externals = Array.from(el.querySelectorAll('a[href^="https://l.facebook.com/l.php?u="]'))
          .map(a => a.href);
        return {
          url: link?.href || null,
          time: time?.innerText || null,
          body: body?.innerText?.slice(0, 4000) || null,
          externals: externals,
        };
      }).filter(p => p.url)
    """) or []
    for p in batch:
        seen.setdefault(p["url"], p)
    if len(seen) >= TARGET:
        break
    scroll(640, 400, dy=900)
    wait(2.5)
```

Notes:
- Page feeds are usually **less dense** than active Group feeds — a slow Page
  may only render 8–15 posts total before you hit the footer. Use
  `if len(batch) == 0 for two consecutive iterations` as a stop condition.
- Pinned posts re-appear at the top on every fresh load. The `seen` dict
  dedupes them naturally via permalink.

## Decoding the external-URL redirector

Identical to groups.md — every outbound link is wrapped in
`https://l.facebook.com/l.php?u={URL-encoded real URL}&h=...`. Strip the wrapper.

```python
from urllib.parse import urlparse, parse_qs, unquote
def decode_fb_link(href):
    if not href.startswith("https://l.facebook.com/l.php"):
        return href
    q = parse_qs(urlparse(href).query)
    return unquote(q["u"][0]) if "u" in q else href
```

## Handoff to Firecrawl

Same pattern as groups — Pages are the walled-garden surface that Harness is
good at; the external URLs the Page has shared are public and better suited to
Firecrawl's schema-native extraction.

```python
external_urls = sorted({decode_fb_link(x) for p in seen.values() for x in p["externals"]})
print(f"harvested {len(external_urls)} unique external URLs from Page")
# In the calling conversation:
#   firecrawl_extract(urls=external_urls, prompt="...", schema={...})
```

## Rate-limit discipline

Pages are public, so the ceiling is higher than Groups — but the account-level
detection still applies, because you're driving a real logged-in session.

- **≥2 seconds between scrolls** inside the collect loop
- **≥2 seconds between Pages** if you're sweeping multiple (down from 3s for Groups)
- **No more than ~12 Pages per hour** for sustained monitoring (up from 6 Groups/hr)
- **Don't re-open the same Page within 10 minutes** — repeated hits inside a
  short window is a heuristic that triggers soft-throttling even on public content

Symptoms of over-pacing: the "See more" links on long posts stop being clickable,
the login interstitial appears even though you're signed in, or the URL silently
redirects to `/login/device-based/`. If any of those fire, **stop**, let Jay look
at the screen, and don't try to auto-resolve.

## Self-inspection block (run when selectors stop working)

```python
print(js("""
  ({
    articles: document.querySelectorAll('div[role="article"]').length,
    body_preview_a: document.querySelectorAll('div[data-ad-preview="message"]').length,
    body_preview_b: document.querySelectorAll('div[data-ad-comet-preview="message"]').length,
    external_redirectors: document.querySelectorAll('a[href^="https://l.facebook.com/l.php?u="]').length,
    pfbid_posts: document.querySelectorAll('a[href*="/posts/"][href*="pfbid"]').length,
    permalink_php: document.querySelectorAll('a[href*="/permalink.php"]').length,
    story_php: document.querySelectorAll('a[href*="/story.php"]').length,
    h1_present: !!document.querySelector('h1'),
  })
"""))
# If any count is 0 on a Page you know has posts, the selector drifted.
# Open DevTools, inspect a post, find the new stable attribute, update the
# DOM anchors table above.
```

## Full example — mine one Page, emit JSON for downstream tools

```bash
cd ~/Developer/browser-harness && uv run browser-harness <<'PY'
import json, sys
from urllib.parse import urlparse, parse_qs, unquote

PAGE = "BoatingOntario.ca"   # vanity slug OR numeric Page ID
TARGET = 30
MAX_SCROLLS = 25

goto_url(f"https://www.facebook.com/{PAGE}/posts")
wait_for_load()
wait(3)

info = page_info()
if "/checkpoint/" in info["url"] or "/login" in info["url"]:
    sys.exit("AUTH_WALL — stop and have the account re-verify.")

# Header metadata
meta = js("""
  ({
    name: document.querySelector('h1')?.innerText || null,
    verified: !!document.querySelector('h1 svg[aria-label*="Verified"]'),
    category: (Array.from(document.querySelectorAll('a[href*="/pages/category/"]'))[0]?.innerText) || null,
    followers: (Array.from(document.querySelectorAll('a'))
      .find(a => /followers$/.test(a.getAttribute('href')||''))?.innerText) || null,
    website_redirector: (Array.from(document.querySelectorAll('a[href^="https://l.facebook.com/l.php"]'))
      .find(a => !a.closest('div[role="article"]'))?.href) || null,
  })
""")

# Feed sweep
seen = {}
empty_streak = 0
for _ in range(MAX_SCROLLS):
    batch = js("""
      Array.from(document.querySelectorAll('div[role="article"]')).map(el => {
        const link = el.querySelector('a[href*="/posts/"][href*="pfbid"], a[href*="/permalink.php"], a[href*="/story.php"]');
        const body = el.querySelector('div[data-ad-preview="message"], div[data-ad-comet-preview="message"]');
        const time = el.querySelector('abbr, a[role="link"] > span > span');
        const externals = Array.from(el.querySelectorAll('a[href^="https://l.facebook.com/l.php?u="]')).map(a => a.href);
        return { url: link?.href, time: time?.innerText,
                 body: body?.innerText?.slice(0, 4000), externals };
      }).filter(p => p.url)
    """) or []
    before = len(seen)
    for p in batch:
        seen.setdefault(p["url"], p)
    empty_streak = empty_streak + 1 if len(seen) == before else 0
    if len(seen) >= TARGET or empty_streak >= 2:
        break
    scroll(640, 400, dy=900)
    wait(2.5)

def decode(u):
    if not u.startswith("https://l.facebook.com/l.php"): return u
    q = parse_qs(urlparse(u).query)
    return unquote(q["u"][0]) if "u" in q else u

posts = list(seen.values())
if meta.get("website_redirector"):
    meta["website"] = decode(meta["website_redirector"])
all_externals = sorted({decode(x) for p in posts for x in p["externals"]})
capture_screenshot(f"/tmp/fb-page-{PAGE}.png", full=True)
print(json.dumps({
    "page": PAGE,
    "meta": meta,
    "post_count": len(posts),
    "posts": posts,
    "external_urls": all_externals,
}, ensure_ascii=False))
PY
```

The stdout JSON is the handoff payload — parse it in the calling agent and
route `external_urls` into `firecrawl_extract`, route `meta` into a
competitor-intel table, or feed `posts` into keyword matching.

## When to reach for pages.md vs groups.md

| If the URL is... | Use |
|------------------|-----|
| `facebook.com/groups/{id_or_slug}` | `groups.md` |
| `facebook.com/{vanity}` or `facebook.com/{numeric_id}` | `pages.md` |
| `facebook.com/profile.php?id={id}` | neither — that's a **personal profile**, different DOM and much stricter rate limits |
| `facebook.com/marketplace/...` | neither — dedicated Marketplace skill needed |

A quick way to tell Pages from personal profiles when the URL shape is
ambiguous: Pages have an `h1` with a verified-badge slot and a category link
underneath; personal profiles have a cover photo component and a "Friends" tab.

## Gotchas log (append when you hit something new)

- **Initial version:** Post-article selectors inherited from `groups.md` because
  FB renders the feed article component identically across Group and Page
  contexts. Run the self-inspection block on first live use to confirm no drift
  since the groups.md verification date, and append a note here with what you
  found.
