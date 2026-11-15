# Google Play — App Details and Developer App Lists

Field-tested against play.google.com on 2026-10-23 using plain HTTP (Python urllib) and a Browser Use cloud browser.

robots.txt (checked 2026-10-23) for `User-agent: *` disallows /store/search and /_ (which covers /_/PlayStoreUi/data/batchexecute), and has no rule matching /store/apps/details or /store/apps/developer, the only paths this skill requests.

## Quick summary

- **App detail pages** (`/store/apps/details?id=<package>`) return the full record over plain HTTP: one JSON-LD `SoftwareApplication` block plus `AF_initDataCallback` JSON blobs. Every field people ask for (title, developer, rating, ratings count, installs, price, category, last updated, version, content rating) is in there. No browser needed.
- **Developer pages** (`/store/apps/developer?id=<exact name>`) render that developer's first 20 apps on load (Google LLC 20, Microsoft Corporation 20, Rovio Entertainment Oy 16, Mojang 3). The page loads more only when scrolled, through /_/PlayStoreUi/data/batchexecute, which robots.txt disallows, so this skill reads the first load and flags a full page of 20 as possibly incomplete.
- A name that does not match a developer exactly gives a Not Found page.
- The skill does not use search: /store/search is disallowed by robots.txt. Start from package names you already have, or from a developer page.
- Across today's runs (detail pages over HTTP at 0.5-1 s spacing, detail and developer pages in the browser): no 429, no CAPTCHA, no consent interstitial.
- The plain-HTTP code sends a truthful client User-Agent (`browser-harness-skill/1.0 (Python urllib)`); Play served detail pages to it normally.

## What works

### 1. Details for package names (plain HTTP only)

Runs as a single script. `play_app()` handles one package name. Every request retries 429/5xx and network errors with backoff (honouring `Retry-After` as seconds or an HTTP date, up to `MAX_WAIT` = 120 s) and raises if it still fails or if the server asks for a longer wait, so a failed fetch is never a silent gap.

```python
import re, json, time, email.utils, urllib.parse, urllib.request, urllib.error

H = {"User-Agent": "browser-harness-skill/1.0 (Python urllib)", "Accept-Language": "en-US,en;q=0.9"}
HL, GL = "en_US", "US"          # language and store country (country sets currency and availability)
RETRY_CODES = {429, 500, 502, 503, 504}
MAX_WAIT = 120                  # seconds; a longer Retry-After stops the run instead of sleeping

def _retry_after(value):
    """Retry-After as seconds, or as an HTTP date; None if absent or unparseable."""
    if not value:
        return None
    if value.strip().isdigit():
        return int(value.strip())
    try:
        return max(0.0, email.utils.parsedate_to_datetime(value).timestamp() - time.time())
    except (TypeError, ValueError):
        return None

def fetch(url, tries=4):
    """GET. Retries 429/5xx and network errors with backoff, then raises.
    Raises at once if Retry-After asks for more than MAX_WAIT seconds.
    Other HTTP errors (404 included) raise urllib.error.HTTPError immediately."""
    for i in range(tries):
        req = urllib.request.Request(url, headers=H)
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read().decode()
        except urllib.error.HTTPError as e:
            if e.code not in RETRY_CODES or i == tries - 1:
                raise
            wait = _retry_after(e.headers.get("Retry-After"))
            if wait is not None and wait > MAX_WAIT:
                raise RuntimeError(f"HTTP {e.code}: server asked to wait {wait:.0f}s (> {MAX_WAIT}s); stopping") from e
            wait = wait if wait is not None else 2 ** (i + 1)
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if i == tries - 1:
                raise
            wait = 2 ** (i + 1)
        time.sleep(wait)

def callbacks(html):
    """Yield every AF_initDataCallback payload embedded in a Play page."""
    for m in re.finditer(r"AF_initDataCallback\(\{key: '(ds:\d+)', hash: '\d+', data:(.*?), sideChannel: \{\}\}\);</script>", html, re.S):
        try:
            yield m.group(1), json.loads(m.group(2))
        except ValueError:
            pass

def g(o, *path):
    """Safe nested index: returns None instead of raising."""
    for p in path:
        try:
            o = o[p]
        except (IndexError, KeyError, TypeError):
            return None
    return o

def num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None

def text(x):
    return x if isinstance(x, str) else None

def ld_num(x):
    """JSON-LD numbers are strings ('4.34', '36528069'); None if absent or not a number."""
    try:
        return float(x) if x not in (None, "") else None
    except (TypeError, ValueError):
        return None

def first(*vals):
    return next((v for v in vals if v is not None), None)

def offer_fields(o):
    """[micros, currency, text] -> (price, currency, price_text). Free apps have micros 0 and an empty text."""
    o = o if isinstance(o, list) else []
    micros = num(g(o, 0))
    return ((micros / 1e6) if micros is not None else None, text(g(o, 1)),
            text(g(o, 2)) or ("Free" if micros == 0 else None))

def ld_app(html, app_id):
    """The JSON-LD SoftwareApplication block whose url carries id=<app_id>, or {}.
    A block with no url (or a url without id) is never assumed to be this app."""
    for m in re.finditer(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
        try:
            d = json.loads(m.group(1))
        except ValueError:
            continue
        for item in (d if isinstance(d, list) else [d]):
            if not isinstance(item, dict) or "applicationCategory" not in item:
                continue
            ids = urllib.parse.parse_qs(urllib.parse.urlparse(text(item.get("url")) or "").query).get("id")
            if ids == [app_id]:
                return item
    return {}

def ld_author(ld):
    a = ld.get("author")
    a = a[0] if isinstance(a, list) and a else a
    return text(a.get("name")) if isinstance(a, dict) else text(a)

def play_app(app_id):
    """Full detail record for one package name, or None if Play returns HTTP 404
    or the page has neither app data nor JSON-LD for this id."""
    url = "https://play.google.com/store/apps/details?" + urllib.parse.urlencode({"id": app_id, "hl": HL, "gl": GL})
    try:
        html = fetch(url)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    a = next((g(d, 1, 2) for _, d in callbacks(html) if g(d, 1, 2, 77, 0) == app_id), None)
    ld = ld_app(html, app_id)
    if a is None and not ld:
        return None          # not an app page (removed app, region-locked, or an error page)
    price, currency, price_text = offer_fields(g(a, 57, 0, 0, 0, 0, 1, 0))
    agg = ld.get("aggregateRating") if isinstance(ld.get("aggregateRating"), dict) else {}
    offer = ld.get("offers")
    offer = offer[0] if isinstance(offer, list) and offer else offer
    offer = offer if isinstance(offer, dict) else {}
    ld_count = ld_num(agg.get("ratingCount"))
    price = first(price, ld_num(offer.get("price")))
    ads = g(a, 48)                   # ["Contains ads"] when the app has ads, null when it has none
    return {
        "app_id": app_id,
        "title": text(g(a, 0, 0)) or text(ld.get("name")),
        "developer": text(g(a, 68, 0)) or ld_author(ld),
        "developer_id": text(g(a, 68, 2)),
        "rating": first(num(g(a, 51, 0, 1)), ld_num(agg.get("ratingValue"))),
        "ratings_count": first(num(g(a, 51, 2, 1)), int(ld_count) if ld_count is not None else None),
        "installs": text(g(a, 13, 0)),
        "min_installs": num(g(a, 13, 1)),
        "installs_exact": num(g(a, 13, 2)),
        "price": price,
        "currency": currency or text(offer.get("priceCurrency")),
        "price_text": price_text or ("Free" if price == 0 else None),
        "category": text(g(a, 79, 0, 0, 0)),
        "category_id": text(g(a, 79, 0, 0, 2)) or text(ld.get("applicationCategory")),
        "updated": text(g(a, 145, 0, 0)),
        "updated_ts": num(g(a, 145, 0, 1, 0)),
        "version": text(g(a, 140, 0, 0, 0)) or ("Varies with device" if a else None),
        "content_rating": text(g(a, 9, 0)) or text(ld.get("contentRating")),
        "released": text(g(a, 10, 0)),
        "contains_ads": True if text(g(ads, 0)) else (False if a is not None and ads is None else None),
        "in_app_purchases": text(g(a, 19, 0)),
        "url": url,
    }

# --- 1) full records for a few package names, including one that does not exist ---
for app_id in ["com.spotify.music", "com.mojang.minecraftpe", "org.videolan.vlc", "com.example.does.not.exist"]:
    rec = play_app(app_id)
    print(json.dumps(rec) if rec else f"{app_id}: no record (HTTP 404, or no data for this id on the page)")
    time.sleep(1)

# --- 2) a batch of package names (for example from a developer page, block 3), one request per second ---
batch = ["com.whatsapp", "com.instagram.android", "com.google.android.youtube", "com.microsoft.teams", "com.rovio.baba",
         "com.ninjakiwi.bloonstd6", "com.mojang.minecraftedu", "com.duolingo", "com.netflix.mediaclient", "com.android.chrome"]
rows, missing = [], []
for app_id in batch:
    rec = play_app(app_id)
    if rec:
        rows.append(rec)
    else:
        missing.append(app_id)
    time.sleep(1)
print("detailed:", len(rows), "of", len(batch), "missing:", missing)
for r in rows[:5]:
    print(r["app_id"], "|", r["title"], "|", r["developer"], "|", r["rating"], r["ratings_count"], "|",
          r["installs"], "|", r["price_text"], "|", r["category"], "|", r["updated"], "|", r["version"], "|", r["content_rating"])
```

Output (from the run on 2026-10-23):

```text
{"app_id": "com.spotify.music", "title": "Spotify: Music and Podcasts", "developer": "Spotify AB", "developer_id": "6523013212965523194", "rating": 4.3489933, "ratings_count": 36528069, "installs": "1,000,000,000+", "min_installs": 1000000000, "installs_exact": 3171683950, "price": 0.0, "currency": "USD", "price_text": "Free", "category": "Music & Audio", "category_id": "MUSIC_AND_AUDIO", "updated": "Oct 23, 2026", "updated_ts": 1792759042, "version": "Varies with device", "content_rating": "Teen", "released": "May 27, 2014", "contains_ads": true, "in_app_purchases": "$4.99 - $203.88 per item", "url": "https://play.google.com/store/apps/details?id=com.spotify.music&hl=en_US&gl=US"}
{"app_id": "com.mojang.minecraftpe", "title": "Minecraft: Dream it, Build it!", "developer": "Mojang", "developer_id": "4772240228547998649", "rating": 4.303256, "ratings_count": 5866778, "installs": "50,000,000+", "min_installs": 50000000, "installs_exact": 99618770, "price": 6.99, "currency": "USD", "price_text": "$6.99", "category": "Arcade", "category_id": "GAME_ARCADE", "updated": "Sep 25, 2026", "updated_ts": 1790357188, "version": "1.26.52.3", "content_rating": "Everyone 10+", "released": "Aug 15, 2011", "contains_ads": false, "in_app_purchases": "$0.99 - $49.99 per item", "url": "https://play.google.com/store/apps/details?id=com.mojang.minecraftpe&hl=en_US&gl=US"}
{"app_id": "org.videolan.vlc", "title": "VLC for Android", "developer": "Videolabs", "developer_id": "6364851808230428105", "rating": 4.042392, "ratings_count": 2009187, "installs": "500,000,000+", "min_installs": 500000000, "installs_exact": 515866848, "price": 0.0, "currency": "USD", "price_text": "Free", "category": "Video Players & Editors", "category_id": "VIDEO_PLAYERS", "updated": "Oct 14, 2026", "updated_ts": 1791980045, "version": "Varies with device", "content_rating": "Everyone", "released": "Feb 4, 2015", "contains_ads": false, "in_app_purchases": null, "url": "https://play.google.com/store/apps/details?id=org.videolan.vlc&hl=en_US&gl=US"}
com.example.does.not.exist: no record (HTTP 404, or no data for this id on the page)
detailed: 10 of 10 missing: []
com.whatsapp | WhatsApp | WhatsApp LLC | 4.624199 246257140 | 10,000,000,000+ | Free | Communication | Oct 19, 2026 | 2.26.41.77 | Everyone
com.instagram.android | Instagram | Instagram | 3.9892468 169555719 | 5,000,000,000+ | Free | Social | Oct 21, 2026 | Varies with device | Teen
com.google.android.youtube | YouTube | Google LLC | 3.8285916 172317597 | 10,000,000,000+ | Free | Video Players & Editors | Oct 20, 2026 | Varies with device | Teen
com.microsoft.teams | Microsoft Teams | Microsoft Corporation | 4.648416 8823533 | 500,000,000+ | Free | Business | Oct 22, 2026 | 1416/1.0.0.2026183002 | Everyone
com.rovio.baba | Angry Birds 2 | Rovio Entertainment Oy | 4.0748243 6320070 | 100,000,000+ | Free | Casual | Oct 20, 2026 | 26.7.1 | Everyone
```

### 2. Same core fields from the rendered page (cloud browser fallback)

Use this if plain HTTP starts returning something other than an app page. JSON-LD carries title, developer, rating, ratings count, price, currency, category id and content rating. Installs and last updated come from the visible page text. `open_play()` waits until the tab's URL has the requested path and `id` before reading anything, so it never parses the previous page. Harness timeouts (`TimeoutError` from the daemon, or the `Runtime.evaluate timed out` RuntimeError from `js()`) are retried. Nothing here brings the tab to the foreground.

```python
import json, time, urllib.parse

def _retry(fn, *args, tries=3):
    """Call a harness helper, retrying only its timeouts: TimeoutError from the daemon IPC,
    or the 'Runtime.evaluate timed out' RuntimeError that js() raises. Other errors propagate."""
    for i in range(tries):
        try:
            return fn(*args)
        except (TimeoutError, RuntimeError) as e:
            if i == tries - 1 or not (isinstance(e, TimeoutError) or "timed out" in str(e)):
                raise
            time.sleep(2)

def open_play(path, params, ready_expr, timeout=30):
    """Navigate, then wait until the loaded document is THIS url (same path, same id) and ready_expr is true."""
    url = "https://play.google.com" + path + "?" + urllib.parse.urlencode(params)
    _retry(goto_url, url)
    check = f"""(() => {{
      const u = new URL(location.href);
      if (u.pathname !== {json.dumps(path)} || u.searchParams.get('id') !== {json.dumps(params["id"])}) return false;
      return document.readyState === 'complete' && Boolean({ready_expr});
    }})()"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _retry(js, check):
            return url
        time.sleep(0.5)
    raise TimeoutError(f"{url} did not finish loading within {timeout}s")

def browser_app(app_id):
    """Same core fields from the rendered page: JSON-LD plus the labelled 'About this app' facts."""
    open_play("/store/apps/details", {"id": app_id, "hl": "en_US", "gl": "US"},
              "document.querySelector('script[type=\"application/ld+json\"]') || document.title.includes('Not Found')")
    return _retry(js, """(() => {
      const want = %s;
      let ld = {};
      for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
        try {
          const d = JSON.parse(s.textContent);
          for (const it of (Array.isArray(d) ? d : [d])) {
            const id = it && typeof it.url === 'string' && it.url && !it.url.startsWith('#') ? new URL(it.url, location.origin).searchParams.get('id') : null;
            if (it && it.applicationCategory && id === want) { ld = it; break; }
          }
        } catch (e) {}
      }
      const first = v => Array.isArray(v) ? v[0] : v;
      const n = v => (v === undefined || v === null || v === '' || isNaN(Number(v))) ? null : Number(v);
      const author = first(ld.author), offer = first(ld.offers) || {}, agg = ld.aggregateRating || {};
      const txt = document.body.innerText;
      const pick = re => { const m = txt.match(re); return m ? m[1].trim() : null; };
      return {
        app_id: new URL(location.href).searchParams.get('id'),
        title: ld.name || null,
        developer: typeof author === 'string' ? author : (author && author.name) || null,
        rating: n(agg.ratingValue),
        ratings_count: n(agg.ratingCount),
        price: n(offer.price),
        currency: offer.priceCurrency || null,
        category_id: ld.applicationCategory || null,
        content_rating: ld.contentRating || null,
        installs_badge: pick(/\\n([\\d.,]+[KMB]?\\+)\\n\\s*Downloads/),
        updated: pick(/Updated on\\n([^\\n]+)/),
        not_found: document.title.includes('Not Found') || !ld.name,
      };
    })()""" % json.dumps(app_id))

new_tab("about:blank")
for app_id in ["com.spotify.music", "com.mojang.minecraftpe", "com.example.does.not.exist"]:
    print(json.dumps(browser_app(app_id)))
    time.sleep(1)
```

Output (from the run on 2026-10-23):

```text
{"app_id": "com.spotify.music", "title": "Spotify: Music and Podcasts", "developer": "Spotify AB", "rating": 4.348993301391602, "ratings_count": 36528068, "price": 0, "currency": "USD", "category_id": "MUSIC_AND_AUDIO", "content_rating": "Teen", "installs_badge": "1B+", "updated": "Oct 23, 2026", "not_found": false}
{"app_id": "com.mojang.minecraftpe", "title": "Minecraft: Dream it, Build it!", "developer": "Mojang", "rating": 4.303256034851074, "ratings_count": 5866776, "price": 6.99, "currency": "USD", "category_id": "GAME_ARCADE", "content_rating": "Everyone 10+", "installs_badge": "50M+", "updated": "Sep 25, 2026", "not_found": false}
{"app_id": "com.example.does.not.exist", "title": null, "developer": null, "rating": null, "ratings_count": null, "price": null, "currency": null, "category_id": null, "content_rating": null, "installs_badge": null, "updated": null, "not_found": true}
```

`browser_app()` returns `app_id`, `title`, `developer`, `rating`, `ratings_count`, `price`, `currency`, `category_id`, `content_rating`, `installs_badge`, `updated`, `not_found`. JSON-LD is only used when its `url` carries the same `id`, so a miss gives `null`s and `not_found: true`, never another app's data.

### 3. A developer's app list (cloud browser, first load only)

Self-contained. `developer_name()` reads the developer name from the app page's JSON-LD exactly as Play spells it; `developer_apps()` opens `/store/apps/developer?id=<name>` and reads the app cards the page renders on load, re-reading until two reads 1 s apart agree. It returns `None` when Play shows its Not Found page (no such developer page), otherwise `(apps, maybe_more)`. The page renders at most 20 apps before scrolling, so `maybe_more` is `True` when it shows 20 and a warning is printed: the list is the first 20, not the catalog. It does not scroll, because scrolling makes the page fetch more apps from /_/PlayStoreUi/data/batchexecute, which robots.txt disallows. Feed the package names into `play_app()` (block 1) for full records.

```python
import json, time, urllib.parse

def _retry(fn, *args, tries=3):
    """Retry only harness timeouts (TimeoutError, or js()'s 'Runtime.evaluate timed out')."""
    for i in range(tries):
        try:
            return fn(*args)
        except (TimeoutError, RuntimeError) as e:
            if i == tries - 1 or not (isinstance(e, TimeoutError) or "timed out" in str(e)):
                raise
            time.sleep(2)

def open_play(path, params, ready_expr, timeout=30):
    """Navigate, then wait until the loaded document is THIS url (same path, same id) and ready_expr is true."""
    url = "https://play.google.com" + path + "?" + urllib.parse.urlencode(params)
    _retry(goto_url, url)
    check = f"""(() => {{
      const u = new URL(location.href);
      if (u.pathname !== {json.dumps(path)} || u.searchParams.get('id') !== {json.dumps(params["id"])}) return false;
      return document.readyState === 'complete' && Boolean({ready_expr});
    }})()"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _retry(js, check):
            return url
        time.sleep(0.5)
    raise TimeoutError(f"{url} did not finish loading within {timeout}s")

NOT_FOUND = "document.title.includes('Not Found')"
FIRST_LOAD = 20                      # apps the developer page renders before any scrolling

def developer_name(app_id):
    """Developer name exactly as Play spells it (JSON-LD author of this app's page), or None if the app is not found."""
    open_play("/store/apps/details", {"id": app_id, "hl": "en_US", "gl": "US"},
              "document.querySelector('script[type=\"application/ld+json\"]') || " + NOT_FOUND)
    return _retry(js, """(() => {
      for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
        try {
          const d = JSON.parse(s.textContent);
          for (const it of (Array.isArray(d) ? d : [d])) {
            const id = it && typeof it.url === 'string' && it.url && !it.url.startsWith('#') ? new URL(it.url, location.origin).searchParams.get('id') : null;
            if (it && it.applicationCategory && id === %s) {
              const a = Array.isArray(it.author) ? it.author[0] : it.author;
              return typeof a === 'string' ? a : (a && a.name) || null;
            }
          }
        } catch (e) {}
      }
      return null;
    })()""" % json.dumps(app_id))

# one row per package name, in page order; card text is "title\ndeveloper\nrating\nstar"
CARDS_JS = r"""(() => {
  const rows = new Map();
  for (const a of document.querySelectorAll('a[href*="/store/apps/details?id="]')) {
    const id = new URL(a.href).searchParams.get('id');
    if (!id || rows.has(id)) continue;
    const l = a.innerText.split('\n').map(s => s.trim()).filter(Boolean);
    rows.set(id, {app_id: id, title: l[0] || null, developer: l[1] || null,
                  rating: /^\d(\.\d)?$/.test(l[2] || '') ? Number(l[2]) : null});
  }
  return [...rows.values()];
})()"""

def developer_apps(name, reads=5):
    """None if Play shows Not Found (name does not match a developer page exactly), else (apps, maybe_more).
    Reads only what the page renders on load; never scrolls (more apps would come from robots-disallowed /_/)."""
    open_play("/store/apps/developer", {"id": name, "hl": "en_US", "gl": "US"},
              "document.querySelector('a[href*=\"/store/apps/details?id=\"]') || " + NOT_FOUND)
    if _retry(js, NOT_FOUND):
        return None
    apps, prev = None, None
    for _ in range(reads):
        apps = _retry(js, CARDS_JS)
        if apps == prev:
            break
        prev = apps
        time.sleep(1)
    else:
        raise RuntimeError(f"developer_apps({name!r}): card list still changing after {reads} reads")
    if not apps:
        raise RuntimeError(f"developer_apps({name!r}): page loaded but no app cards found; markup changed?")
    maybe_more = len(apps) >= FIRST_LOAD
    if maybe_more:
        print(f"developer_apps({name!r}): page shows the first {len(apps)} apps; the developer may have more (not loaded: needs /_/)")
    return apps, maybe_more

new_tab("about:blank")
last = None
for app_id in ["com.google.android.youtube", "com.microsoft.teams", "com.rovio.baba", "com.mojang.minecraftpe"]:
    name = developer_name(app_id)
    if name is None:
        print(app_id, "-> app page not found, no developer name")
        continue
    time.sleep(1)
    got = developer_apps(name)
    if got is None:
        print(app_id, "->", repr(name), "developer page not found")
        continue
    apps, maybe_more = got
    other = sum(a["developer"] != name for a in apps)
    print(app_id, "->", repr(name), len(apps), "maybe_more:", maybe_more, "other developer:", other, [a["app_id"] for a in apps[:4]])
    last = apps
    time.sleep(1)

print("first row:", json.dumps(last[0]) if last else None)
print("wrong name:", developer_apps("Rovio Entertainment Corporation"))
```

Output (from the run on 2026-10-23):

```text
developer_apps('Google LLC'): page shows the first 20 apps; the developer may have more (not loaded: needs /_/)
com.google.android.youtube -> 'Google LLC' 20 maybe_more: True other developer: 0 ['com.android.chrome', 'com.google.android.apps.messaging', 'com.google.android.googlequicksearchbox', 'com.google.android.gm']
developer_apps('Microsoft Corporation'): page shows the first 20 apps; the developer may have more (not loaded: needs /_/)
com.microsoft.teams -> 'Microsoft Corporation' 20 maybe_more: True other developer: 0 ['com.microsoft.office.outlook', 'com.microsoft.teams', 'com.microsoft.office.officehubrow', 'com.microsoft.skydrive']
com.rovio.baba -> 'Rovio Entertainment Oy' 16 maybe_more: False other developer: 0 ['com.rovio.baba', 'com.rovio.angrybirdsfriends', 'com.rovio.BadPiggies', 'com.rovio.dream']
com.mojang.minecraftpe -> 'Mojang' 3 maybe_more: False other developer: 0 ['com.mojang.minecraftpe', 'com.mojang.minecraftedu', 'com.mojang.minecraftedu_preview']
first row: {"app_id": "com.mojang.minecraftpe", "title": "Minecraft: Dream it, Build it!", "developer": "Mojang", "rating": 4.3}
wrong name: None
```

## Fields

Detail record from `play_app()`, exactly these keys. `a` is the app array `data[1][2]` of the callback whose `a[77][0]` equals the package name. "JSON-LD" means the page's `SoftwareApplication` block, used only when its `url` carries the same `id`.

| Field | Source | Example (observed) |
|---|---|---|
| `app_id` | the package name you asked for | `com.spotify.music` |
| `title` | `a[0][0]` (fallback JSON-LD `name`) | `Spotify: Music and Podcasts` |
| `developer` | `a[68][0]` (fallback JSON-LD `author.name`) | `Spotify AB` |
| `developer_id` | `a[68][2]` | `6523013212965523194` |
| `rating` | `a[51][0][1]` (fallback JSON-LD `aggregateRating.ratingValue`) | `4.3489933` |
| `ratings_count` | `a[51][2][1]` (fallback JSON-LD `aggregateRating.ratingCount`) | `36528080` |
| `installs` | `a[13][0]` | `1,000,000,000+` |
| `min_installs` / `installs_exact` | `a[13][1]` / `a[13][2]` | `1000000000` / `3171683950` |
| `price`, `currency`, `price_text` | `a[57][0][0][0][0][1][0]` = `[micros, currency, text]` (fallback JSON-LD `offers.price` / `offers.priceCurrency`); the text is empty for free apps, so `price_text` becomes `Free` when the price is 0 | `6.99`, `USD`, `$6.99` (Minecraft) |
| `category` / `category_id` | `a[79][0][0][0]` / `a[79][0][0][2]` (fallback JSON-LD `applicationCategory`) | `Arcade` / `GAME_ARCADE` |
| `updated` / `updated_ts` | `a[145][0][0]` / `a[145][0][1][0]` (unix s) | `Oct 23, 2026` / `1792759042` |
| `version` | `a[140][0][0][0]`, null means "Varies with device" | `1.26.52.3` |
| `content_rating` | `a[9][0]` (fallback JSON-LD `contentRating`) | `Everyone 10+` |
| `released` | `a[10][0]` | `May 27, 2014` |
| `contains_ads` | `a[48]` is `["Contains ads"]` for apps with ads (Spotify) and null for apps without (Minecraft, VLC); `null` if the app array is missing or `a[48]` has another shape | `true` |
| `in_app_purchases` | `a[19][0]` | `$4.99 - $203.88 per item` |
| `url` | the detail URL that was fetched | `https://play.google.com/store/apps/details?id=com.spotify.music&hl=en_US&gl=US` |

Developer list from `developer_apps()`: `app_id`, `title`, `developer`, `rating`, read from each rendered app card (link `id` plus the card text lines), plus the `maybe_more` flag. `developer_name()` returns JSON-LD `author.name` from the app page.

## Gotchas

- **Positional arrays, not named keys.** The `AF_initDataCallback` data is nested lists. Indexes above were correct on 2026-10-23; when Play ships a new frontend they can move. The code uses a safe getter `g()` plus type checks (`num()`, `text()`) so a moved field becomes `None` instead of a crash or a wrong type; check for a sudden column of `None`s. `play_app()` falls back to JSON-LD for title, developer, rating, ratings count, price, currency, category id and content rating; installs, updated, version and the rest have no fallback.
- **Callback keys are not stable labels.** The app data was in `ds:5` on the pages tested, but the code finds the callback by matching the package name at `a[77][0]` rather than trusting the key. JSON-LD is only used when its `url` carries the same `id`; a block with no `url`, or a `url` with no `id`, is ignored by all three readers (`ld_app`, `browser_app`, `developer_name`). On the pages tested the `SoftwareApplication` block always had a `url` like `.../details/Spotify_Music_and_Podcasts?id=com.spotify.music&hl=en_US`.
- **Developer pages render 20 apps, then load more on scroll from a disallowed path.** In the cloud browser, Google LLC showed 20 apps on load; one scroll to the bottom made the page call `/_/PlayStoreUi/data/batchexecute?rpcids=qnKhOb` and the list grew to 40. robots.txt disallows `/_`, so `developer_apps()` never scrolls and reports `maybe_more=True` for a full page of 20. Lists under 20 (Rovio Entertainment Oy 16, Mojang 3) are everything the page shows.
- **The page makes its own background requests.** A normal page load also requested `/_/PlayStoreUi/browserinfo` and `/play/log` by itself; the skill does not call these and does nothing to trigger more of them.
- **Developer page names must match exactly.** `Rovio Entertainment Corporation` gave a Not Found page; the name on the Angry Birds 2 page is `Rovio Entertainment Oy`. Take the name from the app page (`developer_name()`, or `developer` from `play_app()`), never from memory. `developer_apps()` returns `None` for Not Found, so "no such page" is distinct from an empty list (an empty list raises).
- **Two kinds of developer page.** App pages link either to `/store/apps/developer?id=<name>` (Spotify) or to `/store/apps/dev?id=<numeric id>` (Microsoft Teams, Angry Birds 2, YouTube). The numeric page is a showcase of 10-11 apps. The name page worked for those numeric developers too, so block 3 always uses the name page.
- **Country and language come from `gl` and `hl`.** With `GL = "DE"` Minecraft came back as `6.99 EUR`, `€6.99`. Set them explicitly; without them Play picks from the request.
- **Missing apps return HTTP 404** (`com.example.does.not.exist`). `fetch()` raises `urllib.error.HTTPError` at once for a 404 (only 429 and 5xx are retried); `play_app()` turns the 404 into `None`, and also returns `None` for any page with neither app data nor matching JSON-LD. Apps unavailable in the chosen country were not tested.
- **Plain urllib, not the harness `http_get`.** `http_get` routes through a proxy when `BROWSER_USE_API_KEY` is set, which can change status-code behaviour; block 1 calls urllib directly so 404, 429 and 5xx are seen as they are. No 429 or 5xx occurred today, so the retry path was not exercised against Play; it was checked against a local test server (429 with `Retry-After: 1` then 200, 503 with an HTTP-date `Retry-After` then 200, `Retry-After: 300` that raises without sleeping, a persistent 503 that raises after the last try without a final sleep, a 404 that raises at once).
- **Numbers are live.** Spotify's ratings count changed between fetches minutes apart. Store a fetch timestamp with every row.
- **Missing app in the browser:** the page title becomes `Not Found` and there is no JSON-LD block; block 2 reports that as `not_found: true` with `null` fields.
- **`version` is often null** for apps that ship per-device builds (Spotify, VLC). That is the page's "Varies with device", not a parse failure.
- **The harness prefixes the tab title with a horse marker** while attached, so `document.title` is not the app name; use JSON-LD `name`.
- **Pacing:** 1 request per 0.5-1 s over HTTP and about one browser page load per second were never throttled today. Keep at least that spacing. On a 429 the code backs off; if Play asks for more than 120 s it stops.

## What does not work

- **Search**: `/store/search` is disallowed by robots.txt for all user agents, so this skill does not use search pages, rendered or over HTTP. Start from package names you have, or from a developer page.
- **A developer's full catalog past the first 20 apps**: the developer page loads the rest only through `/_/PlayStoreUi/data/batchexecute`, which robots.txt disallows, so the skill stops at what the page renders on load and flags it with `maybe_more`.
- **Full catalogs from numeric `/store/apps/dev?id=` pages**: 10-11 apps for the three tested (Microsoft, Rovio, Google). Use the name page.
- **Guessed developer names**: Not Found unless the name matches Play's spelling exactly.
- **User reviews**: not covered; `/store/getreviews` is disallowed by robots.txt and no reviews path was tested.
- **Login-only data** (your library, purchases, personalised recommendations) was not attempted; this skill covers public logged-out pages only.
