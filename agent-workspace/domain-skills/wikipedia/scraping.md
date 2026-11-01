# Wikipedia - Article Text, Infobox and Sections (pages + MediaWiki API)

Field-tested against en.wikipedia.org on 2026-11-01 using a Browser Use cloud browser, logged out. No CAPTCHA, 429 or block seen across ~45 page loads and ~35 API calls.

robots.txt (checked 2026-11-01, one `User-agent: *` group) allows `/wiki/<Article>` and disallows `/w/`, `/api/`, `/wiki/Special:` and a list of `Wikipedia:` process pages (deletion, checkuser...), with four narrow Allow exceptions (`/w/api.php?action=mobileview&`, `/w/load.php?`, `/api/rest_v1/?doc`, `/w/rest.php/site/v1/sitemap`); block 1 loads only allowed `/wiki/` pages, and block 2 calls the robots-disallowed `/w/api.php` and `/api/rest_v1/` paths only because they are Wikimedia's official public APIs.

## Quick summary

- **Article page** (`/wiki/<Title>`, block 1): one `js()` call returns title, page id, revision, Wikidata id, short description, lead text, every section (level, heading, anchor, plain text), the infobox as label/value rows under their header groups, categories and the last-edited line. Citation markers (`[12]`), edit links, hidden sort keys and reference lists are stripped.
- **Redirects, disambiguation, missing pages** are reported, not guessed: `/wiki/Ada_Byron` serves Ada Lovelace with `redirected_from: "Ada_Byron"`; `Mercury` has `disambiguation: true`; an unknown title returns `missing: true` (`wgArticleId` 0).
- **Official API** (block 2, same-origin `fetch()` from a Wikipedia tab): search, batch metadata for up to 50 titles per call (redirects, disambiguation, short description, Wikidata id), the whole article as plain text split into sections (TextExtracts), the table of contents (`prop=tocdata`), the infobox as raw template fields from wikitext, and the REST page summary. 7 API calls ran in ~8 s.
- **Page HTML vs API infobox:** the page gives rendered values (`10 December 1815 / London, England`); the API gives template source (`{{birth date|df=y|1815|12|10}}`). Pick by need.
- Both blocks read robots.txt or stay on the official API, sleep between requests, and raise on a page with no article instead of retrying around it.

## What works

### 1. Article text, infobox and sections from `/wiki/<Title>` (browser)

Self-contained; reads robots.txt in the tab first, then loads 6 articles in the same tab (~13 s in a cloud browser). The last two titles are refused by the robots guard without loading.

```python
import json, time
from urllib.parse import quote, unquote, urlparse

BASE = "https://en.wikipedia.org"
_TAB = []

def _open(url):
    if _TAB:
        goto_url(url)
    else:
        new_tab(url)
        _TAB.append(current_tab())
    wait_for_load()

# robots.txt, group "User-agent: *" (the only one on en.wikipedia.org): plain prefix rules,
# longest match wins, Allow wins a tie. Read once, in the same tab, before any article load.
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
    # Rules list both "Special:" and "Special%3A" spellings, so test raw, decoded and fully-encoded forms.
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
  const root = document.querySelector('#mw-content-text .mw-parser-output');
  if (typeof mw === 'undefined' || !document.querySelector('#firstHeading')) return null;
  const cfg = k => mw.config.get(k);
  const base = {title: document.querySelector('#firstHeading').textContent.trim(), page_id: cfg('wgArticleId'),
                url: location.href, redirected_from: cfg('wgRedirectedFrom')};
  if (!cfg('wgArticleId') || !root) return {...base, missing: true};
  const clean = el => { const c = el.cloneNode(true);
    c.querySelectorAll('sup.reference, sup.noprint, .mw-editsection, style, link, .noprint, [style*="display:none"]')
     .forEach(n => n.remove());
    c.querySelectorAll('br').forEach(b => b.replaceWith('\n'));
    c.querySelectorAll('li, div, p').forEach(b => b.append('\n'));
    return c.textContent.replace(/[\u200b\ufeff]/g, '').replace(/[ \t\u00a0]+/g, ' ')
            .replace(/ *\n */g, '\n').replace(/\n{2,}/g, '\n').trim(); };
  // Infobox: first table.infobox in the article body; rows are label/value pairs under header groups.
  let infobox = null;
  const ib = root.querySelector('table.infobox');
  if (ib) {
    const img = ib.querySelector('.infobox-image img, .infobox-full-data img');
    const cap = ib.querySelector('.infobox-caption');
    infobox = {class: ib.className, title: null, image: img ? img.src : null, caption: cap ? clean(cap) : null, rows: []};
    let group = null;
    for (const tr of ib.querySelectorAll(':scope > tbody > tr')) {
      const th = tr.querySelector(':scope > th'), td = tr.querySelector(':scope > td');
      if (th && th.matches('.infobox-above, .infobox-title') && !infobox.title) infobox.title = clean(th);
      else if (th && th.matches('.infobox-header')) group = clean(th);
      else if (th && td) {
        // Settlement-style boxes: a "mergedtoprow" label row starts a new top-level entry, ending the group.
        if (tr.classList.contains('mergedtoprow')) group = null;
        infobox.rows.push({group, label: clean(th), value: clean(td)});
      } else if (!th && td && td.matches('.infobox-full-data') && !td.querySelector('img')) {
        const v = clean(td); if (v) infobox.rows.push({group, label: null, value: v});  // e.g. "In office ..."
      }
    }
  }
  // Sections: walk headings and text blocks in document order (works with or without <section> wrappers).
  const SKIP = 'table, figure, .infobox, .navbox, .hatnote, .reflist, .refbegin, .references, .mw-references-wrap, ' +
               '.thumb, .gallery, .metadata, .ambox, .sidebar, .shortdescription, .toc, .noprint, .mw-heading';
  let cur = {level: 1, heading: null, anchor: null, text: []};
  const sections = [cur];
  for (const n of root.querySelectorAll('.mw-heading, p, ul, ol, dl, blockquote')) {
    if (n.matches('.mw-heading')) {
      const h = n.querySelector('h2, h3, h4, h5, h6');
      cur = {level: +h.tagName[1], heading: clean(h), anchor: h.id, text: []};
      sections.push(cur); continue;
    }
    // Skip reference lists, navboxes, tables, captions etc., and lists nested in another text block.
    const skip = n.closest(SKIP) || n.parentElement.closest('p, ul, ol, dl, blockquote');
    if (skip && root.contains(skip)) continue;
    const t = clean(n); if (t) cur.text.push(t);
  }
  const cats = cfg('wgCategories') || [];
  const sd = root.querySelector('.shortdescription');
  return {...base, missing: false, rev_id: cfg('wgCurRevisionId'), wikidata: cfg('wgWikibaseItemId'),
    short_description: sd ? sd.textContent.trim() : null,
    disambiguation: cats.includes('Disambiguation pages') || !!document.querySelector('#disambigbox'),
    lead: sections[0].text.join('\n'),
    sections: sections.slice(1).map(s => ({level: s.level, heading: s.heading, anchor: s.anchor, text: s.text.join('\n')})),
    infobox,
    categories: [...document.querySelectorAll('#mw-normal-catlinks li a')].map(a => a.textContent),
    last_modified: (document.querySelector('#footer-info-lastmod') || {textContent: ''}).textContent.trim()};
})()
"""

def wiki_path(title):
    return "/wiki/" + quote(title.replace(" ", "_"), safe="/:(),'!*$;@~-._")

def wiki_article(title):
    """Load /wiki/<title> in the tab and return lead, sections, infobox and page metadata.
    Raises PermissionError on a robots-disallowed path, RuntimeError on a page that is not an article view."""
    path = wiki_path(title)
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
        raise RuntimeError(f"no article on {info['url']} ({info['title']!r}); a block or challenge page? "
                           "Stop here, do not retry around it.")
    time.sleep(1)  # one page per second at most; robots.txt asks for low-speed bots
    return data

for t in ["Ada Lovelace", "Tokyo", "Barack Obama"]:
    a = wiki_article(t)
    print(a["title"], a["page_id"], a["rev_id"], a["wikidata"], "|", a["short_description"], "|", a["last_modified"])
    print("  lead:", len(a["lead"]), "chars:", a["lead"][:120].replace("\n", " "))
    print("  sections:", len(a["sections"]), [(s["level"], s["heading"], len(s["text"])) for s in a["sections"][:5]],
          "... last:", [(s["heading"], len(s["text"])) for s in a["sections"][-3:]])
    ib = a["infobox"]
    print("  infobox:", ib["class"], "|", repr(ib["title"]), "|", len(ib["rows"]), "rows | image:", (ib["image"] or "")[:70])
    for r in [r for r in ib["rows"] if r["group"]][:3] + [r for r in ib["rows"] if not r["group"]][:2]:
        print("    ", r["group"], "|", r["label"], "=", r["value"].replace("\n", " / ")[:80])
    print("  categories:", len(a["categories"]), a["categories"][:3])

for t in ["Ada Byron", "Mercury", "Zzzqqqnonexistent page xyz"]:
    a = wiki_article(t)
    print(t, "->", a["title"], "| redirected_from:", a["redirected_from"], "| missing:", a["missing"],
          "| disambiguation:", a.get("disambiguation"), "| sections:", len(a.get("sections") or []))

for t in ["Special:Random", "Wikipedia:Articles for deletion/Foo"]:
    try:
        wiki_article(t)
    except PermissionError as e:
        print("refused:", e)
```

Output observed on 2026-11-01:

```text
Ada Lovelace 974 1381003492 Q7259 | English mathematician (1815–1852) | This page was last edited on 19 October 2026, at 10:59 (UTC).
  lead: 3186 chars: Augusta Ada King, Countess of Lovelace (née Byron; 10 December 1815 – 27 November 1852), also known as Ada Lovelace, was
  sections: 29 [(2, 'Biography', 0), (3, 'Childhood', 3977), (3, 'Adult years', 4032), (3, 'Education', 1721), (3, 'Death', 756)] ... last: [('General and cited sources', 0), ('Further reading', 569), ('External links', 1451)]
  infobox: infobox biography vcard | 'The Right Honourable\nThe Countess of Lovelace' | 7 rows | image: https://thumb.wikimedia.org/wikipedia/commons/thumb/4/4c/Ada_Lovelace_
     None | Born = Augusta Ada Byron / 10 December 1815 / London, England
     None | Died = 27 November 1852 (aged 36) / Marylebone, London, England
  categories: 28 ['Ada Lovelace', '1815 births', '1852 deaths']
Tokyo 30057 1382193196 Q1490 | Capital and most populous city of Japan | This page was last edited on 27 October 2026, at 05:32 (UTC).
  lead: 3760 chars: Tokyo, officially the Tokyo Metropolis, is the capital and most populous city of Japan. The population of the city prope
  sections: 61 [(2, 'Etymology', 910), (2, 'History', 0), (3, 'Pre-Tokugawa period', 1595), (3, '1590–1868: Tokugawa period', 1921), (3, '1868–1941', 3062)] ... last: [('Guides', 258), ('Contemporary', 1395), ('External links', 73)]
  infobox: infobox ib-settlement vcard | 'Tokyo\n東京都' | 35 rows | image: https://thumb.wikimedia.org/wikipedia/commons/thumb/b/b2/Skyscrapers_o
     Government | • Body = Tokyo Metropolitan Government
     Government | • Governor = Yuriko Koike (indp.)
     Government | • Representatives = 42
     None | None = Tokyo Metropolis
     None | None = Nicknames: The Big Mikan
  categories: 10 ['Tokyo', '1450s establishments in Japan', '1457 establishments in Asia']
Barack Obama 534366 1383215959 Q76 | President of the United States from 2009 to 2017 | This page was last edited on 1 November 2026, at 16:15 (UTC).
  lead: 4209 chars: Barack Hussein Obama II (born August 4, 1961) is an American retired politician who served as the 44th president of the
  sections: 48 [(2, 'Early life and career', 2730), (3, 'Education', 2203), (4, 'College and research jobs', 1040), (4, 'Community organizer and Harvard Law School', 1701), (4, 'University of Chicago Law School', 682)] ... last: [('External links', 0), ('Official', 120), ('Other', 484)]
  infobox: infobox vcard | 'Barack Obama' | 20 rows | image: https://thumb.wikimedia.org/wikipedia/commons/thumb/8/8d/President_Bar
     44th President of the United States | None = In office / January 20, 2009 – January 20, 2017
     44th President of the United States | Vice President = Joe Biden
     44th President of the United States | Preceded by = George W. Bush
  categories: 82 ['Barack Obama', '1961 births', '20th-century African-American academics']
Ada Byron -> Ada Lovelace | redirected_from: Ada_Byron | missing: False | disambiguation: False | sections: 29
Mercury -> Mercury | redirected_from: None | missing: False | disambiguation: True | sections: 27
Zzzqqqnonexistent page xyz -> Zzzqqqnonexistent page xyz | redirected_from: None | missing: True | disambiguation: None | sections: 0
refused: robots.txt disallows /wiki/Special:Random
refused: robots.txt disallows /wiki/Wikipedia:Articles_for_deletion/Foo
```

### 2. Official MediaWiki API from a Wikipedia tab (browser `fetch`)

Self-contained. Opens `/wiki/Main_Page` once so `fetch()` is same-origin, then calls only `/w/api.php` and `/api/rest_v1/`.

```python
import html, json, re, time
from urllib.parse import urlencode, quote

BASE = "https://en.wikipedia.org"
# Wikimedia asks API clients to identify themselves; from a browser, Api-User-Agent is the header for that.
# The browser's own User-Agent is left untouched.
HEADERS = {"Api-User-Agent": "browser-harness-wikipedia-skill/1.0 (https://github.com/browser-use/browser-harness)"}

# Same-origin fetch() needs a tab on en.wikipedia.org; /wiki/Main_Page is allowed by robots.txt.
new_tab(BASE + "/wiki/Main_Page")
wait_for_load()

def _fetch(url):
    raw = js("""(async () => { const r = await fetch(%s, {headers: %s});
      return JSON.stringify({status: r.status, retry: r.headers.get('retry-after'), body: await r.text()}); })()"""
             % (json.dumps(url), json.dumps(HEADERS)))
    return json.loads(raw)

def _get_json(url, tries=3):
    """GET a same-origin JSON URL. Backs off on 429/503 or an API maxlag error (Retry-After, max 60 s), then raises."""
    for i in range(tries):
        r = _fetch(url)
        body = json.loads(r["body"]) if r["body"][:1] in "{[" else {}
        err = body.get("error") or {}
        if r["status"] in (429, 503) or err.get("code") == "maxlag":
            wait = min(60.0, float(r["retry"] or 5 * 2 ** i))
            if i < tries - 1:
                time.sleep(wait)
                continue
        if r["status"] != 200 or err:
            raise RuntimeError(f"{url}: HTTP {r['status']} {err or r['body'][:200]!r}")
        time.sleep(0.3)  # serial requests, small gap
        return body
    raise RuntimeError(f"{url}: still throttled after {tries} tries; stop and come back later")

def api(**params):
    """MediaWiki Action API (/w/api.php), JSON format version 2."""
    q = {"format": "json", "formatversion": 2, "maxlag": 5, **params}
    return _get_json(BASE + "/w/api.php?" + urlencode(q))

def search(query, limit=10, offset=0):
    r = api(action="query", list="search", srsearch=query, srlimit=limit, sroffset=offset, srprop="snippet|wordcount|timestamp")
    hits = [{"title": h["title"], "page_id": h["pageid"], "words": h.get("wordcount"),
             "snippet": html.unescape(re.sub(r"<[^>]+>", "", h.get("snippet", "")))} for h in r["query"]["search"]]
    nxt = (r.get("continue") or {}).get("sroffset")
    return {"total": r["query"]["searchinfo"]["totalhits"], "hits": hits, "next_offset": nxt}

def page_meta(titles):
    """Up to 50 titles per call. Follows redirects; returns {requested title: meta}."""
    r = api(action="query", titles="|".join(titles), redirects=1, prop="info|pageprops")["query"]
    pages = {p["title"]: p for p in r["pages"]}
    norm = {n["from"]: n["to"] for n in r.get("normalized", [])}
    redir = {n["from"]: n["to"] for n in r.get("redirects", [])}
    out = {}
    for t in titles:
        final = norm.get(t, t)
        redirected = final in redir
        while final in redir:
            final = redir[final]
        p = pages.get(final, {})
        pp = p.get("pageprops") or {}
        out[t] = {"title": p.get("title", final), "page_id": p.get("pageid"), "missing": bool(p.get("missing") or p.get("invalid")),
                  "redirected": redirected,
                  "disambiguation": "disambiguation" in pp, "short_description": pp.get("wikibase-shortdesc"),
                  "wikidata": pp.get("wikibase_item"), "rev_id": p.get("lastrevid"), "bytes": p.get("length"), "touched": p.get("touched")}
    return out

def plain_text(title):
    """Whole article as plain text (TextExtracts), split on its == Heading == lines. No infobox, tables or references."""
    p = api(action="query", titles=title, redirects=1, prop="extracts", explaintext=1, exsectionformat="wiki")["query"]["pages"][0]
    if p.get("missing"):
        return None
    parts = re.split(r"^(={2,6})\s*(.+?)\s*\1\s*$", p["extract"], flags=re.M)
    sections = [{"level": 1, "heading": None, "text": parts[0].strip()}]
    for i in range(1, len(parts), 3):
        sections.append({"level": len(parts[i]), "heading": parts[i + 1], "text": parts[i + 2].strip()})
    return {"title": p["title"], "page_id": p["pageid"], "sections": sections}

def toc(title):
    r = api(action="parse", page=title, redirects=1, prop="tocdata|revid")["parse"]
    return [{"number": s["number"], "level": s["hLevel"], "heading": s["line"], "anchor": s["anchor"]} for s in r["tocdata"]["sections"]]

def _split_top(s, sep="|"):
    """Split on sep outside {{...}}, [[...]] and {{{...}}}."""
    out, depth, cur, i = [], 0, [], 0
    while i < len(s):
        two = s[i:i + 2]
        if two in ("{{", "[["):
            depth += 1; cur.append(two); i += 2; continue
        if two in ("}}", "]]") and depth:
            depth -= 1; cur.append(two); i += 2; continue
        if s[i] == sep and depth == 0:
            out.append("".join(cur)); cur = []; i += 1; continue
        cur.append(s[i]); i += 1
    out.append("".join(cur))
    return out

def infobox_wikitext(title):
    """Raw parameters of the first {{Infobox ...}} template in the lead section's wikitext."""
    wt = api(action="parse", page=title, redirects=1, prop="wikitext", section=0)["parse"]["wikitext"]
    wt = re.sub(r"<!--.*?-->", "", wt, flags=re.S)
    m = re.search(r"\{\{\s*Infobox[ _]", wt, re.I)
    if not m:
        return None
    depth, i = 0, m.start()
    while i < len(wt):
        if wt.startswith("{{", i):
            depth += 1; i += 2
        elif wt.startswith("}}", i):
            depth -= 1; i += 2
            if depth == 0:
                break
        else:
            i += 1
    body = wt[m.start() + 2:i - 2]
    name, *params = _split_top(body)
    fields = {}
    for p in params:
        k, eq, v = p.partition("=")
        if eq and k.strip():
            fields[k.strip()] = v.strip()
    return {"template": name.strip(), "fields": fields}

def rest_summary(title):
    return _get_json(BASE + "/api/rest_v1/page/summary/" + quote(title.replace(" ", "_"), safe=""))

# 1. Find the article
s = search("analytical engine Babbage", limit=5)
print("search total:", s["total"], "next_offset:", s["next_offset"])
for h in s["hits"]:
    print("  ", h["page_id"], h["title"], h["words"], "|", h["snippet"][:70])

# 2. Batch metadata, redirects and disambiguation flags for several titles in one call
for t, m in page_meta(["Ada Byron", "Tokyo", "Mercury", "Zzzqqqnonexistent page xyz", "python (programming language)"]).items():
    print(f"  {t!r} -> {m['title']!r} id={m['page_id']} missing={m['missing']} redirected={m['redirected']} "
          f"disambig={m['disambiguation']} wd={m['wikidata']} | {m['short_description']}")

# 3. Full plain text split into sections
pt = plain_text("Ada Lovelace")
print(pt["title"], pt["page_id"], len(pt["sections"]), "sections;", "lead", len(pt["sections"][0]["text"]), "chars")
print("  ", [(x["level"], x["heading"], len(x["text"])) for x in pt["sections"][1:6]])

# 4. Table of contents (headings, numbering, anchors)
tc = toc("Ada Lovelace")
print("toc:", len(tc), tc[:3])

# 5. Infobox as raw template fields
ib = infobox_wikitext("Ada Lovelace")
print("infobox:", ib["template"], len(ib["fields"]), "fields")
for k in ("name", "birth_date", "death_date", "known_for", "spouse"):
    print("  ", k, "=", ib["fields"].get(k, "")[:90])
ib2 = infobox_wikitext("Tokyo")
print("infobox:", ib2["template"], len(ib2["fields"]), "fields; population_total =", ib2["fields"].get("population_total"))

# 6. REST page summary (lead extract, thumbnail, description)
r = rest_summary("Ada Lovelace")
print("summary:", r["title"], r["type"], r["description"], r["revision"], "|", r["extract"][:100])
```

Output observed on 2026-11-01:

```text
search total: 181 next_offset: 5
   1271 Analytical engine 3875 | century after Babbage had proposed the pioneering analytical engine. B
   5698 Charles Babbage 12304 | century. Babbage, who died before the complete successful engineering
   8324 Difference engine 4547 | success of the difference engine. By improving the concept as an analy
   974 Ada Lovelace 10098 | writer chiefly known for work on Charles Babbage's proposed mechanical
   73053077 Henry Prevost Babbage 172 | works included Babbage's Calculating Engines (1889) and a working Anal
  'Ada Byron' -> 'Ada Lovelace' id=974 missing=False redirected=True disambig=False wd=Q7259 | English mathematician (1815–1852)
  'Tokyo' -> 'Tokyo' id=30057 missing=False redirected=False disambig=False wd=Q1490 | Capital and most populous city of Japan
  'Mercury' -> 'Mercury' id=19007 missing=False redirected=False disambig=True wd=Q48397 | Topics referred to by the same term
  'Zzzqqqnonexistent page xyz' -> 'Zzzqqqnonexistent page xyz' id=None missing=True redirected=False disambig=False wd=None | None
  'python (programming language)' -> 'Python (programming language)' id=23862 missing=False redirected=False disambig=False wd=Q28865 | General-purpose programming language
Ada Lovelace 974 30 sections; lead 3186 chars
   [(2, 'Biography', 0), (3, 'Childhood', 3981), (3, 'Adult years', 4033), (3, 'Education', 1722), (3, 'Death', 756)]
toc: 29 [{'number': '1', 'level': 2, 'heading': 'Biography', 'anchor': 'Biography'}, {'number': '1.1', 'level': 3, 'heading': 'Childhood', 'anchor': 'Childhood'}, {'number': '1.2', 'level': 3, 'heading': 'Adult years', 'anchor': 'Adult_years'}]
infobox: Infobox scientist 16 fields
   name = The Countess of Lovelace
   birth_date = {{birth date|df=y|1815|12|10}}
   death_date = {{death date and age|df=y|1852|11|27|1815|12|10}}
   known_for = [[Mathematics]], [[computing]]
   spouse = {{marriage|[[William King-Noel, 1st Earl of Lovelace]]|1835}}
infobox: Infobox settlement 95 fields; population_total = 14,254,039
summary: Ada Lovelace standard English mathematician (1815–1852) 1381003492 | Augusta Ada King, Countess of Lovelace, also known as Ada Lovelace, was an English mathematician and
```

## Fields

`wiki_article(title)` returns:

| Key | Source | Example / note |
|---|---|---|
| title | `#firstHeading` | `"Ada Lovelace"` (target title after a redirect) |
| page_id, rev_id | `mw.config` `wgArticleId`, `wgCurRevisionId` | `974`, `1381003492` |
| url | `location.href` | canonical URL; the address bar is rewritten after a redirect |
| redirected_from | `wgRedirectedFrom` | `"Ada_Byron"` or `null` |
| missing | `wgArticleId == 0` | `true` returns only `title, page_id, url, redirected_from, missing` |
| wikidata | `wgWikibaseItemId` | `"Q7259"` |
| short_description | `.shortdescription` (hidden div) | `"English mathematician (1815–1852)"` |
| disambiguation | category "Disambiguation pages" or `#disambigbox` | `true` for `Mercury` |
| lead | text blocks before the first heading | 3186 chars for Ada Lovelace |
| sections[] | `.mw-heading` + following `p, ul, ol, dl, blockquote` | `{level: 2..6, heading, anchor, text}`; parent headings with only subsections have `text: ""` |
| infobox | first `table.infobox` | `{class, title, image, caption, rows: [{group, label, value}]}` or `null`; `label` is `null` for full-width rows such as "In office ..." |
| categories | `#mw-normal-catlinks` | visible categories only (28 for Ada Lovelace) |
| last_modified | `#footer-info-lastmod` | `"This page was last edited on 19 October 2026, at 10:59 (UTC)."` |

Block 2 helpers: `search()` -> `{total, hits: [{title, page_id, words, snippet}], next_offset}`; `page_meta()` -> `{requested: {title, page_id, missing, redirected, disambiguation, short_description, wikidata, rev_id, bytes, touched}}`; `plain_text()` -> `{title, page_id, sections: [{level, heading, text}]}` (lead is `level 1, heading None`); `toc()` -> `[{number, level, heading, anchor}]`; `infobox_wikitext()` -> `{template, fields}` or `None`; `rest_summary()` -> Wikimedia's summary JSON (`title, type, description, extract, thumbnail, revision, timestamp, content_urls...`).

## Gotchas

- **Article HTML uses `<section>` wrappers** (Parsoid read views) while `action=parse&prop=text` returns the older flat HTML. Block 1 walks `.mw-heading` and text blocks in document order, so it works on both.
- **Hidden text leaks without cleanup.** Dates carry a hidden ISO copy (`(1815-12-10)` in a `display:none` span); `clean()` drops `[style*="display:none"]`, `sup.reference`, `.noprint` and `.mw-editsection`.
- **Infobox shapes differ.** Biography boxes have flat rows; settlement boxes group rows under `infobox-header` (`Government`, `Area`, `Population`) with labels like `• Total`; officeholder boxes have one header per office plus a label-less "In office" row. The rendered class (`infobox biography vcard`) does not name the template (`Infobox scientist`); use block 2 for the template name.
- **Section text excludes** tables, figures and captions, navboxes, hatnotes, maintenance boxes, `.noprint` widgets (spoken-article players fill in late and leaked into `External links` on one run) and reference lists. `References`/`Citations` sections therefore come back empty or short; use `Further reading`/`External links` text or the API for references.
- **Redirects:** the page is served at the requested URL and its address is rewritten by script; `page_info()["url"]` already showed `/wiki/Ada_Lovelace`. `page_meta()` distinguishes a real redirect from title normalization (`python (programming language)` is normalized, not redirected).
- **Plain-text extract vs page text:** TextExtracts drops infoboxes and tables but keeps reference-free prose; section lengths matched the page within a few chars (Childhood 3981 vs 3977).
- **`prop=sections` is deprecated** in `action=parse` (API warning: use `prop=tocdata`). `tocdata` keys are camelCase (`hLevel`, `tocLevel`).
- **Wikitext infobox fields are raw**: templates, links and `<ref>` tags stay in the values; `infobox_wikitext()` only strips HTML comments and splits on top-level `|`.
- `maxlag=5` makes the API refuse work when replicas lag; `_get_json` waits (Retry-After, max 60 s) and retries twice, then raises.

## What does not work

- `/wiki/Special:*` pages (Random, Search, Export, WhatLinksHere...): robots-disallowed; `wiki_article()` refuses them before loading. Use `list=search` in block 2 instead of `Special:Search`.
- `/w/index.php?...` views (history, raw, printable): robots-disallowed and not an official API; not used.
- Wikipedia process pages such as `Wikipedia:Articles_for_deletion/...`: robots-disallowed; refused by the guard.
- Plain HTTP clients without a browser were not tested here; Wikimedia's API etiquette asks scripts to send a descriptive User-Agent with contact details.
