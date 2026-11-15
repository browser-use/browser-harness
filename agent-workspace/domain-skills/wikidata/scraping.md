# Wikidata - Entity Lookup by Q-id or Name, Claims, Linked IDs, SPARQL Lists

Field-tested against www.wikidata.org and query.wikidata.org on 2026-11-04 using a Browser Use cloud browser, logged out. No CAPTCHA, 429 or block seen across ~40 entity page loads, ~60 Action API calls and ~12 SPARQL queries.

robots.txt (checked 2026-11-04, `User-agent: *`): www.wikidata.org allows `/wiki/Q42`, `/wiki/Property:P31` and `/wiki/Wikidata:Main_Page` and disallows `/w/`, `/api/` and `/wiki/Special:` (so `Special:EntityData` and `Special:Search` are out); query.wikidata.org disallows `/sparql` and `/bigdata` but not the query UI at `/`. Block 1 loads only allowed `/wiki/` pages; blocks 2 and 3 call the robots-disallowed `/w/api.php` and `/sparql` only because they are Wikidata's official public APIs.

## Quick summary

- **Entity page** (`/wiki/Q42`, `/wiki/Property:P31`, block 1): one `js()` call returns label, description, the terms table (labels and aliases per language), every statement with rank, value, linked Q-id or URL, qualifiers and reference count, the Identifiers section with each external link, and sitelinks. Redirected ids and missing ids are reported, not guessed.
- **Name -> Q-id** needs the API (block 2): `wbsearchentities` matches labels and aliases, but its order does not put the famous entity first (`Douglas Adams` -> `Q28421831`, an engineer, before `Q42`). `resolve()` re-sorts the hits by sitelink count.
- **Official Action API** (block 2, same-origin `fetch()` from a Wikidata tab): `wbgetentities` for up to 50 ids per call (labels, aliases, claims, sitelinks, redirects), labels for every referenced property/item, best-rank values, and external IDs turned into links via each property's formatter URL (P1630).
- **SPARQL** (block 3, `fetch()` from the query.wikidata.org UI tab): lists (laureates by year, top countries), reverse lookup from an external ID to the item, ASK. Start-and-poll, since queries can run up to 60 s.
- All blocks run serially with pauses, back off on 429/maxlag and raise on anything unexpected instead of retrying around it.

## What works

### 1. Entity by Q-id from `/wiki/<id>` (browser)

Self-contained; reads robots.txt in the tab first, then loads entity pages in the same tab. Property ids map to `/wiki/Property:P<n>`. The last two ids are refused by the robots guard without loading.

```python
import json, re, time
from urllib.parse import quote, unquote, urlparse

BASE = "https://www.wikidata.org"
_TAB = []

def _open(url):
    if _TAB:
        goto_url(url)
    else:
        new_tab(url)
        _TAB.append(current_tab())
    wait_for_load()

# robots.txt, group "User-agent: *": plain prefix rules, longest match wins, Allow wins a tie.
# Read once, in the same tab, before any entity load.
_open(BASE + "/robots.txt")
RULES, _star = [], False
for line in js("document.body.innerText").splitlines():
    line = line.split("#", 1)[0].strip()
    k, _, v = (x.strip() for x in line.partition(":"))
    if k.lower() == "user-agent":
        _star = v == "*"
    elif _star and k.lower() in ("allow", "disallow") and v:
        RULES.append((k.lower() == "allow", v))
assert RULES, "could not read robots.txt"

def robots_allowed(path):
    raw = unquote(path)
    for p in {path, raw, quote(raw, safe="/")}:
        best, ok = -1, True
        for allow, pat in RULES:
            if p.startswith(pat) and (len(pat) > best or (len(pat) == best and allow)):
                best, ok = len(pat), allow
        if not ok:
            return False
    return True

EXTRACT_JS = r"""
(() => {
  if (typeof mw === 'undefined' || !document.querySelector('#firstHeading')) return null;
  const id = mw.config.get('wbEntityId');
  const base = {url: location.href, page_title: mw.config.get('wgPageName'), page_id: mw.config.get('wgArticleId'),
                rev_id: mw.config.get('wgCurRevisionId'), redirected_from: mw.config.get('wgRedirectedFrom')};
  if (!id) return {...base, id: null, missing: !mw.config.get('wgArticleId')};
  const txt = el => el ? el.textContent.replace(/\s+/g, ' ').trim() : null;
  const q = (el, s) => el ? el.querySelector(s) : null;
  // Terms: the "In more languages" table; one row per language shown to this viewer (always mul + en for an en browser,
  // sometimes more, e.g. en-us, es, zh-hant, depending on the page's own language suggestions).
  const terms = {};
  for (const tr of document.querySelectorAll('tr.wikibase-entitytermsforlanguageview')) {
    const lang = [...tr.classList].find(c => c.startsWith('wikibase-entitytermsforlanguageview-')).slice(36);
    const lab = q(tr, '.wikibase-labelview'), des = q(tr, '.wikibase-descriptionview');
    terms[lang] = {label: lab && !lab.classList.contains('wb-empty') ? txt(q(lab, '.wikibase-labelview-text')) : null,
                   description: des && !des.classList.contains('wb-empty') ? txt(q(des, '.wikibase-descriptionview-text')) : null,
                   aliases: [...tr.querySelectorAll('.wikibase-aliasesview-list-item')].map(txt)};
  }
  // A snak is a value cell: an entity link (Q/P/L id), an external-id link, a URL, plain text, or unknown/no value.
  const snak = sv => {
    const cell = q(sv, '.wikibase-snakview-value');
    if (!cell) return null;
    // Coordinate values lazy-load an interactive map whose controls and attribution land in textContent; drop it.
    const v = cell.cloneNode(true);
    v.querySelectorAll('.mw-kartographer-map, .mw-kartographer-container').forEach(x => x.remove());
    const kind = v.classList.contains('wikibase-snakview-variation-somevaluesnak') ? 'somevalue'
               : v.classList.contains('wikibase-snakview-variation-novaluesnak') ? 'novalue' : 'value';
    // First link with text (Commons media values start with an image-only thumbnail link).
    const a = [...v.querySelectorAll('a[href]')].find(x => x.textContent.trim()) || null;
    const m = a && a.getAttribute('href').match(/^\/wiki\/(?:(?:Property|Lexeme):)?([QPL]\d+(?:-[SF]\d+)?)$/);
    // Commons media values append "600 × 386; 38 KB" after the file link; keep the file name only.
    const file = a && /commons\.wikimedia\.org\/wiki\/File:/.test(a.href);
    return {kind, text: file ? txt(a) : txt(v), entity: m ? m[1] : null, link: a && !m ? a.href : null};
  };
  const sectionOf = el => {
    const h = [...document.querySelectorAll('h2.wb-section-heading')].filter(h => h.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING).pop();
    return h ? h.id : null;
  };
  const statements = [], identifiers = [];
  for (const g of document.querySelectorAll('.wikibase-statementgroupview')) {
    const pid = g.dataset.propertyId || g.id;
    const plabel = txt(q(g, '.wikibase-statementgroupview-property-label'));
    const vals = [...g.querySelectorAll(':scope .wikibase-statementlistview-listview > .wikibase-statementview')].map(st => {
      const rank = st.classList.contains('wb-preferred') ? 'preferred' : st.classList.contains('wb-deprecated') ? 'deprecated' : 'normal';
      const main = snak(q(st, '.wikibase-statementview-mainsnak .wikibase-snakview'));
      const quals = [...st.querySelectorAll('.wikibase-statementview-qualifiers .wikibase-snakview')].map(sv => {
        const pa = q(sv, '.wikibase-snakview-property a');
        return {property: pa ? pa.getAttribute('href').split(':').pop() : null, property_label: txt(pa), ...snak(sv)};
      });
      // Qualifier groups show the property name once; later snaks of the same property inherit it.
      for (let i = 1; i < quals.length; i++) if (!quals[i].property) { quals[i].property = quals[i-1].property; quals[i].property_label = quals[i-1].property_label; }
      return {rank, ...main, qualifiers: quals, references: st.querySelectorAll('.wikibase-referenceview').length};
    });
    (sectionOf(g) === 'identifiers' ? identifiers : statements).push({property: pid, property_label: plabel, values: vals});
  }
  const sitelinks = [...document.querySelectorAll('.wikibase-sitelinkview')].map(li => {
    const a = q(li, '.wikibase-sitelinkview-page a');
    return {site: li.dataset.wbSiteid, title: txt(a), url: a ? a.href : null};
  }).filter(s => s.url);
  return {...base, id, missing: false,
    label: txt(document.querySelector('.wikibase-title-label')),
    description: txt(document.querySelector('.wikibase-entitytermsview-heading-description:not(.wb-empty)')),
    datatype: txt(document.querySelector('.wikibase-propertyview-datatype-value')),
    terms, statements, identifiers, sitelinks};
})()
"""

def entity_path(eid):
    eid = eid.strip()
    if re.fullmatch(r"[Qq]\d+", eid):
        return "/wiki/" + eid.upper()
    if re.fullmatch(r"[Pp]\d+", eid):
        return "/wiki/Property:" + eid.upper()
    if re.fullmatch(r"[Ll]\d+", eid):
        return "/wiki/Lexeme:" + eid.upper()
    return "/wiki/" + quote(eid.replace(" ", "_"), safe="/:")

def wd_entity(eid):
    """Load the entity page (Q42, P31, L1) and return terms, statements, identifiers and sitelinks.
    Raises PermissionError on a robots-disallowed path, RuntimeError on a page that is not an entity view."""
    path = entity_path(eid)
    if not robots_allowed(path):
        raise PermissionError(f"robots.txt disallows {path}")
    _open(BASE + path)
    final = urlparse(page_info()["url"]).path
    if not robots_allowed(final):
        raise PermissionError(f"{path} landed on disallowed {final}")
    data = None
    for _ in range(20):
        data = json.loads(js("JSON.stringify(" + EXTRACT_JS + ")") or "null")
        if data:
            break
        time.sleep(0.5)
    if not data:
        info = page_info()
        raise RuntimeError(f"no entity on {info['url']} ({info['title']!r}); a block or challenge page? "
                           "Stop here, do not retry around it.")
    time.sleep(1)  # one page per second at most
    return data

def first(e, pid):
    """Text of the best value of a property: preferred rank first, deprecated never."""
    for group in e["statements"] + e["identifiers"]:
        if group["property"] == pid:
            vals = [v for v in group["values"] if v["rank"] != "deprecated"]
            vals.sort(key=lambda v: v["rank"] != "preferred")
            return vals[0]["text"] if vals else None

for eid in ["Q42", "Q90", "P31"]:
    e = wd_entity(eid)
    print(e["id"], "|", e["label"], "|", e["description"], "| rev", e["rev_id"], "| datatype:", e["datatype"])
    print("  terms:", {k: (t["label"], t["aliases"][:3]) for k, t in e["terms"].items()})
    print("  statements:", len(e["statements"]), "properties,", sum(len(g["values"]) for g in e["statements"]), "values;",
          "identifiers:", len(e["identifiers"]), "; sitelinks:", len(e["sitelinks"]))
    for g in e["statements"][:4]:
        v = g["values"][0]
        print(f"    {g['property']} {g['property_label']} = {v['text']} ({v['entity'] or v['link'] or v['kind']}, {v['rank']}, "
              f"{len(v['qualifiers'])} qualifiers, {v['references']} refs) [+{len(g['values']) - 1} more]")
    for g in e["identifiers"][:3]:
        v = g["values"][0]
        print(f"    {g['property']} {g['property_label']} = {v['text']} -> {v['link']}")
    print("  sitelinks:", [(s["site"], s["title"]) for s in e["sitelinks"] if s["site"] in ("enwiki", "dewiki", "enwikiquote")])

e = wd_entity("Q90")
print("Q90 population (preferred):", first(e, "P1082"), "| country:", first(e, "P17"), "| coords:", first(e, "P625"))
pop = next(g for g in e["statements"] if g["property"] == "P1082")
for v in pop["values"][:3]:
    print("   ", v["rank"], v["text"], [(x["property_label"], x["text"]) for x in v["qualifiers"]])

for eid in ["Q19746657", "Q999999999999"]:
    e = wd_entity(eid)
    print(eid, "->", e.get("id"), "| label:", e.get("label"), "| redirected_from:", e["redirected_from"], "| missing:", e["missing"])

for eid in ["Special:EntityData/Q42.json", "Special:Search"]:
    try:
        wd_entity(eid)
    except PermissionError as err:
        print("refused:", err)
```

Output observed on 2026-11-04:

```text
Q42 | Douglas Adams | British science fiction writer and humorist (1952–2001) | rev 2563066692 | datatype: None
  terms: {'mul': ('Douglas Adams', ['Douglas Noël Adams', 'Douglas Noel Adams', 'Douglas N. Adams']), 'en': (None, [])}
  statements: 58 properties, 79 values; identifiers: 258 ; sitelinks: 133
    P31 instance of = human (Q5, normal, 1 qualifiers, 3 refs) [+0 more]
    P18 image = Douglas adams portrait.jpg (https://commons.wikimedia.org/wiki/File:Douglas_adams_portrait.jpg, normal, 25 qualifiers, 1 refs) [+0 more]
    P109 signature = Douglas Adams signature.svg (https://commons.wikimedia.org/wiki/File:Douglas_Adams_signature.svg, normal, 3 qualifiers, 1 refs) [+0 more]
    P21 sex or gender = male (Q6581097, normal, 0 qualifiers, 3 refs) [+0 more]
    P214 VIAF cluster ID = 113230702 -> https://viaf.org/en/viaf/113230702
    P213 ISNI = 0000000080456315 -> https://isni.org/isni/0000000080456315
    P1015 BIBSYS ID = 90196888 -> https://authority.bibsys.no/authority/rest/authorities/html/90196888
  sitelinks: [('dewiki', 'Douglas Adams'), ('enwiki', 'Douglas Adams'), ('enwikiquote', 'Douglas Adams')]
Q90 | Paris | capital and most populous city in France | rev 2563923081 | datatype: None
  terms: {'mul': (None, ['Paris']), 'en': ('Paris', ['City of Light', 'City of Love', 'Lutetia'])}
  statements: 105 properties, 437 values; identifiers: 230 ; sitelinks: 366
    P31 instance of = commune of France (Q484170, normal, 1 qualifiers, 3 refs) [+14 more]
    P361 part of = Île-de-France (Q13917, normal, 0 qualifiers, 0 refs) [+0 more]
    P571 inception = 3. century BCE (value, normal, 0 qualifiers, 1 refs) [+0 more]
    P154 logo image = Paris horizontal logo.svg (https://commons.wikimedia.org/wiki/File:Paris_horizontal_logo.svg, normal, 3 qualifiers, 0 refs) [+1 more]
    P300 ISO 3166-2 code = FR-75C -> None
    P214 VIAF cluster ID = 158822968 -> https://viaf.org/en/viaf/158822968
    P213 ISNI = 000000012114268X -> https://isni.org/isni/000000012114268X
  sitelinks: [('dewiki', 'Paris'), ('enwiki', 'Paris'), ('enwikiquote', 'Paris')]
P31 | instance of | type to which this subject corresponds/belongs. Different from P279 (subclass of); for example: K2 is an instance of mountain; volcano is a subclass of mountain | rev 2564690832 | datatype: Item
  terms: {'mul': (None, ['rdf:type', '∈']), 'en': ('instance of', ['is a', 'is an', 'is a[n]'])}
  statements: 19 properties, 244 values; identifiers: 0 ; sitelinks: 0
    P31 instance of = Wikidata property (Q18616576, deprecated, 1 qualifiers, 0 refs) [+2 more]
    P6104 maintained by WikiProject = WikiProject Ontology (Q60005226, normal, 0 qualifiers, 0 refs) [+0 more]
    P6609 transitive over = subclass of (P279, normal, 0 qualifiers, 0 refs) [+0 more]
    P1629 Wikidata item of this property = instance of (Q21503252, preferred, 1 qualifiers, 0 refs) [+1 more]
  sitelinks: []
Q90 population (preferred): 2,103,778 | country: France | coords: 48°51'24"N, 2°21'8"E
    normal 2,145,906 [('point in time', '1 January 2020'), ('determination method or standard', 'census')]
    normal 2,165,423 [('point in time', '1 January 2019'), ('determination method or standard', 'census')]
    normal 2,175,601 [('point in time', '1 January 2018'), ('determination method or standard', 'census')]
Q19746657 -> Q1000 | label: Gabon | redirected_from: Q19746657 | missing: False
Q999999999999 -> None | label: None | redirected_from: None | missing: True
refused: robots.txt disallows /wiki/Special:EntityData/Q42.json
refused: robots.txt disallows /wiki/Special:Search
```

### 2. Name search, full lookup and linked IDs via the official Action API (browser `fetch`)

Self-contained. Opens `/wiki/Wikidata:Main_Page` once so `fetch()` is same-origin, then calls only `/w/api.php`.

```python
import json, time
from urllib.parse import urlencode

BASE = "https://www.wikidata.org"
# Wikimedia asks API clients to identify themselves; from a browser, Api-User-Agent is the header for that.
# The browser's own User-Agent is left untouched.
HEADERS = {"Api-User-Agent": "browser-harness-wikidata-skill/1.0 (https://github.com/browser-use/browser-harness)"}

# Same-origin fetch() needs a tab on www.wikidata.org; /wiki/Wikidata:Main_Page is allowed by robots.txt.
new_tab(BASE + "/wiki/Wikidata:Main_Page")
wait_for_load()

def _fetch(url):
    raw = js("""(async () => { const r = await fetch(%s, {headers: %s});
      return JSON.stringify({status: r.status, retry: r.headers.get('retry-after'), body: await r.text()}); })()"""
             % (json.dumps(url), json.dumps(HEADERS)))
    return json.loads(raw)

def api(_allow=(), **params):
    """Wikibase/MediaWiki Action API (/w/api.php). Backs off on 429/503 or maxlag (Retry-After, max 60 s), then raises.
    API error codes listed in _allow are returned in the body instead of raised."""
    url = BASE + "/w/api.php?" + urlencode({"format": "json", "formatversion": 2, "maxlag": 5, **params})
    for i in range(3):
        r = _fetch(url)
        body = json.loads(r["body"]) if r["body"][:1] in "{[" else {}
        err = body.get("error") or {}
        if (r["status"] in (429, 503) or err.get("code") == "maxlag") and i < 2:
            time.sleep(min(60.0, float(r["retry"] or 5 * 2 ** i)))
            continue
        if r["status"] != 200 or (err and err.get("code") not in _allow):
            raise RuntimeError(f"{params.get('action')}: HTTP {r['status']} {err or r['body'][:200]!r}")
        time.sleep(0.3)  # serial requests, small gap
        return body
    raise RuntimeError("still throttled after 3 tries; stop and come back later")

def search(name, lang="en", limit=7, type="item"):
    """Name -> candidate entities (label/alias prefix match, ranked by Wikidata)."""
    r = api(action="wbsearchentities", search=name, language=lang, uselang=lang, type=type, limit=limit)
    return [{"id": h["id"], "label": h.get("label"), "description": h.get("description"),
             "matched": h["match"]["type"] + ":" + h["match"]["text"]} for h in r["search"]]

def text_search(query, limit=5):
    """CirrusSearch over items (the API behind Special:Search). Takes filters such as haswbstatement:P31=Q5."""
    r = api(action="query", list="search", srsearch=query, srnamespace=0, srlimit=limit, srprop="")
    ids = [h["title"] for h in r["query"]["search"]]
    ents = get_entities(ids, props="labels|descriptions") if ids else {}
    return {"total": r["query"]["searchinfo"]["totalhits"],
            "hits": [{"id": i, "label": term(ents[i], "labels"), "description": term(ents[i], "descriptions")} for i in ids]}

def get_entities(ids, props="labels|descriptions|aliases|claims|sitelinks", langs="en|mul"):
    """Up to 50 ids per call. Follows redirects; returns {requested id: entity JSON} (missing ids get {"missing": True})."""
    out = {}
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        while True:
            r = api(_allow=("no-such-entity",), action="wbgetentities", ids="|".join(chunk), props=props,
                    languages=langs, languagefallback=1)
            bad = (r.get("error") or {}).get("id")
            if not bad:
                break
            # An id that never existed fails the whole call: mark it missing and ask again without it.
            out[bad] = {"missing": True}
            chunk = [x for x in chunk if x != bad]
            if not chunk:
                break
        ents = r.get("entities", {})
        for eid in chunk:
            e = ents.get(eid) or next((x for x in ents.values() if x.get("redirects", {}).get("from") == eid), {"missing": True})
            out[eid] = {"missing": True} if "missing" in e else e
    return out

def resolve(name, limit=7):
    """Name -> candidates from wbsearchentities, re-sorted by sitelink count (how many wikis have an article).
    Wikidata's own order does not favour the famous entity; read the description before picking."""
    hits = search(name, limit=limit)
    ents = get_entities([h["id"] for h in hits], props="sitelinks") if hits else {}
    for h in hits:
        h["sitelinks"] = len(ents[h["id"]].get("sitelinks", {}))
    return sorted(hits, key=lambda h: -h["sitelinks"])

def term(e, kind, lang="en"):
    """Label/description in lang, falling back to 'mul' (Wikidata's default-for-all-languages label)."""
    t = e.get(kind, {})
    v = t.get(lang) or t.get("mul")
    return v["value"] if v else None

_LABELS = {}
def labels(ids):
    need = sorted({i for i in ids if i not in _LABELS})
    for eid, e in get_entities(need, props="labels|datatype|claims", langs="en|mul").items():
        # Formatter URL (P1630) turns an external id into a link; take a preferred-rank one when there are several.
        fc = sorted(e.get("claims", {}).get("P1630", []), key=lambda c: c["rank"] != "preferred")
        fmt = [c["mainsnak"].get("datavalue", {}).get("value") for c in fc if c["rank"] != "deprecated"]
        _LABELS[eid] = {"label": term(e, "labels"), "datatype": e.get("datatype"), "formatter": fmt[0] if fmt else None}
    return {i: _LABELS[i] for i in ids}

def render(snak, lab):
    """Human-readable value of a snak; entity ids become their English labels."""
    if snak["snaktype"] != "value":
        return {"somevalue": "unknown value", "novalue": "no value"}[snak["snaktype"]]
    v, t = snak["datavalue"]["value"], snak["datavalue"]["type"]
    if t == "wikibase-entityid":
        return f"{(lab.get(v['id']) or {}).get('label')} ({v['id']})"
    if t == "time":
        y, m, d = v["time"][1:].split("T")[0].split("-")
        sign = "-" if v["time"][0] == "-" else ""
        return sign + {9: y, 10: f"{y}-{m}", 11: f"{y}-{m}-{d}"}.get(v["precision"], f"{y} (precision {v['precision']})")
    if t == "quantity":
        unit = v["unit"].rsplit("/", 1)[-1]
        return v["amount"].lstrip("+") + ("" if unit == "1" else f" {(lab.get(unit) or {}).get('label') or unit}")
    if t == "monolingualtext":
        return f"{v['text']} [{v['language']}]"
    if t == "globecoordinate":
        return f"{v['latitude']:.4f}, {v['longitude']:.4f}"
    return str(v)

def entity_summary(eid, max_values=3):
    """Labels, best-rank claims with qualifiers, and external IDs with links. One call for the entity, then
    one wbgetentities call per 50 referenced properties/items for their labels, datatypes and formatter URLs."""
    e = get_entities([eid])[eid]
    if e.get("missing"):
        return {"id": eid, "missing": True}
    claims = e.get("claims", {})
    ref_ids = set(claims)
    for cl in claims.values():
        for c in cl:
            for s in [c["mainsnak"]] + [q for qs in c.get("qualifiers", {}).values() for q in qs]:
                ref_ids.add(s["property"])
                dv = s.get("datavalue", {})
                if dv.get("type") == "wikibase-entityid":
                    ref_ids.add(dv["value"]["id"])
                if dv.get("type") == "quantity" and "/entity/" in dv["value"]["unit"]:
                    ref_ids.add(dv["value"]["unit"].rsplit("/", 1)[-1])
    lab = labels(sorted(ref_ids))
    out = {"id": e["id"], "redirected_from": e.get("redirects", {}).get("from"), "label": term(e, "labels"),
           "description": term(e, "descriptions"),
           "aliases": [a["value"] for k in ("en", "mul") for a in e.get("aliases", {}).get(k, [])],
           "claims": {}, "external_ids": {}, "sitelinks": {k: v["title"] for k, v in e.get("sitelinks", {}).items()}}
    for pid, cl in claims.items():
        # Best rank: preferred statements if any, else normal; deprecated never.
        best = [c for c in cl if c["rank"] == "preferred"] or [c for c in cl if c["rank"] == "normal"]
        pl = lab[pid]
        if pl["datatype"] == "external-id":
            vals = [c["mainsnak"]["datavalue"]["value"] for c in best if c["mainsnak"]["snaktype"] == "value"]
            out["external_ids"][pid] = {"label": pl["label"], "values": vals,
                                        "urls": [pl["formatter"].replace("$1", v) for v in vals] if pl["formatter"] else []}
            continue
        out["claims"][pid] = {"label": pl["label"], "count": len(cl), "values": [
            {"value": render(c["mainsnak"], lab),
             "qualifiers": {lab[q]["label"]: [render(s, lab) for s in qs] for q, qs in c.get("qualifiers", {}).items()},
             "references": len(c.get("references", []))} for c in best[:max_values]]}
    return out

# 1. Name -> Q-id
for name in ["Douglas Adams", "Paris", "Mercury"]:
    hits = search(name, limit=4)
    print(name, "->", [(h["id"], h["label"], (h["description"] or "")[:40], h["matched"]) for h in hits])

for q in ["Douglas Adams", "Douglas Adams haswbstatement:P31=Q5"]:
    r = text_search(q, limit=3)
    print(repr(q), r["total"], "hits ->", [(h["id"], h["label"], (h["description"] or "")[:40]) for h in r["hits"]])
for name in ["Douglas Adams", "Mercury"]:
    print("resolve", name, "->", [(h["id"], h["sitelinks"], (h["description"] or "")[:35]) for h in resolve(name)[:3]])

# 2. Full lookup: labels, claims, linked IDs
s = entity_summary("Q42")
print(s["id"], "|", s["label"], "|", s["description"], "| aliases:", s["aliases"])
print("  claims:", len(s["claims"]), "properties; external ids:", len(s["external_ids"]), "; sitelinks:", len(s["sitelinks"]))
for pid in ["P31", "P569", "P19", "P69", "P800", "P2048"]:
    c = s["claims"][pid]
    print(f"  {pid} {c['label']} ({c['count']}):", [(v["value"], v["qualifiers"]) for v in c["values"]][:2])
for pid in ["P214", "P345", "P646", "P227"]:
    x = s["external_ids"].get(pid)
    print(f"  {pid} {x['label']}: {x['values']} {x['urls'][:1]}")

# 3. Preferred rank wins; redirects and missing ids are reported
p = entity_summary("Q90")
print("Q90 population:", p["claims"]["P1082"]["count"], "statements, best:", p["claims"]["P1082"]["values"])
for eid, e in get_entities(["Q19746657", "Q999999999999"], props="labels").items():
    print(eid, "->", e.get("id"), term(e, "labels") if not e.get("missing") else None, "| redirects:", e.get("redirects"), "| missing:", "missing" in e)
```

Output observed on 2026-11-04:

```text
Douglas Adams -> [('Q28421831', 'Douglas Adams', 'American environmental engineer', 'label:Douglas Adams'), ('Q42', 'Douglas Adams', 'British science fiction writer and humor', 'label:Douglas Adams'), ('Q117249850', 'Douglas Adams', 'Global Co-Head of Equity Capital Markets', 'label:Douglas Adams'), ('Q61853920', 'Douglas H Adams', 'researcher ORCID ID = 0000-0002-3539-662', 'alias:Douglas Adams')]
Paris -> [('Q90', 'Paris', 'capital and most populous city in France', 'label:Paris'), ('Q483020', 'Paris Saint-Germain FC', 'association football club in Paris, Fran', 'label:Paris Saint-Germain FC'), ('Q830149', 'Paris', 'city in and county seat of Lamar County,', 'label:Paris'), ('Q18331346', 'Paris', 'family name', 'label:Paris')]
Mercury -> [('Q165745', 'Mercury Records', 'American record label', 'label:Mercury Records'), ('Q613883', 'Mercury', 'automobile marque of the Ford Motor Comp', 'label:Mercury'), ('Q1231263', 'Mercury', 'commune in Savoie, France', 'label:Mercury'), ('Q308', 'Mercury', 'first planet from the Solar System and s', 'label:Mercury')]
'Douglas Adams' 953 hits -> [('Q28421831', 'Douglas Adams', 'American environmental engineer'), ('Q3107329', "The Hitchhiker's Guide to the Galaxy", '1979 novel by Douglas Adams'), ('Q51132157', 'Travessa Douglas Adams', 'street in Brazil')]
'Douglas Adams haswbstatement:P31=Q5' 35 hits -> [('Q28421831', 'Douglas Adams', 'American environmental engineer'), ('Q42', 'Douglas Adams', 'British science fiction writer and humor'), ('Q10268476', 'Douglas Howe Adams', 'American cricket player (1876-1931)')]
resolve Douglas Adams -> [('Q42', 133, 'British science fiction writer and '), ('Q932869', 10, 'American professor of English'), ('Q21454969', 2, 'British painter (1853–1920)')]
resolve Mercury -> [('Q308', 274, 'first planet from the Solar System '), ('Q925', 187, 'chemical element with symbol Hg and'), ('Q1150', 88, 'Roman god of trade, merchants, thie')]
Q42 | Douglas Adams | British science fiction writer and humorist (1952–2001) | aliases: ['Douglas Noël Adams', 'Douglas Noel Adams', 'Douglas N. Adams']
  claims: 58 properties; external ids: 258 ; sitelinks: 133
  P31 instance of (1): [('human (Q5)', {'statement is subject of': ['Q42 (Q42395533)']})]
  P569 date of birth (1): [('1952-03-11', {})]
  P19 place of birth (1): [('Cambridge (Q350)', {})]
  P69 educated at (2): [('Brentwood School (Q4961791)', {'end time': ['1970'], 'start time': ['1959']}), ("St John's College (Q691283)", {'academic major': ['English literature (Q109587623)'], 'academic degree': ['Bachelor of Arts (Q1765120)'], 'start time': ['1971'], 'end time': ['1974']})]
  P800 notable work (3): [("The Hitchhiker's Guide to the Galaxy (Q25169)", {}), ('Dirk Gently series (Q20736364)', {})]
  P2048 height (1): [('1.96 metre', {})]
  P214 VIAF cluster ID: ['113230702'] ['https://viaf.org/en/viaf/113230702']
  P345 IMDb ID: ['nm0010930'] ['https://wikidata-externalid-url.toolforge.org/?p=345&url_prefix=https://www.imdb.com/&id=nm0010930']
  P646 Freebase ID: ['/m/0282x'] ['https://www.google.com/search?kgmid=/m/0282x']
  P227 GND ID: ['119033364'] ['https://d-nb.info/gnd/119033364']
Q90 population: 10 statements, best: [{'value': '2103778', 'qualifiers': {'determination method or standard': ['census (Q39825)'], 'point in time': ['2023-01-01']}, 'references': 1}]
Q999999999999 -> None None | redirects: None | missing: True
Q19746657 -> Q1000 Gabon | redirects: {'from': 'Q19746657', 'to': 'Q1000'} | missing: False
```

### 3. Lists with SPARQL (query.wikidata.org, browser `fetch`)

Self-contained. Opens the query UI at `https://query.wikidata.org/` (allowed) and POSTs to same-origin `/sparql`. Labels come from the `wikibase:label` service with `en,mul`.

```python
import json, time
from urllib.parse import urlencode

WDQS = "https://query.wikidata.org"
HEADERS = {"Accept": "application/sparql-results+json",
           "Content-Type": "application/x-www-form-urlencoded",
           "Api-User-Agent": "browser-harness-wikidata-skill/1.0 (https://github.com/browser-use/browser-harness)"}

# The query UI at query.wikidata.org/ is allowed by robots.txt; fetch() from it to /sparql is same-origin.
new_tab(WDQS + "/")
wait_for_load()
if not js("location.origin") == WDQS:
    raise RuntimeError(f"tab landed on {js('location.href')}: stop, do not retry around it")

# js() gives up after a few seconds and SPARQL can take up to 60 s, so start the fetch, then poll for it.
START_JS = """(() => { window.__wd = window.__wd || {}; const id = String(Math.random()).slice(2); window.__wd[id] = null;
  fetch('/sparql', {method: 'POST', headers: %s, body: %s})
    .then(async r => { window.__wd[id] = {status: r.status, retry: r.headers.get('retry-after'), text: await r.text()}; })
    .catch(e => { window.__wd[id] = {status: 0, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__wd[%s]; if (v) delete window.__wd[%s]; return v; })()"""

def sparql(query, tries=3, timeout=75):
    """Run one SPARQL query on the public endpoint. Returns a list of {var: value} dicts (ASK returns a bool).
    Backs off on 429 (Retry-After, max 120 s); raises on timeouts and syntax errors instead of reshaping the query."""
    body = urlencode({"query": query})
    for attempt in range(tries):
        rid = json.dumps(js(START_JS % (json.dumps(HEADERS), json.dumps(body))))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"no answer after {timeout}s")
            time.sleep(0.5)
        time.sleep(1)  # serial queries, one per second at most
        if r["status"] == 200:
            d = json.loads(r["text"])
            if "boolean" in d:
                return d["boolean"]
            return [{k: v["value"] for k, v in row.items()} for row in d["results"]["bindings"]]
        if r["status"] == 429 and attempt < tries - 1:
            time.sleep(min(120.0, float(r["retry"] or 30)))
            continue
        raise RuntimeError(f"HTTP {r['status']}: {r['text'][:300]}")
    raise RuntimeError("still throttled; stop and come back later")

def qid(uri):
    return uri.rsplit("/", 1)[-1]

# 1. A list: Nobel Prize in Physics (Q38104) laureates since 2020, with the year from the P585 qualifier.
t0 = time.time()
rows = sparql("""
SELECT ?person ?personLabel ?year WHERE {
  ?person p:P166 ?award .
  ?award ps:P166 wd:Q38104 ; pq:P585 ?date .
  BIND(YEAR(?date) AS ?year)
  FILTER(?year >= 2020)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,mul". }
} ORDER BY ?year ?personLabel""")
print(f"physics laureates since 2020: {len(rows)} rows in {time.time() - t0:.1f}s")
for r in rows:
    print("  ", r["year"], qid(r["person"]), r["personLabel"])

# 2. Reverse lookup: which item carries this external ID? (IMDb nm0010930, GND 119033364)
for pid, value in [("P345", "nm0010930"), ("P227", "119033364")]:
    rows = sparql(f'SELECT ?item ?itemLabel WHERE {{ ?item wdt:{pid} "{value}" . '
                  'SERVICE wikibase:label { bd:serviceParam wikibase:language "en,mul". } }')
    print(pid, value, "->", [(qid(r["item"]), r["itemLabel"]) for r in rows])

# 3. Ranked list with best-rank values only (wdt:): 5 most populous sovereign states (Q3624078).
rows = sparql("""
SELECT ?country ?countryLabel ?population ?capitalLabel WHERE {
  ?country wdt:P31 wd:Q3624078 ; wdt:P1082 ?population .
  OPTIONAL { ?country wdt:P36 ?capital . }
  FILTER NOT EXISTS { ?country wdt:P576 ?dissolved . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,mul". }
} ORDER BY DESC(?population) LIMIT 5""")
for r in rows:
    print("  ", qid(r["country"]), r["countryLabel"], f"{int(float(r['population'])):,}", "| capital:", r.get("capitalLabel"))

# 4. ASK and a syntax error (raised, not retried)
print("Q42 is human:", sparql("ASK { wd:Q42 wdt:P31 wd:Q5 }"))
try:
    sparql("SELECT ?x WHERE { ?x wdt:P31 }")
except RuntimeError as e:
    print("error:", str(e)[:120].replace("\n", " "))
```

Output observed on 2026-11-04:

```text
physics laureates since 2020: 18 rows in 7.1s
   2020 Q493956 Andrea M. Ghez
   2020 Q65807 Reinhard Genzel
   2020 Q193803 Roger Penrose
   2021 Q1235614 Giorgio Parisi
   2021 Q3675789 Syukuro Manabe
   2021 Q109370 Klaus Hasselmann
   2022 Q364997 Alain Aspect
   2022 Q78610 Anton Zeilinger
   2022 Q1365270 John Clauser
   2023 Q565544 Anne L'Huillier
   2023 Q86970 Ferenc Krausz
   2023 Q57020342 Pierre Agostini
   2024 Q92894 Geoffrey Hinton
   2024 Q391237 John Hopfield
   2025 Q555849 John Clarke
   2025 Q28976188 John M. Martinis
   2025 Q26703310 Michel Devoret
   2026 Q20942818 Francis Halzen
P345 nm0010930 -> [('Q42', 'Douglas Adams')]
P227 119033364 -> [('Q42', 'Douglas Adams')]
   Q148 People's Republic of China 1,404,890,000 | capital: Beijing
   Q668 India 1,326,093,247 | capital: New Delhi
   Q30 United States 340,110,988 | capital: Washington, D.C.
   Q252 Indonesia 275,439,000 | capital: Jakarta
   Q843 Pakistan 223,773,700 | capital: Islamabad
Q42 is human: True
error: HTTP 400: SPARQL-QUERY: queryStr=SELECT ?x WHERE { ?x wdt:P31 } java.util.concurrent.ExecutionException: org.openrdf.que
```

## Fields

`wd_entity(id)` (block 1) returns:

| Key | Source | Example / note |
|---|---|---|
| id, label, description | `mw.config` `wbEntityId`, `.wikibase-title-label`, heading description | `"Q42"`, `"Douglas Adams"`, `"British science fiction writer and humorist (1952–2001)"` |
| page_id, rev_id, url | `wgArticleId`, `wgCurRevisionId`, `location.href` | `rev_id` changes on every edit |
| redirected_from | `wgRedirectedFrom` | `"Q19746657"` for a merged item now at `Q1000` |
| missing | no `wbEntityId` and `wgArticleId` 0 | `true` for `Q999999999999` |
| datatype | `.wikibase-propertyview-datatype-value` | properties only: `"Item"` for P31 |
| terms | "In more languages" table | `{lang: {label, description, aliases}}`; a logged-out en browser always gets `mul` and `en` rows, sometimes more (`en-us`, `es`, `zh-hant` in one run, not in another); use the API for a fixed language set |
| statements[] / identifiers[] | `.wikibase-statementgroupview`, split by the `#claims` / `#identifiers` headings | `{property, property_label, values: [{rank, kind, text, entity, link, qualifiers, references}]}` |
| values[].kind | snak variation class | `value`, `somevalue` (unknown value) or `novalue` |
| values[].entity / link | first link with text in the value | `entity` = `Q5`/`P279` for item/property values; `link` = external URL (identifier link, Commons file page) |
| values[].qualifiers | qualifier snaks | `{property, property_label, kind, text, entity, link}`; the property name is shown once per group, the block copies it down |
| sitelinks[] | `.wikibase-sitelinkview` | `{site: "enwiki", title, url}` |

Block 2: `search()` -> `[{id, label, description, matched}]`; `text_search()` -> `{total, hits: [{id, label, description}]}`; `resolve()` adds `sitelinks` (count) and sorts by it; `get_entities()` -> `{requested id: wbgetentities JSON}` or `{"missing": True}`; `entity_summary()` -> `{id, redirected_from, label, description, aliases, claims: {pid: {label, count, values: [{value, qualifiers, references}]}}, external_ids: {pid: {label, values, urls}}, sitelinks: {site: title}}`. Block 3: `sparql()` -> list of `{var: value}` strings (URIs for items; `qid()` strips them) or a bool for ASK.

## Gotchas

- **Labels moved to `mul`.** Q42's English label row is empty and the page shows the `mul` ("default for all languages") label `Douglas Adams`; its aliases are under `mul` too. Always ask for `en|mul` (API) or `"en,mul"` (SPARQL label service) and fall back to `mul`.
- **Search order is not popularity.** `wbsearchentities` and `list=search` (even with `haswbstatement:P31=Q5`) both returned `Q28421831` (American environmental engineer) before `Q42`; `list=search` also reordered its lower hits between two runs. Sorting by sitelink count put `Q42` (133) first; for `Mercury` it gives the planet (274), then the element (187), then the god (88). Read the description before picking.
- **Coordinate values carry a map.** The P625 cell lazy-loads an interactive map whose zoom buttons and attribution end up in `textContent` once it renders; block 1 removes the map before reading the value.
- **Ranks.** Best rank = preferred statements if any, else normal; deprecated never. `wdt:` in SPARQL and `entity_summary()` follow that. Preferred is an editor's choice, not "newest": India's preferred P1082 is the 2020 figure 1,326,093,247 while a normal-rank 2018 value is 1,349,217,956. Read `p:`/`pq:P585` (point in time) when the date matters.
- **Page order is raw order.** On `/wiki/Property:P31` the first P31 value is a deprecated one; block 1 keeps every value with its rank, and `first()` skips deprecated and prefers preferred.
- **One unknown id fails the whole `wbgetentities` call** with `no-such-entity` (HTTP 200, `error.id` names it). `get_entities()` marks that id missing and asks again without it. Redirected ids come back under the target id with `redirects: {from, to}`.
- **Formatter URLs vary.** P1630 can have several values; take the preferred one. IMDb (P345) uses a Toolforge redirector because one property covers several IMDb id prefixes; Freebase (P646) points at a Google search. The entity page renders its own links (VIAF `https://viaf.org/en/viaf/113230702`).
- **Commons media values** (P18 image) render a thumbnail link before the file link plus a `600 × 386; 38 KB` size line; block 1 takes the first link that has text. Q42's P18 has 25 qualifiers: one `media legend` per language.
- **Big pages.** Q42 has 58 statement properties, 258 identifier properties and 133 sitelinks (page height ~56,000 px); Q90 has 437 statement values. The single `js()` extract still finishes well inside the 5 s limit; whole block 1 runs in ~14 s.
- **SPARQL needs start-and-poll.** The laureates query took 1.7-9 s (faster when repeated), and can pass `js()`'s 5 s limit. A bad query returns HTTP 400 with a Java stack trace in the body; the block raises instead of rewriting the query.
- **Crowd-edited data lags.** The physics query returned only one 2026 laureate on 2026-11-04; check recent events against a primary source.

## What does not work

- `/wiki/Special:EntityData/Q42.json`, `/wiki/Special:Search` and every other `/wiki/Special:` page: robots-disallowed; `wd_entity()` refuses them before loading. Use `wbgetentities` and `wbsearchentities`/`list=search` in block 2 instead.
- `/w/index.php` views (history, raw): robots-disallowed and not an official API; not used.
- query-scholarly.wikidata.org: during authoring it answered 429 "Aggressively rate-limiting to 1 req / min" (an outage rule); not used, not worked around.
- Not tested: the Wikibase REST API (`/w/rest.php/wikibase/v1/...`), Lexeme pages beyond the path mapping, and editing (needs login). Plain HTTP (curl with a descriptive User-Agent) answered `api.php` and `/sparql` during authoring, but the blocks here are the browser path.
