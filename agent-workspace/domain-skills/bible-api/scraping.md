# bible-api.com - Look Up Bible Verses in the KJV and the World English Bible (official JSON API)

Field-tested against bible-api.com on 2026-11-10 using a Browser Use cloud browser (logged out) plus `curl` from a laptop. 2 page loads and 9 in-page `fetch()` calls in the browser, 14 curl calls, all serial at 2.5 s or more spacing: every verse call was HTTP 200, the non-200s were the deliberate 404 probes below and robots.txt. No 429, no challenge, no key, no login.

robots.txt (checked 2026-11-10): https://bible-api.com/robots.txt is HTTP 404 `{"error":"not found"}` (no rules, no named AI-agent groups). Terms: the home page "Terms of Use" says "This service is free for anyone to use as long as you don't abuse my server. This service is rate limited to 15 requests every 30 seconds (based on IP address)... Do not use this API to download an entire bible"; no AI, agent, scraping, key or non-commercial clause. Code is MIT (github.com/seven1m/bible_api); translations served are public domain or freely licensed. This skill asks for single verses only.

## Quick summary

- **No scraping.** `GET https://bible-api.com/<book>+<chapter>:<verse>?translation=kjv|web` returns JSON: `reference`, `verses[]`, `text`, `translation_id`, `translation_name`, `translation_note`. CORS `*`, no key.
- **Default translation is `web`** (World English Bible). Always pass `translation=` so the answer says which one you quoted.
- **Rate limit: 15 requests every 30 s per IP** (Terms of Use). The blocks pace 2.5 s per call, serial. Never pull whole books or bibles: the terms say they will likely block you; the data is on GitHub.
- **References are free text:** `romans+8:28`, `rom+8:28`, `john%203:16` all work; `reference` in the answer is the normalized form (`Romans 8:28`).
- **Errors:** an unknown book or verse is HTTP 404 JSON `{"error":"not found"}`; an unknown translation id (`niv`) is an nginx **HTML** 404 page. Check the content type.
- **KJV text has hard line breaks** mid-sentence (`...according to\nhis purpose.`). Collapse whitespace before quoting.

## What works

### 1. Quote Romans 8:28 and John 3:16 in the KJV and the WEB (browser)

`on_site()` opens the home page once and later calls reuse that tab; `fetch()` there is same-origin. `verse()` returns parsed JSON on 200, waits 30 s once on 429/5xx and otherwise raises, so a 404 never looks like an empty passage.

```python
import json, time, urllib.parse

REFS = ["Romans 8:28", "John 3:16"]  # single verses only; never request whole books
TRANSLATIONS = ["kjv", "web"]        # King James Version, World English Bible (both Public Domain)

SITE = "https://bible-api.com/"
PAUSE = 2.5  # Terms of Use: 15 requests every 30 s per IP; keep calls serial

def on_site():
    """fetch() runs from a logged-out bible-api.com tab (the docs home page). Reuse the tab if already there."""
    try:
        if js("location.origin") == SITE.rstrip("/"):
            return
    except Exception:
        pass
    new_tab(SITE)
    wait_for_load()
    if "bible-api.com" not in (js("document.title") or ""):
        raise RuntimeError(f"bible-api.com did not serve its home page (title {js('document.title')!r}): stop, do not retry around it")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__bib = window.__bib || {}; const id = String(Math.random()).slice(2); window.__bib[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__bib[id] = {status: r.status, type: r.headers.get('content-type'), text: await r.text()}; })
    .catch(e => { window.__bib[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__bib[%s]; if (v) delete window.__bib[%s]; return v; })()"""

def verse(ref, translation, timeout=30):
    """One reference -> parsed JSON. 404 {"error":"not found"} = no such verse; an HTML 404 = unknown translation id.
    Waits 30 s once on 429/5xx, raises on anything else, so a failure never looks like an empty passage."""
    url = SITE + urllib.parse.quote(ref.lower()) + "?translation=" + translation
    for attempt in range(2):
        rid = json.dumps(js(START_JS % json.dumps(url)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"{url}: no answer after {timeout}s")
            time.sleep(0.3)
        time.sleep(PAUSE)
        if r["status"] == 200 and "json" in (r["type"] or ""):
            return json.loads(r["text"])
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(30)
            continue
        raise RuntimeError(f"{url}: HTTP {r['status']} {' '.join(r['text'].split())[:120]!r}; stopping")

on_site()
for ref in REFS:
    print(ref)
    for tr in TRANSLATIONS:
        d = verse(ref, tr)
        if len(d["verses"]) != 1:  # one verse asked, one verse back
            raise RuntimeError(f"{ref} ({tr}): expected 1 verse, got {len(d['verses'])} ({d['reference']})")
        text = " ".join(d["text"].split())  # KJV text carries hard line breaks mid-sentence
        print(f'  {d["translation_name"]} ({d["translation_id"]}, {d["translation_note"]}): "{text}" ({d["reference"]})')
```

Output (from the run on 2026-11-10):

```text
Romans 8:28
  King James Version (kjv, Public Domain): "And we know that all things work together for good to them that love God, to them who are the called according to his purpose." (Romans 8:28)
  World English Bible (web, Public Domain): "We know that all things work together for good for those who love God, to those who are called according to his purpose." (Romans 8:28)
John 3:16
  King James Version (kjv, Public Domain): "For God so loved the world, that he gave his only begotten Son, that whosoever believeth in him should not perish, but have everlasting life." (John 3:16)
  World English Bible (web, Public Domain): "For God so loved the world, that he gave his one and only Son, that whoever believes in him should not perish, but have eternal life." (John 3:16)
```

### 2. Terms, robots.txt, translation ids and error shapes (browser)

Reads the Terms of Use from the home page, then makes 5 small calls: robots.txt, the translation list (`/data`), and three deliberate 404s.

```python
import json, time

SITE = "https://bible-api.com/"

def on_site():
    try:
        if js("location.origin") == SITE.rstrip("/"):
            return
    except Exception:
        pass
    new_tab(SITE)
    wait_for_load()
    if "bible-api.com" not in (js("document.title") or ""):
        raise RuntimeError(f"bible-api.com did not serve its home page (title {js('document.title')!r}): stop")

START_JS = """(() => { window.__bib = window.__bib || {}; const id = String(Math.random()).slice(2); window.__bib[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__bib[id] = {status: r.status, type: r.headers.get('content-type'), text: await r.text()}; })
    .catch(e => { window.__bib[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__bib[%s]; if (v) delete window.__bib[%s]; return v; })()"""

def raw(path, timeout=30):
    """GET SITE+path from inside the tab -> (status, content-type, text). No retries: this block only inspects answers."""
    rid = json.dumps(js(START_JS % json.dumps(SITE + path)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > timeout:
            raise RuntimeError(f"{path}: no answer after {timeout}s")
        time.sleep(0.3)
    time.sleep(2.5)  # 15 requests every 30 s per IP
    return r["status"], r["type"], r["text"]

on_site()
# Terms of Use, as the home page shows them
terms = js("""(() => { const h = [...document.querySelectorAll('h2,h3')].find(e => /terms of use/i.test(e.textContent));
  let out = [], n = h && h.nextElementSibling; while (n && !/^H[23]$/.test(n.tagName)) { out.push(n.innerText); n = n.nextElementSibling; }
  return out.join(' '); })()""")
terms = " ".join(terms.split()).replace("\u2014", " - ")  # the page uses an em dash; print a plain hyphen
print("Terms of Use:", terms.split(" I make no")[0][:330])

s, t, body = raw("robots.txt")
print(f"\nrobots.txt: HTTP {s} {t} {body}")

s, t, body = raw("data")  # translation list (identifier, name, language, license)
tr = {x["identifier"]: x for x in json.loads(body)["translations"]}
print(f"\n/data: HTTP {s}, {len(tr)} translations")
for k in ("kjv", "web"):
    print(f"  {k}: {tr[k]['name']} | {tr[k]['language']} | {tr[k]['license']}")

for path in ("john+3:99?translation=kjv", "notabook+1:1", "john+3:16?translation=niv"):
    s, t, body = raw(path)
    print(f"\n{path}: HTTP {s} {t} {' '.join(body.split())[:80]}")
```

Output (from the run on 2026-11-10):

```text
Terms of Use: This service is free for anyone to use as long as you don't abuse my server. This service is rate limited to 15 requests every 30 seconds (based on IP address), and this may change in the future. Do not use this API to download an entire bible - it's too slow and we will likely block you. Instead, get the data from the source.

robots.txt: HTTP 404 application/json;charset=utf-8 {"error":"not found"}

/data: HTTP 200, 37 translations
  kjv: King James Version | English | Public Domain
  web: World English Bible | English | Public Domain

john+3:99?translation=kjv: HTTP 404 application/json;charset=utf-8 {"error":"not found"}

notabook+1:1: HTTP 404 application/json;charset=utf-8 {"error":"not found"}

john+3:16?translation=niv: HTTP 404 text/html <html> <head><title>404 Not Found</title></head> <body> <center><h1>404 Not Foun
```

### 3. Same lookups with curl (no browser)

curl's default User-Agent got HTTP 200 on every verse call.

```bash
for REF in "romans+8:28" "john+3:16"; do
  for TR in kjv web; do
    curl -sS --fail "https://bible-api.com/$REF?translation=$TR" | python3 -c '
import json, sys
d = json.load(sys.stdin)
print(d["reference"], "|", d["translation_id"], "|", " ".join(d["text"].split()))
'
    sleep 2.5  # 15 requests every 30 s per IP
  done
done
curl -sS -o /dev/null -w 'no such verse (john 3:99): HTTP %{http_code} %{content_type}\n' "https://bible-api.com/john+3:99?translation=kjv"
```

Output (from the run on 2026-11-10):

```text
Romans 8:28 | kjv | And we know that all things work together for good to them that love God, to them who are the called according to his purpose.
Romans 8:28 | web | We know that all things work together for good for those who love God, to those who are called according to his purpose.
John 3:16 | kjv | For God so loved the world, that he gave his only begotten Son, that whosoever believeth in him should not perish, but have everlasting life.
John 3:16 | web | For God so loved the world, that he gave his one and only Son, that whoever believes in him should not perish, but have eternal life.
no such verse (john 3:99): HTTP 404 application/json;charset=utf-8
```

## Fields

| Field | Notes |
|---|---|
| `reference` | normalized reference, `Romans 8:28` (input `rom+8:28` gives the same) |
| `verses[]` | `{book_id, book_name, chapter, verse, text}`; `book_id` is the USFM code (`ROM`, `JHN`) |
| `text` | all verses joined; KJV keeps source line breaks (`\n`) |
| `translation_id`, `translation_name`, `translation_note` | `kjv` / `King James Version` / `Public Domain`; `web` / `World English Bible` / `Public Domain` |
| `/data` `translations[]` | `{identifier, name, language, language_code, license, url}`; 37 translations on 2026-11-10 |

## Gotchas

- **Unknown translation = HTML, not JSON.** `translation=niv` returns nginx's `404 Not Found` page with `text/html`. Only ids in `/data` work (no NIV, ESV or NKJV: the list is public domain or freely licensed only).
- **Translation list changes.** The home page notes Almeida (`almeida`) and Revised Young's Literal Translation (`ylt`) were removed in November 2026. Check `/data` before hard-coding other ids.
- **Default is WEB, not KJV.** Omitting `translation=` gives the World English Bible.
- **Single-chapter books:** `jude+1` means verse 1, not the chapter (documented). For the whole chapter, add `single_chapter_book_matching=indifferent` (home page; not tested here).
- **No rate-limit headers.** Responses carry no `X-RateLimit-*` or `Retry-After`; pace yourself (15 per 30 s).
- **404s count against you.** More than 10 HTTP 404s in 30 s from one IP gets every request a 403 `Forbidden` for an hour (`lib/abuse_middleware.rb` in seven1m/bible_api, read 2026-11-10; not provoked). Block 2 makes 4 404s (robots.txt and three probes) 2.5 s apart. Run it once; on an unexpected 404, fix the reference instead of trying variants.
- **Tab marker.** The harness prefixes the tab title with a horse emoji; the blocks match a substring of the title only.

## What does not work

- **Whole books or bibles:** the Terms of Use say "Do not use this API to download an entire bible... we will likely block you". Not used; the data is on GitHub.
- **Copyrighted translations** (NIV, ESV, NKJV, NASB): not served.
- **Not tested:** the parameterized `/data/<translation>/<BOOK>/<chapter>` chapter API, `/data/<translation>/random`, verse ranges (`matt+25:31-33,46`), rate-limit behaviour (never provoked).
