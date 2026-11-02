# Google Patents - Title, Claims, Citations and Family of a Patent

Field-tested against patents.google.com on 2026-11-02 using a Browser Use cloud browser (logged out) and plain HTTP (Python urllib).

robots.txt (checked 2026-11-02) for `User-agent: *` is `Disallow: /*` with `Allow: /$`, `/advanced$`, `/patent/` and `/sitemap/`; this skill only requests `/patent/<number>/en` pages, so search (`/?q=...`) and the `/xhr/` endpoints are never used.

## Quick summary

- A patent page (`/patent/<publication number>/en`) is server-rendered HTML with schema.org microdata (`itemprop` attributes). Title, bibliographic data, every claim, every citation table and the family tables are all in that one document. No pagination: US7479949B2 lists 1,122 + 1,683 citing documents in one page.
- The browser block opens one patent page so the tab is on `patents.google.com`, then for each number calls `fetch('/patent/<number>/en')` inside the tab and parses the response with `DOMParser`. It does not read the rendered page: the Polymer app rewrites the DOM without the `itemprop` markup, and it only renders in a visible tab.
- The same pages return HTTP 200 over plain HTTP with a truthful User-Agent (`browser-harness-skill/1.0 (Python urllib)`). Block 2 parses them with the standard library only and produced a record identical to the browser's, key for key, for US6285999B1 and CN101861562A.
- Counts match what the page shows: the visible "Patent Citations (28)" on US6285999B1 is `citations` (7) + `citations_family` (21), and "Cited By (936)" is `cited_by` (817) + `cited_by_family` (119). CN101861562A: 1,050 and 2,806, also matching.
- Missing numbers return HTTP 404. A number without a kind code (`US7479949`) returns the granted document (`US7479949B2`). Numbers are case-sensitive: `us6285999b1` is a 404.
- Pages are large: 0.45 MB (US9876543B2) to 7.9 MB (US7479949B2), mostly image and definition markup. Keep at least 2 s between patents.
- Across about 25 browser page loads and in-page fetches and about 25 plain HTTP requests on 2026-11-02, at 1-2 s spacing: no 429, no CAPTCHA, no consent page.

## What works

### 1. Read a patent: title, claims, citations, family (browser)

Self-contained. `gp_open()` points the tab at a patent page and raises if it lands anywhere else. `gp_patent()` returns the full record (keys in Fields below), `None` for a 404, and raises on any other status, a failed fetch, a redirect off `/patent/` (no challenge was seen in testing; Google's `/sorry/` page is on google.com, so a redirect there is expected to fail the fetch) or a page without the patent article. Nothing retries around a block.

```python
import json, os, tempfile, time

# robots.txt (User-agent: *) allows only /, /advanced, /patent/ and /sitemap/; every request below is a /patent/ page.
PATENT_JS = r"""
(async (num, lang) => {
  const url = `/patent/${encodeURIComponent(num)}/${lang}`;
  let r;
  try { r = await fetch(url); }
  catch (e) { return {error: `fetch failed (${e}); a cross-origin redirect here usually means a google.com/sorry challenge`}; }
  if (r.status === 404) return {not_found: true};
  if (r.status !== 200) return {error: `HTTP ${r.status}`};
  if (!new URL(r.url).pathname.startsWith('/patent/')) return {error: `redirected to ${r.url}`};
  const doc = new DOMParser().parseFromString(await r.text(), 'text/html');
  const art = doc.querySelector('article[itemtype$="ScholarlyArticle"]');
  if (!art) return {error: 'no patent article in the page'};
  const clean = s => (s || '').replace(/\s+/g, ' ').trim() || null;
  const txt = (root, sel) => { const e = root && root.querySelector(sel); return e ? clean(e.getAttribute('datetime') || e.textContent) : null; };
  const all = (root, sel) => [...root.querySelectorAll(sel)].map(e => clean(e.textContent)).filter(Boolean);
  const rows = (prop, fields) => [...doc.querySelectorAll(`tr[itemprop="${prop}"]`)].map(tr => {
    const o = {};
    for (const f of fields) o[f] = f === 'examinerCited' ? !!tr.querySelector('[itemprop=examinerCited]') : txt(tr, `[itemprop=${f}]`);
    return o;
  });
  const CIT = ['publicationNumber', 'examinerCited', 'priorityDate', 'publicationDate', 'assigneeOriginal', 'title'];
  const APP = ['applicationNumber', 'ifiStatus', 'representativePublication', 'priorityDate', 'filingDate', 'title'];

  // Claims: the innermost element carrying a claim number. Markup differs by office
  // (div.claim[num], <claim num>, li.claim > div.claim). Machine translations keep the
  // source-language text in .google-src-text; drop it so only the English text remains.
  const cs = doc.querySelector('section[itemprop=claims]');
  let claims = [];
  if (cs) {
    cs.querySelectorAll('.google-src-text').forEach(e => e.remove());
    const sel = 'claim[num], div.claim[num]';
    claims = [...cs.querySelectorAll(sel)].filter(e => !e.querySelector(sel)).map(e => ({
      num: parseInt(e.getAttribute('num'), 10),
      text: clean(e.textContent),
      marked_dependent: !!(e.closest('.claim-dependent') || e.querySelector('claim-ref')),
    }));
  }
  const fam = doc.querySelector('section[itemprop=family]');
  const famId = fam ? [...fam.querySelectorAll('h2')].map(h => h.textContent.match(/ID=(\d+)/)).find(Boolean) : null;
  return {
    number: txt(art, 'dd[itemprop=publicationNumber]'),
    title: txt(art, ':scope > span[itemprop=title]'),
    url: r.url,
    pdf: art.querySelector('a[itemprop=pdfLink]')?.href || null,
    status: txt(art, '[itemprop=legalStatusIfi] [itemprop=status]'),
    inventors: all(art, 'dd[itemprop=inventor]'),
    assignee_original: all(art, 'dd[itemprop=assigneeOriginal]'),
    assignee_current: all(art, 'dd[itemprop=assigneeCurrent]'),
    application_number: txt(art, ':scope > dd[itemprop=applicationNumber]'),
    priority_date: txt(art, 'time[itemprop=priorityDate]'),
    filing_date: txt(art, 'time[itemprop=filingDate]'),
    publication_date: txt(art, 'time[itemprop=publicationDate]'),
    abstract: txt(doc, 'section[itemprop=abstract] [itemprop=content]'),
    claims_count: parseInt(txt(doc, 'section[itemprop=claims] h2 [itemprop=count]'), 10) || null,
    claims,
    citations: rows('backwardReferencesOrig', CIT),           // documents this publication cites
    citations_family: rows('backwardReferencesFamily', CIT),  // "Family To Family Citations"
    citations_non_patent: all(doc, 'tr[itemprop=detailedNonPatentLiterature] [itemprop=title]'),
    cited_by: rows('forwardReferencesOrig', CIT),             // later documents citing this one
    cited_by_family: rows('forwardReferencesFamily', CIT),    // "Families Citing this family"
    family_id: famId ? famId[1] : null,
    family_applications: rows('applications', APP),
    family_before: rows('beforeApplications', APP),
    family_after: rows('afterApplications', APP),
    also_published_as: rows('docdbFamily', ['publicationNumber', 'publicationDate']),
    country_status: rows('countryStatus', ['countryCode', 'num', 'representativePublication']),
    priority_applications: rows('priorityApps', APP),
  };
})
"""

def gp_open(num):
    """Point the tab at a patent page (any /patent/ page works as the origin for gp_patent)."""
    goto_url(f"https://patents.google.com/patent/{num}/en")
    wait_for_load()
    time.sleep(2)
    href = js("location.href")
    if not href.startswith("https://patents.google.com/patent/"):
        raise RuntimeError(f"tab landed on {href}, not a patent page (challenge or redirect). Stop and tell the user.")

def gp_patent(num, lang="en"):
    """Full record for one publication number ('US6285999B1'), or None when Google Patents returns 404.
    Runs fetch() inside the attached patents.google.com tab and parses the server-rendered page."""
    rec = js(f"{PATENT_JS}({json.dumps(num)}, {json.dumps(lang)})")
    if rec.get("not_found"):
        return None
    if "error" in rec:
        raise RuntimeError(f"{num}: {rec['error']}. Stop and tell the user; do not retry around it.")
    return rec

new_tab("about:blank")
gp_open("US6285999B1")

# --- 1) one patent, read in full ---
p = gp_patent("US6285999B1")
print(p["number"], "|", p["title"], "|", p["status"], "| priority", p["priority_date"], "| published", p["publication_date"])
print("inventors:", p["inventors"], "| original assignee:", p["assignee_original"], "| application:", p["application_number"])
print(f'claims: {p["claims_count"]} listed, {len(p["claims"])} parsed, not marked dependent:',
      [c["num"] for c in p["claims"] if not c["marked_dependent"]])
print("claim 1:", p["claims"][0]["text"][:200])
print(f'citations: {len(p["citations"])} + {len(p["citations_family"])} family-to-family, {len(p["citations_non_patent"])} non-patent')
for c in p["citations"][:3]:
    print("  ", c["publicationNumber"], "examiner-cited" if c["examinerCited"] else "not marked", c["publicationDate"], c["assigneeOriginal"], "|", c["title"])
print(f'cited by: {len(p["cited_by"])} + {len(p["cited_by_family"])} family-to-family')
print("family", p["family_id"], "| applications:", len(p["family_applications"]),
      "| also published as:", [r["publicationNumber"] for r in p["also_published_as"]])
for a in p["family_applications"][:3]:
    print("  ", a["applicationNumber"], a["ifiStatus"], a["representativePublication"], a["filingDate"], "|", a["title"])
out = os.path.join(tempfile.gettempdir(), f'{p["number"]}.json')
with open(out, "w") as f:
    json.dump(p, f, indent=1, ensure_ascii=False)
print("saved full record:", os.path.basename(out), "in tempfile.gettempdir()")

# --- 2) other offices (EP, machine-translated CN, WIPO), a number without kind code, and one that does not exist ---
for num in ["EP2541389B1", "CN101861562A", "WO2008030976A2", "US7479949", "US99999999B9"]:
    time.sleep(2)
    q = gp_patent(num)
    if q is None:
        print(f"{num}: not found (HTTP 404)")
        continue
    print(f'{num} -> {q["number"]} | {q["title"][:70]} | {q["status"]} | claims {q["claims_count"]}/{len(q["claims"])} '
          f'| cites {len(q["citations"])}+{len(q["citations_family"])} | cited by {len(q["cited_by"])}+{len(q["cited_by_family"])} '
          f'| family {q["family_id"]}, {len(q["also_published_as"])} publications, '
          f'{len(q["country_status"])} countries')
```

Output (from the run on 2026-11-02):

```text
US6285999B1 | Method for node ranking in a linked database | Expired - Lifetime | priority 1997-01-10 | published 2001-09-04
inventors: ['Lawrence Page'] | original assignee: ['Leland Stanford Junior University'] | application: US09/004,827
claims: 29 listed, 29 parsed, not marked dependent: [1, 8, 9, 10, 18, 19]
claim 1: 1. A computer implemented method of scoring a plurality of linked documents, comprising: obtaining a plurality of documents, at least some of the documents being linked documents, at least some of the
citations: 7 + 21 family-to-family, 20 non-patent
   US4953106A examiner-cited 1990-08-28 At&T Bell Laboratories | Technique for drawing directed graphs
   US5450535A examiner-cited 1995-09-12 At&T Corp. | Graphs employing clusters
   US5748954A not marked 1998-05-05 Carnegie Mellon University | Method for searching a queued and ranked constructed catalog of files stored on a network
cited by: 817 + 119 family-to-family
family 26673538 | applications: 10 | also published as: ['US8131715B1', 'US8521730B1', 'US7058628B1', 'US6799176B1', 'US7908277B1', 'US8126884B1', 'US8195651B1', 'US8131717B1', 'US8725726B1']
   US09/004,827 Expired - Lifetime US6285999B1 1998-01-09 | Method for node ranking in a linked database
   US09/895,174 Expired - Lifetime US7058628B1 2001-07-02 | Method for node ranking in a linked database
   US09/899,068 Expired - Lifetime US6799176B1 2001-07-06 | Method for scoring documents in a linked database
saved full record: US6285999B1.json in tempfile.gettempdir()
EP2541389B1 -> EP2541389B1 | Soft keyboard display for portable multifunction device | Active | claims 13/13 | cites 0+1050 | cited by 0+2805 | family 39092692, 86 publications, 10 countries
CN101861562A -> CN101861562A | Touch screen device, method and graphical user interface for determini | Granted | claims 45/45 | cites 0+1050 | cited by 61+2745 | family 39092692, 86 publications, 10 countries
WO2008030976A2 -> WO2008030976A2 | Touch screen device, method, and graphical user interface for determin | Ceased | claims None/45 | cites 0+1050 | cited by 168+2637 | family 39092692, 86 publications, 10 countries
US7479949 -> US7479949B2 | Touch screen device, method, and graphical user interface for determin | Active | claims 20/20 | cites 49+1001 | cited by 1122+1683 | family 39092692, 86 publications, 10 countries
US99999999B9: not found (HTTP 404)
```

### 2. Same record over plain HTTP (no browser)

Self-contained, Python standard library only. `html.parser` builds a small tree and the same `itemprop` lookups run on it, so the keys and values match block 1 (block 1 also has `pdf`, `assignee_current`, `application_number`, `abstract`, `family_before`, `family_after`). `fetch()` returns `None` on 404 and raises on any other status or on a redirect off `/patent/`; it does not retry. Parsing a 7.9 MB page takes a few seconds.

```python
import json, re, time, urllib.error, urllib.parse, urllib.request
from html.parser import HTMLParser

# robots.txt (User-agent: *) allows only /, /advanced, /patent/ and /sitemap/; this only requests /patent/ pages.
UA = {"User-Agent": "browser-harness-skill/1.0 (Python urllib)", "Accept-Language": "en-US,en;q=0.9"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

class Node:
    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.parent, self.kids = tag, dict(attrs), parent, []
    def text(self):
        out = []
        def walk(n):
            for k in n.kids:
                if isinstance(k, str):
                    out.append(k)
                elif "google-src-text" not in (k.attrs.get("class") or "").split():  # drop machine-translation source text
                    walk(k)
        walk(self)
        return re.sub(r"\s+", " ", "".join(out)).strip() or None
    def find_all(self, pred):
        for k in self.kids:
            if isinstance(k, Node):
                if pred(k):
                    yield k
                yield from k.find_all(pred)
    def find(self, pred):
        return next(self.find_all(pred), None)
    def has_class(self, c):
        return c in (self.attrs.get("class") or "").split()

class Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = self.cur = Node("#root", [], None)
    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs, self.cur)
        self.cur.kids.append(n)
        if tag not in VOID:
            self.cur = n
    def handle_startendtag(self, tag, attrs):
        self.cur.kids.append(Node(tag, attrs, self.cur))
    def handle_endtag(self, tag):
        n = self.cur
        while n is not None and n.tag != tag:
            n = n.parent
        if n is not None and n.parent is not None:  # close the matching open tag; ignore stray end tags
            self.cur = n.parent
    def handle_data(self, data):
        self.cur.kids.append(data)

def prop(name, tag=None):
    return lambda n: n.attrs.get("itemprop") == name and (tag is None or n.tag == tag)

def val(root, name, tag=None):
    n = root.find(prop(name, tag)) if root else None
    return (n.attrs.get("datetime") or n.text()) if n else None

def rows(doc, name, fields):
    out = []
    for tr in doc.find_all(prop(name, "tr")):
        out.append({f: (tr.find(prop(f)) is not None) if f == "examinerCited" else val(tr, f) for f in fields})
    return out

CIT = ["publicationNumber", "examinerCited", "priorityDate", "publicationDate", "assigneeOriginal", "title"]
APP = ["applicationNumber", "ifiStatus", "representativePublication", "priorityDate", "filingDate", "title"]

def fetch(url):
    """HTML for a /patent/ page, None on 404. Any other status, or a redirect off /patent/, raises: stop, do not retry around it."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
            final = r.geturl()
            if urllib.parse.urlparse(final).netloc != "patents.google.com" or not urllib.parse.urlparse(final).path.startswith("/patent/"):
                raise RuntimeError(f"redirected to {final} (challenge?). Stop.")
            return r.read().decode("utf-8", "replace"), final
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, url
        raise RuntimeError(f"HTTP {e.code} for {url}. Stop and back off; do not retry around it.") from e

def gp_patent_http(num, lang="en"):
    html, final = fetch(f"https://patents.google.com/patent/{urllib.parse.quote(num)}/{lang}")
    if html is None:
        return None
    t = Tree(); t.feed(html); doc = t.root
    art = doc.find(lambda n: n.tag == "article" and (n.attrs.get("itemtype") or "").endswith("ScholarlyArticle"))
    if art is None:
        raise RuntimeError(f"{num}: no patent article in the page. Stop.")
    top_title = next((k for k in art.kids if isinstance(k, Node) and k.attrs.get("itemprop") == "title"), None)
    cs = doc.find(prop("claims", "section"))
    claims = []
    if cs:
        is_claim = lambda n: "num" in n.attrs and (n.tag == "claim" or (n.tag == "div" and n.has_class("claim")))
        for c in cs.find_all(is_claim):
            if c.find(is_claim):
                continue  # keep the innermost numbered claim element
            dep, p = False, c.parent
            while p is not None and not dep:
                dep, p = p.has_class("claim-dependent"), p.parent
            claims.append({"num": int(c.attrs["num"]), "text": c.text(),
                           "marked_dependent": dep or c.find(lambda n: n.tag == "claim-ref") is not None})
    fam = doc.find(prop("family", "section"))
    fam_id = None
    for h in (fam.find_all(lambda n: n.tag == "h2") if fam else []):
        m = re.search(r"ID=(\d+)", h.text() or "")
        if m:
            fam_id = m.group(1); break
    count = val(cs, "count") if cs else None
    return {
        "number": val(art, "publicationNumber", "dd"),
        "title": top_title.text() if top_title else None,
        "url": final,
        "status": val(art.find(prop("legalStatusIfi")), "status"),
        "inventors": [n.text() for n in art.find_all(prop("inventor", "dd"))],
        "assignee_original": [n.text() for n in art.find_all(prop("assigneeOriginal", "dd"))],
        "priority_date": val(art, "priorityDate", "time"),
        "filing_date": val(art, "filingDate", "time"),
        "publication_date": val(art, "publicationDate", "time"),
        "claims_count": int(count) if count and count.isdigit() else None,
        "claims": claims,
        "citations": rows(doc, "backwardReferencesOrig", CIT),
        "citations_family": rows(doc, "backwardReferencesFamily", CIT),
        "citations_non_patent": [val(tr, "title") for tr in doc.find_all(prop("detailedNonPatentLiterature", "tr"))],
        "cited_by": rows(doc, "forwardReferencesOrig", CIT),
        "cited_by_family": rows(doc, "forwardReferencesFamily", CIT),
        "family_id": fam_id,
        "family_applications": rows(doc, "applications", APP),
        "also_published_as": rows(doc, "docdbFamily", ["publicationNumber", "publicationDate"]),
        "country_status": rows(doc, "countryStatus", ["countryCode", "num", "representativePublication"]),
        "priority_applications": rows(doc, "priorityApps", APP),
    }

for num in ["US6285999B1", "EP2541389B1", "US99999999B9"]:
    p = gp_patent_http(num)
    time.sleep(2)
    if p is None:
        print(num, "-> not found (HTTP 404)")
        continue
    print(json.dumps({
        "number": p["number"], "title": p["title"], "status": p["status"], "inventors": p["inventors"],
        "claims_count": p["claims_count"], "claims_parsed": len(p["claims"]),
        "marked_dependent": sum(c["marked_dependent"] for c in p["claims"]),
        "citations": len(p["citations"]), "citations_family": len(p["citations_family"]),
        "citations_non_patent": len(p["citations_non_patent"]),
        "cited_by": len(p["cited_by"]), "cited_by_family": len(p["cited_by_family"]),
        "family_id": p["family_id"], "also_published_as": [r["publicationNumber"] for r in p["also_published_as"]][:5],
        "priority_applications": [r["applicationNumber"] for r in p["priority_applications"]][:3],
    }, ensure_ascii=False))
```

Output (from the run on 2026-11-02):

```text
{"number": "US6285999B1", "title": "Method for node ranking in a linked database", "status": "Expired - Lifetime", "inventors": ["Lawrence Page"], "claims_count": 29, "claims_parsed": 29, "marked_dependent": 23, "citations": 7, "citations_family": 21, "citations_non_patent": 20, "cited_by": 817, "cited_by_family": 119, "family_id": "26673538", "also_published_as": ["US8131715B1", "US8521730B1", "US7058628B1", "US6799176B1", "US7908277B1"], "priority_applications": ["US09/004,827", "US09/895,174", "US09/899,068"]}
{"number": "EP2541389B1", "title": "Soft keyboard display for portable multifunction device", "status": "Active", "inventors": ["Bas Ording", "Kenneth Kocienda"], "claims_count": 13, "claims_parsed": 13, "marked_dependent": 11, "citations": 0, "citations_family": 1050, "citations_non_patent": 0, "cited_by": 0, "cited_by_family": 2805, "family_id": "39092692", "also_published_as": ["CA2658413C", "KR20120116996A", "KR20170101315A", "KR101462363B1", "US11029838B2"], "priority_applications": []}
US99999999B9 -> not found (HTTP 404)
```

## Fields

Record from `gp_patent()` / `gp_patent_http()`. "Row" means a `<tr itemprop="...">` of the server HTML; row fields are `publicationNumber`, `examinerCited` (bool), `priorityDate`, `publicationDate`, `assigneeOriginal`, `title` for citations, and `applicationNumber`, `ifiStatus`, `representativePublication`, `priorityDate`, `filingDate`, `title` for applications.

| Field | Source | Example (observed, US6285999B1) |
|---|---|---|
| `number` | `dd[itemprop=publicationNumber]` | `US6285999B1` |
| `title` | `span[itemprop=title]`, direct child of the `article` | `Method for node ranking in a linked database` |
| `status` | `[itemprop=legalStatusIfi] [itemprop=status]` | `Expired - Lifetime` (Google's assumption, not a legal conclusion) |
| `inventors`, `assignee_original` | `dd[itemprop=inventor]`, `dd[itemprop=assigneeOriginal]` | `["Lawrence Page"]`, `["Leland Stanford Junior University"]` |
| `priority_date`, `filing_date`, `publication_date` | `time[itemprop=...]` `datetime` | `1997-01-10`, `1998-01-09`, `2001-09-04` |
| `claims_count` | `section[itemprop=claims] h2 [itemprop=count]` | `29`; `None` when the heading has no count (WO2008030976A2) |
| `claims[]` | innermost `claim[num]` or `div.claim[num]` in the claims section | `{"num": 1, "text": "1. A computer implemented method ...", "marked_dependent": false}` |
| `citations` | rows `backwardReferencesOrig` | 7 rows; first `US4953106A`, examiner-cited |
| `citations_family` | rows `backwardReferencesFamily` ("Family To Family Citations") | 21 rows |
| `citations_non_patent` | `tr[itemprop=detailedNonPatentLiterature] [itemprop=title]` | 20 strings |
| `cited_by`, `cited_by_family` | rows `forwardReferencesOrig`, `forwardReferencesFamily` | 817, 119 rows |
| `family_id` | `ID=<n>` heading in `section[itemprop=family]` | `26673538` |
| `family_applications` | rows `applications` | 10 rows |
| `also_published_as` | rows `docdbFamily` (`publicationNumber`, `publicationDate`) | 9 rows, `US8131715B1` first |
| `country_status` | rows `countryStatus` (`countryCode`, `num`, `representativePublication`) | `[{"countryCode": "US", "num": "10", ...}]` |
| `priority_applications` | rows `priorityApps` | 12 rows |
| `url` | final URL of the fetch | `https://patents.google.com/patent/US6285999B1/en` |

## Gotchas

- **Read the server HTML, not the rendered page.** In the browser, the `itemprop` markup is gone after the app renders (`document.querySelectorAll('[itemprop=claims]')` is 0), and the rendered page shows family only as a "Worldwide applications" timeline of country codes. Fetching the same `/patent/` URL from inside the tab returns the original HTML (HTTP 200, `itemprop="claims"` present). CDP `Page.getResourceContent` on the main document failed with "Resource was not cached", so the in-page fetch is one extra GET per patent.
- **The app renders only in a visible tab.** In a background tab the URL and title were right but the page stayed 770 px tall with no headings; `activate_tab()` made it render. The blocks above do not depend on rendering.
- **Citations come in pairs.** The page's visible "Patent Citations (N)" and "Cited By (N)" each merge two tables: the document's own (`*Orig` rows) and "Family To Family" rows. The skill keeps them apart. The server HTML also has a `backwardReferences` table (same set as `backwardReferencesOrig` on the 3 patents checked) and a `forwardReferences` table ("Cited By (1663)" on US6285999B1, a superset of the 817 `forwardReferencesOrig` that matches no visible count); the skill does not use either.
- **Grants can have no citations of their own.** EP2541389B1 has 0 `citations` and 0 `cited_by`, but 1,050 and 2,805 family-to-family rows; the citations sit on other family members.
- **`examinerCited`** is the page's `*` mark ("Cited by examiner"). `False` means no mark, not necessarily applicant-cited; the page also defines a third-party mark that no tested patent used.
- **`marked_dependent` comes from markup only** (a `.claim-dependent` wrapper or a `claim-ref` element). US and EP claims carry it (US6285999B1: 23 of 29 marked). WIPO OCR claims (WO2008030976A2) carry none, so all 45 read as not dependent; machine-translated CN claims are partly marked. Do not treat unmarked as independent without reading the text ("The method of claim 1, ...").
- **Machine translations.** On CN101861562A the claims are "Translated from Chinese" and each segment holds the source text in `.google-src-text`; both blocks drop it, so `text` is English only. Remove that step if you need the original.
- **Kind codes.** `US7479949` returned the B2 grant, but which document a bare number picks is Google's choice; pass the full number (`US7479949B2`, `US20080122796A1`) when it matters. Use upper case.
- **Plain urllib, not the harness `http_get`.** `http_get` can route through a proxy when `BROWSER_USE_API_KEY` is set, which can change status behaviour; block 2 calls urllib directly so 404 and 429 are seen as they are.
- **Harness tab marker.** While attached, the harness prefixes the tab title with a horse emoji; read `title` from the record, not `document.title`.
- **Pacing.** 2 s between patents was never throttled today. A 429 or any other non-200, non-404 status raises in both blocks, and so does a redirect off `/patent/` (a `google.com/sorry` challenge was not triggered in testing): stop and tell the user.

## What does not work

- **Search**: result pages (`/?q=...`) and the app's data endpoints (`/xhr/query`, `/xhr/result`) are disallowed by robots.txt (`Disallow: /*`, only `/$`, `/advanced$`, `/patent/`, `/sitemap/` allowed). Start from publication numbers you already have, or from the numbers inside a record (`also_published_as`, `cited_by`, `family_applications`).
- **PDF and images**: `pdf` links to `patentimages.storage.googleapis.com`, a different host; not fetched or tested here.
- **Description text, classifications, legal events**: present in the same HTML (`section[itemprop=description]`, `classifications`, `legalEvents` rows) but not extracted or checked by this skill.
- **Other page languages** (`/patent/<number>/de` etc.): not tested; the blocks use `/en`.
- **Login-only features** (saved searches, alerts) were not attempted; this skill covers public logged-out pages only.
