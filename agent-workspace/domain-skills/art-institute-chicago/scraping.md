# Art Institute of Chicago - Is an Artwork On View Right Now, and in Which Gallery? (public API)

Field-tested against api.artic.edu on 2026-11-10 using a Browser Use cloud browser (logged out) plus `curl` from a laptop. 2 browser page loads (one artwork page, the API docs page), 22 in-page `fetch()` calls and about 20 curl calls, all serial at 1 s or more spacing: every call was HTTP 200 except the deliberate 404/403 probes below. No 429, no challenge, no key, no login.

robots.txt (checked 2026-11-10): api.artic.edu has `User-agent: *` with an empty `Disallow:` (all allowed); www.artic.edu `*` disallows only `/press/exhibition-press-room`, `/press/art-institute-images`, `/authors/57/james-rondeau`, `/artworks/recentlyViewed`, `/artworks/addRecentlyViewed`, `/ajaxData`, `/*/exploreFurther$`. No named AI-agent groups on either host. Terms (www.artic.edu/terms, read in full): data in AIC's Public API is CC0, usable "for any purpose, including commercial and noncommercial uses, without additional permission"; other site Materials are noncommercial-only, and the logo, lion statues and building are trademarks. Artwork responses: the `description` field is CC BY 4.0, everything else CC0 (`info.license_text`). The API docs ask you to "avoid extensive scraping of our API", to "throttle your requests to no more than one per second" if you do, and to send an `AIC-User-Agent` header with your project name and a contact email as a courtesy (the blocks send a project URL; put your own contact in it); anonymous users get 60 requests per minute. No AI/ML clause. This skill never requests `description` (CC BY: attribute it if you add it), uses no AIC logo, and reads data only from the API.

## Quick summary

- **No scraping.** `GET https://api.artic.edu/api/v1/artworks/search?q=<title artist>&fields=id,title,artist_title,artist_display,is_on_view,gallery_title,gallery_id&limit=10` finds the work; `is_on_view` and `gallery_title` answer the question. `Access-Control-Allow-Origin: *`, no key.
- **Then re-read the record:** `GET /api/v1/artworks/<id>?fields=...` (search hits come from an index copy; hit `timestamp`s were 2026-11-05/06 on 2026-11-10) and `GET /api/v1/galleries/<gallery_id>` for `floor`, `number`, `is_closed`.
- **Answer (2026-11-10):** Monet's *Water Lilies* (1906, id 16568, 1933.1157) is on view in **Gallery 243, floor 2** (Painting and Sculpture of Europe). The artwork page www.artic.edu/artworks/16568 said the same ("On View ... Gallery 243").
- **`q=` ranks, it does not filter.** `pagination.total` was 133165 (the whole collection) for all 6 `q` values tried. Match title and artist yourself (block 1) or send an Elasticsearch `query[...]` filter (block 2: 3 matches).
- **Titles repeat.** `q=water lilies` also returns *Water Lilies* by Jack Beal (id 93464, not on view). Always check the artist.
- **On view is not "open".** `is_on_view` means installed in a gallery. On Tuesday 2026-11-10 the site header read "Closed today, next open tomorrow." Check www.artic.edu/visit before going. The API's `/hours` endpoint exists but its `license_text` is noncommercial-only, so this skill does not use it.
- **Rate limit:** 60 requests per minute anonymous, `x-ratelimit-remaining` header on every response. Block 1 pauses 1 s per call.

## What works

### 1. Is it on view, and where? (browser, official API)

`on_api_tab()` opens the API docs page (api.artic.edu/docs/) once and later calls reuse that tab, so `fetch()` is same-origin. `get_json()` returns parsed JSON on 200, backs off on 429/5xx and otherwise raises, so an error never looks like "not on view". The last work is one that is off view on loan, to show that branch.

```python
import json, re, time

# (title, artist) pairs to check; the title is matched exactly (case-insensitive), the artist by substring.
WORKS = [
    ("Water Lilies", "Monet"),
    ("Nighthawks", "Hopper"),
    ("American Gothic", "Wood"),
    ("Arrival of the Normandy Train, Gare Saint-Lazare", "Monet"),
]
API = "https://api.artic.edu/api/v1/"
FIELDS = "id,title,artist_title,artist_display,date_display,main_reference_number,is_on_view,gallery_title,gallery_id,on_loan_display,updated_at,timestamp"
AIC_UA = "browser-harness domain skill (https://github.com/browser-use/browser-harness)"  # courtesy header the API docs ask for
PAUSE = 1.0  # docs: no more than one request per second; anonymous limit is 60 per minute

def on_api_tab():
    """fetch() runs same-origin from a logged-out api.artic.edu tab (the API docs page). Reuse it if already there."""
    try:
        if js("location.origin") == "https://api.artic.edu":
            return
    except Exception:
        pass
    new_tab("https://api.artic.edu/docs/")
    wait_for_load()
    if "Art Institute" not in (js("document.title") or ""):
        raise RuntimeError(f"api.artic.edu did not serve its docs (title {js('document.title')!r}): stop, do not retry around it")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__aic = window.__aic || {}; const id = String(Math.random()).slice(2); window.__aic[id] = null;
  fetch(%s, {credentials: 'omit', headers: {'AIC-User-Agent': %s}})
    .then(async r => { window.__aic[id] = {status: r.status, left: r.headers.get('x-ratelimit-remaining'), text: await r.text()}; })
    .catch(e => { window.__aic[id] = {status: 0, left: null, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__aic[%s]; if (v) delete window.__aic[%s]; return v; })()"""

def get_json(url, tries=3, timeout=60):
    """GET url from inside the tab -> parsed JSON. Backs off on 429/5xx, otherwise raises, so an error never looks like 'not found'."""
    for attempt in range(tries):
        rid = json.dumps(js(START_JS % (json.dumps(url), json.dumps(AIC_UA))))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"{url}: no answer after {timeout}s")
            time.sleep(0.3)
        time.sleep(PAUSE)
        if r["status"] == 200:
            get_json.left = r["left"]
            return json.loads(r["text"])
        if r["status"] not in (0, 429, 500, 502, 503, 504) or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {r['status']} {' '.join(r['text'].split())[:200]!r}; stopping")
        time.sleep(60 if r["status"] == 429 else 5)  # the anonymous limit is per minute; a dead tab or 5xx retries sooner

def q(s):
    return js(f"encodeURIComponent({json.dumps(s)})")

on_api_tab()
for title, artist in WORKS:
    s = get_json(API + f"artworks/search?q={q(title + ' ' + artist)}&fields={FIELDS}&limit=10")
    hits = [a for a in s["data"] if (a["title"] or "").strip().lower() == title.lower()
            and artist.lower() in (a["artist_title"] or a["artist_display"] or "").lower()]
    print(f"\n{title} ({artist}): search total {s['pagination']['total']}, exact title+artist matches in top 10: {len(hits)}")
    for h in hits:
        # The search index can lag; re-read the record itself for the current values.
        a = get_json(API + f"artworks/{h['id']}?fields={FIELDS}")["data"]
        where = "not on view"
        if a["is_on_view"]:
            g = get_json(API + f"galleries/{a['gallery_id']}?fields=id,title,number,floor,is_closed")["data"] if a["gallery_id"] else {}
            where = f"ON VIEW in {a['gallery_title']} (floor {g.get('floor')}, gallery is_closed={g.get('is_closed')})"
        print(f"  {a['id']}  {a['title']}, {a['date_display']}  {(a['artist_display'] or 'artist unknown').splitlines()[0]}  [{a['main_reference_number']}]")
        loan = re.sub(r"<[^>]+>", "", a["on_loan_display"] or "")  # HTML fragment
        print(f"    {where}" + (f"  loan: {loan}" if loan else ""))
        print(f"    record updated {a['updated_at']}; search index copy {h['timestamp']}, search said on_view={h['is_on_view']} {h['gallery_title']}")
        print(f"    https://www.artic.edu/artworks/{a['id']}")
print("\nrate limit left this minute:", get_json.left)
```

Output (from the run on 2026-11-10, 23:21 UTC):

```text

Water Lilies (Monet): search total 133165, exact title+artist matches in top 10: 1
  16568  Water Lilies, 1906  Claude Monet (French, 1840–1926)  [1933.1157]
    ON VIEW in Gallery 243 (floor 2, gallery is_closed=False)
    record updated 2026-11-03T15:15:09-06:00; search index copy 2026-11-05T22:20:21-06:00, search said on_view=True Gallery 243
    https://www.artic.edu/artworks/16568

Nighthawks (Hopper): search total 133165, exact title+artist matches in top 10: 1
  111628  Nighthawks, 1942  Edward Hopper (American, 1882–1967)  [1942.51]
    ON VIEW in Gallery 262 (floor 2, gallery is_closed=False)
    record updated 2026-10-22T16:24:57-05:00; search index copy 2026-11-05T23:39:12-06:00, search said on_view=True Gallery 262
    https://www.artic.edu/artworks/111628

American Gothic (Wood): search total 133165, exact title+artist matches in top 10: 1
  6565  American Gothic, 1930  Grant Wood (American, 1891–1942)  [1930.934]
    ON VIEW in Gallery 263 (floor 2, gallery is_closed=False)
    record updated 2026-10-22T21:41:21-05:00; search index copy 2026-11-05T22:13:37-06:00, search said on_view=True Gallery 263
    https://www.artic.edu/artworks/6565

Arrival of the Normandy Train, Gare Saint-Lazare (Monet): search total 133165, exact title+artist matches in top 10: 1
  16571  Arrival of the Normandy Train, Gare Saint-Lazare, 1877  Claude Monet (French, 1840–1926)  [1933.1158]
    not on view  loan: On loan to Nationalmuseum in Stockholm for To the Sea! Coastal Tourism and the Visual Arts
    record updated 2026-11-06T03:32:44-06:00; search index copy 2026-11-06T03:32:44-06:00, search said on_view=False None
    https://www.artic.edu/artworks/16571

rate limit left this minute: 48
```

### 2. Same answer with curl, filtered search (no browser)

`query[...]` takes an Elasticsearch query as GET parameters: `match_phrase` on `title` plus `match` on `artist_title` returns only real matches, so `pagination.total` is meaningful. The phrase match is stemmed ("water lilies" also hits "Water Lily Pond").

```bash
UA='AIC-User-Agent: browser-harness domain skill (https://github.com/browser-use/browser-harness)'
API=https://api.artic.edu/api/v1
# Elasticsearch filter instead of q=: only works whose title has the phrase AND whose artist matches
curl -sS --fail -G -H "$UA" "$API/artworks/search" \
  --data-urlencode 'query[bool][must][0][match_phrase][title]=water lilies' \
  --data-urlencode 'query[bool][must][1][match][artist_title]=monet' \
  --data-urlencode 'fields=id,title,artist_title,date_display,is_on_view,gallery_title,gallery_id' \
  --data-urlencode 'limit=20' | python3 -c '
import json, sys
d = json.load(sys.stdin)
print("matches:", d["pagination"]["total"], "| api version", d["info"]["version"])
for a in d["data"]:
    print(" ", a["id"], a["title"], a["date_display"], "|", a["artist_title"], "|",
          "on view, " + a["gallery_title"] if a["is_on_view"] else "not on view")
'
sleep 1
curl -sS --fail -H "$UA" "$API/artworks/16568?fields=id,title,is_on_view,gallery_title,gallery_id,on_loan_display,updated_at" | python3 -c '
import json, sys; a = json.load(sys.stdin)["data"]; print("record:", a)'
sleep 1
curl -sS --fail -H "$UA" "$API/galleries/2147479703?fields=title,number,floor,is_closed" | python3 -c '
import json, sys; print("gallery:", json.load(sys.stdin)["data"])'
sleep 1
curl -sS -o /dev/null -w 'unknown id: HTTP %{http_code}\n' -H "$UA" "$API/artworks/999999999"
sleep 1
curl -sS -o /dev/null -w 'limit=101: HTTP %{http_code}\n' -H "$UA" "$API/artworks/search?q=monet&fields=id&limit=101"
```

Output (from the run on 2026-11-10, 23:21 UTC):

```text
matches: 3 | api version 1.16
  16568 Water Lilies 1906 | Claude Monet | on view, Gallery 243
  87088 Water Lily Pond 1900 | Claude Monet | on view, Gallery 243
  97933 Water Lily Pond 1917–19 | Claude Monet | on view, Gallery 243
record: {'id': 16568, 'title': 'Water Lilies', 'is_on_view': True, 'on_loan_display': None, 'gallery_title': 'Gallery 243', 'gallery_id': 2147479703, 'updated_at': '2026-11-03T15:15:09-06:00'}
gallery: {'title': 'Gallery 243', 'is_closed': False, 'number': '243', 'floor': '2'}
unknown id: HTTP 404
limit=101: HTTP 403
```

## Fields

| Field | Where | Notes |
|---|---|---|
| `id` | artwork | stable numeric ID; page is `https://www.artic.edu/artworks/<id>` (redirects to `/artworks/<id>/<slug>`) |
| `title`, `artist_title`, `artist_display` | artwork | `artist_display` has nationality and dates on its first line (`Claude Monet (French, 1840–1926)`) |
| `main_reference_number` | artwork | accession number (`1933.1157`) |
| `is_on_view` | artwork | `true` = on display in a gallery; `false` with `gallery_title` and `gallery_id` `null` |
| `gallery_title`, `gallery_id` | artwork | `Gallery 243`, `2147479703`; feed `gallery_id` to `/galleries/<id>` |
| `on_loan_display` | artwork | HTML fragment when lent elsewhere (`<p>On loan to Nationalmuseum in Stockholm for <i>To the Sea! ...</i></p>`); `null` otherwise |
| `updated_at`, `timestamp` | artwork | record update time; `timestamp` is when that copy was indexed (search hits can lag the record) |
| `floor`, `number`, `is_closed` | gallery | `"2"`, `"243"`, `false`; strings, not ints |
| `_score` | search hit | relevance only |
| `description` | artwork | CC BY 4.0, not CC0; not requested here |
| `info.license_text`, `info.version` | every response | license per endpoint; API version `1.16` on 2026-11-10 |

## Gotchas

- **`q=` matches everything.** Total 133165 for `q=monet`, `q=Water Lilies Monet` and `q=Nighthawks Hopper` alike. Only the ranking changes; filter the hits.
- **Unknown `fields` names are silently dropped** (`fields=id,bogus_field` returned only `id`, HTTP 200). Check the key exists before trusting a missing value.
- **Errors are JSON with a status field:** unknown id is HTTP 404 `{"status":404,"error":"Not found",...}`; `limit=101` is HTTP 403 `Invalid limit`; `page=1001&limit=10` is HTTP 403 `Invalid number of results` (search cannot page past 10,000 results).
- **Same-origin tab.** `AIC-User-Agent` is not a CORS-safelisted header, so from another origin the fetch would need a preflight (not tested); block 1 fetches from an api.artic.edu tab, which is same-origin.
- **Tab marker.** The harness prefixes the tab title with a horse emoji; block 1 matches a substring of the title only.

## What does not work

- **Museum hours from this skill:** `/api/v1/hours` data is marked noncommercial-only in its own `license_text`; read www.artic.edu/visit yourself instead.
- **Images and descriptions:** not needed for this task. Images come from IIIF (`https://www.artic.edu/iiif/2/<image_id>/full/843,/0/default.jpg`) and carry their own licensing; the `description` text is CC BY 4.0.
- **Not tested:** bulk export / data dumps, `/exhibitions` (temporary shows), `/tours`, paging deep into search, rate-limit behavior past 60 per minute (never provoked).
