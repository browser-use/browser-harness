# UniProt - Find the Reviewed Human TP53 Protein and Report Its Accession, Length and Function (REST API, no key)

Field-tested against rest.uniprot.org on 2026-11-14 using a fresh Browser Use cloud browser (logged out) plus Python `urllib` and `curl` from a Linux machine. 8 browser page loads (API JSON pages and both robots files) and 39 in-page `fetch()` calls, 36 curl calls and 6 urllib calls to rest.uniprot.org and www.uniprot.org, all serial at 1 s or more spacing: every call was HTTP 200 except the deliberate HTTP 400 probes and the HTTP 303 redirect of an old accession below. No 429, no challenge, no key, no login.

robots.txt (checked 2026-11-14, curl and the cloud browser): https://rest.uniprot.org/robots.txt has one group, `User-agent: *`, disallowing `/docs/`, `/idmapping/` and the `/stream/` path of 13 data sets (`/uniprotkb/stream/`, `/uniref/stream/`, `/uniparc/stream/`, `/taxonomy/stream/` and 9 more). No named AI-agent groups, so GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider fall under `*` and may fetch the `/uniprotkb/search` and `/uniprotkb/<accession>.json` paths used here (block 3 checks all 11 with `urllib.robotparser`). https://www.uniprot.org/robots.txt disallows `/blast/`, `/align/`, `/peptide-search/`, `/id-mapping/` and `/basket/` for `*`; this skill never loads www.uniprot.org pages, ID mapping or any stream endpoint. Licence: https://www.uniprot.org/help/license ("lastModified" 2024-12-18): "We have chosen to apply the Creative Commons Attribution 4.0 International (CC BY 4.0) License to all copyrightable parts of our databases." The same page: "We make no warranties regarding the correctness of the data" and "Any medical or genetic information is provided for research, educational and informational purposes only. It is not in any way intended to be used as a substitute for professional medical advice, diagnosis, treatment or care." UniProt names EMBL-EBI as one of its host institutions (https://www.uniprot.org/help/about), and the EMBL-EBI Terms of Use (https://www.ebi.ac.uk/about/terms-of-use, "Last revised: 14th October 2026") say: "EMBL-EBI expects attribution (e.g. in publications, services or products) for the use of any of its Data Resources and Tools in accordance with good scientific practice" and "Any attempt to use EMBL-EBI Data Resources and Tools to a level that prevents, or is likely to prevent, EMBL-EBI providing services to others, will result in the user being blocked." The programmatic access page calls the REST API "RESTful URLs that can be bookmarked, linked and used in programs". No AI/ML, scraping, automated-access or non-commercial clause in either. Naming: this skill writes "UniProt" and "UniProtKB" as plain text, cites the UniProt Consortium and the release, and uses no UniProt or EMBL-EBI logo. This skill is not affiliated with or endorsed by UniProt or EMBL-EBI.

**Attribution:** cite "UniProt Consortium", the UniProtKB release from the `x-uniprot-release` header (2026_04 here), the accession and entry version, and the licence (CC BY 4.0). For a publication, https://www.uniprot.org/help/publications says "please consider citing our latest publication" and names The UniProt Consortium, "UniProt: the Universal Protein Knowledgebase in 2025", Nucleic Acids Res. 53:D609-D617 (2025), https://doi.org/10.1093/nar/gkae1010 Block 1 prints a source line.

## Quick summary

- **No scraping.** `GET https://rest.uniprot.org/uniprotkb/search?query=gene:TP53+AND+organism_id:9606+AND+reviewed:true&fields=accession,protein_name,length,cc_function&format=json&size=5` returns the one entry. `GET /uniprotkb/P04637.json?fields=accession,length,sequence` confirms it. No key, `access-control-allow-origin: *`.
- **Answer (UniProtKB release 2026_04, 04-November-2026; run 2026-11-14, 23:33 UTC):** the reviewed (Swiss-Prot) human TP53 entry is **P04637** (P53_HUMAN), "Cellular tumor antigen p53", **393 amino acids** (canonical isoform P04637-1; the entry lists 9 isoforms), protein existence "1: Evidence at protein level", entry version 316. **Function** (first sentence): "Multifunctional transcription factor that induces cell cycle arrest, DNA repair or apoptosis upon binding to its target DNA sequence." It "Acts as a tumor suppressor in many tumor types"; block 1 prints the whole FUNCTION comment.
- **`reviewed:true` is the filter that matters.** Human `gene:TP53` has 114 entries: 1 reviewed (Swiss-Prot) and 113 unreviewed (TrEMBL). Without `organism_id:9606` there are 34 reviewed TP53 entries (mouse P02340, rat P10361 ...). Free text `TP53` instead of `gene:TP53` finds 757 reviewed human entries, ranked TP53TG5 first.
- **Silent failure:** a wrong taxon id (`organism_id:96060`) is HTTP 200 with 0 results. Wrong field names are loud: `gen:TP53` and `fields=funtion` are HTTP 400 with a reason, `size=501` is HTTP 400 "'size' must be less than or equal to 500".
- **Paging** uses the `Link: <...>; rel="next"` header and an opaque cursor; https://www.uniprot.org/help/rest-api-headers says you "_need_ to read it from this response header". `x-total-results` gives the count. Blocks 1 and 3 follow it and check the total.
- **Rate limit:** none published for search or entry calls. Of the help pages read here (api_queries, api_retrieve_entries, rest-api-headers, pagination), only api_queries mentions 429, for the stream endpoint ("In the case of the stream API having too many requests a `429` status will be returned"), which robots.txt disallows anyway. EMBL-EBI blocks load that "prevents ... providing services to others". Blocks pace 1 s per call, serial, and wait 60 s once on 429/500/502/503/504.

## What works

### 1. The reviewed human TP53 entry, cross-checked against the entry (browser)

`on_rest_tab()` opens one logged-out rest.uniprot.org JSON page, so `fetch()` is same-origin and can read the `Link`, `x-total-results` and `x-uniprot-release` headers. `get()` returns parsed JSON and headers on HTTP 200, waits 60 s once on 429/500/502/503/504 and otherwise raises. `search()` follows the `Link` header to the end and checks the count against `x-total-results`. The block keeps only hits whose primary gene name and taxon match, requires exactly one, then re-reads the entry and checks accession, sequence length, release and function text.

```python
import json, re, textwrap, time, urllib.parse
from datetime import datetime, timezone

GENE = "TP53"      # HGNC gene symbol; the gene: field also matches synonyms (gene:p53 finds the same entry)
TAXON = 9606       # NCBI taxonomy id for Homo sapiens; organism_id is exact, organism_name is free text
FIELDS = "accession,id,protein_name,gene_primary,organism_name,organism_id,length,cc_function"

SITE = "https://rest.uniprot.org"
PAUSE = 1.0  # no published rate limit; EMBL-EBI blocks use "that prevents ... providing services to others". Keep calls serial.

def on_rest_tab():
    """fetch() runs same-origin from a logged-out rest.uniprot.org tab (a JSON page). Reuse it."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(SITE + "/uniprotkb/P04637?format=json&fields=accession")
    wait_for_load()
    body = js("document.body ? document.body.innerText : ''") or ""
    if js("location.origin") != SITE or '"primaryAccession"' not in body:
        raise RuntimeError(f"rest.uniprot.org did not serve an entry (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it. The API exposes Link, X-Total-Results
# and X-UniProt-Release to scripts (access-control-expose-headers), and same-origin fetch() can read them anyway.
START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit', headers: {Accept: 'application/json'}})
    .then(async r => { const h = {}; r.headers.forEach((v, k) => { h[k] = v; });
      window.__u[id] = {status: r.status, url: r.url, headers: h, text: await r.text()}; })
    .catch(e => { window.__u[id] = {status: 0, url: '', headers: {}, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

def get(url, timeout=60):
    """GET url from inside the tab -> (parsed JSON, headers). Waits 60 s once on 429/500/502/503/504 or a network error
    (429 = too many requests), raises on anything else (400 = bad query or field name, with a message)."""
    for attempt in range(2):
        rid = json.dumps(js(START_JS % json.dumps(url)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"{url}: no answer after {timeout}s")
            time.sleep(0.3)
        time.sleep(PAUSE)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(60)
            continue
        if r["status"] != 200 or "json" not in r["headers"].get("content-type", ""):
            raise RuntimeError(f"{url}: HTTP {r['status']} {' '.join(r['text'].split())[:200]!r}; stopping")
        return json.loads(r["text"]), r["headers"]

def search(query, fields, size=25):
    """All results of a UniProtKB search, following the Link rel="next" header page by page (the help page: the
    cursor "you _need_ to read it from this response header"). Checks the total against X-Total-Results."""
    url = SITE + "/uniprotkb/search?" + urllib.parse.urlencode(
        {"query": query, "fields": fields, "format": "json", "size": size})
    out, total, release, pages = [], None, None, 0
    while url:
        d, h = get(url)
        pages += 1
        total = int(h["x-total-results"]) if total is None else total
        release = release or (h.get("x-uniprot-release"), h.get("x-uniprot-release-date"))
        if h.get("x-uniprot-release") != release[0]:
            raise RuntimeError(f"release changed mid-paging ({release[0]} -> {h.get('x-uniprot-release')}): start again")
        out += d["results"]
        m = re.search(r'<([^>]+)>;\s*rel="next"', h.get("link", ""))
        url = m[1] if m else None
    if len(out) != total:
        raise RuntimeError(f"got {len(out)} results, X-Total-Results says {total}: stop")
    return out, release, pages

def clean(text):
    """Drop the inline evidence tags: (PubMed:123, PubMed:456), (By similarity)."""
    text = re.sub(r"\s*\((?:PubMed:\d+(?:,\s*)?)+\)", "", text)
    return re.sub(r"\s*\(By similarity\)", "", text)

on_rest_tab()
now = datetime.now(timezone.utc)

# 1. The reviewed (Swiss-Prot) human entry for the gene.
q = f"gene:{GENE} AND organism_id:{TAXON} AND reviewed:true"
hits, (rel, rel_date), pages = search(q, FIELDS, size=5)
exact = [r for r in hits if r.get("genes") and r["genes"][0].get("geneName", {}).get("value", "").upper() == GENE.upper()
         and r.get("organism", {}).get("taxonId") == TAXON and r["entryType"] == "UniProtKB reviewed (Swiss-Prot)"]
print(f"UniProtKB release {rel} ({rel_date}); query {q!r}: {len(hits)} hit(s) in {pages} page(s), "
      f"{len(exact)} with primary gene name {GENE}")
if len(exact) != 1:
    raise RuntimeError(f"expected exactly one reviewed human {GENE} entry, got {[r['primaryAccession'] for r in exact]}: stop")
e = exact[0]
acc, length = e["primaryAccession"], e["sequence"]["length"]
func = [t["value"] for c in e.get("comments", []) if c["commentType"] == "FUNCTION" for t in c.get("texts", [])]
if not func:
    raise RuntimeError(f"{acc}: no FUNCTION comment in the search result: stop")

# 2. Cross-check against the entry itself: same accession, the sequence really has that many residues, and
#    the entry version and isoforms (length is for the canonical isoform only).
d, h = get(SITE + f"/uniprotkb/{acc}.json?" + urllib.parse.urlencode(
    {"fields": "accession,length,sequence,cc_function,cc_alternative_products,version,sequence_version,date_modified,protein_existence"}))
if d["primaryAccession"] != acc or len(d["sequence"]["value"]) != length or d["sequence"]["length"] != length:
    raise RuntimeError(f"entry {acc} does not match the search result: {d['primaryAccession']}, "
                       f"{len(d['sequence']['value'])} residues vs length {length}: stop")
if h.get("x-uniprot-release") != rel:
    raise RuntimeError(f"entry served from release {h.get('x-uniprot-release')}, search from {rel}: re-run")
func2 = [t["value"] for c in d.get("comments", []) if c["commentType"] == "FUNCTION" for t in c.get("texts", [])]
if func2 != func:
    raise RuntimeError(f"{acc}: FUNCTION text differs between search and entry: stop")
iso = [i for c in d.get("comments", []) if c["commentType"] == "ALTERNATIVE PRODUCTS" for i in c["isoforms"]]
canon = [i["isoformIds"][0] for i in iso if i.get("isoformSequenceStatus") == "Displayed"]
audit = d["entryAudit"]

print(f"\n{acc} ({e['uniProtkbId']}), {e['proteinDescription']['recommendedName']['fullName']['value']}, "
      f"gene {e['genes'][0]['geneName']['value']}, {e['organism']['scientificName']} (taxon {TAXON})")
print(f"  length: {length} aa (canonical isoform {canon[0] if canon else acc}; {len(iso)} isoforms listed), "
      f"sequence checked: {len(d['sequence']['value'])} residues, starts {d['sequence']['value'][:10]}")
print(f"  {d['proteinExistence']}; entry version {audit['entryVersion']}, sequence version {audit['sequenceVersion']}, "
      f"last annotation update {audit['lastAnnotationUpdateDate']}")
ev = sum(len(t.get("evidences", [])) for c in d["comments"] if c["commentType"] == "FUNCTION" for t in c["texts"])
print(f"  function ({len(func[0]):,} chars raw, backed by {ev} evidence records; inline (PubMed:...) tags removed):")
for p in func:
    print(textwrap.fill(clean(p), 110, initial_indent="    ", subsequent_indent="    "))

print(f"\nSource: UniProt Consortium, UniProtKB release {rel} ({rel_date}), entry {acc} version {audit['entryVersion']}, "
      f"https://www.uniprot.org/uniprotkb/{acc}/entry, accessed {now:%d %B %Y %H:%M} UTC. Licence CC BY 4.0. "
      "Research and educational use; not medical advice.")
```

Output (from the run on 2026-11-14, 23:33 UTC):

```text
UniProtKB release 2026_04 (04-November-2026); query 'gene:TP53 AND organism_id:9606 AND reviewed:true': 1 hit(s) in 1 page(s), 1 with primary gene name TP53

P04637 (P53_HUMAN), Cellular tumor antigen p53, gene TP53, Homo sapiens (taxon 9606)
  length: 393 aa (canonical isoform P04637-1; 9 isoforms listed), sequence checked: 393 residues, starts MEEPQSDPSV
  1: Evidence at protein level; entry version 316, sequence version 4, last annotation update 2026-11-04
  function (2,624 chars raw, backed by 18 evidence records; inline (PubMed:...) tags removed):
    Multifunctional transcription factor that induces cell cycle arrest, DNA repair or apoptosis upon binding
    to its target DNA sequence. Acts as a tumor suppressor in many tumor types; induces growth arrest or
    apoptosis depending on the physiological circumstances and cell type. Negatively regulates cell division
    by controlling expression of a set of genes required for this process. One of the activated genes is an
    inhibitor of cyclin-dependent kinases. Apoptosis induction seems to be mediated either by stimulation of
    BAX and FAS antigen expression, or by repression of Bcl-2 expression. Its pro-apoptotic activity is
    activated via its interaction with PPP1R13B/ASPP1 or TP53BP2/ASPP2. However, this activity is inhibited
    when the interaction with PPP1R13B/ASPP1 or TP53BP2/ASPP2 is displaced by PPP1R13L/iASPP. In cooperation
    with mitochondrial PPIF is involved in activating oxidative stress-induced necrosis; the function is
    largely independent of transcription. Induces the transcription of long intergenic non-coding RNA p21
    (lincRNA-p21) and lincRNA-Mkln1. LincRNA-p21 participates in TP53-dependent transcriptional repression
    leading to apoptosis and seems to have an effect on cell-cycle regulation. Implicated in Notch signaling
    cross-over. Prevents CDK7 kinase activity when associated to CAK complex in response to DNA damage, thus
    stopping cell cycle progression. Isoform 2 enhances the transactivation activity of isoform 1 from some
    but not all TP53-inducible promoters. Isoform 4 suppresses transactivation activity and impairs growth
    suppression mediated by isoform 1. Isoform 7 inhibits isoform 1-mediated apoptosis. Regulates the
    circadian clock by repressing CLOCK-BMAL1-mediated transcriptional activation of PER2

Source: UniProt Consortium, UniProtKB release 2026_04 (04-November-2026), entry P04637 version 316, https://www.uniprot.org/uniprotkb/P04637/entry, accessed 14 November 2026 23:33 UTC. Licence CC BY 4.0. Research and educational use; not medical advice.
```

### 2. robots.txt, query mistakes and entry edge cases (browser)

2 page loads and 15 in-page `fetch()` calls in the same tab.

```python
import json, time, urllib.parse

SITE = "https://rest.uniprot.org"
S = "/uniprotkb/search?"

START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit', headers: {Accept: 'application/json'}})
    .then(async r => { const t = await r.text(); window.__u[id] = {status: r.status, redirected: r.redirected, url: r.url,
      total: r.headers.get('x-total-results'), next: !!r.headers.get('link'), bytes: t.length, text: t.slice(0, 8000)}; })
    .catch(e => { window.__u[id] = {status: 0, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

def raw(path):
    """One in-page GET -> the answer's status, redirect, X-Total-Results, Link presence, size and body start.
    No retries: this block only inspects answers."""
    rid = json.dumps(js(START_JS % json.dumps(SITE + path)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{path}: no answer after 60s")
        time.sleep(0.3)
    time.sleep(1.0)
    return r

def q(query, fields="accession,gene_primary", size=3):
    return S + urllib.parse.urlencode({"query": query, "fields": fields, "format": "json", "size": size})

def brief(r):
    out = f"HTTP {r['status']}"
    if r.get("redirected"):
        out += f" (redirected to {r['url'].replace(SITE, '')})"
    try:
        d = json.loads(r["text"])
    except ValueError:
        return out + f" {r.get('bytes', 0):,} chars (only the first 8,000 kept here)"
    if "messages" in d:
        return out + f" {d['messages']}"
    if "results" in d:
        accs = [f"{x['primaryAccession']}:{(x.get('genes') or [{}])[0].get('geneName', {}).get('value', '-')}" for x in d["results"]]
        return out + f" total {int(r['total']):,}{', has next page' if r['next'] else ''}, first {accs}"
    return out + f" {r['bytes']:,} chars, {d.get('entryType')} {d.get('primaryAccession')}"

try:
    on_site = js("location.origin") == SITE
except Exception:
    on_site = False
if not on_site:
    new_tab(SITE + "/uniprotkb/P04637?format=json&fields=accession")
    wait_for_load()

goto_url(SITE + "/robots.txt")
wait_for_load()
st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
txt = js("document.body.innerText")
print(f"rest.uniprot.org/robots.txt HTTP {st}:")
print("\n".join("  " + l for l in txt.strip().splitlines() if l.strip() and not l.startswith("#")))
goto_url(SITE + "/uniprotkb/P04637?format=json&fields=accession")  # back to a JSON page for same-origin fetch()
wait_for_load()
print()

GH = "gene:TP53 AND organism_id:9606"
for label, path in (
    ("reviewed human gene:TP53          ", q(GH + " AND reviewed:true")),
    ("human gene:TP53, any review status", q(GH)),
    ("reviewed gene:TP53, any organism  ", q("gene:TP53 AND reviewed:true")),
    ("synonym gene:p53, reviewed human  ", q("gene:p53 AND organism_id:9606 AND reviewed:true")),
    ("free text TP53, reviewed human    ", q("TP53 AND organism_id:9606 AND reviewed:true")),
    ("organism_name:human, reviewed     ", q("gene:TP53 AND organism_name:human AND reviewed:true")),
    ("typo organism_id:96060            ", q("gene:TP53 AND organism_id:96060 AND reviewed:true")),
    ("typo query field gen:TP53         ", q("gen:TP53 AND organism_id:9606")),
    ("typo return field funtion         ", q(GH, fields="accession,funtion")),
    ("size=501                          ", q(GH, size=501)),
    ("entry P04637.json, all fields     ", "/uniprotkb/P04637.json"),
    ("entry P04637.json?fields=...      ", "/uniprotkb/P04637.json?fields=accession,length,cc_function"),
    ("old accession Q15086              ", "/uniprotkb/Q15086.json?fields=accession,length"),
    ("isoform P04637-2                  ", "/uniprotkb/P04637-2.json?fields=accession,length"),
    ("bad accession XX04637             ", "/uniprotkb/XX04637.json"),
):
    r = raw(path)
    print(f"{label} {brief(r)}")
    if "isoform" in label and r["status"] == 200:
        print(f"{'':35}  length {json.loads(r['text'])['sequence']['length']} (canonical P04637 is 393)")
```

Output (from the run on 2026-11-14, 23:35 UTC):

```text
rest.uniprot.org/robots.txt HTTP 200:
  User-agent: *
  Disallow: /docs/
  Disallow: /idmapping/
  Disallow: /arba/stream/
  Disallow: /citations/stream/
  Disallow: /database/stream/
  Disallow: /diseases/stream/
  Disallow: /genecentric/stream/
  Disallow: /keywords/stream/
  Disallow: /locations/stream/
  Disallow: /proteomes/stream/
  Disallow: /taxonomy/stream/
  Disallow: /uniparc/stream/
  Disallow: /uniprotkb/stream/
  Disallow: /uniref/stream/
  Disallow: /unirule/stream/

reviewed human gene:TP53           HTTP 200 total 1, first ['P04637:TP53']
human gene:TP53, any review status HTTP 200 total 114, has next page, first ['P04637:TP53', 'K7PPA8:TP53', 'A0A386NCW8:TP53']
reviewed gene:TP53, any organism   HTTP 200 total 34, has next page, first ['P04637:TP53', 'P67939:TP53', 'P10361:Tp53']
synonym gene:p53, reviewed human   HTTP 200 total 1, first ['P04637:TP53']
free text TP53, reviewed human     HTTP 200 total 757, has next page, first ['Q9Y2B4:TP53TG5', 'P04637:TP53', 'Q12888:TP53BP1']
organism_name:human, reviewed      HTTP 200 total 1, first ['P04637:TP53']
typo organism_id:96060             HTTP 200 total 0, first []
typo query field gen:TP53          HTTP 400 ["'gen' is not a valid search field"]
typo return field funtion          HTTP 400 ["Invalid fields parameter value 'funtion'"]
size=501                           HTTP 400 ["'size' must be less than or equal to 500"]
entry P04637.json, all fields      HTTP 200 848,769 chars (only the first 8,000 kept here)
entry P04637.json?fields=...       HTTP 200 4,019 chars, UniProtKB reviewed (Swiss-Prot) P04637
old accession Q15086               HTTP 200 (redirected to /uniprotkb/P04637?from=Q15086) 848,769 chars (only the first 8,000 kept here)
isoform P04637-2                   HTTP 200 151 chars, UniProtKB reviewed (Swiss-Prot) P04637-2
                                     length 341 (canonical P04637 is 393)
bad accession XX04637              HTTP 400 ["The 'accession' value has invalid format. It should be a valid UniProtKB accession"]
```

### 3. Same answer with Python urllib, robots check for every agent, Link-header paging (no browser)

Python's default `urllib` User-Agent also got HTTP 200; this block sends a descriptive one.

```python
import json, re, sys, time, urllib.error, urllib.parse, urllib.request, urllib.robotparser

API = "https://rest.uniprot.org"
UA = "uniprot-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]

def get(url):
    """-> (parsed JSON, headers). One 60 s wait on HTTP 429/500/502/503/504 or a network error; exits on anything
    else (400 carries a 'messages' list)."""
    for attempt in range(2):
        time.sleep(1.0)  # no published rate limit; stay serial
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"}), timeout=60) as r:
                return json.load(r), r.headers
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(60)
                continue
            sys.exit(f"HTTP {e.code} {url}: {e.read().decode()[:200]}")
        except OSError as e:  # URLError (DNS, refused connection), timeouts, resets
            if attempt == 0:
                time.sleep(60)
                continue
            sys.exit(f"{url}: {e}")

def search(query, fields, size):
    """Yield every result page by page; the next page URL comes only from the Link header (cursor is opaque)."""
    url = f"{API}/uniprotkb/search?" + urllib.parse.urlencode({"query": query, "fields": fields, "format": "json", "size": size})
    seen = 0
    while url:
        d, h = get(url)
        seen += len(d["results"])
        yield d["results"], h
        m = re.search(r'<([^>]+)>;\s*rel="next"', h.get("Link", ""))
        url = m[1] if m else None
    if seen != int(h["X-Total-Results"]):
        sys.exit(f"paged {seen} results, X-Total-Results says {h['X-Total-Results']}")

# robots.txt: every agent group must allow the two paths used here.
rp = urllib.robotparser.RobotFileParser()
with urllib.request.urlopen(urllib.request.Request(f"{API}/robots.txt", headers={"User-Agent": UA}), timeout=30) as r:
    rp.parse(r.read().decode().splitlines())
paths = ["/uniprotkb/search?query=x", "/uniprotkb/P04637.json", "/uniprotkb/stream/x", "/idmapping/run"]
for p in paths:
    ok = {a: rp.can_fetch(a, API + p) for a in AGENTS}
    print(f"robots {p:<28} {'allowed' if all(ok.values()) else 'DISALLOWED' if not any(ok.values()) else ok} for all {len(AGENTS)} agents")
if not all(rp.can_fetch(a, API + p) for a in AGENTS for p in paths[:2]):
    sys.exit("robots.txt now disallows a path this skill uses: stop")

# The answer.
(page, h), = list(search("gene:TP53 AND organism_id:9606 AND reviewed:true", "accession,length,cc_function", 5))
if len(page) != 1:
    sys.exit(f"expected 1 reviewed human TP53 entry, got {[x['primaryAccession'] for x in page]}")
e = page[0]
func = next(t["value"] for c in e["comments"] if c["commentType"] == "FUNCTION" for t in c["texts"])
first = re.sub(r"\s*\((?:PubMed:\d+(?:,\s*)?)+\)", "", func).split(". ")[0]
print(f"\nrelease {h['X-UniProt-Release']} ({h['X-UniProt-Release-Date']}): {e['primaryAccession']}, "
      f"{e['sequence']['length']} aa; function starts: {first}.")

# Paging: every human entry with that gene name, 50 per page, reviewed vs unreviewed.
kinds, n_pages = {}, 0
for results, h in search("gene:TP53 AND organism_id:9606", "accession,reviewed", 50):
    n_pages += 1
    for x in results:
        kinds[x["entryType"]] = kinds.get(x["entryType"], 0) + 1
print(f"\nall human gene:TP53 entries: {sum(kinds.values())} in {n_pages} pages of up to 50 (X-Total-Results {h['X-Total-Results']}): {kinds}")
```

Output (from the run on 2026-11-14, 23:34 UTC):

```text
robots /uniprotkb/search?query=x    allowed for all 11 agents
robots /uniprotkb/P04637.json       allowed for all 11 agents
robots /uniprotkb/stream/x          DISALLOWED for all 11 agents
robots /idmapping/run               DISALLOWED for all 11 agents

release 2026_04 (04-November-2026): P04637, 393 aa; function starts: Multifunctional transcription factor that induces cell cycle arrest, DNA repair or apoptosis upon binding to its target DNA sequence.

all human gene:TP53 entries: 114 in 3 pages of up to 50 (X-Total-Results 114): {'UniProtKB reviewed (Swiss-Prot)': 1, 'UniProtKB unreviewed (TrEMBL)': 113}
```

### 4. curl, headers and TSV

```bash
S=https://rest.uniprot.org/uniprotkb/search
# the answer: accession, length, first sentence of the function (curl -G encodes the query)
curl -sS --fail -G "$S" --data-urlencode 'query=gene:TP53 AND organism_id:9606 AND reviewed:true' \
  -d fields=accession,length,cc_function -d format=json -d size=5 \
  | python3 -c 'import json,sys; r=json.load(sys.stdin)["results"]; e=r[0]; f=e["comments"][0]["texts"][0]["value"]; print(len(r), "hit:", e["primaryAccession"], e["sequence"]["length"], "aa |", f.split(" (PubMed")[0])'
sleep 1
# release, total and paging headers
curl -sS -G -D - -o /dev/null "$S" --data-urlencode 'query=gene:TP53 AND organism_id:9606' -d fields=accession -d format=json -d size=50 \
  | tr -d '\r' | grep -iE '^(x-uniprot-release|x-uniprot-release-date|x-total-results|link|cache-control|access-control-allow-origin):' | cut -c1-160
sleep 1
# TSV is the shortest form for a table
curl -sS --fail -G "$S" --data-urlencode 'query=gene:TP53 AND organism_id:9606 AND reviewed:true' -d fields=accession,id,length,gene_primary -d format=tsv
sleep 1
# 400s carry a reason; a wrong taxon id is a silent HTTP 200 with zero results
curl -sS -G -w ' <- HTTP %{http_code}\n' "$S" --data-urlencode 'query=gene:TP53 AND organism_id:96060' -d fields=accession -d format=json
```

Output (from the run on 2026-11-14, 23:35 UTC):

```text
1 hit: P04637 393 aa | Multifunctional transcription factor that induces cell cycle arrest, DNA repair or apoptosis upon binding to its target DNA sequence
cache-control: public, max-age=43200
x-uniprot-release: 2026_04
link: <https://rest.uniprot.org/uniprotkb/search?format=json&fields=accession&query=gene%3ATP53%20AND%20organism_id%3A9606&cursor=1q25awc2b43xtjd29ul6mzs0jmb7af
x-total-results: 114
access-control-allow-origin: *
x-uniprot-release-date: 04-November-2026
Entry	Entry Name	Length	Gene Names (primary)
P04637	P53_HUMAN	393	TP53
{"results":[]} <- HTTP 200
```

## Fields (uniprotkb/search and entry JSON)

| Return field (`fields=`) | JSON path | Notes |
|---|---|---|
| `accession` | `primaryAccession` | stable ID (P04637). Merged old IDs are `secondaryAccessions`; requesting one (Q15086) redirects with HTTP 303 to `/uniprotkb/P04637?from=Q15086` |
| (always) | `entryType` | `UniProtKB reviewed (Swiss-Prot)` or `UniProtKB unreviewed (TrEMBL)`; query filter `reviewed:true` / `reviewed:false` |
| `id` | `uniProtkbId` | entry name, P53_HUMAN; key your data on the accession |
| `protein_name` | `proteinDescription.recommendedName.fullName.value` | plus `alternativeNames` (Tumor suppressor p53, Phosphoprotein p53, Antigen NY-CO-13) |
| `gene_primary`, `gene_names` | `genes[0].geneName.value`, `genes[0].synonyms` | the `gene:` query field matches synonyms too (`gene:p53` finds P04637) and is case-insensitive (`Tp53`, `tp53` in other species) |
| `organism_name`, `organism_id` | `organism.scientificName`, `organism.taxonId` | query with `organism_id:9606` (exact taxon); `organism_name:human` also gave 1 hit here, but the query-fields help (https://www.uniprot.org/help/query-fields) says `organism_name:sheep` matches "organisms whose name contains the term" |
| `length`, `mass` | `sequence.length`, `sequence.molWeight` | canonical isoform only (393 aa, 43,653 Da); `sequence` adds `sequence.value` |
| `cc_function` | `comments[commentType=FUNCTION].texts[].value` | one text of 2,624 chars here, with inline `(PubMed:...)` tags and an `evidences` list (ECO codes, PubMed IDs) |
| `cc_alternative_products` | `comments[commentType=ALTERNATIVE PRODUCTS].isoforms` | 9 isoforms; `isoformSequenceStatus` `Displayed` marks the canonical one (P04637-1) |
| `version`, `sequence_version`, `date_modified` | `entryAudit.entryVersion`, `.sequenceVersion`, `.lastAnnotationUpdateDate` | 316, 4, 2026-11-04 |
| `protein_existence` | `proteinExistence` | "1: Evidence at protein level" |
| response headers | `x-uniprot-release`, `x-uniprot-release-date`, `x-total-results`, `link` | exposed to browser scripts via `access-control-expose-headers`; `cache-control: public, max-age=43200` |

## Gotchas

- **Quote the release.** UniProtKB changes every release (2026_04 dated 04-November-2026 here; the entry's last annotation update is the same day). Take the release from `x-uniprot-release` and quote it with the accession and entry version. Block 1 stops if search and entry come from different releases.
- **Length is the canonical isoform.** P04637 is 393 aa; isoform P04637-2 is 341 aa and is served at `/uniprotkb/P04637-2.json`. Say "393 aa (canonical isoform)" if the question could mean another isoform.
- **Full entries are big.** `/uniprotkb/P04637.json` with no `fields` was 848,769 chars; `?fields=accession,length,cc_function` was 4,019. Always pass `fields`.
- **The 303 redirect drops `fields`.** `/uniprotkb/Q15086.json?fields=accession,length` (a merged old accession) redirected to `/uniprotkb/P04637?from=Q15086` and returned the full 848,769-char entry. Resolve old accessions first, then ask for the new one with `fields`. A malformed accession (`XX04637`) is HTTP 400.
- **Free text is not a gene search.** `TP53 AND organism_id:9606 AND reviewed:true` returned 757 entries, TP53TG5 and TP53BP1 among the first; use the `gene:` field. Block 1 also filters on the primary gene name, because `gene:` matches synonyms.
- **Wrong taxon ids fail silently.** `organism_id:96060` is HTTP 200, `{"results":[]}`, `x-total-results: 0`. Block 1 checks `organism.taxonId` on every hit and requires exactly one.
- **The function text carries citations inline.** The raw FUNCTION value repeats `(PubMed:11025664, PubMed:12524540, ...)` after most sentences; block 1 strips those tags for display. Keep the raw text and `evidences` if you need the references. The text has no final full stop.
- **Stream and ID mapping are off-limits here.** The docs (https://www.uniprot.org/help/api_queries) suggest `/uniprotkb/stream` for small result sets; robots.txt disallows `/uniprotkb/stream/` and `/idmapping/`. Python's robot parser lets `/uniprotkb/stream?query=...` through (the rule has a trailing slash), but this skill treats the stream endpoint as excluded and pages `/uniprotkb/search` instead (500 per page at most).
- **Medical use.** The licence page says medical or genetic information is "for research, educational and informational purposes only". Say so when quoting function or disease text.
- **Tab marker.** The harness sets the tab title to a horse emoji; the blocks check `location.origin` and the JSON, not the title.

## What does not work

- **`/uniprotkb/stream`, `/idmapping/`, `/docs/`** on rest.uniprot.org: disallowed in robots.txt (see above). Not used.
- **www.uniprot.org pages** for data: the site is a JavaScript app; curl of https://www.uniprot.org/help/license returned HTTP 200 with a 5,570-byte shell holding the "UniProt website fallback message" and none of the licence text. The same help text comes from rest.uniprot.org/help/<id> as JSON, and entries from rest.uniprot.org. Not used beyond citation links.
- **`size` above 500**: HTTP 400.
- **Not tested:** rate-limit behaviour (never provoked), the SPARQL and Java APIs, `compressed=true`, `includeIsoform=true`, and formats other than JSON and TSV.
