# WoRMS (World Register of Marine Species) via marinespecies.org/rest - Turn a Marine Species Name, or a List of Names, into the Accepted Name, AphiaID, Status, Full Classification, Common Names and Recorded Distribution, with the WoRMS Citation: Fuzzy-Match Typos, Catch Homonyms, Page Synonyms (JSON REST webservice, no key)

Field-tested against www.marinespecies.org/rest on 2026-11-25 (US Pacific afternoon; 2026-11-26 00:30 UTC to 00:44 UTC, 01:30-01:44 in Belgium, where WoRMS is hosted) using a fresh Browser Use cloud browser (logged out; one session `ka-worms-1125`, 00:33:54-00:43:07 UTC, stopped and confirmed `stopped` afterwards) plus Python `urllib` and `curl` from a Linux machine. 13 browser page loads (one API answer to open the tab; block 2 loaded robots.txt, the about page, the webservice page, a taxon page, example.com and an API answer in each of its two runs) and 84 in-page `fetch()` calls (blocks 1 and 2: 21 per run each), 66 urllib calls (block 3 ran twice: robots.txt and 32 API calls each) and 71 curl calls (45 while exploring, 6 of them www.marinespecies.org pages, robots.txt or a script file; 13 in each of block 4's two runs), all serial and at least 1.2 s apart in the blocks (robots.txt asks `Crawl-delay: 1`). Every call was HTTP 200 except the deliberate HTTP 204 ("Nothing found") and HTTP 400 probes and three HTTP 404s while looking for the OpenAPI file. No 403 or 429, no challenge, no key, no login. Data calls took 0.5-1.9 s; the one 50-record `like=true` search took 3.9 s (1.8 s when the verifier repeated it at 00:52 UTC). Each block ran twice; the outputs shown come from the second run, and the first runs differed only as noted under each output. An independent re-run on 2026-11-26 (blocks 1 and 2 in a new cloud browser `kv-worms-1125`, 00:47-00:49 UTC, stopped and confirmed `stopped` afterwards; blocks 3 and 4 at 00:49-00:50 UTC, block 4 again at 00:54 UTC after a comment fix) reproduced every output apart from the clock and the slowest call. Later on 2026-11-26 block 4 got a `trap ... EXIT` that removes its temporary file even when the script stops early; that version re-ran from the same Linux machine at 01:01-01:04 UTC with the same output apart from the clock and timings. After review on 2026-11-26, block 3 stops on a result list of the wrong length or an empty HTTP 200 body and treats a record with no accepted name as unresolved, block 4 adds `--retry-max-time 120`, and the docstrings name the retried statuses; block 1 re-ran in a new cloud browser (01:22:43-01:23:33 UTC, stopped and confirmed `stopped`), blocks 3 and 4 from the Linux machine at 01:15-01:17 UTC, with the same output apart from the clock and timings. Block 3 then got URL-size batches for the exact lookup (a 500-name GET is HTTP 400 at the server, see Limits) and re-ran at 01:31-01:32 UTC with the same output apart from the clock.

robots.txt (checked 2026-11-26 UTC, curl, the cloud browser and `urllib.robotparser`): https://www.marinespecies.org/robots.txt is four lines, `User-agent: *`, `Disallow: /structure`, `Disallow: /export`, `Crawl-delay: 1`. No group names an AI agent, so GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider fall under `*`; every path this skill uses (`/rest/...`, `/aphia.php?p=taxdetails`, `/about.php`) is allowed for all 11 agents, with a crawl delay of 1 s (block 3). Terms: the "Terms of use" on https://www.marinespecies.org/about.php#terms say "The text on the WoRMS pages is open-access under the terms of the Creative Commons Attribution License (CC-BY)", "This License permits unrestricted use, provided it is cited as requested on the WoRMS webpages, unless stated otherwise on the individual pages", "Images are by default open-access under the terms of the CC BY-NC-SA license" (this skill fetches no images), "Re-distribution of the entire database is not permitted, unless by prior written agreement" and "We strongly encourage the use of the on-line tools and available webservices". The webservice page https://www.marinespecies.org/aphia.php?p=webservice adds "Don't use the webservice to harvest WoRMS completely, you can request a database dump" and "Please, let us know if you are using the webservice". No AI/ML, scraping, automated-access or non-commercial-only clause for the text data (block 2 found none of the words scrap, artificial intelligence, machine learning, robot, crawl or non-commercial on the about page), and neither page states a call-rate limit. Citation (about page, "Citing WoRMS"): "WoRMS Editorial Board (2026). World Register of Marine Species. Available from https://www.marinespecies.org at VLIZ. Accessed 2026-11-26. doi:10.14284/170"; "If the data from WoRMS constitute a substantial proportion of the records used in analyses, the chief editor(s) of the database should be contacted." Naming: this skill says "WoRMS (World Register of Marine Species)", hosted by VLIZ (the Flanders Marine Institute), uses no WoRMS logo, prints the citation with every answer, looks names up one list at a time (never the whole register), and is not endorsed by WoRMS or VLIZ.

**Taxonomic opinion, not a fixed fact.** WoRMS editors keep changing names; `status`, `valid_AphiaID` and the classification are WoRMS's current view on the day you call. Quote the AphiaID, the access date and the citation with every answer.

## Quick summary

- **No scraping.** All GET, JSON, no key: `GET https://www.marinespecies.org/rest/AphiaRecordsByName/{name}?like=false&marine_only=true` (one name, exact), `GET /AphiaRecordsByNames?scientificnames[]=...` (up to 500 exact names), `GET /AphiaRecordsByMatchNames?scientificnames[]=...` (up to 50 names, fuzzy TAXAMATCH), then per AphiaID `/AphiaRecordByAphiaID/{id}`, `/AphiaClassificationByAphiaID/{id}`, `/AphiaVernacularsByAphiaID/{id}`, `/AphiaDistributionsByAphiaID/{id}` and `/AphiaSynonymsByAphiaID/{id}`. The human page is `https://www.marinespecies.org/aphia.php?p=taxdetails&id={id}` (the record's `url`). The OpenAPI 3.0 description is at https://www.marinespecies.org/rest/api-docs/openapi.json (served as YAML). CORS is open (`Access-Control-Allow-Origin: *`).
- **Answer (run 2026-11-26, 00:40 UTC):** `Delphinus delphis` = **AphiaID 137094**, accepted, *Delphinus delphis* Linnaeus, 1758, Species; Animalia > Chordata > Mammalia > Cetartiodactyla > Delphinidae (15 ranks from Biota); English names "common dolphin", "short-beaked common dolphin" and 4 more (90 names in 37 languages); 19 distribution records at 17 places, 16 of them valid (Wimereux only `doubtful`); 24 synonyms. The typo `Gadus morua` matches *Gadus morhua* (126436, `phonetic`); `Delphinus orca Linnaeus, 1758` is an unaccepted basionym of **Orcinus orca** (137102); `Delphinus orca` alone is ambiguous (two authors, two accepted species).
- **Switch to the accepted ID first.** Only `valid_AphiaID` has common names and distribution: for unaccepted 148730 both answer HTTP 204, and its classification still ends at *Delphinus orca* under genus *Delphinus*.
- **Limits:** none published and no rate-limit headers; robots.txt asks `Crawl-delay: 1`. Batches: 50 names per TAXAMATCH call (51 is HTTP 400), 500 per exact `AphiaRecordsByNames` call by the API docs, but these are GETs and the URL is the real limit (2026-11-26 01:29-01:30 UTC: 200 names, an 8 KB URL, worked in 17.7 s; 300 names, 12 KB, got HTTP 414; 500 names, 20 KB, HTTP 400), so block 3 keeps each URL's names under 6,000 bytes, 50 records per page with `offset=1, 51, 101...`. The blocks run serially 1.2 s apart, wait once on 429, 500, 502, 503, 504 or a network error (`Retry-After` as seconds or an HTTP date, else 10 s; over 120 s they stop) and then stop; block 2 only inspects answers (no retry); block 4 lets `curl --retry 1` retry once, and `--retry-max-time 120` drops that retry when Retry-After asks for longer. Do not loop over the register: WoRMS asks you not to harvest it.

## What works

### 1. A list of names -> accepted name, AphiaID, status, classification, common names, distribution, synonyms, citation (browser)

`on_worms_tab()` opens one logged-out API answer so `fetch()` runs same-origin (cross-origin works too, but then the page cannot read `Retry-After`, see block 2). `get()` returns parsed JSON on HTTP 200 and `None` on HTTP 204, waits once on 429, 500, 502, 503, 504 or a network error and otherwise raises. One TAXAMATCH call for the whole list (up to 50 names), then 5 calls per accepted species: 21 `fetch()` calls for these 6 names. `pick()` keeps the best match class, prefers species-rank candidates for a two-word name, and refuses to guess when candidates point to more than one accepted name.

```python
import email.utils, json, time
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import quote

API = "https://www.marinespecies.org/rest"
PAUSE = 1.2   # robots.txt: "Crawl-delay: 1" for every agent; stay a little above it, serial
NAMES = ["Delphinus delphis", "Gadus morua", "Delphinus orca", "Delphinus orca Linnaeus, 1758",
         "Carcharodon carcharias", "Fakeus notrealis"]   # up to 50 per AphiaRecordsByMatchNames call
LANG = "eng"  # ISO 639-3 code of the common names to print in full
MATCH_ORDER = ["exact", "exact_subgenus", "exact_replaced", "like", "phonetic", "near_1", "near_2", "near_3"]   # match_quarantine, match_deleted sort last

def on_worms_tab():
    """fetch() runs same-origin from a logged-out www.marinespecies.org/rest answer (CORS is open too, see block 2)."""
    try:
        if js("location.origin") == "https://www.marinespecies.org":
            return
    except Exception:
        pass
    new_tab(API + "/AphiaRecordByAphiaID/137094")
    wait_for_load()
    if js("location.origin") != "https://www.marinespecies.org" or '"AphiaID":137094' not in (js("document.body ? document.body.innerText : ''") or ""):
        raise RuntimeError(f"www.marinespecies.org/rest did not answer for AphiaID 137094 (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__w = window.__w || {}; const id = String(Math.random()).slice(2); window.__w[id] = null;
  fetch(%s, {credentials: 'omit', cache: 'no-store'})
    .then(async r => { const h = {}; r.headers.forEach((v, k) => { h[k] = v; });
      window.__w[id] = {status: r.status, headers: h, text: await r.text()}; })
    .catch(e => { window.__w[id] = {status: 0, headers: {}, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__w[%s]; if (v) delete window.__w[%s]; return v; })()"""

calls = []
def fetch(url):
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 90:
            raise RuntimeError(f"{url}: no answer after 90s")
        time.sleep(0.2)
    calls.append((r["status"], round(time.time() - t0, 1)))
    time.sleep(PAUSE)
    return r

def retry_wait(value, default=10):
    """Retry-After as delay-seconds or an HTTP date -> seconds to wait; missing or unreadable -> default."""
    v = (value or "").strip()
    if v.isdigit():
        return int(v)
    try:
        return max(0, int((email.utils.parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()) + 1)
    except (TypeError, ValueError):
        return default

def get(path):
    """GET API + path -> parsed JSON, or None on HTTP 204 ("Nothing found", empty body).
    Waits once on 429, 500, 502, 503, 504 or a network error (Retry-After in seconds or as an HTTP date, else 10 s; over 120 s stops).
    Raises on anything else, with WoRMS's validation message for a 400."""
    url = API + path
    for attempt in range(2):
        r = fetch(url)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            wait = retry_wait(r["headers"].get("retry-after"))
            if wait > 120:
                raise RuntimeError(f"{url}: server asks to wait {wait} s: stopping")
            time.sleep(wait)
            continue
        break
    if r["status"] == 204:
        return None
    if r["status"] != 200 or "json" not in r["headers"].get("content-type", ""):
        raise RuntimeError(f"{url}: HTTP {r['status']} {' '.join(r['text'].split())[:160]!r}; stopping")
    return json.loads(r["text"])

def pick(name, cands):
    """TAXAMATCH candidates for one name -> (accepted AphiaID or None, note). Keeps the best match class,
    then species-rank candidates for a two-word name; more than one accepted target left means ambiguous."""
    if not cands:
        return None, "no match"
    best = min(MATCH_ORDER.index(c["match_type"]) if c["match_type"] in MATCH_ORDER else 99 for c in cands)
    cands = [c for c in cands if (MATCH_ORDER.index(c["match_type"]) if c["match_type"] in MATCH_ORDER else 99) == best]
    if len(name.split()) == 2 and any(c["rank"] == "Species" for c in cands):
        cands = [c for c in cands if c["rank"] == "Species"]
    targets = {c["valid_AphiaID"] for c in cands}
    if None in targets:
        return None, "status " + ", ".join(f"{c['status']!r} with no accepted name ({c['AphiaID']})" for c in cands)
    if len(targets) > 1:
        return None, "AMBIGUOUS: " + "; ".join(f"{c['scientificname']} {c['authority']} ({c['AphiaID']}, {c['status']}) -> {c['valid_name']} ({c['valid_AphiaID']})"
                                             for c in cands) + ": add the authority to the name"
    c = cands[0]
    note = f"{c['match_type']} match on {c['scientificname']} {c['authority']} (AphiaID {c['AphiaID']}, {c['status']}"
    note += f", {c['unacceptreason']})" if c["unacceptreason"] else ")"
    return targets.pop(), note

def paged(path):
    """Synonyms come 50 per page; offset=51 asks for the next 50; HTTP 204 ends the list."""
    out, offset = [], 1
    while True:
        page = get(f"{path}?offset={offset}") if offset > 1 else get(path)
        out += page or []
        if not page or len(page) < 50:
            return out
        offset += 50

def ranks(node):
    out = []
    while node:
        out.append((node["rank"], node["scientificname"], node["AphiaID"]))
        node = node.get("child")
    return out

on_worms_tab()
now = datetime.now(timezone.utc)
print(f"WoRMS (World Register of Marine Species) REST webservice, {len(NAMES)} names, checked {now:%Y-%m-%d %H:%M} UTC")

# 1. One TAXAMATCH call for the whole list: one result list per name, in input order ([] = no match)
q = "&".join("scientificnames[]=" + quote(n) for n in NAMES)
matched = get(f"/AphiaRecordsByMatchNames?{q}&marine_only=true")
if not isinstance(matched, list) or len(matched) != len(NAMES):
    raise RuntimeError(f"AphiaRecordsByMatchNames returned {type(matched).__name__} of {len(matched or [])} for {len(NAMES)} names: stop")

done = {}
for name, cands in zip(NAMES, matched):
    aid, note = pick(name, cands or [])
    print(f"\n{name!r}: {note}")
    if aid is None:
        continue
    if aid in done:
        print(f"  = {done[aid]} (AphiaID {aid}), shown above")
        continue
    # 2. The accepted record, its classification, common names, distribution and synonyms
    rec = get(f"/AphiaRecordByAphiaID/{aid}")
    if rec is None or rec["AphiaID"] != aid or rec["status"] != "accepted":
        raise RuntimeError(f"AphiaID {aid}: record {rec and (rec['AphiaID'], rec['status'])}, expected an accepted record: stop")
    done[aid] = rec["scientificname"]
    tree = ranks(get(f"/AphiaClassificationByAphiaID/{aid}"))
    if tree[-1][2] != aid:
        raise RuntimeError(f"classification of {aid} ends at {tree[-1]}: stop")
    vern = get(f"/AphiaVernacularsByAphiaID/{aid}") or []
    dist = get(f"/AphiaDistributionsByAphiaID/{aid}") or []
    syn = paged(f"/AphiaSynonymsByAphiaID/{aid}")
    flags = [k[2:].lower() for k in ("isMarine", "isBrackish", "isFreshwater", "isTerrestrial") if rec[k] == 1]
    print(f"  accepted: {rec['scientificname']} {rec['authority']}, AphiaID {aid}, {rec['rank']}, status {rec['status']}, "
          f"habitat {'/'.join(flags) or 'not given'}, extinct {rec['isExtinct']}, modified {rec['modified'][:10]}")
    print(f"  {rec['url']}  {rec['lsid']}")
    print("  classification: " + " > ".join(f"{r} {n}" for r, n, _ in tree))
    langs = Counter(v["language"] for v in vern)
    print(f"  common names: {len(vern)} in {len(langs)} languages; {LANG}: {sorted({v['vernacular'] for v in vern if v['language_code'] == LANG}) or 'none'}")
    places = {}
    for d in dist:   # the same locality can come back several times (one per source)
        places.setdefault((d["locality"], d["locationID"]), set()).add(d["recordStatus"])
    ok = sorted(l for (l, _), s in places.items() if "valid" in s)
    doubt = sorted(l for (l, _), s in places.items() if "valid" not in s)
    print(f"  distribution: {len(dist)} records, {len(places)} distinct places; valid ({len(ok)}): {'; '.join(ok[:8])}{' ...' if len(ok) > 8 else ''}")
    if doubt:
        print(f"    doubtful or other only ({len(doubt)}): {'; '.join(doubt)}")
    reasons = Counter(s["unacceptreason"] or s["status"] for s in syn)
    print(f"  synonyms: {len(syn)} ({', '.join(f'{k} {v}' for k, v in reasons.most_common(3))}), e.g. {', '.join(s['scientificname'] for s in syn[:3])}")
    print(f"  page citation: {rec['citation']}")

print(f"\n{len(calls)} API calls, statuses {sorted({s for s, _ in calls})}, slowest {max(t for _, t in calls)} s")
print(f"Cite: WoRMS Editorial Board ({now:%Y}). World Register of Marine Species. Available from https://www.marinespecies.org at VLIZ. "
      f"Accessed {now:%Y-%m-%d}. doi:10.14284/170")
```

Output (second run, 2026-11-26 00:40 UTC; the 00:35 UTC run printed the same apart from the clock and "slowest 1.9 s"):

```text
WoRMS (World Register of Marine Species) REST webservice, 6 names, checked 2026-11-26 00:40 UTC

'Delphinus delphis': exact match on Delphinus delphis Linnaeus, 1758 (AphiaID 137094, accepted)
  accepted: Delphinus delphis Linnaeus, 1758, AphiaID 137094, Species, status accepted, habitat marine, extinct None, modified 2008-08-20
  https://www.marinespecies.org/aphia.php?p=taxdetails&id=137094  urn:lsid:marinespecies.org:taxname:137094
  classification: Superdomain Biota > Kingdom Animalia > Phylum Chordata > Subphylum Vertebrata > Infraphylum Gnathostomata > Megaclass Tetrapoda > Class Mammalia > Subclass Theria > Order Cetartiodactyla > Suborder Cetancodonta > Infraorder Cetacea > Superfamily Odontoceti > Family Delphinidae > Genus Delphinus > Species Delphinus delphis
  common names: 90 in 37 languages; eng: ['common dolphin', 'saddle-backed dolphin', 'sea porpoise', 'short-beaked common dolphin', 'short-beaked saddle-backed dolphin', 'short-beaked saddleback dolphin']
  distribution: 19 records, 17 distinct places; valid (16): Azores Exclusive Economic Zone; Belgian Exclusive Economic Zone; European waters (ERMS scope); Greek Exclusive Economic Zone; Gulf of Maine; Gulf of St. Lawrence; Ionian sea; Irish Exclusive economic Zone ...
    doubtful or other only (1): Wimereux
  synonyms: 24 (synonym 20, preoccupied 2, Spelling variation 1), e.g. Delphinus albimanus, Delphinus algeriensis, Delphinus bairdi
  page citation: Fordyce, E.; Perrin, W.F. (2026). World Cetacea Database. Delphinus delphis Linnaeus, 1758. Accessed through: World Register of Marine Species at: https://www.marinespecies.org/aphia.php?p=taxdetails&id=137094 on 2026-11-26

'Gadus morua': phonetic match on Gadus morhua Linnaeus, 1758 (AphiaID 126436, accepted)
  accepted: Gadus morhua Linnaeus, 1758, AphiaID 126436, Species, status accepted, habitat marine/brackish, extinct None, modified 2008-01-15
  https://www.marinespecies.org/aphia.php?p=taxdetails&id=126436  urn:lsid:marinespecies.org:taxname:126436
  classification: Superdomain Biota > Kingdom Animalia > Phylum Chordata > Subphylum Vertebrata > Infraphylum Gnathostomata > Parvphylum Osteichthyes > Gigaclass Actinopterygii > Superclass Actinopteri > Class Teleostei > Order Gadiformes > Suborder Gadoidei > Family Gadidae > Genus Gadus > Species Gadus morhua
  common names: 49 in 28 languages; eng: ['Atlantic cod', 'cod']
  distribution: 35 records, 26 distinct places; valid (26): Belgian Exclusive Economic Zone; Birkenfels (shipwreck); British Isles; Davis Strait; Dutch Exclusive  Economic Zone; European waters (ERMS scope); FAO fishing area 21; Grevelingen ...
  synonyms: 18 (unaccepted 15, misspelling 2, synonym 1), e.g. Asellus major, Gadus arenosus, Gadus callarias
  page citation: Froese, R. and D. Pauly. Editors. (2026). FishBase. Gadus morhua Linnaeus, 1758. Accessed through: World Register of Marine Species at: https://www.marinespecies.org/aphia.php?p=taxdetails&id=126436 on 2026-11-26

'Delphinus orca': AMBIGUOUS: Delphinus orca Linnaeus, 1758 (148730, unaccepted) -> Orcinus orca (137102); Delphinus orca Temminck & Schlegel, 1841 (383893, unaccepted) -> Grampus griseus (137098): add the authority to the name

'Delphinus orca Linnaeus, 1758': exact match on Delphinus orca Linnaeus, 1758 (AphiaID 148730, unaccepted, basionym)
  accepted: Orcinus orca (Linnaeus, 1758), AphiaID 137102, Species, status accepted, habitat marine, extinct None, modified 2008-08-20
  https://www.marinespecies.org/aphia.php?p=taxdetails&id=137102  urn:lsid:marinespecies.org:taxname:137102
  classification: Superdomain Biota > Kingdom Animalia > Phylum Chordata > Subphylum Vertebrata > Infraphylum Gnathostomata > Megaclass Tetrapoda > Class Mammalia > Subclass Theria > Order Cetartiodactyla > Suborder Cetancodonta > Infraorder Cetacea > Superfamily Odontoceti > Family Delphinidae > Genus Orcinus > Species Orcinus orca
  common names: 106 in 39 languages; eng: ['grampus', 'killer whale', 'killer-trasher', 'orca', 'sword grampus', 'swordfish']
  distribution: 25 records, 23 distinct places; valid (23): Antarctica; Azores Exclusive Economic Zone; Belgian Exclusive Economic Zone; Comoran Exclusive Economic Zone; European waters (ERMS scope); Gulf of Maine; Gulf of Mexico; Gulf of St. Lawrence ...
  synonyms: 38 (synonym 35, basionym 1, misspelling of rectipinna 1), e.g. Delphinus duhameli, Delphinus gladiator, Delphinus grampus
  page citation: Fordyce, E.; Perrin, W.F. (2026). World Cetacea Database. Orcinus orca (Linnaeus, 1758). Accessed through: World Register of Marine Species at: https://www.marinespecies.org/aphia.php?p=taxdetails&id=137102 on 2026-11-26

'Carcharodon carcharias': exact match on Carcharodon carcharias (Linnaeus, 1758) (AphiaID 105838, accepted)
  accepted: Carcharodon carcharias (Linnaeus, 1758), AphiaID 105838, Species, status accepted, habitat marine/brackish, extinct None, modified 2008-01-15
  https://www.marinespecies.org/aphia.php?p=taxdetails&id=105838  urn:lsid:marinespecies.org:taxname:105838
  classification: Superdomain Biota > Kingdom Animalia > Phylum Chordata > Subphylum Vertebrata > Infraphylum Gnathostomata > Parvphylum Chondrichthyes > Class Elasmobranchii > Subclass Neoselachii > Infraclass Selachii > Superorder Galeomorphi > Order Lamniformes > Family Lamnidae > Genus Carcharodon > Species Carcharodon carcharias
  common names: 93 in 23 languages; eng: ['Tommy', 'anchovy-eater', 'blue pointer', 'cowshark', 'death shark', 'demon shark', 'great white death', 'great white shark', 'jumping shark', 'man-eater shark', 'mudshark', 'tuna shark', 'uptail', 'white death', 'white death shark', 'white pointer', 'white shark']
  distribution: 42 records, 35 distinct places; valid (35): Azores Exclusive Economic Zone; British Columbia; Canadian Exclusive Economic Zone [Pacific part]; Coastal Waters of Southeast Alaska and British Columbia; Eritrean Exclusive Economic Zone; Europe; European waters (ERMS scope); FAO fishing area 47 ...
  synonyms: 18 (unaccepted 16, misspelling - incorrect subsequent spelling 1, synonym 1), e.g. Carcharias atwoodi, Carcharias lamia, Carcharias maso
  page citation: Froese, R. and D. Pauly. Editors. (2026). FishBase. Carcharodon carcharias (Linnaeus, 1758). Accessed through: World Register of Marine Species at: https://www.marinespecies.org/aphia.php?p=taxdetails&id=105838 on 2026-11-26

'Fakeus notrealis': no match

21 API calls, statuses [200], slowest 1.7 s
Cite: WoRMS Editorial Board (2026). World Register of Marine Species. Available from https://www.marinespecies.org at VLIZ. Accessed 2026-11-26. doi:10.14284/170
```

### 2. robots.txt, terms, the webservice rules, the taxon page, CORS, what the API does with mistakes (browser)

6 page loads and 21 in-page `fetch()` calls in the same tab. The CORS check runs from https://example.com: the body is readable, but only `content-type` and `content-length` are visible to the page.

```python
import json, time
from urllib.parse import quote

API = "https://www.marinespecies.org/rest"
SITE = "https://www.marinespecies.org"

START_JS = """(() => { window.__w = window.__w || {}; const id = String(Math.random()).slice(2); window.__w[id] = null;
  fetch(%s, {credentials: 'omit', cache: 'no-store'})
    .then(async r => { const h = {}; r.headers.forEach((v, k) => { h[k] = v; });
      window.__w[id] = {status: r.status, headers: h, text: await r.text()}; })
    .catch(e => { window.__w[id] = {status: 0, headers: {}, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__w[%s]; if (v) delete window.__w[%s]; return v; })()"""

def raw(url):
    """One in-page GET -> {status, headers, text}. No retries: this block only inspects answers."""
    rid = json.dumps(js(START_JS % json.dumps(url if url.startswith("http") else API + url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 90:
            raise RuntimeError(f"{url}: no answer after 90s")
        time.sleep(0.2)
    time.sleep(1.2)   # robots.txt Crawl-delay: 1
    return r

def page(url):
    """Load a page -> (HTTP status, content type, final URL, visible text)."""
    for attempt in range(2):
        try:
            goto_url(url)
            wait_for_load()
            break
        except Exception as e:
            if attempt:
                raise
            print(f"  (navigation to {url} failed once: {type(e).__name__}; retrying in 10 s)")
            time.sleep(10)
    time.sleep(1.2)
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    return st, js("document.contentType"), js("location.href"), js("(document.body || document.documentElement).innerText || ''") or ""

# robots.txt: one '*' group, no named AI-agent group
st, ct, href, txt = page(SITE + "/robots.txt")
lines = [l.strip() for l in txt.splitlines() if l.strip()]
print(f"{href} HTTP {st} {ct}: {lines}")

# Terms of use and citation (about.php), webservice rules (aphia.php?p=webservice)
st, ct, href, txt = page(SITE + "/about.php#terms")
flat = " ".join(txt.split())
print(f"\n{href} HTTP {st}")
for n in ("The text on the WoRMS pages is open-access under the terms of the Creative Commons Attribution License (CC-BY)",
          "This License permits unrestricted use, provided it is cited as requested on the WoRMS webpages",
          "Images are by default open-access under the terms of the CC BY-NC-SA license",
          "Re-distribution of the entire database is not permitted, unless by prior written agreement",
          "We strongly encourage the use of the on-line tools and available webservices",
          "WoRMS Editorial Board (2026). World Register of Marine Species. Available from https://www.marinespecies.org at VLIZ. Accessed",
          "doi:10.14284/170",
          "Individual pages are individually authored and dated",
          "If the data from WoRMS constitute a substantial proportion of the records used in analyses, the chief editor(s) of the database should be contacted"):
    print(f"  {'found' if n in flat else 'MISSING'}: {n[:100]!r}")
low = flat.lower()
print(f"  words scrap/AI/ML/robot/crawl/non-commercial: {[w for w in ('scrap', 'artificial intelligence', 'machine learning', 'robot', 'crawl', 'non-commercial', 'noncommercial') if w in low] or 'none'}")

st, ct, href, txt = page(SITE + "/aphia.php?p=webservice")
flat = " ".join(txt.split())
print(f"\n{href} HTTP {st}")
for n in ("Don't use the webservice to harvest WoRMS completely, you can request a database dump",
          "Please, let us know if you are using the webservice"):
    print(f"  {'found' if n in flat else 'MISSING'}: {n!r}")
low = flat.lower()
print(f"  rate words: {[w for w in ('requests per', 'per second', 'per minute', 'rate limit', 'throttl', '429', 'api key') if w in low] or 'none'}")

# The human taxon page agrees with the API
st, ct, href, txt = page(SITE + "/aphia.php?p=taxdetails&id=137094")
flat = " ".join(txt.split())
print(f"\n{href} HTTP {st}: title {js('document.title')!r}")
print(f"  'AphiaID 137094' {'found' if 'AphiaID 137094' in flat else 'MISSING'}; 'accepted' {'found' if 'accepted' in flat.lower() else 'MISSING'}; "
      f"'Delphinidae' {'found' if 'Delphinidae' in flat else 'MISSING'}")

# CORS: a cross-origin fetch() from example.com reads the API answer
page("https://example.com/")
r = raw(API + "/AphiaRecordByAphiaID/137094")
print(f"\ncross-origin fetch() from {js('location.origin')}: HTTP {r['status']} {r['headers'].get('content-type')}, body readable: {r['text'].startswith('{')}; "
      f"headers JS can read: {sorted(r['headers'])}")

page(API + "/AphiaRecordByAphiaID/137094")   # back on the API host
print()

def brief(r):
    t = " ".join(r["text"].split())
    if r["status"] == 200 and t.startswith("["):
        d = json.loads(r["text"])
        if d and isinstance(d[0], dict):
            t = f"{len(d)} records: " + ", ".join(f"{x['scientificname']} [{x['status']}{', ' + x['match_type'] if x.get('match_type') else ''}]" for x in d[:4]) + (" ..." if len(d) > 4 else "")
        else:
            t = f"{len(d)} lists: " + " | ".join(", ".join(f"{x['scientificname']} {x['authority']} [{x['match_type']}] -> {x['valid_name']}" for x in g) or "[]" for g in d)
    elif r["status"] == 200 and t.startswith("{"):
        d = json.loads(r["text"])
        t = f"{d.get('scientificname')} [{d.get('status')}] -> {d.get('valid_name')}" if "status" in d else t[:110]
    return f"HTTP {r['status']} {r['headers'].get('content-type', '-') or '-'} {len(r['text'])}B: {t[:150] or '(empty body)'}"

N = lambda s: quote(s)
for label, path in (
    ("unknown name                         ", f"/AphiaRecordsByName/{N('Fakeus notrealis')}?like=false&marine_only=true"),
    ("unknown AphiaID 999999999            ", "/AphiaRecordByAphiaID/999999999"),
    ("AphiaID 'abc'                        ", "/AphiaRecordByAphiaID/abc"),
    ("name with authority, ByName          ", f"/AphiaRecordsByName/{N('Delphinus delphis Linnaeus, 1758')}?like=false&marine_only=true"),
    ("lower-case name                      ", f"/AphiaRecordsByName/{N('delphinus delphis')}?like=false&marine_only=true"),
    ("'Gadus morhua', like left at default ", f"/AphiaRecordsByName/{N('Gadus morhua')}"),
    ("Homo sapiens, marine_only=true       ", f"/AphiaRecordsByName/{N('Homo sapiens')}?like=false&marine_only=true"),
    ("Homo sapiens, marine_only=false      ", f"/AphiaRecordsByName/{N('Homo sapiens')}?like=false&marine_only=false"),
    ("Delphinus orca (two homonyms)        ", f"/AphiaRecordsByName/{N('Delphinus orca')}?like=false&marine_only=true"),
    ("record of unaccepted 148730          ", "/AphiaRecordByAphiaID/148730"),
    ("classification of unaccepted 148730  ", "/AphiaClassificationByAphiaID/148730"),
    ("vernaculars of unaccepted 148730     ", "/AphiaVernacularsByAphiaID/148730"),
    ("distributions of unaccepted 148730   ", "/AphiaDistributionsByAphiaID/148730"),
    ("ByNames (exact) Gadus morua          ", "/AphiaRecordsByNames?scientificnames[]=" + N("Gadus morhua") + "&scientificnames[]=" + N("Gadus morua") + "&like=false"),
    ("MatchNames typo 'Delphinus delfis'   ", "/AphiaRecordsByMatchNames?scientificnames[]=" + N("Delphinus delfis")),
    ("MatchNames with authorships[]        ", "/AphiaRecordsByMatchNames?scientificnames[]=" + N("Delphinus orca") + "&authorships[]=" + N("Temminck & Schlegel, 1841")),
    ("MatchNames without []                ", "/AphiaRecordsByMatchNames?scientificnames=" + N("Gadus morhua")),
    ("MatchNames, 51 names                 ", "/AphiaRecordsByMatchNames?" + "&".join(["scientificnames[]=" + N("Gadus morhua")] * 51)),
    ("synonyms of 137094, offset=51        ", "/AphiaSynonymsByAphiaID/137094?offset=51"),
):
    print(f"{label} {brief(raw(path))}")

h = raw("/AphiaRecordByAphiaID/137094")["headers"]
print("\nheaders:", {k: h.get(k) for k in ("content-type", "cache-control", "etag", "last-modified", "retry-after", "access-control-allow-origin",
                                            "x-ratelimit-limit", "x-ratelimit-remaining", "content-encoding")})
print("Source: WoRMS (World Register of Marine Species), hosted by VLIZ, via https://www.marinespecies.org/rest.")
```

Output (second run, 2026-11-26 00:41 UTC; the first run printed `access-control-allow-origin None` on the CORS line, because a cross-origin page cannot read that header, so the line now lists the headers the page can read):

```text
https://www.marinespecies.org/robots.txt HTTP 200 text/plain: ['User-agent: *', 'Disallow: /structure', 'Disallow: /export', 'Crawl-delay: 1']

https://www.marinespecies.org/about.php#terms HTTP 200
  found: 'The text on the WoRMS pages is open-access under the terms of the Creative Commons Attribution Licen'
  found: 'This License permits unrestricted use, provided it is cited as requested on the WoRMS webpages'
  found: 'Images are by default open-access under the terms of the CC BY-NC-SA license'
  found: 'Re-distribution of the entire database is not permitted, unless by prior written agreement'
  found: 'We strongly encourage the use of the on-line tools and available webservices'
  found: 'WoRMS Editorial Board (2026). World Register of Marine Species. Available from https://www.marinespe'
  found: 'doi:10.14284/170'
  found: 'Individual pages are individually authored and dated'
  found: 'If the data from WoRMS constitute a substantial proportion of the records used in analyses, the chie'
  words scrap/AI/ML/robot/crawl/non-commercial: none

https://www.marinespecies.org/aphia.php?p=webservice HTTP 200
  found: "Don't use the webservice to harvest WoRMS completely, you can request a database dump"
  found: 'Please, let us know if you are using the webservice'
  rate words: none

https://www.marinespecies.org/aphia.php?p=taxdetails&id=137094 HTTP 200: title '🐴 WoRMS - World Register of Marine Species - Delphinus delphis Linnaeus, 1758'
  'AphiaID 137094' found; 'accepted' found; 'Delphinidae' found

cross-origin fetch() from https://example.com: HTTP 200 application/json, body readable: True; headers JS can read: ['content-length', 'content-type']

unknown name                          HTTP 204 - 0B: (empty body)
unknown AphiaID 999999999             HTTP 204 - 0B: (empty body)
AphiaID 'abc'                         HTTP 400 application/json 177B: { "code": 400, "success": false, "errors": [ { "type": "validation_error", "message": "id must be a valid integer." } ] }
name with authority, ByName           HTTP 204 - 0B: (empty body)
lower-case name                       HTTP 200 application/json 949B: 1 records: Delphinus delphis [accepted, exact]
'Gadus morhua', like left at default  HTTP 200 application/json 6555B: 7 records: Gadus morhua [accepted, like], Gadus morhua callarias [unaccepted, like], Gadus morhua kildinensis [unaccepted, like], Gadus morhua macroce
Homo sapiens, marine_only=true        HTTP 204 - 0B: (empty body)
Homo sapiens, marine_only=false       HTTP 200 application/json 835B: 1 records: Homo sapiens [accepted, exact]
Delphinus orca (two homonyms)         HTTP 200 application/json 1912B: 2 records: Delphinus orca [unaccepted, exact], Delphinus orca [unaccepted, exact]
record of unaccepted 148730           HTTP 200 application/json 946B: Delphinus orca [unaccepted] -> Orcinus orca
classification of unaccepted 148730   HTTP 200 application/json 1102B: {"AphiaID":1,"rank":"Superdomain","scientificname":"Biota","child":{"AphiaID":2,"rank":"Kingdom","scientificna
vernaculars of unaccepted 148730      HTTP 204 - 0B: (empty body)
distributions of unaccepted 148730    HTTP 204 - 0B: (empty body)
ByNames (exact) Gadus morua           HTTP 200 application/json 915B: 2 lists: Gadus morhua Linnaeus, 1758 [exact] -> Gadus morhua | []
MatchNames typo 'Delphinus delfis'    HTTP 200 application/json 1893B: 1 lists: Delphinus delphis Linnaeus, 1758 [near_2] -> Delphinus delphis, Delphinus (Delphis) Gray, 1864 [near_2] -> Delphinus
MatchNames with authorships[]         HTTP 200 application/json 967B: 1 lists: Delphinus orca Temminck & Schlegel, 1841 [exact] -> Grampus griseus
MatchNames without []                 HTTP 400 application/json 183B: { "code": 400, "success": false, "errors": [ { "type": "validation_error", "message": "scientificnames must be an array." } ] }
MatchNames, 51 names                  HTTP 400 application/json 196B: { "code": 400, "success": false, "errors": [ { "type": "validation_error", "message": "scientificnames must not exceed 50 element(s)." } ] }
synonyms of 137094, offset=51         HTTP 204 - 0B: (empty body)

headers: {'content-type': 'application/json', 'cache-control': None, 'etag': None, 'last-modified': None, 'retry-after': None, 'access-control-allow-origin': '*', 'x-ratelimit-limit': None, 'x-ratelimit-remaining': None, 'content-encoding': None}
Source: WoRMS (World Register of Marine Species), hosted by VLIZ, via https://www.marinespecies.org/rest.
```

### 3. Same API with Python urllib: robots check for every agent, a name list (exact first, fuzzy for the rest), one JSON file per run (no browser)

Sends a descriptive User-Agent. Exact names go through `AphiaRecordsByNames` (500 a call), and only the names that found nothing go to TAXAMATCH (50 a call), which is slower and looser. Writes `names.csv` (one row per input name) and `species.json` (one entry per accepted AphiaID, with the citation and access time) into the folder given as the first argument. `MAX_NAMES` keeps it a lookup, not a copy of the register.

```python
import csv, email.utils, json, sys, time, urllib.error, urllib.request, urllib.robotparser
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

API = "https://www.marinespecies.org/rest"
UA = "worms-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]
NAMES = ["Delphinus delphis", "Gadus morhua", "Gadus morua", "Carcharodon carcharias", "Orcinus orca",
         "Mytilus edulis", "Thunnus thynnus", "Delphinus orca", "Fakeus notrealis"]
MAX_NAMES = 500   # a working list, not a copy of the register: WoRMS says "Don't use the webservice to harvest WoRMS completely"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "worms_out")
stats = Counter()
last = [0.0]

def retry_wait(value, default=10):
    """Retry-After as delay-seconds or an HTTP date -> seconds to wait; missing or unreadable -> default."""
    v = (value or "").strip()
    if v.isdigit():
        return int(v)
    try:
        return max(0, int((email.utils.parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()) + 1)
    except (TypeError, ValueError):
        return default

def get(path):
    """GET API + path -> parsed JSON, or None on HTTP 204 ("Nothing found"). Serial, at least 1.2 s apart
    (robots.txt Crawl-delay: 1). Waits once on 429, 500, 502, 503, 504 or a network error (Retry-After in seconds or as an HTTP date,
    else 10 s; over 120 s exits). Exits on a 400 with WoRMS's validation message, or on anything else."""
    url = API + path
    for attempt in range(2):
        time.sleep(max(0, 1.2 - (time.time() - last[0])))
        last[0] = time.time()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"}), timeout=90) as r:
                stats["calls"] += 1
                body = r.read()
                stats["bytes"] += len(body)
                if r.status == 204:
                    stats["204"] += 1
                    return None
                if not body:
                    sys.exit(f"{url}: HTTP {r.status} with an empty body: stop")
                return json.loads(body)
        except urllib.error.HTTPError as e:
            stats["calls"] += 1
            body = e.read().decode("utf-8", "replace")
            if attempt == 0 and e.code in (429, 500, 502, 503, 504):
                wait = retry_wait(e.headers.get("Retry-After"))
                if wait > 120:
                    sys.exit(f"{url}: server asks to wait {wait} s: stopping")
                time.sleep(wait)
                continue
            try:
                msg = "; ".join(x["message"] for x in json.loads(body)["errors"])
            except (ValueError, KeyError, TypeError):
                msg = " ".join(body.split())[:150]
            sys.exit(f"HTTP {e.code} {url}: {msg}")
        except OSError as e:   # DNS, refused connection, timeout, reset
            if attempt == 0:
                time.sleep(10)
                continue
            sys.exit(f"{url}: {e}")

def batches(names, most, max_url=6000):
    """Up to `most` names per call and at most max_url bytes of names in the URL: a GET with 200 names (8 KB URL)
    worked, 300 names (12 KB) got HTTP 414 and 500 names (20 KB) HTTP 400, before the API itself saw them."""
    out, cur, size = [], [], 0
    for n in names:
        add = len("scientificnames[]=" + quote(n)) + 1
        if cur and (len(cur) == most or size + add > max_url):
            out.append(cur)
            cur, size = [], 0
        cur.append(n)
        size += add
    return out + ([cur] if cur else [])

def names_query(names):
    return "&".join("scientificnames[]=" + quote(n) for n in names)

def per_name(path, part):
    """One result list per name, in input order (HTTP 204 = none matched); any other shape stops."""
    res = get(path)
    if res is None:
        return [[]] * len(part)
    if not isinstance(res, list) or len(res) != len(part):
        sys.exit(f"{path.split('?')[0]}: {len(res) if isinstance(res, list) else type(res).__name__} result lists for {len(part)} names: stop")
    return res

# 1. robots.txt: one '*' group (Disallow /structure, /export; Crawl-delay 1), no named AI-agent group
rp = urllib.robotparser.RobotFileParser("https://www.marinespecies.org/robots.txt")
with urllib.request.urlopen(urllib.request.Request(rp.url, headers={"User-Agent": UA}), timeout=30) as r:
    lines = r.read().decode("utf-8", "replace").splitlines()
    rp.parse(lines)
    print(f"{rp.url}: HTTP {r.status} {r.headers.get('Content-Type')}, {len(lines)} lines, "
          f"groups {[l.strip() for l in lines if l.lower().startswith('user-agent')]}")
for p in ("/rest/AphiaRecordsByNames", "/rest/AphiaRecordsByMatchNames", "/rest/AphiaRecordByAphiaID/137094",
          "/rest/AphiaClassificationByAphiaID/137094", "/rest/AphiaVernacularsByAphiaID/137094",
          "/rest/AphiaDistributionsByAphiaID/137094", "/rest/AphiaSynonymsByAphiaID/137094",
          "/aphia.php?p=taxdetails&id=137094", "/about.php"):
    ok = all(rp.can_fetch(a, "https://www.marinespecies.org" + p) for a in AGENTS)
    delays = sorted({rp.crawl_delay(a) for a in AGENTS})
    print(f"  robots {p:<44} {'allowed' if ok else 'DISALLOWED'} for all {len(AGENTS)} agents; crawl-delay {delays}")
    if not ok:
        sys.exit("robots.txt now disallows a path this skill uses: stop")

now = datetime.now(timezone.utc)
names = list(dict.fromkeys(n.strip() for n in NAMES if n.strip()))
if len(names) > MAX_NAMES:
    sys.exit(f"{len(names)} names: over MAX_NAMES={MAX_NAMES}; this is a lookup, not a harvest")
print(f"\nWoRMS (World Register of Marine Species), {len(names)} names, checked {now:%Y-%m-%d %H:%M} UTC")

# 2. Exact names first (AphiaRecordsByNames: the API takes 500 names, the GET URL fewer; see batches()), TAXAMATCH only for the rest (up to 50 a call)
found = {}
for part in batches(names, 500):
    for n, recs in zip(part, per_name(f"/AphiaRecordsByNames?{names_query(part)}&like=false&marine_only=true", part)):
        if recs:
            found[n] = ("exact", recs)
left = [n for n in names if n not in found]
for part in batches(left, 50):
    for n, recs in zip(part, per_name(f"/AphiaRecordsByMatchNames?{names_query(part)}&marine_only=true", part)):
        found[n] = ("fuzzy", recs or [])
print(f"  exact: {sum(1 for v in found.values() if v[0] == 'exact')}, sent to TAXAMATCH: {len(left)}")

rows, species = [], {}
for n in names:
    how, recs = found[n]
    targets = {r["valid_AphiaID"] for r in recs}   # None = a record with no accepted name: never pick past it
    if len(targets) != 1 or None in targets:
        why = "no match" if not recs else ("no accepted name: " if None in targets else "ambiguous: ") + "; ".join(
            f"{r['scientificname']} {r['authority']} -> {r['valid_name']} ({r['valid_AphiaID']})" for r in recs)
        rows.append({"input": n, "match": how, "AphiaID": "", "accepted_name": "", "note": why})
        print(f"  {n!r}: {why}")
        continue
    aid, r0 = targets.pop(), recs[0]
    rows.append({"input": n, "match": f"{how}/{r0['match_type']}", "AphiaID": aid, "accepted_name": r0["valid_name"],
                 "note": f"{r0['scientificname']} is {r0['status']}" + (f" ({r0['unacceptreason']})" if r0["unacceptreason"] else "")})
    species.setdefault(aid, None)

# 3. Details once per accepted AphiaID
for aid in species:
    rec = get(f"/AphiaRecordByAphiaID/{aid}")
    node, tree = get(f"/AphiaClassificationByAphiaID/{aid}"), []
    while node:
        tree.append({"rank": node["rank"], "name": node["scientificname"], "AphiaID": node["AphiaID"]})
        node = node.get("child")
    vern = get(f"/AphiaVernacularsByAphiaID/{aid}") or []
    dist = get(f"/AphiaDistributionsByAphiaID/{aid}") or []
    syn, off = [], 1
    while True:
        page = get(f"/AphiaSynonymsByAphiaID/{aid}" + (f"?offset={off}" if off > 1 else "")) or []
        syn += page
        if len(page) < 50:
            break
        off += 50
    if rec["status"] != "accepted" or tree[-1]["AphiaID"] != aid:
        sys.exit(f"AphiaID {aid}: status {rec['status']!r}, classification ends at {tree[-1]}: stop")
    places = sorted({(d["locality"], d["locationID"], d["higherGeography"]) for d in dist if d["recordStatus"] == "valid"}, key=str)
    species[aid] = {
        "AphiaID": aid, "name": rec["scientificname"], "authority": rec["authority"], "rank": rec["rank"], "status": rec["status"],
        "url": rec["url"], "lsid": rec["lsid"], "modified": rec["modified"],
        "habitat": {k[2:].lower(): rec[k] for k in ("isMarine", "isBrackish", "isFreshwater", "isTerrestrial")}, "isExtinct": rec["isExtinct"],
        "classification": tree,
        "common_names": sorted({(v["language_code"], v["vernacular"]) for v in vern}),
        "distribution_valid": [{"locality": l, "locationID": i, "higherGeography": g} for l, i, g in places],
        "distribution_records": len(dist), "distribution_not_valid": sum(1 for d in dist if d["recordStatus"] != "valid"),
        "synonyms": [{"AphiaID": s["AphiaID"], "name": s["scientificname"], "authority": s["authority"],
                      "reason": s["unacceptreason"] or s["status"]} for s in syn],
        "page_citation": rec["citation"],
    }
    s = species[aid]
    eng = [v for l, v in s["common_names"] if l == "eng"]
    oceans = Counter(p["higherGeography"] for p in s["distribution_valid"] if p["higherGeography"])
    print(f"  {aid:>7} {s['name']} {s['authority']}: {' > '.join(t['name'] for t in tree if t['rank'] in ('Kingdom', 'Phylum', 'Class', 'Order', 'Family'))}; "
          f"{len(s['common_names'])} common names (eng {len(eng)}: {', '.join(eng[:3]) or 'none'}{', ...' if len(eng) > 3 else ''}); "
          f"{len(places)} valid places, top regions {dict(oceans.most_common(2))}; {len(syn)} synonyms")

OUT.mkdir(parents=True, exist_ok=True)
cite = (f"WoRMS Editorial Board ({now:%Y}). World Register of Marine Species. Available from https://www.marinespecies.org at VLIZ. "
        f"Accessed {now:%Y-%m-%d}. doi:10.14284/170")
(OUT / "species.json").write_text(json.dumps({"source": "WoRMS (World Register of Marine Species), hosted by VLIZ, CC BY",
                                              "citation": cite, "accessed": now.isoformat(timespec="seconds"),
                                              "species": list(species.values())}, ensure_ascii=False, indent=1))
with open(OUT / "names.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["input", "match", "AphiaID", "accepted_name", "note"])
    w.writeheader()
    w.writerows(rows)
print(f"\nnames.csv: {len(rows)} rows ({sum(1 for r in rows if r['AphiaID'])} resolved), species.json: {len(species)} species, "
      f"{(OUT / 'species.json').stat().st_size:,} bytes")
for r in rows:
    print(f"  {r['input']:<24} {r['match']:<16} {str(r['AphiaID']):>7} {r['accepted_name']:<24} {r['note'][:80]}")
print(f"totals: {stats['calls']} API calls ({stats['204']} HTTP 204), {stats['bytes']:,} bytes")
print("Cite: " + cite)
```

Output (second run, 2026-11-26 00:41 UTC; the 00:38 UTC run printed the same data and totals, but cut the English names at 70 characters, mid-word):

```text
https://www.marinespecies.org/robots.txt: HTTP 200 text/plain, 4 lines, groups ['User-agent: *']
  robots /rest/AphiaRecordsByNames                    allowed for all 11 agents; crawl-delay [1]
  robots /rest/AphiaRecordsByMatchNames               allowed for all 11 agents; crawl-delay [1]
  robots /rest/AphiaRecordByAphiaID/137094            allowed for all 11 agents; crawl-delay [1]
  robots /rest/AphiaClassificationByAphiaID/137094    allowed for all 11 agents; crawl-delay [1]
  robots /rest/AphiaVernacularsByAphiaID/137094       allowed for all 11 agents; crawl-delay [1]
  robots /rest/AphiaDistributionsByAphiaID/137094     allowed for all 11 agents; crawl-delay [1]
  robots /rest/AphiaSynonymsByAphiaID/137094          allowed for all 11 agents; crawl-delay [1]
  robots /aphia.php?p=taxdetails&id=137094            allowed for all 11 agents; crawl-delay [1]
  robots /about.php                                   allowed for all 11 agents; crawl-delay [1]

WoRMS (World Register of Marine Species), 9 names, checked 2026-11-26 00:41 UTC
  exact: 7, sent to TAXAMATCH: 2
  'Delphinus orca': ambiguous: Delphinus orca Linnaeus, 1758 -> Orcinus orca (137102); Delphinus orca Temminck & Schlegel, 1841 -> Grampus griseus (137098)
  'Fakeus notrealis': no match
   137094 Delphinus delphis Linnaeus, 1758: Animalia > Chordata > Mammalia > Cetartiodactyla > Delphinidae; 90 common names (eng 6: common dolphin, saddle-backed dolphin, sea porpoise, ...); 16 valid places, top regions {'North Atlantic Ocean': 4, 'North Sea': 2}; 24 synonyms
   126436 Gadus morhua Linnaeus, 1758: Animalia > Chordata > Teleostei > Gadiformes > Gadidae; 49 common names (eng 2: Atlantic cod, cod); 26 valid places, top regions {'North Atlantic Ocean': 8, 'Belgium': 3}; 18 synonyms
   105838 Carcharodon carcharias (Linnaeus, 1758): Animalia > Chordata > Elasmobranchii > Lamniformes > Lamnidae; 93 common names (eng 17: Tommy, anchovy-eater, blue pointer, ...); 35 valid places, top regions {'North Atlantic Ocean': 4, 'Canada': 2}; 18 synonyms
   137102 Orcinus orca (Linnaeus, 1758): Animalia > Chordata > Mammalia > Cetartiodactyla > Delphinidae; 106 common names (eng 6: grampus, killer whale, killer-trasher, ...); 23 valid places, top regions {'North Atlantic Ocean': 4, 'Gulf of Saint Lawrence': 2}; 38 synonyms
   140480 Mytilus edulis Linnaeus, 1758: Animalia > Mollusca > Bivalvia > Mytilida > Mytilidae; 26 common names (eng 5: bay mussel, blue mussel, common blue mussel, ...); 39 valid places, top regions {'Belgium': 6, 'North Atlantic Ocean': 4}; 22 synonyms
   127029 Thunnus thynnus (Linnaeus, 1758): Animalia > Chordata > Teleostei > Scombriformes > Scombridae; 74 common names (eng 7: Atlantic bluefin tuna, blue-fin tuna, blue-fin tunny, ...); 18 valid places, top regions {'North Atlantic Ocean': 5, 'Canada': 2}; 15 synonyms

names.csv: 9 rows (7 resolved), species.json: 6 species, 75,684 bytes
  Delphinus delphis        exact/exact       137094 Delphinus delphis        Delphinus delphis is accepted
  Gadus morhua             exact/exact       126436 Gadus morhua             Gadus morhua is accepted
  Gadus morua              fuzzy/phonetic    126436 Gadus morhua             Gadus morhua is accepted
  Carcharodon carcharias   exact/exact       105838 Carcharodon carcharias   Carcharodon carcharias is accepted
  Orcinus orca             exact/exact       137102 Orcinus orca             Orcinus orca is accepted
  Mytilus edulis           exact/exact       140480 Mytilus edulis           Mytilus edulis is accepted
  Thunnus thynnus          exact/exact       127029 Thunnus thynnus          Thunnus thynnus is accepted
  Delphinus orca           exact                                             ambiguous: Delphinus orca Linnaeus, 1758 -> Orcinus orca (137102); Delphinus orc
  Fakeus notrealis         fuzzy                                             no match
totals: 32 API calls (0 HTTP 204), 256,371 bytes
Cite: WoRMS Editorial Board (2026). World Register of Marine Species. Available from https://www.marinespecies.org at VLIZ. Accessed 2026-11-26. doi:10.14284/170
```

### 4. curl: one name, a fuzzy list, classification, common names, distribution, synonyms, headers, mistakes

```bash
B=https://www.marinespecies.org/rest
UA="worms-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
# --retry 1 retries once on a timeout or HTTP 408, 429, 500, 502, 503 or 504, 10 s later (or after the server's Retry-After);
# --retry-max-time 120 skips the retry when Retry-After would wait past 120 s. robots.txt asks Crawl-delay: 1, so 1.2 s apart
C=(curl -sS -A "$UA" --max-time 90 --retry 1 --retry-delay 10 --retry-max-time 120)
T=$(mktemp); trap 'rm -f "$T"' EXIT
# 1. a name -> AphiaRecords (like=false: exact name only; spaces as %20). HTTP 204 with an empty body = nothing found
"${C[@]}" --fail "$B/AphiaRecordsByName/Delphinus%20delphis?like=false&marine_only=true" | python3 -c 'import json, sys
for r in json.load(sys.stdin): print(r["AphiaID"], r["scientificname"], r["authority"], r["status"], "->", r["valid_AphiaID"], r["valid_name"], "|", r["rank"], "| match", r["match_type"], "| modified", r["modified"])'
sleep 1.2
"${C[@]}" -o /dev/null -w 'unknown name: HTTP %{http_code}, %{size_download} bytes\n' "$B/AphiaRecordsByName/Fakeus%20notrealis?like=false&marine_only=true"
sleep 1.2
# 2. a list of names, fuzzy (TAXAMATCH, max 50): one result list per name, in order; [] = no match. The [] in scientificnames[] is required
"${C[@]}" --fail -G "$B/AphiaRecordsByMatchNames" --data-urlencode 'scientificnames[]=Gadus morua' \
  --data-urlencode 'scientificnames[]=Delphinus orca' --data-urlencode 'scientificnames[]=Fakeus notrealis' -d marine_only=true -o "$T"
python3 -c 'import json, sys
for i, g in enumerate(json.load(open(sys.argv[1]))): print(i, [(r["scientificname"], r["authority"], r["match_type"], r["status"], "->", r["valid_name"], r["valid_AphiaID"]) for r in g] or "no match")' "$T"
sleep 1.2
# 3. classification (nested "child" objects) -> one line
"${C[@]}" --fail "$B/AphiaClassificationByAphiaID/137094" | python3 -c 'import json, sys
n, out = json.load(sys.stdin), []
while n: out.append(n["rank"] + " " + n["scientificname"]); n = n["child"]
print(" > ".join(out))'
sleep 1.2
# 4. common names: English only, plus the count of languages
"${C[@]}" --fail "$B/AphiaVernacularsByAphiaID/137094" | python3 -c 'import json, sys
v = json.load(sys.stdin); print(len(v), "names in", len({x["language"] for x in v}), "languages; eng:", sorted(x["vernacular"] for x in v if x["language_code"] == "eng"))'
sleep 1.2
# 5. distribution: records repeat per source; recordStatus valid/doubtful; locationID is a Marine Regions MRGID
"${C[@]}" --fail "$B/AphiaDistributionsByAphiaID/137094" | python3 -c 'import json, sys, collections
d = json.load(sys.stdin); print(len(d), "records;", dict(collections.Counter(x["recordStatus"] for x in d)), "| first:", {k: d[0][k] for k in ("locality", "locationID", "higherGeography", "recordStatus", "qualityStatus")})'
sleep 1.2
# 6. synonyms (50 a page; offset=51 is the next page, HTTP 204 when there is none)
"${C[@]}" --fail "$B/AphiaSynonymsByAphiaID/137094" | python3 -c 'import json, sys
s = json.load(sys.stdin); print(len(s), "synonyms, e.g.", [(x["scientificname"], x["authority"], x["unacceptreason"]) for x in s[:3]])'
sleep 1.2
"${C[@]}" -o /dev/null -w 'synonyms offset=51: HTTP %{http_code}\n' "$B/AphiaSynonymsByAphiaID/137094?offset=51"
sleep 1.2
# 7. headers: CORS open; no ETag, Last-Modified, gzip or rate-limit headers; a vliz_webc cookie
"${C[@]}" -D - -o /dev/null -H 'Accept-Encoding: gzip' "$B/AphiaRecordByAphiaID/137094" | tr -d '\r' \
  | grep -iE '^(HTTP/|(content-type|content-encoding|cache-control|etag|last-modified|retry-after|x-rate[a-z-]*|access-control-allow-origin|set-cookie):)'
sleep 1.2
# 8. mistakes: HTTP 400 with {"code", "success", "errors": [{"type", "message"}]}
for u in "AphiaRecordByAphiaID/abc" "AphiaRecordsByMatchNames?scientificnames=Gadus%20morhua" "AphiaRecordsByMatchNames"; do
  curl -sS -A "$UA" --max-time 60 -o "$T" -w "%{http_code} " "$B/$u"; python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["errors"][0]["message"], " <-", sys.argv[2])' "$T" "$u"; sleep 1.2
done
# 9. robots: one "*" group, Crawl-delay 1
"${C[@]}" https://www.marinespecies.org/robots.txt | tr -d '\r' | paste -sd ' '
echo "Cite: WoRMS Editorial Board ($(date -u +%Y)). World Register of Marine Species. Available from https://www.marinespecies.org at VLIZ. Accessed $(date -u +%F). doi:10.14284/170"
```

Output (second run, 2026-11-26 00:42 UTC; the 00:39 UTC run printed the same apart from the cookie value `vliz_webc2`):

```text
137094 Delphinus delphis Linnaeus, 1758 accepted -> 137094 Delphinus delphis | Species | match exact | modified 2008-08-20T11:25:36.853Z
unknown name: HTTP 204, 0 bytes
0 [('Gadus morhua', 'Linnaeus, 1758', 'phonetic', 'accepted', '->', 'Gadus morhua', 126436)]
1 [('Delphinus orca', 'Linnaeus, 1758', 'exact', 'unaccepted', '->', 'Orcinus orca', 137102), ('Delphinus orca', 'Temminck & Schlegel, 1841', 'exact', 'unaccepted', '->', 'Grampus griseus', 137098)]
2 no match
Superdomain Biota > Kingdom Animalia > Phylum Chordata > Subphylum Vertebrata > Infraphylum Gnathostomata > Megaclass Tetrapoda > Class Mammalia > Subclass Theria > Order Cetartiodactyla > Suborder Cetancodonta > Infraorder Cetacea > Superfamily Odontoceti > Family Delphinidae > Genus Delphinus > Species Delphinus delphis
90 names in 37 languages; eng: ['common dolphin', 'saddle-backed dolphin', 'sea porpoise', 'short-beaked common dolphin', 'short-beaked saddle-backed dolphin', 'short-beaked saddleback dolphin']
19 records; {'valid': 18, 'doubtful': 1} | first: {'locality': 'European waters (ERMS scope)', 'locationID': 'http://marineregions.org/mrgid/7130', 'higherGeography': 'North Atlantic Ocean', 'recordStatus': 'valid', 'qualityStatus': 'unreviewed'}
24 synonyms, e.g. [('Delphinus albimanus', 'Peale, 1848', 'synonym'), ('Delphinus algeriensis', 'Loche, 1860', 'synonym'), ('Delphinus bairdi', 'Norris & Prescott, 1961', 'synonym')]
synonyms offset=51: HTTP 204
HTTP/2 200
access-control-allow-origin: *
content-type: application/json
set-cookie: vliz_webc=vliz_webc1; path=/
400 id must be a valid integer.  <- AphiaRecordByAphiaID/abc
400 scientificnames must be an array.  <- AphiaRecordsByMatchNames?scientificnames=Gadus%20morhua
400 scientificnames is required.  <- AphiaRecordsByMatchNames
User-agent: * Disallow: /structure Disallow: /export Crawl-delay: 1
Cite: WoRMS Editorial Board (2026). World Register of Marine Species. Available from https://www.marinespecies.org at VLIZ. Accessed 2026-11-26. doi:10.14284/170
```

## Fields

| Endpoint / field | Value | Notes |
|---|---|---|
| `AphiaRecordsByName/{name}` | `[AphiaRecord]`, max 50 | `like` defaults to **true** (adds `%`), `marine_only` and `extant_only` default to true, `offset` 1, 51, ... for the next 50; HTTP 204 for no match |
| `AphiaRecordsByNames?scientificnames[]=` | `[[AphiaRecord], ...]` one list per name, in order | exact (`like` defaults to false here), up to 500 names by the docs, but a 12 KB URL (300 names) got HTTP 414; `[]` for a name with no match |
| `AphiaRecordsByMatchNames?scientificnames[]=` | `[[AphiaRecord], ...]` one list per name, in order | TAXAMATCH fuzzy, up to 50 names; an authority may go inside the name or in `authorships[]`; `match_authority` defaults to true |
| AphiaRecord | `AphiaID, url, scientificname, authority, status, unacceptreason, taxonRankID, rank, valid_AphiaID, valid_name, valid_authority, parentNameUsageID, originalNameUsageID, kingdom, phylum, class, order, family, genus, citation, lsid, isMarine, isBrackish, isFreshwater, isTerrestrial, isExtinct, match_type, modified` | habitat flags are `1`, `0` or `null`; `modified` is the record's last edit in GMT (`2008-08-20T11:25:36.853Z` for 137094); `lsid` `urn:lsid:marinespecies.org:taxname:137094`; `citation` is the page citation naming its source database (World Cetacea Database, FishBase) and the access date |
| `match_type` | `exact`, `exact_subgenus`, `exact_replaced`, `like`, `phonetic`, `near_1`, `near_2`, `near_3`, `match_quarantine`, `match_deleted` | from the OpenAPI file; `Gadus morua` -> `phonetic`, `Delphinus delfis` -> `near_2` |
| `status` | `accepted`, `unaccepted`, and others such as `junior subjective synonym`, `superseded combination`, `misspelling - incorrect subsequent spelling` (all three among the 50 `AphiaRecordsByName/Gadus?like=true` records); technical `quarantined`, `deleted` (OpenAPI file) | `unacceptreason` is free text: `synonym`, `basionym`, `preoccupied`, `Spelling variation`, `misspelling of rectipinna` |
| `AphiaClassificationByAphiaID/{id}` | nested `{AphiaID, rank, scientificname, child}`, `child: null` at the end | starts at `Superdomain Biota`; 15 levels for *Delphinus delphis* including sub-, infra- and super-ranks |
| `AphiaVernacularsByAphiaID/{id}` | `[{vernacular, language_code, language}]` | three-letter language codes, not documented in the OpenAPI file (`eng`, `dan`, `ale`; `ypk` = "Yupik languages"); 90 names in 37 languages for 137094; HTTP 204 if none |
| `AphiaDistributionsByAphiaID/{id}` | `[{locality, locationID, higherGeography, higherGeographyID, recordStatus, typeStatus, establishmentMeans, invasiveness, occurrence, decimalLatitude, decimalLongitude, qualityStatus}]` | `locationID` is a Marine Regions URL (`http://marineregions.org/mrgid/7130`); `recordStatus` `valid`, `doubtful` or `inaccurate` and `qualityStatus` `checked`, `trusted` or `unreviewed` (OpenAPI file; 137094 and 126436 showed only `valid`/`doubtful` and `trusted`/`unreviewed`); lat/lon were `null` in all 54 records checked (137094 and 126436) |
| `AphiaSynonymsByAphiaID/{id}` | `[AphiaRecord]`, 50 a page | `offset=51` for the next page; HTTP 204 when there is none |
| errors | HTTP 400 `{"code": 400, "success": false, "errors": [{"type": "validation_error", "message": ...}]}` | "id must be a valid integer.", "scientificnames must be an array.", "scientificnames is required.", "scientificnames must not exceed 50 element(s)." |
| response headers | `content-type: application/json`, `access-control-allow-origin: *`, `set-cookie: vliz_webc=vliz_webc1` (or `vliz_webc2`) | no `ETag`, `Last-Modified`, `Content-Encoding`, `Retry-After` or rate-limit headers; HTTP 204 has no content type; TAXAMATCH answers (with a match or HTTP 204) also send `cache-control: no-store, no-cache, must-revalidate` and a `PHPSESSID` session cookie, the other endpoints no `Cache-Control` |

## Gotchas

- **HTTP 204 means "Nothing found", with an empty body.** Not `[]` and not 404: `json.loads("")` raises. `get()` in every block returns `None` for it. Unknown names, unknown AphiaIDs, no common names, no distribution and the page after the last synonym page are all 204.
- **`like` defaults to true on `AphiaRecordsByName`.** `Gadus morhua` without `like=false` returns 7 records (the species plus `Gadus morhua callarias` and other subspecies, `match_type` `like`). Always send `like=false` for one exact name.
- **`marine_only` defaults to true.** `Homo sapiens` is HTTP 204 with it and found (AphiaID 1455977, `isMarine` 0) with `marine_only=false`. Send `marine_only=false` for freshwater or terrestrial taxa. `extant_only` also defaults to true (not tested with fossils).
- **Homonyms.** `Delphinus orca` matches two unaccepted names: Linnaeus, 1758 (-> *Orcinus orca*, 137102) and Temminck & Schlegel, 1841 (-> *Grampus griseus*, 137098). Do not take the first one: blocks 1 and 3 report it as ambiguous. Add the authority to the name for `AphiaRecordsByMatchNames` (`Delphinus orca Linnaeus, 1758`) or pass `authorships[]`; `AphiaRecordsByName` with the authority inside the name is HTTP 204.
- **Fuzzy matches can be a different rank.** `Delphinus delfis` (`near_2`) matches *Delphinus delphis* and the subgenus `Delphinus (Delphis)` Gray, 1864. Block 1 keeps the best match class and species-rank candidates for a two-word name; check `match_type` before trusting anything that is not `exact`.
- **Use `valid_AphiaID`.** An unaccepted ID keeps its old record: AphiaID 148730's classification ends at *Delphinus orca* under genus *Delphinus*, and its common names and distribution are HTTP 204. Follow `valid_AphiaID` (blocks 1 and 3 check the record they fetch is `accepted`).
- **`scientificnames[]` needs the brackets.** `scientificnames=Gadus%20morhua` is HTTP 400 "must be an array". Raw `[]` and `%5B%5D` (curl `--data-urlencode`) both work. 51 names in one TAXAMATCH call is HTTP 400.
- **Names are case-insensitive and `+` works as a space.** `delphinus delphis` and `Delphinus+delphis` both return 137094; `quote()` (`%20`) is what the blocks send.
- **Distribution repeats places.** Each source adds its own record: *Delphinus delphis* has 19 records at 17 places (Westerschelde and the Belgian EEZ twice), one `doubtful`. Group by `locality` and `locationID`, and keep `recordStatus` (block 1 prints the doubtful-only places apart). The places are a mix of oceans, EEZs, estuaries and a shipwreck, not a range map.
- **Common names are recorded names, not checked translations.** The English list for *Carcharodon carcharias* has 17 entries, from "great white shark" to "Tommy"; *Delphinus delphis* includes "sea porpoise". Show them as "names recorded in WoRMS" and pick by `language_code`.
- **Two citations.** Cite WoRMS itself (the Editorial Board line, current year, access date, doi:10.14284/170) and, when you use one taxon page, its `citation` field, which names the source database (World Cetacea Database, FishBase); the about page asks for global, regional or thematic registers to be cited "accordingly". The blocks compute the year and access date from the UTC clock; the about page showed "(2026)" on 2026-11-26.
- **Cross-origin pages see only two headers.** From example.com, `fetch()` read the body but only `content-type` and `content-length`, so a `Retry-After` would be invisible. Block 1 runs from a www.marinespecies.org/rest answer.
- **No caching headers, no gzip.** No `ETag` or `Last-Modified`, and `Accept-Encoding: gzip` still returned an uncompressed body. Cache by AphiaID with `modified` yourself. A `vliz_webc` cookie comes back on every answer (and a `PHPSESSID` on TAXAMATCH answers); none is needed, and the blocks send no cookies (`credentials: 'omit'`, plain urllib and curl).
- **No full dumps.** "Re-distribution of the entire database is not permitted" and "Don't use the webservice to harvest WoRMS completely". Look up the names you have; for a copy, the about page says "In exceptional cases, institutes may request a copy of the database" with a form (taxonomic data only, no distributions). If WoRMS is a large share of the records in an analysis, the about page asks you to contact the chief editors.
- **No images, no logo.** Images are CC BY-NC-SA by default; the blocks fetch none and use no WoRMS logo.
- **Tab marker.** The harness puts a horse emoji in the tab title (block 2's taxon page title starts with it); the blocks check `location.origin` and the page text, not the title.

## What does not work

- **An authority inside the name for `AphiaRecordsByName`**: HTTP 204; use `AphiaRecordsByMatchNames` with the authority or `authorships[]` (blocks 2 and 4).
- **`scientificnames` without `[]`, no names, more than 50 names for TAXAMATCH, a non-integer AphiaID**: HTTP 400 `validation_error` (blocks 2 and 4).
- **Common names or distribution for an unaccepted AphiaID**: HTTP 204; use `valid_AphiaID`.
- **`/rest/api-docs`, `/rest/swagger.json`, `/rest/openapi.json`**: HTTP 404; the OpenAPI file is `/rest/api-docs/openapi.json`.
- **Conditional GETs and gzip**: no `ETag`, `Last-Modified` or `Content-Encoding`.
- **Not tested:** a 429 or 503 (never seen), synonym lists longer than 50 (no taxon here had more than 38, so the paging loop only ever saw one page and then a 204), `extant_only=false` and fossil taxa, the SOAP service, `AphiaRecordsByDate`, attributes, sources, external IDs, children, `AphiaRecordsByVernacular`, and the `Ajax` name-suggestion endpoint.
