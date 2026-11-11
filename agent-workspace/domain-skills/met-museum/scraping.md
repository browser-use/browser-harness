# Metropolitan Museum of Art - Is an Artwork On View at the Met, and in Which Gallery? (public API)

Field-tested against collectionapi.metmuseum.org on 2026-11-11 using a Browser Use cloud browser (logged out) plus `curl` and Python `urllib` from a Linux machine. 11 browser page loads (the API docs page, 3 robots.txt files, 4 object pages, the terms, the visit page, the gallery-closures page), 18 in-page `fetch()` calls and about 130 curl/urllib calls, all serial: every API call was HTTP 200 except the 404/405/410 answers listed below. No 429 from the API, no challenge, no key, no login.

robots.txt (checked 2026-11-11): collectionapi.metmuseum.org/robots.txt is HTTP 404 (`{"message":"Not Found"}`) and metmuseum.github.io/robots.txt is HTTP 404, for `*`, GPTBot, ChatGPT-User, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot and CCBot alike, so nothing is disallowed there. www.metmuseum.org (read in the cloud browser; curl gets an HTTP 429 Vercel Security Checkpoint challenge, `x-vercel-mitigated: challenge`, for every user agent) has `user-agent: *` disallowing only `/temp`, `/upload`, `/ghidorah`, `/style-guide`, `/style`, `/welcome`, plus `user-agent: Pinterest` with `Crawl-delay: 1`. No named AI-agent groups on any host. Terms (www.metmuseum.org/policies/terms-and-conditions, last updated October 25, 2018, read in full): Open Access (OA) materials are CC0, "for any purpose, including commercial and noncommercial use, free of charge and without requiring permission"; the API section says the API serves OA content under CC0, that the Museum logs IP addresses and usage, gives no availability guarantee, "may limit the number of transactions a user may send or receive through the API" and "may in the future require access through assigned keys". Non-OA site Materials are noncommercial, educational and personal use only. THE METROPOLITAN MUSEUM OF ART, MMA, "THE MET" logo and others are trademarks, and "the Trademarks may not be used in an URL"; the Open Access README says not to use the trademarks or imply endorsement. API docs (metmuseum.github.io): no registration or key, "Please limit request rate to 80 requests per second." No AI/ML or scraping clause. This skill reads data only from the API, uses no Met logo, and leaves hours and closures to the visitor.

## Quick summary

- **No scraping.** `GET https://collectionapi.metmuseum.org/public/collection/v1.1/search?title=true&q=<title>` and `...&artistOrCulture=true&q=<artist>` return object IDs; `GET /public/collection/v1/objects/<id>` returns the record, and its `GalleryNumber` answers the question (`""` = not on view). `Access-Control-Allow-Origin: *`, no key.
- **`/v1/search` is gone.** It answers HTTP 410 since 2026-10-01 with a JSON message pointing to `/v1.1/search`. `/v1.1/search` pages (`limit` default 100, max 500, `offset + limit` at most 10,000). Objects stay on `/v1/objects/<id>` (`/v1.1/objects/<id>` is HTTP 404).
- **Answer (2026-11-11):** Van Gogh's *Sunflowers* (1887, object 436524, accession 49.41) is on view in **Gallery 825**, European Paintings. The object page www.metmuseum.org/art/collection/search/436524 said the same: "On view at The Met Fifth Avenue in Gallery 825". It is the 1887 Paris canvas (43.2 x 61 cm); the page names related versions in Amsterdam (oil sketch, Van Gogh Museum), Bern and Otterlo.
- **On view is not "open".** On Wednesday 2026-11-11 the visit page said "The museum is closed today" (Wednesday: Closed; Sun to Tue and Thu 10 am to 5 pm; Fri and Sat 10 am to 9 pm). Gallery 825 was not on the gallery-closures list (last updated November 10). Check www.metmuseum.org/plan-your-visit before going.
- **Titles repeat.** `title=true&q=Washington Crossing the Delaware` matched 21 objects; two are titled exactly that by Leutze: the painting (on view, Gallery 760) and a lithograph (not on view). Always check title and artist on the record.
- **Rate limit:** docs ask for at most 80 requests per second; no rate-limit headers seen. Block 1 pauses 0.25 s per call.

## What works

### 1. Is it on view, and where? (browser, official API)

`on_docs_tab()` opens the API docs page (metmuseum.github.io) once and later calls reuse that tab; the API allows any origin, so `fetch()` works from there. `get_json()` returns parsed JSON on 200 (or on 404 where the caller says a 404 is an answer), backs off on 429/5xx and otherwise raises, so an error never looks like "not on view". The `isOnView=true` search is run as a cross-check on `GalleryNumber`. The last work is one that is not on view, to show that branch.

```python
import json, time

# (title, artist) pairs to check; the title is matched exactly (case-insensitive), the artist by substring.
WORKS = [
    ("Sunflowers", "van Gogh"),
    ("Irises", "van Gogh"),
    ("Washington Crossing the Delaware", "Leutze"),
    ("Road in Etten", "van Gogh"),
]
API = "https://collectionapi.metmuseum.org/public/collection/"
PAUSE = 0.25  # docs: limit request rate to 80 requests per second; this stays far below it

def on_docs_tab():
    """fetch() runs from a logged-out tab on the API docs page (metmuseum.github.io). The API sends
    Access-Control-Allow-Origin: *, so plain GETs work cross-origin. Reuse the tab if already there."""
    try:
        if js("location.origin") == "https://metmuseum.github.io":
            return
    except Exception:
        pass
    new_tab("https://metmuseum.github.io/")
    wait_for_load()
    if "Collection API" not in (js("document.title") or ""):
        raise RuntimeError(f"metmuseum.github.io did not serve the API docs (title {js('document.title')!r}): stop, do not retry around it")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__met = window.__met || {}; const id = String(Math.random()).slice(2); window.__met[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__met[id] = {status: r.status, text: await r.text()}; })
    .catch(e => { window.__met[id] = {status: 0, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__met[%s]; if (v) delete window.__met[%s]; return v; })()"""

def get_json(path, tries=3, timeout=60, ok=(200,)):
    """GET API+path from inside the tab -> (status, parsed JSON). Backs off on 429/5xx, otherwise raises,
    so an error never looks like 'not on view'. Pass ok=(200, 404) where a 404 is an expected answer."""
    for attempt in range(tries):
        rid = json.dumps(js(START_JS % json.dumps(API + path)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"{path}: no answer after {timeout}s")
            time.sleep(0.3)
        time.sleep(PAUSE)
        if r["status"] in ok:
            return r["status"], json.loads(r["text"])
        if r["status"] not in (0, 429, 500, 502, 503, 504) or attempt == tries - 1:
            raise RuntimeError(f"{path}: HTTP {r['status']} {' '.join(r['text'].split())[:200]!r}; stopping")
        time.sleep(30 if r["status"] == 429 else 5)

def ids(path):
    """All object IDs for a v1.1 search (pages of 500; offset+limit may not exceed 10,000)."""
    out, offset = [], 0
    while True:
        _, d = get_json(f"{path}&limit=500&offset={offset}")
        page = d["objectIDs"] or []  # null, not [], when nothing matches
        out += page
        offset += len(page)
        if d["total"] > 10000:  # the API serves at most 10,000 IDs per search, so an intersection could miss the work
            raise RuntimeError(f"{path}: {d['total']} matches, more than the 10,000 the search serves; the answer would be "
                               "incomplete. Use /v1/objects or the Open Access CSV for complete lists")
        if not page or offset >= d["total"]:
            return d["total"], out

def q(s):
    return js(f"encodeURIComponent({json.dumps(s)})")

on_docs_tab()
for title, artist in WORKS:
    # q= alone ranks the whole record; title=true / artistOrCulture=true restrict it to one field each.
    # The two flags cannot be combined (title=true&artistOrCulture=true&q=sunflowers -> 0), so intersect two searches.
    t_total, by_title = ids(f"v1.1/search?title=true&q={q(title)}")
    a_total, by_artist = ids(f"v1.1/search?artistOrCulture=true&q={q(artist)}")
    _, on_view = ids(f"v1.1/search?artistOrCulture=true&isOnView=true&q={q(artist)}")
    artist_ids = set(by_artist)
    both = [i for i in by_title if i in artist_ids]
    print(f"\n{title} ({artist}): title search {t_total}, artist search {a_total}, in both {len(both)}")
    found = 0
    for oid in both:
        status, o = get_json(f"v1/objects/{oid}", ok=(200, 404))
        if status == 404:  # search can return IDs the object endpoint rejects ("Not a valid object")
            print(f"  {oid}  skipped: object endpoint said {o.get('message')!r}")
            continue
        if o["title"].strip().lower() != title.lower() or artist.lower() not in o["artistDisplayName"].lower():
            continue
        found += 1
        g = o["GalleryNumber"]
        where = f"ON VIEW in Gallery {g}" if g else "not on view"
        print(f"  {o['objectID']}  {o['title']}, {o['objectDate']}  {o['artistDisplayName']} ({o['artistDisplayBio']})  [{o['accessionNumber']}]")
        print(f"    {where}  (isOnView=true search agrees: {(oid in on_view) == bool(g)})  {o['department']}, {o['medium']}")
        print(f"    metadata updated {o['metadataDate']}; public domain {o['isPublicDomain']}")
        print(f"    {o['objectURL']}")
    if not found:
        print("  no object with that exact title by that artist")
```

Output (from the run on 2026-11-11, 23:22 UTC):

```text

Sunflowers (van Gogh): title search 36, artist search 31, in both 1
  436524  Sunflowers, 1887  Vincent van Gogh (Dutch, Zundert 1853–1890 Auvers-sur-Oise)  [49.41]
    ON VIEW in Gallery 825  (isOnView=true search agrees: True)  European Paintings, Oil on canvas
    metadata updated 2026-11-06T04:53:14.23Z; public domain True
    https://www.metmuseum.org/art/collection/search/436524

Irises (van Gogh): title search 43, artist search 31, in both 1
  436528  Irises, 1890  Vincent van Gogh (Dutch, Zundert 1853–1890 Auvers-sur-Oise)  [58.187]
    ON VIEW in Gallery 099  (isOnView=true search agrees: True)  European Paintings, Oil on canvas
    metadata updated 2026-11-06T04:53:14.23Z; public domain True
    https://www.metmuseum.org/art/collection/search/436528

Washington Crossing the Delaware (Leutze): title search 21, artist search 10, in both 2
  11417  Washington Crossing the Delaware, 1851  Emanuel Leutze (American, Schwäbisch Gmünd 1816–1868 Washington, D.C.)  [97.34]
    ON VIEW in Gallery 760  (isOnView=true search agrees: True)  The American Wing, Oil on canvas
    metadata updated 2025-10-03T04:51:20.327Z; public domain True
    https://www.metmuseum.org/art/collection/search/11417
  894635  Washington Crossing the Delaware, ca. 1870  Emanuel Leutze (American, Schwäbisch Gmünd 1816–1868 Washington, D.C.)  [1980.1037]
    not on view  (isOnView=true search agrees: True)  Drawings and Prints, Hand-colored lithograph
    metadata updated 2025-06-27T04:50:31.807Z; public domain False
    https://www.metmuseum.org/art/collection/search/894635

Road in Etten (van Gogh): title search 102, artist search 31, in both 2
  459193  Road in Etten, 1881  Vincent van Gogh (Dutch, Zundert 1853–1890 Auvers-sur-Oise)  [1975.1.774]
    not on view  (isOnView=true search agrees: True)  Robert Lehman Collection, Chalk, pencil, pastel, watercolor.  Underdrawing in pen and brown ink.
    metadata updated 2025-01-29T04:54:03.16Z; public domain True
    https://www.metmuseum.org/art/collection/search/459193
  828389  skipped: object endpoint said 'Not a valid object'
```

### 2. Same answer with curl, filters and error shapes (no browser)

```bash
API=https://collectionapi.metmuseum.org/public/collection
# Filters narrow the match set: on view, European Paintings (departmentId 11), "sunflowers" anywhere in the record
curl -sS --fail -G "$API/v1.1/search" \
  --data-urlencode 'q=sunflowers' --data-urlencode 'isOnView=true' --data-urlencode 'departmentId=11' | python3 -c '
import json, sys; d = json.load(sys.stdin); print("on view, European Paintings, q=sunflowers:", d["total"], d["objectIDs"])'
sleep 1
curl -sS --fail "$API/v1/objects/436524" | python3 -c '
import json, sys; o = json.load(sys.stdin)
print("record:", {k: o[k] for k in ("objectID", "title", "artistDisplayName", "objectDate", "accessionNumber", "GalleryNumber", "isPublicDomain", "metadataDate")})'
sleep 1
for v in true True; do
  curl -sS --fail "$API/v1.1/search?q=sunflowers&isOnView=$v" | python3 -c "
import json, sys; print('isOnView=$v -> total', json.load(sys.stdin)['total'])"
  sleep 1
done
curl -sS --fail "$API/v1.1/search?q=zzzxqvnotathing" | python3 -c '
import json, sys; print("no match:", json.load(sys.stdin))'
sleep 1
curl -sS -w ' <- unknown id: HTTP %{http_code}\n' "$API/v1/objects/999999999"
sleep 1
curl -sS -o /dev/null -w 'old /v1/search: HTTP %{http_code}\n' "$API/v1/search?q=sunflowers"
```

Output (from the run on 2026-11-11, 23:23 UTC):

```text
on view, European Paintings, q=sunflowers: 3 [436524, 437112, 437115]
record: {'objectID': 436524, 'title': 'Sunflowers', 'artistDisplayName': 'Vincent van Gogh', 'objectDate': '1887', 'accessionNumber': '49.41', 'GalleryNumber': '825', 'isPublicDomain': True, 'metadataDate': '2026-11-06T04:53:14.23Z'}
isOnView=true -> total 18
isOnView=True -> total 178
no match: {'total': 0, 'objectIDs': None}
{"message":"ObjectID not found"}
 <- unknown id: HTTP 404
old /v1/search: HTTP 410
```

## Fields

| Field | Where | Notes |
|---|---|---|
| `total`, `objectIDs` | search | `total` is exact; `objectIDs` is `null` (not `[]`) when nothing matches or `offset` is past the end |
| `objectID` | object | stable numeric ID; page is `objectURL` = `https://www.metmuseum.org/art/collection/search/<id>` |
| `title`, `artistDisplayName`, `artistDisplayBio` | object | `Sunflowers`, `Vincent van Gogh`, `Dutch, Zundert 1853–1890 Auvers-sur-Oise` |
| `accessionNumber` | object | `49.41`; docs: "not always unique" |
| `GalleryNumber` | object | string: `"825"`, `"099"`; `""` when not on view |
| `department`, `medium`, `objectDate` | object | `European Paintings`, `Oil on canvas`, `1887` |
| `isPublicDomain`, `primaryImage` | object | image URLs are filled only for Open Access images |
| `metadataDate` | object | last metadata update (`2026-11-06T04:53:14.23Z` for 436524) |
| `isHighlight` | object | `false` for *Sunflowers*, `true` for *Wheat Field with Cypresses* (436535) |

## Gotchas

- **Boolean filters are case-sensitive and silently ignored when wrong.** `q=sunflowers&isOnView=true` gives total 18; `isOnView=True` and `isOnView=yes` give 178 (no filter), HTTP 200. Send lowercase `true`.
- **`title=true` and `artistOrCulture=true` cannot be combined** (`title=true&artistOrCulture=true&q=sunflowers` returned total 0). Block 1 runs both searches and intersects them.
- **`q=` alone is broad.** `q=sunflowers` matched 178 objects; `title=true` cut it to 36, of which 1 is by van Gogh.
- **Search can return IDs the object endpoint rejects.** 828389 came back in `artistOrCulture=true&q=van Gogh` (1 of 31 hits); `/v1/objects/828389` is HTTP 404 `{"message":"Not a valid object"}`. An unknown id is HTTP 404 `{"message":"ObjectID not found"}`.
- **Paging limits fail quietly.** `limit=600` returned 500 IDs; `limit=0`, `-1` or `abc` returned the default 100; `hasImages=true&offset=9999&limit=2` returned 1 ID and `offset=10000` returned `null`, all HTTP 200. Past 10,000 matches use `/v1/objects` or the Open Access CSV.
- **`GalleryNumber` and the `isOnView` search agreed** for all 30 readable van Gogh records (18 on view, 12 not), but the API has no gallery endpoint, floor or building field. *Irises* (436528) is in "Gallery 099"; the object page shows the same number.
- **HEAD is HTTP 405.** Use GET. CORS headers (`Access-Control-Allow-Origin: *`) come back when the request sends an `Origin`.
- **Tab marker.** The harness prefixes the tab title with a horse emoji; block 1 matches a substring of the title only.

## What does not work

- **`/public/collection/v1/search`:** HTTP 410 since 2026-10-01; switch the path to `/v1.1/search`.
- **Hours, closures, tickets from the API:** not in it. They are on www.metmuseum.org pages, which are not Open Access; read them yourself.
- **Not tested:** the Open Access CSV, `/v1/objects?metadataDate=` bulk sync, images, the departments filter beyond `departmentId=11`, rate-limit behavior near 80 requests per second (never provoked).
