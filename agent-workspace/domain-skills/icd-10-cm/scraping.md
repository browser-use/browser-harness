# ICD-10-CM via the NLM Clinical Table Search Service (clinicaltables.nlm.nih.gov) - Find the Diagnosis Code for a Condition in Plain Words or Look Up a Code's Name (REST API, no key)

Field-tested against clinicaltables.nlm.nih.gov on 2026-11-16 (the logged runs were 23:30-23:35 UTC; blocks 1 and 3 re-run on 2026-11-17, 00:39-00:43 UTC, after review fixes) using a fresh Browser Use cloud browser (logged out) plus Python `urllib` and `curl` from a Linux machine. 5 browser page loads (an API JSON page, robots.txt, the home page, the FAQ) and 40 in-page `fetch()` calls (block 1 was also run for E11, I21.0, high blood pressure, S72.001A, hypertension, diabtes and s72.001a), 73 curl calls (1 of them robots.txt) and 13 urllib calls (2 of them robots.txt), all serial at 0.25 s or more spacing: every call was HTTP 200 except the deliberate HTTP 400 probes and the HTTP 404 of robots.txt. No 429, no 503, no challenge, no key, no login.

robots.txt (checked 2026-11-16, curl, the cloud browser and `urllib.robotparser`): https://clinicaltables.nlm.nih.gov/robots.txt answers HTTP 404 with an HTML page `Cannot GET /robots.txt`, so the host has no rules and no named AI-agent groups; under RFC 9309 (section 2.3.1.3) an unavailable robots.txt (4xx) means a crawler "MAY access any resources", and Python's parser treats it as allow-all for GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider (block 3 checks all 11 agents). Terms: the FAQ https://clinicaltables.nlm.nih.gov/faq.html says the Clinical Table Search Service (CTSS) "is open to the general public and free of charge", "Registration is not required to use this service" and "THIS SERVICE IS PROVIDED "AS IS"". It adds that "some datasets, such as LOINC, have their own terms of use" listed in the home page "Details" column; the ICD-10-CM row says only "From CDC" and "Data version: 2027; 74,879 records", and the Medical conditions row "From the NLM PHR & Regenstrief Institute" with "Data version: 2026-10-01; 2,418 records", with no extra terms for either. No AI/ML, scraping, automated-access or non-commercial clause. Naming: the FAQ says "neither the names of the National Library of Medicine (NLM), the Lister Hill National Center for Biomedical Communications (LHNCBC), the National Institutes of Health (NIH), nor the names of any of the software contributors may be used to endorse or promote products derived from this service without specific prior written permission", so this skill names the source only as "ICD-10-CM via the NLM Clinical Table Search Service" in plain text, uses no NLM, NIH or HHS logo or branding, and is not affiliated with or endorsed by NLM, LHNCBC, NIH or CDC.

**Privacy:** the FAQ says the service logs "the complete request URL (including the search parameters)" and "Do NOT include any PHI (Protected Health Information) or PII (Personally Identifiable Information) information in your requests." Send condition words or codes only, never a patient's name, date of birth, record number or note text.

## Quick summary

- **No scraping.** `GET https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search?sf=code,name&terms=type%202%20diabetes&maxList=5` -> `[94, ["E11.65","E11.9","E10.A2","E11.21","E11.36"], null, [["E11.65","Type 2 diabetes mellitus with hyperglycemia"], ...]]`. `?sf=code&terms=E11.9&q=code:E11.9` -> `[1, ["E11.9"], null, [["E11.9","Type 2 diabetes mellitus without complications"]]]`. No key, `Access-Control-Allow-Origin: *`.
- **Answer (ICD-10-CM data version 2027, 74,879 codes; run 2026-11-16, 23:32 UTC):** "type 2 diabetes" matches **94 codes**; **93** contain the phrase (**87 in E11**, **6 in O24**, pre-existing type 2 diabetes in pregnancy, childbirth or the puerperium), and 1 is a false hit (**E10.A2** "Type 1 diabetes mellitus, presymptomatic, Stage 2"). **E11.9 = "Type 2 diabetes mellitus without complications"**.
- **The code table only knows official wording.** "heart attack", "high blood pressure" and "sprained ankle" all return `[0, [], null, []]`. The same service's Medical conditions table (`/api/conditions/v3/search`) has lay synonyms and suggested codes: "heart attack" -> I21.9 "Acute myocardial infarction, unspecified" and I21.4 (NSTEMI); "high blood pressure" -> I10 "Essential (primary) hypertension". Block 1 uses it only after a 0 and confirms every suggested code in the ICD-10-CM table.
- **Search is ANDed prefix matching, not a phrase.** Every word must start a word in the code or name, in any order: "type 2 diabetes" also hits "Type 1 ... Stage 2", "with" also hits "without", and "hypertension" misses I11.9 "Hypertensive heart disease without heart failure". Block 1 splits phrase matches from loose ones.
- **Silent failure:** lay words, typos (`diabtes`), a code without its dot (`E119`) and words sent with the default `sf=code` are all HTTP 200 with total 0. Category headers (E11, I21.0) are not codes in the table; `terms=E11` lists the 87 codes under it. Of the mistakes tried, only a missing `terms`, `count` over 500 or `offset + count` over 7,500 is an HTTP 400 `Bad request: See main page for documentation.` (HTML, not JSON).
- **Rate limit:** the FAQ says "The advised maximum request rate is 25 requests per second. This is a soft limit", asks for a heads-up via the NLM Support Center above 50 requests/second regularly or 50,000 calls per day, says to check "X-RateLimit-Limit", "Retry-After" and that "The service may respond with status code 503 if the system is overwhelmed regardless of your request rate". All blocks pace 0.25 s per call, serial; blocks 1 and 3 wait `Retry-After` (seconds or an HTTP date; default 60 s, at most 120 s) once on 429/5xx; block 3 caches answers on disk for 12 h, matching the server's `Cache-Control: public, max-age=43200`.

## What works

### 1. Plain words or a code -> ICD-10-CM codes and names (browser)

`on_ctss_tab()` opens one logged-out clinicaltables.nlm.nih.gov API JSON page, so `fetch()` is same-origin. `get()` returns the parsed `[total, codes, extra, rows]` array on HTTP 200, waits once on 429/500/502/503/504 and otherwise raises. A query shaped like a code is looked up exactly (`q=code:...`), and a non-code like E11 lists the codes under it. Words go to the code table with `sf=code,name`, paged 500 at a time; rows that do not contain the words as a phrase are printed apart. Only when the code table returns 0 does it ask the conditions table for lay synonyms, then confirms each suggested code. It first reads the ICD-10-CM data version from the home page HTML and prints it with the answer. 8 `fetch()` calls in all for the 3 queries.

```python
import json, re, time, urllib.parse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

QUERIES = ["type 2 diabetes", "E11.9", "heart attack"]  # plain words or a code. Never patient data (FAQ: no PHI/PII)

SITE = "https://clinicaltables.nlm.nih.gov"
ICD = "/api/icd10cm/v3/search"
COND = "/api/conditions/v3/search"  # same service: ~2,400 conditions with lay synonyms and suggested ICD-10-CM codes
PAUSE = 0.25  # FAQ: "advised maximum request rate is 25 requests per second". Stay serial and far below it.
CODE_RE = re.compile(r"[A-Z][0-9][0-9A-Z](\.[0-9A-Z]{1,4})?")  # E11, E11.9, S72.001A (the API needs the dot)

def on_ctss_tab():
    """fetch() runs same-origin from a logged-out clinicaltables.nlm.nih.gov JSON page. Reuse it."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(SITE + ICD + "?sf=code,name&terms=E11.9")
    wait_for_load()
    body = js("document.body ? document.body.innerText : ''") or ""
    if js("location.origin") != SITE or '"E11.9"' not in body:
        raise RuntimeError(f"clinicaltables.nlm.nih.gov did not serve the ICD-10-CM API (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit', headers: {Accept: 'application/json'}})
    .then(async r => { const h = {}; r.headers.forEach((v, k) => { h[k] = v; });
      window.__u[id] = {status: r.status, headers: h, text: await r.text()}; })
    .catch(e => { window.__u[id] = {status: 0, headers: {}, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

def retry_after(v):
    """Retry-After in seconds: a number or an HTTP date (both are valid); 60 when absent or unreadable; 1 to 120."""
    try:
        s = float(v)
    except (TypeError, ValueError):
        try:
            s = (parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError):
            s = 60
    return min(max(s, 1), 120)

def fetch(url):
    """One in-page GET -> {status, headers, text}."""
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{url}: no answer after 60s")
        time.sleep(0.2)
    time.sleep(PAUSE)
    return r

def get(path, **params):
    """GET path?params from inside the tab -> parsed JSON array. On 429/500/502/503/504 or a network error waits
    Retry-After (default 60 s, at most 120 s) once; raises on anything else (400 = "Bad request", plain text)."""
    url = SITE + path + "?" + urllib.parse.urlencode(params)
    for attempt in range(2):
        r = fetch(url)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(retry_after(r["headers"].get("retry-after")))
            continue
        if r["status"] != 200 or "json" not in r["headers"].get("content-type", ""):
            raise RuntimeError(f"{url}: HTTP {r['status']} {' '.join(r['text'].split())[:200]!r}; stopping")
        d = json.loads(r["text"])
        if not (isinstance(d, list) and len(d) >= 4 and isinstance(d[0], int)):
            raise RuntimeError(f"{url}: not the [total, codes, extra, rows] array: {r['text'][:200]!r}")
        return d

def icd_search(terms, sf="code,name", q=None):
    """(server total, [(code, name)]), paged 500 at a time. The server refuses offset + count > 7,500, so when
    total > 7,500 only the first 7,500 rows come back: callers must report that as partial."""
    rows, total = [], None
    while total is None or len(rows) < min(total, 7500):
        p = dict(sf=sf, df="code,name", terms=terms, count=500, offset=len(rows))
        if q:
            p["q"] = q
        d = get(ICD, **p)
        total = d[0]
        if not d[3]:
            break
        rows += [tuple(x) for x in d[3]]
    return total, rows

def exact_code(code):
    """Code -> its name, or None. terms= alone is a prefix search (E11 -> 87 codes), so pin it with q=code:..."""
    _, rows = icd_search(code, sf="code", q=f"code:{code}")
    return dict(rows).get(code)

def partial(total, rows):
    return f" (PARTIAL: only the first {len(rows):,} of {total:,} matches can be paged)" if total > len(rows) else ""

def data_version():
    """(source, data version, records) of the ICD-10-CM row in the home page table, read from its HTML."""
    r = fetch(SITE + "/")
    m = re.search(r'db=icd10cm".*?From <a[^>]*>([^<]+)</a>\s*<div class="data_versions">Data version: ([^;<]+); '
                  r'([\d,]+) records', r["text"], re.S)
    if r["status"] != 200 or not m:
        raise RuntimeError(f"home page HTTP {r['status']}: no ICD-10-CM data version row; check it by hand")
    return m[1].strip(), m[2].strip(), int(m[3].replace(",", ""))

def phrase(text):
    return r"\b" + r"\s+".join(map(re.escape, text.split())) + r"\b"

on_ctss_tab()
now = datetime.now(timezone.utc)
src, version, records = data_version()
size = get(ICD, sf="code,name", terms="", maxList=1)[0]
print(f"ICD-10-CM data version {version} (from {src}, {records:,} records on the home page; {size:,} codes in the table) "
      f"via the NLM Clinical Table Search Service, queried {now:%Y-%m-%d %H:%M} UTC")

for text in QUERIES:
    t = " ".join(text.split())
    print(f"\n=== {t!r}")
    if CODE_RE.fullmatch(t.upper()):
        code = t.upper()
        name = exact_code(code)
        if name:
            print(f"  {code} = {name!r}")
            continue
        total, rows = icd_search(code, sf="code")
        kids = [r for r in rows if r[0].startswith(code)]
        print(f"  {code} is not a code in this table" + (f"; {len(kids)} codes start with it (a category or header):"
                                                         if kids else " and no code starts with it") + partial(total, rows))
        for c, n in kids[:8]:
            print(f"    {c:<9} {n}")
        continue
    total, rows = icd_search(t)
    if total:
        hit = [r for r in rows if re.search(phrase(t), r[1], re.I)]
        loose = [r for r in rows if r not in hit]
        cats = {}
        for c, _ in hit:
            cats[c[:3]] = cats.get(c[:3], 0) + 1
        print(f"  {total} codes match all words (partial, any order); {len(hit)} contain the phrase {t!r}" + partial(total, rows))
        print("  by category: " + ", ".join(f"{k} {v}" for k, v in sorted(cats.items(), key=lambda kv: -kv[1])))
        print("  first 8 phrase matches in server order:")
        for c, n in hit[:8]:
            print(f"    {c:<9} {n}")
        for c, n in loose:
            print(f"  NOT the phrase (words matched apart): {c} {n}")
        continue
    # 0 hits: the code table has only official wording ("myocardial infarction", not "heart attack").
    print(f"  0 ICD-10-CM codes contain the words {t!r}; trying lay synonyms in the conditions table")
    d = get(COND, terms=t, df="primary_name,consumer_name", ef="icd10cm", maxList=5)
    if not d[0]:
        print("  no condition matched either: rephrase in clinical words (check the spelling; typos match nothing)")
        continue
    for (primary, consumer), sug in zip(d[3], d[2]["icd10cm"]):
        print(f"  condition {primary!r} (lay: {consumer!r}) suggests:")
        for s in sug:
            code = s["code"].rstrip("?")
            name = exact_code(code) if code == s["code"] else None
            state = (f"confirmed in ICD-10-CM: {name!r}" if name else
                     "needs a 7th character (episode of care); not looked up" if code != s["code"] else
                     "NOT FOUND in the ICD-10-CM table: do not use")
            print(f"    {s['code']:<9} {state}")

print(f"\nSource: ICD-10-CM (data version {version}) via the NLM Clinical Table Search Service, {SITE}{ICD}?sf=code,name&terms=..., "
      f"accessed {now:%d %B %Y %H:%M} UTC. Search aid only, not coding or medical advice.")
```

Output (from the run on 2026-11-17, 00:42 UTC):

```text
ICD-10-CM data version 2027 (from CDC, 74,879 records on the home page; 74,879 codes in the table) via the NLM Clinical Table Search Service, queried 2026-11-17 00:42 UTC

=== 'type 2 diabetes'
  94 codes match all words (partial, any order); 93 contain the phrase 'type 2 diabetes'
  by category: E11 87, O24 6
  first 8 phrase matches in server order:
    E11.65    Type 2 diabetes mellitus with hyperglycemia
    E11.9     Type 2 diabetes mellitus without complications
    E11.21    Type 2 diabetes mellitus with diabetic nephropathy
    E11.36    Type 2 diabetes mellitus with diabetic cataract
    E11.41    Type 2 diabetes mellitus with diabetic mononeuropathy
    E11.42    Type 2 diabetes mellitus with diabetic polyneuropathy
    E11.44    Type 2 diabetes mellitus with diabetic amyotrophy
    E11.620   Type 2 diabetes mellitus with diabetic dermatitis
  NOT the phrase (words matched apart): E10.A2 Type 1 diabetes mellitus, presymptomatic, Stage 2

=== 'E11.9'
  E11.9 = 'Type 2 diabetes mellitus without complications'

=== 'heart attack'
  0 ICD-10-CM codes contain the words 'heart attack'; trying lay synonyms in the conditions table
  condition 'Myocardial infarction' (lay: 'Heart attack (myocardial infarction)') suggests:
    I21.9     confirmed in ICD-10-CM: 'Acute myocardial infarction, unspecified'
  condition 'Non-Q-wave infarct' (lay: 'Non-Q-wave heart attack') suggests:
    I21.4     confirmed in ICD-10-CM: 'Non-ST elevation (NSTEMI) myocardial infarction'

Source: ICD-10-CM (data version 2027) via the NLM Clinical Table Search Service, https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search?sf=code,name&terms=..., accessed 17 November 2026 00:42 UTC. Search aid only, not coding or medical advice.
```

The same block with `QUERIES = ["E11", "I21.0", "high blood pressure", "S72.001A", "hypertension", "diabtes", "s72.001a"]` (same run, 18 `fetch()` calls) printed: E11 "is not a code in this table; 87 codes start with it" (E11.00, E11.01, ...); I21.0 the same with 3 codes (I21.01, I21.02, I21.09); "high blood pressure" 0 in the code table, then 5 conditions all suggesting I10 "Essential (primary) hypertension" except "Hypertension with pregnancy" -> O13.9; S72.001A and lower-case s72.001a both "Fracture of unspecified part of neck of right femur, initial encounter for closed fracture"; "hypertension" 80 codes in 15 categories (I87 20, O10 18, I27 7, ...); "diabtes" "no condition matched either".

### 2. robots.txt, the terms page and query mistakes (browser)

3 page loads, 1 return to the API page and 16 in-page `fetch()` calls in the same tab.

```python
import json, re, time

SITE = "https://clinicaltables.nlm.nih.gov"
ICD = SITE + "/api/icd10cm/v3/search"

START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { const t = await r.text(); window.__u[id] = {status: r.status, type: r.headers.get('content-type') || '',
      text: t}; })
    .catch(e => { window.__u[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

def raw(query):
    """One in-page GET of ICD?query -> status, content type and body. No retries: this block only inspects answers."""
    rid = json.dumps(js(START_JS % json.dumps(ICD + "?" + query)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{query}: no answer after 60s")
        time.sleep(0.2)
    time.sleep(0.25)
    return r

def brief(r):
    out = f"HTTP {r['status']}"
    if "json" not in r["type"]:
        return out + f" {r['type'].split(';')[0]} {' '.join(r['text'].split())[:60]!r}"
    d = json.loads(r["text"])
    return out + f" total {d[0]}, {len(d[1])} returned" + (f", first {d[3][0]}" if d[3] else "")

def page(url):
    goto_url(url)
    wait_for_load()
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    return st, js("document.body ? document.body.innerText : ''") or ""

try:
    on_site = js("location.origin") == SITE
except Exception:
    on_site = False
if not on_site:
    new_tab(ICD + "?sf=code,name&terms=E11.9")
    wait_for_load()

st, txt = page(SITE + "/robots.txt")
print(f"robots.txt HTTP {st}: {' '.join(txt.split())[:60]!r}")
st, txt = page(SITE + "/")
m = re.search(r"ICD-10-CM\s.*?From (\S+)\s+Data version: ([^;]+); ([\d,]+) records", txt, re.S)
print(f"home page HTTP {st}: ICD-10-CM row " + (f"'From {m[1]}', data version {m[2]!r}, {m[3]} records" if m else "NOT FOUND"))
st, txt = page(SITE + "/faq.html")
flat = " ".join(txt.split())
for needle in ("open to the general public and free of charge", "advised maximum request rate is 25 requests per second",
               "exceed 50 requests/second", "exceed 50,000 calls per day", '"X-RateLimit-Limit", "Retry-After"',
               "status code 503", "Do NOT include any PHI", "Registration is not required"):
    print(f"faq HTTP {st}: {'found' if needle in flat else 'MISSING'}: {needle!r}")
page(ICD + "?sf=code,name&terms=E11.9")  # back to an API page for same-origin fetch()
print()

for label, query in (
    ("words, both fields               ", "sf=code,name&terms=type%202%20diabetes&maxList=3"),
    ("same words, default sf=code      ", "terms=type%202%20diabetes&maxList=3"),
    ("lay words: heart attack          ", "sf=code,name&terms=heart%20attack"),
    ("typo: diabtes                    ", "sf=code,name&terms=diabtes"),
    ("word form: hypertensive          ", "sf=code,name&terms=hypertensive&maxList=1"),
    ("code, lower case: e11.9          ", "sf=code&terms=e11.9"),
    ("code without the dot: E119       ", "sf=code&terms=E119"),
    ("category: E11 (prefix search)    ", "sf=code&terms=E11&maxList=2"),
    ("category pinned: q=code:E11      ", "sf=code&terms=E11&q=code:E11"),
    ("code pinned: q=code:E11.9        ", "sf=code&terms=E11.9&q=code:E11.9"),
    ("empty terms (whole table)        ", "sf=code,name&terms=&maxList=1"),
    ("no terms parameter               ", "sf=code,name"),
    ("maxList=1000 (cap 500)           ", "sf=code,name&terms=a&maxList=1000"),
    ("count=501                        ", "sf=code,name&terms=a&count=501"),
    ("offset 7400 + count 100 = 7,500  ", "sf=code,name&terms=a&count=100&offset=7400"),
    ("offset 7400 + count 101 > 7,500  ", "sf=code,name&terms=a&count=101&offset=7400"),
):
    print(f"{label} {brief(raw(query))}")
```

Output (from the run on 2026-11-16, 23:33 UTC):

```text
robots.txt HTTP 404: 'Cannot GET /robots.txt'
home page HTTP 200: ICD-10-CM row 'From CDC', data version '2027', 74,879 records
faq HTTP 200: found: 'open to the general public and free of charge'
faq HTTP 200: found: 'advised maximum request rate is 25 requests per second'
faq HTTP 200: found: 'exceed 50 requests/second'
faq HTTP 200: found: 'exceed 50,000 calls per day'
faq HTTP 200: found: '"X-RateLimit-Limit", "Retry-After"'
faq HTTP 200: found: 'status code 503'
faq HTTP 200: found: 'Do NOT include any PHI'
faq HTTP 200: found: 'Registration is not required'

words, both fields                HTTP 200 total 94, 3 returned, first ['E11.65', 'Type 2 diabetes mellitus with hyperglycemia']
same words, default sf=code       HTTP 200 total 0, 0 returned
lay words: heart attack           HTTP 200 total 0, 0 returned
typo: diabtes                     HTTP 200 total 0, 0 returned
word form: hypertensive           HTTP 200 total 35, 1 returned, first ['I16.0', 'Hypertensive urgency']
code, lower case: e11.9           HTTP 200 total 1, 1 returned, first ['E11.9', 'Type 2 diabetes mellitus without complications']
code without the dot: E119        HTTP 200 total 0, 0 returned
category: E11 (prefix search)     HTTP 200 total 87, 2 returned, first ['E11.00', 'Type 2 diabetes mellitus with hyperosmolarity without nonketotic hyperglycemic-hyperosmolar coma (NKHHC)']
category pinned: q=code:E11       HTTP 200 total 0, 0 returned
code pinned: q=code:E11.9         HTTP 200 total 1, 1 returned, first ['E11.9', 'Type 2 diabetes mellitus without complications']
empty terms (whole table)         HTTP 200 total 74879, 1 returned, first ['A00.0', 'Cholera due to Vibrio cholerae 01, biovar cholerae']
no terms parameter                HTTP 400 text/html 'Bad request: See main page for documentation.'
maxList=1000 (cap 500)            HTTP 200 total 30751, 500 returned, first ['E67.0', 'Hypervitaminosis A']
count=501                         HTTP 400 text/html 'Bad request: See main page for documentation.'
offset 7400 + count 100 = 7,500   HTTP 200 total 30751, 100 returned, first ['M84.572S', 'Pathological fracture in neoplastic disease, left ankle, sequela']
offset 7400 + count 101 > 7,500   HTTP 400 text/html 'Bad request: See main page for documentation.'
```

### 3. Same lookups with Python urllib, robots check for every agent, 12 h disk cache (no browser)

Python's default `urllib` User-Agent was not tried for API calls; this block sends a descriptive one (the robots fetch inside `rp.read()` uses the default). The cache is one JSON file per URL. Run with an empty cache.

```python
import hashlib, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request, urllib.robotparser
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

SITE = "https://clinicaltables.nlm.nih.gov"
ICD = "/api/icd10cm/v3/search"
UA = "icd-10-cm-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]
CACHE_DIR = "~/.cache/icd-10-cm-skill"
CACHE = os.path.expanduser(CACHE_DIR)
TTL = 12 * 3600  # the server sends Cache-Control: public, max-age=43200 (12 h)
calls = hits = 0

def retry_after(v):
    """Retry-After in seconds: a number or an HTTP date (both are valid); 60 when absent or unreadable; 1 to 120."""
    try:
        s = float(v)
    except (TypeError, ValueError):
        try:
            s = (parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError):
            s = 60
    return min(max(s, 1), 120)

def get(path, **params):
    """GET -> parsed [total, codes, extra, rows], from the disk cache when younger than TTL. Once waits Retry-After
    (default 60 s, at most 120 s) on 429/500/502/503/504 or a network error; exits on anything else."""
    global calls, hits
    url = SITE + path + "?" + urllib.parse.urlencode(params)
    f = os.path.join(CACHE, hashlib.sha256(url.encode()).hexdigest() + ".json")
    try:
        if time.time() - os.path.getmtime(f) < TTL:
            hits += 1
            return json.load(open(f))
    except (OSError, ValueError):
        pass
    for attempt in range(2):
        time.sleep(0.25)  # advised maximum is 25 requests/s; stay serial and far below
        calls += 1
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(retry_after(e.headers.get("Retry-After")))
                continue
            sys.exit(f"HTTP {e.code} {url}: {e.read().decode()[:200]}")
        except OSError as e:  # URLError (DNS, refused connection), timeouts, resets
            if attempt == 0:
                time.sleep(60)
                continue
            sys.exit(f"{url}: {e}")
    if not (isinstance(d, list) and len(d) >= 4 and isinstance(d[0], int)):
        sys.exit(f"{url}: not the [total, codes, extra, rows] array")
    os.makedirs(CACHE, exist_ok=True)
    json.dump(d, open(f, "w"))
    return d

def search(terms):
    """All codes whose code or name matches every word -> (total, [(code, name)]), 500 per page. Only the first
    7,500 can be paged, so len(rows) < total means a partial answer."""
    rows, total = [], None
    while total is None or len(rows) < min(total, 7500):
        d = get(ICD, sf="code,name", df="code,name", terms=terms, count=500, offset=len(rows))
        total = d[0]
        if not d[3]:
            break
        rows += [tuple(x) for x in d[3]]
    return total, rows

def data_version():
    """(data version, records) of the ICD-10-CM row on the home page (one uncached call)."""
    global calls
    time.sleep(0.25)
    calls += 1
    req = urllib.request.Request(SITE + "/", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        html = r.read().decode()
    m = re.search(r'db=icd10cm".*?<div class="data_versions">Data version: ([^;<]+); ([\d,]+) records', html, re.S)
    if not m:
        sys.exit("home page has no ICD-10-CM data version row: check it by hand")
    return m[1].strip(), m[2]

def name_of(code):
    d = get(ICD, sf="code", df="code,name", terms=code, q=f"code:{code}")
    return dict(map(tuple, d[3])).get(code.upper())

# robots.txt: the host answers 404. RobotFileParser.read() treats a 4xx other than 401/403 as "allow all"
# (RFC 9309, section 2.3.1.3: unavailable robots.txt, the crawler MAY access any resources).
rp = urllib.robotparser.RobotFileParser(SITE + "/robots.txt")
try:
    urllib.request.urlopen(urllib.request.Request(rp.url, headers={"User-Agent": UA}), timeout=30)
    print("robots.txt now exists: read it before going on")
except urllib.error.HTTPError as e:
    print(f"robots.txt: HTTP {e.code}")
rp.read()
for p in [ICD + "?sf=code,name&terms=x", "/api/conditions/v3/search?terms=x"]:
    ok = all(rp.can_fetch(a, SITE + p) for a in AGENTS)
    print(f"robots {p:<42} {'allowed' if ok else 'DISALLOWED'} for all {len(AGENTS)} agents")
    if not ok:
        sys.exit("robots.txt now disallows a path this skill uses: stop")

version, records = data_version()
print(f"\nICD-10-CM data version {version} ({records} records on the home page); "
      f"table size: {get(ICD, sf='code,name', terms='', maxList=1)[0]:,} codes")
for words in ["type 2 diabetes", "asthma", "migraine with aura", "covid", "sprained ankle"]:
    total, rows = search(words)
    pat = r"\b" + r"\s+".join(map(re.escape, words.split())) + r"\b"
    hit = [r for r in rows if re.search(pat, r[1], re.I)]
    cats = sorted({c[:3] for c, _ in hit})
    print(f"  {words!r:<20} {total:>4} matches, {len(hit):>4} with the phrase, categories {cats[:6]}"
          + (" ..." if len(cats) > 6 else "") + (f" (PARTIAL: first {len(rows):,} of {total:,})" if total > len(rows) else ""))
for code in ["E11.9", "J45.909", "U07.1", "E11", "e119"]:
    print(f"  {code!r:<9} -> {name_of(code)!r}")

n1 = calls
search("type 2 diabetes")
name_of("E11.9")
print(f"\nnetwork calls {n1}, then {calls - n1} more for 2 repeated lookups (cache hits so far: {hits}, cache {CACHE_DIR})")
print(f"Source: ICD-10-CM (data version {version}) via the NLM Clinical Table Search Service. Search aid only, not coding or medical advice.")
```

Output (from the run on 2026-11-17, 00:39 UTC):

```text
robots.txt: HTTP 404
robots /api/icd10cm/v3/search?sf=code,name&terms=x allowed for all 11 agents
robots /api/conditions/v3/search?terms=x          allowed for all 11 agents

ICD-10-CM data version 2027 (74,879 records on the home page); table size: 74,879 codes
  'type 2 diabetes'      94 matches,   93 with the phrase, categories ['E11', 'O24']
  'asthma'               19 matches,   19 with the phrase, categories ['J45', 'J82', 'Z82']
  'migraine with aura'   24 matches,    8 with the phrase, categories ['G43']
  'covid'                 7 matches,    7 with the phrase, categories ['U07', 'U09', 'Z11', 'Z20', 'Z28', 'Z86']
  'sprained ankle'        0 matches,    0 with the phrase, categories []
  'E11.9'   -> 'Type 2 diabetes mellitus without complications'
  'J45.909' -> 'Unspecified asthma, uncomplicated'
  'U07.1'   -> 'COVID-19'
  'E11'     -> None
  'e119'    -> None

network calls 12, then 0 more for 2 repeated lookups (cache hits so far: 2, cache ~/.cache/icd-10-cm-skill)
Source: ICD-10-CM (data version 2027) via the NLM Clinical Table Search Service. Search aid only, not coding or medical advice.
```

### 4. curl, headers and mistakes

```bash
B=https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search
# plain words -> codes; sf=code,name searches both fields (the default sf=code finds no words)
curl -sS --fail -G "$B" --data-urlencode "terms=type 2 diabetes" -d sf=code,name -d maxList=5; echo
sleep 0.25
# code -> name, pinned with q so E11.9 cannot pull in longer codes
curl -sS --fail "$B?sf=code&terms=E11.9&q=code:E11.9"; echo
sleep 0.25
# partial words: "with" also matches "without"
curl -sS --fail -G "$B" --data-urlencode "terms=migraine with aura" -d sf=code,name -d count=500 \
  | python3 -c 'import json,re,sys; d=json.load(sys.stdin); w=[r for r in d[3] if not re.search(r"\bwith\b", r[1])]; print(d[0], "matches,", len(w), "without the word \"with\", e.g.", w[0])'
sleep 0.25
# headers: caching and CORS
curl -sS -D - -o /dev/null "$B?sf=code,name&terms=E11.9" | tr -d '\r' \
  | grep -iE '^(HTTP/|(content-type|cache-control|access-control-allow-origin|x-ratelimit-limit|retry-after):)'
sleep 0.25
# mistakes: lay words and missing dots are silent HTTP 200 with total 0; a missing terms parameter is HTTP 400
curl -sS -w ' <- HTTP %{http_code}\n' -G "$B" --data-urlencode "terms=heart attack" -d sf=code,name
sleep 0.25
curl -sS -w ' <- HTTP %{http_code}\n' "$B?sf=code&terms=E119"
sleep 0.25
curl -sS -w ' <- HTTP %{http_code}\n' "$B?sf=code,name"
```

Output (from the run on 2026-11-16, 23:34 UTC):

```text
[94,["E11.65","E11.9","E10.A2","E11.21","E11.36"],null,[["E11.65","Type 2 diabetes mellitus with hyperglycemia"],["E11.9","Type 2 diabetes mellitus without complications"],["E10.A2","Type 1 diabetes mellitus, presymptomatic, Stage 2"],["E11.21","Type 2 diabetes mellitus with diabetic nephropathy"],["E11.36","Type 2 diabetes mellitus with diabetic cataract"]]]
[1,["E11.9"],null,[["E11.9","Type 2 diabetes mellitus without complications"]]]
24 matches, 6 without the word "with", e.g. ['G43.009', 'Migraine without aura, not intractable, without status migrainosus']
HTTP/1.1 200 OK
Access-Control-Allow-Origin: *
Content-Type: application/json; charset=utf-8
Cache-Control: public, max-age=43200
[0,[],null,[]] <- HTTP 200
[0,[],null,[]] <- HTTP 200
Bad request:  See main page for documentation. <- HTTP 400
```

## Fields (icd10cm and conditions search)

| Call | Response / parameter | Notes |
|---|---|---|
| `/api/icd10cm/v3/search` | `[total, codes, extra, rows]` | a positional JSON array, not an object. `total` counts all matches on the server; `codes` are the returned codes; `extra` is `null` unless `ef` is given (`ef=name` -> `{"name": [...]}`); `rows` are `[code, name]` pairs (the `df` fields) |
| `terms` | required | words or partial words, ANDed ("an implicit AND between them", API doc). Empty `terms=` returns the whole table (total 74,879); no `terms` at all is HTTP 400 |
| `sf` | default `code` | fields searched. Use `sf=code,name` for words; with the default, "type 2 diabetes" returns 0 |
| `q` | optional | Elasticsearch query string, not wildcarded: `q=code:E11.9` pins one code; `q=code:E11` returns 0 (no such record) |
| `df`, `cf`, `ef` | `code,name`; `code`; none | display fields, the field used as "code", extra fields. The table has 2 fields: `code` ("containing 3, 4, 5, 6 or 7 digits") and `name` ("The long description") |
| `maxList` | default 7 | up to 500; values above 500 are cut to 500 without an error (maxList=1000 returned 500). No paging |
| `count`, `offset` | 7, 0 | paging: `count` at most 500 (501 -> HTTP 400), `offset + count` at most 7,500 (7,501 -> HTTP 400) |
| `/api/conditions/v3/search` | `df=primary_name,consumer_name&ef=icd10cm` | 2,418 conditions; `extra.icd10cm[i]` is a list of `{code, name}`; the doc says codes may end in `?`, a placeholder for the 7th character (episode of care) of injury codes |
| response headers | `Cache-Control`, `Access-Control-Allow-Origin`, `ETag` | `public, max-age=43200`; `*`; weak ETag. No `X-RateLimit-Limit` header on normal answers |

## Gotchas

- **Quote the data version.** The home page lists ICD-10-CM as "From CDC", "Data version: 2027; 74,879 records" (blocks 1 and 3 read it from the home page HTML and print it, block 2 from the rendered page; an empty `terms=` gives the same 74,879). Store the version with every answer.
- **Positional array.** Read `d[0]` (total), `d[1]` (codes), `d[3]` (`[code, name]` rows). `d[2]` is `null` without `ef`. The blocks check the shape and stop if it changes.
- **Prefix words, ANDed, any order.** "type 2" alone returned 111 codes including "Neurofibromatosis, type 2" and "Von Willebrand disease, type 2A". "migraine with aura" returned 24 codes, 6 of which never contain the word "with" (G43.009 "Migraine without aura, not intractable, without status migrainosus"). Word forms do not match: none of the 80 "hypertension" codes starts with "Hypertensive", so I11.9 "Hypertensive heart disease without heart failure" is missed; "hypertensive" has 35 codes. Filter the rows yourself (block 1 checks the phrase) and try both word forms.
- **The table holds the codes, not the category headers.** E11 and I21.0 are not records (`q=code:E11` -> 0); `terms=E11` with `sf=code` is a prefix search that lists the 87 E11.xx codes. A code like S72.001 lists 16 codes with 7th characters (S72.001A, S72.001B, ...).
- **Codes need their dot.** `E119` -> 0, `E11.9` -> 1. Case does not matter (`e11.9` works).
- **Server order is not a recommendation.** For "type 2 diabetes" E11.65 came first and E11.9 second; for "hypertension" I10 was 8th. Neither the order nor the first hit says which code fits a case.
- **Lay words need the conditions table.** It is a hand-edited list of 2,418 conditions with "suggested ICD-10-CM codes" (its doc page). It covers common conditions ("heart attack", "high blood pressure") but not everything: "broken hip" and "diabtes" returned 0. Treat its codes as suggestions and confirm them in the ICD-10-CM table, as block 1 does.
- **Totals.** The API doc says the total "is limited to 10,000"; `terms=a` reported 30,751 here, so do not rely on either. Only the first 7,500 matches of one query can be paged; blocks 1 and 3 print "PARTIAL" when the total is larger.
- **The `Date` header can be days old.** A request on 2026-11-16 got `Date: Fri, 06 Nov 2026 09:19:07 GMT` and another `Sun, 15 Nov 2026 20:29:37 GMT`, both with `ctss-info: h=06`; an answer with `h=05` carried the current date. Record your own clock for "accessed".
- **Not coding or medical advice.** The service is a search aid for code names. Which code fits a patient depends on the record and the official coding rules; ask a certified coder or clinician.
- **Tab marker.** The harness sets the tab title to a horse emoji; the blocks check `location.origin` and the JSON, not the title.

## What does not work

- **Plain-language or misspelled searches in the code table.** No synonyms, no fuzzy matching: "heart attack", "high blood pressure", "sprained ankle" and "diabtes" all return 0. Use clinical words or the conditions table.
- **Paging past 7,500 matches, or more than 500 per page**: HTTP 400. A query can report a larger total, but only its first 7,500 rows can be read; the blocks mark such an answer as partial.
- **Not tested:** rate-limit behaviour (never provoked), the FHIR ValueSet `$expand` access the API doc mentions, ICD-10-CM data downloads, and code systems other than ICD-10-CM and the conditions table.
