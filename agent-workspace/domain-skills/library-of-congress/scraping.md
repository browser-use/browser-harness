# Library of Congress (loc.gov) - Find Digitized Photos or Maps for a Topic and Get Item Titles, Dates, Image URLs and Rights Notes (JSON API, no key)

Field-tested against www.loc.gov on 2026-11-19 (US Pacific afternoon; 2026-11-19 23:57 to 2026-11-20 00:23 UTC) using a fresh Browser Use cloud browser (logged out; one session, 00:03-00:21 UTC) plus Python `urllib` and `curl` from a Linux machine. 4 browser page loads (the "Working Within Limits" page, robots.txt, the legal page and the limits page again) and 32 in-page `fetch()` calls (block 1 ran 3 times; 1 probe of an HTML page), 22 curl calls and 30 urllib calls (4 of them robots.txt) to www.loc.gov, plus 1 curl call for https://tile.loc.gov/robots.txt (HTTP 404, no rules), all serial and at least 6.5 s apart. Every call was HTTP 200 except the deliberate HTTP 404 (unknown item) and HTTP 403 (HTML page without `fo=json`) probes below and five transient failures, all on the first request for a URL: two HTTP/2 stream cuts (curl error 92 `INTERNAL_ERROR` after 47.1 s on a collection search and after 64.1 s on map item 73690241), an HTTP 503 JSON `{"exception": "service unavailable"}` on the retry of that map item 7 s later, an HTTP 525 from Cloudflare on the first call of block 4's first run, and a urllib `IncompleteRead` in block 3's first run. The collection search answered in 0.15 s when repeated 7 s later (`X-Nearside-Cache: HIT`). Most answers took 0.1-4.3 s; the first request for a URL took up to 27.9 s (block 1's first run) or 16.5 s (a map search probe). No 429, no CAPTCHA on a JSON URL, no key, no login. The blocks retry once after 30 s on these failures; block 4's output below is its second run.

robots.txt (checked 2026-11-19/20, curl, the cloud browser and `urllib.robotparser`): https://www.loc.gov/robots.txt names only `008` and `Baiduspider` / `Baiduspider-image` (each `Disallow: /`). The `User-agent: *` group disallows `/cgi-bin/`, `/web_arch/`, `/rr/mopic/staff`, `/loc/volunteers`, `/ficmanagers`, `/preserv/extranet/`, `/myloc`, `/nationalfilmregistry`, `/fedsearch`, `/search`, `/pictures/search` and `/pictures/related`, and sets `Crawl-Delay: 5`. There are no named AI-agent groups, so GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider fall under `*`: `/photos/`, `/maps/`, `/item/` and `/collections/` are allowed for all 11 agents, and `/search/` for none (block 3). **So this skill never calls `/search/?fo=json`**, the general search the API docs also describe; it uses the format endpoints (`/photos/`, `/maps/`, `/books/`) and `/collections/<slug>/`. Terms: the legal page https://www.loc.gov/legal/ says "We reserve the right to block IP addresses that fail to honor our websites’ robot.txt files, or submit requests at a rate that negatively impacts service delivery to patrons. Current guidelines recommend that software programs submit a total of no more than 10 requests per minute to our applications, regardless of the number of machines used to submit requests. We also reserve the right to terminate programs that require more than 24 hours to complete." The "Working Within Limits" page https://www.loc.gov/apis/json-and-yaml/working-within-limits/ says "The API is accessible to the public with no API key or authentication required. Rate limiting is strongly encouraged.", lists the JSON/YAML API at 20 requests per minute with 1 hour blocked if the rate is exceeded (image services and `/storage-services/` media 150 per minute each), and warns "users may encounter 429 status codes or HTML pages with CAPTCHAs even when operating below the rates listed below." No AI/ML, scraping, crawling or non-commercial wording on either page (block 2 checks the quotes). Naming: this skill writes "Library of Congress" in plain text and shows no logo or seal; the legal page says its links "are not endorsements", and this skill is not affiliated with or endorsed by the Library.

**The Library usually does not own the rights.** The legal page: "As a publicly supported institution, we generally do not own the rights to materials in our collections. You should determine for yourself whether or not an item is protected by copyright or in the public domain". Every item record carries its own statement: `rights_advisory` (short, e.g. "No known restrictions on publication.") and `rights` (the collection's statement as HTML). Report both with the item URL, and treat a missing statement as "unknown", never as "free to use".

## Quick summary

- **No scraping.** `GET https://www.loc.gov/photos/?q=wright%20brothers&fo=json&c=5&fa=online-format:image|access-restricted:false&at=results,pagination` -> `{"pagination": {"of": 414, "next": "...&sp=2", ...}, "results": [{"url": "https://www.loc.gov/item/2001696291/", "title": "[Group including the Wright brothers]", "date": "1900-01-01", "image_url": ["...00495v.jpg#h=828&w=1024", ...], "item": {"rights_advisory": "No known restrictions.", ...}}, ...]}`. `/maps/`, `/books/` and `/collections/<slug>/` take the same `q`, `fo=json`, `c` (per page), `sp` (page), `fa` (facet filter) and `at` (which top-level parts to return). Then `GET /item/<id>/?fo=json&at=item` for the item's rights and image list. JSON, `Access-Control-Allow-Origin: *`, no key.
- **Answers (block 1, 2026-11-20 00:20 UTC):** photos "wright brothers": **414 online images**; the first is **"[Group including the Wright brothers]", [1900 Dec. 27]**, 1024 px JPEG https://tile.loc.gov/storage-services/service/pnp/ppprs/00400/00495v.jpg, rights "No known restrictions.". Maps "yellowstone national park": **30 online images**; the first is **"Yellowstone National Park", 190?**, rights "The content of the Library of Congress Geography and Map Division digitized collections is free to use and reuse unless a Rights Advisory statement is present that indicates otherwise."
- **Keep `/item/` results only.** Without a filter the first photo result for "wright brothers" is the collection "Wright Brothers Negatives" (`url` .../collections/wright-brothers-negatives/about-this-collection/). `fa=online-format:image|access-restricted:false` keeps images that can be viewed off-site (469 -> 414 results); the blocks also drop any result whose `url` has no `/item/`.
- **Rights live in the item record.** Photo search results carry `item.rights_advisory`; map search results carry no rights field at all. One `/item/<id>/?fo=json&at=item` call per item gives `rights_advisory` (photos) and `rights` (both). All 18 image item records read here had a `rights` statement, but the book record `/item/0000000000/` had `rights: []` and no `rights_advisory`; the blocks print "none in the record" in that case.
- **Rate limit: 10 requests per minute in total** (legal page, "regardless of the number of machines"); the JSON API blocks for 1 hour above 20 per minute; robots.txt `Crawl-Delay: 5`. All blocks wait 6.5 s after every request, serial. One search plus N items costs N + 1 requests, so 3 items for 2 topics took about a minute. A 429 or a non-JSON answer (CAPTCHA, Cloudflare "Just a moment...") stops the run; a 5xx or a cut connection waits 30 s and retries once.
- **First answers can be slow or cut.** An uncached query took up to 64.1 s and two were cut mid-stream; the repeat came from cache in 0.15 s. Give each request a 120 s timeout and one retry.

## What works

### 1. Topic -> photos and maps with title, date, image URL and rights note (browser)

`on_loc_tab()` opens the logged-out "Working Within Limits" page (robots.txt allows `/apis/`), so `fetch()` is same-origin (the API also sends `Access-Control-Allow-Origin: *`). `get()` returns parsed JSON on HTTP 200, `None` on 404 (a JSON body), retries once after 30 s on a network error or 502/503/504, and stops on a 429 or any non-JSON answer. One search per topic, then one item record per hit: 8 `fetch()` calls for 2 topics x 3 items.

```python
import html, json, re, time
from datetime import datetime, timezone

ASK = [("photos", "wright brothers"), ("maps", "yellowstone national park")]  # (format endpoint, topic)
N = 3  # items per topic; each item costs one more request

SITE = "https://www.loc.gov"
PAUSE = 6.5  # loc.gov/legal: "no more than 10 requests per minute"; robots.txt Crawl-Delay: 5
ONLINE = "online-format:image|access-restricted:false"  # digitized images viewable off-site

def on_loc_tab():
    """fetch() from a logged-out www.loc.gov page that robots.txt allows (the API's own limits page)."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(SITE + "/apis/json-and-yaml/working-within-limits/")
    wait_for_load()
    txt = js("document.body ? document.body.innerText : ''") or ""
    if js("location.origin") != SITE or "Requests per minute" not in txt:
        raise RuntimeError(f"www.loc.gov did not serve the limits page (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__u[id] = {status: r.status, type: r.headers.get('content-type') || '',
      retry: r.headers.get('retry-after'), text: await r.text()}; })
    .catch(e => { window.__u[id] = {status: 0, type: '', retry: null, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""
calls = []

def fetch(url):
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 120:  # an uncached query took 16-64 s
            raise RuntimeError(f"{url}: no answer after 120 s")
        time.sleep(0.5)
    calls.append((r["status"], round(time.time() - t0, 1)))
    time.sleep(PAUSE)
    return r

def get(path):
    """-> parsed JSON, or None on 404 (a JSON body). A network error or 502/503/504 is retried once after 30 s (a slow
    first answer is usually cached by then). A 429 or any non-JSON answer (a CAPTCHA or Cloudflare "Just a moment..."
    page) means stop: the limits page blocks for 1 hour when the rate is exceeded."""
    for attempt in range(2):
        r = fetch(SITE + path)
        if r["status"] in (0, 502, 503, 504) and attempt == 0:
            time.sleep(30)
            continue
        break
    if r["status"] == 429 or (r["status"] != 0 and "json" not in r["type"]):
        raise RuntimeError(f"{path}: HTTP {r['status']} {r['type'] or '-'} (rate limit, CAPTCHA or challenge page): "
                           "stop all loc.gov requests for 1 hour")
    if r["status"] == 404:
        return None
    if r["status"] != 200:
        raise RuntimeError(f"{path}: HTTP {r['status']} {' '.join(r['text'].split())[:150]!r}; stopping")
    return json.loads(r["text"])

def q(s):
    return re.sub(r"[^A-Za-z0-9._~-]", lambda m: "%%%02X" % ord(m[0]), s)

def biggest_jpeg(urls):
    """image_url entries carry '#h=..&w=..'; keep the widest .jpg (no fragment)."""
    best = (0, None)
    for u in urls or []:
        w = re.search(r"[#&]w=(\d+)", u)
        if ".jpg" in u.split("#")[0] and (int(w[1]) if w else 0) >= best[0]:
            best = (int(w[1]) if w else 0, u.split("#")[0])
    return best[1]

def rights_note(it):
    """Short rights note: rights_advisory, else the rights text without HTML; None when the record has neither."""
    if it.get("rights_advisory"):
        return it["rights_advisory"].strip()
    txt = " ".join(re.sub(r"<[^>]+>", " ", html.unescape(x)) for x in (it.get("rights") or []) if x)
    out = ""
    for sent in re.split(r"(?<=[.!?])\s+", " ".join(txt.split())):  # whole sentences, up to about 260 characters
        if out and len(out) + len(sent) > 260:
            return out + " ..."
        out = (out + " " + sent).strip()
    return out or None

on_loc_tab()
now = datetime.now(timezone.utc)
print(f"Library of Congress loc.gov JSON API, checked {now:%Y-%m-%d %H:%M} UTC")
for fmt, topic in ASK:
    d = get(f"/{fmt}/?q={q(topic)}&fo=json&c={N + 2}&fa={q(ONLINE)}&at=results,pagination")
    hits = [r for r in d["results"] if "/item/" in r.get("url", "")][:N]  # drop collection and web-page records
    print(f"\n{fmt} '{topic}': {d['pagination']['of']} online images; first {len(hits)} items")
    for r in hits:
        item_id = r["url"].rstrip("/").split("/item/")[1]
        rec = get(f"/item/{q(item_id)}/?fo=json&at=item")
        if rec is None:
            print(f"  {item_id}: HTTP 404 now, skipped")
            continue
        it = rec["item"]
        date = (it.get("created_published_date") or it.get("date") or "no date").rstrip(".")
        print(f"  {' '.join((it.get('title') or r['title']).split())[:90]}")
        print(f"    date {date} | {it.get('url') or r['url']}")
        print(f"    image {biggest_jpeg(it.get('image_url') or r.get('image_url')) or 'none listed'}")
        note = rights_note(it)
        print(f"    rights {note!r}" if note else "    rights: none in the record (rights and rights_advisory empty): check the collection page")

print(f"\n{len(calls)} requests, HTTP {sorted(set(s for s, _ in calls))}, {min(t for _, t in calls)}-{max(t for _, t in calls)} s each")
print(f"Source: Library of Congress, {SITE}, accessed {now:%d %B %Y} UTC. The Library generally does not own rights "
      "to its collection items: check each item's rights before reuse.")
```

Output (from the run on 2026-11-20, 00:20 UTC; the first run at 00:04 took 0.6-27.9 s per request, uncached, with the same items):

```text
Library of Congress loc.gov JSON API, checked 2026-11-20 00:20 UTC

photos 'wright brothers': 414 online images; first 3 items
  [Group including the Wright brothers]
    date [1900 Dec. 27] | https://www.loc.gov/item/2001696291/
    image https://tile.loc.gov/storage-services/service/pnp/ppprs/00400/00495v.jpg
    rights 'No known restrictions.'
  Wright brothers aeroplane - patented plans, 1908
    date 1908 | https://www.loc.gov/item/2001695572/
    image https://tile.loc.gov/storage-services/service/pnp/cph/3c20000/3c27000/3c27700/3c27779v.jpg
    rights 'No known restrictions on publication.'
  [Helen Wright, age 12, niece of the Wright brothers, and Leontine Wright]
    date [1901 Jan.] | https://www.loc.gov/item/00653508/
    image https://tile.loc.gov/storage-services/service/pnp/ppprs/00400/00460v.jpg
    rights 'No known restrictions.'

maps 'yellowstone national park': 30 online images; first 3 items
  Yellowstone National Park
    date 190? | https://www.loc.gov/item/97683604/
    image https://tile.loc.gov/image-services/iiif/service:gmd:gmd426:g4262:g4262y:ye000003/full/pct:25/0/default.jpg
    rights 'The content of the Library of Congress Geography and Map Division digitized collections is free to use and reuse unless a Rights Advisory statement is present that indicates otherwise. Credit Line: Library of Congress, Geography and Map Division. ...'
  [Yellowstone National Park boundaries]
    date 1895 | https://www.loc.gov/item/97683574/
    image https://tile.loc.gov/image-services/iiif/service:gmd:gmd426:g4262:g4262y:ye000018/full/pct:25/0/default.jpg
    rights 'The content of the Library of Congress Geography and Map Division digitized collections is free to use and reuse unless a Rights Advisory statement is present that indicates otherwise. Credit Line: Library of Congress, Geography and Map Division. ...'
  Yellowstone National Park
    date 1886 | https://www.loc.gov/item/97683575/
    image https://tile.loc.gov/image-services/iiif/service:gmd:gmd426:g4262:g4262y:ye000005/full/pct:25/0/default.jpg
    rights 'The content of the Library of Congress Geography and Map Division digitized collections is free to use and reuse unless a Rights Advisory statement is present that indicates otherwise. Credit Line: Library of Congress, Geography and Map Division. ...'

8 requests, HTTP [200], 0.1-0.2 s each
Source: Library of Congress, https://www.loc.gov, accessed 20 November 2026 UTC. The Library generally does not own rights to its collection items: check each item's rights before reuse.
```

### 2. robots.txt, the legal and limits quotes, and what the API does with mistakes (browser)

3 page loads and 7 in-page `fetch()` calls in the same tab, each followed by a 6.5 s wait. It does not request `/search/`.

```python
import json, time

SITE = "https://www.loc.gov"
LIMITS = SITE + "/apis/json-and-yaml/working-within-limits/"

START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__u[id] = {status: r.status, type: r.headers.get('content-type') || '', text: await r.text()}; })
    .catch(e => { window.__u[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

def raw(path):
    """One in-page GET, no retries (inspection only), then 6.5 s: loc.gov asks for at most 10 requests per minute."""
    rid = json.dumps(js(START_JS % json.dumps(SITE + path)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 120:
            raise RuntimeError(f"{path}: no answer after 120 s")
        time.sleep(0.5)
    r["secs"] = round(time.time() - t0, 1)
    time.sleep(6.5)
    return r

def page(url):
    goto_url(url)
    wait_for_load()
    time.sleep(6.5)
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    return st, " ".join((js("document.body ? document.body.innerText : (document.documentElement.textContent || '')") or "").split())

st, txt = page(SITE + "/robots.txt")
print(f"robots.txt HTTP {st}: " + " | ".join(
    x for x in ("User-agent: 008", "User-agent: Baiduspider", "Disallow: /search", "Disallow: /pictures/search",
                "Disallow: /pictures/related", "Crawl-Delay: 5") if x in txt) + f" | named AI agents: "
      + str([a for a in ("GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
                         "Google-Extended", "PerplexityBot", "CCBot", "Bytespider") if a.lower() in txt.lower()]))
st, txt = page(SITE + "/legal/")
for needle in ("We reserve the right to block IP addresses that fail to honor our websites’ robot.txt files",
               "submit a total of no more than 10 requests per minute to our applications, regardless of the number of machines",
               "we generally do not own the rights to materials in our collections",
               "The links are not endorsements"):
    print(f"legal HTTP {st}: {'found' if needle in txt else 'MISSING'}: {needle!r}")
st, txt = page(LIMITS)
for needle in ("The API is accessible to the public with no API key or authentication required.",
               "users may encounter 429 status codes or HTML pages with CAPTCHAs even when operating below the rates",
               "JSON/YAML API for loc.gov Requests per minute 20 Time blocked, if rate is exceeded 1 hour",
               "paging past the 100,000th item in a search result is not supported",
               "It is recommended that requests not exceed 1,000 items per page."):
    print(f"limits HTTP {st}: {'found' if needle in txt else 'MISSING'}: {needle!r}")
print()

for label, path in (
    ("photos, no filter, full page  ", "/photos/?q=wright%20brothers&fo=json&c=3"),
    ("photos, at=results,pagination ", "/photos/?q=wright%20brothers&fo=json&c=3&at=results,pagination"),
    ("collection search             ", "/collections/wright-brothers-negatives/?q=kitty%20hawk&fo=json&c=3&at=results,pagination"),
    ("books format                  ", "/books/?q=wright%20brothers&fo=json&c=3&at=results,pagination"),
    ("photos without fo=json        ", "/photos/?q=wright%20brothers&c=3"),
    ("unknown item                  ", "/item/not-a-real-item-zz9/?fo=json&at=item"),
):
    r = raw(path)
    out = f"{label} HTTP {r['status']} {r['type'].split(';')[0] or '-'} {len(r['text']):,} chars {r['secs']} s"
    if "json" in r["type"]:
        d = json.loads(r["text"])
        if "results" in d:
            out += f" | of {d['pagination']['of']} | " + "; ".join(
                f"{x.get('original_format')} {x['title'][:40]!r}" for x in d["results"][:3])
        else:
            out += f" | exception {d.get('exception')!r}, top-level keys {sorted(d)[:6]}"
    print(out)

r = raw("/item/2001696291/?fo=json&at=item,resources")
files = json.loads(r["text"])["resources"][0]["files"][0]
print(f"\nitem 2001696291 resources: HTTP {r['status']}, {len(files)} files")
for f in files:
    print(f"  {f['mimetype']:<10} {f.get('width') or '-'}x{f.get('height') or '-'} {f.get('size') or 0:>11,} bytes {f['url']}")
```

Output (from the run on 2026-11-20, 00:07 UTC):

```text
robots.txt HTTP 200: User-agent: 008 | User-agent: Baiduspider | Disallow: /search | Disallow: /pictures/search | Disallow: /pictures/related | Crawl-Delay: 5 | named AI agents: []
legal HTTP 200: found: 'We reserve the right to block IP addresses that fail to honor our websites’ robot.txt files'
legal HTTP 200: found: 'submit a total of no more than 10 requests per minute to our applications, regardless of the number of machines'
legal HTTP 200: found: 'we generally do not own the rights to materials in our collections'
legal HTTP 200: found: 'The links are not endorsements'
limits HTTP 200: found: 'The API is accessible to the public with no API key or authentication required.'
limits HTTP 200: found: 'users may encounter 429 status codes or HTML pages with CAPTCHAs even when operating below the rates'
limits HTTP 200: found: 'JSON/YAML API for loc.gov Requests per minute 20 Time blocked, if rate is exceeded 1 hour'
limits HTTP 200: found: 'paging past the 100,000th item in a search result is not supported'
limits HTTP 200: found: 'It is recommended that requests not exceed 1,000 items per page.'

photos, no filter, full page   HTTP 200 application/json 111,138 chars 0.8 s | of 469 | ['collection', 'photo, print, drawing'] 'Wright Brothers Negatives'; ['photo, print, drawing'] '[Group including the Wright brothers]'; ['photo, print, drawing'] 'Wright brothers aeroplane - patented pla'
photos, at=results,pagination  HTTP 200 application/json 26,969 chars 1.9 s | of 469 | ['collection', 'photo, print, drawing'] 'Wright Brothers Negatives'; ['photo, print, drawing'] '[Group including the Wright brothers]'; ['photo, print, drawing'] 'Wright brothers aeroplane - patented pla'
collection search              HTTP 200 application/json 25,220 chars 1.2 s | of 106 | ['photo, print, drawing'] '[Surf at Kitty Hawk]'; ['photo, print, drawing'] '[Glider at Kitty Hawk]'; ['photo, print, drawing'] '[Gliding; Kitty Hawk, North Carolina]'
books format                   HTTP 200 application/json 9,322 chars 2.4 s | of 30974 | ['book'] 'Subject File: Patents--By Wright Brother'; ['book'] 'Subject File: Patents--By Wright Brother'; ['book'] 'Subject File: Patents--By Wright Brother'
photos without fo=json         HTTP 403 text/html 6,090 chars 0.7 s
unknown item                   HTTP 404 application/json 2,194 chars 10.4 s | exception 'not found', top-level keys ['caption', 'exception', 'item', 'options', 'status']

item 2001696291 resources: HTTP 200, 6 files
  image/tiff -x-  20,217,780 bytes https://tile.loc.gov/storage-services/master/pnp/ppprs/00400/00495u.tif
  image/tiff -x- 272,973,818 bytes https://tile.loc.gov/storage-services/master/pnp/ppprs/00400/00495a.tif
  image/jpeg 150x121       5,857 bytes https://tile.loc.gov/storage-services/service/pnp/ppprs/00400/00495_150px.jpg
  image/gif  150x121      20,478 bytes https://tile.loc.gov/storage-services/service/pnp/ppprs/00400/00495t.gif
  image/jpeg 640x518      60,263 bytes https://tile.loc.gov/storage-services/service/pnp/ppprs/00400/00495r.jpg
  image/jpeg 1024x828     367,319 bytes https://tile.loc.gov/storage-services/service/pnp/ppprs/00400/00495v.jpg
```

### 3. A topic to CSV with Python urllib: robots check for every agent, paging, disk cache (no browser)

Sends a descriptive User-Agent. Reads `sp=1, 2, ...` at `c=25` until it has `PER_FORMAT` items per format, then one item record each, and writes a CSV with the full rights text. Every answer is cached on disk for 24 h, so a second run makes no requests. Run with an empty cache: 13 requests (robots.txt, 2 searches, 10 items) in about 100 s.

```python
import csv, hashlib, html, http.client, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request, urllib.robotparser
from datetime import datetime, timezone

TOPIC = "erie canal"
FORMATS = ["photos", "maps"]  # loc.gov format endpoints; /collections/<slug>/ works the same way
PER_FORMAT = 5                # items per format, each with its own item record (rights live there)
OUT = "loc_erie_canal.csv"

SITE = "https://www.loc.gov"
UA = "library-of-congress-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]
CACHE_DIR = "~/.cache/library-of-congress-skill"
CACHE = os.path.expanduser(CACHE_DIR)
TTL = 24 * 3600  # the JSON answers carry Cache-Control: max-age=86400
calls = {"http": 0, "cache": 0}

# robots.txt: only 008 and Baiduspider are named; '*' disallows /search, /pictures/search, /pictures/related, Crawl-Delay 5
rp = urllib.robotparser.RobotFileParser(SITE + "/robots.txt")
with urllib.request.urlopen(urllib.request.Request(rp.url, headers={"User-Agent": UA}), timeout=30) as r:
    rp.parse(r.read().decode().splitlines())
    print(f"robots.txt HTTP {r.status}, Crawl-Delay for '*': {rp.crawl_delay('*')}")
for p in ["/photos/?q=x&fo=json", "/maps/?q=x&fo=json", "/item/2001696291/?fo=json", "/collections/x/?q=x&fo=json", "/search/?q=x&fo=json"]:
    ok = [a for a in AGENTS if rp.can_fetch(a, SITE + p)]
    print(f"  {p:<32} allowed for {len(ok)} of {len(AGENTS)} agents")
    if not p.startswith("/search/") and len(ok) != len(AGENTS):
        sys.exit("robots.txt now disallows a path this skill uses: stop")
PAUSE = max(6.5, rp.crawl_delay("*") or 0)  # and loc.gov/legal: "no more than 10 requests per minute"
time.sleep(PAUSE)

def get(path):
    """-> parsed JSON (disk cache for TTL), or None on 404. Network error or 502/503/504: wait 30 s, retry once.
    429 or a non-JSON answer (CAPTCHA, Cloudflare challenge): exit, the API blocks for 1 hour."""
    url = SITE + path
    f = os.path.join(CACHE, hashlib.sha256(url.encode()).hexdigest() + ".json")
    try:
        if time.time() - os.path.getmtime(f) < TTL:
            calls["cache"] += 1
            return json.load(open(f))
    except (OSError, ValueError):
        pass
    for attempt in range(2):
        calls["http"] += 1
        status, ctype, raw = 0, "", b""
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=120) as r:
                status, ctype, raw = r.status, r.headers.get("Content-Type", ""), r.read()
        except urllib.error.HTTPError as e:
            status, ctype, raw = e.code, e.headers.get("Content-Type", ""), e.read()
        except (OSError, http.client.HTTPException) as e:  # timeouts, resets, a body cut short (IncompleteRead)
            raw = str(e).encode()
        time.sleep(PAUSE)
        if status in (0, 502, 503, 504) and attempt == 0:
            time.sleep(30)
            continue
        break
    if status == 429 or (status and "json" not in ctype):
        sys.exit(f"{url}: HTTP {status} {ctype or '-'} (rate limit, CAPTCHA or challenge page): stop loc.gov for 1 hour")
    if status == 404:
        return None
    if status != 200:
        sys.exit(f"{url}: HTTP {status} {' '.join(raw.decode(errors='replace').split())[:200]}")
    body = json.loads(raw)
    os.makedirs(CACHE, exist_ok=True)
    json.dump(body, open(f, "w"))
    return body

def biggest_jpeg(urls):
    best = (0, None)
    for u in urls or []:
        w = re.search(r"[#&]w=(\d+)", u)
        if ".jpg" in u.split("#")[0] and (int(w[1]) if w else 0) >= best[0]:
            best = (int(w[1]) if w else 0, u.split("#")[0])
    return best[1]

def text(x):
    return " ".join(re.sub(r"<[^>]+>", " ", html.unescape(" ".join(x) if isinstance(x, list) else x or "")).split())

rows = []
now = datetime.now(timezone.utc)
print(f"\n'{TOPIC}' on loc.gov, {now:%Y-%m-%d %H:%M} UTC, {PER_FORMAT} items per format, {PAUSE} s between requests")
for fmt in FORMATS:
    got, sp = [], 0
    while len(got) < PER_FORMAT:
        sp += 1
        qs = urllib.parse.urlencode({"q": TOPIC, "fo": "json", "c": 25, "sp": sp, "at": "results,pagination",
                                     "fa": "online-format:image|access-restricted:false"})
        d = get(f"/{fmt}/?{qs}")
        got += [r for r in d["results"] if "/item/" in r.get("url", "")]
        if not d["pagination"].get("next"):
            break
    print(f"  {fmt}: {d['pagination']['of']} online images, {sp} page(s) read")
    for r in got[:PER_FORMAT]:
        iid = r["url"].rstrip("/").split("/item/")[1]
        rec = get(f"/item/{urllib.parse.quote(iid)}/?fo=json&at=item")
        if rec is None:
            continue
        it = rec["item"]
        rows.append({"format": fmt, "item_id": iid, "title": text(it.get("title"))[:200],
                     "date": (it.get("created_published_date") or it.get("date") or "").rstrip("."),
                     "item_url": it.get("url") or r["url"], "image_url": biggest_jpeg(it.get("image_url")),
                     "rights_advisory": it.get("rights_advisory") or "", "rights": text(it.get("rights")),
                     "access_restricted": it.get("access_restricted")})

with open(OUT, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
for x in rows:
    print(f"  {x['format']:<6} {x['item_id']:<10} {x['date'][:22]:<22} {x['title'][:40]:<40} "
          f"rights: {(x['rights_advisory'] or x['rights'] or 'NONE IN RECORD')[:44]}")
print(f"\n{len(rows)} rows -> {OUT}; {sum(not x['image_url'] for x in rows)} without a JPEG, "
      f"{sum(not (x['rights_advisory'] or x['rights']) for x in rows)} without any rights text")
print(f"{calls['http']} HTTP requests, {calls['cache']} from the disk cache ({CACHE_DIR}, {TTL // 3600} h)")
print("Source: Library of Congress (https://www.loc.gov). Check each item's rights before reuse.")
```

Output (from the run on 2026-11-20, 00:15 UTC, empty cache):

```text
robots.txt HTTP 200, Crawl-Delay for '*': 5
  /photos/?q=x&fo=json             allowed for 11 of 11 agents
  /maps/?q=x&fo=json               allowed for 11 of 11 agents
  /item/2001696291/?fo=json        allowed for 11 of 11 agents
  /collections/x/?q=x&fo=json      allowed for 11 of 11 agents
  /search/?q=x&fo=json             allowed for 0 of 11 agents

'erie canal' on loc.gov, 2026-11-20 00:15 UTC, 5 items per format, 6.5 s between requests
  photos: 270 online images, 1 page(s) read
  maps: 22 online images, 1 page(s) read
  photos 2017821363 1941 Oct               Erie Canal, New York                     rights: No known restrictions. For information, see 
  photos 2016794880 [between 1900 and 1906 Erie Canal, Rochester, N.Y.              rights: No known restrictions on publication.
  photos 2016813914 [between 1900 and 1910 Erie Canal, Tonawanda, N.Y.              rights: No known restrictions on publication.
  photos 2016797468 [between 1880 and 1897 Erie Canal at Little Falls               rights: No known restrictions on publication.
  photos 2017821365 1941 Oct               Erie Canal lock, New York                rights: No known restrictions. For information, see 
  maps   gm70004800 1862                   Map shewing the several routes proposed  rights: The content of the Library of Congress Geogr
  maps   98688674   1847                   Map of the proposed Great Western and La rights: The content of the Library of Congress Geogr
  maps   98688769   1852                   Map representing the route of the Philad rights: The content of the Library of Congress Geogr
  maps   00554823   1824                   Map of the state of New York             rights: The content of the Library of Congress Geogr
  maps   00554824   1831                   The tourist's map of the state of New Yo rights: The content of the Library of Congress Geogr

10 rows -> loc_erie_canal.csv; 0 without a JPEG, 0 without any rights text
12 HTTP requests, 0 from the disk cache (~/.cache/library-of-congress-skill, 24 h)
Source: Library of Congress (https://www.loc.gov). Check each item's rights before reuse.
```

The same script run again at 00:17 UTC ended with:

```text
10 rows -> loc_erie_canal.csv; 0 without a JPEG, 0 without any rights text
0 HTTP requests, 12 from the disk cache (~/.cache/library-of-congress-skill, 24 h)
Source: Library of Congress (https://www.loc.gov). Check each item's rights before reuse.
```

### 4. curl, headers and mistakes

```bash
B=https://www.loc.gov
UA='library-of-congress-skill-example/1.0 (+https://github.com/browser-use/browser-harness)'
# loc.gov/legal: no more than 10 requests per minute; robots.txt Crawl-Delay 5. Every call below waits 7 s.
T=$(mktemp); E=$(mktemp); P=$(mktemp)  # temp files, removed at the end
j() {  # GET -> JSON on stdout. A 5xx (a 525 and a 503 were seen) or a cut connection: wait 30 s, retry once.
       # 429 or a non-JSON page (CAPTCHA, Cloudflare "Just a moment..."): stop, the API blocks for 1 hour.
  for i in 1 2; do
    s=$(curl -sS -G -A "$UA" --max-time 120 -o "$T" -w '%{http_code} %{content_type}' "$@")
    case "$s" in
      "200 application/json"*) cat "$T"; return 0 ;;
      5*|000*) if [ $i = 1 ]; then echo "HTTP ${s%% *}: retry in 30 s" >&2; sleep 30; continue; fi ;;
    esac
    echo "HTTP $s: stop (429 or a non-JSON page means stop loc.gov for 1 hour)" >&2; return 1
  done; return 1
}
# search one format endpoint (never /search/: robots.txt disallows it); fa= keeps images viewable off-site
j "$B/maps/" --data-urlencode 'q=chesapeake bay' -d fo=json -d c=3 -d at=results,pagination \
  --data-urlencode 'fa=online-format:image|access-restricted:false' \
  | python3 -c 'import sys, json
d = json.load(sys.stdin); print("maps chesapeake bay:", d["pagination"]["of"], "online images")
for r in d["results"]: print(" ", r["url"], "|", r.get("date"), "|", r["title"][:60])'
sleep 7
# headers: JSON, CORS open, cached a day; the X-Nearside-Cache header says MISS or HIT
curl -sS -G -A "$UA" -D - -o /dev/null "$B/maps/" --data-urlencode 'q=chesapeake bay' -d fo=json -d c=3 -d at=results,pagination \
  --data-urlencode 'fa=online-format:image|access-restricted:false' | tr -d '\r' \
  | grep -iE '^(HTTP/|(content-type|access-control-allow-origin|cache-control|x-nearside-cache|cf-cache-status|retry-after|server):)'
sleep 7
# one item record (at=item drops related items and facets): rights and image list live here
j "$B/item/2017821363/" -d fo=json -d at=item | python3 -c 'import sys, json
it = json.load(sys.stdin)["item"]
print("item:", it["title"], "|", it.get("created_published_date"), "| rights_advisory:", it.get("rights_advisory"))
print("  biggest image:", [u.split("#")[0] for u in it["image_url"] if ".jpg" in u][-1])'
sleep 7
# mistakes: an unknown item is HTTP 404 with a JSON body; the HTML page (no fo=json) is a different answer
curl -sS -A "$UA" -o "$E" -w 'unknown item -> HTTP %{http_code} %{content_type} ' "$B/item/not-a-real-item-zz9/?fo=json&at=item"
python3 -I -c 'import json, sys; print("exception:", json.load(open(sys.argv[1]))["exception"])' "$E"
sleep 7
curl -sS -A "$UA" -o "$P" -w 'no fo=json -> HTTP %{http_code} %{content_type} ' "$B/maps/?q=chesapeake%20bay&c=3"
grep -o '<title>[^<]*</title>' "$P" | head -1 | tr -s ' \n' ' '; echo
rm -f "$T" "$E" "$P"
```

Output (from the run on 2026-11-20, 00:19 UTC; the first run at 00:17 got HTTP 525 on its first call and had no retry; re-run at 00:43 UTC after the temp files moved to `mktemp`, same output):

```text
maps chesapeake bay: 107 online images
  https://www.loc.gov/item/94683953/ | None | Chesapeake Bay wetlands : take pride in Chesapeake Bay
  https://www.loc.gov/item/2017588252/ | 1862 | Chesapeake Bay
  https://www.loc.gov/item/88690563/ | 1987 | Chesapeake Bay program, monitoring vital signs of the bay
HTTP/2 200 
content-type: application/json
access-control-allow-origin: *
x-nearside-cache: MISS
cache-control: no-transform, max-age=86400
cf-cache-status: HIT
server: cloudflare
item: Erie Canal, New York | 1941 Oct. | rights_advisory: No known restrictions. For information, see U.S. Farm Security Administration/Office of War Information Black & White Photographs https://www.loc.gov/rr/print/res/071_fsab.html
  biggest image: https://tile.loc.gov/storage-services/service/pnp/fsa/8c33000/8c33500/8c33505v.jpg
unknown item -> HTTP 404 application/json exception: not found
no fo=json -> HTTP 403 text/html; charset=UTF-8 <title>Just a moment...</title> 
```

## Fields

| Field | Where | Notes |
|---|---|---|
| `pagination.of`, `current`, `next`, `perpage` | search | total results, page number, next page URL (null on the last page). `perpage_options` 25, 50, 100, 150 on the site; the limits page recommends at most 1,000 per page (`c=1000`) and says paging past the 100,000th item "is not supported" |
| `results[].url` | search | `https://www.loc.gov/item/<id>/` for an item; collection and web-page records have other paths |
| `results[].id` | search | the same URL with `http://` |
| `results[].title`, `date`, `original_format`, `online_format` | search | `date` is normalized (`1900-01-01`) and can be null (map 94683953 in block 4); `original_format` `["collection", ...]` marks a collection |
| `results[].image_url` | search, item | a list of the same image in several sizes, each with `#h=..&w=..`; the widest `.jpg` is the useful one (1024 px `...v.jpg` for Prints & Photographs, IIIF `.../full/pct:25/0/default.jpg` for maps) |
| `results[].item.rights_advisory` | search (photos) | absent from map results |
| `results[].access_restricted` | search, item | `true` means viewable only at the Library; facet `access-restricted:true` had 50 of 469 "wright brothers" photo results |
| `item.title`, `item.created_published_date` | item | the date as cataloged, e.g. `[1900 Dec. 27]`, `[between 1900 and 1906]`, `1941 Oct.`; maps often have only `item.date` (`1910`, `190?`) |
| `item.rights_advisory`, `item.rights_information` | item | short statements; seen on photos, not on maps |
| `item.rights` | item | a list of HTML strings, the collection's rights statement and credit line; `[]` on the book record 0000000000 |
| `item.url` | item | the item page to cite |
| `resources[0].files[0]` | item, `at=item,resources` | every file with `mimetype`, `width`, `height`, `size`: TIFF masters were 20,217,780 and 272,973,818 bytes for one 4 x 5 in. glass negative |
| response headers | all | `Content-Type: application/json`, `Access-Control-Allow-Origin: *`, `Server: cloudflare`, `X-Nearside-Cache: MISS`/`HIT`; `Cache-Control: no-transform, max-age=86400` on most answers, `no-cache, max-age=0` with `CF-Cache-Status: BYPASS` on some; no rate-limit headers seen |

## Gotchas

- **`/search/` is off-limits.** The API docs (https://www.loc.gov/apis/json-and-yaml/) list searches at `loc.gov/search/`, and facet links inside JSON answers point to it (`item.dates` -> `https://www.loc.gov/search/?dates=1900/1900&fo=json`), but robots.txt disallows `/search` for every agent, and the legal page reserves the right to block IP addresses that ignore robots.txt. Do not follow those links; use `/photos/`, `/maps/`, `/books/` or `/collections/<slug>/` with the same parameters.
- **Without `fo=json` you get a challenge, not a page.** `/maps/?q=chesapeake%20bay&c=3` returned HTTP 403 `text/html` "Just a moment..." (a Cloudflare challenge) both to curl and to `fetch()` inside a logged-out loc.gov tab, while the same URL with `fo=json` was HTTP 200 JSON. The blocks treat any non-JSON answer as a stop signal, as the limits page asks for CAPTCHA pages.
- **Ten per minute means all your requests.** The legal page counts requests "regardless of the number of machines", so a browser and a script running together share one budget. The blocks wait 6.5 s after every request; do not run them at the same time.
- **Slow first answers get cut.** Map item 73690241 took 64.1 s before the HTTP/2 stream broke and then answered HTTP 503 `{"exception": "service unavailable"}`; a collection search broke after 47.1 s and answered in 0.15 s from cache 7 s later. `at=` makes answers smaller (photos `c=3`: 111,138 characters without `at`, 26,969 with `at=results,pagination`) and `at=item` drops the related items of an item record. urllib (HTTP/1.1) also got a cut body once (`IncompleteRead`); block 3 catches it with the network errors.
- **A made-up numeric id can be real.** `/item/0000000000/` is a catalog record (a book), so test a missing item with a non-numeric id: `/item/not-a-real-item-zz9/?fo=json` is HTTP 404 with a JSON body `{"exception": "not found", "item": {}, ...}`.
- **Facet filters join with `|`.** `fa=online-format:image|access-restricted:false` (URL-encoded `%7C`) applies both. Other filters from the `facets` list: `original-format:...`, `location:...`, `partof:...`, `subject:...`; `dates=1900/1999` limits by year range, which the limits page recommends for large result sets.
- **Counts move.** "erie canal" maps with the filter were 20 at 00:12 UTC, 22 at 00:15 UTC, 17 at about 00:32 UTC and 22 again at 00:35 UTC, and photos "wright brothers" were 469 without the filter at 23:17 and 23:57 UTC. Report counts with the access time.
- **Dates are catalog text.** `created_published_date` (`[between 1880 and 1897]`, `1941 Oct.`) is what the item page shows; `date` and `sort_date` are years for sorting. Strip the trailing period the catalog sometimes adds.
- **Image sizes.** The service JPEGs in `image_url` are fine for previews and links; the TIFF masters in `resources` can be hundreds of MB. Image and `/storage-services/` downloads have their own limit (150 per minute each, 1 hour blocked); https://tile.loc.gov/robots.txt is HTTP 404 (no rules). No image file was downloaded here.
- **Tab marker.** The harness sets the tab title to a horse emoji; the blocks check `location.origin` and the page text, not the title.

## What does not work

- **`/search/?fo=json`, `/pictures/search` and `/pictures/related`**: disallowed by robots.txt; not called. Links to them inside JSON answers (`item.dates`, `creators[].link`) are not followed.
- **HTML search pages** (no `fo=json`): HTTP 403 Cloudflare challenge for scripted clients.
- **Not tested:** a 429 or CAPTCHA on a JSON URL (never provoked; the blocks stop on either), `c` above 25, deep paging, `/books/` item records, the IIIF image service and any image download.
