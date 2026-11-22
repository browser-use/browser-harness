# TED (Tenders Electronic Daily) - Find Open EU Public Tenders by Keyword, CPV Code or Buyer Country Published Since a Date: Title, Buyer, Country, Submission Deadline and Notice Link (Search API, POST JSON, no key)

Field-tested against api.ted.europa.eu, ted.europa.eu and docs.ted.europa.eu on 2026-11-21 (US Pacific afternoon; 23:26-23:42 UTC, which was 00:26-00:42 on Sunday 22 November in Brussels) using a fresh Browser Use cloud browser (logged out; one session, 23:29-23:41 UTC) plus Python `urllib` and `curl` from a Linux machine. 30 browser page loads (16 on ted.europa.eu, 11 on api.ted.europa.eu, 3 on docs.ted.europa.eu) and 64 in-page `fetch()` calls to the API (block 1 ran 3 times, block 2 three times), 73 curl calls (50 while exploring, 23 in three runs of block 4) and 10 urllib calls (block 3 twice), serial and at least 1 s apart, except one exploring curl call that ran during block 2's second run. Every API call was HTTP 200 except the deliberate probes below: HTTP 400 (unknown fields, a 2-letter country, a dashed date, `SORT BY ... ASC`, a broken quote, `limit` 0 and 251, too many fields per page, a page window past 15,000), HTTP 405 (GET) and HTTP 404 (robots.txt on api.ted.europa.eu and docs.ted.europa.eu). All 10 plain-HTTP requests to ted.europa.eu got HTTP 202 with an empty body and `x-amzn-waf-action: challenge` (see Gotchas). curl timed API answers at 0.22-1.41 s. No 429, no key, no login. Block 1's output below is its third run (23:39 UTC), block 2's its third (23:40; its section 5 comment was corrected afterwards, no code change), block 3's its second (23:41), block 4's its third (23:41). Between the last two runs of each block only the times, CloudFront ids, the navigation status of ted.europa.eu/robots.txt (200 or 202) and one tie in block 1's page 2 changed (see Gotchas). An independent re-run at 23:45-23:47 UTC (a new cloud browser, urllib, curl) reproduced all four outputs; only the times, CloudFront ids and the detail page's text length (1,151 characters) differed. After review on 2026-11-22, the blocks gained fixes (the lot count keeps lots that share a deadline, counts are labelled date-level, block 2 compares full per-lot datetimes, block 3 stops on `timedOut`, block 4 picks the earliest deadline by time) and re-ran at 00:59-01:02 UTC (a new cloud browser, urllib, curl): block 1 printed the same notices with the new label and lot counts (2 and 3 lots), block 2 the same deadline tally, blocks 3 and 4 the same totals. A second review (in the browser-use.com sync) made block 3 write the same 12 CSV columns when nothing is open; it re-ran at 01:54 UTC (urllib): the same report and header row (153 open notices at that time), and a watch list with no open notice wrote the 12-column header alone.

robots.txt (checked 2026-11-21, curl, `urllib.robotparser` and the cloud browser): https://api.ted.europa.eu/robots.txt answers HTTP 404 (JSON `"error":"Not Found"` to curl, a "Whitelabel Error Page" in the browser), so the API host has no rules and no named AI-agent groups; under RFC 9309 (section 2.3.1.3) an unavailable robots.txt (4xx) means a crawler "MAY access any resources". https://ted.europa.eu/robots.txt is readable only in a browser (plain HTTP gets the WAF challenge) and has a `User-Agent: *` group that disallows private pages (`/*/my-dashboard`, `/*/preferences`, `/c/portal/login`), Liferay internals (`/web/`, `/documents/`, `/api/jsonws/`, `/*/index` and others) and dynamic search results (`Allow: /*/search/result$`, `Disallow: /*/search/result?`), plus named groups only for `Sogou web spider` and `PetalBot` (`Disallow: /`) and `msnbot/bingbot` (`Crawl-delay: 1`). No group names GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot or Bytespider, so they fall under `*`, which allows `/en/notice/-/detail/<id>`, `/en/notice/<id>/pdf`, `/en/notice/<id>/xml` and `/en/legal-notice` (block 2 checks all 11 agents with RFC 9309 matching). https://docs.ted.europa.eu/robots.txt answers HTTP 404: no rules. This skill reads only the API; it prints notice links for people and never loads ted.europa.eu search result pages. Terms: the TED legal notice https://ted.europa.eu/en/legal-notice says "Unless otherwise noted, the procurement notices published in the Supplement to the Official Journal of the European Union can be freely reused, for commercial or non-commercial purposes", under the "Commission Decision of 12 December 2011 on the reuse of Commission documents" (the page links https://eur-lex.europa.eu/eli/dec/2011/833/oj, Decision 2011/833/EU); the editorial content of the SIMAP websites (TED, TED eNotices2, TED Developer Docs and TED Developer Portal) "is licensed under the Creative Commons Attribution 4.0 International (CC BY 4.0) license", and "The SIMAP's system metadata is dedicated to the public domain in accordance with the Creative Commons Universal Public Domain Dedication deed (CC0 1.0)". It names no AI, machine learning, text and data mining, scraping, crawling or robots (block 2 checks). The API docs https://docs.ted.europa.eu/api/latest/index.html say "TED API allows anonymous access to all services manipulating published notices (i.e., searching for or retrieving notices already published on TED)" and "The Search API does not require a key."; the Search API page says it "is primarily targeted at data reusers and does not require authentication". Naming: this skill writes "TED (Tenders Electronic Daily)" in plain text and shows no logo, because the legal notice says "The SIMAP system's logos (including that of TED) may not be used without the prior consent of the Publications Office of the European Union" and that "trademarks, registered designs, logos and names, are excluded from the Commission's reuse policy". This skill is not affiliated with or endorsed by the Publications Office of the European Union or any EU institution. The legal notice also warns that some content may need extra rights where it "depicts identifiable private individuals or includes third-party works"; this skill reads notice metadata (titles, buyers, dates).

## Quick summary

- **No scraping.** `POST https://api.ted.europa.eu/v3/notices/search` with JSON `{"query": "<expert query>", "fields": [...], "limit": n, "page": p}` -> `{"notices": [...], "totalNoticeCount": 93, "iterationNextToken": ..., "timedOut": false}`. The query is TED expert-search syntax, e.g. `FT~"cloud computing" AND buyer-country=DEU AND classification-cpv=72000000 AND publication-date>=20261115 AND form-type=competition AND deadline-receipt-request>=today() SORT BY deadline-receipt-request`. JSON, no key, no login. GET is HTTP 405.
- **Answers (block 1, 23:39 UTC):** "cloud computing" since 2026-11-01: **4 open notices** (of 11 matches; 7 are contract award notices), the soonest **777211-2026**, Junta de Gobierno de la Diputación Provincial de Huelva (ESP), deadline **2026-11-23 23:59 +01:00**. IT services (CPV 72000000) from German buyers since 2026-11-15: **93 open**, the soonest **808918-2026** (Charité - Universitätsmedizin Berlin, "Implementierung SAP S/4 HANA-Systems für die CFM", 2026-11-23 10:00 +01:00). "electric buses" since 2026-10-01: **65 open** (Germany, Poland, Czechia first). School catering (CPV 55524000) in France since 2026-11-01: 0. Block 3's watch list (CPV 72000000 or 48000000, buyers in DEU or AUT, last 7 days): 153 open, 3 calls in ITERATION mode, written to a CSV.
- **"Open" is your filter, not a scope.** `form-type=competition` keeps calls for competition (award notices drop out) and `deadline-receipt-request>=today()` drops closed ones; `scope: "ACTIVE"` returned the same 11 notices as the default `ALL`. `today()` compares dates only, so the blocks also drop deadlines that passed earlier today.
- **Fields are multilingual dicts.** `notice-title` has 24 languages (`{"eng": "Germany - IT services: ... - Rahmenvertrag ..."}` with en dashes as separators: English country and CPV label, then the title as the buyer wrote it); `buyer-name` comes only in the buyer's language (`{"deu": ["Landesbetrieb Information und Technik NRW"]}`). Deadlines, countries and CPV codes are lists, one entry per lot or buyer.
- **Rate limit: none published.** The API docs and the OpenAPI file (https://api.ted.europa.eu/api-v3.yaml) state paging limits only: 250 notices per page, 10,000 fields per page, 15,000 notices per query in page mode, none in ITERATION mode; no 429 or rate wording (block 2), and no rate-limit headers in answers (block 4). The blocks stay serial, wait 1 s after each call, wait once on 429/5xx (`Retry-After`, else 30 s) and stop above 120 s.

## What works

### 1. Keyword, CPV code or buyer country + a "published since" date -> open notices with title, buyer, country, deadline and link (browser)

`on_api_tab()` opens the API's own Swagger UI page (https://api.ted.europa.eu/swagger-ui/index.html), so `fetch()` is same-origin: the API's CORS header allows only `https://ted.europa.eu`, and ted.europa.eu pages sit behind a WAF challenge. `search()` returns parsed JSON on HTTP 200, raises with the API's reason on HTTP 400, waits once on 429/5xx and otherwise stops. 5 POSTs: one per search plus page 2 of the second.

```python
import email.utils, json, re, time
from datetime import datetime, timezone

SEARCHES = [  # (keyword or None, CPV code or None, buyer country ISO 3166-1 alpha-3 or None, published since, how many to show)
    ("cloud computing", None, None, "2026-11-01", 5),
    (None, "72000000", "DEU", "2026-11-15", 6),       # CPV 72000000 = IT services (covers every 72xxxxxx code)
    ("electric buses", None, None, "2026-10-01", 4),
    (None, "55524000", "FRA", "2026-11-01", 5),       # school catering in France
]
LANG = "eng"  # preferred language for titles; falls back to the notice's own language

API = "https://api.ted.europa.eu"
SEARCH = API + "/v3/notices/search"
FIELDS = ["publication-number", "notice-title", "buyer-name", "buyer-country", "deadline-receipt-request",
          "publication-date", "procedure-type"]
PAUSE = 1.0  # no rate limit is published; stay serial and gentle

def on_api_tab():
    """fetch() from the API's own Swagger page: same origin, no CORS question, no WAF challenge (unlike ted.europa.eu)."""
    try:
        if js("location.origin") == API:
            return
    except Exception:
        pass
    new_tab(API + "/swagger-ui/index.html")
    wait_for_load()
    if js("location.origin") != API:
        raise RuntimeError(f"expected an {API} page, got {js('location.href')}: stop")

# js() gives up after a few seconds, so start the POST, then poll for the answer.
START_JS = """(() => { window.__t = window.__t || {}; const id = String(Math.random()).slice(2); window.__t[id] = null;
  fetch(%s, {method: 'POST', credentials: 'omit', headers: {'Content-Type': 'application/json'}, body: %s})
    .then(async r => { window.__t[id] = {status: r.status, type: r.headers.get('content-type') || '',
      retry: r.headers.get('retry-after'), text: await r.text()}; })
    .catch(e => { window.__t[id] = {status: 0, type: '', retry: null, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__t[%s]; if (v) delete window.__t[%s]; return v; })()"""

def post(body):
    rid = json.dumps(js(START_JS % (json.dumps(SEARCH), json.dumps(json.dumps(body)))))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError("no answer after 60 s")
        time.sleep(0.2)
    time.sleep(PAUSE)
    return r

def retry_wait(value, default):
    v = (value or "").strip()
    if v.isdigit():
        return int(v)
    try:
        return max(0, int((email.utils.parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()) + 1)
    except (TypeError, ValueError):
        return default

def search(query, limit, page=1):
    """POST one expert query -> parsed JSON. Waits once on 429/5xx/network error (Retry-After, else 30 s; over
    120 s stops). A 400 carries the API's reason (unknown field, bad value, syntax error): raised as is."""
    body = {"query": query, "fields": FIELDS, "limit": limit, "page": page}
    for attempt in range(2):
        r = post(body)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            wait = retry_wait(r["retry"], 30)
            if wait > 120:
                raise RuntimeError(f"server asks to wait {wait} s: stopping")
            time.sleep(wait)
            continue
        break
    if r["status"] == 400:
        raise ValueError(f"query refused: {json.loads(r['text']).get('message')}")
    if r["status"] != 200 or "json" not in r["type"]:
        raise RuntimeError(f"HTTP {r['status']} {r['type']} {' '.join(r['text'].split())[:200]!r}: stopping")
    d = json.loads(r["text"])
    if d.get("timedOut"):
        raise RuntimeError("the search timed out on the server (timedOut true): narrow the query")
    return d

def build(keyword, cpv, country, since):
    """Open calls for competition only: form-type=competition and a deadline today or later (date-level test)."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", since):
        raise ValueError(f"since must be YYYY-MM-DD, got {since!r}")
    parts = []
    if keyword:
        parts.append('FT~"%s"' % keyword.replace('"', ""))      # full text, every language version
    if cpv:
        if not re.fullmatch(r"\d{8}", cpv):
            raise ValueError(f"CPV codes have 8 digits (no check digit), got {cpv!r}")
        parts.append(f"classification-cpv={cpv}")               # matches the code and every code below it
    if country:
        if not re.fullmatch(r"[A-Z]{3}", country):
            raise ValueError(f"buyer-country takes ISO 3166-1 alpha-3 (DEU, FRA), got {country!r}")
        parts.append(f"buyer-country={country}")
    parts += [f"publication-date>={since.replace('-', '')}", "form-type=competition", "deadline-receipt-request>=today()"]
    return " AND ".join(parts) + " SORT BY deadline-receipt-request"   # soonest deadline first

def text(v, lang=LANG):
    """Multilingual values: {'eng': 'x'} or {'deu': ['x']} -> one string in `lang`, else the first language given."""
    if not v:
        return ""
    if isinstance(v, dict):
        v = v.get(lang) or next(iter(v.values()))
    if isinstance(v, list):
        v = " / ".join(dict.fromkeys(v))
    return " ".join(str(v).split())

def deadlines(n, now):
    """deadline-receipt-request is one ISO datetime per lot, repeated when lots share it -> (soonest still in the
    future, number of lots)."""
    raw = n.get("deadline-receipt-request") or []
    future = sorted(d for d in {datetime.fromisoformat(x) for x in raw} if d > now)
    return (future[0] if future else None), len(raw)

on_api_tab()
now = datetime.now(timezone.utc)
print(f"TED (Tenders Electronic Daily) Search API, checked {now:%Y-%m-%d %H:%M} UTC")
for keyword, cpv, country, since, show in SEARCHES:
    q = build(keyword, cpv, country, since)
    d = search(q, limit=show)
    label = " + ".join(x for x in (f'"{keyword}"' if keyword else "", f"CPV {cpv}" if cpv else "", country or "") if x)
    print(f"\n{label}, published since {since}: {d['totalNoticeCount']} open notices (deadline date today or later)")
    print(f"  query: {q}")
    for n in d["notices"]:
        due, lots = deadlines(n, now)
        # English notice-title: "<Country> - <CPV label> - <title as written>", joined by en dashes (U+2013)
        parts = text(n.get("notice-title")).split(" \u2013 ", 2)
        title, what = (parts[2], parts[1]) if len(parts) == 3 else (parts[-1], "")
        link = (n.get("links", {}).get("html", {}) or {}).get(LANG[:3].upper()) or f"https://ted.europa.eu/en/notice/-/detail/{n['publication-number']}"
        print(f"  {n['publication-number']}  published {n['publication-date'][:10]}  "
              f"deadline {due.strftime('%Y-%m-%d %H:%M %z') if due else 'PASSED earlier today'}"
              + (f" ({lots} lots)" if lots > 1 else "") + f"  {n.get('procedure-type', '')}")
        print(f"    {title[:100]}" + (f"  [{what[:50]}]" if what else ""))
        print(f"    buyer: {text(n.get('buyer-name'))[:70]} ({', '.join(dict.fromkeys(n.get('buyer-country') or []))})")
        print(f"    {link}")

# page 2 of the busiest search, same order
q = build(None, "72000000", "DEU", "2026-11-15")
p2 = search(q, limit=6, page=2)
print(f"\npage 2 of CPV 72000000 + DEU (limit 6): {[n['publication-number'] for n in p2['notices']]}")
print(f"\nSource: TED (Tenders Electronic Daily), Publications Office of the European Union, Search API, accessed {now:%d %B %Y %H:%M} UTC.")
```

Output (from the third run on 2026-11-21, 23:39 UTC; the runs at 23:30 and 23:36 gave the same notices, apart from one tie on page 2):

```text
TED (Tenders Electronic Daily) Search API, checked 2026-11-21 23:39 UTC

"cloud computing", published since 2026-11-01: 4 open notices (deadline date today or later)
  query: FT~"cloud computing" AND publication-date>=20261101 AND form-type=competition AND deadline-receipt-request>=today() SORT BY deadline-receipt-request
  777211-2026  published 2026-11-09  deadline 2026-11-23 23:59 +0100  open
    Contrato de Servicios para la dotación de una Plataforma Tecnológica multientidad para la gestión ad  [Software maintenance and repair services]
    buyer: Junta de Gobierno de la Diputación Provincial de Huelva (ESP)
    https://ted.europa.eu/en/notice/-/detail/777211-2026
  790764-2026  published 2026-11-13  deadline 2026-12-07 11:00 +0100 (2 lots)  neg-w-call
    Entwicklung, Bereitstellung und Betrieb eines Workflow?Fachdienstes, sowie der Aufbau und Betrieb ei  [Computer-related services]
    buyer: gematik GmbH (DEU)
    https://ted.europa.eu/en/notice/-/detail/790764-2026
  789259-2026  published 2026-11-12  deadline 2026-12-11 12:00 +0100  open
    Rahmenvertrag "Unterstützungs-/Dienstleistungen im Bereich IT-Betriebs-Compliance"  [IT services: consulting, software development, Int]
    buyer: Landesbetrieb Information und Technik NRW (DEU)
    https://ted.europa.eu/en/notice/-/detail/789259-2026
  810212-2026  published 2026-11-20  deadline 2026-12-21 10:00 +0100  neg-w-call
    Beschaffung und Implementierung einer ERP-Suite  [Enterprise resource planning software package]
    buyer: Klinikum Lippe GmbH (DEU)
    https://ted.europa.eu/en/notice/-/detail/810212-2026

CPV 72000000 + DEU, published since 2026-11-15: 93 open notices (deadline date today or later)
  query: classification-cpv=72000000 AND buyer-country=DEU AND publication-date>=20261115 AND form-type=competition AND deadline-receipt-request>=today() SORT BY deadline-receipt-request
  808918-2026  published 2026-11-20  deadline 2026-11-23 10:00 +0100  neg-w-call
    Implementierung SAP S/4 HANA-Systems für die CFM  [Software supply services]
    buyer: Charité - Universitätsmedizin Berlin (DEU)
    https://ted.europa.eu/en/notice/-/detail/808918-2026
  794257-2026  published 2026-11-16  deadline 2026-11-23 12:00 +0100  open
    Verlängerung Pflege und Support von Oracle-Lizenzen des Staatsbetriebes Sächsische Informatik Dienst  [Software maintenance and repair services]
    buyer: Staatsbetrieb Sächsische Informatik Dienste (DEU)
    https://ted.europa.eu/en/notice/-/detail/794257-2026
  807223-2026  published 2026-11-19  deadline 2026-11-24 00:00 +0100  open
    Spend Management Solution ("SMS") Purchase-to-Pay, Accounts Payable, Expenses, Corporate Cards and T  [Software supply services]
    buyer: EIT RawMaterials GmbH (DEU)
    https://ted.europa.eu/en/notice/-/detail/807223-2026
  799229-2026  published 2026-11-17  deadline 2026-11-24 09:30 +0100  open
    Beschaffung Dokumentenmanagementsystem für den Landkreis Harz  [Document management services]
    buyer: Landkreis Harz - Fachdienst Zentrale Vergabestelle (DEU)
    https://ted.europa.eu/en/notice/-/detail/799229-2026
  798323-2026  published 2026-11-17  deadline 2026-11-24 10:00 +0100  open
    Blockchainanalysetool (TRM)  [Software supply services]
    buyer: Zentrale Vergabestelle im Bayerischen Landesamt für Steuern (DEU)
    https://ted.europa.eu/en/notice/-/detail/798323-2026
  803392-2026  published 2026-11-18  deadline 2026-11-24 12:00 +0100 (3 lots)  open
    Beratungs- und Prüfleistungen des Kompetenzzentrums Barrierefreiheit  [IT services: consulting, software development, Int]
    buyer: Landesamt für Zentrale Polizeiliche Dienste Nordrhein-Westfalen (DEU)
    https://ted.europa.eu/en/notice/-/detail/803392-2026

"electric buses", published since 2026-10-01: 65 open notices (deadline date today or later)
  query: FT~"electric buses" AND publication-date>=20261001 AND form-type=competition AND deadline-receipt-request>=today() SORT BY deadline-receipt-request
  740868-2026  published 2026-10-26  deadline 2026-11-23 12:00 +0100  open
    Beschaffung von 12 Niederflursolobussen mit Elektroantrieb  [Electric buses]
    buyer: Reisen Service Omnibusverkehre GmbH (DEU)
    https://ted.europa.eu/en/notice/-/detail/740868-2026
  742573-2026  published 2026-10-27  deadline 2026-11-24 08:00 +0100  open
    Zakup zeroemisyjnego autobusu komunikacji zbiorowej w Bełchatowie  [Electric buses]
    buyer: Miasto Bełchatów reprezentowane przez Prezydenta Miasta Bełchatowa (POL)
    https://ted.europa.eu/en/notice/-/detail/742573-2026
  737134-2026  published 2026-10-23  deadline 2026-11-24 10:00 +0100  open
    Nákup 11 kloubových elektrobusů  [Electric buses]
    buyer: ČSAD Střední Čechy, a.s. (CZE)
    https://ted.europa.eu/en/notice/-/detail/737134-2026
  721607-2026  published 2026-10-19  deadline 2026-11-24 10:30 +0100  open
    Zakup fabrycznie nowego autobusu elektrycznego przystosowanego do nauki jazdy  [Electric buses]
    buyer: Miejskie Zakłady Autobusowe sp. z o.o. (POL)
    https://ted.europa.eu/en/notice/-/detail/721607-2026

CPV 55524000 + FRA, published since 2026-11-01: 0 open notices (deadline date today or later)
  query: classification-cpv=55524000 AND buyer-country=FRA AND publication-date>=20261101 AND form-type=competition AND deadline-receipt-request>=today() SORT BY deadline-receipt-request

page 2 of CPV 72000000 + DEU (limit 6): ['795470-2026', '803777-2026', '800869-2026', '809844-2026', '806207-2026', '808431-2026']

Source: TED (Tenders Electronic Daily), Publications Office of the European Union, Search API, accessed 21 November 2026 23:39 UTC.
```

### 2. robots.txt, the legal notice, the docs, the paging limits, what the API does with mistakes, and what a notice link does (browser)

8 page loads and 16 in-page `fetch()` calls. ted.europa.eu pages first answer with an AWS WAF challenge; a browser runs it and the page follows, so `page()` waits for text. Section 4 compares `deadline-receipt-request` with the two specific deadline fields on 100 open notices.

```python
import json, re, time

API = "https://api.ted.europa.eu"
SITE = "https://ted.europa.eu"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]

def page(url, wait_for=None, tries=40):
    """Page load. ted.europa.eu answers the first request with an AWS WAF challenge (HTTP 202, empty body);
    the browser runs it and the real page follows, so wait for `wait_for` in the text."""
    goto_url(url)
    wait_for_load()
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    txt = ""
    for _ in range(tries):
        txt = js("document.body ? document.body.innerText : (document.documentElement.textContent || '')") or ""
        if (wait_for and wait_for in txt) or (not wait_for and txt.strip()):
            break
        time.sleep(0.5)
    return st, txt

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

# 1) robots.txt: the API host has none (JSON 404); ted.europa.eu needs the browser (WAF challenge).
st, txt = page(API + "/robots.txt")
print(f"{API}/robots.txt HTTP {st}: {' '.join(txt.split())[:90]!r}")
st, txt = page(SITE + "/robots.txt", "User-Agent")
g = robots_groups(txt)
print(f"{SITE}/robots.txt HTTP {st}, {len(txt)} chars; "
      f"groups: {sorted(g)}; named AI-agent groups: {[a for a in AGENTS[1:] if a.lower() in g]}")
for path in ("/en/notice/-/detail/789259-2026", "/en/notice/789259-2026/pdf", "/en/notice/789259-2026/xml",
             "/en/legal-notice", "/en/search/result?FT=cloud"):
    rules = {a: g.get(a.lower(), g.get("*", [])) for a in AGENTS}
    ok = all(allowed(r, path) for r in rules.values())
    print(f"  {path:<34} {'allowed for all ' + str(len(AGENTS)) + ' agents' if ok else 'DISALLOWED'}")

# 2) Terms: the legal notice (reuse, licences, logos) and the API docs (no key).
st, txt = page(SITE + "/en/legal-notice", "Copyright notice")
t = " ".join(txt.split())
for needle in ("the procurement notices published in the Supplement to the Official Journal of the European Union can be freely reused, for commercial or non-commercial purposes",
               "Commission Decision of 12 December 2011 on the reuse of Commission documents",
               "is licensed under the Creative Commons Attribution 4.0 International (CC BY 4.0) license",
               "The SIMAP system’s logos (including that of TED) may not be used without the prior consent of the Publications Office of the European Union",
               "patents, trademarks, registered designs, logos and names, are excluded from the Commission’s reuse policy",
               "metadata is dedicated to the public domain in accordance with the Creative Commons Universal Public Domain Dedication deed (CC0 1.0)"):
    print(f"legal-notice HTTP {st}: {'found' if needle in t else 'MISSING'}: {needle[:95]!r}")
links = js("[...document.querySelectorAll('a')].map(a => a.href).filter(h => /2011.833|32011D0833/i.test(h))")
print(f"legal-notice link to the 2011 reuse decision: {links[:1]}")
words = [w for w in ("artificial intelligence", "machine learning", "text and data mining", "scraping", "crawl", "robot", "non-commercial only")
         if w in t.lower()]
print(f"legal-notice mentions {words or 'none'} of: AI, machine learning, text and data mining, scraping, crawl, robot")

st, txt = page("https://docs.ted.europa.eu/api/latest/index.html", "Getting started")
t = " ".join(txt.split())
for needle in ("TED API allows anonymous access to all services manipulating published notices",
               "The Search API does not require a key."):
    print(f"docs HTTP {st}: {'found' if needle in t else 'MISSING'}: {needle!r}")
print(f"docs mention a request rate limit: {'yes' if re.search(r'rate.?limit|requests per', t, re.I) else 'no'}")

# 3) Back on the API host: its OpenAPI file states the paging limits; then what the API does with mistakes.
page(API + "/swagger-ui/index.html")
START_JS = """(() => { window.__t = window.__t || {}; const id = String(Math.random()).slice(2); window.__t[id] = null;
  fetch(%s, %s).then(async r => { window.__t[id] = {status: r.status, type: r.headers.get('content-type') || '',
      text: await r.text()}; }).catch(e => { window.__t[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__t[%s]; if (v) delete window.__t[%s]; return v; })()"""

def call(url, opts):
    rid = json.dumps(js(START_JS % (json.dumps(url), json.dumps(opts))))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{url}: no answer after 60 s")
        time.sleep(0.2)
    time.sleep(1.0)
    return r

def post(body):
    return call(API + "/v3/notices/search", {"method": "POST", "credentials": "omit",
                                             "headers": {"Content-Type": "application/json"}, "body": json.dumps(body)})

y = call(API + "/api-v3.yaml", {"credentials": "omit"})["text"]
for needle in ("Maximum number of retrievable notices: 15k.", "Maximum number of notices per page: 250.",
               "Maximum number of fields per page: 10k.", "There is no limit on the number of retrievable notices."):
    print(f"api-v3.yaml: {'found' if needle in y else 'MISSING'}: {needle!r}")
print(f"api-v3.yaml mentions 429 or a request rate: {'yes' if re.search(r'429|rate.?limit|requests per', y, re.I) else 'no'}")
print()

def brief(r):
    if "json" not in r["type"]:
        return f"HTTP {r['status']} {r['type'] or '-'} {' '.join(r['text'].split())[:80]!r}"
    d = json.loads(r["text"])
    if "notices" in d:
        return f"HTTP {r['status']} totalNoticeCount {d['totalNoticeCount']}, first {[n['publication-number'] for n in d['notices'][:3]]}"
    return f"HTTP {r['status']} {(d.get('error') or {}).get('type')}: {d.get('message', '')[:110]}"

# the list of returnable fields comes back in the 400 answer to an unknown one
msg = json.loads(post({"query": "publication-number=789259-2026", "fields": ["no-such-field"], "limit": 1})["text"])["message"]
ALL_FIELDS = re.search(r"supported values are: (.*)\)\s*$", msg).group(1).split(",")  # names can hold "(t)"
print(f"returnable fields listed in the 400 for an unknown field: {len(ALL_FIELDS)}, e.g. {sorted(f for f in ALL_FIELDS if f.startswith('deadline-receipt'))}")
F = ["publication-number"]
CLOUD = 'FT~"cloud computing" AND publication-date>=20261101'
for label, r in (
    ("GET instead of POST                  ", call(API + "/v3/notices/search?query=FT~cloud", {"credentials": "omit"})),
    ("keyword only, scope ALL (default)    ", post({"query": CLOUD, "fields": F, "limit": 3})),
    ("keyword only, scope ACTIVE           ", post({"query": CLOUD, "fields": F, "limit": 3, "scope": "ACTIVE"})),
    ("+ form-type=competition              ", post({"query": CLOUD + " AND form-type=competition", "fields": F, "limit": 3})),
    ("+ deadline-receipt-request>=today()  ", post({"query": CLOUD + " AND form-type=competition AND deadline-receipt-request>=today()", "fields": F, "limit": 3})),
    ("buyer-country=DE (alpha-2)           ", post({"query": "buyer-country=DE AND publication-date>=today(-3)", "fields": F, "limit": 1})),
    ("publication-date>=2026-11-01         ", post({"query": "publication-date>=2026-11-01", "fields": F, "limit": 1})),
    ("unknown query field                  ", post({"query": "deadline-date>=today()", "fields": F, "limit": 1})),
    ("unknown return field                 ", post({"query": CLOUD, "fields": ["deadline-date"], "limit": 1})),
    ("SORT BY ... ASC                      ", post({"query": CLOUD + " SORT BY publication-date ASC", "fields": F, "limit": 1})),
    ("limit 251                            ", post({"query": CLOUD, "fields": F, "limit": 251})),
    ("41 fields x limit 250                ", post({"query": "publication-date>=today(-1)", "fields": ALL_FIELDS[:41], "limit": 250})),
    ("page 61 x limit 250 (past 15,000)    ", post({"query": "publication-date>=20260101", "fields": F, "limit": 250, "page": 61})),
):
    print(f"{label} {brief(r)}")

# 4) What deadline-receipt-request holds: the tender deadline (open procedures) or the deadline for requests
#    to participate (restricted / negotiated ones). Compare with the two specific fields on 100 notices.
r = post({"query": "form-type=competition AND publication-date>=today(-2) AND deadline-receipt-request>=today()",
          "fields": ["publication-number", "procedure-type", "deadline-receipt-request", "deadline-receipt-tender-date-lot",
                     "deadline-receipt-tender-time-lot", "deadline-receipt-request-date-lot", "deadline-receipt-request-time-lot"],
          "limit": 100})

def lot_times(n, kind):
    """'2026-12-19+01:00' + '00:00:00+01:00' -> '2026-12-19T00:00:00+01:00', one per lot (date and time are two fields)."""
    return {f"{d[:10]}T{t}" for d, t in zip(n.get(f"deadline-receipt-{kind}-date-lot") or [], n.get(f"deadline-receipt-{kind}-time-lot") or [])}

tally = {}
for n in json.loads(r["text"])["notices"]:
    d = set(n.get("deadline-receipt-request") or [])   # every lot's full datetime must match
    src = ("tender date" if d and d <= lot_times(n, "tender") else
           "request-to-participate date" if d and d <= lot_times(n, "request") else "neither")
    tally.setdefault(n.get("procedure-type"), {}).setdefault(src, 0)
    tally[n.get("procedure-type")][src] += 1
print(f"\ndeadline-receipt-request equals, on 100 open notices published in the last 3 days: {json.dumps(tally)}")

# 5) Notice links are for people. In this browser both pages showed only the site frame as text (the /html link
#    sat on the WAF challenge page, HTTP 202, in one earlier try). The Search API fields above are the reliable source.
for url, want in ((SITE + "/en/notice/-/detail/789259-2026", "789259-2026 - Competition"),
                  (SITE + "/en/notice/789259-2026/html", "Deadline")):
    st, txt = page(url, want, 40)
    print(f"{url} HTTP {st}, {len(txt.strip()):,} chars of text, {want!r} {'shown' if want in txt else 'NOT shown after 20 s'}")
page(API + "/swagger-ui/index.html")  # back to the API page
```

Output (from the third run on 2026-11-21, 23:40 UTC):

```text
https://api.ted.europa.eu/robots.txt HTTP 404: 'Whitelabel Error Page This application has no configured error view, so you are seeing thi'
https://ted.europa.eu/robots.txt HTTP 202, 1311 chars; groups: ['*', 'msnbot/bingbot', 'petalbot', 'sogou web spider']; named AI-agent groups: []
  /en/notice/-/detail/789259-2026    allowed for all 11 agents
  /en/notice/789259-2026/pdf         allowed for all 11 agents
  /en/notice/789259-2026/xml         allowed for all 11 agents
  /en/legal-notice                   allowed for all 11 agents
  /en/search/result?FT=cloud         DISALLOWED
legal-notice HTTP 200: found: 'the procurement notices published in the Supplement to the Official Journal of the European Uni'
legal-notice HTTP 200: found: 'Commission Decision of 12 December 2011 on the reuse of Commission documents'
legal-notice HTTP 200: found: 'is licensed under the Creative Commons Attribution 4.0 International (CC BY 4.0) license'
legal-notice HTTP 200: found: 'The SIMAP system’s logos (including that of TED) may not be used without the prior consent of t'
legal-notice HTTP 200: found: 'patents, trademarks, registered designs, logos and names, are excluded from the Commission’s re'
legal-notice HTTP 200: found: 'metadata is dedicated to the public domain in accordance with the Creative Commons Universal Pu'
legal-notice link to the 2011 reuse decision: ['https://eur-lex.europa.eu/eli/dec/2011/833/oj']
legal-notice mentions none of: AI, machine learning, text and data mining, scraping, crawl, robot
docs HTTP 200: found: 'TED API allows anonymous access to all services manipulating published notices'
docs HTTP 200: found: 'The Search API does not require a key.'
docs mention a request rate limit: no
api-v3.yaml: found: 'Maximum number of retrievable notices: 15k.'
api-v3.yaml: found: 'Maximum number of notices per page: 250.'
api-v3.yaml: found: 'Maximum number of fields per page: 10k.'
api-v3.yaml: found: 'There is no limit on the number of retrievable notices.'
api-v3.yaml mentions 429 or a request rate: no

returnable fields listed in the 400 for an unknown field: 1830, e.g. ['deadline-receipt-answers-date-lot', 'deadline-receipt-answers-time-lot', 'deadline-receipt-expressions-date-lot', 'deadline-receipt-expressions-time-lot', 'deadline-receipt-request', 'deadline-receipt-request-date-lot', 'deadline-receipt-request-time-lot', 'deadline-receipt-tender-date-lot', 'deadline-receipt-tender-time-lot']
GET instead of POST                   HTTP 405 None: Request method 'GET' is not supported
keyword only, scope ALL (default)     HTTP 200 totalNoticeCount 11, first ['756633-2026', '777211-2026', '779559-2026']
keyword only, scope ACTIVE            HTTP 200 totalNoticeCount 11, first ['756633-2026', '777211-2026', '779559-2026']
+ form-type=competition               HTTP 200 totalNoticeCount 4, first ['777211-2026', '789259-2026', '790764-2026']
+ deadline-receipt-request>=today()   HTTP 200 totalNoticeCount 4, first ['777211-2026', '789259-2026', '790764-2026']
buyer-country=DE (alpha-2)            HTTP 400 QUERY_UNSUPPORTED_FIELD_VALUE: Value 'DE' is not supported for search field 'buyer-country' in expert search
publication-date>=2026-11-01          HTTP 400 QUERY_INVALID_FIELD_FORMAT: Value for search field 'publication-date' in expert search does not follow pattern '20[0-9]{2}(0[1-9]|1[0-2])(
unknown query field                   HTTP 400 QUERY_UNKNOWN_FIELD: Unknown search field 'deadline-date' found in expert query
unknown return field                  HTTP 400 UNSUPPORTED_VALUE: Parameter 'fields' contains unsupported value (supported values are: sme-part,touchpoint-gateway-ted-esen,subm
SORT BY ... ASC                       HTTP 400 QUERY_SYNTAX_ERROR: Syntax error in expert query at line 1, col 77: extraneous input 'ASC' expecting <EOF>
limit 251                             HTTP 400 SEARCH_EXCEEDS_MAX_LIMIT: Value (251) of parameter 'limit' exceeds maximum allowed value (250)
41 fields x limit 250                 HTTP 400 SEARCH_FIELDS_PER_PAGE_EXCEEDS_MAX_LIMIT: Value (10750) of parameter 'Fields per page' exceeds maximum allowed value (10000)
page 61 x limit 250 (past 15,000)     HTTP 400 SEARCH_WINDOW_TOO_WIDE: Value (15250) of parameter 'Window size (page x limit)' exceeds maximum allowed value (15000)

deadline-receipt-request equals, on 100 open notices published in the last 3 days: {"neg-w-call": {"request-to-participate date": 6}, "open": {"tender date": 92}, "oth-single": {"tender date": 1}, "restricted": {"request-to-participate date": 1}}
https://ted.europa.eu/en/notice/-/detail/789259-2026 HTTP 200, 902 chars of text, '789259-2026 - Competition' shown
https://ted.europa.eu/en/notice/789259-2026/html HTTP 200, 1,548 chars of text, 'Deadline' NOT shown after 20 s
```

### 3. A watch list with Python urllib: robots check for every agent, every open notice in ITERATION mode, CSV, next deadlines in UTC (no browser)

ITERATION mode pages with an `iterationNextToken` over a frozen snapshot (OpenAPI: "the user cannot miss notices or have duplicated notices"); the list ends with an empty page, so 153 notices took 3 calls of up to 100. Deadlines keep the buyer's offset in `deadline` and are converted for `deadline_utc`.

```python
import collections, csv, email.utils, json, sys, time, urllib.error, urllib.request, urllib.robotparser
from datetime import datetime, timezone

CPV = ["72000000", "48000000"]   # IT services, software packages (each covers every code below it)
COUNTRIES = ["DEU", "AUT"]       # buyer country, ISO 3166-1 alpha-3
DAYS = 7                         # published in the last 7 days
OUT = "ted-open-tenders.csv"  # written to the current directory

UA = "ted-tenders-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
API = "https://api.ted.europa.eu"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]
FIELDS = ["publication-number", "notice-title", "buyer-name", "buyer-country", "deadline-receipt-request",
          "publication-date", "procedure-type", "classification-cpv"]
PAUSE = 1.0  # no rate limit is published; serial, 1 s apart
calls = collections.Counter()

def retry_wait(value, default):
    v = (value or "").strip()
    if v.isdigit():
        return int(v)
    try:
        return max(0, int((email.utils.parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()) + 1)
    except (TypeError, ValueError):
        return default

def http(url, body=None):
    """GET, or POST JSON when `body` is given -> (status, headers, bytes). 4xx other than 429 is returned;
    waits once on 429/5xx or a network error (Retry-After, else 30 s; over 120 s exits)."""
    data = json.dumps(body).encode() if body is not None else None
    hdr = {"User-Agent": UA, **({"Content-Type": "application/json"} if data else {})}
    for attempt in range(2):
        time.sleep(PAUSE)
        calls["POST" if data else "GET"] += 1
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=hdr), timeout=60) as r:
                return r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                wait = retry_wait(e.headers.get("Retry-After"), 30)
                if wait > 120:
                    sys.exit(f"{url}: server asks to wait {wait} s: stopping")
                time.sleep(wait)
                continue
            return e.code, e.headers, e.read()
        except OSError as e:
            if attempt == 0:
                time.sleep(30)
                continue
            sys.exit(f"{url}: {e}")

def text(v, lang="eng"):
    if not v:
        return ""
    if isinstance(v, dict):
        v = v.get(lang) or next(iter(v.values()))
    if isinstance(v, list):
        v = " / ".join(dict.fromkeys(v))
    return " ".join(str(v).split())

# 1) robots.txt. The API host has none (HTTP 404): everything allowed. ted.europa.eu answers plain HTTP with
#    an AWS WAF challenge (HTTP 202, empty body), so its robots.txt is read in a browser (block 2).
st, h, body = http(API + "/robots.txt")
rp = urllib.robotparser.RobotFileParser()
rp.parse(body.decode(errors="replace").splitlines() if st == 200 else [])  # 4xx: no rules (RFC 9309 2.3.1.3)
ok = all(rp.can_fetch(a, API + "/v3/notices/search") for a in AGENTS)
print(f"robots {API}: HTTP {st}: /v3/notices/search {'allowed' if ok else 'DISALLOWED'} for all {len(AGENTS)} agents")
if not ok:
    sys.exit("robots.txt now disallows the search endpoint: stop")
st, h, body = http("https://ted.europa.eu/robots.txt")
print(f"robots https://ted.europa.eu: HTTP {st}, {len(body)} bytes, x-amzn-waf-action: {h.get('x-amzn-waf-action')} "
      f"(not readable without a browser)")

# 2) Every open notice for the watch list, all pages, in ITERATION mode (no 15,000 cap, consistent pages).
query = (f"classification-cpv IN ({' '.join(CPV)}) AND buyer-country IN ({' '.join(COUNTRIES)}) "
         f"AND publication-date>=today(-{DAYS}) AND form-type=competition AND deadline-receipt-request>=today() "
         f"SORT BY deadline-receipt-request")
now = datetime.now(timezone.utc)
rows, token, pages, total, size = [], None, 0, None, 0
while True:
    body = {"query": query, "fields": FIELDS, "limit": 100, "paginationMode": "ITERATION"}
    if token:
        body["iterationNextToken"] = token
    st, h, raw = http(API + "/v3/notices/search", body)
    if st != 200:
        sys.exit(f"HTTP {st}: {raw.decode(errors='replace')[:300]}")
    d = json.loads(raw)
    if d.get("timedOut"):
        sys.exit("the search timed out on the server (timedOut true): the list would be partial, narrow the query")
    pages, size = pages + 1, size + len(raw)
    total = d["totalNoticeCount"] if total is None else total
    if not d["notices"]:
        break
    for n in d["notices"]:
        per_lot = n.get("deadline-receipt-request") or []   # one per lot, repeated when lots share a deadline
        ds = sorted(datetime.fromisoformat(x) for x in set(per_lot))
        due = next((x for x in ds if x > now), None)
        if due is None:
            continue  # today's deadline already passed (the query compares dates only)
        parts = text(n.get("notice-title")).split(" \u2013 ", 2)
        rows.append({"publication_number": n["publication-number"],
                     "published": n["publication-date"][:10],
                     "deadline": due.isoformat(), "deadline_utc": due.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M"),
                     "lots": len(per_lot), "procedure": n.get("procedure-type", ""),
                     "country": " ".join(dict.fromkeys(n.get("buyer-country") or [])),
                     "buyer": text(n.get("buyer-name")),
                     "title": parts[-1], "title_en_prefix": " \u2013 ".join(parts[:-1]),
                     "cpv": " ".join(dict.fromkeys(n.get("classification-cpv") or [])),
                     "url": f"https://ted.europa.eu/en/notice/-/detail/{n['publication-number']}"})
    token = d.get("iterationNextToken")
    if not token:
        break

seen = {r["publication_number"] for r in rows}
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["publication_number", "published", "deadline", "deadline_utc", "lots", "procedure",
                                      "country", "buyer", "title", "title_en_prefix", "cpv", "url"])  # also when empty
    w.writeheader()
    w.writerows(rows)
print(f"\nwatch list CPV {'+'.join(CPV)}, buyers in {'+'.join(COUNTRIES)}, published since today({-DAYS}), "
      f"checked {now:%Y-%m-%d %H:%M} UTC")
print(f"  totalNoticeCount {total}; {pages} pages of up to 100 ({size / 1e6:.1f} MB); {len(rows)} still open "
      f"({len(seen)} distinct); written to {OUT}")
print(f"  by buyer country: {dict(collections.Counter(r['country'] for r in rows).most_common())}")
print(f"  by procedure: {dict(collections.Counter(r['procedure'] for r in rows).most_common())}")
print("  next 5 deadlines (UTC):")
for r in sorted(rows, key=lambda r: r["deadline_utc"])[:5]:
    print(f"    {r['deadline_utc']}  {r['publication_number']:<12} {r['country']}  {r['buyer'][:38]:<38}  {r['title'][:50]}")
print(f"calls: {dict(calls)}")
print("Source: TED (Tenders Electronic Daily), Publications Office of the European Union, Search API.")
```

Output (from the second run on 2026-11-21, 23:41 UTC):

```text
robots https://api.ted.europa.eu: HTTP 404: /v3/notices/search allowed for all 11 agents
robots https://ted.europa.eu: HTTP 202, 0 bytes, x-amzn-waf-action: challenge (not readable without a browser)

watch list CPV 72000000+48000000, buyers in DEU+AUT, published since today(-7), checked 2026-11-21 23:41 UTC
  totalNoticeCount 153; 3 pages of up to 100 (1.2 MB); 153 still open (153 distinct); written to ted-open-tenders.csv
  by buyer country: {'DEU': 139, 'AUT': 13, 'DNK GBR DEU POL': 1}
  by procedure: {'open': 102, 'neg-w-call': 45, 'restricted': 6}
  next 5 deadlines (UTC):
    2026-11-23 09:00  808918-2026  DEU  Charité - Universitätsmedizin Berlin    Implementierung SAP S/4 HANA-Systems für die CFM
    2026-11-23 11:00  794257-2026  DEU  Staatsbetrieb Sächsische Informatik Di  Verlängerung Pflege und Support von Oracle-Lizenze
    2026-11-23 11:00  803732-2026  DEU  Deutsche Bundesbank                     Beschaffung und Integration eines Statistiktools f
    2026-11-23 23:00  807223-2026  DEU  EIT RawMaterials GmbH                   Spend Management Solution ("SMS") Purchase-to-Pay,
    2026-11-24 08:30  799229-2026  DEU  Landkreis Harz - Fachdienst Zentrale V  Beschaffung Dokumentenmanagementsystem für den Lan
calls: {'GET': 2, 'POST': 3}
Source: TED (Tenders Electronic Daily), Publications Office of the European Union, Search API.
```

The CSV columns: `publication_number, published, deadline, deadline_utc, lots, procedure, country, buyer, title, title_en_prefix, cpv, url`.

### 4. curl, headers and mistakes

```bash
S=https://api.ted.europa.eu/v3/notices/search
UA='ted-tenders-skill-example/1.0 (+https://github.com/browser-use/browser-harness)'
# open calls for competition: keyword + buyer country, published since a date, soonest deadline first
curl -sS --fail -A "$UA" -X POST "$S" -H 'Content-Type: application/json' -d '{
  "query": "FT~\"cybersecurity\" AND buyer-country IN (NLD BEL) AND publication-date>=20261101 AND form-type=competition AND deadline-receipt-request>=today() SORT BY deadline-receipt-request",
  "fields": ["publication-number", "notice-title", "buyer-name", "buyer-country", "deadline-receipt-request"],
  "limit": 3}' \
  | python3 -c 'import sys, json, datetime as dt
d = json.load(sys.stdin)
print("open notices (deadline date today or later)", d["totalNoticeCount"])
for n in d["notices"]:
    t = n["notice-title"].get("eng") or next(iter(n["notice-title"].values()))
    b = next(iter(n["buyer-name"].values()))[0]
    print(n["publication-number"], "|", min(n["deadline-receipt-request"], key=dt.datetime.fromisoformat), "|", ",".join(sorted(set(n["buyer-country"]))), "|", b, "|", t.split(" \u2013 ", 2)[-1][:70])
    print("   ", n["links"]["html"]["ENG"])'
sleep 1
# only the count: limit 1 (the OpenAPI file allows 0, the server answers 0 with HTTP 400)
curl -sS --fail -A "$UA" -X POST "$S" -H 'Content-Type: application/json' \
  -d '{"query": "classification-cpv=33000000 AND publication-date>=today(-7) AND form-type=competition AND deadline-receipt-request>=today()", "fields": ["publication-number"], "limit": 1}' \
  | python3 -c 'import sys, json; d = json.load(sys.stdin); print("medical equipment (CPV 33000000), deadline date today or later, published in the last 7 days:", d["totalNoticeCount"])'
sleep 1
# checkQuerySyntax: validate a query without running it
curl -sS -A "$UA" -X POST "$S" -H 'Content-Type: application/json' -w ' <- HTTP %{http_code}\n' \
  -d '{"query": "FT~\"cybersecurity\" AND buyer-country=NLD", "fields": ["publication-number"], "checkQuerySyntax": true}'
sleep 1
# response headers: JSON, no cache, no rate-limit headers; CORS only for the ted.europa.eu origin
curl -sS -A "$UA" -D - -o /dev/null -X POST "$S" -H 'Content-Type: application/json' -H 'Origin: https://ted.europa.eu' \
  -d '{"query": "publication-number=789259-2026", "fields": ["publication-number"], "limit": 1}' | tr -d '\r' \
  | grep -iE '^(HTTP/|(content-type|access-control-allow-origin|cache-control|retry-after|x-ratelimit-[a-z]+|ratelimit[a-z-]*|via):)'
sleep 1
# mistakes: limit 0, GET, a 2-letter country, a notice link on ted.europa.eu from plain HTTP (WAF challenge)
T=$(mktemp)
curl -sS -A "$UA" -o "$T" -w 'limit 0 -> HTTP %{http_code} ' -X POST "$S" -H 'Content-Type: application/json' \
  -d '{"query": "buyer-country=NLD", "fields": ["publication-number"], "limit": 0}'; cat "$T"; echo; sleep 1
curl -sS -A "$UA" -o "$T" -w 'GET -> HTTP %{http_code} ' "$S"; cat "$T"; echo; sleep 1
curl -sS -A "$UA" -o "$T" -w 'buyer-country=NL -> HTTP %{http_code} ' -X POST "$S" -H 'Content-Type: application/json' \
  -d '{"query": "buyer-country=NL", "fields": ["publication-number"], "limit": 1}'; cat "$T"; echo; sleep 1
curl -sS -A "$UA" -D "$T.h" -o "$T" -w 'notice xml link -> HTTP %{http_code} %{size_download} bytes, ' https://ted.europa.eu/en/notice/789259-2026/xml
grep -i '^x-amzn-waf-action' "$T.h" | tr -d '\r'
rm -f "$T" "$T.h"
```

Output (from the third run on 2026-11-21, 23:41 UTC):

```text
open notices (deadline date today or later) 4
778712-2026 | 2026-11-30T14:00:59+01:00 | AUT,BEL,DEU,DNK,ESP,EST,FIN,FRA,GRC,HUN,IRL,ITA,LUX,LVA,MLT,NLD,POL,PRT,ROU,SVK,SVN,SWE | European Commission, DG BUDG - Budget | Financial and accounting support
    https://ted.europa.eu/en/notice/-/detail/778712-2026
759639-2026 | 2026-12-07T16:00:59+01:00 | AUT,BEL,CZE,DEU,DNK,ESP,EST,FIN,FRA,GRC,HUN,IRL,ITA,LTU,LUX,LVA,MLT,NLD,POL,PRT,ROU,SVK,SVN,SWE | European Commission, PMO - Office for the Administration and Payment of Individual Entitlements | Assistance and Insurance Coverage for work-related travel
    https://ted.europa.eu/en/notice/-/detail/759639-2026
787043-2026 | 2026-12-11T11:00:15Z | NLD | Gemeente Rotterdam | Procesautomatisering Civiele Kunstwerken
    https://ted.europa.eu/en/notice/-/detail/787043-2026
medical equipment (CPV 33000000), deadline date today or later, published in the last 7 days: 963
{"notices":[],"totalNoticeCount":null,"iterationNextToken":null,"timedOut":false} <- HTTP 200
HTTP/2 200 
content-type: application/json
cache-control: no-cache, no-store, max-age=0, must-revalidate
via: 1.1 a0b427283378586768b4d5106d110a84.cloudfront.net (CloudFront), 1.1 07376b66dca155058b0aef79e9ec035a.cloudfront.net (CloudFront)
access-control-allow-origin: https://ted.europa.eu
limit 0 -> HTTP 400 {"message":"Value (0) of parameter 'limit' is below minimum allowed value (1)","error":{"type":"SEARCH_BELOW_MIN_LIMIT","limit":0,"minLimits":1}}
GET -> HTTP 405 {"message":"Request method 'GET' is not supported","error":null}
buyer-country=NL -> HTTP 400 {"message":"Value 'NL' is not supported for search field 'buyer-country' in expert search","error":{"type":"QUERY_UNSUPPORTED_FIELD_VALUE","location":{"beginColumn":14,"beginLine":1,"endColumn":16,"endLine":1},"fieldName":"buyer-country","fieldValue":"NL"}}
notice xml link -> HTTP 202 0 bytes, x-amzn-waf-action: challenge
```

## Fields

| Field | Value | Notes |
|---|---|---|
| `publication-number` | `789259-2026` | the notice id; https://ted.europa.eu/en/notice/-/detail/789259-2026 is the page for people |
| `notice-title` | `{"eng": "Germany - IT services: consulting, software development, Internet and support - Rahmenvertrag ...", "deu": ..., ...}` | 24 language keys (3-letter, lower case), parts joined by en dashes (U+2013); in the `eng` and `hun` versions checked, country and CPV label are translated and the last part is the buyer's own title |
| `title-proc` | `{"deu": "Rahmenvertrag ..."}` | the procedure title in the buyer's language only |
| `buyer-name` | `{"deu": ["Landesbetrieb Information und Technik NRW"]}` | buyer's language only; a list (several buyers in joint procurement) |
| `buyer-country` | `["DEU"]` | ISO 3166-1 alpha-3, one entry per buyer, repeated (800199-2026 listed `FIN` 21 times); two European Commission notices listed 22 and 24 countries |
| `deadline-receipt-request` | `["2026-12-11T12:00:00+01:00"]` | one ISO datetime per lot with the offset the buyer gave (`+01:00`, `+02:00`, `Z` seen). The tender deadline for `open` procedures, the deadline for requests to participate for `restricted` and `neg-w-call` (block 2, 100 open notices: `open` 92 of 92 and `oth-single` 1 of 1 matched the tender date, `neg-w-call` 6 of 6 and `restricted` 1 of 1 the request date) |
| `deadline-receipt-tender-date-lot`, `-time-lot` | `["2026-12-11+01:00"]`, `["12:00:00+01:00"]` | tender deadline split in two; absent on notices that only take requests to participate |
| `deadline-receipt-request-date-lot`, `-time-lot` | `["2026-12-07+01:00"]`, `["11:00:00+01:00"]` | deadline for requests to participate |
| `publication-date` | `2026-11-12+01:00` | date with an offset; query it as `publication-date>=20261112` or `>=today(-7)` |
| `procedure-type` | `open`, `restricted`, `neg-w-call`, `oth-single` | the values seen in block 2's 100 notices |
| `notice-type`, `form-type` | `cn-standard` / `competition`; `can-standard` (award) | only `form-type=competition` was used as a filter |
| `classification-cpv` | `["72000000", "72000000"]` | 8-digit CPV codes, repeated per lot; the query matches a code and every code below it |
| `links` | `{"xml": {"MUL": ...}, "pdf": {...24}, "pdfs": {...}, "html": {...24}, "htmlDirect": {...24}}` | always returned, asked for or not: about 4.4 KB per notice (100 notices with one field: 438,868 and 438,638 bytes in two checks) |
| `totalNoticeCount`, `iterationNextToken`, `timedOut` | | top level; `totalNoticeCount` is `null` with `checkQuerySyntax: true` |
| response headers | `Content-Type: application/json`, `Cache-Control: no-cache, no-store, max-age=0, must-revalidate`, `Access-Control-Allow-Origin: https://ted.europa.eu`, `Via: ... (CloudFront)` | no `Retry-After` or rate-limit headers seen |

The full list of returnable fields (1,830 on 2026-11-21) comes back in the HTTP 400 for an unknown field name (block 2) and in the OpenAPI file.

## Gotchas

- **POST with a JSON body.** `GET /v3/notices/search?query=...` is HTTP 405 `"Request method 'GET' is not supported"`.
- **Countries are alpha-3.** `buyer-country=DE` is HTTP 400 `QUERY_UNSUPPORTED_FIELD_VALUE`; use `DEU`, or `buyer-country IN (DEU AUT)`. Joint procurement lists every buyer's country, so `buyer-country=DEU` also matched a notice listed as `DNK GBR DEU POL`, and two European Commission notices found by a Netherlands/Belgium search listed 22 and 24 countries (block 4).
- **Dates are `YYYYMMDD` or `today(+-n)`.** `publication-date>=2026-11-01` is HTTP 400 `QUERY_INVALID_FIELD_FORMAT` with the pattern in the message.
- **`today()` is a date.** `deadline-receipt-request>=today()` keeps deadlines that passed earlier today; compare the full datetime in code (blocks 1 and 3). Several notices close at `23:59` or `00:00` local time; 807223-2026's `2026-11-24T00:00+01:00` is 2026-11-23 23:00 UTC.
- **Deadlines are per lot and per procedure kind.** Take the soonest future one and say how many lots there are. For `restricted` and `neg-w-call` procedures the date is the deadline for requests to participate, not for tenders (block 2). Some dynamic purchasing systems run for years: 793022-2026 (`dps-usage-lot` `dps-nlist`) has `2034-12-31T23:59:59+01:00`, so `SORT BY deadline-receipt-request DESC` on block 1's IT-services query or block 3's watch list starts there; wider queries start with placeholder dates such as `2099-12-31` or `2999-12-31`.
- **Titles are only partly English.** The `eng` title is "<Country> - <CPV label> - <buyer's own title>" joined by en dashes (U+2013), and the last part stays in the buyer's language. Source text can hold a `?` where a character was lost (790764-2026: `Workflow?Fachdienstes`, the same in `title-proc`).
- **Full text reaches the English CPV label.** `FT~"electric buses"` matched Polish and Czech notices whose `eng` title carries the CPV label "Electric buses" (block 1).
- **CPV codes are hierarchical.** `classification-cpv=72000000` matched 793275-2026, which lists only 72250000 and 48820000; `72*` gave the same 107 results while exploring.
- **Sorting.** `SORT BY <field>` is ascending and `SORT BY <field> DESC` descending; `SORT BY <field> ASC` is HTTP 400 `QUERY_SYNTAX_ERROR`. Ties are not stable across calls: page 2 of the same query ended with 803739-2026 at 23:36 and 808431-2026 at 23:39 UTC, both due at the same minute. Use ITERATION mode (block 3) for a complete list.
- **Paging limits.** `limit` 1-250 (0 is HTTP 400 `SEARCH_BELOW_MIN_LIMIT`, although the OpenAPI file says minimum 0; 251 is `SEARCH_EXCEEDS_MAX_LIMIT`); `page` x `limit` at most 15,000 (`SEARCH_WINDOW_TOO_WIDE`); fields x `limit` at most 10,000, counted with 2 more fields per notice than you ask for (41 fields x 250 was reported as 10,750: `SEARCH_FIELDS_PER_PAGE_EXCEEDS_MAX_LIMIT`).
- **`checkQuerySyntax: true`** validates without searching: HTTP 200 with `"notices": []` and `"totalNoticeCount": null`, or HTTP 400 with the error location.
- **Notice links are for people.** Plain HTTP to any ted.europa.eu URL (notice XML, PDF, page, robots.txt, legal notice) got HTTP 202, an empty body and `x-amzn-waf-action: challenge`. In the cloud browser the detail page loaded but showed only the site frame as text (902-1,151 characters with "789259-2026 - Competition"), and the `/html` link stayed on the challenge page once (HTTP 202, no text) and showed the same frame later. Ask the Search API for the fields you need instead.
- **Cross-origin `fetch()`.** The API answers with `Access-Control-Allow-Origin: https://ted.europa.eu` only; run in-page calls from an api.ted.europa.eu page (block 1 uses the Swagger UI page).
- **Counts move.** Notices carry Monday-Friday publication dates (2026-10-26 to 2026-11-20: 3,195-4,105 notices per weekday, 0 on Saturdays and Sundays) and the docs say they are published "no later than 09:00 CET on the publication date of the next OJ S"; date every count.
- **Tab marker.** The harness may set the tab title to a horse emoji; the blocks check `location.origin` and the page text, not the title.

## What does not work

- **GET requests** to the search endpoint: HTTP 405.
- **`scope: "ACTIVE"` as an "open tenders" filter**: it returned the same 11 notices (award notices included) as `ALL` for "cloud computing" since 2026-11-01.
- **Notice XML, PDF or HTML over plain HTTP**: HTTP 202 WAF challenge with an empty body.
- **ted.europa.eu search result URLs with parameters**: robots.txt disallows `/*/search/result?` for every agent; use the API.
- **Not tested:** the 429 response (never provoked), an expired or invalid `iterationNextToken`, the XML bulk download page (`/simap/xml-bulk-download`), the Visualisation and other keyed APIs, and notices with no `eng` title (the blocks fall back to the first language given).
