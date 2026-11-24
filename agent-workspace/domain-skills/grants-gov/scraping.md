# Grants.gov - Find Open and Forecasted US Federal Grant Opportunities for a Keyword: Number, Title, Agency, Open and Close Dates, Then Award Ceiling, Award Floor and Eligibility for the Top Hit (search2 and fetchOpportunity JSON APIs, POST, no key)

Field-tested against api.grants.gov, www.grants.gov and www.hhs.gov on 2026-11-23 (US Eastern evening; roughly 23:30-23:45 UTC, saved exploration files from 23:33 UTC) using fresh Browser Use cloud browsers (logged out; one session 23:34:28-23:42:02 UTC, and a second, new one at 23:44:29-23:44:40 UTC for block 1's last run) plus Python `urllib` and `curl` from a Linux machine. 42 browser page loads (36 on www.grants.gov, 4 on www.hhs.gov, 2 on api.grants.gov) and 80 in-page `fetch()` calls to the API (block 1 ran 5 times, block 2 three times), 59 curl calls (41 while exploring, 18 in two runs of block 4) and 61 urllib calls (block 3 ran 6 times with 10 calls each, plus one TLS test), all serial and at least 1 s apart. Every API answer was HTTP 200 except the deliberate probes below: HTTP 403 `{"message":"Missing Authentication Token"}` (a GET, a CORS preflight `OPTIONS` and `/robots.txt` on api.grants.gov) and HTTP 502 (a body that is not JSON). 11 in-page `fetch()` calls failed on purpose or by CORS (see Gotchas), and every plain `curl` or Python request to www.grants.gov failed certificate verification (incomplete chain, see Gotchas). curl timed answers at 0.22-0.87 s (0.87 s for all 790 posted opportunities in one call). No 429, no key, no login, no cookie. Before the code review, the last runs were block 1's fifth (23:44 UTC), block 2's third (23:40), block 3's sixth (23:44) and block 4's second (23:41); block 2's output below is that run, and the outputs shown for blocks 1, 3 and 4 come from the re-runs after the review (see the end of this paragraph). Between the last two runs of each block only the times changed, plus one printed label in block 1 (the default order is no longer called relevance, which is not documented), and in earlier runs the eligibility code order in block 3 (now sorted, because the API returns it in a different order per call) and an `&amp;` in a title in block 4 (now decoded). Block 1's first run (23:35) stopped on a `cfdas` entry without a number and block 3's first (23:38) on a sort bug; both were fixed before the runs shown. An earlier live check on the same day (23:19 UTC, while choosing this site) gave the same 149 hits. An independent verifier re-ran all four blocks verbatim on 2026-11-23 23:46 to 23:47 UTC (a new cloud browser, urllib, curl): every block ran, and apart from the printed times every output was identical to the one shown. After a code review, blocks 1, 3 and 4 changed and re-ran on 2026-11-24 between 00:28 and 00:36 UTC (browser blocks in a new cloud browser); the outputs shown for them come from those runs. A second review round changed blocks 1 and 3 again; their re-runs at 00:43-00:44 UTC (block 1 in another new cloud browser) printed the same apart from times. A website review made block 3 neutralise spreadsheet formulas in the CSV (widened in a second pass to full-width signs and leading whitespace); its re-runs at 01:45 and 01:52 UTC printed the same apart from the time and wrote a byte-identical CSV.

robots.txt (checked 2026-11-23, curl, `urllib.robotparser` and the cloud browser): https://api.grants.gov/robots.txt answers HTTP 403 with the JSON `{"message":"Missing Authentication Token"}` (the same answer a GET or an OPTIONS to the search endpoint gets), so the API host has no rules and no named AI-agent groups; under RFC 9309 (section 2.3.1.3) an unavailable robots.txt (4xx) means a crawler "MAY access any resources". https://www.grants.gov/robots.txt is `User-agent: *` / `Allow: /` and nothing else (read in the cloud browser by block 2, and with `curl -k` while choosing this site because the server sends an incomplete certificate chain). No group names GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot or Bytespider, so all of them fall under `*`, which allows `/api/api-guide`, `/api/common/search2`, `/api/common/fetchopportunity` and `/search-results-detail/<id>` (block 2 checks all 11 agents). Terms: the API guide https://www.grants.gov/api/api-guide says "Authentication and authorization are not required for the following APIs: Endpoint: search2, Endpoint: fetchOpportunity" and, under "Unrestricted Access", that "The primary endpoint, v1/api/search2, is designed to be accessible without user authentication (in other words, no login or authentication key required)", "allowing the public and developers alike to conduct thorough searches"; the endpoint pages say "Authentication and authorization is not required for search2" and "... for fetchOpportunity". The guide also says "some will require an API key from Grants.gov": the two endpoints used here are not among them. The site footer's "Disclaimers" link goes to the exit disclaimer https://www.grants.gov/exit-disclaimer, which is about links to other websites ("these sites are not endorsed by the federal government"). Grants.gov is an HHS site (https://www.grants.gov/support/about-grants-gov: "Managed by the Department of Health and Human Services, Grants.gov is an E-Government initiative operating under the governance of the Office of Management and Budget"); the HHS website disclaimers https://www.hhs.gov/digital/policies/disclaimers/index.html say "Reference in this website to any specific commercial product, process, service, manufacturer, or company is not an endorsement or recommendation by the U.S. Government" and that its licensed "stock photos are not in the public domain". None of these pages mentions AI, machine learning, text and data mining, scraping, crawling, robots, automated access or non-commercial use (block 2 checks), and no licence restriction was found for the opportunity data, which federal agencies publish. Naming: this skill writes "Grants.gov" in plain text, shows no Grants.gov or HHS logo, and is not affiliated with or endorsed by Grants.gov, HHS or any US government agency.

## Quick summary

- **No scraping.** `POST https://api.grants.gov/v1/api/search2` with JSON `{"keyword": "artificial intelligence", "oppStatuses": "forecasted|posted", "rows": 10, "startRecordNum": 0}` -> `{"errorcode": 0, "msg": "Webservice Succeeds", "token": "...", "data": {"hitCount": 149, "oppHits": [{"id", "number", "title", "agencyCode", "agency", "openDate", "closeDate", "oppStatus", "docType", "cfdaList"}], "oppStatusOptions": [...], "agencies": [...], "eligibilities": [...], ...}}`. Then `POST /v1/api/fetchOpportunity` with `{"opportunityId": 320753}` (the `id`, not the `number`) -> one opportunity with a `synopsis` block (posted) or a `forecast` block (forecasted) holding `awardCeiling`, `awardFloor`, `estimatedFunding` and `applicantTypes`. JSON, no key, no login. GET is HTTP 403.
- **Answers (block 1 as shown below, re-run 24 November 2026 00:31 UTC; the 23:44 UTC run on 23 November gave the same values):** "artificial intelligence" has **149** open and forecasted opportunities (124 posted, 25 forecasted; 113 as a quoted phrase). First in the default order: **PD-19-127Y**, NSF, "Science of Learning and Augmented Intelligence (SL)", open 09/19/2019, close **02/10/2027**: award ceiling **none**, award floor **$550**, eligibility **99 Unrestricted**. Top forecast: **W519TC-25-S-0001**, Army Contracting Command Rock Island, "Broad Agency Announcement for Fundamental AI Research", no close date, no award amounts, eligibility **25 Others** with the text "institutions of higher education, nonprofit organizations, state and local governments, foreign organizations, foreign public entities, and for-profit organizations". Closing soonest: G27AS00044 (Geological Survey) on 11/30/2026. Block 3 writes all 149 to a CSV; block 4 shows DE-FOA-0003612 (Office of Science): ceiling $16,000,000, floor $500,000, estimated total $293,760,000.
- **Filters are codes in pipe-separated strings.** `agencies` (`NSF`, `DOD-AMC-ACCRI`, `DOD*`), `eligibilities` (`23` small businesses, `99` unrestricted ...), `fundingCategories` (`ST`, `HL` ...), `cfda` (Assistance Listing number, e.g. `47.075`); the codes come back as facets in every search2 answer, and the eligibility and category codes (not the agency codes) are also listed on https://www.grants.gov/api/status-codes. Wrong names, separators and codes give `hitCount 0` or are ignored, never an error (block 2).
- **Rate limit: none published as a number.** The status-codes page says "429 Too Many Requests: Too many of the user's requests hit the API too quickly. We recommend an exponential backoff of your requests."; answers carry no rate-limit headers (block 4). The blocks stay serial, wait 1 s around each call, back off on 429/5xx (`Retry-After`, else 30 s once in block 1, 15 s then 30 s in block 3, `curl --retry 3` on block 4's data calls) and stop when asked to wait more than 120 s.

## What works

### 1. Keyword -> open and forecasted opportunities with number, title, agency, open and close dates, then award ceiling, floor and eligibility for the top hit (browser)

`on_grants_tab()` opens the search2 docs page on www.grants.gov (allowed by robots.txt). The API answers `Access-Control-Allow-Origin: *`, but its CORS preflight (`OPTIONS`) is HTTP 403, so `post()` sends the JSON body without a `Content-Type` header: that keeps the request "simple" (no preflight), and the API still parses the body as JSON. `post()` checks HTTP 200, JSON and `errorcode` 0, and drops the anonymous session `token` from every answer. 5 POSTs: the search, the quoted-phrase count, the closing-soonest list and two `fetchOpportunity` calls.

```python
import email.utils, html, json, time
from datetime import datetime, timezone

KEYWORD = "artificial intelligence"
STATUSES = "forecasted|posted"   # pipe-separated string; a comma gives 0 hits without an error
SHOW = 8

API = "https://api.grants.gov/v1/api"
DOCS = "https://www.grants.gov/api/common/search2"   # any www.grants.gov page works; robots.txt allows /
PAUSE = 1.0  # no number is published; the status-codes page asks for exponential backoff on 429

def on_grants_tab():
    try:
        if js("location.origin") == "https://www.grants.gov":
            return
    except Exception:
        pass
    new_tab(DOCS)
    wait_for_load()
    if js("location.origin") != "https://www.grants.gov":
        raise RuntimeError(f"expected a www.grants.gov page, got {js('location.href')}: stop")

# No Content-Type header on purpose: that keeps the POST a CORS "simple request". With
# 'Content-Type: application/json' the browser sends an OPTIONS preflight, which the API answers
# with HTTP 403 "Missing Authentication Token", and fetch() fails. The API reads the body as JSON either way.
START_JS = """(() => { window.__g = window.__g || {}; const id = String(Math.random()).slice(2); window.__g[id] = null;
  fetch(%s, {method: 'POST', credentials: 'omit', body: %s})
    .then(async r => { window.__g[id] = {status: r.status, type: r.headers.get('content-type') || '',
      retry: r.headers.get('retry-after'), text: await r.text()}; })
    .catch(e => { window.__g[id] = {status: 0, type: '', retry: null, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__g[%s]; if (v) delete window.__g[%s]; return v; })()"""

def retry_wait(value, default):
    v = (value or "").strip()
    if v.isdigit():
        return int(v)
    try:
        return max(0, int((email.utils.parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()) + 1)
    except (TypeError, ValueError):
        return default

def post(endpoint, body):
    """POST JSON -> parsed `data`. Waits once on 429/5xx/network error (Retry-After, else 30 s; over 120 s
    stops). Checks errorcode 0, then drops the anonymous session 'token' the API puts in every answer."""
    for attempt in range(2):
        rid = json.dumps(js(START_JS % (json.dumps(f"{API}/{endpoint}"), json.dumps(json.dumps(body)))))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > 60:
                raise RuntimeError("no answer after 60 s")
            time.sleep(0.2)
        time.sleep(PAUSE)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            wait = retry_wait(r["retry"], 30)
            if wait > 120:
                raise RuntimeError(f"server asks to wait {wait} s: stopping")
            time.sleep(wait)
            continue
        break
    if r["status"] != 200 or "json" not in r["type"]:
        raise RuntimeError(f"{endpoint}: HTTP {r['status']} {r['type']} {' '.join(r['text'].split())[:200]!r}: stopping")
    d = json.loads(r["text"])
    d.pop("token", None)  # anonymous session token: never print or store it
    if d.get("errorcode") != 0:
        raise RuntimeError(f"{endpoint}: errorcode {d.get('errorcode')} {d.get('msg')!r}")
    return d["data"]

def search(keyword, rows, start=0, sort=""):
    d = post("search2", {"keyword": keyword, "oppStatuses": STATUSES, "rows": rows, "startRecordNum": start,
                         "sortBy": sort})
    if sort and d["hitCount"] == 0:
        print(f"  (0 hits with sortBy {sort!r}: an unknown sortBy also gives 0, check the spelling)")
    return d

def money(v):
    """awardCeiling / awardFloor are strings: digits, 'none', '0' or missing."""
    if v is None or v == "":
        return "not given"
    return f"${int(v):,}" if str(v).isdigit() else str(v)

def details(opp_id):
    d = post("fetchOpportunity", {"opportunityId": int(opp_id)})
    if str(d.get("id")) != str(opp_id):
        raise RuntimeError(f"fetchOpportunity {opp_id}: no such opportunity (HTTP 200, errorcode 0, no 'id' in data)")
    # posted opportunities carry a 'synopsis' block, forecasts a 'forecast' block; the other one is absent
    block = d.get("synopsis") or d.get("forecast") or {}
    kind = "synopsis" if d.get("synopsis") else "forecast" if d.get("forecast") else "none"
    return d, block, kind

on_grants_tab()
now = datetime.now(timezone.utc)
print(f"Grants.gov search2, keyword {KEYWORD!r}, oppStatuses {STATUSES!r}, checked {now:%Y-%m-%d %H:%M} UTC")

d = search(KEYWORD, SHOW)
st = {o["value"]: o["count"] for o in d["oppStatusOptions"]}
print(f"hitCount {d['hitCount']} (posted {st.get('posted')}, forecasted {st.get('forecasted')}; "
      f"not asked for: closed {st.get('closed')}, archived {st.get('archived')})")
q = search(f'"{KEYWORD}"', 1)
print(f"as a quoted phrase: hitCount {q['hitCount']} (unquoted words also match opportunities that have only some of them)")
if not d["oppHits"]:
    if d["hitCount"]:
        raise RuntimeError(f"hitCount {d['hitCount']} but no rows came back: an inconsistent answer, retry later")
    raise SystemExit(f"no open or forecasted opportunity for {KEYWORD!r}: try fewer words, or add closed|archived")
print(f"\nTop {SHOW} in the default order (sortBy empty):")
for h in d["oppHits"]:
    close = h["closeDate"] or "-"
    print(f"  {h['number']:<22} {h['oppStatus']:<10} open {h['openDate']}  close {close:<10}  {h['agencyCode']:<14} {html.unescape(h['title'])[:60]}")  # titles can hold &amp;

soon = search(KEYWORD, 5, sort="closeDate|asc")
print("\nClosing soonest (sortBy closeDate|asc; hits with no close date, all forecasts and some posted, sort last):")
for h in soon["oppHits"]:
    when = (f"{h['closeDate']} (in {(datetime.strptime(h['closeDate'], '%m/%d/%Y').date() - now.date()).days} days)"
            if h["closeDate"] else "no close date")
    print(f"  {when}  {h['number']:<18} {h['agency'][:34]:<34} {html.unescape(h['title'])[:50]}")

top = d["oppHits"][0]
first_forecast = next((h for h in d["oppHits"] if h["docType"] == "forecast"), None)
for h in [top] + ([first_forecast] if first_forecast and first_forecast is not top else []):
    o, b, kind = details(h["id"])
    print(f"\nfetchOpportunity {h['id']} ({kind}): {o['opportunityNumber']}  {html.unescape(o['opportunityTitle'])}")
    print(f"  agency: {o['agencyDetails']['agencyName']} ({o['owningAgencyCode']}), top agency {o['topAgencyDetails']['agencyName']}")
    print(f"  award ceiling {money(b.get('awardCeiling'))}, award floor {money(b.get('awardFloor'))}, "
          f"estimated total funding {money(b.get('estimatedFunding'))}, cost sharing {b.get('costSharing')}")
    if kind == "synopsis":
        print(f"  posted {b.get('postingDate')}, closes {b.get('responseDate') or 'no date'}, archive {b.get('archiveDate')}")
    else:
        print(f"  forecast posted {b.get('postingDate')}, est. synopsis {b.get('estSynopsisPostingDate') or 'not given'}, "
              f"est. close {b.get('estApplicationResponseDate') or 'not given'}, fiscal year {b.get('fiscalYear')}")
    types = "; ".join(a["id"] + " " + a["description"][:70] for a in b.get("applicantTypes") or [])
    print(f"  eligibility: {types or 'not given'}")
    extra = " ".join((b.get("applicantEligibilityDesc") or "").split())
    print(f"  additional eligibility text: {extra[:200] or '(empty)'}")
    print(f"  instruments: {[f['description'] for f in b.get('fundingInstruments') or []]}, ALN {sorted({c['cfdaNumber'] for c in o.get('cfdas') or [] if c.get('cfdaNumber')})}")  # some cfdas entries carry no number
    print(f"  page for people: https://www.grants.gov/search-results-detail/{o['id']}")
print(f"\nSource: Grants.gov search2 and fetchOpportunity APIs, accessed {now:%d %B %Y %H:%M} UTC.")
```

Output (re-run on 2026-11-24 after the code-review fixes, 00:31 UTC, in a new cloud browser; the 23:36-23:44 runs on 2026-11-23 printed the same opportunities and values, with each "in N days" one higher; with a keyword that has no hits the block now stops with "no open or forecasted opportunity"):

```text
Grants.gov search2, keyword 'artificial intelligence', oppStatuses 'forecasted|posted', checked 2026-11-24 00:31 UTC
hitCount 149 (posted 124, forecasted 25; not asked for: closed 675, archived 3926)
as a quoted phrase: hitCount 113 (unquoted words also match opportunities that have only some of them)

Top 8 in the default order (sortBy empty):
  PD-19-127Y             posted     open 09/19/2019  close 02/10/2027  NSF            Science of Learning and Augmented Intelligence (SL)
  W519TC-25-S-0001       forecasted open 04/16/2025  close -           DOD-AMC-ACCRI  Broad Agency Announcement for Fundamental AI Research
  PAS-TUNIS- APS FY2026  forecasted open 05/06/2026  close -           DOS-TUN        Annual Program Statement (APS) For Fiscal Year 2026
  26-504                 posted     open 02/05/2026  close 09/28/2027  NSF            Postdoctoral Research Fellowships in Biology (PRFB)
  25-531                 posted     open 01/04/2025  close 01/20/2027  NSF            Cybersecurity Innovation for Cyberinfrastructure (CICI)
  26-512                 posted     open 07/21/2026  close 11/03/2027  NSF            Unlocking Dataset Value for AI-Enabled Scientific Discovery
  26-503                 posted     open 02/04/2026  close 04/05/2027  NSF            Artificial Intelligence and Cybersecurity Education Innovati
  PAS-TUNIS-FY2025       forecasted open 06/02/2025  close -           DOS-TUN        Annual Program Statement (APS) for Fiscal Year 2025

Closing soonest (sortBy closeDate|asc; hits with no close date, all forecasts and some posted, sort last):
  11/30/2026 (in 6 days)  G27AS00044         Geological Survey                  Cooperative Agreement for affiliated Partner with
  12/02/2026 (in 8 days)  G27AS00040         Geological Survey                  Cooperative Agreement for affiliated Partner with
  12/04/2026 (in 10 days)  NNH25ZDA001N-CRYO  NASA Headquarters                  ROSES 2025: A.16 Cryosphere
  12/07/2026 (in 13 days)  G27AS00047         Geological Survey                  Cooperative Agreement for affiliated Partner with
  12/07/2026 (in 13 days)  G27AS00062         Geological Survey                  Cooperative Agreement for affiliated Partner with

fetchOpportunity 320753 (synopsis): PD-19-127Y  Science of Learning and Augmented Intelligence (SL)
  agency: U.S. National Science Foundation (NSF), top agency U.S. National Science Foundation
  award ceiling none, award floor $550, estimated total funding not given, cost sharing False
  posted Sep 19, 2019 12:00:00 AM EDT, closes Feb 10, 2027 12:00:00 AM EST, archive Sep 03, 2027 12:00:00 AM EDT
  eligibility: 99 Unrestricted (i.e., open to any type of entity above), subject to any
  additional eligibility text: (empty)
  instruments: ['Grant'], ALN ['47.075']
  page for people: https://www.grants.gov/search-results-detail/320753

fetchOpportunity 358687 (forecast): W519TC-25-S-0001  Broad Agency Announcement for Fundamental AI Research
  agency: Army Contracting Command Rock Island (DOD-AMC-ACCRI), top agency Department of Defense
  award ceiling not given, award floor not given, estimated total funding not given, cost sharing False
  forecast posted Apr 16, 2025 12:00:00 AM EDT, est. synopsis not given, est. close not given, fiscal year 2025
  eligibility: 25 Others (see text field entitled "Additional Information on Eligibility
  additional eligibility text: Eligible applicants under this BAA include institutions of higher education, nonprofit organizations, state and local governments, foreign organizations, foreign public entities, and for-profit organi
  instruments: ['Cooperative Agreement'], ALN ['12.431']
  page for people: https://www.grants.gov/search-results-detail/358687

Source: Grants.gov search2 and fetchOpportunity APIs, accessed 24 November 2026 00:31 UTC.
```

### 2. robots.txt, the API guide and disclaimers, the status codes, and what the API does with mistakes (browser)

11 page loads and 18 in-page `fetch()` calls. Error answers from the API (403, 502) carry no CORS header, so in the browser they surface as `TypeError: Failed to fetch`; block 4 shows the real status codes with curl.

```python
import json, re, time

API = "https://api.grants.gov/v1/api"
WWW = "https://www.grants.gov"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]

def page(url, wait_for=None, tries=30):
    goto_url(url)
    wait_for_load()
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    txt = ""
    for _ in range(tries):
        txt = js("document.body ? document.body.innerText : (document.documentElement.textContent || '')") or ""
        if (wait_for and wait_for in txt) or (not wait_for and txt.strip()):
            break
        time.sleep(0.5)
    return st, " ".join(txt.split())

def robots_groups(txt):
    """RFC 9309 groups -> {agent (lower case): [(allow?, pattern)]}; consecutive User-agent lines share a group."""
    groups, agents, last_was_ua = {}, [], False
    for line in txt.splitlines():
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        k, v = (x.strip() for x in line.split(":", 1))
        k = k.lower()
        if k == "user-agent":
            agents = agents if last_was_ua else []
            agents.append(v.lower())
            groups.setdefault(v.lower(), [])
            last_was_ua = True
        elif k in ("allow", "disallow"):
            last_was_ua = False
            for a in agents:
                groups[a].append((k == "allow", v))
        else:
            last_was_ua = False
    return groups

def allowed(rules, path):
    """Longest matching pattern wins, Allow wins a tie; '*' is any run of characters, '$' ends the path."""
    best = (-1, True)
    for allow, pat in rules:
        if not pat:
            continue
        rx = "^" + re.escape(pat).replace(r"\*", ".*").replace(r"\$", "$")
        if re.match(rx, path) and (len(pat), allow) > best:
            best = (len(pat), allow)
    return best[1]

START_JS = """(() => { window.__g = window.__g || {}; const id = String(Math.random()).slice(2); window.__g[id] = null;
  fetch(%s, %s).then(async r => { window.__g[id] = {status: r.status, type: r.headers.get('content-type') || '',
      text: await r.text()}; }).catch(e => { window.__g[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__g[%s]; if (v) delete window.__g[%s]; return v; })()"""

def call(url, opts):
    rid = json.dumps(js(START_JS % (json.dumps(url), json.dumps(opts))))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{url}: no answer after 60 s")
        time.sleep(0.2)
    time.sleep(1.0)
    return r

def post(endpoint, body, raw=False, headers=None):
    return call(f"{API}/{endpoint}", {"method": "POST", "credentials": "omit", "headers": headers or {},
                                      "body": body if raw else json.dumps(body)})

# 1) robots.txt on both hosts. The API host answers 403 JSON (an API Gateway "no route" answer), which RFC 9309
#    (2.3.1.3) treats like 4xx "unavailable": no rules. www.grants.gov is read as a page.
st, txt = page(WWW + "/robots.txt")
g = robots_groups(js("document.body.innerText"))
print(f"{WWW}/robots.txt HTTP {st}: {txt!r}; groups {sorted(g)}; named AI-agent groups: {[a for a in AGENTS[1:] if a.lower() in g]}")
for path in ("/api/api-guide", "/api/common/search2", "/api/common/fetchopportunity", "/search-results-detail/320753"):
    rules = {a: g.get(a.lower(), g.get("*", [])) for a in AGENTS}
    print(f"  {path:<32} {'allowed for all ' + str(len(AGENTS)) + ' agents' if all(allowed(r, path) for r in rules.values()) else 'DISALLOWED'}")
st, txt = page("https://api.grants.gov/robots.txt")  # a page load: fetch() of it fails CORS (403 has no CORS header)
print(f"https://api.grants.gov/robots.txt HTTP {st}: {txt[:60]!r} -> {'no rules for any agent' if 400 <= (st or 0) < 500 else 'CHECK BY HAND'}")

# 2) Terms: the API guide and endpoint pages (no key, unrestricted), the two disclaimers, the status codes (429).
CHECKS = [
    ("/api/api-guide", "API GUIDE", ["Authentication and authorization are not required for the following APIs: Endpoint: search2 Endpoint: fetchOpportunity",
                                      "Unrestricted Access",
                                      "is designed to be accessible without user authentication (in other words, no login or authentication key required)",
                                      "allowing the public and developers alike to conduct thorough searches",
                                      "some will require an API key from Grants.gov"]),
    ("/api/common/search2", "SEARCH2", ["Authentication and authorization is not required for search2", '"aln": ""']),
    ("/api/common/fetchopportunity", "FETCHOPPORTUNITY", ["Authentication and authorization is not required for fetchOpportunity"]),
    ("/api/status-codes", "STATUS CODES", ["429 Too Many Requests Too many of the user’s requests hit the API too quickly. We recommend an exponential backoff of your requests."]),
    ("/exit-disclaimer", "EXIT DISCLAIMER", ["these sites are not endorsed by the federal government"]),
    ("https://www.hhs.gov/digital/policies/disclaimers/index.html", "Website Disclaimers",
     ["Reference in this website to any specific commercial product, process, service, manufacturer, or company is not an endorsement or recommendation by the U.S. Government",
      "The stock photos are not in the public domain and may not be utilized by others under the HHS license."]),
]
WORDS = ("artificial intelligence", "machine learning", "text and data mining", "scrap", "crawl", "robot", "automated", "non-commercial", "rate limit")
for path, title, needles in CHECKS:
    st, t = page(path if path.startswith("http") else WWW + path, title)
    for n in needles:
        print(f"{path} HTTP {st}: {'found' if n in t else 'MISSING'}: {n[:100]!r}")
    print(f"{path}: mentions {[w for w in WORDS if w in t.lower()] or 'none'} of {list(WORDS)}")
page(WWW + "/api/common/search2", "SEARCH2")
print(f"footer 'Disclaimers' link on www.grants.gov: {js('[...document.querySelectorAll(\"a\")].filter(a => a.textContent.trim() === \"Disclaimers\").map(a => a.href)')}")

# 3) What the API does with mistakes (from a www.grants.gov page; no Content-Type header, see block 1).
def brief(r):
    if r["status"] == 0:  # error answers (403, 502) carry no Access-Control-Allow-Origin, so fetch() sees nothing
        return f"fetch() failed ({r['text']}): CORS hides the error status, block 4 shows it with curl"
    if "json" not in r["type"]:
        return f"HTTP {r['status']} {r['type'] or '-'} {' '.join(r['text'].split())[:70]!r}"
    d = json.loads(r["text"])
    d.pop("token", None)
    data = d.get("data") or {}
    if "hitCount" in data:
        return f"HTTP {r['status']} errorcode {d.get('errorcode')} hitCount {data['hitCount']}"
    if "id" in data or "revision" in data:
        return f"HTTP {r['status']} errorcode {d.get('errorcode')} id {data.get('id')} number {data.get('opportunityNumber')}"
    return f"HTTP {r['status']} {json.dumps(d)[:90]}"

AI = {"keyword": "artificial intelligence", "rows": 1}
for label, r in (
    ("baseline: forecasted|posted                ", post("search2", {**AI, "oppStatuses": "forecasted|posted"})),
    ("oppStatuses omitted                        ", post("search2", AI)),
    ("oppStatuses 'forecasted,posted' (comma)    ", post("search2", {**AI, "oppStatuses": "forecasted,posted"})),
    ("aln 47.075 (the name the docs use)         ", post("search2", {**AI, "aln": "47.075"})),
    ("cfda 47.075 (the name searchParams echoes) ", post("search2", {**AI, "cfda": "47.075"})),
    ("agencies DOD (top-level code)              ", post("search2", {**AI, "agencies": "DOD"})),
    ("agencies DOD* (prefix)                     ", post("search2", {**AI, "agencies": "DOD*"})),
    ("agencies NSF|DOD-AMC-ACCRI                 ", post("search2", {**AI, "agencies": "NSF|DOD-AMC-ACCRI"})),
    ("eligibilities 23 (small businesses)        ", post("search2", {**AI, "eligibilities": "23"})),
    ("fundingCategories ST                       ", post("search2", {**AI, "fundingCategories": "ST"})),
    ("sortBy closeDate|asc                       ", post("search2", {**AI, "sortBy": "closeDate|asc"})),
    ("sortBy 'closedate' (unknown)               ", post("search2", {**AI, "sortBy": "closedate"})),
    ("body is not JSON                           ", post("search2", "keyword=ai", raw=True)),
    ("with Content-Type: application/json        ", post("search2", AI, headers={"Content-Type": "application/json"})),
    ("GET search2                                ", call(f"{API}/search2", {"credentials": "omit"})),
    ("fetchOpportunity 320753                    ", post("fetchOpportunity", {"opportunityId": 320753})),
    ("fetchOpportunity '320753' (string)         ", post("fetchOpportunity", {"opportunityId": "320753"})),
    ("fetchOpportunity 999999999 (no such id)    ", post("fetchOpportunity", {"opportunityId": 999999999})),
):
    print(f"{label} {brief(r)}")

# 4) The page for people: the opportunity id (not the number) goes in the URL.
st, t = page(WWW + "/search-results-detail/320753", "PD-19-127Y")
print(f"\n{WWW}/search-results-detail/320753 HTTP {st}: {'shows PD-19-127Y' if 'PD-19-127Y' in t else 'PD-19-127Y NOT shown after 15 s'}, "
      f"{'Award Ceiling' if 'Award Ceiling' in t else 'no Award Ceiling label'}, {len(t):,} chars of text")
page(WWW + "/api/common/search2", "SEARCH2")  # back to a docs page for block 1
```

Output (from the third run on 2026-11-23, 23:40 UTC; the 23:37 run printed the same lines):

```text
https://www.grants.gov/robots.txt HTTP 200: 'User-agent: * Allow: /'; groups ['*']; named AI-agent groups: []
  /api/api-guide                   allowed for all 11 agents
  /api/common/search2              allowed for all 11 agents
  /api/common/fetchopportunity     allowed for all 11 agents
  /search-results-detail/320753    allowed for all 11 agents
https://api.grants.gov/robots.txt HTTP 403: '{"message":"Missing Authentication Token"}' -> no rules for any agent
/api/api-guide HTTP 200: found: 'Authentication and authorization are not required for the following APIs: Endpoint: search2 Endpoint'
/api/api-guide HTTP 200: found: 'Unrestricted Access'
/api/api-guide HTTP 200: found: 'is designed to be accessible without user authentication (in other words, no login or authentication'
/api/api-guide HTTP 200: found: 'allowing the public and developers alike to conduct thorough searches'
/api/api-guide HTTP 200: found: 'some will require an API key from Grants.gov'
/api/api-guide: mentions none of ['artificial intelligence', 'machine learning', 'text and data mining', 'scrap', 'crawl', 'robot', 'automated', 'non-commercial', 'rate limit']
/api/common/search2 HTTP 200: found: 'Authentication and authorization is not required for search2'
/api/common/search2 HTTP 200: found: '"aln": ""'
/api/common/search2: mentions none of ['artificial intelligence', 'machine learning', 'text and data mining', 'scrap', 'crawl', 'robot', 'automated', 'non-commercial', 'rate limit']
/api/common/fetchopportunity HTTP 200: found: 'Authentication and authorization is not required for fetchOpportunity'
/api/common/fetchopportunity: mentions none of ['artificial intelligence', 'machine learning', 'text and data mining', 'scrap', 'crawl', 'robot', 'automated', 'non-commercial', 'rate limit']
/api/status-codes HTTP 200: found: '429 Too Many Requests Too many of the user’s requests hit the API too quickly. We recommend an expon'
/api/status-codes: mentions none of ['artificial intelligence', 'machine learning', 'text and data mining', 'scrap', 'crawl', 'robot', 'automated', 'non-commercial', 'rate limit']
/exit-disclaimer HTTP 200: found: 'these sites are not endorsed by the federal government'
/exit-disclaimer: mentions none of ['artificial intelligence', 'machine learning', 'text and data mining', 'scrap', 'crawl', 'robot', 'automated', 'non-commercial', 'rate limit']
https://www.hhs.gov/digital/policies/disclaimers/index.html HTTP 200: found: 'Reference in this website to any specific commercial product, process, service, manufacturer, or com'
https://www.hhs.gov/digital/policies/disclaimers/index.html HTTP 200: found: 'The stock photos are not in the public domain and may not be utilized by others under the HHS licens'
https://www.hhs.gov/digital/policies/disclaimers/index.html: mentions none of ['artificial intelligence', 'machine learning', 'text and data mining', 'scrap', 'crawl', 'robot', 'automated', 'non-commercial', 'rate limit']
footer 'Disclaimers' link on www.grants.gov: ['https://www.grants.gov/exit-disclaimer']
baseline: forecasted|posted                 HTTP 200 errorcode 0 hitCount 149
oppStatuses omitted                         HTTP 200 errorcode 0 hitCount 149
oppStatuses 'forecasted,posted' (comma)     HTTP 200 errorcode 0 hitCount 0
aln 47.075 (the name the docs use)          HTTP 200 errorcode 0 hitCount 149
cfda 47.075 (the name searchParams echoes)  HTTP 200 errorcode 0 hitCount 6
agencies DOD (top-level code)               HTTP 200 errorcode 0 hitCount 0
agencies DOD* (prefix)                      HTTP 200 errorcode 0 hitCount 41
agencies NSF|DOD-AMC-ACCRI                  HTTP 200 errorcode 0 hitCount 20
eligibilities 23 (small businesses)         HTTP 200 errorcode 0 hitCount 41
fundingCategories ST                        HTTP 200 errorcode 0 hitCount 68
sortBy closeDate|asc                        HTTP 200 errorcode 0 hitCount 149
sortBy 'closedate' (unknown)                HTTP 200 errorcode 0 hitCount 0
body is not JSON                            fetch() failed (TypeError: Failed to fetch): CORS hides the error status, block 4 shows it with curl
with Content-Type: application/json         fetch() failed (TypeError: Failed to fetch): CORS hides the error status, block 4 shows it with curl
GET search2                                 fetch() failed (TypeError: Failed to fetch): CORS hides the error status, block 4 shows it with curl
fetchOpportunity 320753                     HTTP 200 errorcode 0 id 320753 number PD-19-127Y
fetchOpportunity '320753' (string)          HTTP 200 errorcode 0 id 320753 number PD-19-127Y
fetchOpportunity 999999999 (no such id)     HTTP 200 errorcode 0 id None number None

https://www.grants.gov/search-results-detail/320753 HTTP 200: shows PD-19-127Y, Award Ceiling, 6,690 chars of text
```

### 3. Every hit with Python urllib: robots check for every agent, paging with startRecordNum, award data for the top 5, CSV (no browser)

`startRecordNum` is a 0-based offset; 149 hits took 3 calls of 50. Each `fetchOpportunity` answer is 7-191 KB (the opportunity's whole history comes with it), so the block fetches details only for the top 5. Dates are written as `YYYY-MM-DD`. `cell()` puts a `'` before any value that starts with `=`, `+`, `-` or `@` (also the full-width forms, or after leading spaces, tabs or line breaks), so text from the API opens as text, not as a formula, in a spreadsheet. Excel drops that `'` when the sheet is saved back to CSV, so a re-saved file needs the same check before it is opened again.

```python
import collections, csv, email.utils, html, json, ssl, sys, time, urllib.error, urllib.request, urllib.robotparser
from datetime import datetime, timezone

KEYWORD = "artificial intelligence"
STATUSES = "forecasted|posted"
PAGE = 50        # rows per search2 call; startRecordNum moves through the list
DETAILS = 5      # fetchOpportunity calls for the top hits (one call each, ~7-190 KB)
OUT = "grants-gov-ai.csv"  # written to the current directory

UA = "grants-gov-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
API = "https://api.grants.gov/v1/api"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]
PAUSE = 1.0  # no number is published; serial, 1 s apart, back off on 429
calls = collections.Counter()

FORMULA = ("=", "+", "-", "@", "\uff1d", "\uff0b", "\uff0d", "\uff20")  # ASCII and full-width = + - @

def cell(v):
    """API text for a CSV cell. A value that starts with = + - @ (also full-width, or after leading spaces,
    tabs or line breaks) can run as a formula when a spreadsheet opens the file, so it gets a leading '
    and opens as text. Excel drops that ' if the sheet is saved back to CSV."""
    v = str(v)
    return "'" + v if v[:1] in ("\t", "\r", "\n") or v.lstrip().startswith(FORMULA) else v

def retry_wait(value, default):
    v = (value or "").strip()
    if v.isdigit():
        return int(v)
    try:
        return max(0, int((email.utils.parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()) + 1)
    except (TypeError, ValueError):
        return default

def http(url, body=None):
    """GET, or POST JSON when `body` is given -> (status, bytes). 4xx other than 429 is returned; waits on
    429/5xx or a network error, doubling the wait (Retry-After, else 15 s, then 30 s; over 120 s exits)."""
    data = json.dumps(body).encode() if body is not None else None
    hdr = {"User-Agent": UA, **({"Content-Type": "application/json"} if data else {})}
    for attempt in range(3):
        time.sleep(PAUSE)
        calls["POST" if data else "GET"] += 1
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=hdr), timeout=60) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 2:
                wait = retry_wait(e.headers.get("Retry-After"), 15 * 2 ** attempt)
                if wait > 120:
                    sys.exit(f"{url}: server asks to wait {wait} s: stopping")
                time.sleep(wait)
                continue
            return e.code, e.read()
        except urllib.error.URLError as e:
            if isinstance(e.reason, ssl.SSLError):
                raise
            if attempt < 2:
                time.sleep(15 * 2 ** attempt)
                continue
            sys.exit(f"{url}: {e}")

def api(endpoint, body):
    st, raw = http(f"{API}/{endpoint}", body)
    if st != 200:
        sys.exit(f"{endpoint}: HTTP {st} {raw[:200]!r}")
    d = json.loads(raw)
    d.pop("token", None)  # anonymous session token: never print or store it
    if d.get("errorcode") != 0:
        sys.exit(f"{endpoint}: errorcode {d.get('errorcode')} {d.get('msg')!r}")
    return d["data"], len(raw)

def day(s):
    return datetime.strptime(s, "%m/%d/%Y").date() if s else None

# 1) robots.txt. api.grants.gov answers 403 JSON: unavailable, so no rules (RFC 9309 2.3.1.3). Python's
#    robotparser would treat 401/403 as "disallow all", so feed it nothing instead of letting it read().
st, body = http("https://api.grants.gov/robots.txt")
if st != 200 and not (400 <= st < 500 and st != 429):
    sys.exit(f"robots.txt api.grants.gov: HTTP {st}, rules unknown: stop")
rp = urllib.robotparser.RobotFileParser()
rp.parse(body.decode(errors="replace").splitlines() if st == 200 else [])
ok = all(rp.can_fetch(a, API + "/search2") and rp.can_fetch(a, API + "/fetchOpportunity") for a in AGENTS)
print(f"robots https://api.grants.gov: HTTP {st} {body[:45]!r}: search2 and fetchOpportunity "
      f"{'allowed' if ok else 'DISALLOWED'} for all {len(AGENTS)} agents")
if not ok:
    sys.exit("robots.txt now disallows the API: stop")
try:
    http("https://www.grants.gov/robots.txt")
except urllib.error.URLError as e:
    print(f"robots https://www.grants.gov: {e.reason.__class__.__name__}: {getattr(e.reason, 'verify_message', e.reason)} "
          f"(the server sends an incomplete certificate chain; block 2 reads it in a browser)")

# 2) Every hit, PAGE rows at a time.
now = datetime.now(timezone.utc)
hits, total, size = [], None, 0
while total is None or len(hits) < total:
    d, n = api("search2", {"keyword": KEYWORD, "oppStatuses": STATUSES, "rows": PAGE, "startRecordNum": len(hits)})
    size += n
    total = d["hitCount"] if total is None else total
    if not d["oppHits"]:
        break
    hits += d["oppHits"]
ids = [h["id"] for h in hits]
partial = len(set(ids)) < total   # an empty page came back early, or pages overlapped
print(f"\n{KEYWORD!r}, {STATUSES}, checked {now:%Y-%m-%d %H:%M} UTC: hitCount {total}, read {len(hits)} "
      f"({len(set(ids))} distinct) in {calls['POST']} calls of {PAGE} ({size / 1e3:.0f} KB)")
if partial:
    print(f"PARTIAL: only {len(set(ids))} distinct of {total} hits came back; the CSV below is incomplete, re-run later")

# 3) Award ceiling, floor and eligibility for the top hits (default order).
extra = {}
for h in hits[:DETAILS]:
    o, n = api("fetchOpportunity", {"opportunityId": int(h["id"])})
    if str(o.get("id")) != h["id"]:
        sys.exit(f"fetchOpportunity {h['id']}: no such opportunity")
    b = o.get("synopsis") or o.get("forecast") or {}
    extra[h["id"]] = {"award_ceiling": b.get("awardCeiling") or "", "award_floor": b.get("awardFloor") or "",
                      "estimated_funding": b.get("estimatedFunding") or "",
                      "eligibility_codes": " ".join(sorted(a["id"] for a in b.get("applicantTypes") or [])),  # order varies per call
                      "detail_kb": round(n / 1e3)}

cols = ["number", "id", "status", "doc_type", "agency_code", "agency", "title", "open_date", "close_date", "aln",
        "award_ceiling", "award_floor", "estimated_funding", "eligibility_codes", "url"]
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    for h in hits:
        e = extra.get(h["id"], {})
        row = {"number": h["number"], "id": h["id"], "status": h["oppStatus"], "doc_type": h["docType"],
               "agency_code": h["agencyCode"], "agency": h["agency"], "title": html.unescape(h["title"]),  # titles can hold &amp;
               "open_date": str(day(h["openDate"]) or ""), "close_date": str(day(h["closeDate"]) or ""),
               "aln": " ".join(h.get("cfdaList") or []),
               **{k: e.get(k, "") for k in ("award_ceiling", "award_floor", "estimated_funding", "eligibility_codes")},
               "url": f"https://www.grants.gov/search-results-detail/{h['id']}"}
        w.writerow({k: cell(v) for k, v in row.items()})  # every value is API text or derived from it
print(f"written to {OUT} ({len(hits)} rows{', ' + str(len(set(ids))) + ' distinct of ' + str(total) + ', PARTIAL' if partial else ''}, dates as YYYY-MM-DD, award columns filled for the top {DETAILS})")

print(f"  by status: {dict(collections.Counter(h['oppStatus'] for h in hits))}")
print(f"  top agencies: {collections.Counter(h['agency'] for h in hits).most_common(5)}")
closing = sorted(((day(h["closeDate"]), h) for h in hits if h["closeDate"]), key=lambda x: x[0])
soon = [(c, h) for c, h in closing if (c - now.date()).days <= 30]
latest = f"{closing[-1][0]} ({closing[-1][1]['number']})" if closing else "none"
print(f"  closing within 30 days: {len(soon)}; closing date in the past: {sum(c < now.date() for c, _ in closing)}; "
      f"latest close {latest}")
print(f"  no close date ('' in closeDate): {dict(collections.Counter(h['oppStatus'] for h in hits if not h['closeDate']))}")
print(f"\ntop {DETAILS} with award data:")
for h in hits[:DETAILS]:
    e = extra[h["id"]]
    print(f"  {h['number']:<22} {h['oppStatus']:<10} ceiling {e['award_ceiling'] or '-':>9}  floor {e['award_floor'] or '-':>7}  "
          f"eligibility {e['eligibility_codes'] or '-':<6} ({e['detail_kb']} KB)  {html.unescape(h['title'])[:44]}")
print(f"calls: {dict(calls)}")
print("Source: Grants.gov search2 and fetchOpportunity APIs.")
```

Output (re-run on 2026-11-24 after the code-review fixes, 00:28 UTC; identical to the 23:39-23:44 runs on 2026-11-23 apart from the time):

```text
robots https://api.grants.gov: HTTP 403 b'{"message":"Missing Authentication Token"}': search2 and fetchOpportunity allowed for all 11 agents
robots https://www.grants.gov: SSLCertVerificationError: unable to get local issuer certificate (the server sends an incomplete certificate chain; block 2 reads it in a browser)

'artificial intelligence', forecasted|posted, checked 2026-11-24 00:28 UTC: hitCount 149, read 149 (149 distinct) in 3 calls of 50 (73 KB)
written to grants-gov-ai.csv (149 rows, dates as YYYY-MM-DD, award columns filled for the top 5)
  by status: {'posted': 124, 'forecasted': 25}
  top agencies: [('National Institutes of Health', 40), ('U.S. National Science Foundation', 19), ('Dept of the Army -- Materiel Command', 8), ('Air Force Office of Scientific Research', 8), ('Geological Survey', 6)]
  closing within 30 days: 20; closing date in the past: 0; latest close 2099-01-01 (DFOP0018819)
  no close date ('' in closeDate): {'forecasted': 25, 'posted': 6}

top 5 with award data:
  PD-19-127Y             posted     ceiling      none  floor     550  eligibility 99     (191 KB)  Science of Learning and Augmented Intelligen
  W519TC-25-S-0001       forecasted ceiling         -  floor       -  eligibility 25     (7 KB)  Broad Agency Announcement for Fundamental AI
  PAS-TUNIS- APS FY2026  forecasted ceiling    200000  floor   10000  eligibility 00 12 13 20 25 (16 KB)  Annual Program Statement (APS) For Fiscal Ye
  26-504                 posted     ceiling      none  floor  220000  eligibility 25     (35 KB)  Postdoctoral Research Fellowships in Biology
  25-531                 posted     ceiling   1200000  floor    none  eligibility 25     (48 KB)  Cybersecurity Innovation for Cyberinfrastruc
calls: {'GET': 2, 'POST': 8}
Source: Grants.gov search2 and fetchOpportunity APIs.
```

The CSV columns: `number, id, status, doc_type, agency_code, agency, title, open_date, close_date, aln, award_ceiling, award_floor, estimated_funding, eligibility_codes, url`.

### 4. curl, headers and mistakes

```bash
S=https://api.grants.gov/v1/api/search2
F=https://api.grants.gov/v1/api/fetchOpportunity
UA='grants-gov-skill-example/1.0 (+https://github.com/browser-use/browser-harness)'
# data calls retry 429/5xx/timeouts up to 3 times (curl waits Retry-After, else 1 s, 2 s, 4 s) and give up after 120 s;
# the mistake probes further down have no retry, so the 502 shows once
RETRY=(--retry 3 --retry-max-time 120)
# open and forecasted opportunities for a phrase, NSF and every DOD sub-agency, closing soonest first
curl -sS --fail "${RETRY[@]}" -A "$UA" -X POST "$S" -H 'Content-Type: application/json' \
  -d '{"keyword": "\"machine learning\"", "oppStatuses": "forecasted|posted", "agencies": "NSF|DOD*", "sortBy": "closeDate|asc", "rows": 5}' \
  | python3 -c 'import sys, json, html
d = json.load(sys.stdin)
if d["errorcode"] != 0: sys.exit("errorcode %s %s" % (d["errorcode"], d["msg"]))
print("hitCount", d["data"]["hitCount"], {o["value"]: o["count"] for o in d["data"]["oppStatusOptions"]})
for h in d["data"]["oppHits"]:
    print(h["id"], "|", h["number"], "|", h["oppStatus"], "|", h["openDate"], "->", h["closeDate"] or "-", "|", h["agencyCode"], "|", html.unescape(h["title"])[:60])'
sleep 1
# award ceiling, floor and eligibility for one opportunity: the id (first column above), not the number;
# 361526 is DE-FOA-0003612, an opportunity with all three award fields filled
curl -sS --fail "${RETRY[@]}" -A "$UA" -X POST "$F" -H 'Content-Type: application/json' -d '{"opportunityId": 361526}' \
  | python3 -c 'import sys, json, html
o = json.load(sys.stdin)["data"]
if "id" not in o: sys.exit("no such opportunity")
b = o.get("synopsis") or o.get("forecast")
print(o["opportunityNumber"], "|", html.unescape(o["opportunityTitle"]), "|", o["agencyDetails"]["agencyName"])
print("ceiling", b.get("awardCeiling"), "floor", b.get("awardFloor"), "estimated total", b.get("estimatedFunding"), "| closes", b.get("responseDate"))
print("eligibility", [a["id"] + " " + a["description"][:40] for a in b.get("applicantTypes") or []])'
sleep 1
# response headers: JSON, CORS open to any origin, no cache or rate-limit headers
curl -sS "${RETRY[@]}" -A "$UA" -D - -o /dev/null -X POST "$S" -H 'Content-Type: application/json' -d '{"keyword": "artificial intelligence", "rows": 1}' \
  | tr -d '\r' | grep -iE '^(HTTP/|(content-type|access-control-allow-[a-z]+|cache-control|retry-after|x-ratelimit-[a-z]+|ratelimit[a-z-]*):)'
sleep 1
# mistakes: GET, a CORS preflight (OPTIONS), a body that is not JSON, a comma in oppStatuses, an unknown id
T=$(mktemp)
curl -sS -A "$UA" -o "$T" -w 'GET search2 -> HTTP %{http_code} ' "$S"; cat "$T"; echo; sleep 1
curl -sS -A "$UA" -o "$T" -w 'OPTIONS (preflight) -> HTTP %{http_code} ' -X OPTIONS "$S" -H 'Origin: https://example.org' \
  -H 'Access-Control-Request-Method: POST' -H 'Access-Control-Request-Headers: content-type'; cat "$T"; echo; sleep 1
curl -sS -A "$UA" -o "$T" -w 'not JSON -> HTTP %{http_code} ' -X POST "$S" -H 'Content-Type: application/json' -d 'keyword=ai'; cat "$T"; echo; sleep 1
curl -sS -A "$UA" -X POST "$S" -H 'Content-Type: application/json' -d '{"keyword": "artificial intelligence", "oppStatuses": "forecasted,posted", "rows": 1}' \
  | python3 -c 'import sys, json; d = json.load(sys.stdin); print("oppStatuses with a comma -> errorcode", d["errorcode"], "hitCount", d["data"]["hitCount"])'
sleep 1
curl -sS -A "$UA" -X POST "$F" -H 'Content-Type: application/json' -d '{"opportunityId": 999999999}' \
  | python3 -c 'import sys, json; d = json.load(sys.stdin); print("unknown opportunityId -> errorcode", d["errorcode"], d["msg"], "| id in data:", "id" in d["data"])'
sleep 1
# www.grants.gov sends an incomplete certificate chain: plain curl fails, the API host does not
curl -sS -A "$UA" -o /dev/null -w 'www.grants.gov/robots.txt -> HTTP %{http_code}\n' https://www.grants.gov/robots.txt 2>&1 | head -1
rm -f "$T"
```

Output (re-run on 2026-11-24 after the code-review fixes, 00:28 UTC, which added the id column; the 23:39 and 23:41 runs on 2026-11-23 printed the same opportunities and headers):

```text
hitCount 27 {'posted': 25, 'closed': 15, 'archived': 397, 'forecasted': 2}
362871 | N0001426SF001 | posted | 06/18/2026 -> 12/11/2026 | DOD-ONR | Fiscal Year (FY) 2027 Department of the Navy (DoN) Historica
351404 | HM047623BAA0001 | posted | 12/15/2023 -> 12/14/2026 | DOD-NGIA | Boosting Innovative GEOINT - Science & Technology  Broad Age
352741 | N00173-24-S-BA01 | posted | 03/01/2024 -> 12/30/2026 | DOD-ONR-NRL | NRL Long Range Broad Agency Announcement (BAA) for Basic and
320753 | PD-19-127Y | posted | 09/19/2019 -> 02/10/2027 | NSF | Science of Learning and Augmented Intelligence (SL)
364165 | FA955027S0002 | posted | 10/28/2026 -> 02/19/2027 | DOD-AFOSR | AFRL/AFOSR-Taiwan NSTC Frontiers in Materials and Nanostruct
DE-FOA-0003612 | The Genesis Mission:  Transforming Science and Energy with AI | Office of Science
ceiling 16000000 floor 500000 estimated total 293760000 | closes Dec 17, 2026 12:00:00 AM EST
eligibility ['99 Unrestricted (i.e., open to any type of ']
HTTP/2 200
content-type: application/json
access-control-allow-origin: *
access-control-allow-headers: Content-Type,X-Amz-Date,Authorization,X-Api-Key,x-requested-with
access-control-allow-methods: OPTIONS,POST,GET,PUT,DELETE,PATCH
GET search2 -> HTTP 403 {"message":"Missing Authentication Token"}
OPTIONS (preflight) -> HTTP 403 {"message":"Missing Authentication Token"}
not JSON -> HTTP 502 {"message": "Internal server error"}
oppStatuses with a comma -> errorcode 0 hitCount 0
unknown opportunityId -> errorcode 0 Webservice Succeeds | id in data: False
curl: (60) SSL certificate problem: unable to get local issuer certificate
```

## Fields

| Field | Value | Notes |
|---|---|---|
| `errorcode`, `msg` | `0`, `"Webservice Succeeds"` | check both; an unknown `opportunityId` also returns these (see Gotchas) |
| `token` | a JWT-like string | an anonymous session token in every answer; not needed for anything here, so drop it and never log it |
| `data.hitCount` | `149` | hits for the statuses you asked for |
| `data.oppHits[].id` | `"320753"` (a string) | the id `fetchOpportunity` takes and the page for people uses: https://www.grants.gov/search-results-detail/320753 |
| `data.oppHits[].number` | `"PD-19-127Y"` | the agency's opportunity number; can contain spaces (`PAS-TUNIS- APS FY2026`) |
| `data.oppHits[].title` | `"Boosting Innovative GEOINT - Science &amp; Technology ..."` | HTML entities are not decoded |
| `data.oppHits[].agencyCode`, `agency` | `"DOD-AMC-ACCRI"`, `"Army Contracting Command Rock Island"` | the sub-agency; `fetchOpportunity`'s `topAgencyDetails` gives the department |
| `data.oppHits[].openDate`, `closeDate` | `"09/19/2019"`, `"02/10/2027"` | `MM/DD/YYYY` strings; `closeDate` is `""` on every forecast and on some posted ones |
| `data.oppHits[].oppStatus`, `docType` | `posted`/`synopsis`, `forecasted`/`forecast` | the only two pairs seen in 149 hits |
| `data.oppHits[].cfdaList` | `["47.075"]` | Assistance Listing numbers (ALN, formerly CFDA) |
| `data.oppStatusOptions` | `[{"value": "posted", "count": 124}, {"value": "closed", "count": 675}, ...]` | counts for all four statuses, whatever `oppStatuses` you sent |
| `data.agencies`, `eligibilities`, `fundingCategories`, `fundingInstruments`, `dateRangeOptions` | `[{"label": "Department of Defense", "value": "DOD", "count": 41, "subAgencyOptions": [...]}]` | facets for the current query: the codes to filter with |
| `synopsis` or `forecast` (fetchOpportunity) | object or absent | posted opportunities have `synopsis`, forecasts have `forecast`; the other key is missing |
| `awardCeiling`, `awardFloor`, `estimatedFunding` | `"16000000"`, `"500000"`, `"293760000"`; `"none"`; missing | strings; `...Formatted` twins add commas (`"16,000,000"`) |
| `applicantTypes` | `[{"id": "99", "description": "Unrestricted (i.e., open to any type of entity above), ..."}]` | eligibility codes; order varies between calls |
| `applicantEligibilityDesc` | free text | "Additional Information on Eligibility"; empty on PD-19-127Y, the full answer on W519TC-25-S-0001 |
| `responseDate` (synopsis), `estApplicationResponseDate` (forecast) | `"Feb 10, 2027 12:00:00 AM EST"` | a different date format from search2; `responseDateStr` is `"2027-02-10-00-00-00"` |
| `opportunityHistoryDetails` | list | 185,781 of the 191,136 bytes for 320753 |
| response headers | `content-type: application/json`, `access-control-allow-origin: *` | no `cache-control`, `retry-after` or rate-limit headers seen |

## Gotchas

- **POST JSON only.** `GET /v1/api/search2` is HTTP 403 `{"message":"Missing Authentication Token"}`, although the endpoint needs no key: the same answer comes back for `OPTIONS` and for `/robots.txt`. A body that is not JSON is HTTP 502 `{"message": "Internal server error"}`.
- **In a browser, leave out `Content-Type`.** With `Content-Type: application/json` the browser sends a CORS preflight, which is HTTP 403, and `fetch()` fails. Without the header the POST is a simple request and works from any page. Error answers carry no CORS header, so a failed call shows only `TypeError: Failed to fetch` (block 2); retry from curl to see the status.
- **Silent zeroes.** These return HTTP 200, `errorcode` 0 and `hitCount 0`, never an error: `oppStatuses` with a comma (`forecasted,posted`; use a pipe), an unknown `sortBy` (`closedate`; use `closeDate|asc`, `openDate|desc`), and a top-level agency code that has sub-agencies (`DOD`; use `DOD*` for all 41, or a sub-agency code such as `DOD-AMC-ACCRI`). `NSF` works as is because it has no sub-agency codes. Check `hitCount` against the facet counts before you report "nothing found".
- **`aln` is ignored; `cfda` works.** The docs' request body uses `aln`, but `aln: "47.075"` left the 149 hits unchanged while `cfda: "47.075"` gave 6 (block 2); `searchParams` in the answer echoes `cfda`.
- **Keywords are not ANDed.** "artificial intelligence" gave 149 hits, "artificial" 122 and "intelligence" 143, so the two-word search includes hits that do not match both words; `"\"artificial intelligence\""` (quoted) gave 113. The default order (`sortBy` empty) is not documented and is not by date or number; `relevance|desc` gave 0 hits.
- **Omitting `oppStatuses`** gave the same 149 as `forecasted|posted`; send it anyway so the scope is explicit. Add `closed|archived` for history (675 and 3,926 for this keyword).
- **Close dates.** `closeDate` is `""` on all 25 forecasts and on 6 of the 124 posted hits (PD-26-367Y, PWEAA2023, FA955026S0001, N0016424SNB35, FA7000-21-S-0001, W911NF-22-S-0011); `sortBy closeDate|asc` puts them last. Some close dates are placeholders far in the future: DFOP0018819 `01/01/2099`, 27-501 `11/19/2076`. Block 3 found no posted hit with a close date in the past.
- **Forecasts are estimates.** `fetchOpportunity` on a forecast has no `synopsis`; award fields can be missing entirely (W519TC-25-S-0001) or present (PAS-TUNIS- APS FY2026: ceiling 200000, floor 10000). Estimated dates can already be past while the status is still `forecasted` (that forecast's `estApplicationResponseDate` is Jun 08, 2026; the FY2025 one's Jul 06, 2025).
- **Award amounts are agency-entered strings.** `"none"` is common; PD-19-127Y has floor `"550"` and ceiling `"none"`; 25-531 has ceiling `"1200000"` and floor `"none"`. Print what is there; do not compute with `"none"`.
- **`fetchOpportunity` with an unknown id** answers HTTP 200, `errorcode` 0, "Webservice Succeeds", and a `data` object without `id`; check that `data.id` equals the id you asked for. A string id (`"320753"`) works like a number. `{"opportunityNumber": ...}` is not a lookup: it answered with a backend "not available" message.
- **Titles hold HTML entities** (`&amp;`); decode them with `html.unescape`.
- **Two date formats.** search2 uses `MM/DD/YYYY`; `fetchOpportunity` uses `Feb 10, 2027 12:00:00 AM EST` and `...Str` fields like `2027-02-10-00-00-00`.
- **`rows` has no documented maximum.** `rows: 5000` with only `oppStatuses: posted` returned all 790 posted opportunities in one call (281 KB, 0.87 s). Paging with `rows` and `startRecordNum` returned 149 distinct hits in block 3.
- **www.grants.gov sends an incomplete certificate chain.** Python and curl fail with "unable to get local issuer certificate" (blocks 3 and 4); browsers fill in the chain. api.grants.gov verifies normally, so the data path needs no `-k` or disabled verification.
- **Counts move.** Opportunities are posted and closed every day; date every count.
- **Tab marker.** The harness may set the tab title to a horse emoji; the blocks check `location.origin` and the page text, not the title.

## What does not work

- **GET requests** to the API: HTTP 403.
- **`Content-Type: application/json` from a browser page**: the preflight is HTTP 403 and `fetch()` fails.
- **`aln` as a filter**: ignored; use `cfda`.
- **`agencies: "DOD"`** and other top-level codes with sub-agencies: 0 hits; use `DOD*` or the sub-agency code.
- **Plain HTTPS to www.grants.gov from Python or curl** without adding the missing intermediate certificate: certificate verification fails.
- **Not tested:** the 429 response (never provoked), the keyed Grants.gov APIs, the staging host https://api.staging.grants.gov, the `fundingInstruments` and `dateRange` filters, and opportunities in `closed` or `archived` status beyond their counts.
