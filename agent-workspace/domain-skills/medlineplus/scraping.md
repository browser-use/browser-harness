# MedlinePlus Health Topics via the MedlinePlus Web Service (wsearch.nlm.nih.gov) - Get the Plain-Language Summary and Page Link for a Condition (XML API, no key)

Field-tested against wsearch.nlm.nih.gov on 2026-11-17 (US Eastern evening; the logged runs were 2026-11-18, 00:02-00:08 UTC) using a fresh Browser Use cloud browser (logged out; one session, 00:05-00:07 UTC) plus Python `urllib` and `curl` from a Linux machine. 11 browser page loads (an API XML page, both robots files, the Web Service page and the "Linking to and Using Content" page) and 38 in-page `fetch()` calls (blocks 1 and 2 each ran twice), 33 curl calls and 12 urllib calls (4 of them robots.txt), all serial at 1 s or more spacing: every API call was HTTP 200 except the deliberate HTTP 400 "Expired Results" probes, plus the HTTP 404 of the API host's robots.txt. No 429, no challenge, no key, no login.

robots.txt (checked 2026-11-17 and 2026-11-18 UTC, curl, the cloud browser and `urllib.robotparser`): https://wsearch.nlm.nih.gov/robots.txt answers HTTP 404 (Apache "Not Found" page), so the API host has no rules and no named AI-agent groups; under RFC 9309 (section 2.3.1.3) an unavailable robots.txt (4xx) means a crawler "MAY access any resources", and Python's parser treats it as allow-all. https://medlineplus.gov/robots.txt has one `User-agent: *` group and no named AI-agent groups, so GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider fall under `*`; it disallows only `/URLchecker/`, `/usp/`, `/cgi/`, `/logs/`, `/glftp/`, the `feeds`/`groupfeeds` paths, `/xml/`, `/xml/vocabulary/`, two `scwidget` pages and tutorial `.swf` files, none of which this skill uses; the health topic pages it links to (`/asthma.html`, `/spanish/asthma.html`) are allowed for all 11 agents (block 3). Terms: the Web Service page https://medlineplus.gov/about/developers/webservices/ says the service "is free of charge and does not require registration or licensing" and asks: "please indicate that the information is from MedlinePlus.gov but do not use the MedlinePlus logo or otherwise imply that MedlinePlus endorses your particular product". Its Acceptable Use Policy: "no more than 85 requests per minute per IP address", "Requests that exceed this limit will not be serviced, and service will not be restored until the request rate falls beneath the limit", the service "is updated once per day, Tuesday-Saturday", and "NLM recommends caching results for a 12-24 hour period"; it encourages the `tool` and `email` parameters. The page https://medlineplus.gov/about/using/usingcontent/ lists "Summaries on health topic pages" as public domain, asks for the credit "Source: MedlinePlus, National Library of Medicine." (or "Courtesy of MedlinePlus from the National Library of Medicine"), and says "Any content from the A.D.A.M. Medical Encyclopedia" and "Drug monographs from the American Society of Health-System Pharmacists" are copyrighted and "You may not ingest and/or brand the copyrighted content found on MedlinePlus in an EHR, patient portal, or other health IT system". No AI/ML, scraping, automated-access or non-commercial clause on either page. Naming: this skill says "MedlinePlus" in plain text with the credit line above, uses no MedlinePlus, NLM or NIH logo, and is not affiliated with or endorsed by MedlinePlus, NLM or NIH. It returns only health topic titles, links and summaries: every block stops on any result URL that is not a `medlineplus.gov/<topic>.html` page, and none of them fetch encyclopedia (`/ency/`) or drug (`/druginfo/`) pages.

**Not medical advice.** MedlinePlus health topics are general consumer health information. Show the summary with its link and credit, and send people to a clinician for decisions about their own care. Send condition words only, never a person's name, record number or notes.

## Quick summary

- **No scraping.** `GET https://wsearch.nlm.nih.gov/ws/query?db=healthTopics&term=asthma&retmax=10&tool=<yourtool>` -> XML `<nlmSearchResult>` with `<count>56</count>` and `<document rank="1" url="https://medlineplus.gov/asthma.html">` whose `<content name="FullSummary">` begins "What is asthma?" then "Asthma is a chronic (long-term) lung disease. It affects your airways, the tubes that carry air in and out of your lungs." `db=healthTopicsSpanish&term=asma` -> 64 topics, top https://medlineplus.gov/spanish/asthma.html. No key, no registration.
- **Answer (run 2026-11-18, 00:06 UTC):** "asthma" matches **56 health topics**; the top one is **"Asthma" at https://medlineplus.gov/asthma.html** (summary 5,180 characters as plain text), then Asthma in Children, Allergy, COPD. "high blood pressure" matches 114; the "High Blood Pressure" topic is **second** in server order, after "How to Prevent High Blood Pressure".
- **Strip the highlight spans.** Titles, alt-titles, summaries, group names and snippets come back with the query words wrapped in `<span class="qt0">...</span>` (escaped as `&lt;span ...&gt;` in the XML, sometimes nested 3 deep: "heart attack" gives `<span class="qt0"><span class="qt2">Heart</span></span><span class="qt2"> </span>...`). The summary is also HTML (`p`, `ul`, `li`). The blocks drop every tag with Python's `HTMLParser`.
- **The first result is not always the topic you asked for, and `rank` is not the order.** The asthma topic carries `rank="1"` and comes before `rank="0"` (the doc: a title or alt-title match is "boosted to the top, regardless of the rank"), but for "high blood pressure" the exact topic is #2. Blocks 1 and 3 pick the topic whose title or alt-title equals the words, else the first one.
- **Silent failure:** a typo (`asthmaa`), no match, a missing `db` or a wrong-case `db=healthtopics` are all HTTP 200 with `<count>0</count>`; a typo also carries `<spellingCorrection>asthma</spellingCorrection>`, which blocks 1 and 3 follow once. A missing `term` is HTTP 200 with `<error-msg>`. Only an expired paging `file=` gave a non-200 (HTTP 400 HTML "Expired Results").
- **Rate limit:** at most 85 requests per minute per IP, and cache 12-24 h (Acceptable Use Policy). All blocks pace 1 s per call, serial (60/min at most); blocks 1 and 3 wait `Retry-After` (seconds or an HTTP date; default 60 s) once on 429/5xx and stop when it asks for more than 120 s; block 3 caches answers on disk for 12 h. The server itself sends `Cache-Control: max-age=3600, public`.

## What works

### 1. Condition words -> best health topic, summary and link (browser)

`on_ws_tab()` opens one logged-out wsearch.nlm.nih.gov XML answer, so `fetch()` is same-origin (the API sends no `Access-Control-Allow-Origin`, so a page on another origin cannot read it). `search()` returns the parsed XML on HTTP 200, waits once on 429/500/502/503/504 and otherwise raises. `topics()` turns each `<document>` into plain-text fields and stops on any URL that is not a health topic page. On `count` 0 with a `spellingCorrection`, it searches the suggestion once. 5 `fetch()` calls for the 4 queries.

```python
import html, json, re, time, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

QUERIES = [("asthma", "healthTopics"), ("high blood pressure", "healthTopics"), ("asthmaa", "healthTopics"),
           ("asma", "healthTopicsSpanish")]  # condition words, never patient data
SHOW = 3  # other topics to list after the best one

SITE = "https://wsearch.nlm.nih.gov"
WS = SITE + "/ws/query"
TOOL = "medlineplus-skill-example"  # the doc asks for a constant tool= with no spaces. email= is optional: not sent
PAUSE = 1.0  # Acceptable Use Policy: at most 85 requests per minute per IP. 1 s apart = at most 60/min
TOPIC_URL = re.compile(r"https://medlineplus\.gov/(spanish/)?[a-z0-9]+\.html")  # health topic pages only

def on_ws_tab():
    """fetch() runs same-origin from a logged-out wsearch.nlm.nih.gov XML page (the API sends no CORS allow-origin)."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(WS + "?" + urllib.parse.urlencode(dict(db="healthTopics", term="asthma", retmax=1, tool=TOOL)))
    wait_for_load()
    body = js("document.documentElement ? document.documentElement.textContent : ''") or ""
    if js("location.origin") != SITE or "medlineplus.gov/asthma.html" not in (js("document.documentElement.outerHTML") or body):
        raise RuntimeError(f"wsearch.nlm.nih.gov did not serve the MedlinePlus Web service (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { const h = {}; r.headers.forEach((v, k) => { h[k] = v; });
      window.__u[id] = {status: r.status, headers: h, text: await r.text()}; })
    .catch(e => { window.__u[id] = {status: 0, headers: {}, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

def retry_after(v):
    """Retry-After in seconds: a number or an HTTP date; 60 when absent or unreadable; at least 1. Over 120 s: stop."""
    try:
        s = float(v)
    except (TypeError, ValueError):
        try:
            s = (parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError):
            s = 60
    if s > 120:
        raise RuntimeError(f"server asks to wait {s:.0f} s (over 120 s): stopping")
    return max(s, 1)

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

def search(term, db="healthTopics", retmax=10):
    """-> parsed <nlmSearchResult> root. Waits Retry-After once on 429/500/502/503/504 or a network error,
    raises on any other status, on non-XML and on an <error-msg> answer."""
    url = WS + "?" + urllib.parse.urlencode(dict(db=db, term=term, retmax=retmax, tool=TOOL))
    for attempt in range(2):
        r = fetch(url)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(retry_after(r["headers"].get("retry-after")))
            continue
        break
    if r["status"] != 200 or "xml" not in r["headers"].get("content-type", ""):
        raise RuntimeError(f"{url}: HTTP {r['status']} {' '.join(r['text'].split())[:200]!r}; stopping")
    root = ET.fromstring(r["text"].encode())
    if root.tag != "nlmSearchResult" or root.find("count") is None:
        err = " ".join((root.findtext("error-msg") or r["text"][:200]).split())
        raise RuntimeError(f"{url}: {err}")
    return root

class Text(HTMLParser):
    """HTML fragment -> plain text: drops every tag (the qt0/qt1 highlight spans too), one line per p/li."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = [""]
    def handle_starttag(self, tag, attrs):
        if tag in ("p", "li", "ul", "ol", "br", "h3", "h4"):
            self.out.append("- " if tag == "li" else "")
    def handle_endtag(self, tag):
        if tag in ("p", "li", "ul", "ol", "h3", "h4"):
            self.out.append("")
    def handle_data(self, d):
        self.out[-1] += d

def plain(fragment):
    t = Text()
    t.feed(fragment or "")
    t.close()
    return [" ".join(x.split()) for x in t.out if x.strip(" -")]

def topics(root):
    """<document>s in server order -> dicts with plain-text fields. Stops on any URL that is not a health topic page,
    so nothing from the A.D.A.M. encyclopedia or the ASHP drug pages (both copyrighted) is returned."""
    out = []
    for d in root.iter("document"):
        f = {}
        for c in d.findall("content"):
            f.setdefault(c.get("name"), []).append(c.text or "")
        if not TOPIC_URL.fullmatch(d.get("url", "")):
            raise RuntimeError(f"unexpected non-health-topic URL {d.get('url')!r}: stopping")
        summary = (f.get("FullSummary") or [""])[0]
        paras = [p for p in (plain(x) for x in re.findall(r"<p>(.*?)</p>", summary, re.S)) if p]
        out.append(dict(rank=int(d.get("rank", -1)), url=d.get("url"), title=" ".join(plain(f["title"][0])),
                        alt=[" ".join(plain(a)) for a in f.get("altTitle", [])],
                        groups=[" ".join(plain(g)) for g in f.get("groupName", [])],
                        lead=paras[0][0] if paras else (plain(summary) or [""])[0],
                        summary=plain(summary)))
    return out

def pick(docs, term):
    """The topic whose title or alt-title equals the query; else the first one in server order."""
    key = " ".join(term.lower().split())
    for d in docs:
        if key == d["title"].lower() or key in (a.lower() for a in d["alt"]):
            return d, "title or alt-title equals the query"
    return docs[0], "first in server order"

on_ws_tab()
now = datetime.now(timezone.utc)
print(f"MedlinePlus health topics via the MedlinePlus Web Service, queried {now:%Y-%m-%d %H:%M} UTC")
for term, db in QUERIES:
    print(f"\n=== {term!r} ({db})")
    root = search(term, db)
    count = int(root.findtext("count"))
    if count == 0 and root.findtext("spellingCorrection"):
        fix = root.findtext("spellingCorrection")
        print(f"  0 topics; the service suggests {fix!r}: searching that instead")
        term, root = fix, search(fix, db)
        count = int(root.findtext("count"))
    if count == 0:
        print("  0 topics and no spelling suggestion: try other words")
        continue
    docs = topics(root)
    best, why = pick(docs, term)
    print(f"  {count} topics. Best: {best['title']!r} {best['url']} ({why}; #{docs.index(best) + 1} in server order, "
          f"rank attribute {best['rank']})")
    print(f"  groups: {', '.join(best['groups'])}")
    print(f"  summary ({len(' '.join(best['summary'])):,} chars, {len(best['summary'])} lines), lead paragraph:")
    print(f"    {best['lead'][:300]}" + ("..." if len(best["lead"]) > 300 else ""))
    others = [d for d in docs if d is not best][:SHOW]
    print("  next in server order: " + "; ".join(f"{d['title']} {d['url']}" for d in others))

print("\nSource: MedlinePlus, National Library of Medicine (https://medlineplus.gov), health topic summaries via "
      f"{WS}, accessed {now:%d %B %Y %H:%M} UTC. General health information, not medical advice.")
```

Output (from the run on 2026-11-18, 00:06 UTC):

```text
MedlinePlus health topics via the MedlinePlus Web Service, queried 2026-11-18 00:06 UTC

=== 'asthma' (healthTopics)
  56 topics. Best: 'Asthma' https://medlineplus.gov/asthma.html (title or alt-title equals the query; #1 in server order, rank attribute 1)
  groups: Lungs and Breathing, Immune System
  summary (5,180 chars, 57 lines), lead paragraph:
    Asthma is a chronic (long-term) lung disease. It affects your airways, the tubes that carry air in and out of your lungs. When you have asthma, your airways can become inflamed and narrowed. This can cause wheezing, coughing, and tightness in your chest. When these symptoms get worse than usual, it ...
  next in server order: Asthma in Children https://medlineplus.gov/asthmainchildren.html; Allergy https://medlineplus.gov/allergy.html; COPD https://medlineplus.gov/copd.html

=== 'high blood pressure' (healthTopics)
  114 topics. Best: 'High Blood Pressure' https://medlineplus.gov/highbloodpressure.html (title or alt-title equals the query; #2 in server order, rank attribute 1)
  groups: Older Adults, Blood, Heart and Circulation
  summary (2,978 chars, 18 lines), lead paragraph:
    Blood pressure is the force of your blood pushing against the walls of your arteries. Each time your heart beats, it pumps blood into the arteries. Your blood pressure is highest when your heart beats, pumping the blood. This is called systolic pressure. When your heart is at rest, between beats, yo...
  next in server order: How to Prevent High Blood Pressure https://medlineplus.gov/howtopreventhighbloodpressure.html; High Blood Pressure in Pregnancy https://medlineplus.gov/highbloodpressureinpregnancy.html; Blood Pressure Medicines https://medlineplus.gov/bloodpressuremedicines.html

=== 'asthmaa' (healthTopics)
  0 topics; the service suggests 'asthma': searching that instead
  56 topics. Best: 'Asthma' https://medlineplus.gov/asthma.html (title or alt-title equals the query; #1 in server order, rank attribute 1)
  groups: Lungs and Breathing, Immune System
  summary (5,180 chars, 57 lines), lead paragraph:
    Asthma is a chronic (long-term) lung disease. It affects your airways, the tubes that carry air in and out of your lungs. When you have asthma, your airways can become inflamed and narrowed. This can cause wheezing, coughing, and tightness in your chest. When these symptoms get worse than usual, it ...
  next in server order: Asthma in Children https://medlineplus.gov/asthmainchildren.html; Allergy https://medlineplus.gov/allergy.html; COPD https://medlineplus.gov/copd.html

=== 'asma' (healthTopicsSpanish)
  64 topics. Best: 'Asma' https://medlineplus.gov/spanish/asthma.html (title or alt-title equals the query; #1 in server order, rank attribute 1)
  groups: Pulmón y vías respiratorias, Sistema inmunitario
  summary (5,691 chars, 55 lines), lead paragraph:
    El asma es una enfermedad pulmonar crónica (de largo plazo). Afecta las vías respiratorias, los conductos que llevan el aire hacia y desde los pulmones. Cuando tiene asma, sus vías respiratorias pueden inflamarse y estrecharse. Esto puede causar sibilancias, tos y opresión en el pecho. Cuando estos ...
  next in server order: Asma en niños https://medlineplus.gov/spanish/asthmainchildren.html; Alergia https://medlineplus.gov/spanish/allergy.html; Enfermedad de obstrucción pulmonar crónica https://medlineplus.gov/spanish/copd.html

Source: MedlinePlus, National Library of Medicine (https://medlineplus.gov), health topic summaries via https://wsearch.nlm.nih.gov/ws/query, accessed 18 November 2026 00:06 UTC. General health information, not medical advice.
```

### 2. robots.txt, the terms pages and query mistakes (browser)

4 page loads, 1 return to the API page and 14 in-page `fetch()` calls in the same tab.

```python
import json, re, time
import xml.etree.ElementTree as ET

SITE = "https://wsearch.nlm.nih.gov"
WS = SITE + "/ws/query"
T = "&tool=medlineplus-skill-example"

START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__u[id] = {status: r.status, type: r.headers.get('content-type') || '', text: await r.text()}; })
    .catch(e => { window.__u[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

def raw(query):
    """One in-page GET of WS?query -> status, content type and body. No retries: this block only inspects answers."""
    rid = json.dumps(js(START_JS % json.dumps(WS + "?" + query)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{query}: no answer after 60s")
        time.sleep(0.2)
    time.sleep(1.0)  # at most 85 requests per minute per IP
    return r

def brief(r):
    out = f"HTTP {r['status']}"
    try:
        root = ET.fromstring(r["text"].encode())
    except ET.ParseError:
        return out + f" {r['type'].split(';')[0]} not XML: {' '.join(re.sub(r'<style.*?</style>|<[^>]+>', ' ', r['text'], flags=re.S).split())[:70]!r}"
    if root.find("error-msg") is not None:
        return out + f" error-msg {' '.join(root.findtext('error-msg').split())[:70]!r}"
    docs = [(d.get("rank"), d.get("url").rsplit("/", 1)[1]) for d in root.iter("document")]
    sc = root.findtext("spellingCorrection")
    return out + f" count {root.findtext('count')}" + (f", spellingCorrection {sc!r}" if sc else "") + \
        (f", first (rank, page) {docs[:3]}" if docs else "")

def page(url):
    goto_url(url)
    wait_for_load()
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    return st, js("document.body ? document.body.innerText : (document.documentElement.textContent || '')") or ""

try:
    on_site = js("location.origin") == SITE
except Exception:
    on_site = False
if not on_site:
    new_tab(WS + "?db=healthTopics&term=asthma&retmax=1" + T)
    wait_for_load()

st, txt = page(SITE + "/robots.txt")
print(f"wsearch robots.txt HTTP {st}: {' '.join(txt.split())[:60]!r}")
st, txt = page("https://medlineplus.gov/robots.txt")
lines = [l.strip() for l in txt.splitlines() if l.strip()]
print(f"medlineplus.gov robots.txt HTTP {st}: {len(lines)} lines; user-agent lines {[l for l in lines if l.lower().startswith('user-agent')]}")
print("  disallowed: " + " ".join(l.split(":", 1)[1].strip() for l in lines if l.lower().startswith("disallow")))
st, txt = page("https://medlineplus.gov/about/developers/webservices/")
flat = " ".join(txt.split())
for needle in ("free of charge and does not require registration or licensing", "do not use the MedlinePlus logo",
               "no more than 85 requests per minute per IP address", "caching results for a 12-24 hour period",
               "updated once per day, Tuesday-Saturday", "the first document in the first results set may have a rank greater than zero"):
    print(f"webservices HTTP {st}: {'found' if needle in flat else 'MISSING'}: {needle!r}")
st, txt = page("https://medlineplus.gov/about/using/usingcontent/")
flat = " ".join(txt.split())
for needle in ("Summaries on health topic pages", "Source: MedlinePlus, National Library of Medicine",
               "Any content from the A.D.A.M. Medical Encyclopedia", "Drug monographs from the American Society of Health-System Pharmacists",
               "You may not ingest and/or brand the copyrighted content"):
    print(f"usingcontent HTTP {st}: {'found' if needle in flat else 'MISSING'}: {needle!r}")
page(WS + "?db=healthTopics&term=asthma&retmax=1" + T)  # back to an API page for same-origin fetch()
print()

for label, query in (
    ("asthma, first 3                  ", "db=healthTopics&term=asthma&retmax=3"),
    ("high blood pressure (words ANDed)", "db=healthTopics&term=high+blood+pressure&retmax=3"),
    ("phrase in %22 quotes             ", "db=healthTopics&term=%22high+blood+pressure%22&retmax=3"),
    ("field search title:asthma        ", "db=healthTopics&term=title:asthma&retmax=3"),
    ("OR operator                      ", "db=healthTopics&term=%22diabetes+medicines%22+OR+%22diabetes+drugs%22&retmax=3"),
    ("Spanish db, Spanish word         ", "db=healthTopicsSpanish&term=asma&retmax=2"),
    ("Spanish db, English word         ", "db=healthTopicsSpanish&term=asthma&retmax=2"),
    ("misspelling asthmaa              ", "db=healthTopics&term=asthmaa"),
    ("no match zzqxv                   ", "db=healthTopics&term=zzqxv"),
    ("no db parameter                  ", "term=asthma"),
    ("db=healthtopics (lower case)     ", "db=healthtopics&term=asthma"),
    ("no term parameter                ", "db=healthTopics"),
    ("retstart=54 without file/server  ", "db=healthTopics&term=asthma&retstart=54&retmax=5"),
    ("expired/unknown file= paging     ", "file=viv_XXXXXX&server=pvlb7srch15&retstart=10"),
):
    print(f"{label} {brief(raw(query + T))}")
```

Output (from the run on 2026-11-18, 00:06 UTC):

```text
wsearch robots.txt HTTP 404: 'Not Found The requested URL was not found on this server.'
medlineplus.gov robots.txt HTTP 200: 17 lines; user-agent lines ['User-agent: *']
  disallowed: /URLchecker/ /usp/ /cgi/ /logs/ /glftp/ /feeds/topics/ /groupfeeds/ /spanish/feeds/topics/ /spanish/groupfeeds/ /xml/ /xml/vocabulary/ /scwidget/topsearch.html /spanish/scwidget/topsearch.html /tutorials/*.swf$ /spanish/tutorials/*.swf$
webservices HTTP 200: found: 'free of charge and does not require registration or licensing'
webservices HTTP 200: found: 'do not use the MedlinePlus logo'
webservices HTTP 200: found: 'no more than 85 requests per minute per IP address'
webservices HTTP 200: found: 'caching results for a 12-24 hour period'
webservices HTTP 200: found: 'updated once per day, Tuesday-Saturday'
webservices HTTP 200: found: 'the first document in the first results set may have a rank greater than zero'
usingcontent HTTP 200: found: 'Summaries on health topic pages'
usingcontent HTTP 200: found: 'Source: MedlinePlus, National Library of Medicine'
usingcontent HTTP 200: found: 'Any content from the A.D.A.M. Medical Encyclopedia'
usingcontent HTTP 200: found: 'Drug monographs from the American Society of Health-System Pharmacists'
usingcontent HTTP 200: found: 'You may not ingest and/or brand the copyrighted content'

asthma, first 3                   HTTP 200 count 56, first (rank, page) [('1', 'asthma.html'), ('0', 'asthmainchildren.html'), ('2', 'allergy.html')]
high blood pressure (words ANDed) HTTP 200 count 114, first (rank, page) [('0', 'howtopreventhighbloodpressure.html'), ('1', 'highbloodpressure.html'), ('2', 'highbloodpressureinpregnancy.html')]
phrase in %22 quotes              HTTP 200 count 97, first (rank, page) [('0', 'highbloodpressure.html'), ('1', 'pulmonaryhypertension.html'), ('2', 'howtopreventhighbloodpressure.html')]
field search title:asthma         HTTP 200 count 2, first (rank, page) [('0', 'asthma.html'), ('1', 'asthmainchildren.html')]
OR operator                       HTTP 200 count 12, first (rank, page) [('0', 'diabetesmedicines.html'), ('1', 'diabetestype2.html'), ('2', 'hyperglycemia.html')]
Spanish db, Spanish word          HTTP 200 count 64, first (rank, page) [('1', 'asthma.html'), ('0', 'asthmainchildren.html')]
Spanish db, English word          HTTP 200 count 19, first (rank, page) [('0', 'asthma.html'), ('1', 'asthmainchildren.html')]
misspelling asthmaa               HTTP 200 count 0, spellingCorrection 'asthma'
no match zzqxv                    HTTP 200 count 0
no db parameter                   HTTP 200 count 0
db=healthtopics (lower case)      HTTP 200 count 0
no term parameter                 HTTP 200 error-msg 'The “term” parameter is missing in your request. This is a required pa'
retstart=54 without file/server   HTTP 200 count 56, first (rank, page) [('54', 'noseinjuriesanddisorders.html'), ('55', 'rashes.html')]
expired/unknown file= paging      HTTP 400 text/html not XML: 'Expired Results Expired Results The results set that you were browsing'
```

### 3. Same lookups with Python urllib, robots check for every agent, 12 h disk cache (no browser)

Sends a descriptive User-Agent and a constant `tool=` (curl's default User-Agent also got HTTP 200). The cache is one XML file per URL. Run with an empty cache.

```python
import hashlib, os, re, sys, time, urllib.error, urllib.parse, urllib.request, urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

WS = "https://wsearch.nlm.nih.gov/ws/query"
TOOL = "medlineplus-skill-example"
UA = "medlineplus-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]
CACHE_DIR = "~/.cache/medlineplus-skill"
CACHE = os.path.expanduser(CACHE_DIR)
TTL = 12 * 3600  # NLM recommends caching results for 12-24 h (the server itself sends max-age=3600)
PAUSE = 1.0      # at most 85 requests per minute per IP; 1 s apart stays at or under 60
TOPIC_URL = re.compile(r"https://medlineplus\.gov/(spanish/)?[a-z0-9]+\.html")
calls = hits = 0

def retry_after(v):
    """Retry-After in seconds: a number or an HTTP date; 60 when absent or unreadable; at least 1. Over 120 s: exit."""
    try:
        s = float(v)
    except (TypeError, ValueError):
        try:
            s = (parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError):
            s = 60
    if s > 120:
        sys.exit(f"server asks to wait {s:.0f} s (over 120 s): stopping")
    return max(s, 1)

def search(term, db="healthTopics", retmax=10):
    """-> <nlmSearchResult> root, from the disk cache when younger than TTL. Once waits Retry-After (default 60 s)
    on 429/500/502/503/504 or a network error; exits on anything else and on an <error-msg> answer."""
    global calls, hits
    url = WS + "?" + urllib.parse.urlencode(dict(db=db, term=term, retmax=retmax, tool=TOOL))
    f = os.path.join(CACHE, hashlib.sha256(url.encode()).hexdigest() + ".xml")
    try:
        if time.time() - os.path.getmtime(f) < TTL:
            hits += 1
            return ET.parse(f).getroot()
    except (OSError, ET.ParseError):
        pass
    for attempt in range(2):
        time.sleep(PAUSE)
        calls += 1
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read()
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(retry_after(e.headers.get("Retry-After")))
                continue
            sys.exit(f"HTTP {e.code} {url}: {' '.join(e.read().decode(errors='replace').split())[:200]}")
        except OSError as e:  # URLError (DNS, refused connection), timeouts, resets
            if attempt == 0:
                time.sleep(60)
                continue
            sys.exit(f"{url}: {e}")
    root = ET.fromstring(body)
    if root.tag != "nlmSearchResult" or root.find("count") is None:
        sys.exit(f"{url}: {' '.join((root.findtext('error-msg') or body[:200].decode(errors='replace')).split())}")
    os.makedirs(CACHE, exist_ok=True)
    open(f, "wb").write(body)
    return root

class Text(HTMLParser):
    """HTML fragment -> plain text lines; every tag (the escaped qt0/qt1 highlight spans too) is dropped."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = [""]
    def handle_starttag(self, tag, attrs):
        if tag in ("p", "li", "ul", "ol", "br"):
            self.out.append("- " if tag == "li" else "")
    def handle_endtag(self, tag):
        if tag in ("p", "li", "ul", "ol"):
            self.out.append("")
    def handle_data(self, d):
        self.out[-1] += d

def plain(fragment):
    t = Text()
    t.feed(fragment or "")
    t.close()
    return [" ".join(x.split()) for x in t.out if x.strip(" -")]

def lookup(term, db="healthTopics"):
    """Condition words -> (count, best topic dict or None, term actually searched). Follows the service's
    spellingCorrection once. Best = title or alt-title equal to the words, else the first in server order."""
    root = search(term, db)
    if root.findtext("count") == "0" and root.findtext("spellingCorrection"):
        term = root.findtext("spellingCorrection")
        root = search(term, db)
    docs = []
    for d in root.iter("document"):
        if not TOPIC_URL.fullmatch(d.get("url", "")):
            sys.exit(f"unexpected non-health-topic URL {d.get('url')!r}: stopping")  # never return encyclopedia/drug text
        f = {}
        for c in d.findall("content"):
            f.setdefault(c.get("name"), []).append(c.text or "")
        s = (f.get("FullSummary") or [""])[0]
        paras = [plain(p) for p in re.findall(r"<p>(.*?)</p>", s, re.S)]
        docs.append(dict(url=d.get("url"), title=" ".join(plain(f["title"][0])),
                         alt=[" ".join(plain(a)).lower() for a in f.get("altTitle", [])],
                         lead=next((p[0] for p in paras if p), (plain(s) or [""])[0]), chars=len(" ".join(plain(s)))))
    key = " ".join(term.lower().split())
    best = next((d for d in docs if key == d["title"].lower() or key in d["alt"]), docs[0] if docs else None)
    return int(root.findtext("count")), best, term

# robots.txt: wsearch.nlm.nih.gov answers 404 (RobotFileParser.read() treats a 4xx other than 401/403 as allow-all,
# RFC 9309 section 2.3.1.3); medlineplus.gov has one '*' group. Check both for every agent.
for host, paths in (("https://wsearch.nlm.nih.gov", ["/ws/query?db=healthTopics&term=x"]),
                    ("https://medlineplus.gov", ["/asthma.html", "/spanish/asthma.html"])):
    rp = urllib.robotparser.RobotFileParser(host + "/robots.txt")
    try:
        with urllib.request.urlopen(urllib.request.Request(rp.url, headers={"User-Agent": UA}), timeout=30) as r:
            print(f"{host}/robots.txt: HTTP {r.status}")
    except urllib.error.HTTPError as e:
        print(f"{host}/robots.txt: HTTP {e.code}")
    rp.read()
    for p in paths:
        ok = all(rp.can_fetch(a, host + p) for a in AGENTS)
        print(f"  robots {p:<34} {'allowed' if ok else 'DISALLOWED'} for all {len(AGENTS)} agents")
        if not ok:
            sys.exit("robots.txt now disallows a path this skill uses: stop")

now = datetime.now(timezone.utc)
print(f"\nMedlinePlus health topics, queried {now:%Y-%m-%d %H:%M} UTC")
for term, db in [("asthma", "healthTopics"), ("type 2 diabetes", "healthTopics"), ("heart attack", "healthTopics"),
                 ("migrane", "healthTopics"), ("sprained ankle", "healthTopics"), ("zzqxv", "healthTopics"),
                 ("diabetes", "healthTopicsSpanish")]:
    count, best, used = lookup(term, db)
    fixed = f" (searched {used!r})" if used != term else ""
    if not best:
        print(f"  {term!r:<18}{fixed} 0 topics")
        continue
    print(f"  {term!r:<18}{fixed} {count:>3} topics -> {best['title']!r} {best['url']} ({best['chars']:,} chars)")
    print(f"      {best['lead'][:110]}...")

n1 = calls
lookup("asthma")
lookup("heart attack")
print(f"\nnetwork calls {n1}, then {calls - n1} more for 2 repeated lookups (cache hits so far: {hits}, cache {CACHE_DIR})")
print("Source: MedlinePlus, National Library of Medicine. General health information, not medical advice.")
```

Output (from the run on 2026-11-18, 00:07 UTC):

```text
https://wsearch.nlm.nih.gov/robots.txt: HTTP 404
  robots /ws/query?db=healthTopics&term=x   allowed for all 11 agents
https://medlineplus.gov/robots.txt: HTTP 200
  robots /asthma.html                       allowed for all 11 agents
  robots /spanish/asthma.html               allowed for all 11 agents

MedlinePlus health topics, queried 2026-11-18 00:07 UTC
  'asthma'            56 topics -> 'Asthma' https://medlineplus.gov/asthma.html (5,180 chars)
      Asthma is a chronic (long-term) lung disease. It affects your airways, the tubes that carry air in and out of ...
  'type 2 diabetes'   92 topics -> 'Diabetes Type 2' https://medlineplus.gov/diabetestype2.html (4,406 chars)
      Type 2 diabetes is a disease in which your blood glucose, or blood sugar, levels are too high. Glucose is your...
  'heart attack'      94 topics -> 'Heart Attack' https://medlineplus.gov/heartattack.html (4,033 chars)
      A heart attack, also called a myocardial infarction, is a type of heart disease. It happens when blood flow to...
  'migrane'          (searched 'migraines')  15 topics -> 'Migraine' https://medlineplus.gov/migraine.html (5,129 chars)
      Migraines are a recurring type of headache. They cause moderate to severe pain that is throbbing or pulsing. T...
  'sprained ankle'     2 topics -> 'Ankle Injuries and Disorders' https://medlineplus.gov/ankleinjuriesanddisorders.html (587 chars)
      Your ankle bone and the ends of your two lower leg bones make up the ankle joint. Your ligaments, which connec...
  'zzqxv'            0 topics
  'diabetes'         276 topics -> 'Diabetes' https://medlineplus.gov/spanish/diabetes.html (6,456 chars)
      La diabetes, también conocida como diabetes mellitus, es una enfermedad en la que los niveles de glucosa (o az...

network calls 8, then 0 more for 2 repeated lookups (cache hits so far: 2, cache ~/.cache/medlineplus-skill)
Source: MedlinePlus, National Library of Medicine. General health information, not medical advice.
```

### 4. curl, headers and mistakes

```bash
B=https://wsearch.nlm.nih.gov/ws/query
T=tool=medlineplus-skill-example
# condition words -> count and the first topic's URL and title (spaces are sent as +, an AND)
curl -sS --fail -G "$B" -d db=healthTopics --data-urlencode "term=asthma" -d retmax=1 -d "$T" \
  | python3 -c 'import re, sys, xml.etree.ElementTree as E
r = E.parse(sys.stdin).getroot(); d = r.find("list/document"); c = {x.get("name"): x.text for x in d}
strip = lambda s: re.sub(r"<[^>]+>", "", s)  # the qt0/qt1 highlight spans
print(r.findtext("count"), "topics;", d.get("url"), "|", strip(c["title"]), "|", strip(re.search(r"<p>(.*?)</p>", c["FullSummary"], re.S)[1])[:90])'
sleep 1
# the raw XML: highlight spans arrive escaped inside the text
curl -sS --fail "$B?db=healthTopics&term=asthma&retmax=1&$T" | grep -m1 -o '<content name="title">[^<]*</content>'
sleep 1
# headers: content type and caching; no CORS allow-origin
curl -sS -D - -o /dev/null "$B?db=healthTopics&term=asthma&retmax=1&$T" | tr -d '\r' \
  | grep -iE '^(HTTP/|(content-type|cache-control|access-control-allow-origin|retry-after|x-ratelimit-limit):)'
sleep 1
# mistakes: a typo is HTTP 200 count 0 with a suggestion; a missing db is a silent count 0; a missing term is an error-msg
curl -sS -w ' <- HTTP %{http_code}\n' "$B?db=healthTopics&term=asthmaa&$T" | tr -d '\n'; echo
sleep 1
curl -sS -w ' <- HTTP %{http_code}\n' "$B?term=asthma&$T" | tr -d '\n'; echo
sleep 1
curl -sS -w ' <- HTTP %{http_code}\n' "$B?db=healthTopics&$T" | tr -s ' \n' ' '; echo
```

Output (from the run on 2026-11-18, 00:08 UTC):

```text
56 topics; https://medlineplus.gov/asthma.html | Asthma | Asthma is a chronic (long-term) lung disease. It affects your airways, the tubes that carr
<content name="title">&lt;span class="qt0"&gt;Asthma&lt;/span&gt;</content>
HTTP/2 200 
content-type: text/xml; charset=UTF-8
cache-control: max-age=3600, public
<?xml version="1.0" encoding="UTF-8"?><nlmSearchResult>  <term>asthmaa</term>  <count>0</count>  <spellingCorrection>asthma</spellingCorrection></nlmSearchResult> <- HTTP 200
<?xml version="1.0" encoding="UTF-8"?><nlmSearchResult>  <term>asthma</term>  <count>0</count></nlmSearchResult> <- HTTP 200
<?xml version="1.0" encoding="UTF-8"?> <nlmSearchResult> <error-msg> The “term” parameter is missing in your request. This is a required parameter. See the MedlinePlus Web service documentation for more information about using the Web service. </error-msg> </nlmSearchResult> <- HTTP 200 
```

## Fields (`/ws/query`, default `rettype=brief`)

| Element / parameter | Value | Notes |
|---|---|---|
| `db` | `healthTopics` or `healthTopicsSpanish` | case-sensitive; missing or wrong -> HTTP 200 `count` 0, no error |
| `term` | words, `"phrase"` (`%22`), `+OR+`, `title:`, `alt-title:`, `mesh:`, `full-summary:`, `group:` | spaces (or `+`) are AND. Missing -> `<error-msg>` |
| `retmax`, `retstart` | default 10, 0 | `retmax=500` returned 500 documents (2.4 MB) for `term=a` (1,016 topics); no cap documented. `retstart` works with `db`+`term` alone (no `file`/`server` needed) |
| `file`, `server` | from the first answer | for paging the doc's way; the file expires. The doc says "the XML output will contain an error message", but the live answer was HTTP 400 HTML "Expired Results" |
| `rettype` | `brief` (default), `topic`, `all` | `topic` returns the full XML record, including 93 `site` links for asthma, some to `medlineplus.gov/ency/` (A.D.A.M., copyrighted). This skill uses `brief` only |
| `tool`, `email` | optional | NLM encourages both; the blocks send `tool` only |
| `<count>` | integer | all matches; `<list num="56" start="0" per="10">` repeats it |
| `<spellingCorrection>` | text | only when present; "asthmaa" -> "asthma", "migrane" -> "migraines" |
| `<document rank url>` | rank, health topic URL | document order is the result order; `rank` can be 1 for the first |
| `content name=` | `title`, `organizationName`, `altTitle` (0..n), `FullSummary`, `mesh` (English only), `groupName` (1..n), `snippet` | `organizationName` is "National Library of Medicine" (Spanish: "Biblioteca Nacional de Medicina"). All text fields carry the highlight spans |
| response headers | `Content-Type: text/xml; charset=UTF-8`, `Cache-Control: max-age=3600, public` | no `Access-Control-Allow-Origin` (even with an `Origin` header), no rate-limit headers seen |

## Gotchas

- **Highlight spans are in every text field**, escaped in the XML so a parser hands them back as literal `<span class="qt0">` text. Strip all tags, not just one class: the class number follows the query word (`qt0`, `qt1`, ...) and spans nest. Keep spaces: some spans hold only a space.
- **The summary starts with a question.** `FullSummary` begins with an untagged heading ("What is asthma?") and then `<p>` paragraphs and lists. Blocks 1 and 3 print the first `<p>` as the lead ("Asthma is a chronic (long-term) lung disease...") and keep the rest as lines.
- **Server order and `rank` disagree.** For "asthma" the order is rank 1, 0, 2, 3...; the doc says title or alt-title matches are boosted "regardless of the rank". Use document order, and match the title or alt-title yourself: "high blood pressure" put "How to Prevent High Blood Pressure" first; the `"high blood pressure"` phrase search put the topic first (97 matches). The alt-titles carry lay and clinical names ("Hypertension", "HBP" for High Blood Pressure; "MI", "Myocardial Infarction" for Heart Attack).
- **Spelling suggestions are not exact titles.** "migrane" suggested "migraines" (plural), which matches no title exactly, so block 3 fell back to the first result (Migraine). Print what was actually searched, as the blocks do.
- **Broad matching.** Words match the whole record, summary included: "asthma" also returns Flu, Smoking, Caffeine and Climate Change. "sprained ankle" returned only 2 topics, the first "Ankle Injuries and Disorders" with a 587-character summary. Read the title before you quote the summary.
- **Spanish.** `db=healthTopicsSpanish` takes Spanish words ("asma" -> 64) and returns `medlineplus.gov/spanish/...` pages; English "asthma" there returned only 19. `mesh` is not in Spanish records.
- **Only health topics.** The Web Service page says it "provides access to MedlinePlus health topic data" (Genetics has its own data files and API); encyclopedia articles and drug pages are not search results here. All 500 URLs for `term=a` and every URL in these runs matched `https://medlineplus.gov/(spanish/)?<name>.html`; the blocks stop if one does not, so copyrighted A.D.A.M. or ASHP text is never returned.
- **Data changes Tuesday to Saturday.** Counts and summaries can move between days (the asthma count was 56 on both 2026-11-17 23:19 UTC and 2026-11-18 00:07 UTC). Store the access date with every answer.
- **Credit and no endorsement.** Show "Source: MedlinePlus, National Library of Medicine" with the topic link, no logo, and nothing that suggests MedlinePlus endorses your product.
- **Tab marker.** The harness sets the tab title to a horse emoji; the blocks check `location.origin` and the XML, not the title.

## What does not work

- **Cross-origin `fetch()`** from a page on another site: no `Access-Control-Allow-Origin` header, so the browser blocks the read. Fetch from a wsearch.nlm.nih.gov page (block 1) or outside the browser (blocks 3, 4).
- **Paging with an old `file=`**: HTTP 400 HTML "The results set that you were browsing has expired." Re-send `db`, `term` and `retstart` instead.
- **Not tested:** the over-limit response (never provoked; the policy says such requests "will not be serviced, and service will not be restored until the request rate falls beneath the limit", with no status code or wait time), `rettype=all`, `group:` field searches, the XML files and MedlinePlus Connect.
