# Twitch — Live Channels by Category & Channel About Info

Field-tested against www.twitch.tv on 2026-10-24 using a Browser Use cloud browser (directory and channel pages) and plain urllib (channel HTML).

robots.txt (fetched 2026-10-24) for `User-agent: *` allows `/directory`, `/<login>` and `/<login>/about` and disallows `/search`, `/embed/`, `/popout/`, `/chat/` and account pages; `gql.twitch.tv/robots.txt` and `api.twitch.tv/robots.txt` are both `Disallow: /`, so this skill only loads www.twitch.tv pages and never calls those hosts itself.

## Quick summary

- **Live channels for a category** (`/directory/category/<slug>?sort=VIEWER_COUNT`): the HTML is a 222 KB app shell with no stream data, so block 1 renders the page in the browser and reads the channel cards (login, display name, title, viewer count, tags, verified, thumbnail). Infinite scroll adds ~24 cards per step and never removes earlier ones: 150 (VALORANT) and 300 (Just Chatting) channels collected in one tab, and a small category (Super Mario Maker 2) ran to its end at 19 channels (3 scroll steps with no new cards while the scroller sat at its bottom). Every run prints whether the list is complete or was cut at the cap.
- **Category slugs** (`/directory`): block 2 reads the box-art cards (name, slug, viewers, tags). 100 cards returned (109 loaded, reported as truncated at the cap); 1 of them was a `/directory/event/...` page, not a category.
- **Channel about info, no browser** (`/<login>`): plain HTTP GET returned 200 with a JSON-LD `ProfilePage` holding display name, bio, profile image, **exact follower count**, social links and recent VODs/clips; `og:title`/`og:description` add live status, stream title and category (no usable viewer count, see Gotchas). 23 channel fetches at ~1 request/s: 23 x HTTP 200, no 429.
- **Channel about info, browser** (`/<login>/about` + `/<login>`): panels (images, text, links), Partner badge, and the live header with the **exact** current viewer count, uptime and the full tag list.

## What works

### 1. Live channels in a category, many pages (browser)

```python
import json, re, time, urllib.parse

CATEGORY_SLUG = "valorant"      # the <slug> in /directory/category/<slug> (block 2 lists them)
SORT = "VIEWER_COUNT"           # RELEVANCE | VIEWER_COUNT | VIEWER_COUNT_ASC | RECENT
MAX_CHANNELS = 150              # ~24-26 cards load per scroll step
PAUSE = 2.0                     # seconds between scroll steps (polite pacing)

BASE = "https://www.twitch.tv/directory/category/" + urllib.parse.quote(CATEGORY_SLUG, safe="")
URL = BASE + "?" + urllib.parse.urlencode({"sort": SORT})

# Generic bot-check markers (none were seen on Twitch at this pace). On a hit: stop and raise, never retry around it.
CHALLENGE_JS = r"""(() => {
  const t = (document.title + ' ' + (document.body ? document.body.innerText.slice(0, 3000) : '')).toLowerCase();
  return /verify (that )?you are (a )?human|are you a robot|unusual traffic from your|press (and|&) hold/.test(t)
    || !!document.querySelector('iframe[src*="captcha"], iframe[src*="challenges.cloudflare.com"], iframe[src*="arkoselabs"], iframe[src*="funcaptcha"], #challenge-form');
})()"""

def safe_js(expr):
    try:
        return js(expr)
    except Exception:       # the page context is replaced mid-navigation
        return None

def open_page(url, timeout=20):
    """Navigate the attached tab (new tab only if it is not on twitch yet); confirm the exact URL, query included."""
    href = safe_js("location.href") or ""
    if href.startswith("https://www.twitch.tv/"):
        goto_url(url)
    else:
        new_tab(url)
    deadline = time.time() + timeout
    while True:
        href = safe_js("location.href") or ""
        if safe_js(CHALLENGE_JS):
            raise RuntimeError(f"bot check on {href}; stopping (do not retry around it)")
        if href.split("#")[0] == url and safe_js("document.readyState") == "complete":
            return href
        if time.time() > deadline:
            raise RuntimeError(f"expected {url}, tab is on {href}")
        time.sleep(0.5)

CARDS_JS = r"""(() => [...document.querySelectorAll('article')].map(art => {
  const link = art.querySelector('a[data-a-target="preview-card-channel-link"]');
  const img = art.querySelector('a[data-a-target="preview-card-image-link"]');
  if (!link || !img) return null;                     // skips the "May Contain Labeled Content" notice
  const title = link.querySelector('h4');
  const name = link.querySelector('p[title]');
  const stat = img.querySelector('.tw-media-card-stat');
  return {
    login: (link.getAttribute('href') || '').replace(/^\//, ''),
    display_name: name ? name.getAttribute('title') : null,
    title: title ? (title.getAttribute('title') || title.textContent) : null,
    viewers_text: stat ? stat.textContent.trim() : null,
    tags: [...art.querySelectorAll('button.tw-tag')].map(b => b.textContent.trim()),
    verified: [...link.querySelectorAll('svg title')].some(t => t.textContent === 'Verified'),
    thumbnail: (img.querySelector('img.tw-image') || {}).src || null,
  };
}).filter(Boolean))()"""

STATE_JS = r"""(() => {
  const t = (document.querySelector('main') || document.body).innerText;
  if (/Category does not exist/.test(t)) return 'missing';
  if (/No results available/.test(t)) return 'empty'; // category exists, nobody live right now
  return '';
})()"""

# The grid scrolls this inner container; at the true end it sits at its bottom and no new cards arrive.
AT_END_JS = r"""(() => {
  const s = document.querySelector('[data-a-target="root-scroller"]');
  return s ? s.scrollHeight - s.scrollTop - s.clientHeight <= 2 : null;
})()"""
REQUIRED = ("login", "display_name", "title", "viewers_text")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")

def redact(s):
    """Mask emails and phone-like numbers (9+ digits) in free text such as stream titles."""
    if not s:
        return s
    s = EMAIL.sub("[email]", s)
    return PHONE.sub(lambda m: "[phone]" if sum(ch.isdigit() for ch in m.group()) >= 9 else m.group(), s)

def viewers_to_int(s):
    """'27.3K viewers' -> 27300, '762 viewers' -> 762, '1 viewer' -> 1 (Twitch rounds K/M)."""
    m = re.match(r"([\d.,]+)\s*([KM]?)", s or "")
    if not m:
        return None
    n = float(m.group(1).replace(",", ""))
    return int(round(n * {"": 1, "K": 1_000, "M": 1_000_000}[m.group(2)]))

def read_cards(seen, incomplete):
    """Add fully rendered cards to seen; remember logins whose card still lacks a required field."""
    if js(CHALLENGE_JS):
        raise RuntimeError("bot check appeared; stopping, no partial list returned")
    for c in js(CARDS_JS):
        if all(c.get(k) for k in REQUIRED):
            seen.setdefault(c["login"], c)
            incomplete.discard(c["login"])
        elif c.get("login") and c["login"] not in seen:
            incomplete.add(c["login"])

open_page(URL)

# Wait for the first cards (the grid renders client-side after load).
deadline, empty_polls = time.time() + 20, 0
while not js(CARDS_JS):
    if js(CHALLENGE_JS):
        raise RuntimeError("bot check on the category page; stopping")
    state = js(STATE_JS)
    if state == "missing":
        raise SystemExit(f"Twitch says category '{CATEGORY_SLUG}' does not exist")
    empty_polls = empty_polls + 1 if state == "empty" else 0
    if empty_polls >= 3:      # stable empty state, not a loading flash
        break
    if time.time() > deadline:
        raise RuntimeError("no channel cards and no empty-state message within 20 s")
    time.sleep(1)

# Infinite scroll: wheel over the grid until MAX_CHANNELS or a verified end of list.
seen, incomplete, stalls, at_end = {}, set(), 0, empty_polls >= 3
while not at_end and len(seen) < MAX_CHANNELS:
    before = len(seen)
    read_cards(seen, incomplete)
    stalls = stalls + 1 if len(seen) == before else 0
    if len(seen) >= MAX_CHANNELS:
        break
    if stalls >= 3:           # 3 scroll steps with no new card
        if not js(AT_END_JS):
            raise RuntimeError(f"cards stopped loading at {len(seen)} but the list is not at its end; no partial list returned")
        at_end = True
        break
    scroll(js("Math.round(innerWidth * 0.55)"), 450, dy=3000)   # pointer over the grid, not the sidebar
    time.sleep(PAUSE)

deadline = time.time() + 10   # give half-rendered cards a moment, then fail loudly
while incomplete and time.time() < deadline:
    time.sleep(1)
    read_cards(seen, incomplete)
if incomplete:
    raise RuntimeError(f"{len(incomplete)} cards never rendered {REQUIRED}; no partial list returned")

channels = list(seen.values())[:MAX_CHANNELS]
for pos, c in enumerate(channels, 1):
    c["title"] = redact(c["title"])
    c["grid_position"] = pos          # order the cards were appended while scrolling
    c["viewers"] = viewers_to_int(c["viewers_text"])
    c["url"] = "https://www.twitch.tv/" + c["login"]
# Counts change while you scroll, so grid order is only roughly sorted; re-sort by the card counts.
if SORT in ("VIEWER_COUNT", "VIEWER_COUNT_ASC"):
    channels.sort(key=lambda c: c["viewers"] if c["viewers"] is not None else -1, reverse=SORT == "VIEWER_COUNT")
for rank, c in enumerate(channels, 1):
    c["rank"] = rank

status = {"complete": at_end, "stopped_at_cap": not at_end, "loaded": len(seen), "returned": len(channels)}
if at_end:
    print(len(channels), "live channels in", CATEGORY_SLUG, "sorted by", SORT, "- complete, reached the end of the list")
else:
    more = "more were already loaded" if len(seen) > MAX_CHANNELS else "the list may continue"
    print(f"TRUNCATED: stopped at MAX_CHANNELS={MAX_CHANNELS} ({more}); {len(channels)} channels in {CATEGORY_SLUG} sorted by {SORT}")
print(json.dumps(status))
print(json.dumps(channels[:2], indent=1, ensure_ascii=False))
```

Real output (trimmed; channel logins and stream titles replaced):

```
TRUNCATED: stopped at MAX_CHANNELS=150 (more were already loaded); 150 channels in valorant sorted by VIEWER_COUNT
{"complete": false, "stopped_at_cap": true, "loaded": 167, "returned": 150}
[
 {
  "login": "<login>",
  "display_name": "<display name>",
  "title": "<stream title>",
  "viewers_text": "6.4K viewers",
  "tags": ["<tag>", "<tag>", "<tag>"],
  "verified": false,
  "thumbnail": "https://static-cdn.jtvnw.net/previews-ttv/live_user_<login>-640x360.jpg",
  "grid_position": 27,
  "viewers": 6400,
  "url": "https://www.twitch.tv/<login>",
  "rank": 1
 },
 ...
]
```

With `CATEGORY_SLUG = "super-mario-maker-2"` the run reached the end: `19 live channels in super-mario-maker-2 sorted by VIEWER_COUNT - complete, reached the end of the list` and `{"complete": true, "stopped_at_cap": false, "loaded": 19, "returned": 19}`. `tetris` (nobody live) returned 0 channels with `complete: true`; an unknown slug exits with `Twitch says category '<slug>' does not exist`.

Sort values observed in the URL and the resulting order (VALORANT): `RELEVANCE` (sort control reads "Recommended For You"; mixed: 3.1K, 762, 2.8K, 61 ...), `VIEWER_COUNT` ("Viewers (High to Low)"; 3K, 2.8K, 2.6K ...), `VIEWER_COUNT_ASC` ("Viewers (Low to High)"; 0, 0, 0, 1 ...), `RECENT` (newest streams, 0-1 viewers). With no `sort` param the default was not stable: one load showed "Recommended For You", another load the same day showed "Viewers (High to Low)". Always pass `sort`.

With `VIEWER_COUNT`, the raw grid order is not strictly descending over 150+ cards (counts move during the 1-2 minutes of scrolling), so the block keeps that order as `grid_position` and re-sorts by the card count for `rank`.

### 2. List categories to get slugs (browser)

```python
import json, re, time

MAX_CATEGORIES = 100   # ~30 box-art cards load per scroll step
PAUSE = 2.0

# Generic bot-check markers (none were seen on Twitch at this pace). On a hit: stop and raise, never retry around it.
CHALLENGE_JS = r"""(() => {
  const t = (document.title + ' ' + (document.body ? document.body.innerText.slice(0, 3000) : '')).toLowerCase();
  return /verify (that )?you are (a )?human|are you a robot|unusual traffic from your|press (and|&) hold/.test(t)
    || !!document.querySelector('iframe[src*="captcha"], iframe[src*="challenges.cloudflare.com"], iframe[src*="arkoselabs"], iframe[src*="funcaptcha"], #challenge-form');
})()"""

def safe_js(expr):
    try:
        return js(expr)
    except Exception:       # the page context is replaced mid-navigation
        return None

def open_page(url, timeout=20):
    """Navigate the attached tab (new tab only if it is not on twitch yet); confirm the exact URL, query included."""
    href = safe_js("location.href") or ""
    if href.startswith("https://www.twitch.tv/"):
        goto_url(url)
    else:
        new_tab(url)
    deadline = time.time() + timeout
    while True:
        href = safe_js("location.href") or ""
        if safe_js(CHALLENGE_JS):
            raise RuntimeError(f"bot check on {href}; stopping (do not retry around it)")
        if href.split("#")[0] == url and safe_js("document.readyState") == "complete":
            return href
        if time.time() > deadline:
            raise RuntimeError(f"expected {url}, tab is on {href}")
        time.sleep(0.5)

CATS_JS = r"""(() => [...document.querySelectorAll('div.game-card')].map(c => {
  const a = c.querySelector('a[data-a-target="tw-box-art-card-link"]');
  const h = c.querySelector('[data-a-target="tw-card-title"] h2');
  const v = c.querySelector('p a[aria-label*="viewers for"]');
  if (!a || !h) return null;
  return {
    name: h.getAttribute('title') || h.textContent,
    path: a.getAttribute('href'),
    viewers_text: v ? v.textContent.trim() : null,
    tags: [...c.querySelectorAll('.tw-tag')].map(t => t.textContent.trim()),
    box_art: (a.querySelector('img') || {}).src || null,
  };
}).filter(Boolean))()"""

def viewers_to_int(s):
    m = re.match(r"([\d.,]+)\s*([KM]?)", s or "")
    if not m:
        return None
    return int(round(float(m.group(1).replace(",", "")) * {"": 1, "K": 1_000, "M": 1_000_000}[m.group(2)]))

AT_END_JS = r"""(() => {
  const s = document.querySelector('[data-a-target="root-scroller"]');
  return s ? s.scrollHeight - s.scrollTop - s.clientHeight <= 2 : null;
})()"""
REQUIRED = ("name", "path", "viewers_text")

def read_cats(seen, incomplete):
    if js(CHALLENGE_JS):
        raise RuntimeError("bot check appeared; stopping, no partial list returned")
    for c in js(CATS_JS):
        if all(c.get(k) for k in REQUIRED):
            seen.setdefault(c["path"], c)
            incomplete.discard(c["path"])
        elif c.get("path") and c["path"] not in seen:
            incomplete.add(c["path"])

open_page("https://www.twitch.tv/directory")
deadline = time.time() + 20
while not js(CATS_JS):
    if js(CHALLENGE_JS):
        raise RuntimeError("bot check on /directory; stopping")
    if time.time() > deadline:
        raise RuntimeError("no category cards rendered within 20 s")
    time.sleep(1)

seen, incomplete, stalls, at_end = {}, set(), 0, False
while len(seen) < MAX_CATEGORIES:
    before = len(seen)
    read_cats(seen, incomplete)
    stalls = stalls + 1 if len(seen) == before else 0
    if len(seen) >= MAX_CATEGORIES:
        break
    if stalls >= 3:
        if not js(AT_END_JS):
            raise RuntimeError(f"cards stopped loading at {len(seen)} but the list is not at its end; no partial list returned")
        at_end = True
        break
    scroll(js("Math.round(innerWidth * 0.55)"), 450, dy=3000)   # pointer over the grid, not the sidebar
    time.sleep(PAUSE)

deadline = time.time() + 10
while incomplete and time.time() < deadline:
    time.sleep(1)
    read_cats(seen, incomplete)
if incomplete:
    raise RuntimeError(f"{len(incomplete)} category cards never rendered {REQUIRED}; no partial list returned")

cats = []
for rank, c in enumerate(list(seen.values())[:MAX_CATEGORIES], 1):
    kind, _, slug = c["path"].strip("/").partition("/")[2].partition("/")   # "category"/"event", slug
    cats.append({**c, "rank": rank, "kind": kind, "slug": slug,
                 "viewers": viewers_to_int(c["viewers_text"]),
                 "url": "https://www.twitch.tv" + c["path"]})

status = {"complete": at_end, "stopped_at_cap": not at_end, "loaded": len(seen), "returned": len(cats)}
if not at_end:
    more = "more were already loaded" if len(seen) > MAX_CATEGORIES else "the list may continue"
    print(f"TRUNCATED: stopped at MAX_CATEGORIES={MAX_CATEGORIES} ({more})")
print(len(cats), "categories;", sum(c["kind"] == "category" for c in cats), "are /directory/category/ pages")
print(json.dumps(status))
print(json.dumps(cats[:3], indent=1, ensure_ascii=False))
```

Real output (trimmed):

```
TRUNCATED: stopped at MAX_CATEGORIES=100 (more were already loaded)
100 categories; 99 are /directory/category/ pages
{"complete": false, "stopped_at_cap": true, "loaded": 109, "returned": 100}
[
 {"name": "Stream-o-Ween", "path": "/directory/event/stream-o-ween-2026", "viewers_text": "34.4K viewers", "tags": [], "kind": "event", "slug": "stream-o-ween-2026", "viewers": 34400, ...},
 {"name": "Just Chatting", "path": "/directory/category/just-chatting", "viewers_text": "200K viewers", "tags": ["IRL"],
  "box_art": "https://static-cdn.jtvnw.net/ttv-boxart/509658-285x380.jpg", "rank": 2, "kind": "category", "slug": "just-chatting", "viewers": 200000,
  "url": "https://www.twitch.tv/directory/category/just-chatting"},
 {"name": "Call of Duty: Modern Warfare 4", "path": "/directory/category/call-of-duty-modern-warfare-4", "viewers_text": "67.4K viewers", "tags": ["FPS", "Shooter", "Action"], "rank": 3, ...}
]
```

`/directory` is ordered by Twitch's recommendation, not strictly by viewers (rank 98-100 had 375, 3.1K, 3.2K viewers).

### 3. Channel about info from the HTML (no browser, preferred)

```python
import gzip, html, json, re, time, urllib.error, urllib.parse, urllib.request

LOGINS = ["twitchgaming", "twitch", "zzqx_no_such_channel_9871"]
UA = "twitch-channel-about/1.0 (python-urllib; one request per second)"   # truthful client UA
PAUSE = 1.0

BUDGET = 120   # one deadline per channel for every request, backoff and refetch
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")

def redact(s):
    """Mask emails and phone-like numbers (9+ digits) in free text (bios, titles)."""
    if not s:
        return s
    s = EMAIL.sub("[email]", s)
    return PHONE.sub(lambda m: "[phone]" if sum(ch.isdigit() for ch in m.group()) >= 9 else m.group(), s)

# Bot-check markers searched in the WHOLE body of every response (200 or error). A bare "captcha" is not one:
# normal Twitch pages (4 of 4 saved) name a "features.auth.components.captcha.fun-captcha" script chunk.
CHALLENGE_RE = re.compile(
    r"challenges\.cloudflare\.com|/cdn-cgi/challenge-platform|captcha-delivery\.com|px-captcha|g-recaptcha|h-captcha"
    r"|arkoselabs|verify (that )?you are (a )?human|are you a robot|unusual traffic from your"
    r"|<title[^>]*>[^<]*(captcha|access denied|attention required|just a moment)", re.I)

def body(data, headers):
    if (headers.get("Content-Encoding") or "") == "gzip":
        data = gzip.decompress(data)
    return data.decode("utf-8", "replace")

def check_challenge(url, page):
    m = CHALLENGE_RE.search(page)
    if m:
        raise RuntimeError(f"{url}: bot check page (marker {m.group(0)[:60]!r}); stopping, not retrying")

def fetch(url, deadline):
    """GET with exponential backoff on 429/5xx until `deadline`; no sleep when the next try would miss it.
    The body is checked for a bot check before any retry or acceptance."""
    delay = 2
    while True:
        left = deadline - time.time()
        if left <= 0:
            raise TimeoutError(f"{url}: deadline reached")
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip", "Accept-Language": "en-US"})
        try:
            with urllib.request.urlopen(req, timeout=min(20, left)) as r:
                page = body(r.read(), r.headers)
        except urllib.error.HTTPError as e:
            try:
                err_page = body(e.read(), e.headers or {})
            except Exception:          # no readable error body
                err_page = ""
            check_challenge(url, err_page)   # a challenge on a 403/429/5xx stops here, before any retry
            if e.code not in (429, 500, 502, 503, 504) or time.time() + delay >= deadline:
                raise          # 403 and other blocks surface at once; retryable codes stop at the deadline
            time.sleep(delay)
            delay *= 2
            continue
        check_challenge(url, page)
        return page

def meta(page, key):
    for pat in (rf'<meta (?:property|name)="{key}" content="([^"]*)"', rf'<meta content="([^"]*)" (?:property|name)="{key}"'):
        m = re.search(pat, page)
        if m:
            return html.unescape(m.group(1))
    return None

def channel_about(login, attempts=4):
    url = "https://www.twitch.tv/" + urllib.parse.quote(login.lower(), safe="")
    deadline = time.time() + BUDGET          # all requests and waits for one login share this deadline
    for attempt in range(attempts):
        page = fetch(url, deadline)
        graph = []
        for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S):
            graph += json.loads(block).get("@graph", [])
        profile = next((g for g in graph if g.get("@type") == "ProfilePage"), None)
        if profile:
            break
        # Unknown (or unavailable) login: Twitch's generic page, og:title "Twitch" and robots "noindex".
        # A real channel never carries both, so this is a positive "missing" signal, not a fallback.
        if meta(page, "og:title") == "Twitch" and meta(page, "robots") == "noindex":
            return {"login": login, "error": "no such channel (or unavailable)"}
        # Anything else (e.g. a ~217 KB shell with no meta tags and no JSON-LD) is transient: refetch.
        wait = 5 * 2 ** attempt              # 5, 10, 20 s
        if attempt == attempts - 1 or time.time() + wait > deadline:
            break
        time.sleep(wait)
    if not profile:
        raise RuntimeError(f"{url}: no ProfilePage JSON-LD and no 'missing channel' marker after {attempt + 1} tries")
    person = profile.get("mainEntity") or {}
    stat = person.get("interactionStatistic") or {}
    if not person.get("name") or not isinstance(stat.get("userInteractionCount"), int):
        raise RuntimeError(f"{url}: ProfilePage lacks name or follower count; not accepting it")
    videos = next((g for g in graph if g.get("@type") == "ItemList"), {}).get("itemListElement", [])
    title = meta(page, "og:title") or ""
    desc = meta(page, "og:description") or ""
    live = title.endswith(" - Live on Twitch")
    # Live og:description is "<title> | Streaming <category> for N viewers." OR "<title> | Streaming <category>."
    # N is NOT used: it was off by up to 300x versus the live count (see Gotchas). Use block 1 or 4 for viewers.
    m = re.match(r"(.*)\|\s*Streaming (.+?)(?: for \d+ viewers?)?\.$", desc, re.S) if live else None
    if live and not m:
        raise RuntimeError(f"{url}: live, but og:description has an unknown shape: {desc[-80:]!r}")
    return {
        "login": person.get("alternateName") or login,
        "display_name": person.get("name"),
        "url": person.get("url") or url,
        "bio": redact(person.get("description")),
        "profile_image": person.get("image"),
        "followers": stat.get("userInteractionCount"),
        "social_links": [u for u in person.get("sameAs", []) if not u.startswith(("mailto:", "tel:"))],
        "live": live,
        "live_title": redact(m.group(1).strip()) if m else None,
        "live_category": m.group(2) if m else None,   # lowercase category name, e.g. "just chatting"
        "recent_videos": [{"title": redact(v.get("name")), "url": v.get("url"), "uploaded": v.get("uploadDate"),
                           "duration": v.get("duration"),
                           "views": (v.get("interactionStatistic") or {}).get("userInteractionCount")}
                          for v in videos if v.get("@type") == "VideoObject"],
        "page_modified": profile.get("dateModified"),
    }

out = []
for i, login in enumerate(LOGINS):
    if i:
        time.sleep(PAUSE)
    out.append(channel_about(login))
print(json.dumps([{**o, "recent_videos": o["recent_videos"][:2]} if "recent_videos" in o else o for o in out], indent=1, ensure_ascii=False))
```

Real output (trimmed):

```
[
 {
  "login": "twitchgaming",
  "display_name": "twitchgaming",
  "url": "https://www.twitch.tv/twitchgaming",
  "bio": "Join /twitchgaming and be a part of the conversation! ...",
  "profile_image": "https://static-cdn.jtvnw.net/jtv_user_pictures/77eb821f-...-profile_image-300x300.jpeg",
  "followers": 584895,
  "social_links": ["https://twitter.com/twitch", "https://instagram.com/twitch"],
  "live": false, "live_title": null, "live_category": null,
  "recent_videos": [],
  "page_modified": "2023-10-15T02:56:52Z"
 },
 {
  "login": "twitch", "display_name": "Twitch", "followers": 2483231,
  "social_links": ["https://twitter.com/twitch", "https://www.instagram.com/twitch/", "https://www.tiktok.com/@twitch", "https://www.youtube.com/twitch"],
  "recent_videos": [
   {"title": "Let's Chat Episode 14 | ...", "url": "https://www.twitch.tv/videos/2908640776", "uploaded": "2026-10-23T16:55:16Z", "duration": "PT3353S", "views": 8},
   ...
  ], ...
 },
 {"login": "zzqx_no_such_channel_9871", "error": "no such channel (or unavailable)"}
]
```

For live channels the same code returned `"live": true`, `"live_title": "<stream title>"` and `"live_category"` as the lowercase category name (`"valorant"`, `"just chatting"`). `og:description` came in two shapes, and the regex handles both: `"<title> | Streaming valorant for 234 viewers."` and `"<title> | Streaming valorant."` (4 of 13 live VALORANT channels had no count). The HTML never gives a usable viewer count; take viewers from block 1 (card) or block 4 (exact).

### 4. Channel about panels and exact live stats (browser)

```python
import json, re, time, urllib.parse

LOGINS = ["twitchgaming", "twitch"]   # channel logins, e.g. the "login" field from block 1
PAUSE = 2.0                           # seconds between page loads
RENDER_TIMEOUT = 20                   # seconds to wait for a positive live or offline marker

# Generic bot-check markers (none were seen on Twitch at this pace). On a hit: stop and raise, never retry around it.
CHALLENGE_JS = r"""(() => {
  const t = (document.title + ' ' + (document.body ? document.body.innerText.slice(0, 3000) : '')).toLowerCase();
  return /verify (that )?you are (a )?human|are you a robot|unusual traffic from your|press (and|&) hold/.test(t)
    || !!document.querySelector('iframe[src*="captcha"], iframe[src*="challenges.cloudflare.com"], iframe[src*="arkoselabs"], iframe[src*="funcaptcha"], #challenge-form');
})()"""

def safe_js(expr):
    try:
        return js(expr)
    except Exception:       # the page context is replaced mid-navigation
        return None

def open_page(url, timeout=20):
    """Navigate the attached tab (new tab only if it is not on twitch yet); confirm the exact URL, query included."""
    href = safe_js("location.href") or ""
    if href.startswith("https://www.twitch.tv/"):
        goto_url(url)
    else:
        new_tab(url)
    deadline = time.time() + timeout
    while True:
        href = safe_js("location.href") or ""
        if safe_js(CHALLENGE_JS):
            raise RuntimeError(f"bot check on {href}; stopping (do not retry around it)")
        if href.split("#")[0] == url and safe_js("document.readyState") == "complete":
            return href
        if time.time() > deadline:
            raise RuntimeError(f"expected {url}, tab is on {href}")
        time.sleep(0.5)

ABOUT_JS = r"""(() => {
  const main = document.querySelector('main') || document.body;
  if (!main) return null;
  if (/Sorry\. Unless you've got a time machine, that content is unavailable/.test(main.innerText)) return {missing: true};
  const p = document.querySelector('[data-a-target="about-panel"]');
  if (!p || !p.querySelector('h3')) return null;   // panel shell renders before its content
  const f = [...p.querySelectorAll('div')].find(d => / followers?$/.test(d.textContent.trim()) && d.children.length <= 1);
  const name = (document.querySelector('main h1') || {}).textContent || null;
  if (!name || !f) return null;                    // required fields not rendered yet: keep polling
  return {
    display_name: name,
    about_heading: (p.querySelector('h3') || {}).textContent || null,
    followers_text: f.textContent.trim(),
    bio: (p.querySelector('p[dir="auto"]') || {}).textContent || null,
    partner: !!p.querySelector('svg[aria-label="Verified Partner"]'),
    social_links: [...p.querySelectorAll('a[role="link"][target="_blank"]')].map(a => ({label: a.textContent.trim(), url: a.href})),
    panels: [...document.querySelectorAll('[data-test-selector="channel_panel_test_selector"]')].map(x => ({
      text: x.innerText.trim().slice(0, 500),
      images: [...x.querySelectorAll('img')].map(i => ({src: i.src, alt: i.alt || null})),
      links: [...x.querySelectorAll('a[href^="http"]')].map(a => a.href),
    })),
  };
})()"""

# {live: false} only on Twitch's own OFFLINE marker; the live dict only once title, viewers and uptime
# all exist; null while neither has rendered (the live header appeared 3.9-5.1 s after navigation).
LIVE_JS = r"""(() => {
  const t = s => { const e = document.querySelector(s); return e ? e.textContent.trim() : null; };
  const st = document.querySelector('.channel-status-info');
  if (document.querySelector('.channel-root__player--offline') && st && /^OFFLINE\b/.test(st.innerText.trim())) return {live: false};
  const title = t('[data-a-target="stream-title"]');
  const viewers = t('[data-a-target="animated-channel-viewers-count"]');
  const uptime = ((document.querySelector('.live-time') || {}).innerText || '').split('\n')[0] || null;
  if (!title || !viewers || !uptime) return null;
  const g = document.querySelector('[data-a-target="stream-game-link"]');
  return {
    live: true,
    stream_title: title,
    category: g ? g.textContent.trim() : null,
    category_url: g ? g.href : null,
    viewers_text: viewers,
    uptime: uptime,
    tags: [...document.querySelectorAll('main .tw-tag')].map(b => b.textContent.trim()),
  };
})()"""

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")

def redact(s):
    """Mask emails and phone-like numbers (9+ digits) in free text (bios, panels, titles)."""
    if not s:
        return s
    s = EMAIL.sub("[email]", s)
    return PHONE.sub(lambda m: "[phone]" if sum(ch.isdigit() for ch in m.group()) >= 9 else m.group(), s)

def count(s):
    """'585K followers' -> 585000, '1,175' -> 1175 (follower counts are rounded by Twitch)."""
    m = re.match(r"([\d.,]+)\s*([KM]?)", s or "")
    if not m:
        return None
    return int(round(float(m.group(1).replace(",", "")) * {"": 1, "K": 1_000, "M": 1_000_000}[m.group(2)]))

def poll(expr, what, timeout=RENDER_TIMEOUT):
    deadline, err = time.time() + timeout, None
    while True:
        try:
            blocked, r = js(CHALLENGE_JS), js(expr)
        except Exception as e:      # navigation in progress, or a tab that stopped answering
            blocked, r, err = False, None, e
        if blocked:
            raise RuntimeError(f"bot check while waiting for {what}; stopping")
        if r:
            return r
        if time.time() > deadline:
            raise RuntimeError(f"{what} did not render within {timeout} s" + (f"; last JS error: {str(err)[:120]}" if err else ""))
        time.sleep(1)

results = []
for i, login in enumerate(LOGINS):
    if i:
        time.sleep(PAUSE)
    base = "https://www.twitch.tv/" + urllib.parse.quote(login.lower(), safe="")
    open_page(base + "/about")
    about = poll(ABOUT_JS, f"about panel for {login}")
    if about.get("missing"):   # unknown logins: "Sorry. Unless you've got a time machine, that content is unavailable."
        results.append({"login": login, "error": "content unavailable"})
        continue
    about["followers"] = count(about["followers_text"])
    about["bio"] = redact(about["bio"])
    about["social_links"] = [l for l in about["social_links"] if not l["url"].startswith(("mailto:", "tel:"))]
    for x in about["panels"]:
        x["text"] = redact(x["text"])
        x["links"] = [u for u in x["links"] if not u.startswith(("mailto:", "tel:"))]
    time.sleep(PAUSE)
    open_page(base)
    live = poll(LIVE_JS, f"live header or OFFLINE marker for {login}")   # never infer offline from absence
    if live["live"]:
        live["stream_title"] = redact(live["stream_title"])
        live["viewers"] = count(live["viewers_text"])
    results.append({"login": login, "url": base, **about, **live})

print(json.dumps([{**r, "panels": r.get("panels", [])[:2]} for r in results], indent=1, ensure_ascii=False))
```

Real output (trimmed):

```
[
 {
  "login": "twitchgaming",
  "url": "https://www.twitch.tv/twitchgaming",
  "display_name": "twitchgaming",
  "about_heading": "About twitchgaming",
  "followers_text": "585K followers",
  "bio": "Join /twitchgaming and be a part of the conversation! ...",
  "partner": true,
  "social_links": [{"label": "Twitter", "url": "https://twitter.com/twitch"}, {"label": "Instagram", "url": "https://instagram.com/twitch"}],
  "panels": [{"text": "", "images": [...], "links": []}, ...],
  "followers": 585000,
  "live": false
 },
 {"login": "twitch", "display_name": "Twitch", "followers_text": "2.5M followers", "partner": true,
  "panels": [{"text": "", "images": [{"src": "https://panels.twitch.tv/panel-12826-image-...", "alt": "Panel Content"}], "links": ["https://twitter.com/Twitch"]}, ...],
  "live": false, ...}
]
```

With `LOGINS` set to the top 3 VALORANT channels plus an unknown login, the live part read: `"live": true, "stream_title": "<stream title>", "category": "VALORANT", "category_url": "https://www.twitch.tv/directory/category/valorant", "viewers_text": "4,705", "viewers": 4705, "uptime": "0:19:58", "tags": [2 tags]`. The other two gave 2,973 and 2,301 viewers with 10 and 5 tags, and the unknown login gave `{"login": "<login>", "error": "content unavailable"}`.

## Fields

| Field | Source | Notes |
|---|---|---|
| `login` | block 1 card `a[data-a-target="preview-card-channel-link"]` href; block 3 JSON-LD `alternateName` | lowercase, unique key; URL is `https://www.twitch.tv/<login>` |
| `display_name` | card `p[title]`; JSON-LD `mainEntity.name`; about `main h1` | may differ in case or script from `login` |
| `title` / `stream_title` / `live_title` | card `h4[title]`; `[data-a-target="stream-title"]`; `og:description` before ` \| Streaming ` | full text in the `title` attribute |
| `viewers_text`, `viewers` | card `.tw-media-card-stat` (`"27.3K viewers"`, rounded); channel page `[data-a-target="animated-channel-viewers-count"]` (`"1,175"`, exact) | block 1 converts K/M, so card counts are approximate; block 3 has no viewer field on purpose |
| `live_category` (block 3) | `og:description` after ` \| Streaming ` | lowercase category name, not the URL slug (`"just chatting"`) |
| `rank`, `grid_position` (block 1) | position after re-sorting by `viewers`; raw card append order | they differ for `VIEWER_COUNT` on long lists |
| `complete`, `stopped_at_cap`, `loaded`, `returned` (blocks 1, 2 `status`) | scroll loop | `complete` only when the scroller reached its bottom with no new cards for 3 steps (or the empty-state message); otherwise the run hit the cap and prints `TRUNCATED` |
| `tags` | card `button.tw-tag`; channel page `main .tw-tag` | cards showed 1-5 tags, the channel page showed all (10 for one channel whose card showed 3) |
| `verified` | card `svg > title` = `Verified` | |
| `partner` | about panel `svg[aria-label="Verified Partner"]` | |
| `thumbnail` | card `img.tw-image` | `previews-ttv/live_user_<login>-640x360.jpg` |
| `category`, `category_url` | `[data-a-target="stream-game-link"]` | display name and `/directory/category/<slug>` |
| `uptime` | `.live-time` first line | `H:MM:SS` |
| `followers` | JSON-LD `interactionStatistic.userInteractionCount` (exact, `584895`); about panel text (rounded, `585K`) | |
| `bio` | JSON-LD `mainEntity.description`; about `p[dir="auto"]` | |
| `profile_image` | JSON-LD `mainEntity.image` / `og:image` | 300x300 |
| `social_links` | JSON-LD `sameAs`; about `a[role="link"][target="_blank"]` (with labels) | |
| `panels` | `[data-test-selector="channel_panel_test_selector"]` | many are image-only (`alt: "Panel Content"`); links can be sponsor links |
| `recent_videos` | JSON-LD `ItemList` of `VideoObject` | VODs and clips: title, url, uploadDate, ISO duration, views |
| `name`, `slug`, `viewers`, `kind` (block 2) | `div.game-card` h2 `title`, href, `p a[aria-label*="viewers for"]` | `kind` is `category` or `event` |

## Gotchas

- **The grid is client-rendered.** `document.readyState == "complete"` arrives before any card exists; block 1 polls for cards (they appeared within a few seconds). The first `<article>` is a "May Contain Labeled Content" notice with no channel link; block 1 skips it.
- **Empty and missing categories.** A category with nobody live (Tetris on 2026-10-24) shows `No results available`. An unknown slug shows `Category does not exist`.
- **Scrolling** uses mouse-wheel events over the grid (`scroll(x, y, dy=3000)`); the page scrolls an inner container (`[data-a-target="root-scroller"]`), not `window`. Pointing at the left sidebar scrolls the sidebar instead. Twitch shows no end-of-list text or spinner, so the end is: 3 steps with no new cards while that container sits at its bottom (Super Mario Maker 2: scrollTop + clientHeight = scrollHeight). If cards stop arriving while the container is not at its bottom, blocks 1 and 2 raise instead of returning a partial list. Cards that never render a required field also raise.
- **Caps are stops, not results.** `MAX_CHANNELS` / `MAX_CATEGORIES` end the run early and the output says `TRUNCATED`; raise the cap to get more, never treat a capped list as the full category.
- **Viewer counts on cards are rounded** (`3.2K`, `221K`). For exact numbers open the channel page (block 4).
- **The HTML viewer count is wrong, not just late.** It looks frozen from early in the stream: for 9 live VALORANT channels the `og:description` count vs the card count was e.g. 234 vs 2.9K, 677 vs 1.3K, 1 vs 365, 83 vs 364. Against block 4's player header: 234 vs 3,586, 1 vs 359, and 2,323 vs 2,546 for a channel whose HTML had said 2,323 hours earlier too (uptime 7:03:55). Block 3 therefore returns no viewer number; block 4's player header is exact and current.
- **`/about` does not show the live header.** Live title, category, uptime and exact viewers only render on `/<login>`, which is why block 4 loads both pages. On 3 live channels the header appeared 3.9-5.1 s after navigation (a fixed 4 s wait missed one). Offline channels never show it; instead `.channel-root__player--offline` plus a `.channel-status-info` reading `OFFLINE` appeared within ~3 s. Block 4 polls for one of those two positive states and raises after 20 s if neither shows, so a slow page is never reported as offline.
- **Unresponsive tab:** in one long session a live channel tab stopped answering JS (`Runtime.evaluate timed out`) and block 4 raised after 20 s with that error in the message; the same logins ran fine in a fresh cloud browser.
- **The about panel renders an empty shell first**; block 4 waits until its `h3`, the `main h1` name and the follower line all exist. Unknown logins show "Sorry. Unless you've got a time machine, that content is unavailable."
- **Transient shell pages:** 2 of 15 live channels came back HTTP 200 as a ~217 KB page with no meta tags and no JSON-LD; 4 refetches of each a minute later were all normal. Block 3 refetches (5, 10, 20 s) and raises if the profile never appears. It only reports "no such channel" on a positive marker: unknown logins return HTTP 200 with `og:title` = `Twitch` and `<meta name="robots" content="noindex">`, while real channels have `robots` = `index` and the shell page has no meta at all.
- **Consent:** the cloud browser showed a "Cookies & Ads Choices" button; it did not block cards or about pages, so the blocks leave it alone.
- **Pacing:** blocks use 2 s between scroll steps and page loads and 1 request/s for plain HTTP. No 429 or challenge was seen at that rate. Block 3 backs off on 429/5xx under one 120 s deadline per channel that also covers the shell refetches, never sleeps when the next try would miss it, and then raises; a 403 raises at once. Every response body, error statuses included, is checked for a bot check before any retry.
- **Bot checks:** none appeared, so the challenge check is generic (captcha iframes, "verify you are human" style text in the browser; in block 3, specific challenge-vendor markers and that text anywhere in the body of any response, 200 or error). Block 3 does not match a bare `captcha`: all 4 saved channel and directory HTML pages contain it twice as a script-chunk name (`features.auth.components.captcha.fun-captcha`). On a hit every block raises and stops; do not retry, rotate sessions or change the request to get past it.
- **Contact data:** bios, panel text and stream titles are free text and sometimes carry business emails or phone numbers. The blocks mask emails and 9+ digit phone-like numbers (`[email]`, `[phone]`) and drop `mailto:`/`tel:` links before printing.

## What does not work

- **Plain HTTP for live channel lists:** `/directory/category/<slug>` returned 200 with only `BreadcrumbList` and `CollectionPage` JSON-LD and no stream cards. Use the browser (block 1).
- **`gql.twitch.tv`** (the endpoint the page itself uses for the grid) is `Disallow: /` in its robots.txt; this skill does not call it.
- **Helix API without credentials:** `GET https://api.twitch.tv/helix/streams?first=5` returned `401 {"error":"Unauthorized","message":"OAuth token is missing"}`. The official API needs a registered app and token; not covered here.
- **Search:** `/search` is disallowed by robots.txt; find categories through `/directory` (block 2) instead.
