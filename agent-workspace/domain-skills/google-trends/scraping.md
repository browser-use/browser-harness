# Google Trends - "Trending now" searches by country (RSS feed and /trending)

Field-tested against trends.google.com on 2026-11-01 using a Browser Use cloud browser, logged out (plus plain HTTP for robots.txt, the RSS feed and the /trending HTML). No consent wall, CAPTCHA or "unusual traffic" page seen across about 40 browser page loads and more than 50 plain HTTP requests.

robots.txt (fetched 2026-11-01) has one `User-agent: *` group with only `Disallow: /explore?` and `Disallow: /trends/explore?`, so `/trending` and `/trending/rss` are allowed; Explore (interest over time, related queries for a term) is blocked and not used here.

## Quick summary

- **RSS, no browser:** `https://trends.google.com/trending/rss?geo=<CC>` returns exactly 10 items: the 10 most recently started trends for that country or region (`US`, `GB`, `JP`, `US-CA`...), each with approximate traffic (`2000+`), start time and up to 3 news articles (title, URL, source). It ignores `hours`, `category` and `hl`. Unknown geo = HTTP 400.
- **/trending page, everything:** `https://trends.google.com/trending?geo=<CC>&hl=en-US&hours=<4|24|48|168>` ships every trend for that window in one inline script, `AF_initDataCallback({key: 'ds:0', ...})` (658 trends for US / 24 h on 2026-11-01). The table shows 25 rows at a time, but no paging or clicking is needed: read the script. Row count matched the page's own pager ("1-25 of 658") on all 10 loads.
- Per trend: title, search volume floor (200000 = "200K+"), increase % (capped at 1000), start and end time (no end = active), category ids, and the "Trend breakdown" related queries. News for a trend loads only on click; use the RSS feed for news.
- **Category and "active only" are client-side filters.** `category=17` in the URL filters the visible table, not the data the page ships; filter the rows yourself. Category ids are in block 2 (`CATEGORIES`), confirmed against the page's Category menu.
- The same `ds:0` script is in the plain-HTTP HTML (about 1.7 MB for US), so block 3 works without a browser.

## What works

### 1. RSS feed: 10 newest trends with news, per country (plain HTTP)

Self-contained; runs in plain `python3` or in `browser-harness` (no browser used). Default urllib user agent.

```python
import json, re, time, urllib.error, urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

BASE = "https://trends.google.com"
HT = "{https://trends.google.com/trending/rss}"   # namespace of the ht:* tags

# robots.txt, group "User-agent: *", wildcard rules matched Google-style:
# longest matching pattern wins, Allow wins a tie.
def _robots_rules():
    txt = urllib.request.urlopen(BASE + "/robots.txt", timeout=20).read().decode()
    rules, in_star, prev_ua = [], False, False
    for line in txt.splitlines():
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        k, v = (x.strip() for x in line.split(":", 1))
        k = k.lower()
        if k == "user-agent":
            in_star = (in_star and prev_ua) or v == "*"
            prev_ua = True
            continue
        prev_ua = False
        if in_star and k in ("allow", "disallow") and v:
            rules.append((k == "allow", v))
    return rules

RULES = _robots_rules()

def robots_allowed(path):
    best_len, ok = -1, True
    for allow, pat in RULES:
        rx = re.escape(pat.rstrip("$")).replace(r"\*", ".*") + ("$" if pat.endswith("$") else "")
        if re.match(rx, path) and (len(pat) > best_len or (len(pat) == best_len and allow)):
            best_len, ok = len(pat), allow
    return ok

def trends_rss(geo):
    """The 10 newest 'Trending now' searches for a country (US, GB, DE...) or region (US-CA)."""
    path = f"/trending/rss?geo={geo}"
    if not robots_allowed(path):
        raise PermissionError(f"robots.txt disallows {path}")
    try:
        body = urllib.request.urlopen(BASE + path, timeout=20).read()
    except urllib.error.HTTPError as e:
        if e.code == 400:
            raise ValueError(f"Google Trends does not know geo {geo!r} (HTTP 400)") from None
        raise   # 429 or 5xx: stop and back off, do not retry around it
    items = []
    for it in ET.fromstring(body).iter("item"):
        items.append({
            "title": it.findtext("title"),
            "approx_traffic": it.findtext(HT + "approx_traffic"),   # "2000+", "50K+"... a floor, not a count
            "started": parsedate_to_datetime(it.findtext("pubDate")).isoformat(),
            "picture": it.findtext(HT + "picture"),
            "picture_source": it.findtext(HT + "picture_source"),
            "news": [{"title": n.findtext(HT + "news_item_title"),
                      "url": n.findtext(HT + "news_item_url"),
                      "source": n.findtext(HT + "news_item_source")}
                     for n in it.findall(HT + "news_item")],
        })
    return items

print("explore allowed?", robots_allowed("/explore?q=python"), "| rss allowed?", robots_allowed("/trending/rss?geo=US"))
for geo in ["US", "GB", "DE", "IN", "BR", "JP", "US-CA"]:
    items = trends_rss(geo)
    print(f"{geo:6} {len(items)} items")
    for t in items[:3]:
        top = t["news"][0] if t["news"] else {}
        print(f"   {t['title']!r:34} {t['approx_traffic']:>6}  {t['started']}  news={len(t['news'])} first: {top.get('source')}")
    time.sleep(1)
try:
    trends_rss("XX")
except ValueError as e:
    print("XX:", e)
```

Output observed on 2026-11-01 (trimmed):

```text
explore allowed? False | rss allowed? True
US     10 items
   'jack endries'                      2000+  2026-11-01T11:30:00-08:00  news=3 first: The New York Times
   'celtics vs magic'                  1000+  2026-11-01T11:30:00-08:00  news=3 first: The Boston Globe
GB     10 items
   'athletic vs real sociedad'          200+  2026-11-01T11:20:00-08:00  news=3 first: Sky Sports
DE     10 items
   'oranienburg'                        500+  2026-11-01T11:30:00-08:00  news=3 first: BILD
JP     10 items
   'vivant 最終 回 予告'                    5000+  2026-11-01T11:20:00-08:00  news=3 first: Yahoo!ニュース
US-CA  10 items
   'zay flowers'                        200+  2026-11-01T11:30:00-08:00  news=3 first: Buffalo Bills
XX: Google Trends does not know geo 'XX' (HTTP 400)
```

### 2. Every trend on /trending, by country and time window (browser)

Self-contained. Opens one tab, reuses it for 10 page loads about 2 s apart (about 60 s in a cloud browser), closes it, saves JSON.

```python
import json, os, re, tempfile, time, urllib.request
from datetime import datetime, timezone

BASE = "https://trends.google.com"

# robots.txt, group "User-agent: *", wildcard rules matched Google-style:
# longest matching pattern wins, Allow wins a tie.
def _robots_rules():
    txt = urllib.request.urlopen(BASE + "/robots.txt", timeout=20).read().decode()
    rules, in_star, prev_ua = [], False, False
    for line in txt.splitlines():
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        k, v = (x.strip() for x in line.split(":", 1))
        k = k.lower()
        if k == "user-agent":
            in_star = (in_star and prev_ua) or v == "*"
            prev_ua = True
            continue
        prev_ua = False
        if in_star and k in ("allow", "disallow") and v:
            rules.append((k == "allow", v))
    return rules

RULES = _robots_rules()

def robots_allowed(path):
    best_len, ok = -1, True
    for allow, pat in RULES:
        rx = re.escape(pat.rstrip("$")).replace(r"\*", ".*") + ("$" if pat.endswith("$") else "")
        if re.match(rx, path) and (len(pat) > best_len or (len(pat) == best_len and allow)):
            best_len, ok = len(pat), allow
    return ok

# Category ids used in the data, with the names the page's Category menu shows.
CATEGORIES = {1: "Autos and Vehicles", 2: "Beauty and Fashion", 3: "Business and Finance", 4: "Entertainment",
              5: "Food and Drink", 6: "Games", 7: "Health", 8: "Hobbies and Leisure", 9: "Jobs and Education",
              10: "Law and Government", 11: "Other", 13: "Pets and Animals", 14: "Politics", 15: "Science",
              16: "Shopping", 17: "Sports", 18: "Technology", 19: "Travel and Transportation", 20: "Climate"}

# The page ships every trend for the chosen geo and window in an inline
# AF_initDataCallback({key: 'ds:0', ...}) script; the table only shows 25 at a time.
READ_STATE = r"""(() => {
  const s = [...document.scripts].find(s => s.textContent.includes("key: 'ds:0'"));
  const pager = document.querySelector('[aria-label^="Showing"]');
  return {ds0: s ? s.textContent : null, pager: pager ? pager.getAttribute('aria-label') : null};
})()"""

def _ts(v):
    return datetime.fromtimestamp(v[0], timezone.utc).isoformat() if v else None

def _volume_label(n):
    return f"{n // 1_000_000}M+" if n >= 1_000_000 else f"{n // 1000}K+" if n >= 1000 else f"{n}+"

_TAB = []

def trending_now(geo="US", hours=24, hl="en-US"):
    """Every 'Trending now' search on /trending for a country or region, in the page's relevance order.
    hours: 4, 24, 48 or 168 (the page's time menu). Returns (rows, total the page's pager shows)."""
    if hours not in (4, 24, 48, 168):
        raise ValueError("hours must be 4, 24, 48 or 168")
    path = f"/trending?geo={geo}&hl={hl}&hours={hours}"
    if not robots_allowed(path):
        raise PermissionError(f"robots.txt disallows {path}")
    if _TAB:
        goto_url(BASE + path)
    else:
        _TAB.append(new_tab(BASE + path))
    wait_for_load()
    st = {}
    for _ in range(30):
        st = js(READ_STATE)
        if st["ds0"] and st["pager"]:
            break
        time.sleep(0.5)
    info = page_info()
    if not st.get("ds0"):
        raise RuntimeError(f"no trends data on {info['url']} ({info['title']!r}); a consent or "
                           "'unusual traffic' page? Stop here, do not retry around it.")
    final = info["url"].removeprefix(BASE)
    if not robots_allowed(final):
        raise PermissionError(f"{path} redirected to disallowed {final}")
    m = re.search(r"data:(\[.*\]), sideChannel:", st["ds0"], re.S)
    if not m:   # unknown geo: the page ships "key: 'ds:0', data:[3], errorHasStatus: true"
        raise ValueError(f"Google Trends returned no trends for geo {geo!r}")
    data = json.loads(m.group(1))
    total = int(re.search(r"of (\d+)", st["pager"] or "of -1").group(1))
    rows = []
    for rank, t in enumerate(data[1] or [], 1):
        rows.append({
            "rank": rank,                                   # page order, "By relevance"
            "title": t[0],
            "volume": t[6],                                 # lower bound: 200000 shows as "200K+"
            "volume_label": _volume_label(t[6]),
            "increase_pct": t[8],                           # the arrow figure, capped at 1000
            "started": _ts(t[3]),
            "ended": _ts(t[4]),                             # None while the trend is active
            "active": not t[4],
            "categories": [CATEGORIES.get(c, str(c)) for c in t[10] or []],
            "breakdown": t[9] or [],                        # related queries ("+ 20 more" on the page)
            "news_ids": len(t[11] or []),                   # article refs; titles load only on click
        })
    return rows, total

# 1. Six countries, past 24 hours: totals, active count, top active trends by volume
results = {}
for geo in ["US", "GB", "DE", "IN", "BR", "JP"]:
    rows, total = trending_now(geo)
    results[geo] = rows
    active = [r for r in rows if r["active"]]
    print(f"{geo}: {len(rows)} trends (pager says {total}), {len(active)} active, "
          f"{sum('Sports' in r['categories'] for r in rows)} sports")
    for r in sorted(active, key=lambda r: -r["volume"])[:3]:
        print(f"   {r['title']!r:36} {r['volume_label']:>6} +{r['increase_pct']}%  since {r['started'][:16]}  "
              f"{','.join(r['categories'])}  e.g. {r['breakdown'][1:3]}")
    time.sleep(2)

# 2. Other windows and a region (state), same function
for geo, hours in [("US", 4), ("US", 168), ("US-CA", 24)]:
    rows, total = trending_now(geo, hours=hours)
    print(f"{geo} past {hours}h: {len(rows)} trends (pager says {total}); first: {rows[0]['title']!r} {rows[0]['volume_label']}")
    time.sleep(2)
try:
    trending_now("XX")
except ValueError as e:
    print("XX:", e)

# 3. Category filter is client-side: filter the rows yourself
us = results["US"]
tech = [r["title"] for r in us if "Technology" in r["categories"]]
print("US technology:", len(tech), tech[:5])

out = os.path.join(tempfile.gettempdir(), "google_trends_now.json")
json.dump(results, open(out, "w"), ensure_ascii=False, indent=1)
print("saved", out)
close_tab(_TAB.pop())
```

Output observed on 2026-11-01 (trimmed):

```text
US: 658 trends (pager says 658), 163 active, 385 sports
   'what time is it'                       1M+ +1000%  since 2026-11-01T04:00  Other  e.g. ['did the time change', 'did the time change last night']
   'mark bowman'                         500K+ +500%  since 2026-11-01T01:50  Sports  e.g. ['ohio state football', 'usc football']
   'cardinals vs cowboys'                200K+ +1000%  since 2026-11-01T13:50  Sports  e.g. ['cowboys game', 'cowboys vs cardinals']
GB: 355 trends (pager says 355), 88 active, 180 sports
   'liverpool f.c. vs arsenal f.c. standings'  200K+ +1000%  since 2026-11-01T16:40  Sports,Entertainment  e.g. ['arsenal vs liverpool', 'liverpool v arsenal']
DE: 395 trends (pager says 395), 120 active, 180 sports
   'eintracht frankfurt – hsv'           200K+ +1000%  since 2026-11-01T15:40  Sports  e.g. ['eintracht frankfurt', 'eintracht frankfurt heute']
IN: 373 trends (pager says 373), 63 active, 151 sports
   'bangladesh vs india'                   1M+ +1000%  since 2026-11-01T00:40  Sports  e.g. ['ban vs ind', 'bangladesh national cricket team vs india national cricket team match scorecard']
BR: 368 trends (pager says 368), 88 active, 201 sports
   'palmeiras x vasco da gama'           500K+ +1000%  since 2026-10-31T20:10  Sports  e.g. ['palmeiras vs vasco', 'palmeiras e vasco']
JP: 406 trends (pager says 406), 72 active, 161 sports
   '全日本 大学駅伝 結果'                         100K+ +1000%  since 2026-11-01T01:30  Sports  e.g. ['青山学院大学駅伝', '駅伝']
US past 4h: 170 trends (pager says 170); first: 'colts vs jaguars' 50K+
US past 168h: 3318 trends (pager says 3318); first: 'patrick stewart' 5M+
US-CA past 24h: 344 trends (pager says 344); first: 'raiders vs jets' 50K+
XX: Google Trends returned no trends for geo 'XX'
US technology: 9 ['youtube tv', 'black friday', 'ocarina of time remake', 'xbox cloud gaming', 'apple iphone duo']
saved <tempdir>/google_trends_now.json
```

### 3. Same data without a browser (plain HTTP)

The server-rendered HTML carries the same `ds:0` script. Self-contained; plain `python3` or `browser-harness`.

```python
import json, re, time, urllib.request
from datetime import datetime, timezone

BASE = "https://trends.google.com"

# robots.txt, group "User-agent: *", wildcard rules matched Google-style (same parser as blocks 1 and 2).
def _robots_rules():
    txt = urllib.request.urlopen(BASE + "/robots.txt", timeout=20).read().decode()
    rules, in_star, prev_ua = [], False, False
    for line in txt.splitlines():
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        k, v = (x.strip() for x in line.split(":", 1))
        k = k.lower()
        if k == "user-agent":
            in_star = (in_star and prev_ua) or v == "*"
            prev_ua = True
            continue
        prev_ua = False
        if in_star and k in ("allow", "disallow") and v:
            rules.append((k == "allow", v))
    return rules

RULES = _robots_rules()

def robots_allowed(path):
    best_len, ok = -1, True
    for allow, pat in RULES:
        rx = re.escape(pat.rstrip("$")).replace(r"\*", ".*") + ("$" if pat.endswith("$") else "")
        if re.match(rx, path) and (len(pat) > best_len or (len(pat) == best_len and allow)):
            best_len, ok = len(pat), allow
    return ok

def trending_now_http(geo="US", hours=24, hl="en-US"):
    """Same ds:0 data as the browser block, from the server-rendered HTML (about 1.7 MB for US/24h)."""
    if hours not in (4, 24, 48, 168):   # anything else silently falls back to 24
        raise ValueError("hours must be 4, 24, 48 or 168")
    path = f"/trending?geo={geo}&hl={hl}&hours={hours}"
    if not robots_allowed(path):
        raise PermissionError(f"robots.txt disallows {path}")
    html = urllib.request.urlopen(BASE + path, timeout=30).read().decode()
    m = re.search(r"AF_initDataCallback\(\{key: 'ds:0', hash: '\d+', data:(\[.*?\]), sideChannel: \{\}\}\);", html, re.S)
    if not m:
        if re.search(r"key: 'ds:0',\s*data:\[\d+\],\s*errorHasStatus", html):   # unknown geo
            raise ValueError(f"Google Trends returned no trends for geo {geo!r}")
        raise RuntimeError(f"no ds:0 block in {path}; a consent or 'unusual traffic' page? Stop, do not retry around it.")
    return [{"title": t[0], "volume": t[6], "increase_pct": t[8], "active": not t[4],
             "started": datetime.fromtimestamp(t[3][0], timezone.utc).isoformat(), "category_ids": t[10] or [],
             "breakdown": t[9] or []} for t in json.loads(m.group(1))[1] or []]

print("disallowed:", [p for allow, p in RULES if not allow])
for geo in ["US", "FR", "AU"]:
    rows = trending_now_http(geo)
    act = [r for r in rows if r["active"]]
    print(geo, len(rows), "trends,", len(act), "active; top active:",
          [(r["title"], r["volume"]) for r in sorted(act, key=lambda r: -r["volume"])[:3]])
    time.sleep(2)
try:
    trending_now_http("XX")
except ValueError as e:
    print("XX:", e)
```

Output observed on 2026-11-01:

```text
disallowed: ['/explore?', '/trends/explore?']
US 658 trends, 167 active; top active: [('what time is it', 1000000), ('mark bowman', 500000), ('angel reese atlanta dream wnba finals', 500000)]
FR 367 trends, 105 active; top active: [('ol – angers', 100000), ('marseille – toulouse', 50000), ('paris fc – monaco', 50000)]
AU 191 trends, 50 active; top active: [('tonga vs samoa 2026', 50000), ('liverpool vs arsenal', 20000), ('the block', 20000)]
XX: Google Trends returned no trends for geo 'XX'
```

## Fields

`ds:0` is `[null, [trend, ...]]`; each trend is a 13-item array (all 658 US trends had 13 items).

| Index | Field | Notes |
|---|---|---|
| 0 | title | Same text as the table row |
| 2 | geo | `"US"`, `"US-CA"`... |
| 3 | `[start_unix]` | UTC seconds; shown as "5 hours ago" |
| 4 | `[end_unix]` or null | null = active ("trending_up Active" on the page); 495 of 658 US trends had ended |
| 6 | volume | Lower bound as an int: 100, 200, 500, 1000 ... 1000000, 5000000; the page shows "1M+", "200K+" |
| 8 | increase % | 50 to 1000; the page shows "1,000%" for 1000 |
| 9 | breakdown | Related queries, first is usually the title itself |
| 10 | category ids | 1 to 3 ids, see `CATEGORIES` (the Category menu has no id 12) |
| 11 | news refs | `[[id, lang, geo], ...]`; the article titles are not in the page HTML |
| 12 | normalized title | Equal to index 0 for 642 of 658 |
| 1, 5, 7 | always null | |

RSS item: `title`, `ht:approx_traffic` ("2000+"), `pubDate` (start time, US Pacific offset), `ht:picture`, `ht:picture_source`, up to 3 `ht:news_item` (`ht:news_item_title`, `ht:news_item_url`, `ht:news_item_source`, `ht:news_item_picture`, `ht:news_item_snippet` usually empty). `<link>` and `<description>` carry nothing useful.

## Gotchas

- The RSS feed is not the top of the page. It is the 10 most recently started trends (checked: all 10 US RSS items were the 10 newest by start time in `ds:0`, ties broken by volume), so it can miss a 1M+ trend that started hours ago. For the biggest trends, use blocks 2 or 3 and sort by `volume`.
- `hours` other than 4, 24, 48, 168 silently falls back to 24 (`hours=12` sent `24` in the page's own request). The helper rejects other values.
- Category, status and sort never reach the data: the page's own `ds:0` request is `[null,null,"<geo>",null,"<hl>",<hours>]`. Loaded directly, `&category=17` filtered the table (385 of 658) but `&status=active` and `&sort=search-volume` did not (still 658, relevance order); clicking the "Show active trends only" switch did (163, the same count as rows with no end time). Filter `categories` and `active` in Python.
- `ds:0` comes in the page's default "By relevance" order (the first 25 matched the table's first page), which is what `rank` keeps.
- `window.AF_initDataChunkQueue` is empty after the page boots; read the inline script text instead, as the blocks do.
- Unknown geo: RSS answers HTTP 400; `/trending` answers 200 with `ds:0` set to `data:[3], errorHasStatus: true`.
- Titles are in the searchers' language whatever `hl` is (DE titles were German, JP Japanese, with `hl=en-US`).
- Counts move by a few rows between loads minutes apart (IN 374 then 373, JP 410 then 406) as trends age out of the window.

## What does not work

- Explore (`/explore?...`, `/trends/explore?...`, interest over time and related topics for a term): robots-disallowed. Not used.
- News headlines for a trend from `/trending`: only ids are in the page; the titles load from a batchexecute call when a row is clicked. Use the RSS feed's `ht:news_item` instead.
- Export > Download CSV: not tested; blocks 2 and 3 already get every row.
