# Discogs - Release, Master and Artist Data

Field-tested against api.discogs.com and www.discogs.com on 2026-11-01 using a Browser Use cloud browser, logged out, plus plain HTTP to the API. No token, no login, no challenge on any API call or release page.

robots.txt (checked 2026-11-01, `User-agent: *` on www.discogs.com and api.discogs.com) disallows `*/release/add`, `/release/edit`, `/release/copy`, `/release/recs`, `/release/stats/`, `/master/stats/`, `/artist2`, `/users/` and more, and has no rule matching `/release/<id>`, `/master/<id>`, `/artist/<id>` or the API's `/releases/<id>`, `/masters/<id>`, `/artists/<id>`; block 1 checks every API path against api.discogs.com/robots.txt, block 2 checks every page path and its redirect target against www.discogs.com/robots.txt.

## Quick summary

- **Use the official API first:** `https://api.discogs.com/releases/<id>`, `/masters/<id>`, `/masters/<id>/versions`, `/artists/<id>`, `/artists/<id>/releases`. JSON, no key. One release call has tracklist, labels + catalog numbers, formats, year, country, genres, styles, barcodes, master id and community stats.
- Unauthenticated limit is **25 requests per minute** (`X-Discogs-Ratelimit: 25` on every response). Block 1 spaces calls 2.5 s apart, waits once on 429, and raises on anything else.
- Send a User-Agent that names your client. Block 1 sends `browser-harness-discogs-skill/1.0 Python-urllib/3.x`, a truthful client string, and got HTTP 200 on every call.
- **Fallback:** `www.discogs.com/release/<id>` server-renders the same data into `window.__APOLLO_CLIENT__.cache` plus a `MusicRelease` JSON-LD block. Block 2 reads both in one `js()` call; its output matched the API field for field on both test releases.
- Plain HTTP to `www.discogs.com` from a non-browser client got a Cloudflare "Just a moment..." page (HTTP 403, even for robots.txt). In the cloud browser every www page loaded. Use the browser for the fallback; the API needs no browser.

## What works

### 1. Official API: releases, master versions, artist discography (plain HTTP)

```python
import json, re, sys, time, urllib.error, urllib.parse, urllib.request

API = "https://api.discogs.com"
UA = f"browser-harness-discogs-skill/1.0 Python-urllib/{sys.version_info.major}.{sys.version_info.minor}"  # truthful, names the client
PACE_S = 2.5     # unauthenticated limit is 25 requests/min (X-Discogs-Ratelimit: 25)

def _robots_rules(base):
    """Rules of the `User-agent: *` group, Google-style wildcards."""
    txt = urllib.request.urlopen(urllib.request.Request(base + "/robots.txt", headers={"User-Agent": UA}), timeout=20).read().decode()
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

RULES = _robots_rules(API)

def robots_allowed(path):
    best, ok = -1, True
    for allow, pat in RULES:
        rx = re.escape(pat.rstrip("$")).replace(r"\*", ".*") + ("$" if pat.endswith("$") else "")
        if re.match(rx, path) and (len(pat) > best or (len(pat) == best and allow)):
            best, ok = len(pat), allow
    return ok

_last = [0.0]

def api(path, **params):
    """GET an api.discogs.com JSON resource. None on 404; one 60 s wait on 429, then raise."""
    if not robots_allowed(path):
        raise PermissionError(f"robots.txt disallows {path}")
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    for attempt in range(2):
        time.sleep(max(0.0, _last[0] + PACE_S - time.time()))
        _last[0] = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/vnd.discogs.v2.discogs+json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                if r.headers.get("X-Discogs-Ratelimit-Remaining") == "0":
                    _last[0] = time.time() + 60   # window used up: next call waits a minute
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 429 and attempt == 0:
                time.sleep(60)   # per-minute limit: wait one minute, once
                continue
            raise RuntimeError(f"{url}: HTTP {e.code} {e.read()[:200]!r}; stop, do not retry around it") from e

def tracks(tl):
    """Flatten a tracklist: headings kept as rows, index tracks expanded into their sub_tracks."""
    out = []
    for t in tl or []:
        row = {"pos": t.get("position"), "type": t.get("type_"), "title": t.get("title"), "duration": t.get("duration") or None}
        out.append(row)
        for s in t.get("sub_tracks") or []:
            out.append({"pos": s.get("position"), "type": "sub_track", "title": s.get("title"), "duration": s.get("duration") or None})
    return out

def artist_credit(artists):
    """'A & B', 'A Feat. B', 'A, B': name variation if credited, Discogs' ' (2)' disambiguator dropped."""
    s = ""
    for a in artists or []:
        j = (a.get("join") or "").strip()
        s += re.sub(r" \(\d+\)$", "", a.get("anv") or a["name"]) + ("," if j == "," else f" {j}" if j else "") + " "
    return s.strip()

def release(rid):
    d = api(f"/releases/{int(rid)}")
    if d is None:
        return None
    return {
        "id": d["id"], "artist": artist_credit(d.get("artists")), "title": d.get("title"),
        "year": d.get("year") or None, "released": d.get("released"), "country": d.get("country"),
        "labels": [(l.get("name"), l.get("catno"), l.get("id")) for l in d.get("labels") or []],
        "formats": [{"name": f.get("name"), "qty": f.get("qty"), "descriptions": f.get("descriptions") or [], "text": f.get("text")} for f in d.get("formats") or []],
        "genres": d.get("genres") or [], "styles": d.get("styles") or [],
        "tracklist": tracks(d.get("tracklist")),
        "master_id": d.get("master_id"),
        "barcodes": [i["value"] for i in d.get("identifiers") or [] if i.get("type") == "Barcode"],
        "have": (d.get("community") or {}).get("have"), "want": (d.get("community") or {}).get("want"),
        "rating": ((d.get("community") or {}).get("rating") or {}).get("average"),
        "num_for_sale": d.get("num_for_sale"), "lowest_price": d.get("lowest_price"),
        "url": d.get("uri"),
    }

def paged(path, key, max_pages=3, per_page=100, **params):
    """Collect a paginated list: (items, total, status), status = complete | truncated_max_pages | not_found."""
    items, page = [], 1
    while True:
        d = api(path, page=page, per_page=per_page, **params)
        if d is None:
            return None, 0, "not_found"
        items += d.get(key) or []
        pg = d["pagination"]
        if page >= pg["pages"]:
            return items, pg["items"], "complete"
        if page >= max_pages:
            return items, pg["items"], "truncated_max_pages"
        page += 1

# 1. Releases: a 7" single, a 13-disc box set with headings and index tracks, a missing id
for rid in (249504, 10398494, 999999999):
    r = release(rid)
    if r is None:
        print(rid, "-> None (404, no such release)")
        continue
    tl = r.pop("tracklist")
    print(json.dumps(r, ensure_ascii=False))
    print("   tracklist:", len(tl), "rows;", {t: sum(1 for x in tl if x["type"] == t) for t in ("heading", "track", "index", "sub_track")})
    for t in tl[:3] + [x for x in tl if x["type"] == "index"][:1]:
        print("   ", t)

# 2. Master: canonical year, main release, every version (pressing)
m = api("/masters/96559")
print("master", m["id"], m["title"], m["year"], "main_release", m["main_release"], "tracks", len(m["tracklist"]))
vers, total, status = paged("/masters/96559/versions", "versions", max_pages=2)
print("versions:", len(vers), "of", total, status)
for v in sorted(vers, key=lambda v: (v.get("released") if v.get("released") not in (None, "", "0") else "9999", v["id"]))[:3]:
    print("   ", v["id"], v["released"], v["country"], v["label"], v["catno"], v["format"], v["major_formats"])

# 3. Artist and discography (role Main, masters collapse their versions)
a = api("/artists/72872")
print("artist", a["id"], a["name"], "| realname", a.get("realname"), "| aliases", [x["name"] for x in a.get("aliases") or []][:3], "| urls", len(a.get("urls") or []))
rels, total, status = paged("/artists/72872/releases", "releases", max_pages=2, sort="year", sort_order="asc")
print("artist releases:", len(rels), "of", total, status)
main = [x for x in rels if x.get("role") == "Main"]
for x in main[:4]:
    print("   ", x["type"], x["id"], x.get("year"), x["title"], "|", x.get("format"), "|", x.get("label"))

# 4. robots guard
print("/users/x allowed?", robots_allowed("/users/x"), "| /releases/1 allowed?", robots_allowed("/releases/1"))
```

Output observed on 2026-11-01:

```text
{"id": 249504, "artist": "Rick Astley", "title": "Never Gonna Give You Up", "year": 1987, "released": "1987-07-00", "country": "UK", "labels": [["RCA", "PB 41447", 895]], "formats": [{"name": "Vinyl", "qty": "1", "descriptions": ["7\"", "45 RPM", "Single", "Stereo"], "text": null}], "genres": ["Electronic", "Pop"], "styles": ["Euro-Disco"], "master_id": 96559, "barcodes": ["5012394144777"], "have": 4159, "want": 594, "rating": 3.88, "num_for_sale": 124, "lowest_price": 0.67, "url": "https://www.discogs.com/release/249504-Rick-Astley-Never-Gonna-Give-You-Up"}
   tracklist: 2 rows; {'heading': 0, 'track': 2, 'index': 0, 'sub_track': 0}
    {'pos': 'A', 'type': 'track', 'title': 'Never Gonna Give You Up', 'duration': '3:32'}
    {'pos': 'B', 'type': 'track', 'title': 'Never Gonna Give You Up (Instrumental)', 'duration': '3:30'}
{"id": 10398494, "artist": "Pink Floyd", "title": "Pink Floyd", "year": 1988, "released": "1988", "country": "Australia", "labels": [["EMI", "PFB1", 26126]], "formats": [{"name": "Vinyl", "qty": "12", "descriptions": ["LP"], "text": null}, {"name": "Box Set", "qty": "1", "descriptions": ["Compilation", "Limited Edition"], "text": null}], "genres": ["Rock"], "styles": ["Psychedelic Rock", "Prog Rock"], "master_id": 586673, "barcodes": [], "have": 414, "want": 388, "rating": 4.66, "num_for_sale": 2, "lowest_price": 600.0, "url": "https://www.discogs.com/release/10398494-Pink-Floyd-Pink-Floyd"}
   tracklist: 111 rows; {'heading': 10, 'track': 90, 'index': 2, 'sub_track': 9}
    {'pos': '', 'type': 'heading', 'title': 'A Nice Pair', 'duration': None}
    {'pos': 'A1', 'type': 'track', 'title': 'Astonomy Dominé', 'duration': None}
    {'pos': 'A2', 'type': 'track', 'title': 'Lucifer Sam', 'duration': None}
    {'pos': '', 'type': 'index', 'title': 'Atom Heart Mother', 'duration': None}
999999999 -> None (404, no such release)
master 96559 Never Gonna Give You Up 1987 main_release 221824 tracks 3
versions: 67 of 67 complete
    182213 1987 US RCA Victor 6784-1-RD 12", 33 ⅓ RPM, Maxi-Single ['Vinyl']
    221824 1987 UK RCA PT 41448 12", 45 RPM, Single ['Vinyl']
    249504 1987 UK RCA PB 41447 7", 45 RPM, Single, Stereo ['Vinyl']
artist 72872 Rick Astley | realname Richard Paul Astley | aliases ['Dick Spatsley'] | urls 7
artist releases: 200 of 2824 truncated_max_pages
    release 3686862 1987 I Surrender (To The Spirit Of The Night) / Never Gonna Give You Up | 7", Jukebox | Jive, RCA
    release 5740035 1987 Beethoven (I Love To Listen To) / Whenever You Need Somebody | 7", Jukebox | RCA
    master 96554 1987 It Would Take A Strong Strong Man | None | None
    master 96559 1987 Never Gonna Give You Up | None | None
/users/x allowed? False | /releases/1 allowed? True
```

`truncated_max_pages` is expected: `max_pages=2` stopped at 200 of 2,824 artist releases.

### 2. Release page fallback (browser, reads the page's own state)

```python
import json, re, time

WWW = "https://www.discogs.com"
PAGE_GAP_S = 5   # robots.txt sets no Crawl-delay for *; stay well under human browsing speed

def robots_rules_from_tab():
    """Read www.discogs.com/robots.txt in the browser (plain HTTP to www can get a Cloudflare challenge)."""
    goto_url(WWW + "/robots.txt")
    wait_for_load()
    txt = js("document.body ? document.body.innerText : ''") or ""
    if "User-agent" not in txt:
        raise SystemExit(f"robots.txt did not load ({js('document.title')!r}): stop, do not retry around it")
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

def robots_allowed(rules, path):
    best, ok = -1, True
    for allow, pat in rules:
        rx = re.escape(pat.rstrip("$")).replace(r"\*", ".*") + ("$" if pat.endswith("$") else "")
        if re.match(rx, path) and (len(pat) > best or (len(pat) == best and allow)):
            best, ok = len(pat), allow
    return ok

EXTRACT = r"""((id) => {
  const c = window.__APOLLO_CLIENT__ && window.__APOLLO_CLIENT__.cache.extract();
  const r = c && c[`Release:{"discogsId":${id}}`];
  if (!r || !r.tracks) return null;
  const d = x => (x && x.__ref ? c[x.__ref] : x) || {};
  const ld = [...document.querySelectorAll('script[type="application/ld+json"]')]
    .map(s => { try { return JSON.parse(s.textContent); } catch (e) { return {}; } })
    .find(j => [].concat(j['@type']).includes('MusicRelease')) || {};
  const tr = t => ({pos: t.position || '', type: (t.trackType || '').toLowerCase(), title: t.title,
                    seconds: t.durationInSeconds});
  const rows = [];
  for (const t of r.tracks.map(d)) {
    rows.push(tr(t));
    for (const s of (t.subTracks || []).map(d)) rows.push({...tr(s), type: 'sub_track'});
  }
  return {
    id, title: r.title,
    artists: (r.primaryArtists || []).map(p => [p.displayName, p.joiningText || '', d(p.artist).discogsId]),
    year: ld.datePublished || null, released: r.released, country: r.country,
    labels: (r.labels || []).filter(l => l.labelRole === 'LABEL').map(l => [l.displayName, l.catalogNumber, d(l.label).discogsId]),
    formats: (r.formats || []).map(f => ({name: f.name, qty: f.quantity, descriptions: f.description || [], text: f.text})),
    genres: r.genres || [], styles: r.styles || [],
    master_id: r.masterRelease ? d(r.masterRelease).discogsId : null,
    barcodes: (r.barcodes || []).filter(b => b.type === 'BARCODE').map(b => b.value),
    have: r.inCollectionCount, want: r.inWantlistCount,
    rating: (ld.aggregateRating || {}).ratingValue ?? null,
    url: location.origin + r.siteUrl, tracklist: rows,
  };
})"""

def release_page(rules, rid, timeout=30):
    """Release data from the page's own state (Apollo cache + JSON-LD). None on the site's 404 page."""
    path = f"/release/{int(rid)}"
    if not robots_allowed(rules, path):
        raise PermissionError(f"robots.txt disallows {path}")
    goto_url(WWW + path)
    wait_for_load()
    deadline = time.time() + timeout
    while time.time() < deadline:
        href, title, body = js("[location.href, document.title, document.body ? document.body.innerText.slice(0, 300) : '']")
        low = (title + " " + body).lower()
        if any(s in low for s in ("just a moment", "verify you are human", "access denied", "attention required")):
            raise SystemExit(f"challenge on {href}: stop and back off, do not retry")
        final = re.sub(r"^https://www\.discogs\.com", "", href)
        if not robots_allowed(rules, final):
            raise PermissionError(f"{path} redirected to disallowed {final}")
        if re.search(rf"/release/{int(rid)}(?!\d)", href):
            data = js(f"{EXTRACT}({int(rid)})")
            if data:
                return data
            if body.lstrip().startswith("Error 404"):
                return None
        time.sleep(0.5)
    raise RuntimeError(f"no release state for {rid} within {timeout} s: {page_info()}")

tab = cdp("Target.createTarget", url="about:blank", background=True)["targetId"]
switch_tab(tab)
try:
    rules = robots_rules_from_tab()
    print("robots: /release/249504", robots_allowed(rules, "/release/249504"),
          "| /release/add", robots_allowed(rules, "/release/add"),
          "| /release/stats/249504", robots_allowed(rules, "/release/stats/249504"),
          "| /artist2", robots_allowed(rules, "/artist2"))
    for rid in (249504, 10398494, 999999999):
        time.sleep(PAGE_GAP_S)
        r = release_page(rules, rid)
        if r is None:
            print(rid, "-> None (site 404 page)")
            continue
        tl = r.pop("tracklist")
        print(json.dumps(r, ensure_ascii=False))
        print("   tracklist:", len(tl), "rows;", {t: sum(1 for x in tl if x["type"] == t) for t in ("heading", "track", "index", "sub_track")})
        for t in tl[:3] + [x for x in tl if x["type"] == "index"][:1]:
            print("   ", t)
finally:
    close_tab(tab)
```

Output observed on 2026-11-01:

```text
robots: /release/249504 True | /release/add False | /release/stats/249504 False | /artist2 False
{"id": 249504, "title": "Never Gonna Give You Up", "artists": [["Rick Astley", "", 72872]], "year": 1987, "released": "1987-07-00", "country": "UK", "labels": [["RCA", "PB 41447", 895]], "formats": [{"name": "Vinyl", "qty": "1", "descriptions": ["7\"", "45 RPM", "Single", "Stereo"], "text": null}], "genres": ["Electronic", "Pop"], "styles": ["Euro-Disco"], "master_id": 96559, "barcodes": ["5012394144777"], "have": 4159, "want": 594, "rating": 3.88, "url": "https://www.discogs.com/release/249504-Rick-Astley-Never-Gonna-Give-You-Up"}
   tracklist: 2 rows; {'heading': 0, 'track': 2, 'index': 0, 'sub_track': 0}
    {'pos': 'A', 'type': 'track', 'title': 'Never Gonna Give You Up', 'seconds': 212}
    {'pos': 'B', 'type': 'track', 'title': 'Never Gonna Give You Up (Instrumental)', 'seconds': 210}
{"id": 10398494, "title": "Pink Floyd", "artists": [["Pink Floyd", "", 45467]], "year": 1988, "released": "1988", "country": "Australia", "labels": [["EMI", "PFB1", 26126]], "formats": [{"name": "Vinyl", "qty": "12", "descriptions": ["LP"], "text": null}, {"name": "Box Set", "qty": "1", "descriptions": ["Compilation", "Limited Edition"], "text": null}], "genres": ["Rock"], "styles": ["Psychedelic Rock", "Prog Rock"], "master_id": 586673, "barcodes": [], "have": 414, "want": 385, "rating": 4.66, "url": "https://www.discogs.com/release/10398494-Pink-Floyd-Pink-Floyd"}
   tracklist: 111 rows; {'heading': 10, 'track': 90, 'index': 2, 'sub_track': 9}
    {'pos': '', 'type': 'heading', 'title': 'A Nice Pair', 'seconds': None}
    {'pos': 'A1', 'type': 'track', 'title': 'Astonomy Dominé', 'seconds': None}
    {'pos': 'A2', 'type': 'track', 'title': 'Lucifer Sam', 'seconds': None}
    {'pos': '', 'type': 'index', 'title': 'Atom Heart Mother', 'seconds': None}
999999999 -> None (site 404 page)
```

## URL patterns (all observed)

| URL | Result |
|---|---|
| `api.discogs.com/releases/<id>` | full release JSON; HTTP 404 `{"message": "That release does not exist or may have been deleted."}` for a missing id |
| `api.discogs.com/masters/<id>` | master: canonical `year`, `main_release`, `most_recent_release`, master tracklist |
| `api.discogs.com/masters/<id>/versions?page=N&per_page=100` | every pressing: `id, released, country, label, catno, format, major_formats`; `per_page=500` is clamped to 100 |
| `api.discogs.com/artists/<id>` | `name, realname, profile, aliases, namevariations, urls, members/groups` |
| `api.discogs.com/artists/<id>/releases?sort=year&sort_order=asc&page=N&per_page=100` | discography rows, `type` = `master` or `release`, `role` = `Main`, `Appearance`, `TrackAppearance`, `UnofficialRelease`... |
| `www.discogs.com/release/<id>` | redirects to `/release/<id>-<Artist>-<Title>?redirected=true`; the site's 404 page (HTTP 404, "Error 404") for a missing id |
| `www.discogs.com/master/<id>`, `/artist/<id>` | same redirect; Apollo cache has `MasterRelease:{...}` / `Artist:{...}` entries; not used by block 2 |

## Fields

Block 1 `release()` and block 2 `release_page()` return the same keys, except where noted:

| Key | API source | Page source (Apollo `Release:{"discogsId":<id>}`) |
|---|---|---|
| `artist` / `artists` | `artists[]` (`name`, `anv`, `join`) joined into one credit | `primaryArtists[]` as `[name, joiningText, artist id]` |
| `title`, `country`, `released`, `genres`, `styles` | same names | same names; `released` is `"1987-07-00"` style on both (`00` = unknown day) |
| `year` | `year` (0 when unknown, returned as `None`) | JSON-LD `datePublished` |
| `labels` | `labels[]` as `[name, catno, id]` | `labels[]` with `labelRole == "LABEL"`; other roles (`DISTRIBUTED_BY`, `PRESSED_BY`...) are the "Companies, etc." section |
| `formats` | `formats[]` `name, qty, descriptions, text` | `formats[]` `name, quantity, description, text` |
| `tracklist` | `tracklist[]` `position, type_, title, duration` (`"3:32"`), `sub_tracks[]` | `tracks[]` -> `Track` refs: `position, trackType, title, durationInSeconds`, `subTracks[]` |
| `master_id` | `master_id` | `masterRelease` ref |
| `barcodes` | `identifiers[]` with `type == "Barcode"` | `barcodes[]` with `type == "BARCODE"` |
| `have`, `want`, `rating` | `community.have/want/rating.average` | `inCollectionCount`, `inWantlistCount`, JSON-LD `aggregateRating.ratingValue` |
| `num_for_sale`, `lowest_price` | API only | not in block 2 (JSON-LD `offers` has `offerCount`, `lowPrice`) |

Tracklist rows: `type` is `track`, `heading` (a disc or side title with empty position), `index` (a suite whose parts follow as `sub_track` rows). The API has more on a release: `extraartists` (credits), `companies`, `notes`, `identifiers` (matrix/runout, label code), `images`, `videos`, `series`.

## Gotchas

- 25 requests/min unauthenticated (`X-Discogs-Ratelimit`, with `-Used` and `-Remaining` on each response). Do not run parallel workers against it. This skill uses no token.
- Discogs appends ` (2)`, ` (3)` to disambiguate same-named artists (`Rick Astley (2)`); `artist_credit()` drops that suffix for display. Keep the artist `id` for identity.
- `released` in versions is `"0"` when unknown (one of the 67 versions of master 96559); block 1 sorts those last. Versions with the same `released` value came back in a different API order across runs, so block 1 breaks ties on `id`.
- `year` on a master is the first-release year; on a release it is that pressing's year. Use the master for "original year".
- Artist discography rows of `type: "master"` have no `format` or `label`; follow `/masters/<id>/versions` for those.
- Community counts can differ by a few between the API and the page (`want` 388 vs 385 for 10398494 in the same hour); they are cached separately.
- `api.discogs.com/database/search?q=...` answered HTTP 200 without a token on 2026-11-01 (59,015 items for "never gonna", pages capped at 200). Do not build on it without a token: block 1 does not use it.
- In-page `fetch("https://api.discogs.com/...")` from a www.discogs.com tab worked (CORS, HTTP 200), but the rate-limit headers are not readable cross-origin. Prefer block 1.
- The release page shows a cookie consent banner; it does not block reading the state, so block 2 never clicks it.

## What does not work

- Plain HTTP to `www.discogs.com` (`/robots.txt` and `/release/249504` with curl): Cloudflare managed challenge, HTTP 403. Do not try to get past it; use the API, or block 2 in a real browser, and stop if the browser also sees a challenge.
- `/release/stats/`, `/master/stats/`, `/release/recs`, `/artist2`, `/users/` and edit/add/copy URLs: disallowed by robots.txt, never requested.
- Full discographies in one call: `/artists/<id>/releases` pages 100 rows at a time (2,824 rows = 29 pages for Rick Astley, about 70 s at the unauthenticated pace).
