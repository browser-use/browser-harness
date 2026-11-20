# CISA Known Exploited Vulnerabilities (KEV) catalog (cisa.gov) - List Vulnerabilities Added in the Last N Days or for One Vendor, With Due Date, Required Action and Ransomware Use (JSON feed, no key)

Field-tested against www.cisa.gov on 2026-11-19 (US Pacific afternoon; 23:32-23:42 UTC) using fresh Browser Use cloud browsers (logged out; two sessions, 23:34-23:36 and 23:39 UTC) plus Python `urllib` and `curl` from a Linux machine. 9 browser page loads (the KEV license 4 times, once as a return page; the catalog page and the "Reducing the Significant Risk" page 2 times each; robots.txt once) and 11 in-page `fetch()` calls (10 to www.cisa.gov, 1 to the GitHub mirror), 57 curl calls and 19 urllib calls to www.cisa.gov (plus 7 curl calls to raw.githubusercontent.com and 1 to api.github.com for the mirror), all serial (1 s apart in the blocks below). The catalog feed answered HTTP 200 every time (1,863,915 bytes, or 204,849 with gzip, in 0.09-0.26 s) except the deliberate HTTP 304 conditional GETs. curl got HTTP 403 (an Akamai "Access Denied" page) for robots.txt, the license, the catalog page and `feeds/known_exploited_vulnerabilities.csv` with every User-Agent tried and with HTTP/1.1 or HTTP/2, while urllib and the cloud browser got HTTP 200 for the first three. No 429, no challenge, no key, no login. Block 1 ran three times (the third in a new cloud browser at 23:39 UTC, which opened the license page first); the output below is that run. An independent verifier re-ran all four blocks at 23:42-23:47 UTC in a separate cloud browser with the same results; blocks 2 and 4 show its re-run after one URL fix.

robots.txt (checked 2026-11-19 in the cloud browser and with `urllib.robotparser`; curl gets HTTP 403): https://www.cisa.gov/robots.txt is the Drupal default file with one `User-agent: *` group (57 rules: `/core/`, `/profiles/`, README files, `/admin/`, `/search/`, `/search?`, `/user/login` and the like) and one `User-agent: PetalBot` group (`Disallow: /`). There are no named AI-agent groups, so GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider fall under `*`, and no rule matches `/sites/default/files/feeds/` or `/sites/default/files/csv/`: the feed is allowed for all 11 agents (block 3). Terms: the KEV license https://www.cisa.gov/sites/default/files/licenses/kev/license.txt, linked as "License" on the catalog page, says "The KEV database is distributed under the Creative Commons 0 1.0 License. You may use this data in any legal manner but note that information provided at any 3rd party links included in the KEV database are bound by the policies and licenses of those 3rd party websites. Use of the information does not authorize you to use the CISA Logo or DHS Seal, nor should such use be interpreted as an endorsement by CISA or DHS." The CC0 1.0 text that follows waives rights "for any purpose whatsoever, including without limitation commercial". The GitHub mirror's README (https://github.com/cisagov/kev-data) says its CC0 license "is identical to the licensing found at" that URL. No AI/ML, scraping, automated-access or non-commercial clause on any of these pages. Naming: this skill says "CISA Known Exploited Vulnerabilities (KEV) catalog" in plain text with a source line, uses no CISA logo or DHS seal, and is not endorsed by CISA or DHS.

**A list of exploited vulnerabilities, with a federal deadline.** The "Reducing the Significant Risk of Known Exploited Vulnerabilities" page https://www.cisa.gov/known-exploited-vulnerabilities says federal civilian executive branch (FCEB) agencies "are required to remediate vulnerabilities in the KEV catalog within prescribed timeframes under BOD 26-04", and "Although not bound by BOD 26-04, every organization ... can significantly strengthen their security and resilience posture by prioritizing the remediation of the vulnerabilities listed in the KEV catalog as well." An entry needs a CVE ID, active exploitation and "a clear remediation action". `dueDate` is that federal deadline, not a deadline for your company. Match your inventory against `vendorProject` and `product` on your side: never send hostnames or asset lists anywhere, this feed takes no query.

## Quick summary

- **No scraping.** `GET https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json` -> one JSON file `{"title":"CISA Catalog of Known Exploited Vulnerabilities","catalogVersion":"2026.11.18","dateReleased":"2026-11-18T19:17:41.0354Z","count":1786,"vulnerabilities":[{"cveID","vendorProject","product","vulnerabilityName","dateAdded","shortDescription","requiredAction","dueDate","knownRansomwareCampaignUse","forensicTriage","notes","cwes"},...]}`. No key, no registration. The CSV is at https://www.cisa.gov/sites/default/files/csv/known_exploited_vulnerabilities.csv (a different folder) and the schema at `.../feeds/known_exploited_vulnerabilities_schema.json`.
- **There is no server-side query.** `?vendor=Fortinet` returned the same 1,863,915 bytes. Download the whole file (about 205 KB with `Accept-Encoding: gzip`) and filter on `dateAdded`, `vendorProject`, `product`, `dueDate` and `knownRansomwareCampaignUse` yourself.
- **Answer (run 2026-11-19, 23:39 UTC, catalog 2026.11.18):** 18 entries were added in the last 14 days (`dateAdded` 2026-11-05 to 2026-11-18), none with ransomware use "Known"; the newest are CVE-2026-90436 (Apache Axis) and CVE-2026-90817 (REDCap), CVE-2026-40217 (LiteLLM) and CVE-2024-10441 (Synology DSM), all added 2026-11-18, three due 2026-11-21. Fortinet has **32 entries, 14 with ransomware use "Known"**, the newest CVE-2025-61624 (Multiple Products, added 2026-10-16, due 2026-10-19); FortiOS alone has 15, 12 "Known".
- **`knownRansomwareCampaignUse` is "Known" or "Unknown"** (361 and 1,425 of 1,786). The schema: "'Unknown' if CISA lacks confirmation", so "Unknown" is not "no".
- **Silent failures:** a wrong query string is ignored (full file, HTTP 200); `feeds/known_exploited_vulnerabilities.csv` does not exist (HTTP 404 in a browser, 403 to curl); `If-None-Match` with the ETag still sends the full 1.86 MB. Use `If-Modified-Since` (HTTP 304, 0 bytes), check `count` against the rows, and check the required fields (blocks 1 and 3).
- **Rate limit:** none is published on the license, catalog, "Reducing the Significant Risk" or mirror README pages. The file changes when CISA adds or updates entries ("typically ... weekdays during normal US Eastern business hours", mirror README); `Cache-Control: max-age` on the JSON was 434-2947 s and counts down between requests (941, 694, 503, 434 from 23:39 to 23:47 UTC; 2947 at 00:53 UTC on 2026-11-20). The blocks make one download per run and a conditional GET after that; block 3 waits `Retry-After` once on 429/5xx (default 60 s) and stops above 120 s; block 4 uses curl's `--retry 1`. Poll at most hourly.

## What works

### 1. Last N days and one vendor -> due date, required action, ransomware use (browser)

`on_cisa_tab()` opens the logged-out KEV license page so `fetch()` runs same-origin on www.cisa.gov. `catalog()` downloads the whole feed once, checks `count` against the rows and the schema's required fields, and retries once after 60 s on a network error or 5xx. The rows are filtered and sorted in Python. Each distinct `requiredAction` text gets a letter so the table stays readable. 1 `fetch()` call.

```python
import json, time
from datetime import date, datetime, timedelta, timezone

DAYS = 14             # "added in the last N days" (dateAdded on or after today minus N, UTC)
VENDOR = "Fortinet"   # matched against vendorProject, case-insensitive; "" for every vendor
SHOW = 8              # newest rows to print for the vendor

SITE = "https://www.cisa.gov"
FEED = SITE + "/sites/default/files/feeds/known_exploited_vulnerabilities.json"
LICENSE = SITE + "/sites/default/files/licenses/kev/license.txt"
REQUIRED = ["cveID", "vendorProject", "product", "vulnerabilityName", "dateAdded", "shortDescription",
            "requiredAction", "dueDate"]  # the schema's required list; the other fields can be absent
KNOWN = set(REQUIRED) | {"knownRansomwareCampaignUse", "forensicTriage", "notes", "cwes"}

def on_cisa_tab():
    """A small logged-out www.cisa.gov page (the KEV license) so fetch() runs same-origin."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(LICENSE)
    wait_for_load()
    txt = js("document.body ? document.body.innerText : ''") or ""
    if js("location.origin") != SITE or "Creative Commons 0 1.0" not in txt:
        raise RuntimeError(f"www.cisa.gov did not serve the KEV license (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit', cache: 'no-store'})
    .then(async r => { const h = {}; r.headers.forEach((v, k) => { h[k] = v; });
      window.__u[id] = {status: r.status, headers: h, text: await r.text()}; })
    .catch(e => { window.__u[id] = {status: 0, headers: {}, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

def fetch(url):
    """One in-page GET -> {status, headers, text}."""
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 90:
            raise RuntimeError(f"{url}: no answer after 90s")
        time.sleep(0.3)
    return r

def catalog():
    """-> (header dict, list of rows). Retries once after 60 s on a network error or 5xx; raises on anything else
    and on a body that is not the catalog (count must equal the number of rows)."""
    for attempt in range(2):
        r = fetch(FEED)
        if (r["status"] == 0 or r["status"] >= 500) and attempt == 0:
            time.sleep(60)
            continue
        break
    if r["status"] != 200 or "json" not in r["headers"].get("content-type", ""):
        raise RuntimeError(f"{FEED}: HTTP {r['status']} {' '.join(r['text'].split())[:200]!r}; stopping")
    body = json.loads(r["text"])
    rows = body.get("vulnerabilities")
    if not isinstance(rows, list) or body.get("count") != len(rows) or not body.get("catalogVersion"):
        raise RuntimeError(f"not the KEV catalog: count {body.get('count')}, rows {type(rows).__name__}; stopping")
    bad = [v.get("cveID", "?") for v in rows if any(not v.get(k) for k in REQUIRED)]
    if bad:
        raise RuntimeError(f"{len(bad)} rows miss a required field, e.g. {bad[:3]}: the schema changed, stop")
    hdr = {k: body[k] for k in body if k != "vulnerabilities"} | {"bytes": len(r["text"]),
                                                                  "last-modified": r["headers"].get("last-modified")}
    return hdr, rows

def due(v, today):
    d = (date.fromisoformat(v["dueDate"]) - today).days
    return f"overdue {-d} d" if d < 0 else ("due today" if d == 0 else f"in {d} d")

def table(rows, today, actions):
    print(f"  {'added':<10} {'due':<10} {'':<14} {'CVE':<16} {'vendor / product':<44} {'ransomware':<10} {'triage':<6} action")
    for v in rows:
        a = actions.setdefault(v["requiredAction"], chr(ord("A") + len(actions)))
        vp = f"{v['vendorProject']} / {v['product']}"
        print(f"  {v['dateAdded']:<10} {v['dueDate']:<10} {due(v, today):<14} {v['cveID']:<16} {vp[:44]:<44} "
              f"{v.get('knownRansomwareCampaignUse', '-'):<10} {v.get('forensicTriage', '-'):<6} {a}")

on_cisa_tab()
now = datetime.now(timezone.utc)
today = now.date()
hdr, rows = catalog()
newest = lambda v: (v["dateAdded"], [int(x) for x in v["cveID"].split("-")[1:]])  # CVE numbers, not text
extra = sorted({k for v in rows for k in v} - KNOWN)
print(f"CISA KEV catalog {hdr['catalogVersion']}, released {hdr['dateReleased']}, {hdr['count']} entries, "
      f"{hdr['bytes']:,} bytes, read {now:%Y-%m-%d %H:%M} UTC")
print(f"fields not in this skill's list (new since 2026-11-19?): {', '.join(extra) or 'none'}")

actions = {}
since = (today - timedelta(days=DAYS)).isoformat()
recent = sorted((v for v in rows if v["dateAdded"] >= since), key=newest, reverse=True)
print(f"\nAdded in the last {DAYS} days (dateAdded >= {since}): {len(recent)}, "
      f"ransomware 'Known' {sum(v.get('knownRansomwareCampaignUse') == 'Known' for v in recent)}")
table(recent, today, actions)

if VENDOR:
    names = sorted({v["vendorProject"] for v in rows})
    exact = [n for n in names if n.casefold() == VENDOR.casefold()]
    mine = sorted((v for v in rows if v["vendorProject"] in exact), key=newest, reverse=True)
    known = [v for v in mine if v.get("knownRansomwareCampaignUse") == "Known"]
    print(f"\nvendorProject = {VENDOR!r}: {len(mine)} entries, first added {mine[-1]['dateAdded'] if mine else '-'}, "
          f"ransomware 'Known' {len(known)}, forensic triage 'Yes' {sum(v.get('forensicTriage') == 'Yes' for v in mine)}"
          f"; newest {min(SHOW, len(mine))}:")
    table(mine[:SHOW], today, actions)
    if not mine:
        near = [n for n in names if VENDOR.casefold() in n.casefold() or n.casefold() in VENDOR.casefold()]
        print(f"  no vendorProject equals {VENDOR!r}; names containing it: {near or 'none'} (also try product)")

print("\ndueDate is the deadline for US federal civilian (FCEB) agencies under BOD 26-04; required action:")
for text, a in actions.items():
    print(f"  {a}: {text}")
print(f"\nSource: CISA Known Exploited Vulnerabilities (KEV) catalog, {FEED}, version {hdr['catalogVersion']}, "
      f"accessed {now:%d %B %Y %H:%M} UTC. CC0 1.0; not endorsed by CISA or DHS.")
```

Output (from the run on 2026-11-19, 23:39 UTC, in a new cloud browser):

```text
CISA KEV catalog 2026.11.18, released 2026-11-18T19:17:41.0354Z, 1786 entries, 1,863,915 bytes, read 2026-11-19 23:39 UTC
fields not in this skill's list (new since 2026-11-19?): none

Added in the last 14 days (dateAdded >= 2026-11-05): 18, ransomware 'Known' 0
  added      due                       CVE              vendor / product                             ransomware triage action
  2026-11-18 2026-11-21 in 2 d         CVE-2026-90817   Vanderbilt University / Research Electronic  Unknown    Yes    A
  2026-11-18 2026-11-21 in 2 d         CVE-2026-90436   Apache / Axis                                Unknown    Yes    A
  2026-11-18 2026-12-02 in 13 d        CVE-2026-40217   BerriAI / LiteLLM                            Unknown    No     A
  2026-11-18 2026-11-21 in 2 d         CVE-2024-10441   Synology / DiskStation Manager (DSM)         Unknown    Yes    A
  2026-11-17 2026-12-01 in 12 d        CVE-2026-115731  Perforce / Puppet Enterprise                 Unknown    No     A
  2026-11-13 2026-11-16 overdue 3 d    CVE-2026-123039  Check Point / Multiple Products              Unknown    Yes    A
  2026-11-13 2026-11-16 overdue 3 d    CVE-2026-114713  UnrealIRCd / UnrealIRCd                      Unknown    Yes    A
  2026-11-10 2026-11-24 in 5 d         CVE-2026-125350  Google / Chromium                            Unknown    No     A
  2026-11-10 2026-11-24 in 5 d         CVE-2026-124194  Microsoft / Office                           Unknown    No     A
  2026-11-10 2026-11-13 overdue 6 d    CVE-2026-116606  Barracuda Networks / Barracuda Email Securit Unknown    Yes    A
  2026-11-10 2026-11-24 in 5 d         CVE-2026-111793  Openwave Messaging Limited / Webtop Media Tr Unknown    No     A
  2026-11-10 2026-11-13 overdue 6 d    CVE-2026-111560  Barracuda Networks / Multiple Products       Unknown    Yes    A
  2026-11-10 2026-11-24 in 5 d         CVE-2026-20320   Cisco / BroadWorks                           Unknown    No     A
  2026-11-09 2026-11-12 overdue 7 d    CVE-2026-123218  IBM / Aspera Faspex                          Unknown    Yes    A
  2026-11-09 2026-11-12 overdue 7 d    CVE-2026-123158  OpenBSD / OpenSSH                            Unknown    Yes    A
  2026-11-09 2026-11-12 overdue 7 d    CVE-2026-116779  SignalWire / FreeSwitch                      Unknown    Yes    A
  2026-11-09 2026-11-12 overdue 7 d    CVE-2026-102895  GPUStack / GPUStack                          Unknown    Yes    A
  2026-11-06 2026-11-20 in 1 d         CVE-2026-19868   SonicWall / SonicOS SSLVPN                   Unknown    No     A

vendorProject = 'Fortinet': 32 entries, first added 2021-11-03, ransomware 'Known' 14, forensic triage 'Yes' 5; newest 8:
  added      due                       CVE              vendor / product                             ransomware triage action
  2026-10-16 2026-10-19 overdue 31 d   CVE-2025-61624   Fortinet / Multiple Products                 Unknown    Yes    A
  2026-10-01 2026-10-04 overdue 46 d   CVE-2026-104286  Fortinet / FortiMail                         Unknown    Yes    A
  2026-09-09 2026-09-12 overdue 68 d   CVE-2025-25249   Fortinet / Multiple Products                 Unknown    Yes    A
  2026-07-27 2026-08-10 overdue 101 d  CVE-2025-68686   Fortinet / FortiOS                           Unknown    No     A
  2026-07-16 2026-07-19 overdue 123 d  CVE-2026-39808   Fortinet / FortiSandbox                      Unknown    Yes    A
  2026-07-16 2026-07-19 overdue 123 d  CVE-2026-25089   Fortinet / FortiSandbox                      Unknown    Yes    A
  2026-04-13 2026-04-16 overdue 217 d  CVE-2026-21643   Fortinet / FortiClient EMS                   Unknown    No     B
  2026-04-06 2026-04-09 overdue 224 d  CVE-2026-35616   Fortinet / FortiClient EMS                   Unknown    No     B

dueDate is the deadline for US federal civilian (FCEB) agencies under BOD 26-04; required action:
  A: Apply mitigations in accordance with vendor instructions, ensuring compliance with CISA’s BOD 26-04 Prioritizing Security Updates Based on Risk (see URL in Notes) guidance and CISA’s “Forensics Triage Requirements” (see URL in Notes). Follow applicable BOD 26-04 guidance for cloud services or discontinue use of the product if mitigations are unavailable. Stakeholders are responsible for evaluating each asset's internet exposure and ensuring adherence to BOD 26-04 patching guidelines.
  B: Apply mitigations per vendor instructions, follow applicable BOD 22-01 guidance for cloud services, or discontinue use of the product if mitigations are unavailable.

Source: CISA Known Exploited Vulnerabilities (KEV) catalog, https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json, version 2026.11.18, accessed 19 November 2026 23:39 UTC. CC0 1.0; not endorsed by CISA or DHS.
```

### 2. robots.txt, the license, the catalog page and URL mistakes (browser)

5 page loads and 8 in-page `fetch()` calls in the same tab. Saves robots.txt to `~/.cache/cisa-kev-skill/` for block 3 in case your client gets HTTP 403.

```python
import json, os, time

SITE = "https://www.cisa.gov"
FEED = SITE + "/sites/default/files/feeds/known_exploited_vulnerabilities.json"
CACHE = os.path.expanduser("~/.cache/cisa-kev-skill")  # block 3 reads the robots.txt saved here

START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, Object.assign({credentials: 'omit', cache: 'no-store'}, %s))
    .then(async r => { const h = {}; r.headers.forEach((v, k) => { h[k] = v; });
      const t = await r.text(); window.__u[id] = {status: r.status, headers: h, size: t.length, head: t.slice(0, 160)}; })
    .catch(e => { window.__u[id] = {status: 0, headers: {}, size: 0, head: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

def raw(url, **opts):
    """One in-page GET -> {status, headers, size, head}. No retries: this block only inspects answers."""
    rid = json.dumps(js(START_JS % (json.dumps(url), json.dumps(opts))))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 90:
            raise RuntimeError(f"{url}: no answer after 90s")
        time.sleep(0.3)
    time.sleep(1)
    return r

def page(url):
    goto_url(url)
    wait_for_load()
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    return st, js("document.body ? document.body.innerText : (document.documentElement.textContent || '')") or ""

st, txt = page(SITE + "/robots.txt")
groups, cur = {}, None
for line in txt.splitlines():
    k, _, v = line.split("#")[0].partition(":")
    k, v = k.strip().lower(), v.strip()
    if k == "user-agent":
        cur = groups.setdefault(v, [])
    elif k in ("allow", "disallow") and cur is not None:
        cur.append(f"{k} {v}")
print(f"www.cisa.gov robots.txt HTTP {st}: groups {list(groups)}; '*' has {len(groups.get('*', []))} rules, "
      f"e.g. {[r for r in groups.get('*', []) if 'search' in r][:2]}; PetalBot {groups.get('PetalBot')}")
feeds_rules = [r for r in groups.get("*", []) if r.split(" ", 1)[1] and FEED[len(SITE):].startswith(r.split(" ", 1)[1].rstrip("*$"))]
print(f"'*' rules matching /sites/default/files/feeds/...: {feeds_rules or 'none'}")
if st == 200 and txt.lstrip().startswith("#"):
    os.makedirs(CACHE, exist_ok=True)
    open(os.path.join(CACHE, "robots.txt"), "w").write(txt)
    print(f"saved robots.txt ({len(txt)} chars) to ~/.cache/cisa-kev-skill/robots.txt for block 3")

for url, needles in (
    (SITE + "/sites/default/files/licenses/kev/license.txt",
     ["distributed under the Creative Commons 0 1.0 License", "You may use this data in any legal manner",
      "does not authorize you to use the CISA Logo or DHS Seal", "nor should such use be interpreted as an endorsement"]),
    (SITE + "/known-exploited-vulnerabilities-catalog",
     ["The KEV catalog is also available in these formats", "Known To Be Used in Ransomware Campaigns?",
      "Forensic triage required per BOD 26-04"]),
    (SITE + "/known-exploited-vulnerabilities",
     ["required to remediate vulnerabilities in the KEV catalog within prescribed timeframes under BOD 26-04",
      "Although not bound by BOD 26-04", "There is a clear remediation action for the vulnerability"]),
):
    st, txt = page(url)
    flat = " ".join(txt.split())
    for n in needles:
        print(f"{url.split('//')[1][:52]:<52} HTTP {st}: {'found' if n in flat else 'MISSING'}: {n[:66]!r}")
    if url.endswith("-catalog"):
        links = js("[...document.querySelectorAll('a')].filter(a => /^(CSV|JSON|JSON Schema.*|License)$/.test(a.innerText.trim()))"
                   ".map(a => a.innerText.trim() + ' -> ' + a.href.replace('https://www.cisa.gov', ''))")
        print("  download links on the catalog page:", links)

page(SITE + "/sites/default/files/licenses/kev/license.txt")  # back to a small same-origin page
print()
for label, url, opts in (
    ("feed JSON                         ", FEED, {}),
    ("feed JSON ?vendor=Fortinet        ", FEED + "?vendor=Fortinet", {}),
    ("CSV, the catalog page's link      ", SITE + "/sites/default/files/csv/known_exploited_vulnerabilities.csv", {}),
    ("CSV next to the JSON (feeds/.csv) ", FEED[:-5] + ".csv", {}),
    ("JSON schema                       ", FEED[:-5] + "_schema.json", {}),
    ("feed, If-Modified-Since = its date", FEED, {"headers": {"If-Modified-Since": "Wed, 18 Nov 2026 19:17:40 GMT"}}),
    ("feed, If-None-Match = its ETag    ", FEED, {"headers": {"If-None-Match": '"1c70eb-66091dd613278"'}}),
    ("GitHub mirror JSON (cross-origin) ", "https://raw.githubusercontent.com/cisagov/kev-data/develop/known_exploited_vulnerabilities.json", {}),
):
    r = raw(url, **opts)
    h = r["headers"]
    print(f"{label} HTTP {r['status']} {r['size']:>9,} chars {h.get('content-type', '-'):<22} "
          f"last-modified {h.get('last-modified', '-')}; {' '.join(r['head'].split())[:48]!r}")
```

Output (from the verifier's re-run on 2026-11-19, 23:47 UTC, after the mirror URL moved to the default branch `develop`; the 404 page size varies by a few chars). Re-run 2026-11-20 00:43 UTC in a new cloud browser after the save line switched to printing `~/.cache/...`: same output except the 404 page size (47,239 chars):

```text
www.cisa.gov robots.txt HTTP 200: groups ['*', 'PetalBot']; '*' has 57 rules, e.g. ['disallow /search/', 'disallow /search?']; PetalBot ['disallow /']
'*' rules matching /sites/default/files/feeds/...: none
saved robots.txt (2174 chars) to ~/.cache/cisa-kev-skill/robots.txt for block 3
www.cisa.gov/sites/default/files/licenses/kev/licens HTTP 200: found: 'distributed under the Creative Commons 0 1.0 License'
www.cisa.gov/sites/default/files/licenses/kev/licens HTTP 200: found: 'You may use this data in any legal manner'
www.cisa.gov/sites/default/files/licenses/kev/licens HTTP 200: found: 'does not authorize you to use the CISA Logo or DHS Seal'
www.cisa.gov/sites/default/files/licenses/kev/licens HTTP 200: found: 'nor should such use be interpreted as an endorsement'
www.cisa.gov/known-exploited-vulnerabilities-catalog HTTP 200: found: 'The KEV catalog is also available in these formats'
www.cisa.gov/known-exploited-vulnerabilities-catalog HTTP 200: found: 'Known To Be Used in Ransomware Campaigns?'
www.cisa.gov/known-exploited-vulnerabilities-catalog HTTP 200: found: 'Forensic triage required per BOD 26-04'
  download links on the catalog page: ['CSV -> /sites/default/files/csv/known_exploited_vulnerabilities.csv', 'JSON -> /sites/default/files/feeds/known_exploited_vulnerabilities.json', 'JSON Schema -> /sites/default/files/feeds/known_exploited_vulnerabilities_schema.json', 'License -> /sites/default/files/licenses/kev/license.txt']
www.cisa.gov/known-exploited-vulnerabilities         HTTP 200: found: 'required to remediate vulnerabilities in the KEV catalog within pr'
www.cisa.gov/known-exploited-vulnerabilities         HTTP 200: found: 'Although not bound by BOD 26-04'
www.cisa.gov/known-exploited-vulnerabilities         HTTP 200: found: 'There is a clear remediation action for the vulnerability'

feed JSON                          HTTP 200 1,863,915 chars application/json       last-modified Wed, 18 Nov 2026 19:17:40 GMT; '{ "title": "CISA Catalog of Known Exploited Vuln'
feed JSON ?vendor=Fortinet         HTTP 200 1,863,915 chars application/json       last-modified Wed, 18 Nov 2026 19:17:40 GMT; '{ "title": "CISA Catalog of Known Exploited Vuln'
CSV, the catalog page's link       HTTP 200 1,115,400 chars text/csv               last-modified Wed, 18 Nov 2026 19:17:52 GMT; 'cveID,vendorProject,product,vulnerabilityName,da'
CSV next to the JSON (feeds/.csv)  HTTP 404    47,241 chars text/html; charset=utf-8 last-modified -; '<!DOCTYPE html> <html lang="en" dir="ltr" prefix'
JSON schema                        HTTP 200     3,623 chars application/json       last-modified Wed, 16 Sep 2026 17:41:50 GMT; '{ "$schema": "http://json-schema.org/draft-07/sc'
feed, If-Modified-Since = its date HTTP 304         0 chars application/json       last-modified Wed, 18 Nov 2026 19:17:40 GMT; ''
feed, If-None-Match = its ETag     HTTP 200 1,863,915 chars application/json       last-modified Wed, 18 Nov 2026 19:17:40 GMT; '{ "title": "CISA Catalog of Known Exploited Vuln'
GitHub mirror JSON (cross-origin)  HTTP 200 1,863,915 chars text/plain; charset=utf-8 last-modified -; '{ "title": "CISA Catalog of Known Exploited Vuln'
```

### 3. Same feed with Python urllib: robots check for every agent, If-Modified-Since cache, changes since your copy, one vendor and product (no browser)

Sends a descriptive User-Agent and `Accept-Encoding: gzip`. The cache is the last copy plus its `Last-Modified`; the next run sends `If-Modified-Since` and reuses the copy on HTTP 304. When a new version arrives it prints the CVE IDs added, changed and removed since your copy (a test with an edited cache printed `2 added ['CVE-2024-10441', 'CVE-2026-40217'], 1 changed ['CVE-2026-90817'], 0 removed []`). Run with an empty cache (no `kev.json` in `~/.cache/cisa-kev-skill/`).

```python
from collections import Counter
import gzip, json, os, sys, time, urllib.error, urllib.request, urllib.robotparser
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime

FEED = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
ROBOTS = "https://www.cisa.gov/robots.txt"
UA = "cisa-kev-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]
CACHE_DIR = "~/.cache/cisa-kev-skill"
CACHE = os.path.expanduser(CACHE_DIR)
BODY, META = os.path.join(CACHE, "kev.json"), os.path.join(CACHE, "kev.meta.json")
REQUIRED = ["cveID", "vendorProject", "product", "vulnerabilityName", "dateAdded", "shortDescription",
            "requiredAction", "dueDate"]

VENDOR = "Fortinet"   # vendorProject, case-insensitive
PRODUCT = "FortiOS"   # substring of product, case-insensitive; "" for all of the vendor's products

def retry_after(v):
    """Retry-After in seconds: a number or an HTTP date; 60 when absent or unreadable; at least 1. Over 120 s: exit."""
    try:
        s = float(v)
    except (TypeError, ValueError):
        try:
            s = (parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError):
            s = 60
    if s != s:  # 'nan'
        s = 60
    if s > 120:
        sys.exit(f"server asks to wait {s:.0f} s (over 120 s): stopping")
    return max(s, 1)

def robots_ok():
    """On 2026-11-19 www.cisa.gov/robots.txt answered HTTP 200 to urllib but 403 (Akamai) to curl. RobotFileParser.read()
    would turn a 403 into disallow-all, while RFC 9309 (2.3.1.3) treats a 4xx as unavailable (a crawler MAY access
    everything), so fetch it here and, on a 4xx, parse the copy block 2 read in a browser."""
    rp = urllib.robotparser.RobotFileParser(ROBOTS)
    try:
        with urllib.request.urlopen(urllib.request.Request(ROBOTS, headers={"User-Agent": UA}), timeout=30) as r:
            lines, src = r.read().decode("utf-8", "replace").splitlines(), f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        saved = os.path.join(CACHE, "robots.txt")
        if not os.path.exists(saved):
            print(f"robots.txt: HTTP {e.code} and no browser copy in {CACHE_DIR}: RFC 9309 reads a 4xx as allowed; "
                  f"run block 2 to check the real file")
            return e.code < 500
        lines = open(saved).read().splitlines()
        src = f"HTTP {e.code} to urllib; parsed the browser copy {CACHE_DIR}/robots.txt " \
              f"({datetime.fromtimestamp(os.path.getmtime(saved), timezone.utc):%Y-%m-%d %H:%M} UTC)"
    rp.parse(lines)
    ok = all(rp.can_fetch(a, FEED) for a in AGENTS)
    print(f"robots.txt: {src}: {FEED[len('https://www.cisa.gov'):]} {'allowed' if ok else 'DISALLOWED'} "
          f"for all {len(AGENTS)} agents; /search/ allowed for '*': {rp.can_fetch('*', 'https://www.cisa.gov/search/')}")
    return ok

def download():
    """-> (body dict, how). Sends If-Modified-Since from the cached copy (CISA answers 304; If-None-Match is ignored)
    and Accept-Encoding: gzip (1.86 MB -> about 205 KB). Retries once on 429/5xx or a network error."""
    meta = json.load(open(META)) if os.path.exists(META) and os.path.exists(BODY) else {}
    h = {"User-Agent": UA, "Accept": "application/json", "Accept-Encoding": "gzip"}
    if meta.get("last-modified"):
        h["If-Modified-Since"] = meta["last-modified"]
    for attempt in range(2):
        t0 = time.time()
        try:
            with urllib.request.urlopen(urllib.request.Request(FEED, headers=h), timeout=60) as r:
                raw, enc, lm = r.read(), r.headers.get("Content-Encoding"), r.headers.get("Last-Modified")
            break
        except urllib.error.HTTPError as e:
            if e.code == 304:
                return json.load(open(BODY)), f"HTTP 304 in {time.time() - t0:.2f} s, cached copy of {meta['last-modified']}"
            if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(retry_after(e.headers.get("Retry-After")))
                continue
            sys.exit(f"HTTP {e.code} {FEED}: {' '.join(e.read()[:300].decode(errors='replace').split())}")
        except OSError as e:  # URLError (DNS, refused connection), timeouts, resets
            if attempt == 0:
                time.sleep(60)
                continue
            sys.exit(f"{FEED}: {e}")
    how = f"HTTP 200 in {time.time() - t0:.2f} s, {len(raw):,} bytes {enc or 'uncompressed'}"
    text = gzip.decompress(raw) if enc == "gzip" else raw
    body = json.loads(text)
    rows = body.get("vulnerabilities")
    if not isinstance(rows, list) or body.get("count") != len(rows):
        sys.exit(f"not the KEV catalog: count {body.get('count')}, rows {type(rows).__name__}")
    bad = [v.get("cveID", "?") for v in rows if any(not v.get(k) for k in REQUIRED)]
    if bad:
        sys.exit(f"{len(bad)} rows miss a required field, e.g. {bad[:3]}: the schema changed, stop")
    os.makedirs(CACHE, exist_ok=True)
    old = json.load(open(BODY)) if os.path.exists(BODY) else None
    open(BODY, "wb").write(text)
    json.dump({"last-modified": lm, "catalogVersion": body["catalogVersion"]}, open(META, "w"))
    if old:  # what changed since the copy you had
        before = {v["cveID"]: v for v in old["vulnerabilities"]}
        new = [v["cveID"] for v in rows if v["cveID"] not in before]
        changed = [v["cveID"] for v in rows if v["cveID"] in before and v != before[v["cveID"]]]
        gone = sorted(set(before) - {v["cveID"] for v in rows})
        how += (f"; since your copy {old['catalogVersion']}: {len(new)} added {new[:10]}, {len(changed)} changed "
                f"{changed[:10]}, {len(gone)} removed {gone[:10]}")
    return body, how

if not robots_ok():
    sys.exit("robots.txt now disallows the feed path: stop")
now = datetime.now(timezone.utc)
today = now.date()
body, how = download()
rows = body["vulnerabilities"]
print(f"CISA KEV catalog {body['catalogVersion']} ({body['count']} entries): {how}")

mine = [v for v in rows if v["vendorProject"].casefold() == VENDOR.casefold()
        and PRODUCT.casefold() in v["product"].casefold()]
mine.sort(key=lambda v: (v["dateAdded"], [int(x) for x in v["cveID"].split("-")[1:]]), reverse=True)
known = [v for v in mine if v.get("knownRansomwareCampaignUse") == "Known"]
print(f"\n{VENDOR} {PRODUCT or '(all products)'}: {len(mine)} entries, {len(known)} with knownRansomwareCampaignUse "
      f"'Known'; years added {dict(sorted(Counter(v['dateAdded'][:4] for v in mine).items()))}")
print(f"  {'added':<10} {'due':<10} {'CVE':<16} {'ransom':<7} {'cwes':<15} vulnerabilityName")
for v in mine:
    print(f"  {v['dateAdded']:<10} {v['dueDate']:<10} {v['cveID']:<16} {v.get('knownRansomwareCampaignUse', '-'):<7} "
          f"{','.join(v.get('cwes') or []) or '-':<15} {v['vulnerabilityName'][:70]}")
late = [v for v in mine if date.fromisoformat(v["dueDate"]) < today]
print(f"  past dueDate (the US federal civilian deadline) on {today}: {len(late)} of {len(mine)}")
print(f"\nSource: CISA Known Exploited Vulnerabilities (KEV) catalog, {FEED}, version {body['catalogVersion']}, "
      f"accessed {now:%d %B %Y %H:%M} UTC. CC0 1.0; not endorsed by CISA or DHS.")
```

Output (from the run on 2026-11-19, 23:38 UTC, empty cache):

```text
robots.txt: HTTP 200: /sites/default/files/feeds/known_exploited_vulnerabilities.json allowed for all 11 agents; /search/ allowed for '*': False
CISA KEV catalog 2026.11.18 (1786 entries): HTTP 200 in 0.15 s, 204,849 bytes gzip

Fortinet FortiOS: 15 entries, 12 with knownRansomwareCampaignUse 'Known'; years added {'2021': 4, '2022': 4, '2023': 2, '2024': 1, '2025': 3, '2026': 1}
  added      due        CVE              ransom  cwes            vulnerabilityName
  2026-07-27 2026-08-10 CVE-2025-68686   Unknown CWE-200         Fortinet FortiOS Exposure of Sensitive Information to an Unauthorized 
  2025-06-25 2025-07-16 CVE-2019-6693    Known   CWE-798         Fortinet FortiOS Use of Hard-Coded Credentials Vulnerability
  2025-03-18 2025-04-08 CVE-2025-24472   Known   CWE-288         Fortinet FortiOS and FortiProxy Authentication Bypass Vulnerability
  2025-01-14 2025-01-21 CVE-2024-55591   Known   CWE-288         Fortinet FortiOS and FortiProxy Authentication Bypass Vulnerability
  2024-02-09 2024-02-16 CVE-2024-21762   Known   CWE-787         Fortinet FortiOS Out-of-Bound Write Vulnerability
  2023-06-13 2023-07-04 CVE-2023-27997   Known   CWE-122         Fortinet FortiOS and FortiProxy SSL-VPN Heap-Based Buffer Overflow Vul
  2023-03-14 2023-04-04 CVE-2022-41328   Unknown CWE-22          Fortinet FortiOS Path Traversal Vulnerability
  2022-12-13 2023-01-03 CVE-2022-42475   Known   CWE-197         Fortinet FortiOS Heap-Based Buffer Overflow Vulnerability
  2022-09-08 2022-09-29 CVE-2018-13374   Known   CWE-732         Fortinet FortiOS and FortiADC Improper Access Control Vulnerability
  2022-01-10 2022-07-10 CVE-2018-13383   Known   CWE-787         Fortinet FortiOS and FortiProxy Out-of-bounds Write
  2022-01-10 2022-07-10 CVE-2018-13382   Known   CWE-285         Fortinet FortiOS and FortiProxy Improper Authorization
  2021-12-10 2021-12-24 CVE-2021-44168   Unknown CWE-494         Fortinet FortiOS Arbitrary File Download
  2021-11-03 2022-05-03 CVE-2020-12812   Known   CWE-178,CWE-287 Fortinet FortiOS SSL VPN Improper Authentication Vulnerability
  2021-11-03 2022-05-03 CVE-2019-5591    Known   CWE-306         Fortinet FortiOS Default Configuration Vulnerability
  2021-11-03 2022-05-03 CVE-2018-13379   Known   CWE-22          Fortinet FortiOS SSL VPN Path Traversal Vulnerability
  past dueDate (the US federal civilian deadline) on 2026-11-19: 15 of 15

Source: CISA Known Exploited Vulnerabilities (KEV) catalog, https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json, version 2026.11.18, accessed 19 November 2026 23:38 UTC. CC0 1.0; not endorsed by CISA or DHS.
```

A second run 2 seconds later printed the same lines except the download line:

```text
CISA KEV catalog 2026.11.18 (1786 entries): HTTP 304 in 0.08 s, cached copy of Wed, 18 Nov 2026 19:17:40 GMT
```

### 4. curl: conditional download, filter, headers, CSV and the GitHub mirror

```bash
F=https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json
K=$(mktemp -d)/kev.json
C="curl -sS --fail --compressed --max-time 60 --retry 1"   # --retry 1: once on 408/429/5xx, honours Retry-After
# 1. Download (gzip on the wire, about 205 KB); -R keeps the server's Last-Modified as the file time
$C -R -o "$K" -w 'HTTP %{http_code}, %{size_download} bytes on the wire, %{time_total} s\n' "$F"
sleep 1
# 2. Next time, -z "$K" sends If-Modified-Since from the file time: 304 and the file is left alone
$C -R -z "$K" -o "$K" -w 'again: HTTP %{http_code}, %{size_download} bytes\n' "$F"
ls -l --time-style='+%Y-%m-%d %H:%M' "$K" | awk '{print "file:", $5, "bytes, mtime", $6, $7}'
# 3. Filter on your side: added in the last 7 days, and one vendor with ransomware use 'Known'
python3 -I - "$K" <<'PY'
import json, sys
from datetime import datetime, timedelta, timezone
b = json.load(open(sys.argv[1]))
if b.get("count") != len(b.get("vulnerabilities") or []):
    sys.exit("count does not match the rows: not the full catalog")
v = b["vulnerabilities"]
since = (datetime.now(timezone.utc).date() - timedelta(days=7)).isoformat()  # dateAdded is a UTC date
print(f"catalogVersion {b['catalogVersion']}, count {b['count']}; dateAdded >= {since}:")
for x in sorted((x for x in v if x["dateAdded"] >= since), key=lambda x: x["dateAdded"], reverse=True):
    print(" ", x["dateAdded"], "due", x["dueDate"], x["cveID"], x["vendorProject"], "/", x["product"], "ransomware", x["knownRansomwareCampaignUse"])
k = [x["cveID"] for x in v if x["vendorProject"] == "Ivanti" and x["knownRansomwareCampaignUse"] == "Known"]
print(f"Ivanti, ransomware 'Known': {len(k)} of {sum(x['vendorProject'] == 'Ivanti' for x in v)}: {', '.join(k)}")
PY
sleep 1
# 4. Headers: Last-Modified (the If-Modified-Since source), the ETag (If-None-Match is ignored), gzip
curl -sS --compressed -D - -o /dev/null "$F" | tr -d '\r' | grep -iE '^(HTTP/|(content-type|content-encoding|last-modified|etag|cache-control):)'
sleep 1
# 5. CSV: the catalog page links /sites/default/files/csv/, not feeds/ (feeds/...csv is 403 to curl, 404 in a browser)
$C -o "$K.csv" "https://www.cisa.gov/sites/default/files/csv/known_exploited_vulnerabilities.csv"
python3 -I -c 'import csv, sys; r = list(csv.DictReader(open(sys.argv[1], encoding="utf-8"))); print("CSV:", len(r), "rows, columns", ",".join(r[0]))' "$K.csv"
sleep 1
curl -sS -o /dev/null -w 'feeds/known_exploited_vulnerabilities.csv: HTTP %{http_code}\n' "${F%.json}.csv"
sleep 1
# 6. GitHub mirror (cisagov/kev-data, same CC0 data, "synchronized within minutes"): compare versions
curl -sS --fail --compressed --max-time 60 https://raw.githubusercontent.com/cisagov/kev-data/develop/known_exploited_vulnerabilities.json \
  | python3 -I -c 'import json, sys; b = json.load(sys.stdin); print("mirror catalogVersion", b["catalogVersion"], "count", b["count"])'
rm -r "$(dirname "$K")"
echo "Source: CISA Known Exploited Vulnerabilities (KEV) catalog, $F, accessed $(date -u '+%d %B %Y %H:%M') UTC."
```

Output (from the re-run on 2026-11-20, 00:53 UTC, after the 7-day window switched to the UTC date; the verifier's run at 2026-11-19 23:47 UTC listed the same entries with `max-age=434`):

```text
HTTP 200, 204849 bytes on the wire, 0.130151 s
again: HTTP 304, 0 bytes
file: 1863915 bytes, mtime 2026-11-18 19:17
catalogVersion 2026.11.18, count 1786; dateAdded >= 2026-11-13:
  2026-11-18 due 2026-11-21 CVE-2024-10441 Synology / DiskStation Manager (DSM) ransomware Unknown
  2026-11-18 due 2026-12-02 CVE-2026-40217 BerriAI / LiteLLM ransomware Unknown
  2026-11-18 due 2026-11-21 CVE-2026-90817 Vanderbilt University / Research Electronic Data Capture (REDCap) ransomware Unknown
  2026-11-18 due 2026-11-21 CVE-2026-90436 Apache / Axis ransomware Unknown
  2026-11-17 due 2026-12-01 CVE-2026-115731 Perforce / Puppet Enterprise ransomware Unknown
  2026-11-13 due 2026-11-16 CVE-2026-114713 UnrealIRCd / UnrealIRCd ransomware Unknown
  2026-11-13 due 2026-11-16 CVE-2026-123039 Check Point / Multiple Products ransomware Unknown
Ivanti, ransomware 'Known': 12 of 38: CVE-2025-22457, CVE-2025-0282, CVE-2021-44529, CVE-2024-21893, CVE-2023-35082, CVE-2023-46805, CVE-2024-21887, CVE-2023-38035, CVE-2023-35078, CVE-2021-22893, CVE-2019-11510, CVE-2019-11539
HTTP/2 200 
content-type: application/json
last-modified: Wed, 18 Nov 2026 19:17:40 GMT
etag: "1c70eb-66091dd613278"
content-encoding: gzip
cache-control: max-age=2947
CSV: 1786 rows, columns cveID,vendorProject,product,vulnerabilityName,dateAdded,shortDescription,requiredAction,dueDate,knownRansomwareCampaignUse,forensicTriage,notes,cwes
feeds/known_exploited_vulnerabilities.csv: HTTP 403
mirror catalogVersion 2026.11.18 count 1786
Source: CISA Known Exploited Vulnerabilities (KEV) catalog, https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json, accessed 20 November 2026 00:53 UTC.
```

## Fields (`known_exploited_vulnerabilities.json`)

| Field | Value | Notes |
|---|---|---|
| `catalogVersion` | `2026.11.18` | the release date as text; compare it with your copy to see if anything changed |
| `dateReleased` | `2026-11-18T19:17:41.0354Z` | UTC timestamp of the release; `Last-Modified` was 19:17:40 GMT |
| `count` | integer | must equal the number of rows (1786) |
| `cveID` | `CVE-2026-90436` | schema pattern `^CVE-[0-9]{4}-[0-9]{4,19}$`; 0 duplicates |
| `vendorProject`, `product` | `Fortinet`, `FortiOS` | free text; `product` is `Multiple Products` in 89 rows; 1 non-ASCII vendor (`Dassault Systèmes`) |
| `vulnerabilityName`, `shortDescription` | text | |
| `dateAdded` | `YYYY-MM-DD` | the day it entered the catalog; 2021-11-03 to 2026-11-18; 4 rows on a weekend |
| `dueDate` | `YYYY-MM-DD` | FCEB deadline; `dueDate - dateAdded` was 21 days in 1,025 rows, 14 in 292, 181 in 238, 3 in 162 |
| `requiredAction` | text | 893 rows "Apply updates per vendor instructions."; newer ones cite BOD 26-04 and "Forensics Triage Requirements" |
| `knownRansomwareCampaignUse` | `Known` / `Unknown` | strings, not booleans |
| `forensicTriage` | `Yes` / `No` | "if this vulnerability requires forensic triage per BOD 26-04"; 108 `Yes` |
| `notes` | text | vendor advisory URLs and an NVD link joined by ` ; ` (every row had an nvd.nist.gov link) |
| `cwes` | list, e.g. `["CWE-178", "CWE-287"]` | 175 rows have `[]`; in the CSV it is one string `"CWE-178, CWE-287"` |
| response headers | `content-type: application/json`, `last-modified`, `etag`, `cache-control: max-age=434..2947` (counts down; the CSV showed 0 and 1811), `content-encoding: gzip` when asked, `vary: Accept-Encoding` | no rate-limit headers seen |

## Gotchas

- **The schema grows without notice.** Only the first eight fields are required. The mirror's schema history has two commits: 2025-01-27 (11 fields, with `cwes`) and 2026-09-17, which added `forensicTriage` (BOD 26-04); the catalog page says "JSON Schema (updated 09-02-2026)" and the cisa.gov file's `Last-Modified` is 16 Sep 2026. Read the optional fields with `.get()`; block 1 lists unknown fields and blocks 1 and 3 stop when a required field is missing.
- **The CSV is in another folder.** The catalog page links `/sites/default/files/csv/known_exploited_vulnerabilities.csv` (1,116,897 bytes, same 1,786 rows and columns). Swapping `.json` for `.csv` in the feed URL gives HTTP 404 in a browser and 403 to curl.
- **curl is blocked on most of www.cisa.gov, not on the feeds.** On 2026-11-19 curl 8.5.0 got Akamai 403 for robots.txt, the license and the catalog page with every User-Agent tried (curl's, a descriptive one, Python's, `Mozilla/5.0`, `GPTBot/1.0`) and over HTTP/1.1 or HTTP/2, while Python urllib got 200 for the same three and both got 200 for the JSON and CSV feeds. The cause is not documented; read pages in a browser or with urllib.
- **`If-None-Match` is ignored, `If-Modified-Since` works.** Sending the exact `etag` still returned the full file (200); `If-Modified-Since` with the `Last-Modified` value returned 304. curl's `-R -z file` does this for you (block 4).
- **"Last N days" depends on your clock.** `dateAdded` is a date with no time zone; the blocks use today's UTC date, so a run late in the US evening is already "tomorrow". `dateReleased` and `Last-Modified` were 19:17 UTC on 2026-11-18.
- **Feed order is newest `dateAdded` first, but not by CVE inside a day.** On 2026-11-18 the order was CVE-2024-10441, CVE-2026-40217, CVE-2026-90817, CVE-2026-90436. Sort yourself, and compare CVE numbers as numbers (CVE-2026-115731 is after CVE-2026-90436).
- **Match the vendor, then the product.** Compare `vendorProject` case-insensitively, then filter `product`: 14 of Fortinet's 32 rows are "Known" ransomware, and 2 of the newest 8 say `Multiple Products`. No `vendorProject` other than `Fortinet` has a product containing "Forti".
- **Old entries keep old text.** `requiredAction` still cites BOD 22-01 in older rows (letter B in block 1), and the federal due dates of all 15 FortiOS entries are past.
- **Mirror.** https://github.com/cisagov/kev-data (default branch `develop`; branches `develop` and `staging`, no `main`, though `raw.githubusercontent.com/.../main/...` still answers with the same file and `github.com/cisagov/kev-data/tree/main` redirects to `develop`) has the same JSON and CSV (identical rows on 2026-11-19, catalogVersion 2026.11.18, same 1,863,915 bytes) and a commit history, which the cisa.gov file lacks; its README says both are "synchronized within minutes of each other". raw.githubusercontent.com/robots.txt was HTTP 404.
- **Related skills.** The `nvd` skill returns CVSS, CWE names and affected versions for CVE IDs you already have, plus the KEV dates of each (`cisaExploitAdd`, `cisaActionDue`); it does not list the catalog by date or vendor. The `epss` skill gives the 30-day exploitation probability for the same IDs.
- **Credit and no logo.** Show "Source: CISA Known Exploited Vulnerabilities (KEV) catalog" with the feed URL, the `catalogVersion` and your access time, no CISA logo or DHS seal, and nothing that suggests CISA or DHS endorses your product.
- **Tab marker.** The harness sets the tab title to a horse emoji; the blocks check `location.origin` and the page text, not the title.

## What does not work

- **Query parameters**: `?vendor=Fortinet` (or anything else) is ignored and the whole file comes back with HTTP 200. Filter locally.
- **`feeds/known_exploited_vulnerabilities.csv`**: HTTP 404 (browser) or 403 (curl). Use the `/csv/` path or the JSON.
- **`If-None-Match`**: no 304; use `If-Modified-Since`.
- **curl on www.cisa.gov pages** (robots.txt, the license, the catalog page): HTTP 403. The feed URLs work.
- **Not tested:** the 429 response (never provoked), the catalog page's own search and filters (the `/search/` path is disallowed in robots.txt; this skill does not use them), the RSS/email subscription, the mirror's commit history for anything but the schema file, and whether removed entries ever disappear from the feed (block 3 reports removals if they do).
