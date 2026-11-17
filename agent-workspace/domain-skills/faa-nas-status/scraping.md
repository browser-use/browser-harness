# FAA NAS Status - Check a US Airport for an Active Ground Stop, Ground Delay Program or Closure, With the Reason and Average Delay (XML feed, no key)

Field-tested against nasstatus.faa.gov on 2026-11-16 (US Pacific afternoon; 23:29-23:39 UTC) using a fresh Browser Use cloud browser (logged out; two short sessions, the second to re-run block 2) plus Python `urllib` and `curl` from a Linux machine. 5 browser page loads (the List View three times and robots.txt twice) and 11 in-page `fetch()` calls, 30 curl calls and 4 urllib calls to nasstatus.faa.gov (plus 2 curl calls to the legacy fly.faa.gov DTD URL and 10 to www.faa.gov for robots.txt and the contractions list), all serial: every call was HTTP 200 except the deliberate HTTP 301 (plain `http://`), 404 (misspelled path), 405 and 411 (`POST`) probes below. No 429, no challenge, no key, no login.

robots.txt (checked 2026-11-16, curl and the cloud browser): https://nasstatus.faa.gov/robots.txt is two lines, `# https://www.robotstxt.org/robotstxt.html` and `User-agent: *`, with no `Disallow` line, so everything is allowed; block 3 checks all 11 agents with `urllib.robotparser`. No named AI-agent groups, so GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider may fetch `/api/airport-status-information` and `/list`. Terms: the NAS Status footer links the feed as "XML" (block 2), and the NAS Status User Guide (https://nasstatus.faa.gov/static/media/NASStatusUserGuide.cccc6d48.pdf, p. 29) says "Active Airport and Active En Route Events are available in a machine readable format, extensible markup language (XML). A link to this page is provided in the Footer". FAA web policies: https://www.faa.gov/web_policies/disclaimer (last updated March 10, 2022) is the standard federal system banner ("provided for U.S. Government-authorized use only ... may be ... monitored, recorded, and subject to audit"), and the linking policy (https://www.faa.gov/web_policies/linking_policy) says "The Federal Aviation Administration and FAA.gov do not endorse the organizations sponsoring linked websites". No licence statement, and no AI/ML, scraping, automated-access or non-commercial clause on nasstatus.faa.gov, the User Guide or those policy pages. No rate limit is published. Naming: "FAA NAS Status (nasstatus.faa.gov)" as plain text; no FAA or DOT logo or seal. This skill is not affiliated with or endorsed by the FAA.

**Attribution:** "Source: FAA NAS Status (nasstatus.faa.gov)", plus the feed's `Update_Time`. Blocks 1 and 3 print that line.

## Quick summary

- **No scraping.** `GET https://nasstatus.faa.gov/api/airport-status-information` returns one small XML document (1,530 to 1,723 bytes in this run) with every active ground stop, ground delay program and airport-closure NOTAM in the US. No key, no parameters: filter by airport yourself.
- **Answer (feed `Update_Time` 23:32:25 UTC, block 1):** **SFO: ground delay program, low ceilings, average delay 1 h 38 min, max 5 h 24 min.** **LGA: ground stop, airport volume, until 7:45 pm EST (00:45 UTC).** SNA: closure NOTAM `DLY 0730-1415` (closed daily 07:30-14:15 UTC until 21 Nov), not in force at 23:33 UTC. LAX: NOTAM closes it only to non-scheduled transient general-aviation aircraft without prior permission. JFK: no event.
- **It moves fast.** At 23:16:09 UTC the feed had an SFO ground stop (low ceilings, until 3:30 pm PST) plus an SFO ground delay program averaging **1 h 5 min**, max 2 h 28 min. By 23:28:55 the SFO ground stop was gone and the average was 1 h 38 min; by 23:32:25 an LGA ground stop had appeared (the JSON in block 2 gives its start as 23:30 UTC). Re-fetch before you answer.
- **Not in the feed = no reported event, not "on time".** The List View showed a PIT deicing event that the XML does not carry. The User Guide (p. 19-20) says FAA facilities are required to report arrival and departure delays of 15 minutes or more.
- **Times come in three forms:** `Update_Time` in GMT, ground-stop `End_Time` in the airport's local zone (`7:45 pm EST`), closure `Start`/`Reopen` in UTC without a year (`May 28 at 16:00 UTC.` is 2027). Block 1 converts all of them to UTC.
- **Rate limit:** none published. The User Guide (p. 5, on the site's "updated" time) says "Updates occur every minute", so poll at most once a minute (block 3). No rate-limit headers; `Cache-Control: no-cache, no-store, must-revalidate`.

## What works

### 1. Is there a ground stop, ground delay or closure at this airport right now? (browser)

`on_nas_tab()` opens the logged-out List View once, so `fetch()` of the feed is same-origin. `get_feed()` waits 60 s once on 429/5xx or a network error and otherwise raises unless it gets `application/xml` with the `AIRPORT_STATUS_INFORMATION` root. `parse()` walks every `Delay_type` block, because the same type can appear twice. `closure()` reads the year and the exact window from the NOTAM's `yymmddhhmm-yymmddhhmm` range, not from `Start`/`Reopen`.

```python
import json, re, time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

AIRPORTS = ["SFO", "LGA", "SNA", "LAX", "JFK"]  # 3-letter FAA codes, as the feed writes them (SFO, not KSFO)

SITE = "https://nasstatus.faa.gov"
FEED = SITE + "/api/airport-status-information"  # the 'XML' link in the NAS Status footer; no key
# End_Time is written in the airport's local zone ("3:30 pm PST", "7:45 pm EST"); UTC offsets for US zone abbreviations.
TZ = {"EST": -5, "EDT": -4, "CST": -6, "CDT": -5, "MST": -7, "MDT": -6, "PST": -8, "PDT": -7,
      "AKST": -9, "AKDT": -8, "HST": -10, "AST": -4, "CHST": 10, "SST": -11}

def on_nas_tab():
    """fetch() runs same-origin from a logged-out nasstatus.faa.gov page. Reuse the tab if it is already there."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(SITE + "/list")
    wait_for_load()
    if js("location.origin") != SITE:
        raise RuntimeError(f"NAS Status did not load (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__o = window.__o || {}; const id = String(Math.random()).slice(2); window.__o[id] = null;
  fetch(%s, {credentials: 'omit', cache: 'no-store'})
    .then(async r => { window.__o[id] = {status: r.status, type: r.headers.get('content-type'), text: await r.text()}; })
    .catch(e => { window.__o[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__o[%s]; if (v) delete window.__o[%s]; return v; })()"""

def get_feed(timeout=60):
    """The XML feed as text. Waits 60 s once on 429/5xx or a network error; raises on anything else."""
    for attempt in range(2):
        rid = json.dumps(js(START_JS % json.dumps(FEED)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"no answer from the feed after {timeout}s")
            time.sleep(0.3)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(60)
            continue
        if r["status"] != 200 or "xml" not in (r["type"] or "") or "<AIRPORT_STATUS_INFORMATION>" not in r["text"]:
            raise RuntimeError(f"feed: HTTP {r['status']} {r['type']} {r['text'][:200]!r}; stopping")
        return r["text"]

def parse(xml_text):
    """-> (update time as UTC datetime, list of events). Each Delay_type block holds one list of items; the same
    Name can appear in several blocks (two 'Airport Closures' blocks on 2026-11-16), so collect them all."""
    root = ET.fromstring(xml_text)
    upd = datetime.strptime(root.findtext("Update_Time").strip(), "%a %b %d %H:%M:%S %Y GMT").replace(tzinfo=timezone.utc)
    events = []
    for dt in root.findall("Delay_type"):
        name = dt.findtext("Name", "").strip()
        for lst in dt:
            if lst.tag == "Name":
                continue
            for item in lst:
                f = {c.tag: (c.text or "").strip() for c in item if len(c) == 0}
                for c in item:  # nested elements (if any) are kept flat as Parent.Child
                    for g in c:
                        f[f"{c.tag}.{g.tag}"] = (g.text or "").strip()
                events.append({"type": name, "arpt": f.get("ARPT", "").upper(), **f})
    return upd, events

def minutes(text):
    """'1 hour and 5 minutes' -> 65; None when the text does not look like that."""
    h = re.search(r"(\d+)\s*hours?", text)
    m = re.search(r"(\d+)\s*minutes?", text)
    if not h and not m:
        return None
    return (int(h[1]) * 60 if h else 0) + (int(m[1]) if m else 0)

def hm(n):
    return f"{n // 60} h {n % 60} min" if n >= 60 else f"{n} min"

def local_end_utc(text, upd):
    """'3:30 pm PST' -> UTC datetime on the feed's day (next day if that is already past); None if the zone is unknown."""
    m = re.fullmatch(r"(\d{1,2}):(\d{2})\s*([ap]m)\s+([A-Z]{2,4})", text.strip(), re.I)
    if not m or m[4].upper() not in TZ:
        return None
    off = timedelta(hours=TZ[m[4].upper()])
    loc_now = upd + off
    h = int(m[1]) % 12 + (12 if m[3].lower() == "pm" else 0)
    end = loc_now.replace(hour=h, minute=int(m[2]), second=0)
    if end < loc_now - timedelta(hours=1):
        end += timedelta(days=1)
    return end - off

def closure(f, now):
    """Decode the NOTAM in an Airport Closures item. Start/Reopen have no year, the NOTAM range (yymmddhhmm UTC) does."""
    notam = f.get("Reason", "")
    rng = re.search(r"(\d{10})-(\d{10}|PERM)", notam)
    if not rng:
        return f"closure NOTAM without a time range, read it: {notam}", None
    start = datetime.strptime(rng[1], "%y%m%d%H%M").replace(tzinfo=timezone.utc)
    end = None if rng[2] == "PERM" else datetime.strptime(rng[2], "%y%m%d%H%M").replace(tzinfo=timezone.utc)
    rest = notam[notam.find("CLSD") + 4:rng.start()].strip() if "CLSD" in notam else None
    span = f"{start:%Y-%m-%d %H:%M}Z to {'PERM' if end is None else f'{end:%Y-%m-%d %H:%M}Z'}"
    active = start <= now and (end is None or now < end)
    if rest is None:
        return f"NOTAM has no CLSD, read it: {notam}", None
    if rest == "":
        return f"CLOSED (whole airport, {span})", active
    if rest.startswith("TO "):
        return f"closed only TO: {rest[3:]} ({span}); other traffic not named", active
    d = re.fullmatch(r"DLY (\d{4})-(\d{4})", rest)
    if d:
        a, b = int(d[1]), int(d[2])
        t = now.hour * 100 + now.minute
        inwin = (a <= t < b) if a < b else (t >= a or t < b)
        return f"CLOSED DAILY {d[1]}-{d[2]}Z ({span}); {'inside' if inwin else 'outside'} that window now", active and inwin
    return f"closure qualifier not decoded ({rest!r}), read the NOTAM: {notam}", None

on_nas_tab()
now = datetime.now(timezone.utc)
upd, events = parse(get_feed())
age = (now - upd).total_seconds() / 60
print(f"feed Update_Time {upd:%Y-%m-%d %H:%M:%S}Z, {age:.1f} min old; {len(events)} events: "
      f"{sorted({(e['type'], e['arpt']) for e in events})}")
if age > 15:
    print("WARNING: feed older than 15 min; re-fetch before trusting it")

for code in AIRPORTS:
    code = code.strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{3}", code):
        raise RuntimeError(f"{code!r}: use the 3-letter FAA code (SFO), not ICAO (KSFO)")
    mine = [e for e in events if e["arpt"] == code]
    if not mine:
        print(f"{code}: no ground stop, ground delay program, closure or other event in the feed "
              f"(not the same as 'on time')")
        continue
    for e in mine:
        t = e["type"]
        if t == "Ground Stop Programs":
            end = local_end_utc(e.get("End_Time", ""), upd)
            print(f"{code}: GROUND STOP, reason '{e.get('Reason')}', until {e.get('End_Time')}"
                  + (f" = {end:%H:%M}Z" if end else " (zone not decoded)"))
        elif t == "Ground Delay Programs":
            avg, mx = minutes(e.get("Avg", "")), minutes(e.get("Max", ""))
            print(f"{code}: GROUND DELAY PROGRAM, reason '{e.get('Reason')}', average delay "
                  f"{hm(avg) if avg is not None else e.get('Avg')} ({e.get('Avg')!r}), max "
                  f"{hm(mx) if mx is not None else e.get('Max')}")
        elif t == "Airport Closures":
            what, active = closure(e, now)
            state = {True: "IN FORCE NOW", False: "not in force now", None: "check by hand"}[active]
            print(f"{code}: AIRPORT CLOSURE NOTAM, {state}: {what}")
        else:  # any other Delay_type (not seen on 2026-11-16): print its fields as given
            print(f"{code}: {t.upper()}: {json.dumps({k: v for k, v in e.items() if k not in ('type', 'arpt')})}")

print(f"\nSource: FAA NAS Status (nasstatus.faa.gov) XML feed, Update_Time {upd:%d %B %Y %H:%M:%S} UTC, "
      f"accessed {now:%d %B %Y %H:%M} UTC. Not affiliated with or endorsed by the FAA.")
```

Output (from the run on 2026-11-16, 23:33 UTC):

```text
feed Update_Time 2026-11-16 23:32:25Z, 0.7 min old; 6 events: [('Airport Closures', 'LAS'), ('Airport Closures', 'LAX'), ('Airport Closures', 'SAN'), ('Airport Closures', 'SNA'), ('Ground Delay Programs', 'SFO'), ('Ground Stop Programs', 'LGA')]
SFO: GROUND DELAY PROGRAM, reason 'low ceilings', average delay 1 h 38 min ('1 hour and 38 minutes'), max 5 h 24 min
LGA: GROUND STOP, reason 'airport volume', until 7:45 pm EST = 00:45Z
SNA: AIRPORT CLOSURE NOTAM, not in force now: CLOSED DAILY 0730-1415Z (2026-11-15 07:30Z to 2026-11-21 14:15Z); outside that window now
LAX: AIRPORT CLOSURE NOTAM, IN FORCE NOW: closed only TO: NON SKED TRANSIENT GA ACFT EXC 24HR PPR CTC ATLANTIC AVIATION 310-258-9884 OR SIGNATURE AVIATION 310-410-9605 (2026-05-27 18:26Z to 2027-05-28 16:00Z); other traffic not named
JFK: no ground stop, ground delay program, closure or other event in the feed (not the same as 'on time')

Source: FAA NAS Status (nasstatus.faa.gov) XML feed, Update_Time 16 November 2026 23:32:25 UTC, accessed 16 November 2026 23:33 UTC. Not affiliated with or endorsed by the FAA.
```

### 2. robots.txt, the footer link, the List View and the JSON behind it (browser)

2 page loads and 5 in-page `fetch()` calls in the same tab. The List View fills its table from `/api/airport-events`, an undocumented JSON endpoint (it is not in the footer or the User Guide) that carries UTC start and end times, average delay in minutes and the ground stop's probability of extension. Use it to cross-check, not as the main source.

```python
import json, re, time
import xml.etree.ElementTree as ET

SITE = "https://nasstatus.faa.gov"

START_JS = """(() => { window.__o = window.__o || {}; const id = String(Math.random()).slice(2); window.__o[id] = null;
  const [url, method] = %s; fetch(url, {method, credentials: 'omit', cache: 'no-store'})
    .then(async r => { const t = await r.text(); window.__o[id] = {status: r.status, type: r.headers.get('content-type'), bytes: t.length, text: t.slice(0, 200000)}; })
    .catch(e => { window.__o[id] = {status: 0, type: '', bytes: 0, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__o[%s]; if (v) delete window.__o[%s]; return v; })()"""

def raw(path, method="GET"):
    """One in-page request -> status, type, size, body. No retries: this block only inspects answers."""
    rid = json.dumps(js(START_JS % json.dumps([SITE + path, method])))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{path}: no answer after 60s")
        time.sleep(0.3)
    time.sleep(1.0)
    return r

def page(url):
    goto_url(url)
    wait_for_load()
    return js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus"), js("document.body ? document.body.innerText : ''")

try:
    here = js("location.origin")
except Exception:
    here = None
if here != SITE:
    new_tab(SITE + "/list")
    wait_for_load()

# 1. robots.txt as the browser sees it
st, txt = page(SITE + "/robots.txt")
print(f"robots.txt HTTP {st}: {txt.strip()!r}")

# 2. the footer 'XML' link on the List View, and the rows that page shows
page(SITE + "/list")
for _ in range(20):  # the table is filled by script after load
    if "Active Airport Events" in (js("document.body.innerText") or "") and js("document.querySelectorAll('table tr').length") > 1:
        break
    time.sleep(1)
xml_links = js("[...document.querySelectorAll('a')].filter(a => /xml/i.test(a.innerText)).map(a => [a.innerText.trim(), a.href])")
print(f"footer XML link(s): {xml_links}")
rows = js("""[...document.querySelectorAll('table tr')].map(tr => [...tr.cells].map(c => c.innerText.trim()))
             .filter(c => c.length > 4 && /^[A-Z0-9]{3}$/.test(c[0]))""")
print(f"List View: {len(rows)} airport rows")
for c in rows:
    print("  " + " | ".join(x for x in c[:6] if x).replace("\u2014", " to ")[:150])  # the page joins times with an em dash

# 3. the documented XML feed, same moment
r = raw("/api/airport-status-information")
root = ET.fromstring(r["text"])
xml_ev = sorted({(dt.findtext("Name"), a.findtext("ARPT")) for dt in root.findall("Delay_type") for a in dt.iter() if a.find("ARPT") is not None})
print(f"\nXML feed HTTP {r['status']} {r['type']} {r['bytes']} chars, Update_Time {root.findtext('Update_Time')}: {xml_ev}")
print(f"Dtd_File: {root.findtext('Dtd_File')}")
only_list = sorted({c[0] for c in rows} - {a for _, a in xml_ev})
print(f"airports on the List View but not in the XML: {only_list}")

# 4. the JSON the List View itself loads (undocumented): UTC times and minutes
r = raw("/api/airport-events")
print(f"\n/api/airport-events HTTP {r['status']} {r['type']} {r['bytes']} chars (undocumented; used by the List View)")
for a in json.loads(r["text"]):
    for k in ("groundStop", "groundDelay", "airportClosure", "freeForm", "arrivalDelay", "departureDelay", "deicing"):
        v = a.get(k)
        if not v:
            continue
        keep = {x: v.get(x) for x in ("impactingCondition", "avgDelay", "maxDelay", "startTime", "endTime",
                                       "probabilityOfExtension", "text", "eventTime", "expTime") if v.get(x) not in (None, "")}
        print(f"  {a['airportId']} {k}: {keep}")

# 5. query strings and methods
for label, path, method in (("?airport=JFK (ignored?)", "/api/airport-status-information?airport=JFK", "GET"),
                            ("POST", "/api/airport-status-information", "POST"),
                            ("typo path", "/api/airport-status-informatio", "GET")):
    r = raw(path, method)
    head = re.sub(r"\s+", " ", r["text"][:90])
    print(f"{label:<24} HTTP {r['status']} {r['type']} {r['bytes']} chars {head!r}")
```

Output (from the run on 2026-11-16, 23:38 UTC; the cloud browser's clock is US Eastern, so the List View shows EST):

```text
robots.txt HTTP 200: '# https://www.robotstxt.org/robotstxt.html\nUser-agent: *'
footer XML link(s): [['XML', 'https://nasstatus.faa.gov/api/airport-status-information']]
List View: 7 airport rows
  LAS | Airport Closure | 28/3:26 PM EDT to 27/6:00 PM EST
  LAX | Airport Closure | 27/2:26 PM EDT to 28/12:00 PM EDT
  SAN | Airport Closure | 01/12:33 PM EDT to 01/3:00 AM EST
  SNA | Airport Closure | 15/2:30 AM EST to 21/9:15 AM EST
  LGA | Ground Stop | 16/6:30 PM EST to 16/7:45 PM EST | Low | Airport volume
  SFO | Ground Delay | 16/6:22 PM EST to 17/1:59 AM EST | 98 mins | Low ceilings
  PIT | Deicing | Started 16/6:43 AM EST

XML feed HTTP 200 application/xml 1723 chars, Update_Time Mon Nov 16 23:37:52 2026 GMT: [('Airport Closures', 'LAS'), ('Airport Closures', 'LAX'), ('Airport Closures', 'SAN'), ('Airport Closures', 'SNA'), ('Ground Delay Programs', 'SFO'), ('Ground Stop Programs', 'LGA')]
Dtd_File: http://www.fly.faa.gov/AirportStatus.dtd
airports on the List View but not in the XML: ['PIT']

/api/airport-events HTTP 200 application/json 8488 chars (undocumented; used by the List View)
  LAS freeForm: {'startTime': '2026-10-28T19:26:00Z', 'endTime': '2027-01-27T23:00:00Z', 'text': 'TO NON SKED TRANSIENT GA ACFT EXC 24HR PPR 702-261-7775'}
  LAX freeForm: {'startTime': '2026-05-27T18:26:00Z', 'endTime': '2027-05-28T16:00:00Z', 'text': 'TO NON SKED TRANSIENT GA ACFT EXC 24HR PPR CTC ATLANTIC AVIATION 310-258-9884 OR SIGNATURE AVIATION 310-410-9605'}
  LGA groundStop: {'impactingCondition': 'airport volume', 'startTime': '2026-11-16T23:30:00Z', 'endTime': '2026-11-17T00:45:00Z', 'probabilityOfExtension': 'LOW'}
  PIT deicing: {'eventTime': '2026-11-16T11:43:00Z', 'expTime': '2026-11-17T07:59:59Z'}
  SAN freeForm: {'startTime': '2026-10-01T16:33:00Z', 'endTime': '2027-01-01T08:00:00Z', 'text': 'TO NON SKED TRANSIENT GA ACFT EXC PPR 619-298-7704'}
  SFO groundDelay: {'impactingCondition': 'low ceilings', 'avgDelay': 98.0, 'maxDelay': 324, 'startTime': '2026-11-16T23:22:00Z', 'endTime': '2026-11-17T06:59:00Z'}
  SNA airportClosure: {'startTime': '2026-11-15T07:30:00Z', 'endTime': '2026-11-21T14:15:00Z', 'text': 'DLY 0730-1415'}
?airport=JFK (ignored?)  HTTP 200 application/xml 1723 chars '<AIRPORT_STATUS_INFORMATION><Update_Time>Mon Nov 16 23:38:17 2026 GMT</Update_Time><Dtd_Fi'
POST                     HTTP 405 application/json 128 chars '{"timestamp":"2026-11-16T23:38:18.850+00:00","status":405,"error":"Method Not Allowed","pa'
typo path                HTTP 404 text/html 49707 chars '<!doctype html> <html lang="en-us"> <head> <meta charset="utf-8"> <title>Website Una'
```

### 3. Watch airports once a minute with Python urllib, robots check for every agent (no browser)

3 polls 60 s apart. Each poll keeps the newest snapshot, because a later request can return an older `Update_Time` (see Gotchas), and prints only what changed.

```python
import re, sys, time, urllib.error, urllib.request, urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

WATCH = ["SFO", "LGA", "SNA", "JFK"]  # 3-letter FAA codes
POLLS, EVERY = 3, 60  # the User Guide says "Updates occur every minute"; polling faster gains nothing

SITE = "https://nasstatus.faa.gov"
FEED = SITE + "/api/airport-status-information"
UA = "faa-nas-status-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]

def get(url):
    """GET -> (status, content-type, text). One 60 s wait on 429/5xx or a network error; exits on anything else."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.headers.get("Content-Type", ""), r.read().decode()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(60)
                continue
            sys.exit(f"HTTP {e.code} {url}: {e.read()[:200]!r}")
        except OSError as e:  # URLError, timeouts, resets
            if attempt == 0:
                time.sleep(60)
                continue
            sys.exit(f"{url}: {e}")

def snapshot():
    """-> (Update_Time UTC, {airport: [event text, ...]}) from one fetch of the XML feed."""
    st, ctype, text = get(FEED)
    if st != 200 or "xml" not in ctype or "<AIRPORT_STATUS_INFORMATION>" not in text:
        sys.exit(f"feed: HTTP {st} {ctype} {text[:200]!r}")
    root = ET.fromstring(text)
    upd = datetime.strptime(root.findtext("Update_Time").strip(), "%a %b %d %H:%M:%S %Y GMT").replace(tzinfo=timezone.utc)
    out = {}
    for dt in root.findall("Delay_type"):
        name = dt.findtext("Name", "").strip()
        for item in dt.iter():
            if item.find("ARPT") is None:
                continue
            f = {c.tag: (c.text or "").strip() for c in item if c.tag != "ARPT"}
            if name == "Ground Delay Programs":
                s = f"ground delay program ({f.get('Reason')}), avg {f.get('Avg')}, max {f.get('Max')}"
            elif name == "Ground Stop Programs":
                s = f"ground stop ({f.get('Reason')}) until {f.get('End_Time')}"
            elif name == "Airport Closures":
                s = f"closure NOTAM {f.get('Reason', '')[:45]}... {f.get('Start')} to {f.get('Reopen')}"
            else:
                s = f"{name}: {f}"
            out.setdefault(item.findtext("ARPT").strip().upper(), []).append(s)
    return upd, out

# robots.txt: 'User-agent: *' with no Disallow line, so every agent may fetch every path.
rp = urllib.robotparser.RobotFileParser(SITE + "/robots.txt")
rp.read()
for p in ("/api/airport-status-information", "/list", "/robots.txt"):
    ok = all(rp.can_fetch(a, SITE + p) for a in AGENTS)
    print(f"robots {p:<34} {'allowed' if ok else 'DISALLOWED'} for all {len(AGENTS)} agents")
    if not ok:
        sys.exit("robots.txt now disallows a path this skill uses: stop")
time.sleep(1)

newest, prev = None, None
for i in range(POLLS):
    if i:
        time.sleep(EVERY)
    upd, ev = snapshot()
    now = datetime.now(timezone.utc)
    if newest and upd < newest:
        # Consecutive requests can return an older snapshot (seen 2026-11-16): ignore it, keep the newest.
        print(f"poll {i + 1} {now:%H:%M:%S}Z: got Update_Time {upd:%H:%M:%S}Z, older than {newest:%H:%M:%S}Z; skipped")
        continue
    newest = upd
    cur = {a: ev.get(a, []) for a in WATCH}
    print(f"poll {i + 1} {now:%H:%M:%S}Z: Update_Time {upd:%H:%M:%S}Z, {sum(map(len, ev.values()))} events at "
          f"{len(ev)} airports {sorted(ev)}")
    for a in WATCH:
        if prev is None or cur[a] != prev[a]:
            tag = "" if prev is None else "CHANGED "
            print(f"  {tag}{a}: " + ("; ".join(cur[a]) if cur[a] else "no event in the feed"))
    if prev is not None and cur == prev:
        print("  no change for", ", ".join(WATCH))
    prev = cur

print(f"\nSource: FAA NAS Status (nasstatus.faa.gov) XML feed, newest Update_Time {newest:%d %B %Y %H:%M:%S} UTC.")
```

Output (from the run on 2026-11-16, 23:34 UTC):

```text
robots /api/airport-status-information    allowed for all 11 agents
robots /list                              allowed for all 11 agents
robots /robots.txt                        allowed for all 11 agents
poll 1 23:34:07Z: Update_Time 23:33:27Z, 6 events at 6 airports ['LAS', 'LAX', 'LGA', 'SAN', 'SFO', 'SNA']
  SFO: ground delay program (low ceilings), avg 1 hour and 38 minutes, max 5 hours and 24 minutes
  LGA: ground stop (airport volume) until 7:45 pm EST
  SNA: closure NOTAM !SNA 11/020 SNA AD AP CLSD DLY 0730-1415 2611... Nov 15 at 07:30 UTC. to Nov 21 at 14:15 UTC.
  JFK: no event in the feed
poll 2 23:35:07Z: Update_Time 23:34:21Z, 6 events at 6 airports ['LAS', 'LAX', 'LGA', 'SAN', 'SFO', 'SNA']
  no change for SFO, LGA, SNA, JFK
poll 3 23:36:07Z: Update_Time 23:35:20Z, 6 events at 6 airports ['LAS', 'LAX', 'LGA', 'SAN', 'SFO', 'SNA']
  no change for SFO, LGA, SNA, JFK

Source: FAA NAS Status (nasstatus.faa.gov) XML feed, newest Update_Time 16 November 2026 23:35:20 UTC.
```

### 4. curl

```bash
F=https://nasstatus.faa.gov/api/airport-status-information
# the answer for one airport: every event that names it, with the feed's Update_Time
curl -sS --fail -A 'faa-nas-status-skill-example/1.0' "$F" | python3 -c 'import sys, xml.etree.ElementTree as ET
A = "SFO"
r = ET.fromstring(sys.stdin.read()); print("Update_Time", r.findtext("Update_Time"))
hits = [(d.findtext("Name"), {c.tag: c.text for c in i}) for d in r.findall("Delay_type") for i in d.iter() if i.findtext("ARPT") == A]
for n, f in hits: print(A, n, f)
print(A, "events:", len(hits))'
sleep 1
# headers: plain XML, no cache, no rate-limit headers, no ETag
curl -sS -D - -o /dev/null --compressed "$F" | tr -d '\r' | grep -iE '^(HTTP/|content-type|content-encoding|cache-control|etag|last-modified|x-ratelimit|retry-after)'
sleep 1
# Dtd_File's URL on the legacy fly.faa.gov now redirects to the NAS Status home page (HTML, no DTD)
curl -sS -L -o /dev/null -w '%{http_code} %{num_redirects} redirects -> %{url_effective} %{content_type}\n' http://www.fly.faa.gov/AirportStatus.dtd
sleep 1
# mistakes: a query string is ignored (full feed comes back); POST without a body is refused
curl -sS -o /dev/null -w '?airport=JFK -> HTTP %{http_code} %{content_type} %{size_download} B\n' "$F?airport=JFK"
sleep 1
curl -sS -o /dev/null -w 'POST -> HTTP %{http_code} %{content_type}\n' -X POST "$F"
```

Output (from the run on 2026-11-16, 23:36 UTC):

```text
Update_Time Mon Nov 16 23:35:20 2026 GMT
SFO Ground Delay Programs {'ARPT': 'SFO', 'Reason': 'low ceilings', 'Avg': '1 hour and 38 minutes', 'Max': '5 hours and 24 minutes'}
SFO events: 1
HTTP/1.1 200 OK
Content-Type: application/xml
Content-Encoding: gzip
Cache-Control: no-cache, no-store, must-revalidate
200 4 redirects -> https://nasstatus.faa.gov/ text/html;charset=UTF-8
?airport=JFK -> HTTP 200 application/xml 1723 B
POST -> HTTP 411 text/html
```

## Fields (XML feed)

| Element | Example | Notes |
|---|---|---|
| `Update_Time` | `Mon Nov 16 23:32:25 2026 GMT` | when the feed was built; changed about once a minute in block 3 |
| `Dtd_File` | `http://www.fly.faa.gov/AirportStatus.dtd` | legacy URL; redirects (4 hops) to the NAS Status home page, HTML, no DTD |
| `Delay_type/Name` | `Ground Stop Programs`, `Ground Delay Programs`, `Airport Closures` | the three types seen on 2026-11-16; the same Name can repeat in a second `Delay_type` block |
| `Ground_Stop_List/Program` | `ARPT` `LGA`, `Reason` `airport volume`, `End_Time` `7:45 pm EST` | `End_Time` is airport-local with a zone abbreviation, no date |
| `Ground_Delay_List/Ground_Delay` | `ARPT` `SFO`, `Reason` `low ceilings`, `Avg` `1 hour and 38 minutes`, `Max` `5 hours and 24 minutes` | durations are English text, not numbers; no start or end time |
| `Airport_Closure_List/Airport` | `ARPT` `SNA`, `Reason` `!SNA 11/020 SNA AD AP CLSD DLY 0730-1415 2611150730-2611211415`, `Start` `Nov 15 at 07:30 UTC.`, `Reopen` `Nov 21 at 14:15 UTC.` | `Reason` is the raw NOTAM; its last token is the UTC range with the year |
| `ARPT` | `SFO` | 3-letter FAA code, not ICAO (`KSFO`) |

`/api/airport-events` (undocumented JSON, block 2) per airport: `groundStop`, `groundDelay`, `airportClosure`, `freeForm`, `arrivalDelay`, `departureDelay`, `deicing`, `airportConfig`, each `null` or an object with ISO UTC `startTime`/`endTime`, `impactingCondition`, and for delays `avgDelay`/`maxDelay` in minutes (`98.0`, `324` for SFO).

## Gotchas

- **`Delay_type` blocks repeat.** On 2026-11-16 there were two `Airport Closures` blocks (SNA in one; LAX, SAN and LAS in the other). Code that takes the first block per type misses airports.
- **Three time formats.** `Update_Time` is GMT; ground-stop `End_Time` is airport-local (`3:30 pm PST` for SFO, `7:45 pm EST` for LGA, which the JSON gives as `2026-11-17T00:45:00Z`); closure `Start`/`Reopen` are UTC with no year. LAX's `Reopen` says `May 28 at 16:00 UTC.`; the NOTAM range `2605271826-2705281600` shows it is 28 May **2027**.
- **A "closure" is often partial.** LAX, SAN and LAS NOTAMs read `AD AP CLSD TO NON SKED TRANSIENT GA ACFT EXC ... PPR`: in the FAA contractions list (Order JO 7340.2, https://www.faa.gov/air_traffic/publications/atpubs/cnt_html/chap2_section_1.html) SKED is schedule, GA general aviation, ACFT aircraft, EXC except, PPR prior permission required. These NOTAMs name no other traffic, yet the List View labels all of them "Airport Closure". Block 1 prints "closed only TO" for these.
- **Daily windows.** SNA's `CLSD DLY 0730-1415` (DLY is daily) runs from 15 to 21 Nov, but the airport is closed only 07:30-14:15 UTC each day. At 23:33 UTC block 1 reports it not in force.
- **Missing airport is not "on time".** The XML lists only ground stops, ground delay programs and closures that are active (plus any other `Delay_type` the FAA adds). PIT deicing was on the List View and in the JSON, not in the XML.
- **`Update_Time` can go backwards (seen once).** Two curl calls about a second apart returned 23:31:41 and then 23:30:45. 76 later calls over 2 minutes (23:42:46-23:44:48 UTC, three feed updates) did not repeat it. Keeping the newest snapshot when polling costs nothing (block 3).
- **Averages are text.** `1 hour and 5 minutes`, `5 hours and 24 minutes`: parse hours and minutes separately (block 1's `minutes()`); the JSON's `avgDelay` is the number (98.0).
- **No filtering on the server.** `?airport=JFK` is ignored and returns the full feed (HTTP 200, same size). `POST` is HTTP 411 from curl without a body and HTTP 405 JSON from the browser.
- **Errors are HTML.** A misspelled path is HTTP 404 with a 49,707-byte HTML "Website Unavailable" page. Check the content type and the root element before parsing.
- **`Dtd_File` is dead.** `http://www.fly.faa.gov/AirportStatus.dtd` redirects to the NAS Status home page. Other fly.faa.gov pages, such as the advisories the List View links to, still load.
- **Tab marker.** The harness sets the tab title to a horse emoji; the blocks check `location.origin`, never the title.

## What does not work

- **Server-side filters** (by airport, type or time): none exist; fetch the whole feed and filter.
- **Delay types other than the three above** (arrival and departure delays, which the User Guide p. 19-20 describes, or others): none were active during this run, so their XML element names were not seen. Block 1 prints any unknown `Delay_type` with its raw fields instead of guessing.
- **Not tested:** rate-limit behaviour (never provoked), the en route events in the feed (the User Guide says the XML carries them; none were active), the other `/api/` paths the List View's script references (`/api/enroute-events`, `/api/operations-plan` and more), and historical data (the feed is "now" only).
