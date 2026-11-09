# Free Dictionary API - Define an English Word: Part of Speech, IPA, Audio Link, Example, Synonyms

Field-tested against api.dictionaryapi.dev on 2026-11-09 using a Browser Use cloud browser (logged out) plus `curl` and Python urllib from a laptop. About 25 browser requests (page loads and in-page `fetch()`) and 35 plain HTTP calls, all serial: entry lookups were HTTP 200 or the documented 404, except one Cloudflare 502 on an uncached word that answered 200 on the next try; every `/media/pronunciations/` audio file tried was a 502 (see Gotchas). No 429, no challenge, no key, no login.

robots.txt (checked 2026-11-09): api.dictionaryapi.dev/robots.txt is HTTP 200 with only Cloudflare's commented content-signal preamble: 0 non-comment lines, no `User-agent` group, no `Content-Signal:` directive and no group for ChatGPT-User, Claude-User, Claude-Web, Perplexity-User, anthropic-ai, ClaudeBot or GPTBot, so nothing restricts `/api/v2/entries/` or `/media/`; dictionaryapi.dev/robots.txt is an S3 403 (not the API host). Terms: there is no ToS; the homepage says the API always will be free, for building "a game, learning application, or next-generation speech and text technology"; the GitHub README (meetDeveloper/freeDictionaryAPI, GPL-3.0) has no usage restrictions and asks for donations; no AI, scraping, key or non-commercial clause. The data is Wiktionary content, `CC BY-SA 3.0` per response, and each audio file carries its own Wikimedia licence: attribution and share-alike apply.

## Quick summary

- **No scraping.** `GET https://api.dictionaryapi.dev/api/v2/entries/en/<word>` returns a JSON list of entries (one per etymology) with `phonetic`, `phonetics[]` (IPA `text`, `audio` URL, licence), `meanings[]` (`partOfSpeech`, `definitions[]` with optional `example`, `synonyms`, `antonyms`), `license` and `sourceUrls` (en.wiktionary.org). Keyless, `access-control-allow-origin: *`, `cache-control: max-age=14400` behind Cloudflare.
- **English only.** The path language `en` works (`en_US/serendipity` answered the same; the repo's app.js maps `en_US` and `en_GB` to `en`); `es/hola` is a 404. Case does not matter (`SERENDIPITY` = `serendipity`); multi-word terms take `%20` (`ice%20cream`).
- **Not found is a JSON 404:** `{"title":"No Definitions Found","message":"Sorry pal, we couldn't find definitions for the word you were looking for.","resolution":...}`.
- **Rate limit: 450 requests per 5 minutes per IP** (`x-ratelimit-limit: 450`; the repo's app.js sets `windowMs: 5 * 60 * 1000, max: 450`), 429 when exceeded (per app.js; not provoked). The blocks pace 1 s per call.
- **Expect gaps, do not fill them.** `example` is optional per definition (serendipity has none), top-level `phonetic` can be absent (hello), `audio` can be `""`. The blocks print "none in the data" instead of inventing one.
- **Browser or plain HTTP.** Block 1 opens an entry URL so the tab is on the API origin and `fetch()` is same-origin; block 2 is curl. Both return the same record.

## What works

### 1. Define words: part of speech, IPA, audio links (checked), first example, synonyms (browser)

Self-contained. `call()` returns the response on 200/404, waits on a 429 (`Retry-After` if sent, else the whole 5-minute window), retries a 5xx twice and otherwise raises, so a failure never looks like "no definition". Each audio link gets one `HEAD` and its status is printed with the Wikimedia file page from `sourceUrl`.

```python
import json, time
from urllib.parse import quote

WORDS = ["serendipity", "ice cream", "qwertyuiopasdf"]  # last one is not a word: 404 "No Definitions Found"

API = "https://api.dictionaryapi.dev/api/v2/entries/en/"
PAUSE = 1.0  # the server allows 450 requests per 5 minutes per IP (x-ratelimit-limit); keep calls serial anyway

def on_api_tab():
    """fetch() runs from a logged-out api.dictionaryapi.dev tab (an entry URL, plain JSON). Reuse the tab if already there."""
    try:
        if js("location.origin") == "https://api.dictionaryapi.dev":
            return
    except Exception:
        pass
    new_tab(API + "serendipity")
    wait_for_load()
    if js("location.origin") != "https://api.dictionaryapi.dev" or not js("document.body.innerText").lstrip().startswith("["):
        raise RuntimeError(f"api.dictionaryapi.dev did not answer with JSON ({js('location.href')}): stop, do not retry around it")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__fd = window.__fd || {}; const id = String(Math.random()).slice(2); window.__fd[id] = null;
  fetch(%s, {credentials: 'omit', method: %s})
    .then(async r => { window.__fd[id] = {status: r.status, type: r.headers.get('content-type'), len: r.headers.get('content-length'),
      retry: r.headers.get('retry-after'), text: %s}; })
    .catch(e => { window.__fd[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__fd[%s]; if (v) delete window.__fd[%s]; return v; })()"""

def call(url, method="GET", tries=3, timeout=60, ok=(200, 404)):
    """-> response dict. 200 and 404 are answers; waits for the window on 429, backs off on 5xx (cache misses
    sometimes come back as a Cloudflare 502), raises on anything else so a failure never looks like "no definition"."""
    for attempt in range(tries):
        body = "await r.text()" if method == "GET" else "''"
        rid = json.dumps(js(START_JS % (json.dumps(url), json.dumps(method), body)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"{url}: no answer after {timeout}s")
            time.sleep(0.3)
        time.sleep(PAUSE)
        if r["status"] in ok:
            return r
        if attempt == tries - 1 or r["status"] not in (0, 429, 500, 502, 503, 504):
            raise RuntimeError(f"{url}: HTTP {r['status']} {r['text'][:120]!r}; stopping")
        # 429: honour Retry-After (seconds) if sent, else wait out the whole 5-minute window. Not x-ratelimit-reset:
        # Cloudflare serves cached copies of it (see Gotchas).
        retry = str(r.get("retry") or "")
        wait = (int(retry) if retry.isdigit() else 300) if r["status"] == 429 else 10 * (attempt + 1)
        time.sleep(min(max(wait, 5), 300))

def define(word):
    """-> dict with IPA, audio links, and per part of speech: first definition, first example, synonyms.
    A word the API does not have -> {"word": ..., "missing": <the 404 body>}."""
    r = call(API + quote(word.strip().lower(), safe=""))  # safe="": a "/" in the term stays inside one path segment
    if r["status"] == 404:
        return {"word": word, "missing": json.loads(r["text"])}
    entries = json.loads(r["text"])  # a list: one entry per etymology
    e0 = entries[0]
    phon = [p for e in entries for p in e["phonetics"]]
    ipa = e0.get("phonetic") or next((p["text"] for p in phon if p.get("text")), None)  # top-level "phonetic" is sometimes absent
    audio = [(p["audio"], p.get("license", {}).get("name"), p.get("sourceUrl")) for p in phon if p.get("audio")]  # "" = no audio
    senses = []
    for e in entries:
        for m in e["meanings"]:
            defs = m["definitions"]
            syn = list(dict.fromkeys(m["synonyms"] + [s for d in defs for s in d["synonyms"]]))
            ant = list(dict.fromkeys(m["antonyms"] + [a for d in defs for a in d["antonyms"]]))
            ex = next(((d["example"], d["definition"]) for d in defs if d.get("example")), None)
            senses.append({"pos": m["partOfSpeech"], "n_defs": len(defs), "definition": defs[0]["definition"],
                           "example": ex, "synonyms": syn, "antonyms": ant})
    return {"word": e0["word"], "ipa": ipa, "audio": audio, "senses": senses, "license": e0["license"]["name"],
            "source": e0["sourceUrls"]}

on_api_tab()
for w in WORDS:
    d = define(w)
    if "missing" in d:
        print(f"\n{w!r}: 404 {d['missing']['title']}: {d['missing']['message']}")
        continue
    print(f"\n{d['word']}  IPA {d['ipa']}  | data {d['license']} from {d['source']}")
    if not d["audio"]:
        print("  audio: none in the data")
    for url, lic, src in d["audio"]:
        h = call(url, "HEAD", tries=1, ok=range(100, 600))  # one HEAD, report whatever comes back
        print(f"  audio {url}  ({lic}) -> HTTP {h['status']} {h['type']}" + (f" {h['len']} bytes" if h["status"] == 200 else f"; file page: {src}"))
    for s in d["senses"]:
        print(f"  {s['pos']} ({s['n_defs']} definitions): {s['definition']}")
        print(f"    example: {s['example'][0]!r} (sense: {s['example'][1][:60]})" if s["example"] else "    example: none in the data")
        print(f"    synonyms: {s['synonyms'] or 'none'} | antonyms: {s['antonyms'] or 'none'}")
```

Output (from the run on 2026-11-09):

```text

serendipity  IPA /ˌsɛ.ɹən.ˈdɪ.pɪ.ti/  | data CC BY-SA 3.0 from ['https://en.wiktionary.org/wiki/serendipity']
  audio https://api.dictionaryapi.dev/media/pronunciations/en/serendipity-au.mp3  (BY-SA 4.0) -> HTTP 502 text/html; charset=UTF-8; file page: https://commons.wikimedia.org/w/index.php?curid=75857831
  audio https://api.dictionaryapi.dev/media/pronunciations/en/serendipity-us.mp3  (BY-SA 3.0) -> HTTP 502 text/html; charset=UTF-8; file page: https://commons.wikimedia.org/w/index.php?curid=965947
  noun (2 definitions): A combination of events which have come together by chance to make a surprisingly good or wonderful outcome.
    example: none in the data
    synonyms: ['chance', 'luck'] | antonyms: ["Murphy's law", 'perfect storm']

ice cream  IPA /ˌaɪsˈkɹiːm/  | data CC BY-SA 3.0 from ['https://en.wiktionary.org/wiki/ice%20cream']
  audio: none in the data
  noun (2 definitions): A dessert made from frozen sweetened cream or a similar substance, usually flavoured.
    example: 'Strawberries are particularly delicious with ice cream.' (sense: A dessert made from frozen sweetened cream or a similar subs)
    synonyms: ['frozen cow juice', 'iced cream', 'cone', 'cornet', 'ice cream cone', 'ice-cream cornet'] | antonyms: none

'qwertyuiopasdf': 404 No Definitions Found: Sorry pal, we couldn't find definitions for the word you were looking for.
```

### 2. Same lookup with curl (no browser)

curl with a truthful User-Agent got HTTP 200; the same JSON as block 1.

```bash
W=serendipity
curl -sS --fail -A "browser-harness-skill/1.0 (curl)" "https://api.dictionaryapi.dev/api/v2/entries/en/$W" | python3 -c '
import json, sys
for e in json.load(sys.stdin):
    ipa = e.get("phonetic") or next((p["text"] for p in e["phonetics"] if p.get("text")), None)
    print(e["word"], "| IPA", ipa, "| audio", [p["audio"] for p in e["phonetics"] if p.get("audio")])
    for m in e["meanings"]:
        ex = next((d["example"] for d in m["definitions"] if d.get("example")), None)
        syn = sorted(set(m["synonyms"] + [s for d in m["definitions"] for s in d["synonyms"]]))
        print(" ", m["partOfSpeech"], "|", m["definitions"][0]["definition"], "| example:", ex, "| synonyms:", syn)
    print("  data licence", e["license"]["name"], e["sourceUrls"])
'
sleep 1
curl -sS -o /dev/null -w 'audio HEAD: HTTP %{http_code} %{content_type}\n' -I "https://api.dictionaryapi.dev/media/pronunciations/en/$W-us.mp3"
sleep 1
curl -sS -w '  <- HTTP %{http_code}\n' "https://api.dictionaryapi.dev/api/v2/entries/en/qwertyuiopasdf"
```

Output (from the run on 2026-11-09):

```text
serendipity | IPA /ˌsɛ.ɹən.ˈdɪ.pɪ.ti/ | audio ['https://api.dictionaryapi.dev/media/pronunciations/en/serendipity-au.mp3', 'https://api.dictionaryapi.dev/media/pronunciations/en/serendipity-us.mp3']
  noun | A combination of events which have come together by chance to make a surprisingly good or wonderful outcome. | example: None | synonyms: ['chance', 'luck']
  data licence CC BY-SA 3.0 ['https://en.wiktionary.org/wiki/serendipity']
audio HEAD: HTTP 502 text/plain; charset=UTF-8
{"title":"No Definitions Found","message":"Sorry pal, we couldn't find definitions for the word you were looking for.","resolution":"You can try the search again at later time or head to the web instead."}  <- HTTP 404
```

## Fields

| Field | Where | Notes |
|---|---|---|
| `word` | entry | lower-cased headword (`serendipity`, `ice cream`) |
| `phonetic` | entry | IPA with slashes (`/ˌsɛ.ɹən.ˈdɪ.pɪ.ti/`); absent on some words (hello), so fall back to the first `phonetics[].text` |
| `phonetics[]` | entry | `{text, audio, sourceUrl, license{name, url}}`; `audio` is `""` when there is none; `-au`, `-uk`, `-us` in the file name = accent; `sourceUrl` is the Wikimedia Commons file page |
| `meanings[]` | entry | `{partOfSpeech, definitions[], synonyms[], antonyms[]}`; the same part of speech can repeat (run: verb, noun, verb, adjective) |
| `definitions[]` | meaning | `{definition, example?, synonyms[], antonyms[]}`; `example` only when Wiktionary has one (run noun: 11 of 23) |
| `license`, `sourceUrls` | entry | `{"name":"CC BY-SA 3.0", ...}`, `["https://en.wiktionary.org/wiki/serendipity"]` |

## Gotchas

- **Audio links were dead on 2026-11-09.** Every `/media/pronunciations/en/*.mp3` tried (serendipity-au, serendipity-us, hello-au, run-us) answered HTTP 502 `error code: 502` to curl, urllib and the cloud browser, between 23:21 and 23:25 UTC. Report the link with its status and give the `sourceUrl` file page as a link for people. Do not script commons.wikimedia.org to resolve it: its robots.txt disallows `/w/` and `/api/` for `User-agent: *`.
- **Synonyms live at two levels.** Both `meanings[].synonyms` and `definitions[].synonyms` carry them; the blocks merge both, in order, without duplicates.
- **Several entries per word.** `bank` returns 4 entries (one per etymology), each with its own meanings; read all of them, not `[0]` only.
- **Rate-limit headers are cached.** On a Cloudflare `HIT` the `x-ratelimit-*` headers are the cached copy (serendipity sent an `x-ratelimit-reset` of 2026-07-30, months in the past, and a `remaining` count that did not drop between calls), so they do not count your calls and block 1 does not use them for its 429 wait. Pace yourself.
- **Cache misses can 502.** An uncached word (`bliss`) gave one Cloudflare 502, then 200 ten seconds later; cached words answered instantly. Block 1 retries a 5xx twice with 10 s and 20 s waits.
- **Tab marker.** The harness prefixes the tab title with a horse emoji; block 1 checks only the origin and that the body starts with `[`.

## What does not work

- **Languages other than English:** `/entries/es/hola` is a 404 "No Definitions Found".
- **Audio files:** HTTP 502 on 2026-11-09 (above).
- **Not tested:** `/api/v1/` (the homepage example shows an older format with `origin` and ssl.gstatic.com audio), rate limiting (never provoked), words with apostrophes or hyphens beyond `ice cream`.
