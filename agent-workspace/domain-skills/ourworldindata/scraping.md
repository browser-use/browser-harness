# Our World in Data - Compare CO2 Emissions per Person for the US, China and India, with the Source Citation (public chart API, no key)

Field-tested against ourworldindata.org on 2026-11-13 using a fresh Browser Use cloud browser (logged out) plus Python `urllib` and `curl` from a Linux server. 6 browser page loads and 16 in-page `fetch()` calls, 76 curl calls (CSV, metadata, robots files, FAQ, legal page) and 6 urllib calls, all serial at 0.5 s or more spacing: every call was HTTP 200 except the deliberate 301/404 probes below and HTTP 403 `error code: 1010` for Python's default User-Agent (1 urllib call, 5 curl calls, see Gotchas). No 429, no challenge page, no key, no login.

robots.txt (checked 2026-11-13, curl and the cloud browser): https://ourworldindata.org/robots.txt is HTTP 200 `text/plain` with one line, `Sitemap: https://ourworldindata.org/sitemap.xml`, and no `User-agent` groups, so nothing is disallowed for `*`. The same bytes came back for User-Agent `*`, GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, Claude-SearchBot, anthropic-ai, Google-Extended, PerplexityBot, Perplexity-User, CCBot, Bytespider, Applebot-Extended and Meta-ExternalAgent: no named AI-agent groups. https://api.ourworldindata.org/robots.txt (the full-metadata host block 1 calls once) is HTTP 404 for all of them (no rules). Terms: the Grapher Chart API docs (https://docs.owid.io/projects/etl/api/chart-api/) state "Base URL: https://ourworldindata.org" and "License: CC BY 4.0". The FAQ (https://ourworldindata.org/faqs) says "For users who work with automated workflows, computational notebooks, or custom applications, we offer direct URLs to access data in CSV format and comprehensive metadata in JSON format", and "Most of the data on Our World in Data comes from third-party providers ... and is subject to the license terms of those providers. You should always check their license before reusing or republishing the data." The site footer: "Our charts, articles, and data are licensed under CC BY, unless stated otherwise." The legal disclaimer (https://ourworldindata.org/organization#legal-disclaimer) is a warranty and liability disclaimer only. No AI/ML, scraping, automated-access or non-commercial clause. The Grapher software "is not freely licensed for reuse without permission"; this skill reads data files only and does not copy or run Grapher code. Naming: the FAQ allows the name or logo only "as it appears on our charts, articles, and other pages" and says "You are not permitted to use our logo on its own or to imply endorsement", so this skill writes "Our World in Data" in plain text as the source, shows no logo, and is not affiliated with or endorsed by Our World in Data or Global Change Data Lab.

**Attribution:** credit both Our World in Data and the underlying provider. The chart's metadata gives the line to use: `citationShort` = "Global Carbon Budget (2026); Population based on various sources (2024) - with major processing by Our World in Data" (the API writes an en dash), plus the chart URL and CC BY 4.0. The full indicator metadata lists each provider's own licence (Global Carbon Project: CC BY 4.0; population: CC BY 4.0) and a `nonRedistributable` flag (false here). Blocks 1, 3 and 4 print the citation.

## Quick summary

- **No scraping.** `GET https://ourworldindata.org/grapher/co-emissions-per-capita.csv?v=1&csvType=filtered&useColumnShortNames=true&country=USA~CHN~IND&time=latest` returns 4 lines of CSV: `entity,code,year,emissions_total_per_capita`. `GET .../co-emissions-per-capita.metadata.json?v=1&useColumnShortNames=true` returns the title, unit, `citationShort`, `lastUpdated` and a `fullMetadata` link.
- **Answer (2026-11-13, 23:32 UTC):** in **2025**, CO2 emissions per person were **United States 14.50 t, China 8.77 t, India 2.19 t** (World 4.74 t). The US emits 1.65x China and 6.63x India per person; China 4.01x India. Fossil fuels and industry only, territorial, excluding land-use change. Data `lastUpdated` 2026-11-10, `nextUpdate` 2027-11-10.
- **Slugs get renamed.** `co2-emissions-per-capita` answers HTTP 301 to `co-emissions-per-capita` (query kept). `fetch()`, urllib and `curl -L` follow it; the blocks print the final slug and use it for the metadata and the citation URL.
- **Missing countries vanish silently.** An unknown code (`USA~XYZ`) or a country with no value in the latest year (`life-expectancy` with `OWID_USS`) is dropped with HTTP 200. The blocks check that every requested code came back.
- **`csvType=filtered` is required** for `country=` and `time=` to apply; without it you get the whole table (27,238 rows, about 820 KB).
- **Metadata needs `useColumnShortNames=true` too,** or its column key is `Annual CO₂ emissions (per capita)` and does not match the CSV header.
- **Rate limit:** none published (Chart API docs, FAQ). Responses come through Cloudflare (`cf-cache-status` HIT, MISS or DYNAMIC) with `access-control-allow-origin: *`; the 200 CSV and metadata answers send no `cache-control` header (only the 301 of a renamed slug sends `cache-control: public, max-age=86400`). Blocks pace 1 s per call, serial, and wait 30 s once on 429/5xx.

## What works

### 1. US, China and India in the latest year, with the citation (browser)

`on_owid_tab()` opens `/robots.txt` on ourworldindata.org once, so `fetch()` is same-origin (the full-metadata call goes to api.ourworldindata.org, which sends `access-control-allow-origin: *`). `get()` returns the response on HTTP 200 with the expected content type, waits 30 s once on 429/5xx and otherwise raises. The block checks the CSV header, that every code came back, and that the metadata has a citation for that exact column, then prints the providers' licences.

```python
import csv, io, json, time

SLUG = "co-emissions-per-capita"  # old slug co2-emissions-per-capita answers 301 to this one; fetch() follows it
WANT = {"USA": "United States", "CHN": "China", "IND": "India"}  # ISO 3166-1 alpha-3 codes as OWID uses them
CONTEXT = ["OWID_WRL"]  # World, for scale; drop it if you only want the three countries

SITE = "https://ourworldindata.org"
PAUSE = 1.0  # no published rate limit; keep calls serial and spaced

def on_owid_tab():
    """fetch() runs same-origin from a logged-out ourworldindata.org tab (/robots.txt, plain text). Reuse it."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(SITE + "/robots.txt")
    wait_for_load()
    body = js("document.body ? document.body.innerText : ''") or ""
    if js("location.origin") != SITE or "Sitemap:" not in body:
        raise RuntimeError(f"ourworldindata.org did not serve /robots.txt (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__ow = window.__ow || {}; const id = String(Math.random()).slice(2); window.__ow[id] = null;
  fetch(%s, {credentials: 'omit', redirect: 'follow'})
    .then(async r => { window.__ow[id] = {status: r.status, url: r.url, redirected: r.redirected,
                                          type: r.headers.get('content-type'), text: await r.text()}; })
    .catch(e => { window.__ow[id] = {status: 0, url: '', redirected: false, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__ow[%s]; if (v) delete window.__ow[%s]; return v; })()"""

def get(path, kind, timeout=60):
    """GET SITE+path (or an absolute https URL) from inside the tab, following 301s (slugs get renamed). kind is 'csv' or 'json'.
    Unknown slug: HTTP 404 {"status":404,"error":"Not found"}. Waits 30 s once on 429/5xx, raises on anything else."""
    for attempt in range(2):
        rid = json.dumps(js(START_JS % json.dumps(path if path.startswith("https://") else SITE + path)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"{path}: no answer after {timeout}s")
            time.sleep(0.3)
        time.sleep(PAUSE)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(30)
            continue
        if r["status"] != 200 or kind not in (r["type"] or ""):
            raise RuntimeError(f"{path}: HTTP {r['status']} {r['type']} {' '.join(r['text'].split())[:160]!r}; stopping")
        return r

on_owid_tab()

# 1. The latest year for the three countries (plus World). csvType=filtered is what makes country= and time= apply.
codes = list(WANT) + CONTEXT
q = f"v=1&csvType=filtered&useColumnShortNames=true&country={'~'.join(codes)}&time=latest"
r = get(f"/grapher/{SLUG}.csv?{q}", "csv")
final_slug = r["url"].split("/grapher/")[1].split(".csv")[0]
if r["redirected"]:
    print(f"slug {SLUG!r} redirected to {final_slug!r}: use the new one")
rows = list(csv.DictReader(io.StringIO(r["text"])))
head = list(rows[0].keys()) if rows else []
if head[:3] != ["entity", "code", "year"] or len(head) != 4:
    raise RuntimeError(f"unexpected CSV header {head}: re-check the chart (it may have several indicators)")
col = head[3]
got = {x["code"]: x for x in rows}
missing = [c for c in codes if c not in got]
if missing:  # unknown codes and entities without data in the latest year are dropped silently, with HTTP 200
    raise RuntimeError(f"no row for {missing}: check the code, or ask for time=earliest..latest and take each country's last year")
years = {got[c]["year"] for c in WANT}
print(f"{len(rows)} rows, column {col!r}, year(s) {sorted(years)}")

# 2. Title, unit and citation from the same chart's metadata.
m = json.loads(get(f"/grapher/{final_slug}.metadata.json?v=1&useColumnShortNames=true", "json")["text"])  # same key as the CSV column
c = m["columns"].get(col)
if not c or not c.get("citationShort"):
    raise RuntimeError(f"metadata has no citation for column {col!r} (columns: {list(m['columns'])}): stop")
print(f"chart: {m['chart']['title']!r}, unit {c['unit']!r}, timespan {c['timespan']}, "
      f"lastUpdated {c['lastUpdated']}, nextUpdate {c['nextUpdate']}")
print(f"what it counts: {c['descriptionShort']}")

# 3. The comparison.
print()
for code in sorted(codes, key=lambda k: -float(got[k][col])):
    x = got[code]
    print(f"  {x['entity']:<14} {x['code']:<8} {x['year']}  {float(x[col]):6.2f} {c['shortUnit']}")
val = {k: float(got[k][col]) for k in WANT}
ks = sorted(WANT, key=lambda k: -val[k])  # works for any WANT, not just these three
print("\n  " + ", ".join(f"{WANT[a]}/{WANT[b]} {val[a] / val[b]:.2f}x" for i, a in enumerate(ks) for b in ks[i + 1:]))

# 4. Who made the underlying data, and under which licence (the FAQ: respect the providers' licences and cite them).
full = json.loads(get(c["fullMetadata"], "json")["text"])  # api.ourworldindata.org, CORS open
if full.get("nonRedistributable"):
    raise RuntimeError("this indicator is marked nonRedistributable: do not republish the numbers")
print("\nproviders:")
for o in full.get("origins", []):
    lic = o.get("license") or {}
    print(f"  {o['producer']} - {o['title']} (published {o.get('datePublished')}): {lic.get('name')} {lic.get('url')}")

year = years.pop() if len(years) == 1 else "/".join(sorted(years))
print(f"\nanswer: in {year}, CO2 emissions per person were " + ", ".join(f"{WANT[k]} {val[k]:.1f} t" for k in ks)
      + f" ({c['unit']}, fossil fuels and industry, excluding land-use change).")
print(f"  Source: {c['citationShort']}. Our World in Data, \"{m['chart']['title']}\", "
      f"https://ourworldindata.org/grapher/{final_slug} (CC BY 4.0), retrieved {m['dateDownloaded']}.")
```

Output (from the run on 2026-11-13, 23:48 UTC):

```text
4 rows, column 'emissions_total_per_capita', year(s) ['2025']
chart: 'CO₂ emissions per capita', unit 'tonnes per person', timespan 1750-2025, lastUpdated 2026-11-10, nextUpdate 2027-11-10
what it counts: Carbon dioxide (CO₂) emissions from burning fossil fuels and industrial processes. This includes emissions from transport, electricity generation, and heating, but not land-use change.

  United States  USA      2025   14.50 t/person
  China          CHN      2025    8.77 t/person
  World          OWID_WRL 2025    4.74 t/person
  India          IND      2025    2.19 t/person

  United States/China 1.65x, United States/India 6.63x, China/India 4.01x

providers:
  Global Carbon Project - Global Carbon Budget (published 2026-11-10): CC BY 4.0 https://doi.org/10.5281/zenodo.5569234
  Global Carbon Project - Global Carbon Budget (published 2026-11-10): CC BY 4.0 https://www.icos-cp.eu/data-services/about-data-portal/data-license
  Various sources - Population (published 2024-07-15): CC BY 4.0 https://creativecommons.org/licenses/by/4.0/

answer: in 2025, CO2 emissions per person were United States 14.5 t, China 8.8 t, India 2.2 t (tonnes per person, fossil fuels and industry, excluding land-use change).
  Source: Global Carbon Budget (2026); Population based on various sources (2024) – with major processing by Our World in Data. Our World in Data, "CO₂ emissions per capita", https://ourworldindata.org/grapher/co-emissions-per-capita (CC BY 4.0), retrieved 2026-11-13.
```

### 2. robots.txt, the FAQ on reuse, and how the API answers odd requests (browser)

Reads robots.txt and four FAQ answers as the pages show them, then makes 9 small same-origin calls: a renamed slug, an unknown slug, an unknown code, country names, a future year, a year range, a country without the latest year, a call without `csvType`, and metadata without `useColumnShortNames`.

```python
import json, time

SITE = "https://ourworldindata.org"

# robots.txt and the FAQ answers on reuse, as the pages show them.
new_tab(SITE + "/robots.txt")
wait_for_load()
if js("location.origin") != SITE:
    raise RuntimeError(f"not on {SITE} (at {js('location.href')}): stop")
print("robots.txt:", repr(js("document.body.innerText").strip()))

goto_url(SITE + "/faqs")
wait_for_load()
text = " ".join((js("document.body.innerText") or "").split())
if "Do you have an API?" not in text:
    raise RuntimeError(f"the FAQ page did not load (at {js('location.href')}): stop")
for q in ("For users who work with automated workflows",
          "Most of the data on Our World in Data comes from third-party providers",
          "You are only permitted to use the Our World in Data name or logo",
          "However, the Grapher is not freely licensed"):
    i = text.find(q)
    if i < 0:
        raise RuntimeError(f"FAQ changed, {q!r} not found: re-read {SITE}/faqs before relying on this skill")
    print(f"\nfaq: {text[i:i + 260]}")

# Same-origin probes, same tab. No retries: this block only inspects answers.
goto_url(SITE + "/robots.txt")
wait_for_load()
START_JS = """(() => { window.__ow = window.__ow || {}; const id = String(Math.random()).slice(2); window.__ow[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__ow[id] = {status: r.status, url: r.url, redirected: r.redirected,
                                          type: r.headers.get('content-type'), text: await r.text()}; })
    .catch(e => { window.__ow[id] = {status: 0, url: '', redirected: false, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__ow[%s]; if (v) delete window.__ow[%s]; return v; })()"""

def raw(path, timeout=60):
    rid = json.dumps(js(START_JS % json.dumps(SITE + path)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > timeout:
            raise RuntimeError(f"{path}: no answer after {timeout}s")
        time.sleep(0.3)
    time.sleep(1.0)
    return r

F = "v=1&csvType=filtered&useColumnShortNames=true"
print()
for path in (f"/grapher/co2-emissions-per-capita.csv?{F}&country=USA~CHN~IND&time=latest",   # renamed slug: 301
             f"/grapher/no-such-chart-xyz.csv?{F}&country=USA&time=latest",                  # unknown slug
             f"/grapher/co-emissions-per-capita.csv?{F}&country=USA~XYZ&time=latest",         # unknown code: dropped
             f"/grapher/co-emissions-per-capita.csv?{F}&country=United%20States~China&time=latest",  # names work too
             f"/grapher/co-emissions-per-capita.csv?{F}&country=USA&time=2099",               # future year: clamped
             f"/grapher/co-emissions-per-capita.csv?{F}&country=USA&time=2023..latest",
             f"/grapher/life-expectancy.csv?{F}&country=JPN~OWID_USS&time=latest",            # USSR ends 1913: dropped
             "/grapher/co-emissions-per-capita.csv?v=1&country=USA&time=latest"):            # no csvType: whole table
    r = raw(path)
    lines = r["text"].strip().split("\n")
    where = f" -> {r['url'].split('.org')[1].split('?')[0]}" if r["redirected"] else ""
    print(f"{path}\n  HTTP {r['status']} {r['type']}{where}, {len(lines)} lines: {' | '.join(lines[:3])[:150]}")

r = raw("/grapher/co-emissions-per-capita.metadata.json?v=1")
print(f"\nmetadata without useColumnShortNames: columns {list(json.loads(r['text'])['columns'])}")
```

Output (from the run on 2026-11-13, 23:32 UTC):

```text
robots.txt: 'Sitemap: https://ourworldindata.org/sitemap.xml'

faq: For users who work with automated workflows, computational notebooks, or custom applications, we offer direct URLs to access data in CSV format and comprehensive metadata in JSON format. You can fetch the complete data or only the subset of the data currently 

faq: Most of the data on Our World in Data comes from third-party providers (such as the WHO, UN, and World Bank) and is subject to the license terms of those providers. You should always check their license before reusing or republishing the data. Our work would n

faq: You are only permitted to use the Our World in Data name or logo as it appears on our charts, articles, and other pages. You have this permission only as long as your use of the material we make available is in accordance with the license terms and follows the

faq: However, the Grapher is not freely licensed for reuse without permission. If you'd like to copy, modify, distribute, or use any part of the Grapher codebase in your own project, product, or service, you'll need to first request written permission from Global C

/grapher/co2-emissions-per-capita.csv?v=1&csvType=filtered&useColumnShortNames=true&country=USA~CHN~IND&time=latest
  HTTP 200 text/csv -> /grapher/co-emissions-per-capita.csv, 4 lines: entity,code,year,emissions_total_per_capita | China,CHN,2025,8.768821 | India,IND,2025,2.1883202
/grapher/no-such-chart-xyz.csv?v=1&csvType=filtered&useColumnShortNames=true&country=USA&time=latest
  HTTP 404 application/json; charset=utf-8, 1 lines: {"status":404,"error":"Not found"}
/grapher/co-emissions-per-capita.csv?v=1&csvType=filtered&useColumnShortNames=true&country=USA~XYZ&time=latest
  HTTP 200 text/csv, 2 lines: entity,code,year,emissions_total_per_capita | United States,USA,2025,14.500179
/grapher/co-emissions-per-capita.csv?v=1&csvType=filtered&useColumnShortNames=true&country=United%20States~China&time=latest
  HTTP 200 text/csv, 3 lines: entity,code,year,emissions_total_per_capita | China,CHN,2025,8.768821 | United States,USA,2025,14.500179
/grapher/co-emissions-per-capita.csv?v=1&csvType=filtered&useColumnShortNames=true&country=USA&time=2099
  HTTP 200 text/csv, 2 lines: entity,code,year,emissions_total_per_capita | United States,USA,2025,14.500179
/grapher/co-emissions-per-capita.csv?v=1&csvType=filtered&useColumnShortNames=true&country=USA&time=2023..latest
  HTTP 200 text/csv, 4 lines: entity,code,year,emissions_total_per_capita | United States,USA,2023,14.335961 | United States,USA,2024,14.21929
/grapher/life-expectancy.csv?v=1&csvType=filtered&useColumnShortNames=true&country=JPN~OWID_USS&time=latest
  HTTP 200 text/csv, 2 lines: entity,code,year,life_expectancy_0 | Japan,JPN,2023,84.7123
/grapher/co-emissions-per-capita.csv?v=1&country=USA&time=latest
  HTTP 200 text/csv, 27239 lines: Entity,Code,Year,CO₂ emissions per capita | Afghanistan,AFG,1949,0.0019921463 | Afghanistan,AFG,1950,0.010366015

metadata without useColumnShortNames: columns ['Annual CO₂ emissions (per capita)']
```

### 3. Same answer with Python urllib (no browser)

Sends its own User-Agent: Cloudflare answers HTTP 403 `error code: 1010` to Python's default `Python-urllib/3.x` (see Gotchas).

```python
import csv, io, json, sys, time, urllib.error, urllib.parse, urllib.request

SLUG, CODES = "co-emissions-per-capita", ["USA", "CHN", "IND"]
BASE = "https://ourworldindata.org/grapher/"
# Cloudflare answers HTTP 403 "error code: 1010" to Python's default User-Agent (Python-urllib/3.x) unless the
# response is already cached. Name your client honestly; do not pretend to be a browser.
UA = {"User-Agent": "co2-compare-script/1.0 (+https://example.org/contact)"}

def get(url):
    """GET -> (final URL, body text). urllib follows the 301 of a renamed slug. Waits 30 s once on 429/5xx."""
    for attempt in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                out = r.geturl(), r.read().decode("utf-8")
            time.sleep(1)  # no published limit; stay serial
            return out
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(30)
                continue
            sys.exit(f"{url}: HTTP {e.code} {e.read().decode()[:160]}")  # unknown slug: 404; blocked UA: 403 "error code: 1010"

q = urllib.parse.urlencode({"v": 1, "csvType": "filtered", "useColumnShortNames": "true",
                            "country": "~".join(CODES), "time": "latest"}, safe="~")
final, text = get(f"{BASE}{SLUG}.csv?{q}")
slug = final.split("/grapher/")[1].split(".csv")[0]
rows = {r["code"]: r for r in csv.DictReader(io.StringIO(text))}
if sorted(rows) != sorted(CODES):  # unknown codes and countries without the latest year vanish with HTTP 200
    sys.exit(f"got {sorted(rows)}, wanted {sorted(CODES)}: stop")
col = [k for k in next(iter(rows.values())) if k not in ("entity", "code", "year")]
if len(col) != 1:
    sys.exit(f"expected one value column, got {col}")
col = col[0]
meta = json.loads(get(f"{BASE}{slug}.metadata.json?v=1&useColumnShortNames=true")[1])
c = meta["columns"][col]
for code in CODES:
    r = rows[code]
    print(f"{r['entity']:<14} {r['year']}  {float(r[col]):5.2f} {c['shortUnit']}")
print(f"Source: {c['citationShort']}. Our World in Data, https://ourworldindata.org/grapher/{slug} (CC BY 4.0), "
      f"data updated {c['lastUpdated']}.")
```

Output (from the run on 2026-11-13, 23:33 UTC; with `SLUG = "co2-emissions-per-capita"` the output was identical, urllib followed the 301):

```text
United States  2025  14.50 t/person
China          2025   8.77 t/person
India          2025   2.19 t/person
Source: Global Carbon Budget (2026); Population based on various sources (2024) – with major processing by Our World in Data. Our World in Data, https://ourworldindata.org/grapher/co-emissions-per-capita (CC BY 4.0), data updated 2026-11-10.
```

### 4. curl

```bash
B=https://ourworldindata.org/grapher
Q='v=1&csvType=filtered&useColumnShortNames=true&country=USA~CHN~IND&time=latest'
curl -sS --fail -L "$B/co-emissions-per-capita.csv?$Q"; echo   # the CSV has no trailing newline
sleep 1
curl -sS --fail -L "$B/co-emissions-per-capita.metadata.json?v=1&useColumnShortNames=true" | python3 -c '
import json, sys
c = json.load(sys.stdin)["columns"]["emissions_total_per_capita"]
print(c["unit"], "| updated", c["lastUpdated"], "| Source:", c["citationShort"])
'
sleep 1
curl -sS -o /dev/null -w 'old slug: HTTP %{http_code} -> %{redirect_url}\n' "$B/co2-emissions-per-capita.csv?$Q"
```

Output (from the run on 2026-11-13, 23:33 UTC):

```text
entity,code,year,emissions_total_per_capita
China,CHN,2025,8.768821
India,IND,2025,2.1883202
United States,USA,2025,14.500179
tonnes per person | updated 2026-11-10 | Source: Global Carbon Budget (2026); Population based on various sources (2024) – with major processing by Our World in Data
old slug: HTTP 301 -> https://ourworldindata.org/grapher/co-emissions-per-capita.csv?v=1&csvType=filtered&useColumnShortNames=true&country=USA%7ECHN%7EIND&time=latest
```

## Fields

| Field | Where | Notes |
|---|---|---|
| `entity`, `code` | CSV | `United States`, `USA`; codes are ISO 3166-1 alpha-3, aggregates use `OWID_` codes (`OWID_WRL` = World) |
| `year` | CSV | integer; `time=latest` gives the chart's latest year (2025 here) |
| `emissions_total_per_capita` | CSV | tonnes of CO2 per person; full float (`14.500179`), round yourself |
| `chart.title`, `chart.citation`, `chart.originalChartUrl` | metadata | `CO₂ emissions per capita` (subscript 2); `citation` lacks the "with major processing" part |
| `columns.<col>.unit`, `shortUnit` | metadata | `tonnes per person`, `t/person` |
| `columns.<col>.citationShort`, `citationLong` | metadata | the line to cite; `citationLong` adds the dataset titles |
| `columns.<col>.descriptionShort`, `descriptionKey`, `descriptionProcessing` | metadata | what is counted (fossil + industry, territorial, no land use, no international aviation/shipping per country) |
| `columns.<col>.lastUpdated`, `nextUpdate`, `timespan` | metadata | `2026-11-10`, `2027-11-10`, `1750-2025` |
| `columns.<col>.fullMetadata` | metadata | `https://api.ourworldindata.org/v1/indicators/1356786.metadata.json` |
| `origins[].producer`, `title`, `license{name,url}`, `datePublished`, `citationFull` | full metadata | provider and its licence; cite `citationFull` for academic use |
| `nonRedistributable` | full metadata | `false` here; if `true`, do not republish the values |
| `dateDownloaded` | metadata | the day of your request (UTC) |

## Gotchas

- **Silent drops, not errors.** `country=USA~XYZ` returns only the USA row; `country=XYZ` returns a bare header `entity,year,emissions_total_per_capita` (no `code` column). Always compare the codes you got with the codes you asked for.
- **`time=latest` is the chart's latest year, not each country's.** A country without a value in that year is dropped (Japan 2023 came back, the USSR, last value 1913, did not). For "each country's most recent value" ask `time=earliest..latest` and take the last row per code. `time=2099` silently returned 2025.
- **Country names work too.** `country=United%20States~China` matched; a leading `~` (`~USA~CHN~IND`, as in the docs examples) gives the same rows. Codes are safer than names.
- **Python's default User-Agent is blocked.** `Python-urllib/3.12` got HTTP 403 `error code: 1010` on uncached requests (both metadata files, CSVs with a new query) and HTTP 200 only on Cloudflare cache hits (`cf-cache-status: HIT`, for example the USA~CHN~IND CSV); `curl/8.5.0`, `python-requests/2.32.3` and a named script UA got HTTP 200. Name your client honestly; do not pretend to be a browser.
- **Rows are sorted by entity name**, not in the order you asked.
- **The CSV has no trailing newline** (block 4 adds `echo`). Values are full floats; the chart shows 3 significant figures (`display.numSignificantFigures: 3` in the full metadata), so round yourself.
- **Per capita here is fossil and industry CO2 only.** It excludes land-use change and international aviation and shipping (in `descriptionKey`). Other charts (consumption-based, including land use, all greenhouse gases) give different numbers; name the measure when you answer.
- **Annual data, updated yearly.** The 2025 values arrived with the 2026-11-10 Global Carbon Budget release; `nextUpdate` is 2027-11-10. Quote the year from the CSV, not "this year".
- **Do not add `nocache`.** The docs list it as a cache bypass; Cloudflare's cached answer (`cf-cache-status: HIT`) is fine for annual data and lighter on the site.
- **Tab marker.** The harness prefixes the tab title with a horse emoji; the blocks check `location.origin` and page text, not the title.

## What does not work

- **Old slugs without redirect handling:** `curl` without `-L` gets HTTP 301, `content-length: 0` and a relative `location`.
- **Unknown slugs:** HTTP 404 `application/json` `{"status":404,"error":"Not found"}` for both `.csv` and `.metadata.json`. Find the current slug on the chart page URL.
- **Using the Grapher code or the logo:** not covered by CC BY (see the access-policy line). This skill only reads CSV and JSON.
- **Not tested:** charts with several indicators (more than one value column; block 1 stops on them), `.zip`, `.config.json`, `.values.json` and `.search-result.json` endpoints, the Tables, Indicators and Search APIs, `time=earliest..latest` per-country fallback beyond the single probe, rate-limit behaviour (never provoked).
