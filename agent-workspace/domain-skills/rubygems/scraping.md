# RubyGems.org - Look Up a Ruby Gem's Latest Version, Total Downloads, Licences, Homepage and Source Links, and the Gems That Depend on It (JSON API, no key)

Field-tested against rubygems.org on 2026-11-20 (US Pacific afternoon; 23:52 UTC on 20 November to 00:01 UTC on 21 November) using a fresh Browser Use cloud browser (logged out; one session, 23:54-00:00 UTC) plus Python `urllib` and `curl` from a Linux machine. 15 browser page loads (the Acceptable Use policy 5 times; robots.txt, https://guides.rubygems.org/robots.txt, the Terms of Service, the rate-limits guide and the rails gem page 2 times each) and 104 in-page `fetch()` calls (block 1 ran 4 times, the first two stopped early by bugs fixed below; block 2 ran twice), 79 curl calls (64 while exploring, 15 in block 4) and 74 urllib calls (block 3 twice), all serial and at least 0.3 s apart (the blocks wait 0.5-1 s). Every call was HTTP 200 except the deliberate probes below: HTTP 404 (a gem name in the wrong case, an unknown gem, a version that is no longer listed), HTTP 400 (search without `query`, search `page=334`) and HTTP 304 (conditional GETs on the versions list). curl timed the first 12 answers at 0.03-0.45 s. No 429, no challenge, no key, no login. Block 1's output below is its third run (23:55 UTC; a fourth run at 00:00 UTC printed the same numbers), block 2's its second (00:00 UTC), block 3's its second (empty cache, after a robots.txt matching fix), block 4's its first. An independent verifier re-ran all four blocks verbatim on 21 November, 00:03-00:05 UTC, in a new cloud browser and an empty cache: every version, licence, link, dependent count, ranking, search result and probe matched; only download totals, byte sizes and `Age` moved. Block 4 was re-run after a comment fix (00:09 UTC, same output apart from moving counts).

robots.txt (checked 2026-11-20, curl, the cloud browser and block 3's own matcher): https://rubygems.org/robots.txt has one group, `User-agent: *`, with `Disallow: /downloads/`, `/gems?letter=*`, `/search?*`, `/names` and `/news`, and no named AI-agent groups, so GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider fall under `*` and may fetch everything under `/api/v1/` and `/api/v2/`, `/info/` and `/gems/<name>/reverse_dependencies` (block 3 checks all 11 agents on every path used). The HTML search page `/search?query=` is disallowed; this skill uses `/api/v1/search.json` instead. https://guides.rubygems.org/robots.txt is `User-agent: *`, `Allow: /`. Terms: the Terms of Service https://rubygems.org/policies/terms-of-service ("Last updated Jun 25, 2025") say the service is "operated by Ruby Central, Inc." and that "Provider shall retain all right, title, and interest to Provider's trademarks, branding, logos, and related assets". The Acceptable Use policy https://rubygems.org/policies/acceptable-use ("Last updated: Jun 25, 2025") forbids content or activity that "Uses the platform for any form of excessive automated bulk activity such as spamming, cryptocurrency mining, or any activity that places undue burden on our servers through automated means." The rate-limits guide https://guides.rubygems.org/rubygems-org-rate-limits/ gives "API and website: 10 requests per second" and "Dependency API: 15 requests per second", and says the team "may occasionally blackhole user IP addresses for extreme cases". No AI/ML, scraping, crawling, robot or non-commercial wording on these pages (block 2 checks the quotes and scans the Terms of Service for the words; a verifier's scan of all three pages on 21 November found none either). Licence: none stated for registry metadata (the Acceptable Use page says the policy text itself is under CC BY 4.0); the Terms of Service say publishers "grant to users of the Service a non-exclusive, worldwide, royalty-free, license to download and reproduce Your Content" and that "All other use of Your Content is subject to any license terms you have applied", so each gem's code has its own licence (`licenses` field), which this skill reports but does not download. Naming: this skill writes "RubyGems.org" in plain text and shows no RubyGems, Ruby or Ruby Central logo; it is not affiliated with or endorsed by Ruby Central or RubyGems.org.

## Quick summary

- **No scraping needed for the facts.** `GET https://rubygems.org/api/v1/gems/rails.json` -> `{"name": "rails", "version": "8.1.4.1", "version_created_at": "2026-11-04T...", "downloads": 820132401, "licenses": ["MIT"], "homepage_uri": "https://rubyonrails.org", "source_code_uri": "https://github.com/rails/rails/tree/v8.1.4.1", ...}` (2.1 KB). `/versions/<name>/latest.json` is just `{"version": "8.1.4.1"}`, `/versions/<name>.json` every version, `/gems/<name>/reverse_dependencies.json` the names of gems whose latest version depends on it, `/search.json?query=<words>&page=<n>` searches, 30 per page. JSON, `Access-Control-Allow-Origin: *`, no key.
- **Answers (block 1, 20 November 2026, 23:55 UTC):** **rails 8.1.4.1** (2026-11-04, MIT), 820,132,401 downloads, homepage https://rubyonrails.org, source https://github.com/rails/rails/tree/v8.1.4.1, 13,634 dependents (11,248 at runtime). **nokogiri 1.19.7** (MIT), 1,305,453,247 downloads; its most-downloaded dependents are **actionpack, loofah, mime-types-data (development only), rails-html-sanitizer, rails-dom-testing**. **rspec 3.13.2** is the latest stable although **4.0.0.beta1** exists; 59,581 gems depend on it, only 1,425 at runtime. "redcloth" is **RedCloth 4.3.4** (names are case-sensitive).
- **"Depends on it" is a name list, mostly development dependencies.** The JSON list is unranked names; `?only=runtime` keeps runtime dependencies (rspec: 1,425 of 59,581). For "most-downloaded dependents", read the HTML page `/gems/<name>/reverse_dependencies` (robots-allowed), which is sorted by downloads, 30 per page, with rounded counts ("860 Million") and no dependency type; block 1 marks the development-only ones by joining with the `only=runtime` list.
- **Latest version:** `gems/<name>.json` `version` skips pre-releases (rspec 3.13.2, not 4.0.0.beta1) and equalled the highest non-pre-release in `/versions/<name>.json` for all 12 gems checked, and `latest.json` for the 10 where both were read. `latest.json` answers HTTP 200 `{"version": "unknown"}` for a gem that does not exist; check the record (HTTP 404) instead.
- **Rate limit: "API and website: 10 requests per second"** (rate-limits guide), no rate-limit headers seen. The blocks wait 0.5-1 s after each call, serial, wait once on 429/5xx (`Retry-After`, else 30 s) and stop above 120 s. Send an identifying User-Agent (none was required: curl's default and no User-Agent both got HTTP 200).

## What works

### 1. Gem names as a person types them -> latest version, downloads, licences, homepage and source links, dependents; and a keyword search (browser)

`on_rubygems_tab()` opens the logged-out Acceptable Use page and `fetch()` runs same-origin. `get()` returns parsed JSON on HTTP 200, `None` on 404 (a `text/plain` "This rubygem could not be found."), waits once on 429/5xx and otherwise raises. The reverse-dependencies HTML page is parsed inside the page with `DOMParser`, so only its 30 table rows come back (sending the 75 KB page to Python broke the harness in the first run). 5 `fetch()` calls per gem (record, latest.json, 2 dependent lists, the dependents page), 2 more for a name in the wrong case, 2 in all for an unknown name, 1 for the search: 25 in all.

```python
import email.utils, json, time, urllib.parse
from datetime import datetime, timezone

GEMS = ["rails", "nokogiri", "rspec", "redcloth", "rails-jason"]  # names as a person types them
SEARCH = ("http client", 5)  # (words, how many), in the API's own order
TOP = 5  # most-downloaded gems whose latest version depends on it

SITE = "https://rubygems.org"
API = SITE + "/api/v1"
PAUSE = 0.5  # rate limits guide: "API and website: 10 requests per second"; stay well under it

def on_rubygems_tab():
    """fetch() from a logged-out RubyGems.org page (same origin; the API also sends Access-Control-Allow-Origin: *)."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(SITE + "/policies/acceptable-use")
    wait_for_load()
    txt = js("document.body ? document.body.innerText : ''") or ""
    if js("location.origin") != SITE or "Acceptable Use" not in txt:
        raise RuntimeError(f"RubyGems.org did not serve its Acceptable Use page (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__g = window.__g || {}; const id = String(Math.random()).slice(2); window.__g[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { let text = await r.text();
      if (%s && r.ok) text = JSON.stringify(rdeps(text));  // HTML page -> its table rows, not 75 KB of HTML
      window.__g[id] = {status: r.status, type: r.headers.get('content-type') || '', retry: r.headers.get('retry-after'), text}; })
    .catch(e => { window.__g[id] = {status: 0, type: '', retry: null, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__g[%s]; if (v) delete window.__g[%s]; return v; })()"""
# The HTML reverse-dependencies page is sorted by downloads; the JSON list is not. Its table rows, parsed in the page:
RDEPS_JS = """window.rdeps = html => [...new DOMParser().parseFromString(html, 'text/html')
  .querySelectorAll('[data-testid="reverse-dependencies"] tr')].map(tr => {
    const td = [...tr.querySelectorAll('td')].map(x => x.textContent.trim().split(/\\s*\\n\\s*/));
    return {name: tr.querySelector('a').getAttribute('href').split('/').pop(), version: td[1][0], downloads: td[td.length - 1][0]}; }); 1"""

def fetch(url, rows=False):
    rid = json.dumps(js(START_JS % (json.dumps(url), "true" if rows else "false")))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{url}: no answer after 60s")
        time.sleep(0.2)
    time.sleep(PAUSE)
    return r

def retry_wait(value, default):
    """Retry-After is seconds or an HTTP date -> seconds to wait; `default` when it is absent or unreadable."""
    v = (value or "").strip()
    if v.isdigit():
        return int(v)
    try:
        return max(0, int((email.utils.parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()) + 1)
    except (TypeError, ValueError):
        return default

def get(url, want="json", rows=False):
    """-> parsed JSON (or HTML text), or None on 404 (a text/plain "This rubygem could not be found."). Waits once
    on 429/5xx or a network error (Retry-After seconds or date, else 30 s; over 120 s stops). Raises on anything else."""
    for attempt in range(2):
        r = fetch(url, rows)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            wait = retry_wait(r["retry"], 30)
            if wait > 120:
                raise RuntimeError(f"{url}: server asks to wait {wait:.0f} s: stopping")
            time.sleep(wait)
            continue
        break
    if r["status"] == 404:
        return None
    if r["status"] != 200 or want not in r["type"]:
        raise RuntimeError(f"{url}: HTTP {r['status']} {r['type']} {' '.join(r['text'].split())[:200]!r}; stopping")
    return json.loads(r["text"]) if want == "json" or rows else r["text"]

def find(typed):
    """Gem names are case-sensitive in the API (redcloth 404, RedCloth 200). On 404, search and take a
    case-insensitive exact name match. -> (record or None, search suggestions)."""
    g = get(f"{API}/gems/{urllib.parse.quote(typed)}.json")
    if g is not None:
        return g, []
    hits = get(f"{API}/search.json?query={urllib.parse.quote(typed)}")
    same = [h for h in hits if h["name"].lower() == typed.lower()]
    if same:  # a search hit lacks version_created_at: read the gem's own record
        return get(f"{API}/gems/{urllib.parse.quote(same[0]['name'])}.json"), []
    return None, [h["name"] for h in hits[:3]]

on_rubygems_tab()
js(RDEPS_JS)
now = datetime.now(timezone.utc)
print(f"RubyGems.org API, checked {now:%Y-%m-%d %H:%M} UTC")
for typed in GEMS:
    g, alt = find(typed)
    if g is None:
        print(f"\n{typed}: no such gem (HTTP 404); search suggests: {', '.join(alt) or 'nothing'}")
        continue
    name = g["name"]
    latest = get(f"{API}/versions/{urllib.parse.quote(name)}/latest.json")["version"]  # 21 bytes; "unknown" if no gem
    rd_all = get(f"{API}/gems/{urllib.parse.quote(name)}/reverse_dependencies.json")  # names only, not ranked
    rd_run = set(get(f"{API}/gems/{urllib.parse.quote(name)}/reverse_dependencies.json?only=runtime"))
    top = get(f"{SITE}/gems/{urllib.parse.quote(name)}/reverse_dependencies", "html", rows=True)  # 30 rows per page
    src = g["source_code_uri"] or g["metadata"].get("source_code_uri")
    print(f"\n{typed} -> {name}: {' '.join((g['info'] or '').split())[:110]}")
    print(f"  latest {g['version']} (published {g['version_created_at'][:10]}, platform {g['platform']}); "
          f"latest.json says {latest}" + ("" if latest == g["version"] else "  <- DIFFERENT"))
    print(f"  downloads {g['downloads']:,} all versions, {g['version_downloads']:,} of {g['version']}")
    print(f"  licences {', '.join(g['licenses'] or []) or 'none declared'}")
    print(f"  homepage {g['homepage_uri'] or 'not set'}; source {src or 'not set'}; page {g['project_uri']}")
    print(f"  {len(rd_all):,} gems' latest versions depend on it ({len(rd_run):,} at runtime); most-downloaded:")
    for d in top[:TOP]:
        print(f"    {d['name']:<22} {d['version']:<12} {d['downloads']:>13} downloads"
              + ("" if d["name"] in rd_run else "  (development dependency only)"))
    run = [d["name"] for d in top if d["name"] in rd_run]
    print(f"  runtime dependents among the top {len(top)}: {', '.join(run[:TOP]) or 'none'}"
          + (f" (+{len(run) - TOP} more)" if len(run) > TOP else ""))

q, n = SEARCH
hits = get(f"{API}/search.json?query={urllib.parse.quote(q)}")  # 30 per page, &page=2 for more
print(f"\nsearch {q!r}: {len(hits)} on page 1, first {n} in the API's order")
for h in hits[:n]:
    print(f"  {h['name']:<44} {h['version']:<9} {h['downloads']:>12,} downloads  {', '.join(h['licenses'] or []) or '-'}")
print(f"\nSource: RubyGems.org (https://rubygems.org) public API and reverse-dependency pages, accessed {now:%d %B %Y %H:%M} UTC.")
```

Output (from the third run on 2026-11-20, 23:55 UTC; a fourth run at 00:00 UTC on 21 November printed the same numbers):

```text
RubyGems.org API, checked 2026-11-20 23:55 UTC

rails -> rails: Ruby on Rails is a full-stack web framework optimized for programmer happiness and sustainable productivity. I
  latest 8.1.4.1 (published 2026-11-04, platform ruby); latest.json says 8.1.4.1
  downloads 820,132,401 all versions, 3,608,027 of 8.1.4.1
  licences MIT
  homepage https://rubyonrails.org; source https://github.com/rails/rails/tree/v8.1.4.1; page https://rubygems.org/gems/rails
  13,634 gems' latest versions depend on it (11,248 at runtime); most-downloaded:
    haml                   7.5.2          211 Million downloads  (development dependency only)
    autoprefixer-rails     10.6.1.0       168 Million downloads  (development dependency only)
    paper_trail            17.0.0         154 Million downloads  (development dependency only)
    browser                6.2.0          152 Million downloads  (development dependency only)
    rack-mini-profiler     5.0.0         90.8 Million downloads  (development dependency only)
  runtime dependents among the top 30: invisible_captcha, rspec_profiling, redmine_crm, gettext_i18n_rails_js

nokogiri -> nokogiri: Nokogiri (鋸) makes it easy and painless to work with XML and HTML from Ruby. It provides a sensible, easy-to-u
  latest 1.19.7 (published 2026-11-02, platform ruby); latest.json says 1.19.7
  downloads 1,305,453,247 all versions, 206,839 of 1.19.7
  licences MIT
  homepage https://nokogiri.org; source https://github.com/sparklemotion/nokogiri; page https://rubygems.org/gems/nokogiri
  7,897 gems' latest versions depend on it (6,889 at runtime); most-downloaded:
    actionpack             8.1.4.1        860 Million downloads
    loofah                 2.25.3         779 Million downloads
    mime-types-data        3.2026.1103    762 Million downloads  (development dependency only)
    rails-html-sanitizer   1.7.2          739 Million downloads
    rails-dom-testing      2.3.0          711 Million downloads
  runtime dependents among the top 30: actionpack, loofah, rails-html-sanitizer, rails-dom-testing, actiontext (+13 more)

rspec -> rspec: BDD for Ruby
  latest 3.13.2 (published 2025-10-21, platform ruby); latest.json says 3.13.2
  downloads 1,044,576,105 all versions, 63,474,928 of 3.13.2
  licences MIT
  homepage https://rspec.info; source https://github.com/rspec/rspec/tree/rspec-v3.13.2/rspec; page https://rubygems.org/gems/rspec
  59,581 gems' latest versions depend on it (1,425 at runtime); most-downloaded:
    unicode-display_width  3.3.0         1.03 Billion downloads  (development dependency only)
    jwt                    3.3.0          847 Million downloads  (development dependency only)
    ast                    2.4.3          834 Million downloads  (development dependency only)
    mail                   2.9.1          796 Million downloads  (development dependency only)
    ruby-progressbar       1.13.0         781 Million downloads  (development dependency only)
  runtime dependents among the top 30: none

redcloth -> RedCloth: Textile parser for Ruby.
  latest 4.3.4 (published 2024-03-13, platform ruby); latest.json says 4.3.4
  downloads 51,122,045 all versions, 12,618,641 of 4.3.4
  licences MIT
  homepage http://redcloth.org; source https://github.com/jgarber/redcloth; page https://rubygems.org/gems/RedCloth
  350 gems' latest versions depend on it (255 at runtime); most-downloaded:
    gitlab-markup          2.2.1         50.9 Million downloads
    stringex               2.8.6         42.1 Million downloads  (development dependency only)
    apipie-rails           1.5.1         13.3 Million downloads  (development dependency only)
    gitlab-gollum-lib      4.2.7.9       10.9 Million downloads  (development dependency only)
    faye                   1.5.1         6.64 Million downloads  (development dependency only)
  runtime dependents among the top 30: gitlab-markup, six-updater-web, trusty-cms, newgem, locomotive_cms (+6 more)

rails-jason: no such gem (HTTP 404); search suggests: jason-rails, gistyle, tjstyle

search 'http client': 30 on page 1, first 5 in the API's order
  ruby_http_client                             3.6.0       62,943,782 downloads  MIT
  philiprehberger-http_client                  0.13.0       8,419,677 downloads  MIT
  http-client                                  0.6.1          298,857 downloads  MIT
  opentelemetry-instrumentation-http_client    0.29.1      38,592,202 downloads  Apache-2.0
  logstash-mixin-http_client                   7.5.0        8,984,162 downloads  Apache License (2.0)

Source: RubyGems.org (https://rubygems.org) public API and reverse-dependency pages, accessed 20 November 2026 23:55 UTC.
```

### 2. robots.txt, the policy quotes, the rate-limits guide, and what the API does with mistakes (browser)

7 page loads and 16 in-page `fetch()` calls in the same tab. The rate-limits guide is on guides.rubygems.org, so it is a page load; the tab returns to rubygems.org before the `fetch()` calls.

```python
import json, re, time

SITE = "https://rubygems.org"
API = SITE + "/api/v1"
GUIDES = "https://guides.rubygems.org"

START_JS = """(() => { window.__g = window.__g || {}; const id = String(Math.random()).slice(2); window.__g[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__g[id] = {status: r.status, type: r.headers.get('content-type') || '', text: await r.text()}; })
    .catch(e => { window.__g[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__g[%s]; if (v) delete window.__g[%s]; return v; })()"""

def raw(path):
    """One in-page GET of API + path (or a full URL). No retries: inspection only. 0.5 s after each call."""
    url = path if path.startswith("https://") else API + path
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{path}: no answer after 60s")
        time.sleep(0.2)
    time.sleep(0.5)
    return r

def page(url):
    goto_url(url)
    wait_for_load()
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    txt = js("document.body ? document.body.innerText : (document.documentElement.textContent || '')") or ""
    return st, " ".join(txt.replace("’", "'").split())

st, txt = page(SITE + "/robots.txt")
print(f"robots.txt HTTP {st}: {txt!r}")
st, txt = page(GUIDES + "/robots.txt")
print(f"guides robots.txt HTTP {st}: {txt!r}")

st, txt = page(SITE + "/policies/acceptable-use")
for needle in ("Last updated: Jun 25, 2025",
               "Uses the platform for any form of excessive automated bulk activity such as spamming, cryptocurrency mining, "
               "or any activity that places undue burden on our servers through automated means."):
    print(f"acceptable-use HTTP {st}: {'found' if needle in txt else 'MISSING'}: {needle!r}")
st, txt = page(SITE + "/policies/terms-of-service")
for needle in ("are operated by Ruby Central, Inc.",
               "Provider shall retain all right, title, and interest to Provider's trademarks, branding, logos, and related assets"):
    print(f"terms-of-service HTTP {st}: {'found' if needle in txt else 'MISSING'}: {needle!r}")
words = ("scrap", "crawl", "robot", "artificial intelligence", "machine learning", "non-commercial", "noncommercial")
print(f"terms-of-service words {words}: {[w for w in words if w in txt.lower()] or 'none'}")
st, txt = page(GUIDES + "/rubygems-org-rate-limits/")
for needle in ("API and website: 10 requests per second", "Dependency API: 15 requests per second",
               "you will see Retry-After header in the response",
               "may occasionally blackhole user IP addresses for extreme cases"):
    print(f"rate-limits HTTP {st}: {'found' if needle in txt else 'MISSING'}: {needle!r}")

# a gem page is rendered on the server: list any /api/ calls it makes from the browser
st, txt = page(SITE + "/gems/rails")
calls = js("performance.getEntriesByType('resource').map(e => e.name).filter(n => n.includes('/api/'))")
shown = re.search(r"(?i)total downloads ([\d,]+)", txt)
print(f"\n/gems/rails page HTTP {st}: its own /api/ calls: {calls}; page shows total downloads {shown[1] if shown else 'not found'}")
print()

def brief(r):
    out = f"HTTP {r['status']} {r['type'].split(';')[0] or '-'} {len(r['text']):,} chars"
    if "json" not in r["type"]:
        return out + f" {' '.join(r['text'].split())[:60]!r}"
    d = json.loads(r["text"])
    if isinstance(d, list):
        first = [x if isinstance(x, str) else x.get("name") or x.get("number") for x in d[:3]]
        return out + f" list of {len(d):,}, first {first}"
    return out + " " + json.dumps({k: d[k] for k in list(d)[:4]}, ensure_ascii=False)[:110]

for label, path in (
    ("gem record                         ", "/gems/rails.json"),
    ("gem record, capital R              ", "/gems/Rails.json"),
    ("gem record, unknown gem            ", "/gems/rails-jason.json"),
    ("latest.json, unknown gem           ", "/versions/rails-jason/latest.json"),
    ("latest.json, rspec (has 4.0 beta)  ", "/versions/rspec/latest.json"),
    ("all versions, rspec                ", "/versions/rspec.json"),
    ("all versions, nokogiri (platforms) ", "/versions/nokogiri.json"),
    ("v2 one version                     ", "https://rubygems.org/api/v2/rubygems/rspec/versions/4.0.0.beta1.json"),
    ("reverse deps, all                  ", "/gems/rack/reverse_dependencies.json"),
    ("reverse deps, only=runtime         ", "/gems/rack/reverse_dependencies.json?only=runtime"),
    ("reverse deps, only=development     ", "/gems/rack/reverse_dependencies.json?only=development"),
    ("reverse deps, only=bogus           ", "/gems/rack/reverse_dependencies.json?only=bogus"),
    ("search                             ", "/search.json?query=redcloth"),
    ("search, page 400                   ", "/search.json?query=redcloth&page=400"),
    ("search, no query                   ", "/search.json"),
    ("autocomplete                       ", "/search/autocomplete?query=nokog"),
):
    print(f"{label} {brief(raw(path))}")
page(SITE + "/policies/acceptable-use")  # back to the start page
```

Output (from the second run, 00:00 UTC on 21 November; 16:00 on 20 November US Pacific):

```text
robots.txt HTTP 200: '# See https://www.robotstxt.org/robotstxt.html for documentation on how to use the robots.txt file User-agent: * Disallow: /downloads/ Disallow: /gems?letter=* Disallow: /search?* Disallow: /names Disallow: /news'
guides robots.txt HTTP 200: 'User-agent: * Allow: / Sitemap: https://guides.rubygems.org/sitemap.xml'
acceptable-use HTTP 200: found: 'Last updated: Jun 25, 2025'
acceptable-use HTTP 200: found: 'Uses the platform for any form of excessive automated bulk activity such as spamming, cryptocurrency mining, or any activity that places undue burden on our servers through automated means.'
terms-of-service HTTP 200: found: 'are operated by Ruby Central, Inc.'
terms-of-service HTTP 200: found: "Provider shall retain all right, title, and interest to Provider's trademarks, branding, logos, and related assets"
terms-of-service words ('scrap', 'crawl', 'robot', 'artificial intelligence', 'machine learning', 'non-commercial', 'noncommercial'): none
rate-limits HTTP 200: found: 'API and website: 10 requests per second'
rate-limits HTTP 200: found: 'Dependency API: 15 requests per second'
rate-limits HTTP 200: found: 'you will see Retry-After header in the response'
rate-limits HTTP 200: found: 'may occasionally blackhole user IP addresses for extreme cases'

/gems/rails page HTTP 200: its own /api/ calls: []; page shows total downloads 820,148,569

gem record                          HTTP 200 application/json 2,148 chars {"name": "rails", "downloads": 820132401, "version": "8.1.4.1", "version_created_at": "2026-11-04T02:47:52.512
gem record, capital R               HTTP 404 text/plain 32 chars 'This rubygem could not be found.'
gem record, unknown gem             HTTP 404 text/plain 32 chars 'This rubygem could not be found.'
latest.json, unknown gem            HTTP 200 application/json 21 chars {"version": "unknown"}
latest.json, rspec (has 4.0 beta)   HTTP 200 application/json 20 chars {"version": "3.13.2"}
all versions, rspec                 HTTP 200 application/json 149,540 chars list of 173, first ['4.0.0.beta1', '3.13.2', '3.13.1']
all versions, nokogiri (platforms)  HTTP 200 application/json 1,470,228 chars list of 1,218, first ['1.19.7', '1.19.7', '1.19.7']
v2 one version                      HTTP 200 application/json 1,689 chars {"name": "rspec", "downloads": 1044576265, "version": "4.0.0.beta1", "version_created_at": "2026-02-18T15:56:4
reverse deps, all                   HTTP 200 application/json 58,001 chars list of 3,758, first ['rack-user-locale', 'rulers_adriennhem', 'jsonapi_rspec']
reverse deps, only=runtime          HTTP 200 application/json 47,186 chars list of 3,086, first ['delayed_job_metrics', 'bug_bunny', 'rack-chartbeat']
reverse deps, only=development      HTTP 200 application/json 11,040 chars list of 683, first ['jsonapi_rspec', 'em-http-promise', 'epona']
reverse deps, only=bogus            HTTP 200 application/json 58,001 chars list of 3,758, first ['rack-user-locale', 'rulers_adriennhem', 'jsonapi_rspec']
search                              HTTP 200 application/json 22,260 chars list of 30, first ['RedCloth', 'redcloth-rails', 'redcloth_on']
search, page 400                    HTTP 400 application/json 52 chars {"error": "Failed to parse search term: 'redcloth'."}
search, no query                    HTTP 400 application/json 44 chars {"error": "Request is missing param 'query'"}
autocomplete                        HTTP 200 application/json 621 chars list of 30, first ['nokogiri', 'nokogumbo', 'nokogiri-diff']
```

### 3. A Gemfile.lock with Python urllib: robots check for every agent, latest stable, newer pre-release, is the locked version still listed, licence change (ETag cache, no browser)

Two calls per gem: the record (latest version, licences, downloads) and the versions list (every version and platform, 1.47 MB for nokogiri, 129 KB with gzip). The versions list has no `yanked` field: a yanked version is simply missing, so a locked version that is not listed was yanked or never existed. Version order follows Gem::Version (any letter makes a pre-release; `4.0.0.beta1` < `4.0.0`). Run with an empty cache; the last pass shows the versions lists coming back as HTTP 304 (the gem records came back 200 every time: their gzip answers carry no ETag, see Gotchas).

```python
import collections, email.utils, gzip, hashlib, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request, urllib.robotparser
from datetime import datetime, timezone

LOCK = {"rails": "7.1.3", "nokogiri": "1.16.0", "rspec": "3.13.0", "puma": "6.4.2", "sidekiq": "7.2.1",
        "RedCloth": "4.3.2", "rest-client": "1.6.13", "devise": "4.9.3", "pg": "1.5.4"}  # name -> version from a Gemfile.lock

UA = "rubygems-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
SITE = "https://rubygems.org"
API = SITE + "/api/v1"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]
USED = ["/api/v1/gems/rails.json", "/api/v1/versions/rails.json", "/api/v1/versions/rails/latest.json",
        "/api/v1/gems/rails/reverse_dependencies.json", "/api/v1/search.json?query=http+client",
        "/gems/rails/reverse_dependencies", "/gems/rails/reverse_dependencies?page=2"]
CACHE_DIR = "~/.cache/rubygems-skill"
CACHE = os.path.expanduser(CACHE_DIR)
PAUSE = 0.5  # "API and website: 10 requests per second"; serial and well under it
calls = collections.Counter()

def retry_wait(value, default):
    """Retry-After is seconds or an HTTP date -> seconds to wait; `default` when it is absent or unreadable."""
    v = (value or "").strip()
    if v.isdigit():
        return int(v)
    try:
        return max(0, int((email.utils.parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()) + 1)
    except (TypeError, ValueError):
        return default

def http(url, headers=None):
    """GET with gzip -> (status, headers, body bytes). 304 and 404 are returned, not raised. Waits once on 429/5xx or
    a network error (Retry-After seconds or date, else 30 s; over 120 s exits); exits on any other error."""
    for attempt in range(2):
        time.sleep(PAUSE)
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip", **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read()
                calls[f"{r.status}"] += 1
                return r.status, r.headers, gzip.decompress(body) if r.headers.get("Content-Encoding") == "gzip" else body
        except urllib.error.HTTPError as e:
            calls[f"{e.code}"] += 1
            if e.code in (304, 404):
                return e.code, e.headers, b""
            if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                wait = retry_wait(e.headers.get("Retry-After"), 30)
                if wait > 120:
                    sys.exit(f"{url}: server asks to wait {wait} s: stopping")
                time.sleep(wait)
                continue
            sys.exit(f"HTTP {e.code} {url}: {' '.join(e.read().decode(errors='replace').split())[:200]}")
        except OSError as e:
            if attempt == 0:
                time.sleep(30)
                continue
            sys.exit(f"{url}: {e}")

def cached_json(url):
    """GET JSON with an ETag disk cache (the server sends Cache-Control max-age=60 and answers If-None-Match with 304).
    -> parsed JSON, or None on 404."""
    f = os.path.join(CACHE, hashlib.sha256(url.encode()).hexdigest() + ".json")
    try:
        old = json.load(open(f))
    except (OSError, ValueError):
        old = None
    st, h, body = http(url, {"If-None-Match": old["etag"]} if old and old.get("etag") else None)
    if st == 304:
        return old["data"]
    if st == 404:
        return None
    data = json.loads(body)
    os.makedirs(CACHE, exist_ok=True)
    json.dump({"etag": h.get("ETag"), "data": data}, open(f, "w"))
    return data

def gkey(v):
    """Gem::Version order: segments compare left to right, numbers as numbers, a letter segment (pre-release) below
    any number; missing segments count as 0 ('4.0.0.beta1' < '4.0.0' < '4.0.0.1')."""
    segs = [(1, int(s)) if s.isdigit() else (0, s) for s in re.findall(r"[0-9]+|[A-Za-z]+", v)]
    return segs + [(1, 0)] * (12 - len(segs))

# 1) robots.txt: every path this skill uses, for every agent. Python's urllib.robotparser ignores the '*' wildcard
# (it calls /search?query=rails allowed), so match the rules here as RFC 9309 says: longest pattern wins, Allow on a tie.
def robots_groups(text):
    groups, agents, in_rules = {}, [], False
    for line in text.splitlines():
        k, _, v = line.split("#")[0].partition(":")
        k, v = k.strip().lower(), v.strip()
        if k == "user-agent":
            agents, in_rules = (agents if not in_rules else []) + [v.lower()], False
            for a in agents:
                groups.setdefault(a, [])
        elif k in ("allow", "disallow") and agents:
            in_rules = True
            for a in agents:
                if v:
                    groups[a].append((k == "allow", v))
    return groups

def allowed(groups, agent, path):
    rules = groups.get(agent.lower(), groups.get("*", []))
    hits = [(len(p), ok) for ok, p in rules
            if re.match(re.escape(p.rstrip("$")).replace(r"\*", ".*") + ("$" if p.endswith("$") else ""), path)]
    return max(hits, default=(0, True))[1]

st, _, body = http(SITE + "/robots.txt")
groups = robots_groups(body.decode())
print(f"robots.txt HTTP {st}: groups {sorted(groups)}; '*' rules {[p for _, p in groups.get('*', [])]}")
for path in USED + ["/search?query=rails", "/gems?letter=R"]:
    ok = [a for a in AGENTS if allowed(groups, a, path)]
    print(f"  {path:<45} allowed for {len(ok)} of {len(AGENTS)} agents")
    if path in USED and len(ok) < len(AGENTS):
        sys.exit("robots.txt now disallows a path this skill uses: stop")
rp = urllib.robotparser.RobotFileParser()
rp.parse(body.decode().splitlines())
print(f"  (urllib.robotparser says /search?query=rails is {'allowed' if rp.can_fetch('*', SITE + '/search?query=rails') else 'disallowed'})")

# 2) Every locked gem: latest stable, newer pre-release, is the pinned version still listed, licence changes.
now = datetime.now(timezone.utc)
print(f"\nGemfile.lock check against RubyGems.org, {now:%Y-%m-%d %H:%M} UTC")
for name, pin in LOCK.items():
    g = cached_json(f"{API}/gems/{urllib.parse.quote(name)}.json")  # ~2 KB: latest version, licences, links
    if g is None:
        print(f"  {name:<12} {pin:<8} not on RubyGems.org (HTTP 404; names are case-sensitive)")
        continue
    vs = cached_json(f"{API}/versions/{urllib.parse.quote(name)}.json")  # every listed version x platform (gzip)
    nums = sorted({v["number"] for v in vs}, key=gkey, reverse=True)
    stable = [n for n in nums if not re.search(r"[A-Za-z]", n)]  # RubyGems: any letter makes a pre-release
    by = {v["number"]: v for v in vs if v["platform"] != "ruby"} | {v["number"]: v for v in vs if v["platform"] == "ruby"}
    mine = by.get(pin)
    newer = [n for n in stable if gkey(n) > gkey(pin)]
    pre = nums[0] if nums and nums[0] not in stable else None
    lic_pin = ", ".join(mine["licenses"] or []) if mine else "?"
    lic_new = ", ".join(g["licenses"] or []) or "none declared"
    print(f"  {name:<12} {pin:<8} -> latest {g['version']} ({g['version_created_at'][:10]})"
          + ("" if stable and stable[0] == g["version"] else f"  <- highest stable in the list is {stable[0] if stable else '-'}")
          + (f"; {len(newer)} newer stable releases" if newer else "; up to date")
          + (f"; newer pre-release {pre}" if pre and gkey(pre) > gkey(pin) else ""))
    print(f"  {'':<21} pinned {pin}: " + (f"published {mine['created_at'][:10]}, licence {lic_pin or 'none declared'}"
                                           if mine else "NOT LISTED (yanked, or never published)")
          + (f"; latest licence {lic_new}" + ("  <- CHANGED" if mine and lic_pin != lic_new else "") if mine else "")
          + f"; {len(nums)} versions, {len({v['platform'] for v in vs})} platform(s); {g['downloads']:,} downloads")

# 3) Run it again: the cached answers come back as HTTP 304 with no body.
first = dict(calls)
for name in LOCK:
    cached_json(f"{API}/gems/{urllib.parse.quote(name)}.json")
    cached_json(f"{API}/versions/{urllib.parse.quote(name)}.json")
print(f"\ncalls by HTTP status: first pass {first}; second pass {dict(calls - collections.Counter(first))} (cache {CACHE_DIR})")
print("Source: RubyGems.org (https://rubygems.org) public API.")
```

Output (from the second run on 2026-11-20, 23:59 UTC, empty cache):

```text
robots.txt HTTP 200: groups ['*']; '*' rules ['/downloads/', '/gems?letter=*', '/search?*', '/names', '/news']
  /api/v1/gems/rails.json                       allowed for 11 of 11 agents
  /api/v1/versions/rails.json                   allowed for 11 of 11 agents
  /api/v1/versions/rails/latest.json            allowed for 11 of 11 agents
  /api/v1/gems/rails/reverse_dependencies.json  allowed for 11 of 11 agents
  /api/v1/search.json?query=http+client         allowed for 11 of 11 agents
  /gems/rails/reverse_dependencies              allowed for 11 of 11 agents
  /gems/rails/reverse_dependencies?page=2       allowed for 11 of 11 agents
  /search?query=rails                           allowed for 0 of 11 agents
  /gems?letter=R                                allowed for 0 of 11 agents
  (urllib.robotparser says /search?query=rails is allowed)

Gemfile.lock check against RubyGems.org, 2026-11-20 23:59 UTC
  rails        7.1.3    -> latest 8.1.4.1 (2026-11-04); 41 newer stable releases
                        pinned 7.1.3: published 2024-01-16, licence MIT; latest licence MIT; 523 versions, 1 platform(s); 820,149,452 downloads
  nokogiri     1.16.0   -> latest 1.19.7 (2026-11-02); 30 newer stable releases
                        pinned 1.16.0: published 2023-12-28, licence MIT; latest licence MIT; 198 versions, 20 platform(s); 1,305,432,478 downloads
  rspec        3.13.0   -> latest 3.13.2 (2025-10-21); 2 newer stable releases; newer pre-release 4.0.0.beta1
                        pinned 3.13.0: published 2024-02-04, licence MIT; latest licence MIT; 173 versions, 1 platform(s); 1,044,577,097 downloads
  puma         6.4.2    -> latest 8.1.2 (2026-11-17); 22 newer stable releases
                        pinned 6.4.2: published 2024-01-08, licence BSD-3-Clause; latest licence BSD-3-Clause; 191 versions, 2 platform(s); 633,317,218 downloads
  sidekiq      7.2.1    -> latest 8.1.7 (2026-08-17); 33 newer stable releases
                        pinned 7.2.1: published 2024-01-19, licence LGPL-3.0; latest licence LGPL-3.0; 242 versions, 1 platform(s); 349,564,025 downloads
  RedCloth     4.3.2    -> latest 4.3.4 (2024-03-13); 2 newer stable releases
                        pinned 4.3.2: published 2016-05-24, licence MIT; latest licence MIT; 30 versions, 5 platform(s); 51,122,053 downloads
  rest-client  1.6.13   -> latest 2.1.0 (2019-08-21); 10 newer stable releases
                        pinned 1.6.13: NOT LISTED (yanked, or never published); 62 versions, 4 platform(s); 494,935,736 downloads
  devise       4.9.3    -> latest 5.0.4 (2026-05-08); 6 newer stable releases
                        pinned 4.9.3: published 2023-10-11, licence MIT; latest licence MIT; 173 versions, 1 platform(s); 306,436,409 downloads
  pg           1.5.4    -> latest 1.7.0 (2026-10-02); 10 newer stable releases
                        pinned 1.5.4: published 2023-09-01, licence BSD-2-Clause; latest licence BSD-2-Clause; 106 versions, 13 platform(s); 491,487,404 downloads

calls by HTTP status: first pass {'200': 19}; second pass {'200': 9, '304': 9} (cache ~/.cache/rubygems-skill)
Source: RubyGems.org (https://rubygems.org) public API.
```

### 4. curl, headers and mistakes

```bash
B=https://rubygems.org/api/v1
UA='rubygems-skill-example/1.0 (+https://github.com/browser-use/browser-harness)'
# one gem: latest version, downloads, licences, homepage and source links (2 KB)
curl -sS --fail -A "$UA" "$B/gems/sidekiq.json" \
  | python3 -c 'import sys, json
g = json.load(sys.stdin)
print(g["name"], g["version"], g["version_created_at"][:10], "| downloads", g["downloads"], "| licences", g["licenses"])
print("homepage", g["homepage_uri"], "| source", g["source_code_uri"], "| changelog", g["changelog_uri"])'
sleep 1
# just the latest version number (21 bytes)
curl -sS --fail -A "$UA" "$B/versions/sidekiq/latest.json"; echo
sleep 1
# which gems depend on it: names only, not ranked; only=runtime drops development dependencies
for only in "" "?only=runtime"; do
  curl -sS --fail -A "$UA" "$B/gems/sidekiq/reverse_dependencies.json$only" \
    | python3 -c 'import sys, json; d = json.load(sys.stdin); print("dependents'"$only"'", len(d), "| first 3", d[:3])'
  sleep 1
done
# search: 30 per page in the API's own order; page=2 for the next 30
curl -sS --fail -A "$UA" "$B/search.json?query=background+jobs&page=1" \
  | python3 -c 'import sys, json
d = json.load(sys.stdin); print("search page 1:", len(d), "hits")
for g in d[:4]: print(" ", g["name"], g["version"], g["downloads"], g["licenses"], g["source_code_uri"] or g["homepage_uri"])'
sleep 1
# every version (all platforms) as gzip: nokogiri is 1.47 MB plain, 0.13 MB gzip; the ETag gives a 304 on repeat
H=$(mktemp)
curl -sS -A "$UA" -H 'Accept-Encoding: gzip' -D "$H" -o /dev/null -w 'versions/nokogiri.json gzip -> HTTP %{http_code}, %{size_download} bytes\n' "$B/versions/nokogiri.json"
E=$(tr -d '\r' < "$H" | sed -n 's/^etag: //Ip')
sleep 1
curl -sS -A "$UA" -H 'Accept-Encoding: gzip' -H "If-None-Match: $E" -o /dev/null -w 'same with If-None-Match -> HTTP %{http_code}, %{size_download} bytes\n' "$B/versions/nokogiri.json"
sleep 1
# API headers: JSON, CORS open for GET, cached 60 s at the CDN, no rate-limit headers
curl -sS -A "$UA" -D - -o /dev/null "$B/gems/sidekiq.json" | tr -d '\r' \
  | grep -iE '^(HTTP/|(content-type|access-control-allow-[a-z]+|cache-control|age|x-cache|etag|retry-after|x-ratelimit-[a-z]+|server|via):)'
sleep 1
# compact index ("used for Bundler dependency resolution", compact index guide): one line per version, oldest first
curl -sS --fail -A "$UA" https://rubygems.org/info/sidekiq | tail -n 1 | cut -c1-110
sleep 1
# mistakes: names are case-sensitive, latest.json says "unknown" with HTTP 200, search pages stop at 333
T=$(mktemp)
curl -sS -A "$UA" -o "$T" -w 'gems/Sidekiq.json -> HTTP %{http_code} %{content_type} ' "$B/gems/Sidekiq.json"; cat "$T"; echo; sleep 1
curl -sS -A "$UA" -o "$T" -w 'versions/sidekik/latest.json -> HTTP %{http_code} ' "$B/versions/sidekik/latest.json"; cat "$T"; echo; sleep 1
curl -sS -A "$UA" -o "$T" -w 'search page=333 -> HTTP %{http_code} ' "$B/search.json?query=background+jobs&page=333"; cat "$T"; echo; sleep 1
curl -sS -A "$UA" -o "$T" -w 'search page=334 -> HTTP %{http_code} ' "$B/search.json?query=background+jobs&page=334"; cat "$T"; echo; sleep 1
curl -sS -A "$UA" -o "$T" -w 'search, no query -> HTTP %{http_code} ' "$B/search.json"; cat "$T"; echo; sleep 1
curl -sS -o "$T" -w "curl's default User-Agent -> HTTP %{http_code}\n" "$B/versions/sidekiq/latest.json"
rm -f "$T" "$H"
```

Output (from the first run on 2026-11-20, 23:59 UTC):

```text
sidekiq 8.1.7 2026-08-17 | downloads 349557845 | licences ['LGPL-3.0']
homepage https://sidekiq.org | source https://github.com/sidekiq/sidekiq | changelog https://github.com/sidekiq/sidekiq/blob/main/Changes.md
{"version":"8.1.7"}
dependents 716 | first 3 ['sidekiq-reliable-fetch', 'inst_data_shipper', 'sidekiq-middleware']
dependents?only=runtime 592 | first 3 ['sidekiq-middleware', 'catena', 'karafka-sidekiq-backend']
search page 1: 30 hits
  background_jobs 0.2.1 12128 ['MIT'] 
  thecore_background_jobs 3.0.11 47853 [] https://github.com/gabrieletassoni/thecore_background_jobs
  ctt-background-jobs 0.8.1 8548 ['MIT'] 
  job-iteration 1.18.1 11729410 ['MIT'] https://github.com/shopify/job-iteration
versions/nokogiri.json gzip -> HTTP 200, 128929 bytes
same with If-None-Match -> HTTP 304, 0 bytes
HTTP/2 200 
content-type: application/json; charset=utf-8
access-control-allow-origin: *
access-control-allow-methods: GET
cache-control: max-age=60, public
via: 1.1 varnish
age: 3403
x-cache: HIT
etag: "8b6e59d7f86cd9f9024ea94ae1e4333b"
server: RubyGems.org
8.1.7 connection_pool:>= 3.0.0,json:>= 2.16.0,logger:>= 1.7.0,rack:>= 3.2.0,redis-client:>= 0.29.0|checksum:91
gems/Sidekiq.json -> HTTP 404 text/plain; charset=utf-8 This rubygem could not be found.
versions/sidekik/latest.json -> HTTP 200 {"version":"unknown"}
search page=333 -> HTTP 200 []
search page=334 -> HTTP 400 {"error":"Failed to parse search term: 'background jobs'."}
search, no query -> HTTP 400 {"error":"Request is missing param 'query'"}
curl's default User-Agent -> HTTP 200
```

## Fields

| Field | Value | Notes |
|---|---|---|
| `name` | `RedCloth` | exact, case-sensitive name; `gems/redcloth.json` is HTTP 404 |
| `version`, `version_created_at`, `platform` | `8.1.4.1`, ISO time, `ruby` | the latest non-pre-release version; for rspec `3.13.2` while `4.0.0.beta1` exists |
| `downloads` | integer | all versions, all time; served through a CDN cache (see Gotchas) |
| `version_downloads` | integer | downloads of `version` only |
| `licenses` | list of strings | of the latest version, as the author wrote them: `MIT`, `LGPL-3.0`, but also `Apache License (2.0)`; can be `[]` |
| `homepage_uri`, `source_code_uri`, `documentation_uri`, `changelog_uri`, `bug_tracker_uri`, `funding_uri` | URL, null or `""` | from the gemspec (background_jobs' `homepage_uri` is `""`); `source_code_uri` can point at a tag (`.../tree/v8.1.4.1`); also under `metadata` |
| `project_uri`, `gem_uri` | `https://rubygems.org/gems/rails`, `.../rails-8.1.4.1.gem` | the gem page and the package file |
| `info` | text | the gemspec description |
| `dependencies.runtime[]`, `dependencies.development[]` | `{"name", "requirements"}` | what this gem needs, for the latest version |
| `/versions/<name>.json`: `number`, `platform`, `prerelease`, `created_at`, `downloads_count`, `licenses`, `sha` | | one entry per version and platform (nokogiri: 1,218 entries, 198 versions, 20 platforms); yanked versions are absent |
| `/versions/<name>/latest.json` | `{"version": "8.1.4.1"}` | `"unknown"` (HTTP 200) for an unknown gem |
| `/gems/<name>/reverse_dependencies.json` | list of names | gems whose latest version depends on it; `only=runtime` / `only=development`; any other `only` value is ignored |
| HTML `/gems/<name>/reverse_dependencies` | name, version, date, downloads | sorted by downloads, 30 rows per page, `?page=2`; counts rounded ("90.8 Million") |
| `/search.json` | list of gem records | 30 per page in the API's own order; no total count |
| API headers | `Content-Type: application/json; charset=utf-8`, `Access-Control-Allow-Origin: *`, `Access-Control-Allow-Methods: GET`, `Cache-Control: max-age=60, public`, `ETag`, `Age`, `X-Cache`, `Via: 1.1 varnish`, `Server: RubyGems.org` | no `Retry-After` or rate-limit headers seen |

## Gotchas

- **Names are case-sensitive.** `gems/RedCloth.json` is HTTP 200, `gems/redcloth.json` and `gems/Rails.json` HTTP 404 with a `text/plain` body, not JSON. Block 1 falls back to `search.json` and takes a case-insensitive exact match (RedCloth comes first for "redcloth").
- **`latest.json` never says 404.** An unknown gem gives HTTP 200 `{"version":"unknown"}`. Read the record first.
- **Pre-releases are in the versions list, first.** rspec's list starts with `4.0.0.beta1` (published 2026-02-18) before `3.13.2`. Skip entries with `prerelease: true` (any letter in the number). The record's `version` already skips them.
- **One entry per platform.** nokogiri's versions list has 11 entries for 1.19.7 (`ruby`, `x86_64-linux-gnu`, `arm64-darwin`, `java`, ...). Count unique `number`s, and prefer the `ruby` platform entry for dates and licences.
- **Yanked versions disappear.** rest-client's list jumps from 1.6.9 to 1.6.14; 1.6.13 is not in `/versions/rest-client.json` or `/info/rest-client`, and `/api/v2/rubygems/rest-client/versions/1.6.13.json` is HTTP 404. The versions list has no `yanked` flag; the gem record's `yanked` (`false`) is about its latest version only.
- **Dependents are mostly development dependencies.** rspec: 59,581 gems in the full list, 1,425 with `only=runtime`. rack: 3,758 in all, 3,086 runtime, 683 development (3,086 + 683 = 3,769, so 11 gems are in both lists). The 5 most-downloaded rails dependents (haml, autoprefixer-rails, paper_trail, browser, rack-mini-profiler) all depend on it for development only. The JSON list is not ranked; the HTML page is ranked but has no dependency type.
- **Search order is not downloads.** "http client" puts ruby_http_client (62.9 M downloads) first, http-client (0.3 M) third and opentelemetry-instrumentation-http_client (38.6 M) fourth. There is no sort parameter or total count; page on with `page=` until `[]`. Pages above 333 are HTTP 400 "Failed to parse search term" even when page 333 is `[]` (334 x 30 = 10,020, so likely a 10,000-hit window); a missing `query` is HTTP 400.
- **Download counts depend on which cache answers.** `Cache-Control: max-age=60`, but a sidekiq record came back with `Age: 3403` and `X-Cache: HIT`. rails' total read 820,146,985 (curl, 23:52 UTC), 820,132,401 (browser, 23:55 and 00:00), 820,149,452 (urllib, 23:59) and 820,148,569 (the gem page, 00:00). Date every number and do not subtract two reads.
- **`urllib.robotparser` ignores the `*` wildcard.** It says `/search?query=rails` is allowed; RFC 9309 matching (block 3) says disallowed for every agent. Use a wildcard-aware check.
- **The gem record loses its ETag when gzipped.** `/versions/<name>.json` sends an ETag with or without gzip and answers `If-None-Match` with HTTP 304. `/gems/<name>.json` sends an ETag only uncompressed (curl without `Accept-Encoding`: HTTP 304 on repeat); its gzip answer has none, so block 3's cache (which asks for gzip) gets HTTP 200 with the body for the records every time.
- **Licences are free text.** `Apache License (2.0)` (logstash-mixin-http_client) next to SPDX ids; thecore_background_jobs has `[]`. Some gems set neither `homepage_uri` nor `source_code_uri` (background_jobs).
- **Tab marker.** The harness may set the tab title to a horse emoji; the blocks check `location.origin` and the page text, not the title.

## What does not work

- **The HTML search page** `/search?query=`: robots.txt disallows `/search?*` for every agent. Use `/api/v1/search.json`.
- **Ranking dependents by exact downloads from the API**: the JSON list has names only; ranking 13,634 rails dependents would take 13,634 more calls. The HTML page gives the order with rounded counts.
- **Seeing yanked versions or why**: the API drops them.
- **Not tested:** the 429 response (never provoked), the YAML variants, `/api/v1/timeframe_versions.json`, attestations, `/api/v2/rubygems/<name>/versions/<v>/contents.json`, owners, and the compact index beyond one `/info/<name>` file (block 4: one line per version, oldest first, what Bundler reads).
