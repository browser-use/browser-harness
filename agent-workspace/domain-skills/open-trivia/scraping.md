# Open Trivia DB - Hard Multiple-Choice Trivia Questions by Category (opentdb.com JSON API)

Field-tested against opentdb.com on 2026-11-11 using a Browser Use cloud browser (logged out) plus plain HTTP (Python urllib, curl) from a laptop. 1 page load and 12 in-page `fetch()` calls in the browser, about 60 plain HTTP calls, all serial and 5.5 s apart except two deliberate back-to-back pairs: every call was HTTP 200 except those two (HTTP 429, response_code 5) and the robots.txt checks (HTTP 404). No challenge, no key, no login.

robots.txt (checked 2026-11-11): https://opentdb.com/robots.txt is an Apache HTTP 404 page (also via http:// and www.), in the logged-out cloud browser and to curl with User-Agent `*`, GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, Claude-SearchBot, anthropic-ai, Google-Extended, PerplexityBot, Perplexity-User, CCBot, Bytespider, Applebot-Extended and Meta-ExternalAgent: no rules, no named AI-agent groups. Terms: opentdb.com has no terms page (`/terms.php`, `/faq.php`, `/about.php` are HTTP 404; the home page and API page link none). The API page (https://opentdb.com/api_config.php) says "The Open Trivia Database provides a completely free JSON API for use in programming projects. Use of this API does not require a API Key", "All data provided by the API is available under the Creative Commons Attribution-ShareAlike 4.0 International License" and "Each IP can only access the API once every 5 seconds". The home page: "Open Trivia DB is created and maintained by the good folks at PIXELTAIL GAMES LLC. We provide this service for free." No AI, scraping or non-commercial clause.

**Attribution:** CC BY-SA 4.0 means credit and share-alike. When you show or pass on the questions, credit "Open Trivia DB (https://opentdb.com)" and link https://creativecommons.org/licenses/by-sa/4.0/ ; blocks 1 and 3 print that line.

## Quick summary

- **No scraping.** `GET https://opentdb.com/api.php?amount=10&category=22&difficulty=hard&type=multiple` returns JSON `{response_code, results[]}`; each result is `{type, difficulty, category, question, correct_answer, incorrect_answers[3]}`. CORS `*`, no key, no cookie needed.
- **Category is a numeric id.** `api_category.php` lists 24 categories; Geography is `22`. `api_count.php?category=22` gives counts per difficulty: 383 Geography questions, 83 hard (both types) on 2026-11-11; one session token reached 77 hard multiple-choice ones.
- **Rate limit: 1 call per IP per 5 s** (API page). A second call inside 5 s is HTTP 429 with `{"response_code":5,"result":[]}` (note `result`, not `results`). The blocks pause 5.5 s after every call.
- **Check `response_code`, not just HTTP status.** Bad input is HTTP 200 with code 1 (not enough questions), 2 (invalid parameter), 3 (unknown token) or 4 (token has seen everything) and `results: []`.
- **Text is HTML-encoded by default** (HTML entities, e.g. the answer `Hulaul&aacute;` seen on 2026-11-11). Ask for `encode=url3986` (block 1) or `encode=base64` (block 2), or `html.unescape()` the default (block 3).
- **The correct answer comes apart from the 3 wrong ones.** Mix them yourself before showing choices. Questions are random per call; use a session token (block 2) to avoid repeats.

## What works

### 1. 10 hard multiple-choice geography questions with answers (browser)

Self-contained. `on_opentdb_tab()` opens the API page once and later calls reuse the tab; `fetch()` there is same-origin. `get()` returns parsed JSON on HTTP 200, waits once on 429/5xx and otherwise raises. The batch is checked (10 results, all hard, multiple, Geography, 3 wrong answers, none equal to the right one) before anything prints.

```python
import json, re, time, urllib.parse

CATEGORY = "Geography"  # category name as api_category.php lists it
AMOUNT, DIFFICULTY, TYPE = 10, "hard", "multiple"  # difficulty: easy|medium|hard (lowercase); type: multiple|boolean

SITE = "https://opentdb.com"
PAUSE = 5.5  # API page: "Each IP can only access the API once every 5 seconds"; keep calls serial

def on_opentdb_tab():
    """fetch() runs same-origin from a logged-out opentdb.com tab (the API docs page). Reuse the tab if already there."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(SITE + "/api_config.php")
    wait_for_load()
    if js("location.origin") != SITE or "Open Trivia DB" not in (js("document.title") or ""):
        raise RuntimeError(f"opentdb.com did not serve its API page (at {js('location.href')}, title {js('document.title')!r}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__otdb = window.__otdb || {}; const id = String(Math.random()).slice(2); window.__otdb[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__otdb[id] = {status: r.status, type: r.headers.get('content-type'), text: await r.text()}; })
    .catch(e => { window.__otdb[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__otdb[%s]; if (v) delete window.__otdb[%s]; return v; })()"""

def raw(path, timeout=30):
    """GET SITE+path from inside the tab -> (HTTP status, content-type, text). Sleeps PAUSE after every call."""
    rid = json.dumps(js(START_JS % json.dumps(SITE + path)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > timeout:
            raise RuntimeError(f"{path}: no answer after {timeout}s")
        time.sleep(0.3)
    time.sleep(PAUSE)
    return r["status"], r["type"] or "", r["text"]

def get(path):
    """JSON from opentdb.com. The rate limit is HTTP 429 {"response_code":5}: wait and retry once. Raises on anything
    else that is not HTTP 200 JSON, so an error never looks like "no questions"."""
    for attempt in range(2):
        s, t, body = raw(path)
        if s == 200 and "json" in t:
            return json.loads(body)
        if s in (0, 429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(PAUSE)
            continue
        raise RuntimeError(f"{path}: HTTP {s} {t} {' '.join(body.split())[:120]!r}; stopping")

on_opentdb_tab()
# The API page's own words on license and rate limit (there is no separate terms page). textContent, not innerText:
# the response-code list sits in a collapsed panel.
page = " ".join((js("document.body.textContent") or "").split())
for pat in (r"All data provided by the API.*?License\.", r"Each IP can only access the API once every \d+ seconds\."):
    m = re.search(pat, page)
    print("API page:", m.group(0) if m else f"(no match for {pat!r}: re-read the page before relying on the facts below)")

cats = get("/api_category.php")["trivia_categories"]
cat = next((c for c in cats if c["name"] == CATEGORY), None)
if cat is None:
    raise RuntimeError(f"no category named {CATEGORY!r}; have {[c['name'] for c in cats]}")
cnt = get(f"/api_count.php?category={cat['id']}")["category_question_count"]
print(f"\n{CATEGORY} = category {cat['id']}: {cnt['total_question_count']} questions, {cnt[f'total_{DIFFICULTY}_question_count']} {DIFFICULTY} (all types)")

# encode=url3986 makes every string percent-encoded; without it the API sends HTML entities (&quot; &#039; &eacute;).
q = urllib.parse.urlencode({"amount": AMOUNT, "category": cat["id"], "difficulty": DIFFICULTY, "type": TYPE, "encode": "url3986"})
d = get(f"/api.php?{q}")
if d["response_code"] != 0:  # 1 not enough questions, 2 bad parameter, 3/4 token problems, 5 rate limit
    raise RuntimeError(f"api.php response_code {d['response_code']}: {d}")
dec = lambda s: urllib.parse.unquote(s)
qs = [{k: ([dec(x) for x in v] if isinstance(v, list) else dec(v)) for k, v in r.items()} for r in d["results"]]

problems = []
if len(qs) != AMOUNT:
    problems.append(f"asked {AMOUNT}, got {len(qs)}")
if len({x["question"] for x in qs}) != len(qs):
    problems.append("duplicate questions in one batch")
for i, x in enumerate(qs, 1):
    if (x["type"], x["difficulty"], x["category"]) != (TYPE, DIFFICULTY, CATEGORY):
        problems.append(f"Q{i} is {x['type']}/{x['difficulty']}/{x['category']}")
    if len(x["incorrect_answers"]) != 3 or x["correct_answer"] in x["incorrect_answers"]:
        problems.append(f"Q{i} has choices {x['incorrect_answers']} + {x['correct_answer']!r}")
if problems:
    raise RuntimeError("bad batch: " + "; ".join(problems))

for i, x in enumerate(qs, 1):
    choices = sorted([x["correct_answer"], *x["incorrect_answers"]], key=str.lower)  # API puts the answer apart; mix it in
    letter = "ABCD"[choices.index(x["correct_answer"])]
    print(f"\n{i:>2}. {x['question']}")
    print("    " + "   ".join(f"{L}) {c}" for L, c in zip("ABCD", choices)))
    print(f"    Answer: {letter}) {x['correct_answer']}")
print("\nQuestions from Open Trivia DB (https://opentdb.com), CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/)")

s, t, _ = raw("/robots.txt")
print(f"robots.txt: HTTP {s} {t}")
```

Output (from the run on 2026-11-11; the 10 questions are a random draw and differ every run):

```text
API page: All data provided by the API is available under the Creative Commons Attribution-ShareAlike 4.0 International License.
API page: Each IP can only access the API once every 5 seconds.

Geography = category 22: 383 questions, 83 hard (all types)

 1. How many stations does the Central Line have on the London Underground?
    A) 43   B) 47   C) 49   D) 51
    Answer: C) 49

 2. What country is not a part of Scandinavia?
    A) Denmark   B) Finland   C) Norway   D) Sweden
    Answer: B) Finland

 3. Bir Tawil, an uninhabited track of land claimed by no country, is located along the border of which two countries?
    A) Chad and Libya   B) Egypt and Sudan   C) Iraq and Saudi Arabia   D) Israel and Jordan
    Answer: B) Egypt and Sudan

 4. Where is the fast food chain "Panda Express" headquartered?
    A) Fresno, California   B) Rosemead, California   C) Sacramento, California   D) San Diego, California
    Answer: B) Rosemead, California

 5. What is special about Lake Titicaca?
    A) Deepest lake in the world   B) Highest navigable lake   C) Longest lake in the world   D) Remains frozen all year round
    Answer: B) Highest navigable lake

 6. In which country is Tallinn located?
    A) Estonia   B) Finland   C) Poland   D) Sweden
    Answer: A) Estonia

 7. What is the Finnish word for "Finland"?
    A) Eesti   B) Magyarország   C) Suomi   D) Sverige
    Answer: C) Suomi

 8. Into which basin does the Jordan River flow into?
    A) Aral Sea   B) Caspian Sea   C) Dead Sea   D) Salton Sea
    Answer: C) Dead Sea

 9. Llanfair­pwllgwyngyll­gogery­chwyrn­drobwll­llan­tysilio­gogo­goch is located on which Welsh island?
    A) Anglesey   B) Bardsey   C) Barry   D) Caldey
    Answer: A) Anglesey

10. Which of these is NOT a city in India?
    A) Ahmedabad   B) Ghaziabad   C) Hyderabad   D) Islamabad
    Answer: D) Islamabad

Questions from Open Trivia DB (https://opentdb.com), CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/)
robots.txt: HTTP 404 text/html; charset=iso-8859-1
```

### 2. Session token for no repeats, plus every response code (plain Python, no browser)

`api_token.php?command=request` returns a 64-hex-char token; pass it as `token=` and the API "will never give you the same question twice". `encode=base64` encodes every string field, including `type`, `difficulty` and `category`. 10 calls, about 55 s.

```python
import base64, json, time, urllib.error, urllib.parse, urllib.request

API = "https://opentdb.com/"
PAUSE = 5.5  # "Each IP can only access the API once every 5 seconds"
CODES = {0: "success", 1: "no results (not enough questions)", 2: "invalid parameter", 3: "token not found",
         4: "token empty (all questions seen)", 5: "rate limit"}

def call(path, pause=PAUSE):
    """GET API+path -> (HTTP status, parsed JSON). HTTP 429 carries JSON too, so read the body either way."""
    try:
        with urllib.request.urlopen(API + path, timeout=30) as r:
            status, body = r.status, r.read()
    except urllib.error.HTTPError as e:
        status, body = e.code, e.read()
    time.sleep(pause)
    return status, json.loads(body)

def questions(amount, category, difficulty, type_, token=None):
    """One api.php batch, base64-decoded. Retries once on the rate limit; raises on any other non-zero code."""
    q = {"amount": amount, "category": category, "difficulty": difficulty, "type": type_, "encode": "base64"}
    if token:
        q["token"] = token
    for attempt in range(2):
        s, d = call("api.php?" + urllib.parse.urlencode(q))
        if d.get("response_code") == 5 and attempt == 0:
            continue  # HTTP 429; call() already slept 5.5 s
        if s != 200 or d.get("response_code") != 0:
            raise RuntimeError(f"api.php HTTP {s} response_code {d.get('response_code')} ({CODES.get(d.get('response_code'))})")
        b = lambda x: base64.b64decode(x).decode("utf-8")
        return [{k: ([b(x) for x in v] if isinstance(v, list) else b(v)) for k, v in r.items()} for r in d["results"]]

# A session token stops repeats across calls ("the API will never give you the same question twice").
s, t = call("api_token.php?command=request")
if s != 200 or t.get("response_code") != 0:
    raise RuntimeError(f"token request failed: HTTP {s} {t}")
tok = t["token"]
print(f"token: {t['response_message']} ({len(tok)} hex chars)")

batch1 = questions(10, 22, "hard", "multiple", tok)
batch2 = questions(10, 22, "hard", "multiple", tok)
seen = [x["question"] for x in batch1 + batch2]
bad = [x for x in batch1 + batch2 if (x["type"], x["difficulty"], x["category"]) != ("multiple", "hard", "Geography")]
if len(batch1) != 10 or len(batch2) != 10 or bad:
    raise RuntimeError(f"bad batches: {len(batch1)}, {len(batch2)}, off-filter {bad[:2]}")
print(f"two batches with one token: {len(seen)} questions, {len(set(seen))} distinct")
x = batch2[0]
print(f"e.g. {x['question']} -> {x['correct_answer']} (wrong: {', '.join(x['incorrect_answers'])})")

# Response codes and HTTP statuses, one deliberate probe each
probes = [
    ("api.php?amount=1&category=22&difficulty=HARD", "difficulty is case-sensitive"),
    ("api.php?amount=0&category=22", "amount below 1"),
    ("api.php?amount=1&category=999", "unknown category"),
    ("api.php?amount=1&category=22&token=deadbeef", "unknown token"),
    ("api.php?amount=51&category=22", "amount above the 50 cap"),
]
print()
for path, why in probes:
    s, d = call(path)
    n = len(d.get("results", []))
    print(f"{why:<30} HTTP {s} response_code {d['response_code']} ({CODES[d['response_code']]}), {n} results")
s1, d1 = call("api.php?amount=1&category=22", pause=0)  # two calls back to back, no pause
s2, d2 = call("api.php?amount=1&category=22")
print(f"{'two calls 0 s apart':<30} HTTP {s1} code {d1['response_code']}, then HTTP {s2} code {d2['response_code']} ({CODES[d2['response_code']]}) keys {sorted(d2)}")
```

Output (from the run on 2026-11-11):

```text
token: Token Generated Successfully! (64 hex chars)
two batches with one token: 20 questions, 20 distinct
e.g. What country is not a part of Scandinavia? -> Finland (wrong: Norway, Sweden, Denmark)

difficulty is case-sensitive   HTTP 200 response_code 2 (invalid parameter), 0 results
amount below 1                 HTTP 200 response_code 2 (invalid parameter), 0 results
unknown category               HTTP 200 response_code 1 (no results (not enough questions)), 0 results
unknown token                  HTTP 200 response_code 3 (token not found), 0 results
amount above the 50 cap        HTTP 200 response_code 0 (success), 50 results
two calls 0 s apart            HTTP 200 code 0, then HTTP 429 code 5 (rate limit) keys ['response_code', 'result']
```

### 3. Same call with curl (default HTML-entity encoding)

```bash
curl -sS --fail 'https://opentdb.com/api.php?amount=10&category=22&difficulty=hard&type=multiple' | python3 -c '
import html, json, sys
d = json.load(sys.stdin)
res = d["results"]
if d["response_code"] != 0 or len(res) != 10:
    sys.exit("response_code %s, %d results" % (d["response_code"], len(res)))
print("questions with an HTML entity before unescape:", sum("&" in r["question"] for r in res), "of", len(res))
for i, r in enumerate(res, 1):
    print("%2d. %s -> %s" % (i, html.unescape(r["question"]), html.unescape(r["correct_answer"])))
'
echo 'Questions from Open Trivia DB (https://opentdb.com), CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/)'
sleep 6  # once every 5 s per IP
curl -sS -o /dev/null -w 'robots.txt: HTTP %{http_code} %{content_type}\n' https://opentdb.com/robots.txt
```

Output (from the run on 2026-11-11):

```text
questions with an HTML entity before unescape: 0 of 10
 1. What is the name of the formerly rich fishing grounds off the island of Newfoundland, Canada? -> Grand Banks
 2. How many countries share a land border with Russia? (Not including disputed territories) -> 14
 3. Where is Timbuktu located? -> Mali, Africa
 4. What year is on the flag of the US state Wisconsin? -> 1848
 5. What country is not a part of Scandinavia? -> Finland
 6. Which is not a country in Africa? -> Guyana
 7. The prefix Sino- (As in Sino-American) is used to refer to what nationality? -> Chinese
 8. Where is Fort Marlborough located? -> Bengkulu
 9. The emblem on the flag of the Republic of Tajikistan features a sunrise over mountains below what symbol? -> Crown
10. What is the name of the Canadian national anthem? -> O Canada
Questions from Open Trivia DB (https://opentdb.com), CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/)
robots.txt: HTTP 404 text/html; charset=iso-8859-1
```

## Fields

| Field | Notes |
|---|---|
| `response_code` | API page: 0 success, 1 no results, 2 invalid parameter, 3 token not found, 4 token empty, 5 rate limit |
| `results[]` | `amount` items; on code 5 the key is `result` |
| `type` | `multiple` (4 choices) or `boolean` (`True`/`False`) |
| `difficulty` | `easy`, `medium`, `hard` (lowercase; `HARD` in the query is code 2) |
| `category` | category name, `Geography`; ids come from `api_category.php` |
| `question`, `correct_answer` | encoded per `encode=` (default HTML entities) |
| `incorrect_answers[]` | 3 strings for `multiple`, 1 for `boolean` |
| `api_count.php` | `{category_id, category_question_count: {total_question_count, total_easy_question_count, total_medium_question_count, total_hard_question_count}}` |
| `api_token.php` | `?command=request` gives `{response_code, response_message, token}`; `?command=reset&token=...` wipes its memory |

## Gotchas

- **Never call twice inside 5 s.** HTTP 429 code 5 comes back immediately (block 2, last line). `api_count.php` answered HTTP 200 right after an `api.php` call on 2026-11-11, but the blocks pace helper calls too.
- **Token runs dry before zero.** With one token, hard multiple-choice Geography gave 50 + 20 + 5 + 2 = 77 questions, then code 4. Once fewer remain than `amount`, the call is code 4 with nothing: after 70 seen, `amount=10` was code 4 while `amount=5` still worked. Step `amount` down, or reset the token. Tokens are deleted "after 6 hours of inactivity" (API page); a reset returned the same token string.
- **`amount` is capped and loosely parsed.** `amount=51` returns 50 with code 0; `amount=0` is code 2. The API page says "Amount = Five" is code 2, but `amount=five` returned 50 questions with code 0 on 2026-11-11. Send an integer from 1 to 50.
- **One category per call.** API page: "Only 1 Category can be requested per API Call." Omit `category` for any category.
- **Decoded text can hold invisible characters.** A question decoded from `url3986` in block 1 carries soft hyphens (U+00AD) inside "Llanfair...gogogoch" (question 9); strip `\u00ad` before comparing strings.
- **User-contributed content.** The home page counts "5,299 Verified Questions". Some text has typos or dated framing ("an uninhabited track of land", "most populous Muslim-majority nation in 2010" seen on 2026-11-11). Quote it as the API gives it; do not treat it as a fact source.
- **Tab marker.** The harness prefixes the tab title with a horse emoji; block 1 matches a substring of the title only.

## What does not work

- **Several categories, or more than 50 questions, in one call:** not supported (API page). Make one call per category, 5 s apart.
- **A fixed question set:** results carry no question id and the API page documents no lookup by id; each call is a random draw.
- **Not tested:** `encode=urlLegacy`, `type=boolean` batches beyond the probes above, `api_count_global.php` beyond one call (21,716 total, 5,299 verified on 2026-11-11), sustained traffic.
