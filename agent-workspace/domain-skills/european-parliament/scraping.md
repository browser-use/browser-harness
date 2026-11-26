# European Parliament Open Data Portal - For a Plenary Sitting Date, List What Parliament Voted On (Vote Items, Tallies, Outcomes) and the Adopted Texts (TA-10-YYYY-NNNN) They Link To, Then Look Up Current MEPs by Country and Political Group (Open Data API v2, JSON-LD, no key)

Field-tested against the European Parliament Open Data Portal API v2 (data.europarl.europa.eu/api/v2) on 2026-11-25 (US Pacific afternoon; 23:38 UTC on 25 November to 00:07 UTC on 26 November, which was 00:38-01:07 on 26 November in Brussels and Strasbourg, CET = UTC+1) using a fresh Browser Use cloud browser `ka-european-par-1125` (logged out; one session, 23:44:53-00:05:22 UTC, confirmed `stopped` through the Browser Use API) plus Python `urllib` and `curl` from a Linux machine. 37 browser page loads (4 while reading the terms pages, 1 in block 1's first run, 8 in each of block 2's four runs) and 83 in-page `fetch()` calls (block 1: 4 in a first run that stopped on a bug, then 5 in each of six runs; block 2: 12, 12, 12 and 13), 71 curl calls (45 while exploring the API, its OpenAPI document and EUR-Lex's robots.txt; 13 in each of block 4's two runs) and 89 urllib calls (block 3's four runs of 6, 9, 9 and 9 commands: 15, 25, 25 and 24 calls), all serial and at least 2 s apart (the API host's robots.txt asks for `Crawl-delay: 2`), with 10 s after the one EUR-Lex page (`Crawl-delay: 10` there). Every call was HTTP 200 except the deliberate probes below: HTTP 204 with an empty body (votes of a day without a sitting, an unknown adopted text, a political-group or country filter written the wrong way, one page past the end) and HTTP 404 (`/meetings/MTG-PL-2026-11-21`, a Saturday, and three guessed paths for the OpenAPI document, which is served at `/api/v2/` itself). curl timed most answers at 0.44-3.0 s (one second page of `/vote-results` took 10.1 s); the 13 `/meps/show-current` calls with a `political-group` filter took 6.6-15.6 s, while the unfiltered list of all 720 current MEPs came back in 0.2-1.0 s. The batch's own check at 23:30 UTC timed `/meetings?year=2026&limit=50` at 36.9 s (645 KB); `limit=5` took 1.4 s here. No 429 in that session, no challenge, no key, no login, and no cookie needed (the load balancer sets `AWSALB` and `AWSALBCORS` cookies; the blocks do not send them back). Answers carry `cache-control: no-cache, no-store, max-age=0, must-revalidate` and no rate-limit header. An independent verifier re-ran all four blocks verbatim between 00:09 and 00:22 UTC on 26 November (fresh cloud browser `kv-european-par-1125`, then urllib and curl) and got the same outputs apart from times and timings; in its first block 2 run two in-page calls to `/adopted-texts/...` at about 00:11 UTC came back HTTP 429 with an empty body in 0.1 s (after 3 earlier calls to that end point in 10 minutes), and the same calls gave 200 and 204 a minute later. The outputs below are block 1's seventh run (00:04 UTC, sitting of 12 November), block 2's fourth (00:03 UTC), block 3's fourth (00:01-00:02 UTC) and block 4's second (00:02 UTC); earlier runs differ only in the fixes they led to (a crash on a list in a set, amendment ids in the report list, the 404 for a day without a sitting, the second data shape described under Gotchas) and in timings. Block 1 also ran on the sitting of 25 November (its sixth run, 23:58 UTC) and gave the same 23 vote items, 124 votes and 17 adopted texts as block 3's `votes 2026-11-25` below. Later on 2026-11-26 block 4 got a `trap ... EXIT` that removes its temporary directory even when the script stops early; that version re-ran from the same Linux machine at 01:01-01:04 UTC with the same output apart from the clock and timings. After review on 2026-11-26, blocks 1 and 3 print an `Item URLs` line after the credit, and block 4 pages vote items and adopted texts, takes the sitting's lowest TA number instead of a fixed one and uses block 3's fallbacks for same-day answers (no `activity_order`, no outcome, `mul` labels). Block 1 re-ran in a new cloud browser (01:23:48-01:24:06 UTC, stopped and confirmed `stopped`), blocks 3 and 4 from the Linux machine at 01:15-01:20 UTC; the outputs of blocks 1, 3 and 4 below are those re-runs.

robots.txt (checked 2026-11-25 23:49-00:04 UTC as pages in the cloud browser, by block 3 with `urllib.robotparser` and by block 4): https://data.europarl.europa.eu/robots.txt has three groups: `User-agent: *` with `Crawl-delay: 2` and `Allow: /`, and `facebookexternalhit` and `SemrushBot`, each with `Disallow: /api/`. It names none of GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot or Bytespider, so they fall under `*`, and every path this skill uses on the API host (`/api/v2/meetings/...`, `/api/v2/adopted-texts...`, `/api/v2/meps/...`, `/api/v2/corporate-bodies/{id}`, the Developers' corner page) is allowed for all of them. https://www.europarl.europa.eu/robots.txt has a group for `008` (only `/portal/`, `/news/`, `/ep-live/`) and a `*` group of 30 lines; the MEP lines are `Disallow: /meps/*/pdf*`, `/meps/*/xml*` and `/meps/*/eptvAjax`, so the profile pages this skill links to (`/meps/en/{id}`), the adopted-text pages (`/doceo/document/TA-...`) and the legal notice are allowed; it names no AI agent either. EUR-Lex's robots.txt (`*`, `Crawl-delay: 10`) does not disallow `/eli/`. Blocks 3 and 4 read robots.txt before any API call and stop if a path they use is ever disallowed. Terms: the Developers' corner page (https://data.europarl.europa.eu/en/developer-corner/opendata-api) says "Open Data API limits the number of requests to be made at the same end point for security reasons. Maximum number of requests 500 in 5min." and links "CC BY 4.0 - Attribution 4.0 International" and the "Rules on the European Parliament's Open Data" (Bureau Decision C/2025/341, http://data.europa.eu/eli/C/2025/341/oj), whose Article 4 says "The re-use of Parliament's open data is subject to the conditions laid down in the Creative Commons Attribution 4.0 International License (CC BY 4.0)" and that "Raw data, metadata or other documents of a comparable nature may alternatively be distributed by Parliament under the Creative Commons Universal Public Domain Dedication deed (CC0 1.0)". The legal notice (https://www.europarl.europa.eu/legal-notice/en/) says reuse of items marked "© European Union, [year(s)] – Source: European Parliament" "is authorised, for personal use or for further non-commercial or commercial dissemination, provided that the entire item is reproduced and the source is acknowledged", and "Any partial reproduction of data or multimedia items from this website must also cite the URL link of the complete item or the web page from which it was sourced". No scraping, crawling, robot, automated-access, machine-learning or text-and-data-mining wording on any of the three pages; the only "artificial intelligence" (in the Bureau Decision's recitals) is about enabling "new technologies to be used, most notably artificial intelligence", and the only "non-commercial" is the grant above (block 2 checks the quotes and scans for the words). Naming: the legal notice says "The European Parliament trademarks europarl®, europarltv®, myeuroparl®, Parlamentarium® and the European Parliament logo may not be used without the European Parliament's prior consent.", so this skill calls the source the "European Parliament Open Data Portal", uses the slug `european-parliament` (not the trademark), shows no logo, and is not affiliated with or endorsed by the European Parliament. Blocks 1, 3 and 4 print the credit line "(c) European Union, [year] - Source: European Parliament" with the portal and licence, block 1 says what it changed, and each block prints the API URLs of the items it shows (`Item URLs`), since the legal notice asks a partial reproduction to cite the URL of the complete item.

## Quick summary

- **No scraping needed.** Open JSON-LD API under `https://data.europarl.europa.eu/api/v2`, no key, no login; always add `format=application/ld+json` (without it the answer is RDF/XML). A sitting's id is built from its date: `MTG-PL-2026-11-12`. Per sitting: `GET /meetings/{id}` (exists? 404 = no sitting that day), `GET /meetings/{id}/vote-results?offset=0&limit=50` (vote items, one per report or resolution), `GET /meetings/{id}/decisions` (every single vote with tallies, in one 1.4-1.8 MB answer), `GET /adopted-texts?sitting-date=YYYY-MM-DD&language=en` (the TA-10-YYYY-NNNN texts dated that day, each with the report ids it `adopts`). Join vote item -> report id (`A-10-2026-0261`) -> adopted text. MEPs: `GET /meps/show-current?offset=0&limit=1000` (all 720, 162 KB, under 1 s) and filter on `api:country-of-representation` and `api:political-group` yourself; `GET /meps/{id}` + `GET /corporate-bodies/{org}?language=en` give a member's group and national party by full name.
- **Answers (checked 26 November 2026, 00:01-00:05 UTC).** Sitting of **Thursday 12 November 2026**: 14 vote items, 226 votes (122 by show of hands, 95 roll-call, 9 electronic), 13 adopted texts **TA-10-2026-0368 to TA-10-2026-0380**; 13 of the 14 items link to one, e.g. "Europe's Beating Cancer Plan" (A-10-2026-0261, 61 votes, the motion for a resolution as a whole ADOPTED +447 -66 =91) -> **TA-10-2026-0376**; "Union retail investor protection rules ***I" (A-9-2024-0162) has one vote, REJECTED +286 -300 =23, and no adopted text. Sitting of **Wednesday 25 November 2026** (same-day data): 23 vote items, 124 roll-call votes, 17 adopted texts **TA-10-2026-0389 to TA-10-2026-0405**; the 6 items without one were votes on "Décision d'engager des négociations interinstitutionnelles" (Global Europe, ESF, Horizon Europe, CEF, asylum and migration, AgoraEU, all 2028-2034). **720 current MEPs**: PPE 185, S&D 135, PfE 86, ECR 84, Renew 78, Verts/ALE 53, The Left 45, NI 27, ESN 27. **Malta: 6** (PPE: Peter AGIUS, David CASA, Roberta METSOLA; S&D: Alex AGIUS SALIBA, Daniel ATTARD, Thomas BAJADA). France, PfE: 29.
- **Two data shapes.** On the sitting day the vote data is thin: only roll-call votes, no `decision_outcome`, labels in one `mul` string (vote items "French - English - German", single votes in French). For the 12 November sitting, read 13 days later, every vote is there with English labels and ADOPTED / REJECTED / LAPSED. The blocks handle both and say "no outcome field yet" instead of guessing.
- **Rate limits:** "Maximum number of requests 500 in 5min." per end point (Developers' corner), and `Crawl-delay: 2` in robots.txt. No rate-limit headers. A brief HTTP 429 can still come well under that limit (see Gotchas). The blocks run serially, 2 s apart, 5 calls for a sitting and 1 for the MEP list.

## What works

### 1. Vote items, tallies and adopted texts for a sitting date, plus current MEPs for a country (browser)

`on_portal_tab()` opens the logged-out Developers' corner page of the Open Data Portal; it is on the API's own origin, so in-page `fetch()` needs no CORS header. The decisions answer is 1.4-1.8 MB, so each call boils its JSON down in the page (`pick`) before it reaches Python. 5 calls: the sitting, its vote items, its votes, the adopted texts dated that day (English only), all current MEPs. Edit `SITTING_DATE`, `COUNTRY` and `GROUP`.

```python
import json, re, time, urllib.parse
from collections import Counter
from datetime import datetime, timezone

SITTING_DATE = "2026-11-12"   # plenary sitting day, YYYY-MM-DD; the sitting id is MTG-PL-<date>
COUNTRY = "MT"                # ISO 3166-1 alpha-2 country the MEP represents (GR for Greece, as the API uses)
GROUP = None                  # None = every group; else the API's label (PPE, S&D, PfE, ECR, Renew, Verts/ALE, The Left, ESN, NI)
API = "https://data.europarl.europa.eu/api/v2"
PAGE = "https://data.europarl.europa.eu/en/developer-corner/opendata-api"
FMT = "format=application%2Fld%2Bjson"
PAUSE = 2.0                   # robots.txt asks for Crawl-delay: 2; the docs allow 500 requests in 5 min

def on_portal_tab():
    """fetch() from the logged-out Developers' corner page: the page and the API share an origin
    (data.europarl.europa.eu), so no CORS header is needed."""
    try:
        if js("location.href").startswith(PAGE):
            return
    except Exception:
        pass
    new_tab(PAGE)
    wait_for_load()
    if not js("location.href").startswith(PAGE):
        raise RuntimeError(f"Open Data Portal page did not load (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll. The answers can be large (the
# decisions of one sitting are 1.4 MB), so each call boils its JSON down in the page with `pick`.
START_JS = """(() => { window.__ep = window.__ep || {}; const id = String(Math.random()).slice(2); window.__ep[id] = null;
  const pick = %s;
  fetch(%s, {credentials: 'omit', cache: 'no-store'})
    .then(async r => { const t = await r.text(); let v = null, err = null;
      if (r.status === 200) { try { v = pick(JSON.parse(t)); } catch (e) { err = String(e) + ' ' + t.slice(0, 120); } }
      window.__ep[id] = {status: r.status, type: r.headers.get('content-type'), size: t.length, data: v, err: err || (r.status === 200 ? null : t.slice(0, 160))}; })
    .catch(e => { window.__ep[id] = {status: 0, size: 0, data: null, err: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__ep[%s]; if (v) delete window.__ep[%s]; return v; })()"""

calls, SOURCES = [], []
def src(url):
    """The API URL of an item, for the credit line (the legal notice asks partial reproductions to cite it):
    the URL without format, offset and limit."""
    u = urllib.parse.urlsplit(url)
    q = urllib.parse.urlencode([(k, v) for k, v in urllib.parse.parse_qsl(u.query) if k not in ("format", "offset", "limit")])
    return f"{u.scheme}://{u.netloc}{u.path}" + (f"?{q}" if q else "")

def call(path, pick, empty_ok=()):
    """GET API+path -> pick(json). HTTP 204 (no content) is how this API says "nothing for that id or
    filter" (/meetings/{id} says 404 for a day without a sitting): returns None for a status in empty_ok.
    429, 500, 502, 503 or 504: one retry after 30 s. Anything else stops."""
    url = API + path + ("&" if "?" in path else "?") + FMT
    if src(url) not in SOURCES:
        SOURCES.append(src(url))
    for attempt in range(2):
        rid = json.dumps(js(START_JS % (pick, json.dumps(url))))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > 120:
                raise RuntimeError(f"{url}: no answer after 120 s")
            time.sleep(0.3)
        calls.append((path.split("?")[0].split("/")[-1] if "MTG-PL" in path else path.split("?")[0].split("/")[1],
                      r["status"], round(time.time() - t0, 2), r["size"]))
        time.sleep(PAUSE)
        if attempt == 0 and r["status"] in (429, 500, 502, 503, 504):
            time.sleep(30)
            continue
        break
    if r["status"] in empty_ok:
        return None
    if r["status"] != 200 or r["err"]:
        raise RuntimeError(f"{url}: HTTP {r['status']} {r['err']!r}; stopping")
    return r["data"]

def paged(path, pick, limit=50):
    """offset/limit paging until a short page (or a 204 past the end)."""
    out, off = [], 0
    while True:
        page = call(f"{path}{'&' if '?' in path else '?'}offset={off}&limit={limit}", pick, empty_ok=(204,)) or []
        out += page
        if len(page) < limit:
            return out
        off += limit

def doc_ref(label):
    """'A10-0310/2026 - Rapporteur - § 3' -> 'A-10-2026-0310' (the id adopted texts give in `adopts`);
    'RC-B10-0508/2026 - ...' -> 'RC-10-2026-0508'."""
    m = re.match(r"(RC-)?([A-C])(\d+)-(\d{4})/(\d{4})\b", label)
    if not m:
        return None
    rc, series, term, num, year = m.groups()
    return f"{'RC' if rc else series}-{term}-{year}-{num}"

on_portal_tab()
sid = "MTG-PL-" + SITTING_DATE
print(f"European Parliament Open Data API v2, checked {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC; sitting {sid}")

sitting = call(f"/meetings/{sid}", "d => d.data.map(x => [x.activity_label.en, x.had_activity_type])", empty_ok=(204, 404))
if not sitting:
    print(f"{sid}: HTTP {calls[-1][1]}, no plenary sitting on {SITTING_DATE}")
else:
    print(f"{sitting[0][0]}: {sitting[0][1].split('/')[-1]}")
    # Two shapes: on the sitting day the data is thin (roll-call votes only, labels in one French-English-German
    # string); once the minutes are processed every vote is there, with English labels and an outcome.
    items = paged(f"/meetings/{sid}/vote-results",
                  "d => d.data.filter(x => (x.had_activity_type || '').endsWith('PLENARY_VOTE_RESULTS')).map(x => "
                  "[x.activity_id, (x.activity_label || {}).en || null, (x.activity_label || {}).mul || '', "
                  "(x.based_on_a_realization_of || []).map(s => s.split('/').pop())])")
    decs = call(f"/meetings/{sid}/decisions",       # every vote of the sitting in one answer; offset/limit are ignored
                "d => d.data.map(x => [(x.inverse_consists_of || [])[0], (x.activity_label || {}).en || "
                "(x.activity_label || {}).mul || (x.referenceText || {}).en || '', x.activity_start_date || '', "
                "parseFloat(x.activity_order || '0'), +x.notation_votingId, x.decision_method.split('/').pop(), "
                "(x.decision_outcome || '').split('/').pop(), x.number_of_votes_favor, x.number_of_votes_against, "
                "x.number_of_votes_abstention, (x.decided_on_a_realization_of || []).map(s => s.split('/').pop())])")
    texts = paged(f"/adopted-texts?sitting-date={SITTING_DATE}&language=en",
                  "d => d.data.map(w => [w.identifier, (w.adopts || []).map(s => s.split('/').pop()), "
                  "(w.title_dcterms || {}).en || '', (w.inverse_created_a_realization_of || []).map(p => p.split('/').pop())])")
    ta_for = {}
    for ta, adopts, title, procs in texts:
        for a in adopts:
            ta_for.setdefault(a, set()).add((ta, title, tuple(p for p in procs if re.fullmatch(r"\d{4}-\d{4}\w?", p))))
    by_item = {}
    for d in decs:
        by_item.setdefault(d[0].split("/")[-1], []).append(d)
    print(f"{len(items)} vote items, {len(decs)} votes ({dict(Counter(d[5] for d in decs))}), "
          f"{len(texts)} adopted texts dated {SITTING_DATE}\n")
    rows = []
    for aid, en, mul, based in items:
        votes = sorted(by_item.get(aid, []), key=lambda d: (d[3], d[2], d[4]))   # activity_order, time, voting id
        refs = sorted(r for r in set(based) | {r for d in votes for r in [doc_ref(d[1])] + d[10] if r}
                      if re.fullmatch(r"(A|B|C|RC)-\d+-\d{4}-\d{4}", r))   # drop amendment ids (...-AM-12)
        tas = sorted({t for r in refs for t in ta_for.get(r, ())})
        bits = mul.split(" - ")                         # sitting day: "French - English - German"
        title = en or (bits[1] if len(bits) == 3 else tas[0][1] if tas else mul)
        first = min((d[2] for d in votes if d[2]), default="")   # only roll-call votes carry a time
        rows.append((first or "~", min((d[4] for d in votes), default=0), aid, title, refs, tas, votes))
    for first, _, aid, title, refs, tas, votes in sorted(rows):
        last = votes[-1] if votes else None
        out = Counter(d[6] for d in votes if d[6])
        print(f"{first[11:16] if first != '~' else '--:--'} {title[:96]}")
        print(f"      item {aid.rsplit('-', 1)[-1]}, {', '.join(refs) or '-'}: {len(votes)} vote(s), "
              f"{sum(d[5] == 'VOTE_ELECTRONIC_ROLLCALL' for d in votes)} roll-call"
              + (f", {dict(out)}" if out else ", no outcome field yet"))
        if last:
            n = lambda v: "-" if v is None else v
            tally = f" +{n(last[7])} -{n(last[8])} ={n(last[9])}" if last[7] is not None else f" (no tally: {last[5]})"
            print(f"      last vote: {re.split(r' [-–] ', last[1])[-1][:50]!r}{' ' + last[6] if last[6] else ''}{tally}")
        for ta, ttl, procs in tas:
            print(f"      adopted text {ta} (procedure {', '.join(procs) or '-'}): "
                  f"https://www.europarl.europa.eu/doceo/document/{ta}_EN.html")
    linked = {t[0] for r in rows for t in r[5]}
    print(f"\n{sum(1 for r in rows if r[5])} of {len(rows)} vote items link to an adopted text; "
          f"adopted texts not reached from a vote item: {sorted({t[0] for t in texts} - linked) or 'none'}")

# MEPs: one call for all current MEPs (filtered calls took 7-15 s each), then filter here
meps = call("/meps/show-current?offset=0&limit=1000",
            "d => d.data.map(p => [p.identifier, p.label, p['api:country-of-representation'], p['api:political-group'], p.sortLabel])")
key = lambda s: re.sub(r"[^A-Z]", "", (s or "").upper())     # 'S&D' == 'S-D', 'Verts/ALE' == 'VERTS-ALE'
pick = [m for m in meps if m[2] == COUNTRY and (GROUP is None or key(m[3]) == key(GROUP))]
print(f"\n{len(meps)} current MEPs; {COUNTRY}{' / ' + GROUP if GROUP else ''}: {len(pick)} "
      f"({', '.join(f'{g} {n}' for g, n in Counter(m[3] for m in pick).most_common())})")
for mid, name, c, g, _ in sorted(pick, key=lambda m: (m[3], m[4] or "")):
    print(f"  {g:<9} {name:<26} id {mid:<7} https://www.europarl.europa.eu/meps/en/{mid}")
print("all groups:", ", ".join(f"{g} {n}" for g, n in Counter(m[3] for m in meps).most_common()))

by = {}
for p, s, t, z in calls:
    by.setdefault(p, []).append((s, t, z))
print(f"\n{len(calls)} API calls: " + ", ".join(f"{p} x{len(v)} HTTP {sorted({s for s, _, _ in v})} "
      f"{min(t for _, t, _ in v):.1f}-{max(t for _, t, _ in v):.1f}s {max(z for _, _, z in v) // 1000} KB" for p, v in by.items()))
print(f"(c) European Union, {SITTING_DATE[:4]} - Source: European Parliament (Open Data Portal, CC BY 4.0). "
      "Changed: vote items joined to adopted texts by report number, MEPs filtered by this script.")
print("Item URLs: " + " ".join(SOURCES))
```

Output (eighth run, 2026-11-26 01:24 UTC in a new cloud browser, after the `Item URLs` line was added; the seventh run at 00:04 UTC printed the same rows apart from call timings; sitting of 12 November; times are CET as the API gives them, `+01:00`). The sixth run, with `SITTING_DATE = "2026-11-25"`, listed the same 23 items and 17 adopted texts as block 3's `votes 2026-11-25` below, with "no outcome field yet" and French vote labels such as 'Proposition de résolution (ensemble du texte)':

```text
European Parliament Open Data API v2, checked 2026-11-26 01:23 UTC; sitting MTG-PL-2026-11-12
Thursday, 12 November 2026: PLENARY_SITTING
14 vote items, 226 votes ({'VOTE_HAND': 122, 'VOTE_ELECTRONIC_ROLLCALL': 95, 'VOTE_ELECTRONIC': 9}), 13 adopted texts dated 2026-11-12

11:18 Amendment of the Statute for Members of the European Parliament, as regards proxy voting
      item 993257, A-10-2026-0270: 13 vote(s), 1 roll-call, {'ADOPTED': 12, 'REJECTED': 1}
      last vote: 'Motion for a resolution (as a whole)' ADOPTED +578 -25 =4
      adopted text TA-10-2026-0370 (procedure 2026-2052): https://www.europarl.europa.eu/doceo/document/TA-10-2026-0370_EN.html
11:19 Union Civil Protection Mechanism and Union support for health emergency preparedness and respons
      item 993371, A-10-2026-0271: 61 vote(s), 18 roll-call, {'REJECTED': 31, 'ADOPTED': 27, 'LAPSED': 3}
      last vote: 'Request for referral back to committee' ADOPTED (no tally: VOTE_HAND)
      adopted text TA-10-2026-0371 (procedure 2025-0223): https://www.europarl.europa.eu/doceo/document/TA-10-2026-0371_EN.html
11:28 Modernisation of the key information document ***I
      item 993385, A-9-2024-0160: 2 vote(s), 1 roll-call, {'ADOPTED': 2}
      last vote: 'Joint statement by Parliament, the Council and the' ADOPTED (no tally: VOTE_HAND)
      adopted text TA-10-2026-0372 (procedure 2023-0166): https://www.europarl.europa.eu/doceo/document/TA-10-2026-0372_EN.html
11:28 Union retail investor protection rules ***I
      item 993381, A-9-2024-0162: 1 vote(s), 1 roll-call, {'REJECTED': 1}
      last vote: 'Am 2' REJECTED +286 -300 =23
11:29 European Chemicals Agency and amending regulations ***I
      item 993378, A-10-2026-0093: 6 vote(s), 2 roll-call, {'ADOPTED': 1, 'LAPSED': 5}
      last vote: 'Commission proposal' LAPSED (no tally: VOTE_ELECTRONIC_ROLLCALL)
      adopted text TA-10-2026-0373 (procedure 2025-0207): https://www.europarl.europa.eu/doceo/document/TA-10-2026-0373_EN.html
11:31 Geographical indications: aligning EU rules with changes to the provisions under the Lisbon Agre
      item 993383, A-10-2026-0211: 1 vote(s), 1 roll-call, {'ADOPTED': 1}
      last vote: 'Am 36' ADOPTED +613 -3 =-
      adopted text TA-10-2026-0374 (procedure 2026-0044): https://www.europarl.europa.eu/doceo/document/TA-10-2026-0374_EN.html
11:35 Association of the overseas countries and territories with the EU including EU/Greenland/Denmark
      item 993372, A-10-2026-0275: 19 vote(s), 2 roll-call, {'ADOPTED': 15, 'REJECTED': 3, 'LAPSED': 1}
      last vote: 'Commission proposal to the Council' ADOPTED +460 -76 =81
      adopted text TA-10-2026-0375 (procedure 2025-0264): https://www.europarl.europa.eu/doceo/document/TA-10-2026-0375_EN.html
11:36 Europe’s Beating Cancer Plan
      item 993373, A-10-2026-0261: 61 vote(s), 48 roll-call, {'ADOPTED': 41, 'REJECTED': 20}
      last vote: 'Motion for a resolution (as a whole)' ADOPTED +447 -66 =91
      adopted text TA-10-2026-0376 (procedure 2025-2139): https://www.europarl.europa.eu/doceo/document/TA-10-2026-0376_EN.html
11:48 EU agri-food promotion policy
      item 993379, A-10-2026-0269: 22 vote(s), 10 roll-call, {'REJECTED': 13, 'ADOPTED': 9}
      last vote: 'Motion for a resolution (as a whole)' ADOPTED +476 -83 =42
      adopted text TA-10-2026-0377 (procedure 2025-2089): https://www.europarl.europa.eu/doceo/document/TA-10-2026-0377_EN.html
11:54 Institutional aspects of artificial intelligence in the context of European integration
      item 993384, A-10-2026-0280: 19 vote(s), 1 roll-call, {'ADOPTED': 14, 'REJECTED': 5}
      last vote: 'Motion for a resolution (as a whole)' ADOPTED +405 -133 =60
      adopted text TA-10-2026-0378 (procedure 2025-2118): https://www.europarl.europa.eu/doceo/document/TA-10-2026-0378_EN.html
11:55 From prototypes to capabilities – enabling new defence actors to scale up
      item 993382, A-10-2026-0268: 1 vote(s), 1 roll-call, {'ADOPTED': 1}
      last vote: 'Motion for a resolution' ADOPTED +411 -133 =41
      adopted text TA-10-2026-0379 (procedure 2026-2025): https://www.europarl.europa.eu/doceo/document/TA-10-2026-0379_EN.html
11:55 Ukrainian children forcibly deported to Russia or living in Russian-occupied territories in Ukra
      item 993391, B-10-2026-0496, B-10-2026-0497, B-10-2026-0498, B-10-2026-0499, B-10-2026-0500, B-10-2026-0501, RC-10-2026-0497: 18 vote(s), 9 roll-call, {'ADOPTED': 9, 'REJECTED': 3, 'LAPSED': 6}
      last vote: 'B10-0501/2026' LAPSED (no tally: VOTE_HAND)
      adopted text TA-10-2026-0380 (procedure 2026-2947): https://www.europarl.europa.eu/doceo/document/TA-10-2026-0380_EN.html
--:-- Request for the waiver of the immunity of András Tivadar Kulja
      item 993386, A-10-2026-0283: 1 vote(s), 0 roll-call, {'ADOPTED': 1}
      last vote: 'Proposal for a decision' ADOPTED (no tally: VOTE_HAND)
      adopted text TA-10-2026-0368 (procedure 2026-2016): https://www.europarl.europa.eu/doceo/document/TA-10-2026-0368_EN.html
--:-- Request for the waiver of the immunity of Afroditi Latinopoulou
      item 993387, A-10-2026-0284: 1 vote(s), 0 roll-call, {'ADOPTED': 1}
      last vote: 'Proposal for a decision' ADOPTED (no tally: VOTE_HAND)
      adopted text TA-10-2026-0369 (procedure 2026-2049): https://www.europarl.europa.eu/doceo/document/TA-10-2026-0369_EN.html

13 of 14 vote items link to an adopted text; adopted texts not reached from a vote item: none

720 current MEPs; MT: 6 (S&D 3, PPE 3)
  PPE       Peter AGIUS                id 113523  https://www.europarl.europa.eu/meps/en/113523
  PPE       David CASA                 id 28122   https://www.europarl.europa.eu/meps/en/28122
  PPE       Roberta METSOLA            id 118859  https://www.europarl.europa.eu/meps/en/118859
  S&D       Alex AGIUS SALIBA          id 197403  https://www.europarl.europa.eu/meps/en/197403
  S&D       Daniel ATTARD              id 256934  https://www.europarl.europa.eu/meps/en/256934
  S&D       Thomas BAJADA              id 256936  https://www.europarl.europa.eu/meps/en/256936
all groups: PPE 185, S&D 135, PfE 86, ECR 84, Renew 78, Verts/ALE 53, The Left 45, NI 27, ESN 27

5 API calls: MTG-PL-2026-11-12 x1 HTTP [200] 0.5-0.5s 12 KB, vote-results x1 HTTP [200] 1.5-1.5s 1258 KB, decisions x1 HTTP [200] 0.5-0.5s 1809 KB, adopted-texts x1 HTTP [200] 1.1-1.1s 30 KB, meps x1 HTTP [200] 0.5-0.5s 162 KB
(c) European Union, 2026 - Source: European Parliament (Open Data Portal, CC BY 4.0). Changed: vote items joined to adopted texts by report number, MEPs filtered by this script.
Item URLs: https://data.europarl.europa.eu/api/v2/meetings/MTG-PL-2026-11-12 https://data.europarl.europa.eu/api/v2/meetings/MTG-PL-2026-11-12/vote-results https://data.europarl.europa.eu/api/v2/meetings/MTG-PL-2026-11-12/decisions https://data.europarl.europa.eu/api/v2/adopted-texts?sitting-date=2026-11-12&language=en https://data.europarl.europa.eu/api/v2/meps/show-current
```

### 2. robots.txt, the API docs, the Open Data rules and legal notice, and what the API does with odd requests (browser)

8 page loads and 13 in-page `fetch()` calls in the same tab. robots.txt is read line by line with comments removed (the `www` file has commented-out rules) and matched Google-style (longest rule wins, `*` = any characters). The quotes are matched on the flattened page text. The probes run from the Developers' corner page.

```python
import json, re, time

API = "https://data.europarl.europa.eu/api/v2"
FMT = "format=application%2Fld%2Bjson"
DEV = "https://data.europarl.europa.eu/en/developer-corner/opendata-api"
RULES = "https://eur-lex.europa.eu/eli/C/2025/341/oj?locale=en"      # Bureau Decision, Rules on the EP's Open Data
LEGAL = "https://www.europarl.europa.eu/legal-notice/en/"

START_JS = """(() => { window.__ep = window.__ep || {}; const id = String(Math.random()).slice(2); window.__ep[id] = null;
  const t0 = performance.now();
  fetch(%s, {credentials: 'omit', cache: 'no-store'})
    .then(async r => { const t = await r.text(); const h = {};
      for (const k of ['content-type', 'retry-after', 'x-ratelimit-limit', 'x-ratelimit-remaining', 'ratelimit', 'cache-control']) if (r.headers.get(k)) h[k] = r.headers.get(k);
      window.__ep[id] = {status: r.status, size: t.length, head: t.slice(0, 110), h: h, ms: Math.round(performance.now() - t0)}; })
    .catch(e => { window.__ep[id] = {status: 0, size: 0, head: String(e), h: {}, ms: 0}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__ep[%s]; if (v) delete window.__ep[%s]; return v; })()"""

def raw(path):
    """One in-page GET -> {status, size, head, h, ms}. No retries: this block only inspects answers."""
    rid = json.dumps(js(START_JS % json.dumps(API + path)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 120:
            raise RuntimeError(f"{path}: no answer after 120 s")
        time.sleep(0.3)
    time.sleep(2.0)                                    # Crawl-delay: 2
    return r

def page(url, wait_for=None, pause=2.0):
    """Load a page -> (HTTP status, final URL, content type, flattened text); waits up to 20 s for a phrase."""
    goto_url(url)
    wait_for_load()
    t0 = time.time()
    while True:
        txt = " ".join((js("(document.body || document.documentElement).innerText || ''") or "").split())
        if not wait_for or wait_for in txt or time.time() - t0 > 20:
            break
        time.sleep(0.5)
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    out = (st, js("location.href"), js("document.contentType"), txt)
    time.sleep(pause)
    return out

# 1) robots.txt on the API host and on www.europarl.europa.eu, as pages
paths = {"data.europarl.europa.eu": ["/api/v2/meetings/MTG-PL-2026-11-25/vote-results", "/api/v2/meps/show-current",
                                     "/api/v2/adopted-texts", "/en/developer-corner/opendata-api"],
         "www.europarl.europa.eu": ["/meps/en/113523", "/doceo/document/TA-10-2026-0389_EN.html", "/legal-notice/en/"]}
for host, ps in paths.items():
    st, _, ct, _ = page(f"https://{host}/robots.txt")
    lines = [l.split("#", 1)[0].strip() for l in (js("document.body.innerText") or "").splitlines()]
    groups, cur, prev_ua = {}, [], False                 # RFC 9309: consecutive User-agent lines share a group
    for l in filter(None, lines):
        k, _, v = (x.strip() for x in l.partition(":"))
        if k.lower() == "user-agent":
            cur = cur if prev_ua else []
            groups[v] = cur
            prev_ua = True
        else:
            cur.append((k, v))
            prev_ua = False
    print(f"{host}/robots.txt HTTP {st} {ct}; user-agent groups: {list(groups)}")
    rules = groups.get("*", [])
    print(f"  '*': {len(rules)} lines, e.g. {rules[:3]}; MEP rules: {[r for r in rules if r[1].startswith('/mep')]}")
    for p in ps:                                         # longest match wins; '*' in a rule = any characters
        hit = max(((len(v), k) for k, v in rules if k in ("Allow", "Disallow") and v
                   and re.match(re.escape(v).replace(r"\*", ".*"), p)), default=(0, "Allow"))
        print(f"    {p}: {'allowed' if hit[1] == 'Allow' else 'DISALLOWED'}")

# 2) the API docs, the Open Data rules and the legal notice, as a reader sees them
for url, needles in (
    (DEV, ["Open Data API limits the number of requests to be made at the same end point for security reasons.",
           "Maximum number of requests 500 in 5min.", "CC BY 4.0 - Attribution 4.0 International",
           "API v2 - the current stable major release, built on the OpenAPI 3 (OAS3) standard."]),
    (RULES, ["The re-use of Parliament’s open data is subject to the conditions laid down in the Creative Commons "
             "Attribution 4.0 International License (CC BY 4.0)",
             "Raw data, metadata or other documents of a comparable nature may alternatively be distributed by "
             "Parliament under the Creative Commons Universal Public Domain Dedication deed (CC0 1.0)",
             "Parliament hereby sets up and undertakes to maintain a European Parliament Open Data Portal"]),
    (LEGAL, ["is authorised, for personal use or for further non-commercial or commercial dissemination, provided "
             "that the entire item is reproduced and the source is acknowledged",
             "“© European Union, [year(s)] – Source: European Parliament”",
             "Any partial reproduction of data or multimedia items from this website must also cite the URL link",
             "The European Parliament trademarks europarl®, europarltv®, myeuroparl®, Parlamentarium® and the "
             "European Parliament logo may not be used without the European Parliament’s prior consent."]),
):
    st, href, ct, txt = page(url, wait_for=needles[0][:40], pause=10.0 if "eur-lex" in url else 2.0)  # EUR-Lex: Crawl-delay 10
    print(f"\n{href.split('//')[1][:60]} HTTP {st}")
    for n in needles:
        print(f"  {'found' if n in txt else 'MISSING'}: {n[:100]!r}")
    low = txt.lower()
    for w in ("scrap", "crawl", "robot", "artificial intelligence", "machine learning", "text and data mining",
              "automat", "non-commercial"):
        hits = [low[max(0, i - 60):i + 40] for i in range(len(low)) if low.startswith(w, i)]
        print(f"  word {w!r}: {len(hits)}" + (f" -> {hits[0]!r}" if hits else ""))

# 3) the human pages this skill links to
for url in ("https://www.europarl.europa.eu/meps/en/113523",
            "https://www.europarl.europa.eu/doceo/document/TA-10-2026-0389_EN.html"):
    st, href, ct, txt = page(url, wait_for="Peter AGIUS" if "meps" in url else "Texts adopted")
    m = re.search(r"(Peter AGIUS .{0,110}|Texts adopted .{0,120})", txt)
    print(f"\n{url} -> HTTP {st} {href.split('europa.eu')[1]}: {m.group(0) if m else txt[:100]!r}")

# 4) what the API does with odd requests (fetch from the Developers' corner page, same origin)
page(DEV, wait_for="Maximum number of requests")
print()
for label, path in (
    ("sitting 25 Nov, limit 5               ", f"/meetings/MTG-PL-2026-11-25/vote-results?{FMT}&offset=0&limit=5"),
    ("no plenary on Sat 21 Nov: votes       ", f"/meetings/MTG-PL-2026-11-21/vote-results?{FMT}&offset=0&limit=5"),
    ("no plenary on Sat 21 Nov: sitting     ", f"/meetings/MTG-PL-2026-11-21?{FMT}"),
    ("decisions offset=0 limit=5            ", f"/meetings/MTG-PL-2026-11-25/decisions?{FMT}&offset=0&limit=5"),
    ("decisions offset=500 limit=5          ", f"/meetings/MTG-PL-2026-11-25/decisions?{FMT}&offset=500&limit=5"),
    ("no format= parameter                  ", "/meetings/MTG-PL-2026-11-25/vote-results?offset=0&limit=2"),
    ("adopted text TA-10-2026-0389, en      ", f"/adopted-texts/TA-10-2026-0389?{FMT}&language=en"),
    ("unknown adopted text TA-10-2026-9999  ", f"/adopted-texts/TA-10-2026-9999?{FMT}"),
    ("MEP id 1 (not current)                ", f"/meps/1?{FMT}"),
    ("all current MEPs (limit=1000)         ", f"/meps/show-current?{FMT}&offset=0&limit=1000"),
    ("current MEPs, FR + group PFE          ", f"/meps/show-current?country-of-representation=FR&political-group=PFE&{FMT}&offset=0&limit=100"),
    ("current MEPs, FR + group PfE (label)  ", f"/meps/show-current?country-of-representation=FR&political-group=PfE&{FMT}&offset=0&limit=100"),
    ("country fr (lower case)               ", f"/meps/show-current?country-of-representation=fr&{FMT}&offset=0&limit=100"),
):
    r = raw(path)
    if label.startswith("sitting"):                    # rate-limit or cache headers, if any, on a normal answer
        print(f"headers seen: {r['h']}")
    print(f"{label} HTTP {r['status']} {r['size'] // 1000:>5} KB {r['ms'] / 1000:5.1f}s "
          f"{(r['h'].get('content-type') or '-').split(';')[0]:<20} {' '.join(r['head'].split())[:58]!r}")
```

Output (fourth run, 2026-11-26 00:03 UTC; the three runs before it, 23:49-23:52 UTC, gave the same robots, quotes and statuses, with the PfE-label probe at 13.9, 9.4 and 9.7 s):

```text
data.europarl.europa.eu/robots.txt HTTP 200 text/plain; user-agent groups: ['*', 'facebookexternalhit', 'SemrushBot']
  '*': 2 lines, e.g. [('Crawl-delay', '2'), ('Allow', '/')]; MEP rules: []
    /api/v2/meetings/MTG-PL-2026-11-25/vote-results: allowed
    /api/v2/meps/show-current: allowed
    /api/v2/adopted-texts: allowed
    /en/developer-corner/opendata-api: allowed
www.europarl.europa.eu/robots.txt HTTP 200 text/plain; user-agent groups: ['008', '*']
  '*': 30 lines, e.g. [('Disallow', '/calendar/'), ('Disallow', '/debats/'), ('Disallow', '/pv1/')]; MEP rules: [('Disallow', '/meps/*/pdf*'), ('Disallow', '/meps/*/xml*'), ('Disallow', '/meps/*/eptvAjax')]
    /meps/en/113523: allowed
    /doceo/document/TA-10-2026-0389_EN.html: allowed
    /legal-notice/en/: allowed

data.europarl.europa.eu/en/developer-corner/opendata-api HTTP 200
  found: 'Open Data API limits the number of requests to be made at the same end point for security reasons.'
  found: 'Maximum number of requests 500 in 5min.'
  found: 'CC BY 4.0 - Attribution 4.0 International'
  found: 'API v2 - the current stable major release, built on the OpenAPI 3 (OAS3) standard.'
  word 'scrap': 0
  word 'crawl': 0
  word 'robot': 0
  word 'artificial intelligence': 0
  word 'machine learning': 0
  word 'text and data mining': 0
  word 'automat': 0
  word 'non-commercial': 0

eur-lex.europa.eu/eli/C/2025/341/oj?locale=en HTTP 200
  found: 'The re-use of Parliament’s open data is subject to the conditions laid down in the Creative Commons '
  found: 'Raw data, metadata or other documents of a comparable nature may alternatively be distributed by Par'
  found: 'Parliament hereby sets up and undertakes to maintain a European Parliament Open Data Portal'
  word 'scrap': 0
  word 'crawl': 0
  word 'robot': 0
  word 'artificial intelligence': 1 -> 'ion and to enable new technologies to be used, most notably artificial intelligence; (2) public orga'
  word 'machine learning': 0
  word 'text and data mining': 0
  word 'automat': 0
  word 'non-commercial': 0

www.europarl.europa.eu/legal-notice/en/ HTTP 200
  found: 'is authorised, for personal use or for further non-commercial or commercial dissemination, provided '
  found: '“© European Union, [year(s)] – Source: European Parliament”'
  found: 'Any partial reproduction of data or multimedia items from this website must also cite the URL link'
  found: 'The European Parliament trademarks europarl®, europarltv®, myeuroparl®, Parlamentarium® and the Euro'
  word 'scrap': 0
  word 'crawl': 0
  word 'robot': 0
  word 'artificial intelligence': 0
  word 'machine learning': 0
  word 'text and data mining': 0
  word 'automat': 0
  word 'non-commercial': 1 -> 'ghts of use, is authorised, for personal use or for further non-commercial or commercial disseminati'

https://www.europarl.europa.eu/meps/en/113523 -> HTTP 200 /meps/en/113523/PETER_AGIUS/home: "Peter AGIUS Group of the European People's Party (Christian Democrats) Member E-mail X Facebook Instagram Malta - Partit N"

https://www.europarl.europa.eu/doceo/document/TA-10-2026-0389_EN.html -> HTTP 200 /doceo/document/TA-10-2026-0389_EN.html: 'Texts adopted : P10_TA(2026)0389 Texts adopted 129k 45k Wednesday, 25 November 2026 - Strasbourg Draft amending budget No 3/2026: adju'

headers seen: {'content-type': 'application/ld+json;charset=UTF-8', 'cache-control': 'no-cache, no-store, max-age=0, must-revalidate'}
sitting 25 Nov, limit 5                HTTP 200     6 KB   0.5s application/ld+json  '{"data":[{"id":"eli/dl/event/MTG-PL-2026-11-25-VOT-ITM-993'
no plenary on Sat 21 Nov: votes        HTTP 204     0 KB   0.4s -                    ''
no plenary on Sat 21 Nov: sitting      HTTP 404     0 KB   0.1s -                    ''
decisions offset=0 limit=5             HTTP 200  1381 KB   0.7s application/ld+json  '{"data":[{"id":"eli/dl/event/MTG-PL-2026-11-25-DEC-201197"'
decisions offset=500 limit=5           HTTP 200  1381 KB   0.5s application/ld+json  '{"data":[{"id":"eli/dl/event/MTG-PL-2026-11-25-DEC-201197"'
no format= parameter                   HTTP 200     3 KB   0.6s application/rdf+xml  '<?xml version="1.0"?> <rdf:RDF xmlns:eli-dl="http://data.e'
adopted text TA-10-2026-0389, en       HTTP 200     2 KB   0.5s application/ld+json  '{"data":[{"id":"eli/dl/doc/TA-10-2026-0389","type":"Work",'
unknown adopted text TA-10-2026-9999   HTTP 204     0 KB   0.3s -                    ''
MEP id 1 (not current)                 HTTP 200    26 KB   0.1s application/ld+json  '{"data":[{"id":"person/1","type":"Person","identifier":"1"'
all current MEPs (limit=1000)          HTTP 200   162 KB   0.2s application/ld+json  '{"data":[{"id":"person/257073","type":"Person","identifier'
current MEPs, FR + group PFE           HTTP 200     6 KB   0.1s application/ld+json  '{"data":[{"id":"person/126699","type":"Person","identifier'
current MEPs, FR + group PfE (label)   HTTP 204     0 KB  11.7s -                    ''
country fr (lower case)                HTTP 204     0 KB   2.5s -                    ''
```

### 3. The same with Python urllib, as a command-line tool: robots check, a sitting's votes, MEPs by country and group, one MEP (no browser)

Standard library only. It runs with `python3 -I`. Save it as `ep.py`. It reads robots.txt first and waits at least its `Crawl-delay` (2 s) between calls. `votes` makes 4 API calls for a sitting, `meps` 1, `mep` 3 (the member, then the group and national party bodies). Exit code 2 = no sitting that day, no MEP for that filter, or a bad argument. On a 429, a 5xx or a network error it retries once after 30 s.

```python
"""European Parliament plenary votes and current MEPs from the Open Data Portal API v2
(Python standard library only).

  python3 ep.py votes 2026-11-25          # vote items of one sitting + linked adopted texts (TA-10-YYYY-NNNN)
  python3 ep.py meps MT                   # current MEPs for a country, by political group
  python3 ep.py meps FR --group PfE       # one group ('S&D' or 'S-D', 'Verts/ALE' or 'VERTS-ALE' both work)
  python3 ep.py mep 113523                # one MEP: group and national party with their full names
"""
import argparse, json, re, sys, time, urllib.error, urllib.parse, urllib.request, urllib.robotparser
from collections import Counter
from datetime import datetime, timezone

HOST = "https://data.europarl.europa.eu"
API = HOST + "/api/v2"
UA = "bh-skill-example-prd-1.0.0 (+https://github.com/browser-use/browser-harness)"   # format the API docs suggest
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider", "bh-skill-example-prd-1.0.0"]
calls, _last, RP, GAP, SOURCES = [], [0.0], None, [2.0], []

def credit(year, note=""):
    return (f"(c) European Union, {year} - Source: European Parliament (Open Data Portal, "
            f"https://data.europarl.europa.eu, CC BY 4.0).{note}\nItem URLs: " + " ".join(SOURCES))

def src(url):
    """The API URL of an item, for the credit line (the legal notice asks partial reproductions to cite it):
    the URL without format, offset and limit."""
    u = urllib.parse.urlsplit(url)
    q = urllib.parse.urlencode([(k, v) for k, v in urllib.parse.parse_qsl(u.query) if k not in ("format", "offset", "limit")])
    return f"{u.scheme}://{u.netloc}{u.path}" + (f"?{q}" if q else "")

def http(url):
    """-> (status, text). Serial, at least GAP s apart (robots.txt Crawl-delay; 500 requests per 5 min)."""
    time.sleep(max(0.0, _last[0] + GAP[0] - time.time()))
    t0 = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/ld+json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            status, body = r.status, r.read()
    except urllib.error.HTTPError as e:
        status, body = e.code, e.read()
    except (urllib.error.URLError, TimeoutError) as e:
        status, body = 0, str(e).encode()
    _last[0] = time.time()
    p = urllib.parse.urlparse(url).path.replace("/api/v2", "")
    p = re.sub(r"/\d+$", "/{id}", re.sub(r"MTG-PL-[\d-]+", "{sitting}", p))   # e.g. /meetings/{sitting}/decisions
    calls.append((p, status, round(time.time() - t0, 2), len(body)))
    return status, body.decode("utf-8", errors="replace")

def call(path, missing=(204,), **params):
    """-> parsed JSON-LD, or None for a status in `missing`: HTTP 204 is this API's "nothing for that id or
    filter"; /meetings/{id} answers 404 for a day without a sitting.
    Checks robots.txt first. 429, 500, 502, 503, 504 or a network error: one retry after 30 s. Anything else: exit."""
    params["format"] = "application/ld+json"
    url = API + path + "?" + urllib.parse.urlencode(params)
    if src(url) not in SOURCES:
        SOURCES.append(src(url))
    if RP and not all(RP.can_fetch(a, url) for a in AGENTS):
        sys.exit(f"robots.txt disallows {path}: stop")
    for attempt in range(2):
        s, text = http(url)
        if attempt == 0 and s in (0, 429, 500, 502, 503, 504):
            time.sleep(30)
            continue
        break
    if s in missing:
        return None
    if s != 200:
        sys.exit(f"{url}: HTTP {s} {' '.join(text.split())[:160]!r}")
    return json.loads(text)

def paged(path, limit=50, keep=lambda x: True, **params):
    """offset/limit pages until a short page; `keep` picks the rows that `limit` counts."""
    out, off = [], 0
    while True:
        d = call(path, offset=off, limit=limit, **params)
        page = [x for x in (d["data"] if d else []) if keep(x)]
        out += page
        if len(page) < limit:
            return out
        off += limit

def robots_load():
    """data.europarl.europa.eu/robots.txt: '*' Allow: / with Crawl-delay: 2 today. Uses the delay it gives."""
    global RP
    s, text = http(HOST + "/robots.txt")
    if 400 <= s < 500 and s != 429:
        print(f"robots.txt: HTTP {s}, no rules")
        return
    if s != 200:
        sys.exit(f"robots.txt: HTTP {s}; rules unknown, try later")
    RP = urllib.robotparser.RobotFileParser()
    RP.parse(text.splitlines())
    GAP[0] = max(GAP[0], float(RP.crawl_delay("*") or 0))
    blocked = [a for a in AGENTS if not RP.can_fetch(a, API + "/meetings")]
    print(f"robots.txt: HTTP 200, crawl-delay {RP.crawl_delay('*')}; /api/v2 allowed for "
          f"{len(AGENTS) - len(blocked)} of {len(AGENTS)} agents" + (f" (not: {blocked})" if blocked else ""))

def doc_ref(label):
    """'A10-0310/2026 - ...' -> 'A-10-2026-0310'; 'RC-B10-0508/2026 - ...' -> 'RC-10-2026-0508'."""
    m = re.match(r"(RC-)?([A-C])(\d+)-(\d{4})/(\d{4})\b", label)
    return m and f"{'RC' if m[1] else m[2]}-{m[3]}-{m[5]}-{m[4]}"

def votes(day):
    sid = "MTG-PL-" + day
    s = call(f"/meetings/{sid}", missing=(204, 404))
    if not s:
        print(f"{sid}: no plenary sitting that day (HTTP {calls[-1][1]})")
        return 2
    print(f"{s['data'][0]['activity_label']['en']} ({sid})")
    # vote items only (the answer also carries split/separate/roll-call requests); limit counts vote items
    items = paged(f"/meetings/{sid}/vote-results", keep=lambda x: x["had_activity_type"].endswith("PLENARY_VOTE_RESULTS"))
    decs = (call(f"/meetings/{sid}/decisions") or {"data": []})["data"]   # every vote at once; offset/limit ignored
    texts = paged("/adopted-texts", **{"sitting-date": day, "language": "en"})
    ta_for, title = {}, {}
    for w in texts:
        title[w["identifier"]] = w.get("title_dcterms", {}).get("en", "")
        for a in w.get("adopts", []):
            ta_for.setdefault(a.split("/")[-1], set()).add(w["identifier"])
    by_item = {}
    for d in decs:
        by_item.setdefault((d.get("inverse_consists_of") or [""])[0], []).append(d)
    lab = lambda x: (x.get("activity_label") or {}).get("en") or (x.get("activity_label") or {}).get("mul") \
        or (x.get("referenceText") or {}).get("en", "")
    doc = re.compile(r"(A|B|C|RC)-\d+-\d{4}-\d{4}")              # report ids; drops amendment ids (...-AM-12)
    rows = []
    for it in items:
        vs = sorted(by_item.get(it["id"], []), key=lambda d: (float(d.get("activity_order", 0)),
                    d.get("activity_start_date", ""), int(d["notation_votingId"])))
        refs = {x.split("/")[-1] for x in it.get("based_on_a_realization_of", [])}
        refs |= {r for d in vs for r in [doc_ref(lab(d))] + [x.split("/")[-1] for x in d.get("decided_on_a_realization_of", [])] if r}
        refs = sorted(r for r in refs if doc.fullmatch(r))
        tas = sorted({t for r in refs for t in ta_for.get(r, ())})
        bits = (it.get("activity_label") or {}).get("mul", "").split(" - ")   # sitting day: "French - English - German"
        name = (it.get("activity_label") or {}).get("en") or (bits[1] if len(bits) == 3 else title.get(tas[0], "") if tas else lab(it))
        first = min((d["activity_start_date"] for d in vs if d.get("activity_start_date")), default="")
        rows.append((first or "~", min((int(d["notation_votingId"]) for d in vs), default=0), name, refs, tas, vs))
    print(f"{len(rows)} vote items, {len(decs)} votes "
          f"({', '.join(f'{k.split(chr(47))[-1]} {v}' for k, v in Counter(d['decision_method'] for d in decs).items())}), "
          f"{len(texts)} adopted texts\n")
    for t, _, name, refs, tas, vs in sorted(rows):
        out = Counter(d["decision_outcome"].split("/")[-1] for d in vs if d.get("decision_outcome"))
        last = vs[-1] if vs else {}
        tally = (f"+{last['number_of_votes_favor']} -{last.get('number_of_votes_against', '-')} "
                 f"={last.get('number_of_votes_abstention', '-')}" if "number_of_votes_favor" in last else "no tally")
        print(f"{t[11:16] if t != '~' else '--:--'}  {name[:100]}")
        print(f"       {', '.join(refs) or '-'}: {len(vs)} vote(s)"
              + (f" ({', '.join(f'{k} {v}' for k, v in out.items())})" if out else " (no outcome field yet)")
              + (f"; last {(last.get('decision_outcome') or '').split('/')[-1] or 'vote'} {tally}" if vs else "")
              + (f" -> {', '.join(tas)}" if tas else " -> no adopted text that day"))
    loose = sorted(set(title) - {t for r in rows for t in r[4]})
    if loose:
        print(f"\nadopted texts dated {day} not linked to a vote item: " + ", ".join(f"{t} {title[t][:60]}" for t in loose))
    print("\n" + credit(day[:4], " Joined by report number by this script."))
    return 0

def gkey(s):
    return re.sub(r"[^A-Z]", "", (s or "").upper())

def meps(country, group):
    d = call("/meps/show-current", offset=0, limit=1000)     # one fast call; filtered calls took 7-15 s
    allm = d["data"] if d else []
    got = [m for m in allm if m.get("api:country-of-representation") == country
           and (not group or gkey(m.get("api:political-group")) == gkey(group))]
    print(f"{len(allm)} current MEPs; {country}{' ' + group if group else ''}: {len(got)}")
    for g, n in Counter(m["api:political-group"] for m in got).most_common():
        names = [m["label"] for m in sorted(got, key=lambda m: m.get("sortLabel", "")) if m["api:political-group"] == g]
        print(f"  {g} ({n}): " + ", ".join(names))
    print("\n" + credit(datetime.now(timezone.utc).year))
    return 0 if got else 2

def mep(mid):
    d = call(f"/meps/{mid}")
    if not d:
        print(f"MEP {mid}: HTTP 204, no such id")
        return 2
    p = d["data"][0]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cur = [m for m in p.get("hasMembership", []) if m.get("memberDuring", {}).get("startDate", "9") <= now
           and m.get("memberDuring", {}).get("endDate", "9999") >= now]
    term = [m for m in cur if m.get("organization") == "org/ep-10"]
    print(f"{p['label']} (id {mid}), current member of the 10th term: {'yes' if term else 'no'}; "
          f"profile https://www.europarl.europa.eu/meps/en/{mid}")
    for kind in ("EU_POLITICAL_GROUP", "NATIONAL_POLITICAL_GROUP"):
        for m in [m for m in cur if m.get("membershipClassification", "").endswith(kind)]:
            b = call(f"/corporate-bodies/{m['organization'].split('/')[-1]}", language="en")["data"][0]
            print(f"  {kind.lower().replace('_', ' ')}: {b.get('label')} = {b.get('prefLabel', {}).get('en')} "
                  f"(since {m['memberDuring']['startDate']}, role {m['role'].split('/')[-1]})")
    print("\n" + credit(now[:4]))
    return 0

ap = argparse.ArgumentParser()
sub = ap.add_subparsers(dest="cmd", required=True)
v = sub.add_parser("votes"); v.add_argument("date", help="plenary sitting day, YYYY-MM-DD")
m = sub.add_parser("meps"); m.add_argument("country", help="ISO 3166-1 alpha-2, e.g. MT, FR, GR (Greece)")
m.add_argument("--group", help="PPE, S&D, PfE, ECR, Renew, Verts/ALE, The Left, ESN or NI")
o = sub.add_parser("mep"); o.add_argument("id", help="MEP id, e.g. 113523")
args = ap.parse_args()
if args.cmd == "votes" and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
    ap.error("date must be YYYY-MM-DD")
if args.cmd == "meps" and not re.fullmatch(r"[A-Za-z]{2}", args.country):
    ap.error("country must be a 2-letter code")
if args.cmd == "mep" and not args.id.isdigit():
    ap.error("id must be a number")

print(f"European Parliament Open Data API v2, checked {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC")
robots_load()
rc = votes(args.date) if args.cmd == "votes" else meps(args.country.upper(), args.group) if args.cmd == "meps" else mep(args.id)
by = {}
for p, st, t, z in calls:
    by.setdefault(p, []).append(st)
print(f"{len(calls)} calls: " + ", ".join(f"{p} x{len(v)} {sorted(set(v))}" for p, v in by.items()))
sys.exit(rc)
```

Output (nine commands, 2026-11-26 01:15-01:16 UTC, after the `Item URLs` line was added; the run at 00:01-00:02 UTC printed the same lines apart from timings, and the sitting answers were the same in the third run at 23:58 UTC):

```text
$ python3 -I ep.py votes 2026-11-12
European Parliament Open Data API v2, checked 2026-11-26 01:15 UTC
robots.txt: HTTP 200, crawl-delay 2; /api/v2 allowed for 12 of 12 agents
Thursday, 12 November 2026 (MTG-PL-2026-11-12)
14 vote items, 226 votes (VOTE_HAND 122, VOTE_ELECTRONIC_ROLLCALL 95, VOTE_ELECTRONIC 9), 13 adopted texts

11:18  Amendment of the Statute for Members of the European Parliament, as regards proxy voting
       A-10-2026-0270: 13 vote(s) (ADOPTED 12, REJECTED 1); last ADOPTED +578 -25 =4 -> TA-10-2026-0370
11:19  Union Civil Protection Mechanism and Union support for health emergency preparedness and response **
       A-10-2026-0271: 61 vote(s) (REJECTED 31, ADOPTED 27, LAPSED 3); last ADOPTED no tally -> TA-10-2026-0371
11:28  Modernisation of the key information document ***I
       A-9-2024-0160: 2 vote(s) (ADOPTED 2); last ADOPTED no tally -> TA-10-2026-0372
11:28  Union retail investor protection rules ***I
       A-9-2024-0162: 1 vote(s) (REJECTED 1); last REJECTED +286 -300 =23 -> no adopted text that day
11:29  European Chemicals Agency and amending regulations ***I
       A-10-2026-0093: 6 vote(s) (ADOPTED 1, LAPSED 5); last LAPSED no tally -> TA-10-2026-0373
11:31  Geographical indications: aligning EU rules with changes to the provisions under the Lisbon Agreemen
       A-10-2026-0211: 1 vote(s) (ADOPTED 1); last ADOPTED +613 -3 =- -> TA-10-2026-0374
11:35  Association of the overseas countries and territories with the EU including EU/Greenland/Denmark rel
       A-10-2026-0275: 19 vote(s) (ADOPTED 15, REJECTED 3, LAPSED 1); last ADOPTED +460 -76 =81 -> TA-10-2026-0375
11:36  Europe’s Beating Cancer Plan
       A-10-2026-0261: 61 vote(s) (ADOPTED 41, REJECTED 20); last ADOPTED +447 -66 =91 -> TA-10-2026-0376
11:48  EU agri-food promotion policy
       A-10-2026-0269: 22 vote(s) (REJECTED 13, ADOPTED 9); last ADOPTED +476 -83 =42 -> TA-10-2026-0377
11:54  Institutional aspects of artificial intelligence in the context of European integration
       A-10-2026-0280: 19 vote(s) (ADOPTED 14, REJECTED 5); last ADOPTED +405 -133 =60 -> TA-10-2026-0378
11:55  From prototypes to capabilities – enabling new defence actors to scale up
       A-10-2026-0268: 1 vote(s) (ADOPTED 1); last ADOPTED +411 -133 =41 -> TA-10-2026-0379
11:55  Ukrainian children forcibly deported to Russia or living in Russian-occupied territories in Ukraine
       B-10-2026-0496, B-10-2026-0497, B-10-2026-0498, B-10-2026-0499, B-10-2026-0500, B-10-2026-0501, RC-10-2026-0497: 18 vote(s) (ADOPTED 9, REJECTED 3, LAPSED 6); last LAPSED no tally -> TA-10-2026-0380
--:--  Request for the waiver of the immunity of András Tivadar Kulja
       A-10-2026-0283: 1 vote(s) (ADOPTED 1); last ADOPTED no tally -> TA-10-2026-0368
--:--  Request for the waiver of the immunity of Afroditi Latinopoulou
       A-10-2026-0284: 1 vote(s) (ADOPTED 1); last ADOPTED no tally -> TA-10-2026-0369

(c) European Union, 2026 - Source: European Parliament (Open Data Portal, https://data.europarl.europa.eu, CC BY 4.0). Joined by report number by this script.
Item URLs: https://data.europarl.europa.eu/api/v2/meetings/MTG-PL-2026-11-12 https://data.europarl.europa.eu/api/v2/meetings/MTG-PL-2026-11-12/vote-results https://data.europarl.europa.eu/api/v2/meetings/MTG-PL-2026-11-12/decisions https://data.europarl.europa.eu/api/v2/adopted-texts?sitting-date=2026-11-12&language=en
5 calls: /robots.txt x1 [200], /meetings/{sitting} x1 [200], /meetings/{sitting}/vote-results x1 [200], /meetings/{sitting}/decisions x1 [200], /adopted-texts x1 [200]
[exit 0]

$ python3 -I ep.py votes 2026-11-25
European Parliament Open Data API v2, checked 2026-11-26 01:16 UTC
robots.txt: HTTP 200, crawl-delay 2; /api/v2 allowed for 12 of 12 agents
Wednesday, 25 November 2026 (MTG-PL-2026-11-25)
23 vote items, 124 votes (VOTE_ELECTRONIC_ROLLCALL 124), 17 adopted texts

12:05  Draft amending budget No 3/2026: adjustments in expenditure, update of revenues and other technical
       A-10-2026-0310: 8 vote(s) (no outcome field yet); last vote +441 -97 =120 -> TA-10-2026-0389
12:07  2027 budgetary procedure: joint text
       A-10-2026-0305: 1 vote(s) (no outcome field yet); last vote +406 -184 =69 -> TA-10-2026-0390
12:11  Establishing Global Europe
       A-10-2026-0277: 1 vote(s) (no outcome field yet); last vote +416 -233 =9 -> no adopted text that day
12:11  European Social Fund 2028–2034
       A-10-2026-0291: 1 vote(s) (no outcome field yet); last vote +457 -199 =6 -> no adopted text that day
12:12  Horizon Europe framework programme for research and innovation 2028–2034
       A-10-2026-0299: 1 vote(s) (no outcome field yet); last vote +458 -190 =14 -> no adopted text that day
12:12  Connecting Europe Facility 2028–2034
       A-10-2026-0301: 1 vote(s) (no outcome field yet); last vote +451 -173 =38 -> no adopted text that day
12:13  Union support for asylum, migration and integration 2028–2034
       A-10-2026-0312: 1 vote(s) (no outcome field yet); last vote +445 -208 =10 -> no adopted text that day
12:14  'AgoraEU' programme 2028–2034
       A-10-2026-0313: 1 vote(s) (no outcome field yet); last vote +448 -206 =10 -> no adopted text that day
12:17  Union procedures for the authorisation and supervision of medicinal products for human use and rules
       A-10-2026-0296: 1 vote(s) (no outcome field yet); last vote +118 -536 =6 -> TA-10-2026-0391
12:21  Union code relating to medicinal products for human use
       A-10-2026-0297: 3 vote(s) (no outcome field yet); last vote +549 -82 =26 -> TA-10-2026-0392
12:26  Amendments to Parliament’s Rules of Procedure on proxy voting during pregnancy and immediately after
       A-10-2026-0298: 3 vote(s) (no outcome field yet); last vote +627 -25 =5 -> TA-10-2026-0393
12:28  Speeding-up environmental assessments (Omnibus VIII on environmental legislation)
       A-10-2026-0290: 40 vote(s) (no outcome field yet); last vote +367 -268 =25 -> TA-10-2026-0394
12:45  Framework for strengthening the availability and security of supply of critical medicinal products a
       A-10-2025-0272: 2 vote(s) (no outcome field yet); last vote +592 -35 =30 -> TA-10-2026-0395
12:48  Placing on the market of genetically modified micro-organisms and the processing of organs
       A-10-2026-0304: 23 vote(s) (no outcome field yet); last vote +351 -176 =132 -> TA-10-2026-0396
12:55  EU-Switzerland broad package of agreements to consolidate, deepen and expand their bilateral relatio
       A-10-2026-0235: 2 vote(s) (no outcome field yet); last vote +554 -22 =79 -> TA-10-2026-0397
12:55  EU-Switzerland broad package of agreements to consolidate, deepen and expand their bilateral relatio
       A-10-2026-0236: 1 vote(s) (no outcome field yet); last vote +584 -13 =60 -> TA-10-2026-0398
12:56  VAT fraud: extension of the application period of the optional reverse charge mechanism and Quick Re
       A-10-2026-0282: 1 vote(s) (no outcome field yet); last vote +629 -2 =26 -> TA-10-2026-0399
12:56  Euratom research and training programme 2028-2032
       A-10-2026-0293: 1 vote(s) (no outcome field yet); last vote +512 -96 =48 -> TA-10-2026-0400
12:58  VAT reverse-charge mechanism
       A-10-2026-0300: 8 vote(s) (no outcome field yet); last vote +409 -185 =30 -> TA-10-2026-0401
13:01  EU-Syria political relations
       A-10-2026-0278: 13 vote(s) (no outcome field yet); last vote +416 -126 =101 -> TA-10-2026-0402
13:06  Towards an EU strategy to protect and strengthen the international justice system and its institutio
       A-10-2026-0281: 2 vote(s) (no outcome field yet); last vote +438 -168 =38 -> TA-10-2026-0403
13:07  Media freedom and rule of law in the Czech Republic: threats to the independence of public broadcast
       RC-10-2026-0508: 8 vote(s) (no outcome field yet); last vote +442 -158 =47 -> TA-10-2026-0404
13:08  Objection pursuant to Rule 115(2) and (3): European List of ship recycling facilities
       B-10-2026-0505: 1 vote(s) (no outcome field yet); last vote +377 -214 =24 -> TA-10-2026-0405

(c) European Union, 2026 - Source: European Parliament (Open Data Portal, https://data.europarl.europa.eu, CC BY 4.0). Joined by report number by this script.
Item URLs: https://data.europarl.europa.eu/api/v2/meetings/MTG-PL-2026-11-25 https://data.europarl.europa.eu/api/v2/meetings/MTG-PL-2026-11-25/vote-results https://data.europarl.europa.eu/api/v2/meetings/MTG-PL-2026-11-25/decisions https://data.europarl.europa.eu/api/v2/adopted-texts?sitting-date=2026-11-25&language=en
5 calls: /robots.txt x1 [200], /meetings/{sitting} x1 [200], /meetings/{sitting}/vote-results x1 [200], /meetings/{sitting}/decisions x1 [200], /adopted-texts x1 [200]
[exit 0]

$ python3 -I ep.py meps MT
European Parliament Open Data API v2, checked 2026-11-26 01:16 UTC
robots.txt: HTTP 200, crawl-delay 2; /api/v2 allowed for 12 of 12 agents
720 current MEPs; MT: 6
  S&D (3): Alex AGIUS SALIBA, Daniel ATTARD, Thomas BAJADA
  PPE (3): Peter AGIUS, David CASA, Roberta METSOLA

(c) European Union, 2026 - Source: European Parliament (Open Data Portal, https://data.europarl.europa.eu, CC BY 4.0).
Item URLs: https://data.europarl.europa.eu/api/v2/meps/show-current
2 calls: /robots.txt x1 [200], /meps/show-current x1 [200]
[exit 0]

$ python3 -I ep.py meps FR --group PfE
European Parliament Open Data API v2, checked 2026-11-26 01:16 UTC
robots.txt: HTTP 200, crawl-delay 2; /api/v2 allowed for 12 of 12 agents
720 current MEPs; FR PfE: 29
  PfE (29): Mathilde ANDROUËT, Jordan BARDELLA, Christophe BAY, Marie-Luce BRASIER-CLAIN, Marie DAUCHY, Valérie DELOGE, Mélanie DISDIER, Anne-Sophie FRIGOUT, Angéline FURET, Jean-Paul GARRAUD, Catherine GRISET, France JAMET, Virginie JORON, Fabrice LEGGERI, Julien LEONARDELLI, Thierry MARIANI, Aleksandar NIKOLIC, Philippe OLIVIER, Gilles PENNELLE, Pascale PIERA, Pierre PIMPIE, Julie RECHAGNEUX, André ROUGÉ, Julien SANCHEZ, Pierre-Romain THIONNET, Rody TOLASSY, Matthieu VALET, Alexandre VARAUT, Séverine WERBROUCK

(c) European Union, 2026 - Source: European Parliament (Open Data Portal, https://data.europarl.europa.eu, CC BY 4.0).
Item URLs: https://data.europarl.europa.eu/api/v2/meps/show-current
2 calls: /robots.txt x1 [200], /meps/show-current x1 [200]
[exit 0]

$ python3 -I ep.py meps GR --group S-D
European Parliament Open Data API v2, checked 2026-11-26 01:16 UTC
robots.txt: HTTP 200, crawl-delay 2; /api/v2 allowed for 12 of 12 agents
720 current MEPs; GR S-D: 4
  S&D (4): Sakis ARNAOUTOGLOU, Nikolas FARANTOURIS, Yannis MANIATIS, Nikos PAPANDREOU

(c) European Union, 2026 - Source: European Parliament (Open Data Portal, https://data.europarl.europa.eu, CC BY 4.0).
Item URLs: https://data.europarl.europa.eu/api/v2/meps/show-current
2 calls: /robots.txt x1 [200], /meps/show-current x1 [200]
[exit 0]

$ python3 -I ep.py mep 113523
European Parliament Open Data API v2, checked 2026-11-26 01:16 UTC
robots.txt: HTTP 200, crawl-delay 2; /api/v2 allowed for 12 of 12 agents
Peter AGIUS (id 113523), current member of the 10th term: yes; profile https://www.europarl.europa.eu/meps/en/113523
  eu political group: PPE = Group of the European People's Party (Christian Democrats) (since 2024-07-16, role MEMBER)
  national political group: PN = Partit Nazzjonalista (since 2024-07-16, role MEMBER)

(c) European Union, 2026 - Source: European Parliament (Open Data Portal, https://data.europarl.europa.eu, CC BY 4.0).
Item URLs: https://data.europarl.europa.eu/api/v2/meps/113523 https://data.europarl.europa.eu/api/v2/corporate-bodies/7018?language=en https://data.europarl.europa.eu/api/v2/corporate-bodies/6690?language=en
4 calls: /robots.txt x1 [200], /meps/{id} x1 [200], /corporate-bodies/{id} x2 [200]
[exit 0]

$ python3 -I ep.py mep 1
European Parliament Open Data API v2, checked 2026-11-26 01:16 UTC
robots.txt: HTTP 200, crawl-delay 2; /api/v2 allowed for 12 of 12 agents
Georg JARZEMBOWSKI (id 1), current member of the 10th term: no; profile https://www.europarl.europa.eu/meps/en/1

(c) European Union, 2026 - Source: European Parliament (Open Data Portal, https://data.europarl.europa.eu, CC BY 4.0).
Item URLs: https://data.europarl.europa.eu/api/v2/meps/1
2 calls: /robots.txt x1 [200], /meps/{id} x1 [200]
[exit 0]

$ python3 -I ep.py votes 2026-11-21
European Parliament Open Data API v2, checked 2026-11-26 01:16 UTC
robots.txt: HTTP 200, crawl-delay 2; /api/v2 allowed for 12 of 12 agents
MTG-PL-2026-11-21: no plenary sitting that day (HTTP 404)
2 calls: /robots.txt x1 [200], /meetings/{sitting} x1 [404]
[exit 2]

$ python3 -I ep.py votes 25-11-2026
usage: ep.py [-h] {votes,meps,mep} ...
ep.py: error: date must be YYYY-MM-DD
[exit 2]
```

### 4. curl: robots, one sitting, one adopted text, MEPs, one MEP's group, headers, odd requests

```bash
#!/usr/bin/env bash
# European Parliament Open Data API v2 with curl: robots, one sitting's vote items and adopted texts,
# current MEPs for a country, one MEP's group, headers, odd requests.
set -euo pipefail
A=https://data.europarl.europa.eu/api/v2
F='format=application%2Fld%2Bjson'
C=(curl -sS --max-time 120 --compressed -A 'bh-skill-example-prd-1.0.0 (+https://github.com/browser-use/browser-harness)')
DAY=2026-11-12; COUNTRY=MT; MEP=113523   # any sitting day, country code, MEP id
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
# 0. robots.txt first: '*' Allow: / and Crawl-delay: 2 today; stop if a path we use is disallowed
code=$("${C[@]}" -o "$T/robots" -w '%{http_code}' https://data.europarl.europa.eu/robots.txt)
echo "robots.txt HTTP $code: $(tr '\n' ' ' < "$T/robots" | head -c 120)"
python3 -c 'import sys, urllib.robotparser
code, text = int(sys.argv[1]), open(sys.argv[2]).read()
if code != 200 and not (400 <= code < 500 and code != 429): sys.exit("robots.txt rules unknown: stop")
rp = urllib.robotparser.RobotFileParser(); rp.parse(text.splitlines() if code == 200 else [])
paths = ("/api/v2/meetings/MTG-PL-2026-11-12/vote-results", "/api/v2/meetings/MTG-PL-2026-11-12/decisions",
         "/api/v2/adopted-texts", "/api/v2/meps/show-current", "/api/v2/meps/113523", "/api/v2/corporate-bodies/7018")
agents = ("*", "GPTBot", "ClaudeBot", "Claude-User", "PerplexityBot", "CCBot", "bh-skill-example-prd-1.0.0")
if not all(rp.can_fetch(a, "https://data.europarl.europa.eu" + p) for a in agents for p in paths): sys.exit("robots.txt disallows a path: stop")
print("robots: paths allowed; crawl-delay", rp.crawl_delay("*"))' "$code" "$T/robots"
sleep 2
# offset/limit pages until a short page or HTTP 204, one JSON row per line; $3 = the activity type that limit counts
pages() {
  local off=0 code n; : > "$2"
  while :; do
    code=$("${C[@]}" -o "$T/p" -w '%{http_code}' "$A/$1&offset=$off&limit=50"); sleep 2
    [ "$code" = 204 ] && return 0
    [ "$code" = 200 ] || { echo "$1: HTTP $code, stop" >&2; return 1; }
    n=$(python3 -c 'import json, sys
d = json.load(open(sys.argv[1]))["data"]
with open(sys.argv[2], "a") as f: f.writelines(json.dumps(x) + "\n" for x in d)
print(sum(1 for x in d if x.get("had_activity_type", "").endswith(sys.argv[3])))' "$T/p" "$2" "${3:-}")
    [ "$n" -lt 50 ] && return 0
    off=$((off + 50))
  done
}
# 1. the sitting's vote items (limit counts vote items; the answer also holds split/separate requests)
pages "meetings/MTG-PL-$DAY/vote-results?$F" "$T/items" PLENARY_VOTE_RESULTS
# 2. every vote of the sitting in one answer (1.8 MB here; offset and limit are ignored)
"${C[@]}" --fail "$A/meetings/MTG-PL-$DAY/decisions?$F" -o "$T/decs"; sleep 2
# 3. adopted texts with that sitting date, English only (25 Nov: 35 KB instead of 618 KB)
pages "adopted-texts?sitting-date=$DAY&language=en&$F" "$T/tas"
# same fallbacks as blocks 1 and 3: a same-day answer has no activity_order, no outcome and only "mul" labels
python3 -c 'import json, re, sys
rows = lambda p: [json.loads(l) for l in open(p)]
items = [x for x in rows(sys.argv[1]) if x["had_activity_type"].endswith("PLENARY_VOTE_RESULTS")]
decs = json.load(open(sys.argv[2]))["data"]; tas = rows(sys.argv[3])
ta = {}
for w in tas:
    for a in w.get("adopts", []): ta.setdefault(a.split("/")[-1], set()).add(w["identifier"])
lab = lambda x: (x.get("activity_label") or {}).get("en") or (x.get("activity_label") or {}).get("mul") or (x.get("referenceText") or {}).get("en", "")
def doc_ref(s):   # "A10-0310/2026 - ..." -> "A-10-2026-0310"
    m = re.match(r"(RC-)?([A-C])(\d+)-(\d{4})/(\d{4})\b", s)
    return m and ("RC" if m[1] else m[2]) + "-" + m[3] + "-" + m[5] + "-" + m[4]
print(len(items), "vote items,", len(decs), "votes,", len(tas), "adopted texts")
for it in items[:5]:
    vs = sorted((d for d in decs if (d.get("inverse_consists_of") or [""])[0] == it["id"]),
                key=lambda d: (float(d.get("activity_order", 0)), d.get("activity_start_date", ""), int(d["notation_votingId"])))
    refs = {x.split("/")[-1] for x in it.get("based_on_a_realization_of", [])}
    refs |= {r for d in vs for r in [doc_ref(lab(d))] + [x.split("/")[-1] for x in d.get("decided_on_a_realization_of", [])] if r}
    refs = sorted(r for r in refs if re.fullmatch(r"(A|B|C|RC)-\d+-\d{4}-\d{4}", r))
    last = vs[-1] if vs else {}
    print(" ", lab(it)[:60], "|", ",".join(refs) or "-", "|", len(vs), "votes | last:", re.split(" [-\u2013] ", lab(last))[-1][:40] or "-",
          (last.get("decision_outcome") or "no-outcome-yet").split("/")[-1], last.get("number_of_votes_favor", "-"), "|",
          ",".join(sorted({t for r in refs for t in ta.get(r, ())})) or "no TA")
open(sys.argv[4], "w").write(min((w["identifier"] for w in tas), default=""))' "$T/items" "$T/decs" "$T/tas" "$T/ta1"
# 4. one adopted text of that sitting (the lowest TA number): title, the report it adopts, the procedure
TA=$(cat "$T/ta1")
if [ -n "$TA" ]; then
  "${C[@]}" --fail "$A/adopted-texts/$TA?$F&language=en" | python3 -c 'import json, sys
w = json.load(sys.stdin)["data"][0]
print(w["identifier"], w["label"], w["document_date"], "|", w["title_dcterms"]["en"], "| adopts", [a.split("/")[-1] for a in w["adopts"]], "|", w["inverse_created_a_realization_of"])'
  sleep 2
else
  echo "no adopted text dated $DAY"
fi
# 5. current MEPs: one call for all 720, then filter on country (filtered calls took 7-15 s)
"${C[@]}" --fail "$A/meps/show-current?$F&offset=0&limit=1000" | python3 -c 'import json, sys, collections
m = json.load(sys.stdin)["data"]; c = sys.argv[1]
mine = sorted((p for p in m if p["api:country-of-representation"] == c), key=lambda p: p["sortLabel"])
print(len(m), "current MEPs;", c, len(mine), dict(collections.Counter(p["api:political-group"] for p in mine)))
for p in mine: print(" ", p["identifier"], p["label"], p["api:political-group"])' "$COUNTRY"
sleep 2
# 6. one MEP: the current political-group membership, then that body's English name
"${C[@]}" --fail "$A/meps/$MEP?$F" -o "$T/mep"
org=$(python3 -c 'import json, sys
p = json.load(open(sys.argv[1]))["data"][0]
g = [m for m in p["hasMembership"] if m.get("membershipClassification", "").endswith("EU_POLITICAL_GROUP") and "endDate" not in m["memberDuring"]]
print(g[0]["organization"].split("/")[-1])' "$T/mep")
sleep 2
"${C[@]}" --fail "$A/corporate-bodies/$org?$F&language=en" | python3 -c 'import json, sys
b = json.load(sys.stdin)["data"][0]; print("MEP", sys.argv[1], "group org", b["identifier"], b["label"], "=", b["prefLabel"]["en"])' "$MEP"
sleep 2
# 7. headers on a normal answer: no rate-limit headers, no caching
"${C[@]}" -D - -o /dev/null "$A/meetings/MTG-PL-$DAY?$F" | tr -d '\r' \
  | grep -iE '^(HTTP/|(content-type|cache-control|access-control-allow-origin|retry-after|x-ratelimit[a-z-]*|ratelimit[a-z-]*):)'
sleep 2
# 8. odd requests: no sitting = 404 on the sitting, 204 on its votes; wrong-case group = 204; no format= = RDF/XML
for p in "meetings/MTG-PL-2026-11-21?$F" "meetings/MTG-PL-2026-11-21/vote-results?$F&offset=0&limit=5" \
         "meps/show-current?country-of-representation=FR&political-group=PfE&$F&offset=0&limit=5" \
         "meetings/MTG-PL-$DAY?offset=0&limit=1"; do
  "${C[@]}" -o "$T/m" -w "${p%%\?*}: HTTP %{http_code} %{content_type} %{time_total}s | " "$A/$p"; head -c 60 "$T/m" | tr '\n' ' '; echo; sleep 2
done
echo "(c) European Union, $(date -u +%Y) - Source: European Parliament (Open Data Portal, CC BY 4.0). Accessed $(date -u '+%d %B %Y %H:%M') UTC."
echo "Item URLs: $A/meetings/MTG-PL-$DAY/vote-results $A/meetings/MTG-PL-$DAY/decisions $A/adopted-texts?sitting-date=$DAY&language=en${TA:+ $A/adopted-texts/$TA} $A/meps/show-current $A/meps/$MEP $A/corporate-bodies/$org"
```

Output (2026-11-26 01:17 UTC, after block 4 started paging, picking the sitting's lowest TA number and using block 3's fallbacks; the run at 00:02 UTC printed the same vote rows except that the Ukrainian children row listed its B-10 reports in API order and without RC-10-2026-0497, and step 4 showed a fixed TA-10-2026-0376. With `DAY=2026-11-25` (01:20 UTC) it printed 23 vote items, 124 votes and 17 adopted texts, French labels and `no-outcome-yet`, and TA-10-2026-0389):

```text
robots.txt HTTP 200: User-agent: * Crawl-delay: 2 Allow: /  User-agent: facebookexternalhit Disallow: /api/  User-agent: SemrushBot Disallow:
robots: paths allowed; crawl-delay 2
14 vote items, 226 votes, 13 adopted texts
  Europe’s Beating Cancer Plan | A-10-2026-0261 | 61 votes | last: Motion for a resolution (as a whole) ADOPTED 447 | TA-10-2026-0376
  Ukrainian children forcibly deported to Russia or living in  | B-10-2026-0496,B-10-2026-0497,B-10-2026-0498,B-10-2026-0499,B-10-2026-0500,B-10-2026-0501,RC-10-2026-0497 | 18 votes | last: B10-0501/2026 LAPSED - | TA-10-2026-0380
  Request for the waiver of the immunity of Afroditi Latinopou | A-10-2026-0284 | 1 votes | last: Proposal for a decision ADOPTED - | TA-10-2026-0369
  Association of the overseas countries and territories with t | A-10-2026-0275 | 19 votes | last: Commission proposal to the Council ADOPTED 460 | TA-10-2026-0375
  EU agri-food promotion policy | A-10-2026-0269 | 22 votes | last: Motion for a resolution (as a whole) ADOPTED 476 | TA-10-2026-0377
TA-10-2026-0368 T10-0368/2026 2026-11-12 | Request for the waiver of the immunity of András Tivadar Kulja | adopts ['A-10-2026-0283'] | ['eli/dl/event/MTG-PL-2026-11-12-PVCRE-ITM-6-2', 'eli/dl/proc/2026-2016']
720 current MEPs; MT 6 {'PPE': 3, 'S&D': 3}
  113523 Peter AGIUS PPE
  197403 Alex AGIUS SALIBA S&D
  256934 Daniel ATTARD S&D
  256936 Thomas BAJADA S&D
  28122 David CASA PPE
  118859 Roberta METSOLA PPE
MEP 113523 group org 7018 PPE = Group of the European People's Party (Christian Democrats)
HTTP/2 200
content-type: application/ld+json;charset=UTF-8
cache-control: no-cache, no-store, max-age=0, must-revalidate
meetings/MTG-PL-2026-11-21: HTTP 404  0.482274s |
meetings/MTG-PL-2026-11-21/vote-results: HTTP 204  0.809663s |
meps/show-current: HTTP 204  10.224755s |
meetings/MTG-PL-2026-11-12: HTTP 200 application/rdf+xml;charset=UTF-8 0.786870s | <?xml version="1.0"?> <rdf:RDF     xmlns:eli-dl="http://data
(c) European Union, 2026 - Source: European Parliament (Open Data Portal, CC BY 4.0). Accessed 26 November 2026 01:17 UTC.
Item URLs: https://data.europarl.europa.eu/api/v2/meetings/MTG-PL-2026-11-12/vote-results https://data.europarl.europa.eu/api/v2/meetings/MTG-PL-2026-11-12/decisions https://data.europarl.europa.eu/api/v2/adopted-texts?sitting-date=2026-11-12&language=en https://data.europarl.europa.eu/api/v2/adopted-texts/TA-10-2026-0368 https://data.europarl.europa.eu/api/v2/meps/show-current https://data.europarl.europa.eu/api/v2/meps/113523 https://data.europarl.europa.eu/api/v2/corporate-bodies/7018
```

## Fields

| Endpoint / field | Value | Notes |
|---|---|---|
| `/meetings/MTG-PL-{date}` -> `data[0]` | `activity_label.en` (`Thursday, 12 November 2026`), `had_activity_type` (`PLENARY_SITTING`), `activity_start_date`, `activity_end_date`, `consists_of` (vote item ids), `recorded_in_a_realization_of` (`PV-10-2026-11-25`, the minutes) | HTTP 404 for a day without a sitting |
| `/meetings/{id}/vote-results` -> `data[]` with `had_activity_type` = `PLENARY_VOTE_RESULTS` | `activity_id` (`MTG-PL-2026-11-12-VOT-ITM-993373`), `activity_label` (24 languages + `mul`; on the sitting day only `mul`), `consists_of` (vote ids), `based_on_a_realization_of` (`A-10-2026-0261`, not on the sitting day), `notation_dlvId` | the same answer also holds `REQUEST_VOTE_SPLIT` (38 on 12 Nov), `REQUEST_VOTE_ROLLCALL` (16) and `REQUEST_VOTE_SEPARATE` (6) rows; `limit` counts vote items only |
| `/meetings/{id}/decisions` -> `data[]` | `inverse_consists_of[0]` (its vote item), `activity_label` (`en` later, French `mul` on the day), `referenceText.en` (`Motion for a resolution (as a whole)`), `decision_method` (`VOTE_HAND`, `VOTE_ELECTRONIC`, `VOTE_ELECTRONIC_ROLLCALL`), `decision_outcome` (`ADOPTED`, `REJECTED`, `LAPSED`; later only), `number_of_votes_favor` / `_against` / `_abstention`, `activity_order` (later only), `activity_start_date` (roll-call only, `+01:00`), `had_voter_favor` / `_against` / `_abstention` (`person/{id}` lists), `decided_on_a_realization_of` (report and amendment ids) | offset and limit are ignored: 124 votes / 1.38 MB on 25 Nov, 226 / 1.86 MB on 12 Nov |
| `/adopted-texts?sitting-date=&language=en` -> `data[]` | `identifier` (`TA-10-2026-0376`), `label` (`T10-0376/2026`), `notation_publicRegister` (`P10_TA(2026)0389`), `document_date`, `title_dcterms.en`, `adopts` (`eli/dl/doc/A-10-2026-0261`), `inverse_created_a_realization_of` (`eli/dl/proc/2025-2139` and a `MTG-PL-...-PVCRE-ITM-...` id) | `language=en` cut 17 texts from 618 KB to 35 KB. HTML: `https://www.europarl.europa.eu/doceo/document/{TA}_EN.html` (HTTP 200) |
| `/procedures/{year-number}` | `label` (`2025/2139(INI)`), `process_type` (`INI`), `created_a_realization_of` (`A-10-2026-0261`, `TA-10-2026-0376`, a committee document), `consists_of` (the vote item) | one call tested |
| `/meps/show-current` -> `data[]` | `identifier` (`113523`), `label` (`Peter AGIUS`), `givenName`, `familyName`, `sortLabel` (`AGIUSP`), `api:country-of-representation` (`MT`), `api:political-group` (`PPE`, `S&D`, `PfE`, `ECR`, `Renew`, `Verts/ALE`, `The Left`, `NI`, `ESN`) | 720 rows on 2026-11-26; `mandate-date=YYYY-MM-DD` for another day (not tested) |
| `/meps/{id}` -> `data[0]` | `label`, `hasMembership[]` (`membershipClassification` `EU_POLITICAL_GROUP`, `NATIONAL_POLITICAL_GROUP`, `COMMITTEE_PARLIAMENTARY_STANDING`, ...; `organization` `org/7018`; `memberDuring.startDate` / `endDate`; `role`), `citizenship`, `img` | also birthday, e-mail, phone and office numbers; the blocks print none of them |
| `/corporate-bodies/{id}?language=en` | `label` (`PPE`), `prefLabel.en` (`Group of the European People's Party (Christian Democrats)`), `classification` (`EU_POLITICAL_GROUP`) | national party: `PN` = `Partit Nazzjonalista` |
| empty answers | HTTP 204, no body, no content type | unknown TA, filter with no match, votes of a day without a sitting, a page past the end |

## Gotchas

- **The sitting day's data is provisional and shaped differently.** At 23:47-00:01 UTC on the day of the 25 November sitting, `/decisions` held only `VOTE_ELECTRONIC_ROLLCALL` votes (124), with no `decision_outcome`, no `activity_order` and labels only in `mul` (vote items as "Fraude à la TVA: ... - VAT fraud: ... - Mehrwertsteuerbetrug: ..."; single votes in French: "Proposition de résolution (ensemble du texte)", "Demande d'ajournement du vote"), and `/vote-results` had no `based_on_a_realization_of`. For 12 November the same endpoints held all 226 votes (122 `VOTE_HAND`, 9 `VOTE_ELECTRONIC`) with outcomes and English labels. When the switch happens was not tested. The blocks take the English title when there is one, else the middle part of a three-part `mul` label, else the adopted text's title, and they do not infer an outcome from the tallies.
- **Join vote items to adopted texts by report id, not by vote.** A vote item points at its report (`based_on_a_realization_of`, or the label's first token on the sitting day: `A10-0310/2026` -> `A-10-2026-0310`, `RC-B10-0508/2026` -> `RC-10-2026-0508`), and an adopted text lists the reports it `adopts`. One text can adopt several documents (TA-10-2026-0380 adopts five B-10 motions and RC-10-2026-0497), and a report can be from an earlier year (TA-10-2026-0395 adopts A-10-2025-0272). `decided_on_a_realization_of` also holds amendment ids such as `A-10-2026-0271-AM-12`; the blocks keep only whole-document ids.
- **"Last vote" is the last in the list, not necessarily the final vote.** Ordered by `activity_order`, the last vote of the civil-protection item on 12 November was "Request for referral back to committee" (ADOPTED, show of hands), of the Ukrainian children resolution "B10-0501/2026" (LAPSED); on 25 November the medicines code item's last roll-call vote was "Article 180, § 4", and for A-10-2026-0296 the only roll-call vote was a rejected request to postpone (+118 -536 =6) although TA-10-2026-0391 adopts that report the same day. Read the label printed next to the tally.
- **Not every vote has a tally.** Show-of-hands votes have no counts; one roll-call vote ("Commission proposal", LAPSED) had none, and one had no abstention count (`Am 36`, +613 -3). The blocks print `no tally` or `-`.
- **`/decisions` ignores offset and limit.** `offset=0&limit=5` and `offset=500&limit=5` both returned all 1,381 KB for 25 November. It also carries every MEP's vote per roll-call (`had_voter_favor` etc. as `person/{id}`), which is why it is large. Ask for it once per sitting.
- **`/vote-results` pages count vote items, not rows.** `limit=10` returned 64 rows holding 10 vote items (1.26 MB, because split and roll-call requests come along); `offset=10&limit=10` returned the other 4. Filter on `had_activity_type` = `PLENARY_VOTE_RESULTS` and stop when fewer than `limit` items come back.
- **HTTP 204 and 404 are this API's "nothing".** No sitting on Saturday 21 November: `/meetings/MTG-PL-2026-11-21` is 404 but `/meetings/MTG-PL-2026-11-21/vote-results` is 204. An unknown adopted text, a filter with no match and a page past the end are 204 with an empty body; `json.loads` on it fails. Check the status first, as the blocks do.
- **A short HTTP 429 can happen far below 500 requests in 5 minutes.** The verifier's cloud browser got 429 (empty body, 0.1 s, `Retry-After` not recorded) on `/adopted-texts/TA-10-2026-0389` and `/adopted-texts/TA-10-2026-9999` at about 00:11 UTC on 26 November after only 3 earlier calls to that end point; a minute later both answered normally. The docs say the limit is per end point "for security reasons" and do not say whether it counts per client. Blocks 1 and 3 retry a 429 once after 30 s; block 2 only inspects and prints the status; block 4 stops (`--fail` under `set -e`).
- **Always send `format=application/ld+json`.** Without it `/vote-results` answered `application/rdf+xml`.
- **Political-group filter values are not the labels.** `political-group=PFE`, `S-D`, `VERTS-ALE`, `THE-LEFT`, `RENEW`, `NI` and `ESN` worked and came back labelled `PfE`, `S&D`, `Verts/ALE`, `The Left`, `Renew`, `NI` and `ESN`; `political-group=PfE` and `S%26D` returned 204. The OpenAPI enum lists `PPE, NI, S-D, VERTS-ALE, ECR, RENEW, THE-LEFT, ID` (no `PFE`, no `ESN`, and `ID` has no current member). Countries are upper case only (`fr` gave 204); Greece is `GR`, as in the enum and the data (21 MEPs). Simplest: fetch all current MEPs once and compare letters only (`S&D` == `S-D`), as the blocks do.
- **Filtered MEP lists are slow.** With curl, `country-of-representation=MT` took 2.3 s and each of 13 calls with a `political-group` filter 6.6-15.6 s (the 204s included); the whole list of 720 took 0.2-1.0 s. In the browser one filtered call was 0.1 s, and the verifier's urllib calls at 00:19-00:20 UTC took 2.9 s (`MT`) and 2.7-6.1 s (9 `political-group` values), so the cost varies, but one unfiltered call was never slower.
- **`/meps/{id}` also returns former members.** `/meps/1` is Georg JARZEMBOWSKI, HTTP 200, with no current membership of `org/ep-10`. Use `show-current` for "current", or check for a membership of `org/ep-10` (classified `EU_INSTITUTION`, no `endDate` for a sitting member) that covers today, as block 3 does.
- **Don't list meetings to find a sitting.** `/meetings?year=2026` starts in January (first row 19 January) and `limit=50` took 36.9 s; build the id from the date and accept a 404.
- **Times are local.** `activity_start_date` carries `+01:00` (CET); only roll-call votes have one.
- **Personal data.** Member records include birthday, e-mail and phone numbers; the API's `User-Agent` parameter text cites Regulation (EU) 2018/1725. The blocks print names, ids, country and group only. The docs suggest a `User-Agent` of the form `{user-id}-{environment}-{version}` (`Project1-prd-1.0.0`); blocks 3 and 4 send `bh-skill-example-prd-1.0.0`.
- **Credit and naming.** Credit "(c) European Union, [year] - Source: European Parliament" (the legal notice's form), name the Open Data Portal and CC BY 4.0, link the item's URL when you reproduce part of it, say what you changed, and do not use the europarl® trademark or the European Parliament logo.
- **Tab marker.** The harness sets the tab title to a horse emoji. Blocks 1 and 2 check `location.href` and page text, not the title.

## What does not work

- **An outcome on the sitting day**: `decision_outcome` is missing in the same-day data (see the first gotcha).
- **English vote labels on the sitting day**: only the `mul` strings.
- **Paging `/decisions`**: offset and limit are ignored.
- **Finding a sitting through `/meetings?year=`**: works, but slow; build `MTG-PL-YYYY-MM-DD`.
- **Not tested:** what a 429 looks like beyond status and empty body (seen twice by the verifier, see Gotchas; the documented limit is 500 requests per 5 minutes per end point), how many days after a sitting the full shape appears, `mandate-date` on `show-current`, `/meps/show-incoming` and `show-outgoing`, `/speeches`, `/plenary-documents`, `/parliamentary-questions`, the `/feed` endpoints, `vote-method` and `filter-output` on `/decisions`, how one MEP voted (the `had_voter_*` lists hold it, not joined here), `text=` and `title=` search on `/adopted-texts`, and sittings before the 10th term.
