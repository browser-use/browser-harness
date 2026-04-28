# News Aggregation — Multi-Source

Field-tested against TechCrunch, The Verge, Ars Technica, BBC, Guardian, Wired, NPR, HN, Reuters, CNN, NYT (2026-04-18).

## Lead with RSS — fastest and most reliable

For every site that has a feed, `http_get` + XML parsing is faster and more reliable than a browser. Use `ThreadPoolExecutor` for parallel fetches.

**Confirmed working RSS feeds (tested):**

| Source | Feed URL | Format | Items | Fetch time |
|--------|----------|--------|-------|------------|
| TechCrunch | `https://techcrunch.com/feed/` | RSS 2.0 | 20 | ~0.08s |
| Ars Technica | `https://feeds.arstechnica.com/arstechnica/index` | RSS 2.0 | 20 | ~0.10s |
| BBC News | `http://feeds.bbci.co.uk/news/rss.xml` | RSS 2.0 | 37 | ~0.23s |
| The Guardian (World) | `https://www.theguardian.com/world/rss` | RSS 2.0 | 45 | ~0.11s |
| The Guardian (Tech) | `https://www.theguardian.com/technology/rss` | RSS 2.0 | 32 | ~0.25s |
| Wired | `https://www.wired.com/feed/rss` | RSS 2.0 | 50 | ~0.10s |
| NPR Top Stories | `https://feeds.npr.org/1001/rss.xml` | RSS 2.0 | 10 | ~0.14s |
| Hacker News | `https://news.ycombinator.com/rss` | RSS 2.0 | 30 | ~0.16s |
| CNN Top Stories | `http://rss.cnn.com/rss/cnn_topstories.rss` | RSS 2.0 | 69 | ~0.25s |
| NYT Homepage | `https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml` | RSS 2.0 | 23 | ~0.12s |
| The Verge | `https://www.theverge.com/rss/index.xml` | **Atom** | 10 | ~0.15s |

## Parallel fetch pattern (4.3x speedup measured)

Sequential fetch of 7 feeds: **0.70s**. Parallel fetch of same 7 feeds: **0.16s** (4.3x speedup).

```python
from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET

RSS_FEEDS = [
    ("TechCrunch",     "https://techcrunch.com/feed/"),
    ("Ars Technica",   "https://feeds.arstechnica.com/arstechnica/index"),
    ("BBC News",       "http://feeds.bbci.co.uk/news/rss.xml"),
    ("Guardian World", "https://www.theguardian.com/world/rss"),
    ("Wired",          "https://www.wired.com/feed/rss"),
    ("NPR",            "https://feeds.npr.org/1001/rss.xml"),
    ("Wired",          "https://www.wired.com/feed/rss"),
]

def fetch_rss(name_url):
    name, url = name_url
    xml_data = http_get(url)
    root = ET.fromstring(xml_data)
    items = root.findall('.//item')
    return name, items

with ThreadPoolExecutor(max_workers=len(RSS_FEEDS)) as ex:
    results = list(ex.map(fetch_rss, RSS_FEEDS))

for name, items in results:
    for item in items[:5]:
        title = item.find('title').text
        link  = item.find('link').text
        print(f"[{name}] {title}")
```

## The Verge requires Atom namespace parsing

The Verge's feed is Atom format, not RSS 2.0. The naive `.//item` selector returns 0 items. The `title` element uses `type="html"` attribute but its `.text` still contains the plain string.

```python
import xml.etree.ElementTree as ET

NS = {'atom': 'http://www.w3.org/2005/Atom'}

xml_data = http_get("https://www.theverge.com/rss/index.xml")
root = ET.fromstring(xml_data)
entries = root.findall('.//atom:entry', NS)   # 10 entries

for e in entries:
    title = e.find('atom:title', NS).text
    link  = e.find('atom:link', NS).get('href')
    print(title, link)
```

Do NOT use `root.findall('.//{http://www.w3.org/2005/Atom}entry')` with a bare namespace — the explicit `NS` dict approach above is cleaner. Do NOT call `.text` on a `find()` result without checking for `None` first (the naive RSS path hit this on The Verge).

## Sites that block http_get entirely

**Reuters** returns HTTP 403/Forbidden for all `http_get` calls, even with a real browser `User-Agent` header. Use browser fallback (see below).

```
Reuters: ERROR HTTP Error 401: HTTP Forbidden   # with AND without User-Agent
```

Reuters's old RSS feeds (`feeds.reuters.com/reuters/topNews`) resolve to DNS NXDOMAIN — they have been shut down.

## Sites that work fine with http_get + User-Agent

NYT, Guardian, HN, CNN all return full HTML via `http_get` without issues. The User-Agent header (`Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36`) is not required for these but doesn't hurt.

```python
headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
html = http_get("https://www.nytimes.com", headers=headers)  # 1.1MB, works
html = http_get("https://news.ycombinator.com")               # 34KB, works without UA
```

**HN parsing via regex (no HTML parser needed):**
```python
import re
html = http_get("https://news.ycombinator.com")
stories = re.findall(r'class="titleline"><a href="([^"]+)"[^>]*>([^<]+)<', html)
# Returns list of (url, title) tuples — 30 stories on the front page
```

## Browser extraction — use when RSS is unavailable

### BBC (`bbc.com/news`)

No consent banner in headless browser (US region served; GDPR banner only appears for EU IP). Articles use `article h2` selectors.

```python
goto_url("https://www.bbc.com/news")
wait_for_load()
wait(2)

headlines = js("""
  Array.from(document.querySelectorAll('article h2'))
    .map(h => ({
      title: h.innerText.trim(),
      url: h.closest('a')?.href || h.closest('[href]')?.href || 
           h.parentElement.querySelector('a')?.href
    }))
    .filter(h => h.title.length > 10)
""")
# Returns 50+ articles. First one is typically LIVE/breaking.
```

If running from a EU IP and a consent banner appears:
```python
accept = js("""
  var btns = Array.from(document.querySelectorAll('button'));
  var btn = btns.find(b => /accept all|agree|continue/i.test(b.innerText));
  if (btn) { btn.click(); return 'clicked: ' + btn.innerText; }
  return 'no banner';
""")
```

Confirmed: `h3` elements on BBC are site-chrome labels ("The BBC is in multiple languages"), NOT article headlines. Use `article h2` only.

### TechCrunch (`techcrunch.com`)

`article` and `.post-block` selectors return 0 results — TechCrunch changed their layout. Articles are in `h3` elements.

```python
goto_url("https://techcrunch.com")
wait_for_load()
wait(2)

articles = js("""
  Array.from(document.querySelectorAll('h3'))
    .map(h => ({
      title: h.innerText?.trim(),
      url: h.closest('a')?.href || h.querySelector('a')?.href || 
           h.parentElement?.querySelector('a')?.href
    }))
    .filter(a => a.title && a.title.length > 20)
""")
# Returns ~10 articles. RSS is preferred (20 items, no JS required).
```

RSS is almost always faster for TechCrunch: **0.08s vs 3-5s browser** load. Only fall back to browser if you need paywall/subscriber content.

### Reuters (`reuters.com`)

`http_get` returns 403. Browser loads but the homepage is heavily JS-rendered with delayed hydration. `h3` selectors only return nav elements after standard `wait_for_load()`. Use `wait(3)` plus scroll:

```python
goto_url("https://www.reuters.com")
wait_for_load()
wait(3)
js("window.scrollTo(0, 500)")
wait(1)
# Category links work for topic nav:
links = js("""
  Array.from(document.querySelectorAll('a[href*="/world/"], a[href*="/technology/"]'))
    .filter(a => a.innerText.trim().length > 20)
    .map(a => ({text: a.innerText.trim(), href: a.href}))
""")
```

Reuters headlines are best obtained from the Guardian or AP — Reuters no longer has a public RSS and their JS hydration is slow.

## Decision tree: which approach to use

```
Does the site have an RSS/Atom feed?
  YES → http_get + XML parse (fastest, ~0.1s per feed)
         - RSS 2.0: root.findall('.//item')
         - Atom:    root.findall('.//atom:entry', {'atom': 'http://www.w3.org/2005/Atom'})
  NO  → Does http_get return valid HTML (not 403/401/JS shell)?
          YES → http_get + regex/BeautifulSoup (fast, ~0.2-0.3s)
          NO  → goto + wait_for_load + wait(2) + js() extraction (slow, 3-8s)
```

## What to skip

- **Reuters RSS** — DNS dead (`feeds.reuters.com` is NXDOMAIN)
- **Reuters http_get** — returns 403 regardless of User-Agent
- **TechCrunch `article`/`.post-block` selectors** — layout changed, use `h3` instead
- **BBC `h3` for headlines** — those are site-chrome labels; use `article h2`
- **The Verge `.//item` selector** — feed is Atom, not RSS; use Atom namespace
