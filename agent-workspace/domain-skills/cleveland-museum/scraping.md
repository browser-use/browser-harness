# Cleveland Museum of Art Open Access (openaccess-api.clevelandart.org) - Find CC0 Artworks by an Artist or Keyword with Title, Date, Creator, Credit Line and Downloadable Web/Print Image URLs (REST API, no key)

Field-tested against openaccess-api.clevelandart.org on 2026-11-19 (US Eastern evening; 2026-11-19 23:57 to 2026-11-20 00:13 UTC) using a fresh Browser Use cloud browser (logged out; one session, 00:01-00:09 UTC) plus Python `urllib` and `curl` from a Linux machine. 19 browser page loads (the API documentation page, 3 robots.txt files 3 times, the Terms and Conditions 3 times, the GitHub README 3 times, then the documentation page again) and 101 in-page `fetch()` calls (blocks 1 and 2 ran 3 times each while they were written), about 110 curl calls (2 to www.clevelandart.org, about 25 to the image CDN openaccess-cdn.clevelandart.org, the rest to the API) and 16 urllib calls (block 3 twice), all serial at 1 s or more spacing (10 s on www.clevelandart.org). Every call was HTTP 200 except the deliberate HTTP 404 (unknown artwork id, the CDN's robots.txt) and HTTP 422 (bad `limit`) probes below and one in-page `fetch()` of a CDN image, which the browser blocked (no CORS header). Most answers took 0.1-1.9 s; 1,000 ids in one call took 10.2 s. No 429, no challenge, no key, no login. An independent verifier re-ran all four blocks verbatim at 2026-11-20 00:15-00:17 UTC (blocks 1 and 2 in a new cloud browser, block 3 in an empty folder): output identical except the run times. Block 2 then moved its README read from github.com to raw.githubusercontent.com (robots.txt, see below) and was re-run at 00:24 UTC with byte-identical output.

robots.txt (checked 2026-11-19/20, curl, the cloud browser and `urllib.robotparser`): https://openaccess-api.clevelandart.org/robots.txt is two lines, `User-agent: Amazonbot` / `Disallow: /`, and nothing for `*`, so GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider may fetch `/api/` (block 3 checks all 12 agents; only Amazonbot is out). https://openaccess-cdn.clevelandart.org/robots.txt is HTTP 404 (no rules). https://www.clevelandart.org/robots.txt has one `*` group with `Crawl-delay: 10` and `Disallow: /api` among others; that is the museum's website host, not the API host, and this skill reads only its robots.txt and terms page there (block 2, 10 s apart). No named AI-agent groups on these three hosts. Block 2 reads the README from raw.githubusercontent.com (robots.txt HTTP 404, no rules), not from github.com, whose robots.txt has `User-agent: Bytespider` / `Disallow: /`. Terms: the Open Access README on GitHub (https://github.com/ClevelandMuseumArt/openaccess, file https://raw.githubusercontent.com/ClevelandMuseumArt/openaccess/master/README.md; README.md last changed 2025-02-24 per the GitHub commit history, while the data files get a "scheduled update" commit daily) says the datasets are "for unrestricted commercial and noncommercial use", dedicated CC0, image assets "under the same terms", "Attribution is not required", "You must not use The Cleveland Museum of Art's trademarks or otherwise claim or imply that the Museum or any other third party endorses you or your use of the dataset", and a modified dataset must say it was modified. The Terms and Conditions (https://www.clevelandart.org/terms-and-conditions, no date on the page) say "CC0 Content may be used free-of-charge for both commercial and non-commercial purposes without the prior consent or permission of CMA", that use of the API is subject to those terms, that CMA logs IP addresses and usage and "may limit the number of transactions a user may send or receive through the API", or "may in the future require access through assigned keys"; content not marked CC0 is for "limited non-commercial, educational, and personal use" only; THE CLEVELAND MUSEUM OF ART® and ARTLENS® are among its trademarks. No AI/ML, scraping, crawling or automated-access clause in either (a word search for scrap, crawl, robot, automat, artificial, machine learning, AI, data mining found none). Naming: this skill writes the source as plain text "Cleveland Museum of Art Open Access", uses no museum logo, and is not affiliated with or endorsed by the museum. It returns images only for records whose `share_license_status` is `CC0`.

**CC0 is the museum's call, per record.** The terms say CMA believes these works are in the public domain "upon reasonable investigation" but "makes no representations or warranties" that they are. Keep `share_license_status`, the page link (`url`) and the access date with each image; a record can change status in the daily update.

## Quick summary

- **No scraping.** `GET https://openaccess-api.clevelandart.org/api/artworks/?artists=<name>&cc0=1&has_image=1&limit=100&fields=...` (or `q=<keyword>`) -> `{"info": {"total": 5, ...}, "data": [{"id": 135382, "accession_number": "1958.39", "title": "The Red Kerchief", "creation_date": "c. 1868–73", "creators": [...], "creditline": "Bequest of Leonard C. Hanna Jr.", "share_license_status": "CC0", "images": {"web": {"url": ".../1958.39_web.jpg", ...}, "print": ..., "full": ...}}]}`. `/api/artworks/<id or accession number>` returns one record, `/api/creators/?name=` resolves an artist. JSON, no key.
- **Answers (block 1, 2026-11-20 00:07 UTC):** **Claude Monet: 5 CC0 works with images**, all 5 of his works there, e.g. *The Red Kerchief* (c. 1868–73, Bequest of Leonard C. Hanna Jr.); **Vincent van Gogh: 5 of 6 works**, e.g. *Adeline Ravoux* (1890); **Rembrandt van Rijn: 117 of 120** (two creator records); **"water lilies": 8 CC0 works with images**, first Monet's *Water Lilies (Agapanthus)* (c. 1915–26). Across the API: 68,813 records, 41,902 CC0 with images, 26,183 copyrighted (none of those has an image).
- **`artists=` is loose, so resolve the artist first.** `artists=van gogh` gives 558 works by 111 different first creators (47 in the first 100 rows, Rembrandt van Rijn 20 of them); `artists=vincent van gogh` gives 5. `q=monet` gives 18 (Monet 5, the rest mention him). Blocks 1 and 3 keep only records whose `creators` is the asked artist; block 1 gets the creator ids from `/api/creators/?name=`.
- **Three image sizes per CC0 record.** `images.web` (900 px on the long side, JPEG, about 0.1-0.5 MB), `images.print` (3400 px, JPEG, 1-6 MB) and `images.full` (TIFF, up to 507 MB for *The Red Kerchief*), on https://openaccess-cdn.clevelandart.org. Download `web` or `print`; HEAD a `full` URL before you fetch it.
- **Rate limit:** none published; the terms say CMA "may limit the number of transactions". All blocks send 1 request per second, serial, wait `Retry-After` (seconds or an HTTP date; default 60 s) once on 429/502/503/504 and stop when it asks for more than 120 s. No rate-limit, `ETag` or `Cache-Control` headers on API answers; data are refreshed once a day ("generally completed by 5am daily", time zone not given).

## What works

### 1. Artist or keyword as a person types it -> CC0 artworks with title, date, creator, credit line and image URLs (browser)

`on_api_tab()` opens the logged-out API documentation page, so `fetch()` is same-origin (see Gotchas for CORS). `get()` returns parsed JSON on HTTP 200, waits once on 429/502/503/504 and otherwise raises. `pick_creator()` asks `/api/creators/?name=` and keeps names that contain every typed word as a whole word; one person can have several creator records (Rembrandt van Rijn has two), so it keeps every id with the chosen name, and it picks a name only when it has 5 times the works of the next one, else it lists choices. `search()` pages `/api/artworks/` 100 at a time with `cc0=1&has_image=1` and keeps records that are `CC0`, have a `web` image and list the chosen creator id. 10 `fetch()` calls for the 6 questions.

```python
import json, re, time, unicodedata, urllib.parse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

ASK = [("artist", "Claude Monet"), ("artist", "van Gogh"), ("artist", "Rembrandt"), ("artist", "Smith"),
       ("keyword", "water lilies"), ("artist", "Monett")]  # (artist or keyword, as a person types it)
SHOW = 3  # artworks printed per question

API = "https://openaccess-api.clevelandart.org"
FIELDS = "id,accession_number,title,creation_date,creators,culture,creditline,share_license_status,images,url"
PAUSE = 1.0  # no published limit (the terms say CMA "may limit the number of transactions"): 1 request per second

def on_api_tab():
    """fetch() from the logged-out API documentation page, so requests are same-origin."""
    try:
        if js("location.origin") == API:
            return
    except Exception:
        pass
    new_tab(API + "/")
    wait_for_load()
    if js("location.origin") != API or "Open Access API" not in (js("document.title + ' ' + (document.body ? document.body.innerText.slice(0, 400) : '')") or ""):
        raise RuntimeError(f"the API host did not serve its documentation page (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__u[id] = {status: r.status, type: r.headers.get('content-type') || '',
      retry: r.headers.get('retry-after'), text: await r.text()}; })
    .catch(e => { window.__u[id] = {status: 0, type: '', retry: null, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

def retry_after(v):
    """Retry-After in seconds: a number or an HTTP date; 60 when absent or unreadable; at least 1. Over 120 s: stop."""
    try:
        s = float(v)
    except (TypeError, ValueError):
        try:
            s = (parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError):
            s = 60
    if s != s:  # 'nan'
        s = 60
    if s > 120:
        raise RuntimeError(f"server asks to wait {s:.0f} s (over 120 s): stopping")
    return max(s, 1)

def fetch(url):
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{url}: no answer after 60s")
        time.sleep(0.2)
    time.sleep(PAUSE)
    return r

def get(path, **params):
    """-> parsed JSON. Waits Retry-After once on 429/502/503/504 or a network error; raises on anything else
    (an unknown artwork id is HTTP 404 {"detail": "Artwork not found"}, a bad parameter HTTP 422)."""
    url = API + path + "?" + urllib.parse.urlencode(params)
    for attempt in range(2):
        r = fetch(url)
        if r["status"] in (0, 429, 502, 503, 504) and attempt == 0:
            time.sleep(retry_after(r["retry"]))
            continue
        break
    if r["status"] != 200 or "json" not in r["type"]:
        raise RuntimeError(f"{path}: HTTP {r['status']} {r['type']} {' '.join(r['text'].split())[:150]!r}; stopping")
    return json.loads(r["text"])

def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]", " ", s).split()

MAX_CREATORS = 500  # creator records read per name at most (10 calls)

def pick_creator(typed):
    """/api/creators/?name= -> (name, ids, artwork count, note), or None. One person can have several creator records
    (Rembrandt van Rijn has two), so the ids of every record with the chosen name are kept. Several different names:
    take the one with 5x the artworks of the next, else return the choices."""
    data, total = [], None
    while total is None or len(data) < min(total, MAX_CREATORS):  # page through every match, up to MAX_CREATORS
        d = get("/api/creators/", name=typed, limit=50, skip=len(data))
        total = d["info"]["total"]
        if not d["data"]:
            break
        data += d["data"]
    if len(data) < total:
        print(f"  PARTIAL: read {len(data)} of {total} creator records for {typed!r}; type more of the name")
    want = norm(typed)
    by_name = {}
    for c in data:
        words = norm(c["name"])
        if all(w in words for w in want):  # every typed word is a whole word of the name ('smith' is not 'silversmith')
            n = by_name.setdefault(c["name"], {"ids": set(), "works": 0, "desc": c["description"]})
            n["ids"].add(c["id"])
            n["works"] += len(c.get("artworks") or [])
    ranked = sorted(by_name.items(), key=lambda kv: -kv[1]["works"])
    if not ranked:
        return None
    if len(ranked) > 1 and ranked[0][1]["works"] < 5 * ranked[1][1]["works"]:
        return "choices", ranked, total
    name, n = ranked[0]
    others = ", ".join(f"{k} ({v['works']})" for k, v in ranked[1:4])
    return "one", (name, n, others), total

MAX_SCAN = 1000  # records read per question at most (10 calls)

def search(params, keep=lambda a: True, every_page=True):
    """/api/artworks/ with cc0 and has_image, 100 per call -> (records that are CC0, have a web image and pass keep(),
    API total, records scanned). every_page=False reads one page (enough to show SHOW works for a keyword)."""
    hits, skip, total = [], 0, None
    while total is None or skip < min(total, MAX_SCAN):
        d = get("/api/artworks/", **params, cc0=1, has_image=1, fields=FIELDS, limit=100, skip=skip)
        total = d["info"]["total"]
        hits += [a for a in d["data"] if a["share_license_status"] == "CC0" and (a.get("images") or {}).get("web") and keep(a)]
        skip += len(d["data"])
        if not d["data"] or not every_page:
            break
    return hits, total, skip

def size(n):
    n = int(n or 0)
    return f"{n / 1e6:.1f} MB" if n >= 1e6 else f"{n / 1e3:.0f} KB"

def show(a):
    who = ""
    for c in a.get("creators") or []:  # qualifier: 'and', 'attributed to', 'workshop of', ... (shown as the record has it)
        part = f"{c['qualifier']} {c['description']}" if c.get("qualifier") else c["description"]
        who += (" " if who and (c.get("qualifier") or "").startswith("and") else "; " if who else "") + part
    who = who or f"no creator recorded (culture: {', '.join(a.get('culture') or []) or 'none'})"
    im = a["images"]
    print(f"  {a['title']} ({a['creation_date']}) - {who}")
    print(f"    credit line: {a['creditline']} | accession {a['accession_number']} | id {a['id']} | {a['share_license_status']} | {a['url']}")
    for k in ("web", "print"):
        if im.get(k):
            print(f"    {k:<5} {im[k]['url']}  {im[k]['width']}x{im[k]['height']}, {size(im[k]['filesize'])}")
    if im.get("full"):
        print(f"    full  {im['full']['url']}  TIFF {im['full']['width']}x{im['full']['height']}, {size(im['full']['filesize'])}")

on_api_tab()
now = datetime.now(timezone.utc)
print(f"Cleveland Museum of Art Open Access API, checked {now:%Y-%m-%d %H:%M} UTC (CC0 works with images only)")
for kind, text in ASK:
    if kind == "keyword":
        hits, total, scanned = search({"q": text}, every_page=False)
        print(f"\nkeyword {text!r}: {total} CC0 works with images (q searches title, creator, description and more)")
    else:
        p = pick_creator(text)
        if p is None:
            print(f"\nartist {text!r}: no creator record has that name; check the spelling (the API does not suggest names)")
            continue
        if p[0] == "choices":
            print(f"\nartist {text!r}: {len(p[1])} different names among {p[2]} creator records; pick one (most works first): "
                  + "; ".join(f"{v['desc']} ({v['works']} works)" for k, v in p[1][:6]) + (" ..." if len(p[1]) > 6 else ""))
            continue
        name, n, others = p[1]
        ids = n["ids"]
        hits, total, scanned = search({"artists": name}, keep=lambda a: any(c["id"] in ids for c in a.get("creators") or []))
        print(f"\nartist {text!r} -> {n['desc']} (creator id {', '.join(map(str, sorted(ids)))}): {n['works']} works in the collection, "
              f"{len(hits)} CC0 with images (artists={name!r} gave {total}; {scanned} read, kept only this creator)"
              + (f" PARTIAL: stopped at {MAX_SCAN}" if scanned < total else "")
              + (f"; other names: {others}" if others else ""))
    for a in hits[:SHOW]:
        show(a)

print(f"\nSource: Cleveland Museum of Art Open Access ({API}), CC0, accessed {now:%d %B %Y %H:%M} UTC. "
      "Not affiliated with or endorsed by the museum.")
```

Output (from the run on 2026-11-20, 00:07 UTC; re-run 00:52 UTC in a new cloud browser after creator matches are paged: same output except the time):

```text
Cleveland Museum of Art Open Access API, checked 2026-11-20 00:07 UTC (CC0 works with images only)

artist 'Claude Monet' -> Claude Monet (French, 1840–1926) (creator id 1844): 5 works in the collection, 5 CC0 with images (artists='Claude Monet' gave 5; 5 read, kept only this creator)
  The Red Kerchief (c. 1868–73) - Claude Monet (French, 1840–1926)
    credit line: Bequest of Leonard C. Hanna Jr. | accession 1958.39 | id 135382 | CC0 | https://clevelandart.org/art/1958.39
    web   https://openaccess-cdn.clevelandart.org/1958.39/1958.39_web.jpg  723x900, 243 KB
    print https://openaccess-cdn.clevelandart.org/1958.39/1958.39_print.jpg  2732x3400, 3.8 MB
    full  https://openaccess-cdn.clevelandart.org/1958.39/1958.39_full.tif  TIFF 11652x14500, 506.9 MB
  Water Lilies (Agapanthus) (c. 1915–26) - Claude Monet (French, 1840–1926)
    credit line: John L. Severance Fund and an anonymous gift | accession 1960.81 | id 136510 | CC0 | https://clevelandart.org/art/1960.81
    web   https://openaccess-cdn.clevelandart.org/1960.81/1960.81_web.jpg  900x419, 135 KB
    print https://openaccess-cdn.clevelandart.org/1960.81/1960.81_print.jpg  3400x1581, 1.7 MB
    full  https://openaccess-cdn.clevelandart.org/1960.81/1960.81_full.tif  TIFF 6388x2970, 56.9 MB
  Spring Flowers (1864) - Claude Monet (French, 1840–1926)
    credit line: Gift of the Hanna Fund | accession 1953.155 | id 130391 | CC0 | https://clevelandart.org/art/1953.155
    web   https://openaccess-cdn.clevelandart.org/1953.155/1953.155_web.jpg  685x900, 215 KB
    print https://openaccess-cdn.clevelandart.org/1953.155/1953.155_print.jpg  2589x3400, 2.7 MB
    full  https://openaccess-cdn.clevelandart.org/1953.155/1953.155_full.tif  TIFF 11304x14845, 503.5 MB

artist 'van Gogh' -> Vincent van Gogh (Dutch, 1853–1890) (creator id 1779): 6 works in the collection, 5 CC0 with images (artists='Vincent van Gogh' gave 5; 5 read, kept only this creator)
  Adeline Ravoux (1890) - Vincent van Gogh (Dutch, 1853–1890)
    credit line: Bequest of Leonard C. Hanna Jr. | accession 1958.31 | id 135299 | CC0 | https://clevelandart.org/art/1958.31
    web   https://openaccess-cdn.clevelandart.org/1958.31/1958.31_web.jpg  900x897, 451 KB
    print https://openaccess-cdn.clevelandart.org/1958.31/1958.31_print.jpg  3400x3389, 6.0 MB
    full  https://openaccess-cdn.clevelandart.org/1958.31/1958.31_full.tif  TIFF 11512x11476, 396.4 MB
  The Large Plane Trees (Road Menders at Saint-Rémy) (1889) - Vincent van Gogh (Dutch, 1853–1890)
    credit line: Gift of the Hanna Fund | accession 1947.209 | id 125249 | CC0 | https://clevelandart.org/art/1947.209
    web   https://openaccess-cdn.clevelandart.org/1947.209/1947.209_web.jpg  900x718, 342 KB
    print https://openaccess-cdn.clevelandart.org/1947.209/1947.209_print.jpg  3400x2713, 4.5 MB
    full  https://openaccess-cdn.clevelandart.org/1947.209/1947.209_full.tif  TIFF 14395x11486, 496.1 MB
  Two Poplars in the Alpilles near Saint-Rémy (1889) - Vincent van Gogh (Dutch, 1853–1890)
    credit line: Bequest of Leonard C. Hanna Jr. | accession 1958.32 | id 135310 | CC0 | https://clevelandart.org/art/1958.32
    web   https://openaccess-cdn.clevelandart.org/1958.32/1958.32_web.jpg  673x900, 338 KB
    print https://openaccess-cdn.clevelandart.org/1958.32/1958.32_print.jpg  2543x3400, 3.9 MB
    full  https://openaccess-cdn.clevelandart.org/1958.32/1958.32_full.tif  TIFF 10950x14640, 481.0 MB

artist 'Rembrandt' -> Rembrandt van Rijn (Dutch, 1606–1669) (creator id 2520, 291869): 120 works in the collection, 117 CC0 with images (artists='Rembrandt van Rijn' gave 117; 117 read, kept only this creator); other names: Rembrandt Bugatti (1), Rembrandt Peale (1)
  Portrait of a Woman (1635 or earlier) - Rembrandt van Rijn (Dutch, 1606–1669) and Studio
    credit line: The Elisabeth Severance Prentiss Collection | accession 1944.90 | id 124089 | CC0 | https://clevelandart.org/art/1944.90
    web   https://openaccess-cdn.clevelandart.org/1944.90/1944.90_web.jpg  738x900, 146 KB
    print https://openaccess-cdn.clevelandart.org/1944.90/1944.90_print.jpg  2789x3400, 1.5 MB
    full  https://openaccess-cdn.clevelandart.org/1944.90/1944.90_full.tif  TIFF 5738x6995, 120.5 MB
  A Young Man with a Chain (c. 1629 or 1632) - Rembrandt van Rijn (Dutch, 1606–1669) and Studio
    credit line: Bequest of John L. Severance | accession 1942.644 | id 122348 | CC0 | https://clevelandart.org/art/1942.644
    web   https://openaccess-cdn.clevelandart.org/1942.644/1942.644_web.jpg  668x893, 229 KB
    print https://openaccess-cdn.clevelandart.org/1942.644/1942.644_print.jpg  2545x3400, 3.5 MB
    full  https://openaccess-cdn.clevelandart.org/1942.644/1942.644_full.tif  TIFF 4992x6668, 99.9 MB
  A Bearded Man Wearing a Hat (c. 1655–60) - studio of Rembrandt van Rijn (Dutch, 1606–1669)
    credit line: Gift of the Hanna Fund | accession 1950.252 | id 127573 | CC0 | https://clevelandart.org/art/1950.252
    web   https://openaccess-cdn.clevelandart.org/1950.252/1950.252_web.jpg  735x900, 118 KB
    print https://openaccess-cdn.clevelandart.org/1950.252/1950.252_print.jpg  2778x3400, 2.0 MB
    full  https://openaccess-cdn.clevelandart.org/1950.252/1950.252_full.tif  TIFF 4462x5462, 73.1 MB

artist 'Smith': 36 different names among 43 creator records; pick one (most works first): Kiki Smith (American, b. 1954) (18 works); David Smith (American, 1906–1965) (11 works); Paul Smith, Provincetown in cooperation with Provincetown Art Association (11 works); William E. Smith (American, 1913–1997) (10 works); Vincent D. Smith (American, 1929–2003) (9 works); Jaune Quick-to-See Smith (Citizen of the Confederated Salish and Kootenai Nation, 1940–2025) (8 works) ...

keyword 'water lilies': 8 CC0 works with images (q searches title, creator, description and more)
  Water Lilies (Agapanthus) (c. 1915–26) - Claude Monet (French, 1840–1926)
    credit line: John L. Severance Fund and an anonymous gift | accession 1960.81 | id 136510 | CC0 | https://clevelandart.org/art/1960.81
    web   https://openaccess-cdn.clevelandart.org/1960.81/1960.81_web.jpg  900x419, 135 KB
    print https://openaccess-cdn.clevelandart.org/1960.81/1960.81_print.jpg  3400x1581, 1.7 MB
    full  https://openaccess-cdn.clevelandart.org/1960.81/1960.81_full.tif  TIFF 6388x2970, 56.9 MB
  Flower Study of a Lily of the Valley (c. 1885–1915) - House of Fabergé (Russian, 1842–1918)
    credit line: The India Early Minshall Collection | accession 1966.443 | id 142734 | CC0 | https://clevelandart.org/art/1966.443
    web   https://openaccess-cdn.clevelandart.org/1966.443/1966.443_web.jpg  680x900, 148 KB
    print https://openaccess-cdn.clevelandart.org/1966.443/1966.443_print.jpg  2567x3400, 1.1 MB
    full  https://openaccess-cdn.clevelandart.org/1966.443/1966.443_full.tif  TIFF 4460x5907, 79.1 MB
  Gunakali Ragini (c. 1750) - no creator recorded (culture: Northwestern India, Rajasthan, Jaipur)
    credit line: Edward L. Whittemore Fund | accession 1954.261 | id 131671 | CC0 | https://clevelandart.org/art/1954.261
    web   https://openaccess-cdn.clevelandart.org/1954.261/1954.261_web.jpg  669x893, 123 KB
    print https://openaccess-cdn.clevelandart.org/1954.261/1954.261_print.jpg  2549x3400, 1.7 MB
    full  https://openaccess-cdn.clevelandart.org/1954.261/1954.261_full.tif  TIFF 5451x7270, 118.9 MB

artist 'Monett': no creator record has that name; check the spelling (the API does not suggest names)

Source: Cleveland Museum of Art Open Access (https://openaccess-api.clevelandart.org), CC0, accessed 20 November 2026 00:07 UTC. Not affiliated with or endorsed by the museum.
```

### 2. robots.txt, the terms and README quotes, and what the API does with each parameter (browser)

6 page loads and 23 in-page `fetch()` calls in the same tab. The website host asks for `Crawl-delay: 10`, so the block waits 10 s around its pages there.

```python
import json, time
from collections import Counter

API = "https://openaccess-api.clevelandart.org"
WWW = "https://www.clevelandart.org"  # robots.txt there asks for Crawl-delay: 10

START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__u[id] = {status: r.status, type: r.headers.get('content-type') || '', text: await r.text()}; })
    .catch(e => { window.__u[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

def raw(path):
    """One in-page GET of API + path (or a full URL) -> status, type and body. No retries: inspection only."""
    url = path if path.startswith("https://") else API + path
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{path}: no answer after 60s")
        time.sleep(0.2)
    time.sleep(1.0)
    return r

def brief(r):
    out = f"HTTP {r['status']} {r['type'].split(';')[0] or '-'}"
    if "json" not in r["type"]:
        return out + f" {' '.join(r['text'].split())[:60]!r}"
    d = json.loads(r["text"])
    if "info" in d:
        rows = d["data"]
        who = Counter((a.get("creators") or [{"description": "(none)"}])[0]["description"].split(" (")[0] for a in rows)
        return out + f" total {d['info']['total']}, {len(rows)} rows" + (
            f", most rows by {who.most_common(3)} ({len(who)} first creators)" if rows and "creators" in rows[0] else "")
    if "data" in d:
        a = d["data"]
        return out + " " + json.dumps({k: a.get(k) for k in ("id", "accession_number", "title", "share_license_status") if k in a}
                                      | ({"images": sorted(k for k, v in (a.get("images") or {}).items() if v)} if "images" in a else {}))
    return out + " " + json.dumps(d)[:120]

def page(url):
    goto_url(url)
    wait_for_load()
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    return st, " ".join((js("document.body ? document.body.innerText : (document.documentElement.textContent || '')") or "").split())

def check(label, st, text, needles):
    for n in needles:
        print(f"{label} HTTP {st}: {'found' if ' '.join(n.split()) in text else 'MISSING'}: {n!r}")

try:
    on_api = js("location.origin") == API
except Exception:
    on_api = False
if not on_api:
    new_tab(API + "/")
    wait_for_load()

for host in (API, "https://openaccess-cdn.clevelandart.org", WWW):
    st, txt = page(host + "/robots.txt")
    print(f"{host}/robots.txt HTTP {st}: {txt[:200]!r}")
    time.sleep(10 if host == WWW else 1)

st, txt = page(WWW + "/terms-and-conditions")
check("terms", st, txt, [
    "CC0 Content may be used free-of-charge for both commercial and non-commercial purposes without the prior consent or permission of CMA",
    "CMA may limit the number of transactions a user may send or receive through the API",
    "may in the future require access through assigned keys",
    "Works designated as CC0 do not require attribution or citation.",
    "nor does it grant permission to use CMA’s trademarks without prior approval",
    "THE CLEVELAND MUSEUM OF ART®"])
time.sleep(10)
# the raw README, not github.com: github.com/robots.txt disallows everything for Bytespider
st, txt = page("https://raw.githubusercontent.com/ClevelandMuseumArt/openaccess/master/README.md")
check("README", st, txt, [
    "for unrestricted commercial and noncommercial use",
    "Attribution is not required",
    "You must not use The Cleveland Museum of Art’s trademarks or otherwise claim or imply that the Museum or any other third party endorses you or your use of the dataset.",
    "Whenever you transform, translate or otherwise modify the dataset, you must make it clear that the resulting information has been modified."])
st, txt = page(API + "/")  # the documentation page; back on the API origin for same-origin fetch()
check("API docs", st, txt, [
    "Last update: 2025-07-11",
    "only artworks with the CC0 share_license_status will additionally provide access to CC0 images.",
    "These automated updates are generally completed by 5am daily.",
    "If no limit provided, API will return the maximum",
    "web: 900px at longest side, 300 dpi, jpeg format",
    "print: 3400px at longest side, 300 dpi, jpeg format",
    "Strictly speaking, these endpoints weren't intended to be used independently of the Collection Online"])
print()

F = "&fields=id,title,creators"
for label, path in (
    ("q=monet (keyword)          ", "/api/artworks/?q=monet&cc0=1&has_image=1&limit=100" + F),
    ("artists=monet              ", "/api/artworks/?artists=monet&cc0=1&has_image=1&limit=100" + F),
    ("artists=van gogh           ", "/api/artworks/?artists=van%20gogh&cc0=1&has_image=1&limit=100" + F),
    ("artists=vincent van gogh   ", "/api/artworks/?artists=vincent%20van%20gogh&cc0=1&has_image=1&limit=100" + F),
    ("creators name=van gogh     ", "/api/creators/?name=van%20gogh&limit=5"),
    ("creators name=monett       ", "/api/creators/?name=monett&limit=5"),
    ("cc0 with no value          ", "/api/artworks/?artists=monet&cc0&limit=5&fields=id"),
    ("cc0=0                      ", "/api/artworks/?artists=monet&cc0=0&limit=5&fields=id"),
    ("has_image=0                ", "/api/artworks/?artists=monet&has_image=0&limit=5&fields=id,images"),
    ("copyrighted&has_image=1    ", "/api/artworks/?copyrighted&has_image=1&limit=5&fields=id"),
    ("copyrighted, any           ", "/api/artworks/?copyrighted&limit=5&fields=id"),
    ("orderby=title              ", "/api/artworks/?artists=monet&cc0=1&orderby=title&limit=5&fields=id"),
    ("orderby=-sortable_date     ", "/api/artworks/?artists=monet&cc0=1&orderby=-sortable_date&limit=5&fields=id"),
    ("limit=5000                 ", "/api/artworks/?cc0=1&has_image=1&limit=5000&fields=id"),
    ("limit=abc                  ", "/api/artworks/?q=cat&limit=abc"),
    ("all CC0 with images        ", "/api/artworks/?cc0=1&has_image=1&limit=1&fields=id"),
    ("all records                ", "/api/artworks/?limit=1&fields=id"),
    ("one artwork by id          ", "/api/artworks/135382?fields=id,accession_number,title,share_license_status,images"),
    ("by accession number        ", "/api/artworks/1958.39?fields=id,accession_number,title,share_license_status,images"),
    ("copyrighted La Vie         ", "/api/artworks/1945.24?fields=id,accession_number,title,share_license_status,images"),
    ("unknown id                 ", "/api/artworks/999999999"),
):
    r = raw(path)
    if label.startswith("creators") and r["status"] == 200:
        d = json.loads(r["text"])
        print(f"{label} HTTP 200 total {d['info']['total']}: {[(c['name'], c['id'], len(c.get('artworks') or [])) for c in d['data']]}")
        continue
    print(f"{label} {brief(r)}")

r = raw("/api/artworks/?artists=monet&cc0=1&limit=1&fields=id,title")
print("\nfields=id,title returns keys:", sorted(json.loads(r["text"])["data"][0]))
r = raw("https://openaccess-cdn.clevelandart.org/1958.39/1958.39_web.jpg")
print("CDN image via fetch() from the API page:", r["status"], r["text"][:60])
```

Output (from the run on 2026-11-20, 00:07-00:08 UTC):

```text
https://openaccess-api.clevelandart.org/robots.txt HTTP 200: 'User-agent: Amazonbot Disallow: /'
https://openaccess-cdn.clevelandart.org/robots.txt HTTP 404: '404 Not Found nginx'
https://www.clevelandart.org/robots.txt HTTP 200: '# * User-agent: * Crawl-delay: 10 Disallow: /membership Disallow: /orders Disallow: /api Disallow: /errors Disallow: /404 Disallow: /500 # Host Host: https://www.clevelandart.org # Sitemaps Sitemap: h'
terms HTTP 200: found: 'CC0 Content may be used free-of-charge for both commercial and non-commercial purposes without the prior consent or permission of CMA'
terms HTTP 200: found: 'CMA may limit the number of transactions a user may send or receive through the API'
terms HTTP 200: found: 'may in the future require access through assigned keys'
terms HTTP 200: found: 'Works designated as CC0 do not require attribution or citation.'
terms HTTP 200: found: 'nor does it grant permission to use CMA’s trademarks without prior approval'
terms HTTP 200: found: 'THE CLEVELAND MUSEUM OF ART®'
README HTTP 200: found: 'for unrestricted commercial and noncommercial use'
README HTTP 200: found: 'Attribution is not required'
README HTTP 200: found: 'You must not use The Cleveland Museum of Art’s trademarks or otherwise claim or imply that the Museum or any other third party endorses you or your use of the dataset.'
README HTTP 200: found: 'Whenever you transform, translate or otherwise modify the dataset, you must make it clear that the resulting information has been modified.'
API docs HTTP 200: found: 'Last update: 2025-07-11'
API docs HTTP 200: found: 'only artworks with the CC0 share_license_status will additionally provide access to CC0 images.'
API docs HTTP 200: found: 'These automated updates are generally completed by 5am daily.'
API docs HTTP 200: found: 'If no limit provided, API will return the maximum'
API docs HTTP 200: found: 'web: 900px at longest side, 300 dpi, jpeg format'
API docs HTTP 200: found: 'print: 3400px at longest side, 300 dpi, jpeg format'
API docs HTTP 200: found: "Strictly speaking, these endpoints weren't intended to be used independently of the Collection Online"

q=monet (keyword)           HTTP 200 application/json total 18, 18 rows, most rows by [('Claude Monet', 5), ('Marie Bracquemond', 2), ('Paul Paulin', 1)] (13 first creators)
artists=monet               HTTP 200 application/json total 5, 5 rows, most rows by [('Claude Monet', 5)] (1 first creators)
artists=van gogh            HTTP 200 application/json total 558, 100 rows, most rows by [('Rembrandt van Rijn', 20), ('Lucas van Leyden', 14), ('Israhel van Meckenem', 6)] (47 first creators)
artists=vincent van gogh    HTTP 200 application/json total 5, 5 rows, most rows by [('Vincent van Gogh', 5)] (1 first creators)
creators name=van gogh      HTTP 200 total 1: [('Vincent van Gogh', 1779, 6)]
creators name=monett        HTTP 200 total 0: []
cc0 with no value           HTTP 200 application/json total 5, 5 rows
cc0=0                       HTTP 200 application/json total 0, 0 rows
has_image=0                 HTTP 200 application/json total 5, 5 rows
copyrighted&has_image=1     HTTP 200 application/json total 0, 0 rows
copyrighted, any            HTTP 200 application/json total 26183, 5 rows
orderby=title               HTTP 200 application/json total 0, 0 rows
orderby=-sortable_date      HTTP 200 application/json total 0, 0 rows
limit=5000                  HTTP 200 application/json total 41902, 1000 rows
limit=abc                   HTTP 422 application/json {"detail": [{"loc": ["query", "limit"], "msg": "value is not a valid integer", "type": "type_error.integer"}]}
all CC0 with images         HTTP 200 application/json total 41902, 1 rows
all records                 HTTP 200 application/json total 68813, 1 rows
one artwork by id           HTTP 200 application/json {"id": 135382, "accession_number": "1958.39", "title": "The Red Kerchief", "share_license_status": "CC0", "images": ["full", "print", "web"]}
by accession number         HTTP 200 application/json {"id": 135382, "accession_number": "1958.39", "title": "The Red Kerchief", "share_license_status": "CC0", "images": ["full", "print", "web"]}
copyrighted La Vie          HTTP 200 application/json {"id": 124245, "accession_number": "1945.24", "title": "La Vie", "share_license_status": "Copyrighted", "images": []}
unknown id                  HTTP 404 application/json {"detail": "Artwork not found"}

fields=id,title returns keys: ['accession_number', 'has_conservation_images', 'id', 'title']
CDN image via fetch() from the API page: 0 TypeError: Failed to fetch
```

### 3. Download the images with Python urllib: robots check for every agent, a credits CSV, files already on disk skipped (no browser)

Sends a descriptive User-Agent (curl's default also got HTTP 200). Checks each JPEG before saving it: HTTP 200, `image/jpeg`, the JPEG start bytes and the full `Content-Length`. Here the artist filter is the exact creator name (`"Katsushika Hokusai (..."`); use block 1's `pick_creator()` for names as people type them. Run in an empty folder; the second run shows the skip.

```python
import csv, hashlib, json, os, sys, time, urllib.error, urllib.parse, urllib.request, urllib.robotparser
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

WANT = [("artist", "Katsushika Hokusai", 3), ("keyword", "water lilies", 2), ("id", "1958.39", 1)]  # (kind, text, how many)
SIZE = "web"     # "web" (900 px JPEG, about 0.1-0.5 MB) or "print" (3400 px JPEG, about 1-6 MB); "full" TIFFs reach 500 MB
OUT = "cma-cc0"  # images + credits.csv go here; files already on disk are not downloaded again

API = "https://openaccess-api.clevelandart.org"
CDN = "https://openaccess-cdn.clevelandart.org"
UA = "cleveland-museum-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider", "Amazonbot"]
FIELDS = "id,accession_number,title,creation_date,creators,creditline,share_license_status,images,url"
PAUSE = 1.0  # no published limit; 1 request per second to the API and the CDN

def retry_after(v):
    """Retry-After in seconds: a number or an HTTP date; 60 when absent or unreadable; at least 1. Over 120 s: exit."""
    try:
        s = float(v)
    except (TypeError, ValueError):
        try:
            s = (parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError):
            s = 60
    if s != s:  # 'nan'
        s = 60
    if s > 120:
        sys.exit(f"server asks to wait {s:.0f} s (over 120 s): stopping")
    return max(s, 1)

def fetch(url):
    """-> (status, headers, body). Once waits Retry-After (default 60 s) on 429/502/503/504 or a network error."""
    for attempt in range(2):
        time.sleep(PAUSE)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=120) as r:
                return r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503, 504) and attempt == 0:
                time.sleep(retry_after(e.headers.get("Retry-After")))
                continue
            return e.code, e.headers, e.read()
        except OSError as e:  # URLError (DNS, refused connection), timeouts, resets
            if attempt == 0:
                time.sleep(60)
                continue
            sys.exit(f"{url}: {e}")

def api(path, **params):
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    st, h, body = fetch(url)
    if st == 404:
        return None
    if st != 200 or "json" not in h.get("Content-Type", ""):
        sys.exit(f"HTTP {st} {url}: {' '.join(body.decode(errors='replace').split())[:200]}")
    return json.loads(body)

def creator_text(a):
    out = ""
    for c in a.get("creators") or []:
        part = f"{c['qualifier']} {c['description']}" if c.get("qualifier") else c["description"]
        out += (" " if out and (c.get("qualifier") or "").startswith("and") else "; " if out else "") + part
    return out or "not recorded"

# robots.txt: the API host blocks only Amazonbot; the CDN host has none (HTTP 404 = no rules).
for host, path in ((API, "/api/artworks/"), (CDN, "/1958.39/1958.39_web.jpg")):
    rp = urllib.robotparser.RobotFileParser(host + "/robots.txt")
    st, _, body = fetch(rp.url)
    if st == 200:
        rp.parse(body.decode().splitlines())
    elif 400 <= st < 500:
        rp.allow_all = True  # what RobotFileParser.read() does on 4xx
    else:
        sys.exit(f"{rp.url}: HTTP {st}, cannot read the rules: stop")
    bad = [a for a in AGENTS if not rp.can_fetch(a, host + path)]
    print(f"robots {host + path:<70} HTTP {st}; allowed for {len(AGENTS) - len(bad)} of {len(AGENTS)} agents"
          + (f", disallowed: {', '.join(bad)}" if bad else ""))
    if set(bad) - {"Amazonbot"}:
        sys.exit("robots.txt now disallows a path this skill uses for an agent other than Amazonbot: stop")

now = datetime.now(timezone.utc)
print(f"\nDownloading {SIZE} images of CC0 works, {now:%Y-%m-%d %H:%M} UTC, into {OUT}/")
os.makedirs(OUT, exist_ok=True)
rows, got, kept = [], 0, 0
for kind, text, n in WANT:
    if kind == "id":  # an id or an accession number
        d = api(f"/api/artworks/{urllib.parse.quote(text)}", fields=FIELDS)
        found = [d["data"]] if d else []
    else:
        d = api("/api/artworks/", **{"q" if kind == "keyword" else "artists": text}, cc0=1, has_image=1, fields=FIELDS, limit=100)
        found = d["data"]
        if kind == "artist":  # artists= also matches other names (see Gotchas): keep the asked creator only
            found = [a for a in found if any(c["description"].startswith(text + " (") for c in a.get("creators") or [])]
    picked = [a for a in found if a["share_license_status"] == "CC0" and (a.get("images") or {}).get(SIZE)][:n]
    print(f"  {kind} {text!r}: {len(found)} found, {len(picked)} taken")
    for a in picked:
        im = a["images"][SIZE]
        path = os.path.join(OUT, im["filename"])
        if os.path.exists(path):
            kept += 1
            data = open(path, "rb").read()
        else:
            st, h, data = fetch(im["url"])
            ctype = h.get("Content-Type", "")
            if st != 200 or not ctype.startswith("image/jpeg") or data[:3] != b"\xff\xd8\xff" or len(data) != int(h.get("Content-Length", -1)):
                print(f"    SKIP {im['url']}: HTTP {st} {ctype} {len(data)} bytes (expected a whole JPEG)")
                continue
            with open(path, "wb") as f:
                f.write(data)
            got += 1
        print(f"    {im['filename']:<22} {len(data):>9,} bytes (API filesize {int(im['filesize']):,}) {im['width']}x{im['height']}  "
              f"{a['title'][:40]} ({a['creation_date']})")
        rows.append({"id": a["id"], "accession_number": a["accession_number"], "title": a["title"], "date": a["creation_date"],
                     "creator": creator_text(a), "credit_line": a["creditline"], "license": a["share_license_status"],
                     "page": a["url"], "image_url": im["url"], "file": im["filename"], "bytes": len(data),
                     "sha256": hashlib.sha256(data).hexdigest()[:16], "checked_utc": f"{now:%Y-%m-%d %H:%M}"})

CREDITS = os.path.join(OUT, "credits.csv")
COLS = ["id", "accession_number", "title", "date", "creator", "credit_line", "license", "page", "image_url", "file", "bytes", "sha256",
        "checked_utc"]  # when this row's license was read; rows kept from earlier runs keep their own date
old = {}
if os.path.exists(CREDITS):  # keep the rows of images from earlier runs; this run's rows replace same-file rows
    with open(CREDITS, newline="", encoding="utf-8") as f:
        old = {r["file"]: r for r in csv.DictReader(f) if r.get("file")}
merged = {**old, **{r["file"]: r for r in rows}}
with open(CREDITS, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
    w.writeheader()
    w.writerows(merged.values())
print(f"\n{got} downloaded, {kept} already on disk, {len(merged)} rows in {OUT}/credits.csv")
print(f"Source: Cleveland Museum of Art Open Access, CC0 (attribution optional), accessed {now:%d %B %Y %H:%M} UTC.")
```

Output (from the run on 2026-11-20, 00:09 UTC, empty folder; re-run 01:03 UTC after credits.csv started keeping earlier rows with a `checked_utc` column: same output except the time; a later run that picked only 1958.39 left 6 rows, 5 with their earlier `checked_utc`):

```text
robots https://openaccess-api.clevelandart.org/api/artworks/                  HTTP 200; allowed for 11 of 12 agents, disallowed: Amazonbot
robots https://openaccess-cdn.clevelandart.org/1958.39/1958.39_web.jpg        HTTP 404; allowed for 12 of 12 agents

Downloading web images of CC0 works, 2026-11-20 00:09 UTC, into cma-cc0/
  artist 'Katsushika Hokusai': 38 found, 3 taken
    1930.189_web.jpg         249,520 bytes (API filesize 259,461) 900x617  South Wind, Clear Sky, from Thirty-Six V (early 1830s)
    1985.327_web.jpg         296,013 bytes (API filesize 305,954) 900x626  Poem by Minamoto no Muneyuki from the se (1835–36)
    1985.326_web.jpg         204,141 bytes (API filesize 214,108) 900x613  Poem by Emperor Sanjo, from the series O (1835–36)
  keyword 'water lilies': 8 found, 2 taken
    1960.81_web.jpg          125,355 bytes (API filesize 134,866) 900x419  Water Lilies (Agapanthus) (c. 1915–26)
    1966.443_web.jpg         138,105 bytes (API filesize 147,610) 680x900  Flower Study of a Lily of the Valley (c. 1885–1915)
  id '1958.39': 1 found, 1 taken
    1958.39_web.jpg          232,571 bytes (API filesize 242,663) 723x900  The Red Kerchief (c. 1868–73)

6 downloaded, 0 already on disk, 6 rows in cma-cc0/credits.csv
Source: Cleveland Museum of Art Open Access, CC0 (attribution optional), accessed 20 November 2026 00:09 UTC.
```

Second run (00:10 UTC), last lines:

```text

0 downloaded, 6 already on disk, 6 rows in cma-cc0/credits.csv
Source: Cleveland Museum of Art Open Access, CC0 (attribution optional), accessed 20 November 2026 00:10 UTC.
```

### 4. curl, image sizes, headers and mistakes

```bash
B=https://openaccess-api.clevelandart.org/api
UA='cleveland-museum-skill-example/1.0 (+https://github.com/browser-use/browser-harness)'
# CC0 works with images by one artist: title, date, creator, credit line, web and print URLs (fields= keeps the answer small)
curl -sS --fail -A "$UA" "$B/artworks/?artists=vincent%20van%20gogh&cc0&has_image=1&limit=3&fields=title,creation_date,creators,creditline,share_license_status,images" \
  | python3 -c 'import sys, json
d = json.load(sys.stdin)
print("total", d["info"]["total"])
for a in d["data"]:
    print(a["share_license_status"], "|", a["title"], "|", a["creation_date"], "|", a["creators"][0]["description"], "|", a["creditline"])
    print("   web", a["images"]["web"]["url"], "| print", a["images"]["print"]["url"])'
sleep 1
# one artwork by accession number (the numeric id works too)
curl -sS --fail -A "$UA" "$B/artworks/1958.39?fields=id,title,share_license_status,images" \
  | python3 -c 'import sys, json
a = json.load(sys.stdin)["data"]
print(a["id"], a["accession_number"], a["title"], a["share_license_status"], a["images"]["full"]["url"], round(int(a["images"]["full"]["filesize"]) / 1e6), "MB TIFF")'
sleep 1
# image sizes before downloading: HEAD on the CDN (no robots.txt there: HTTP 404)
for k in web.jpg print.jpg full.tif; do
  curl -sS -A "$UA" -I -o /dev/null -w "1958.39_$k -> HTTP %{http_code} %{content_type} " "https://openaccess-cdn.clevelandart.org/1958.39/1958.39_$k"
  curl -sS -A "$UA" -I "https://openaccess-cdn.clevelandart.org/1958.39/1958.39_$k" | tr -d '\r' | sed -n 's/^content-length: /bytes /Ip'; sleep 1
done
# API headers: JSON, no rate-limit, ETag or Cache-Control headers; Access-Control-Allow-Origin comes and goes with x-cache-status (Gotchas)
curl -sS -A "$UA" -H 'Origin: https://example.com' -D - -o /dev/null "$B/artworks/?artists=monet&cc0&limit=1&fields=id" | tr -d '\r' \
  | grep -iE '^(HTTP/|(content-type|access-control-allow-[a-z]+|cache-control|etag|retry-after|x-ratelimit-limit|x-cache-status|server):)'
sleep 1
# mistakes: an unknown id is HTTP 404 JSON; a bad limit is HTTP 422; cc0=0 is not "off", it matches nothing
curl -sS -A "$UA" -w ' <- unknown id, HTTP %{http_code}\n' "$B/artworks/999999999"; sleep 1
curl -sS -A "$UA" -w ' <- limit=abc, HTTP %{http_code}\n' "$B/artworks/?q=cat&limit=abc"; sleep 1
curl -sS -A "$UA" "$B/artworks/?artists=monet&cc0=0&fields=id" | python3 -c 'import sys, json; print("cc0=0 -> total", json.load(sys.stdin)["info"]["total"])'
```

Output (from the run on 2026-11-20, 00:11 UTC):

```text
total 5
CC0 | Adeline Ravoux | 1890 | Vincent van Gogh (Dutch, 1853–1890) | Bequest of Leonard C. Hanna Jr.
   web https://openaccess-cdn.clevelandart.org/1958.31/1958.31_web.jpg | print https://openaccess-cdn.clevelandart.org/1958.31/1958.31_print.jpg
CC0 | The Large Plane Trees (Road Menders at Saint-Rémy) | 1889 | Vincent van Gogh (Dutch, 1853–1890) | Gift of the Hanna Fund
   web https://openaccess-cdn.clevelandart.org/1947.209/1947.209_web.jpg | print https://openaccess-cdn.clevelandart.org/1947.209/1947.209_print.jpg
CC0 | Two Poplars in the Alpilles near Saint-Rémy | 1889 | Vincent van Gogh (Dutch, 1853–1890) | Bequest of Leonard C. Hanna Jr.
   web https://openaccess-cdn.clevelandart.org/1958.32/1958.32_web.jpg | print https://openaccess-cdn.clevelandart.org/1958.32/1958.32_print.jpg
135382 1958.39 The Red Kerchief CC0 https://openaccess-cdn.clevelandart.org/1958.39/1958.39_full.tif 507 MB TIFF
1958.39_web.jpg -> HTTP 200 image/jpeg bytes 232571
1958.39_print.jpg -> HTTP 200 image/jpeg bytes 3757896
1958.39_full.tif -> HTTP 200 image/tiff bytes 506883100
HTTP/2 200 
content-type: application/json
server: cloudflare
x-cache-status: HIT
{"detail":"Artwork not found"} <- unknown id, HTTP 404
{"detail":[{"loc":["query","limit"],"msg":"value is not a valid integer","type":"type_error.integer"}]} <- limit=abc, HTTP 422
cc0=0 -> total 0
```

## Fields (`/api/artworks/` and `/api/artworks/<id>`, API version 4.0.3)

| Field | Value | Notes |
|---|---|---|
| `info.total`, `info.parameters` | int, object | `parameters` echoes what the API understood; `total` is all matches, not this page |
| `id`, `accession_number` | `135382`, `"1958.39"` | either works in `/api/artworks/<...>` |
| `title`, `title_in_original_language` | `"The Red Kerchief"`, `"Femme à la capeline rouge"` | |
| `creation_date` | text | `"c. 1868–73"`, `"1635 or earlier"`, `"not dated"`; years as integers in `creation_date_earliest`, `creation_date_latest`, `sortable_date` |
| `creators[]` | `id`, `description`, `qualifier`, `role`, `biography`, `birth_year`, `death_year` | `description` is "Name (Nationality, years)"; `qualifier` is e.g. `"studio of"` or `"and"` (Rembrandt "and Studio"); can be empty, then `culture` is the only maker (e.g. "Northwestern India, Rajasthan, Jaipur") |
| `creditline` | text | how the museum acquired it ("Bequest of Leonard C. Hanna Jr."); the full credit is in `tombstone` ("The Cleveland Museum of Art, Bequest of Leonard C. Hanna Jr., 1958.39") |
| `share_license_status` | `"CC0"`, `"Copyrighted"`, `"Other"` | only `CC0` records carry images; `copyright` holds the notice for the others ("© Estate of Pablo Picasso / Artists Rights Society (ARS), New York") |
| `images.web`, `.print`, `.full` | `url`, `width`, `height`, `filesize`, `filename` | numbers are strings; `filesize` ran 9,505-10,384 bytes above the bytes served for all 8 files checked (7 JPEGs, 1 TIFF; blocks 3 and 4): check `Content-Length`, not `filesize` |
| `alternate_images[]` | `web`, `print`, `full` (`url`, `width`, `height`, `filesize`), `annotation`, `date_created` | other views, e.g. `1958.39_alt0_web.jpg`; no `filename` key there (the docs list one), take it from `url` |
| `url` | `https://clevelandart.org/art/1958.39` | the museum's page for the work; link it with the image |
| `current_location` | text or null | `"222 Impressionism & Post-Impressionism"` |
| `updated_at` | `"2026-11-19 21:32:42.137000"` | no time zone given |
| `date_added_to_oa` | date or null | null for 1958.39; the docs say the `added_to_oa_*` filters work only from 2026 on |
| response headers | `Content-Type: application/json`, `Server: cloudflare`, `x-cache-status: HIT/MISS` | no rate-limit, `ETag` or `Cache-Control`; `Access-Control-Allow-Origin` only on some answers (Gotchas) |

## Gotchas

- **`artists=` matches far more than the artist.** `artists=van gogh` returned 558 records with 111 different first creators (Rembrandt van Rijn 113, Lucas van Leyden 63, Allart van Everdingen 63; 47 in the first 100 rows); `artists=gogh` returned 571. The full name narrows it (`vincent van gogh`, `claude monet`: 5 each), but still check `creators[].id` (block 1) or the exact `description` (block 3). `q=` searches title, creator, description "and several other meaningful fields": `q=monet` gives 18 works by 13 first creators, `q=water lilies` includes House of Fabergé's *Flower Study of a Lily of the Valley* and an Indian painting with no creator.
- **One artist, several creator records; one name, many artists.** `/api/creators/?name=rembrandt` gave 4 records: Rembrandt van Rijn twice (ids 2520 and 291869, 115 and 5 works), Rembrandt Bugatti and Rembrandt Peale. `name=smith` gave 43 records with 43 different names; 36 have "Smith" as a whole word (Kiki Smith, David Smith, William E. Smith...), the other 7 only contain it (Robert Smithson, Jonathan Goldsmith, "master silversmith"...): ask which one. `name=monett` gave 0 and no suggestion.
- **`cc0` is a flag, and `cc0=0` is not "off".** `cc0`, `cc0=`, `cc0=true` and `cc0=1` all gave Monet's 5; `cc0=0` gave total 0. `has_image=0` is ignored (Monet's 5, all with images). Leave a filter out to turn it off.
- **`orderby` breaks the search.** `orderby=title`, `-title`, `title asc`, `sortable_date`, `-sortable_date`, `creation_date` and `bogus` all gave HTTP 200 with total 0, with or without other filters; an empty `orderby=` is ignored. Sort locally (`sortable_date` is the year as an integer).
- **`limit` caps at 1000** (`limit=5000` gave 1000 rows) and a non-integer is HTTP 422 with a FastAPI-style `detail` list. Page with `skip`. 1,000 rows of `fields=id` took 10.2 s in the first test, then 38.9 s and 13.6 s at 00:20-00:22 UTC on 2026-11-20: allow a long timeout.
- **`fields=` always adds a few keys** (`accession_number`, `has_conservation_images`), and it keeps answers small: `creators` alone carries each artist's full biography.
- **CORS is not dependable.** The API's cache keeps the CORS headers of whoever asked first: a new URL first requested with an `Origin` header answered `Access-Control-Allow-Origin: *` on the MISS and on later HITs, even without `Origin`; a new URL first requested without `Origin` answered without it on later HITs, even with `Origin` (reproduced on 2 URLs with curl at 00:13 UTC; block 4's header line shows such a HIT). The CDN sent no CORS header, and `fetch()` of an image from the API page failed with `TypeError` (block 2). Fetch the API from its own documentation page (block 1) and download images outside the browser (blocks 3 and 4), or show them with `<img>`.
- **`full` TIFFs are huge**: 506,883,100 bytes for 1958.39; 57-507 MB across block 1's output. `images.full.filesize` gives the size before you download.
- **Copyrighted works have no images at all**: `copyrighted&has_image=1` gave total 0, and *La Vie* (Picasso, 1945.24) has `"images": {}` with a `copyright` notice. The museum's terms limit non-CC0 content to "limited non-commercial, educational, and personal use"; this skill does not use it.
- **The documented "Collection Online" endpoints** (`/api/collectiononline/jpeg_and_caption/<accession>`, `/tiff/`, `/metadata/`) "weren't intended to be used independently of the Collection Online", the docs say; use the `images` URLs instead.
- **Counts in the docs lag.** The README says "more than 61,000 artworks" and images for "as many as 30,000", the documentation page "more than 64,000 artwork records" and "over 37,000 works"; the API said 68,813 records and 41,902 CC0 with images on 2026-11-19. Quote `info.total` with its date.
- **Tab marker.** The harness sets the tab title to a horse emoji; block 1 checks `location.origin` and the page text, not the title.

## What does not work

- **Sorting with `orderby`** (total 0 for every value tried) and **`cc0=0` / `has_image=0`** as "off" switches.
- **Cross-origin `fetch()` of CDN images** from a browser page: no CORS header, `TypeError: Failed to fetch`.
- **Name suggestions**: `/api/creators/?name=monett` and `q=monett` both give total 0.
- **Not tested:** the 429 response (never provoked; no limit is published), the `/api/exhibitions/` endpoint, the GitHub JSON/CSV dumps (git LFS), downloading a `full` TIFF (HEAD only), and the `copyrighted` records' data beyond one example.
