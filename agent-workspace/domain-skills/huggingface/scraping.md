# Hugging Face - Rank Models and Datasets by Downloads or Likes, Read Card Metadata (public Hub API)

Field-tested against huggingface.co on 2026-11-03 using a Browser Use cloud browser, logged out. Every browser call is a same-origin `fetch()` from a huggingface.co tab to the public Hub API (`/api/models`, `/api/datasets`). No CAPTCHA, login wall, 403 or 429 across about 40 browser API calls and 10 page loads.

robots.txt (fetched 2026-11-03): `User-agent: *` / `Allow: /` with only a Sitemap line, so the listing pages, repo pages, `/raw/` files and `/api/` are all allowed.

## Quick summary

- **No scraping.** Two public JSON endpoints cover the task. No key, no cookies:
  - `GET /api/models?search=&pipeline_tag=&author=&filter=&sort=downloads&limit=` and the same on `/api/datasets` - ranked lists, always descending.
  - `GET /api/models/<org>/<name>` and `/api/datasets/<org>/<name>` - one repo: `cardData` (the README's YAML header, parsed), downloads, likes, gated, license, task, library, parameter count, file list.
- **Sort keys:** `downloads` (last 30 days), `likes`, `trendingScore`, `lastModified`, `createdAt`. All-time downloads are a field (`expand[]=downloadsAllTime`), not a sort key.
- **`expand[]=<field>` trims a list to exactly those fields** (plus `id`). Block 1 asks for downloads, all-time downloads, likes, trending score, task, library and last modified.
- **Facet filters go in `filter=`, repeated = AND:** `filter=gguf&filter=license:mit`. `library=`, `license=`, `language=`, `task_categories=` as their own params are silently ignored and return the unfiltered ranking.
- **Pages:** `limit` caps at 1000; the next page is in the `Link: <...>; rel="next"` header (cursor). Block 1 follows it.
- **Budget:** anonymous callers get 500 `/api` calls per 5 min per IP (`RateLimit-Policy: "fixed window";"api";q=500;w=300`; https://huggingface.co/docs/hub/rate-limits). API responses carry `RateLimit: "api";r=<left>;t=<seconds to reset>`. The blocks pause 0.3 s per call and wait out a 429 by `t`.

## What works

Blocks 1 and 2 share the same helpers: `on_hf_tab()` opens `https://huggingface.co/robots.txt` once (tiny, allowed) and later blocks reuse the tab; it raises if anything other than robots.txt comes back. `get(url)` runs `fetch()` with `credentials: 'omit'`, returns parsed JSON, `None` on 401/404, waits out 429 using the `RateLimit` header and otherwise raises, so a failed call never looks like an empty result.

### 1. Rank models and datasets by downloads or likes (browser)

```python
import json, os, re, tempfile, time, urllib.parse

QUERIES = [   # (kind, filters, sort) - sort: downloads | likes | trendingScore | lastModified | createdAt
    ("models",   {"pipeline_tag": "text-generation"}, "downloads"),
    ("models",   {"search": "qwen"}, "likes"),
    ("datasets", {"filter": "task_categories:text-generation"}, "downloads"),
    ("datasets", {"search": "math"}, "likes"),
]
TOP = 8          # rows per ranking; >1000 follows the Link: rel="next" cursor
PAUSE = 0.3      # seconds between calls; anonymous budget is 500 /api calls per 5 min per IP

FIELDS = {   # expand[] = return exactly these fields (plus id), not the default set
    "models":   ["downloads", "downloadsAllTime", "likes", "trendingScore", "pipeline_tag", "library_name", "lastModified"],
    "datasets": ["downloads", "downloadsAllTime", "likes", "trendingScore", "lastModified"],
}

def on_hf_tab():
    """fetch() runs same-origin from a logged-out huggingface.co tab. Reuse the tab if already there."""
    try:
        if js("location.origin") == "https://huggingface.co":
            return
    except Exception:
        pass
    new_tab("https://huggingface.co/robots.txt")   # tiny page; robots.txt: User-agent: * / Allow: /
    wait_for_load()
    if "User-agent" not in (js("document.body.innerText") or ""):
        raise RuntimeError(f"unexpected page at huggingface.co/robots.txt ({js('document.title')!r}): stop, do not retry around it")

FETCH_JS = """(async () => {
  try { const r = await fetch(%s, {credentials: 'omit'});
        return {status: r.status, text: await r.text(), link: r.headers.get('link'), rl: r.headers.get('ratelimit')}; }
  catch (e) { return {status: 0, text: String(e)}; }
})()"""

def get(url, tries=3):
    """GET a huggingface.co/api URL. Returns (json, next_url). None on 401/404 (anonymous callers get 401 for
    missing, private AND gated-file paths). Waits out 429 using the RateLimit header, raises on anything else."""
    for attempt in range(tries):
        r = js(FETCH_JS % json.dumps(url))
        if r["status"] == 200:
            time.sleep(PAUSE)
            m = re.search(r'<([^>]+)>;\s*rel="next"', r.get("link") or "")
            return json.loads(r["text"]), (m.group(1) if m else None)
        if r["status"] in (401, 404):
            time.sleep(PAUSE)
            return None, None
        if r["status"] not in (0, 429, 500, 502, 503, 504) or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {r['status']} {r['text'][:200]}; stopping")
        reset = re.search(r";t=(\d+)", r.get("rl") or "")
        time.sleep(int(reset.group(1)) + 1 if r["status"] == 429 and reset else 5 * 2 ** attempt)

def ranking(kind, filters, sort, top):
    """Top `top` repos of kind (models|datasets) matching filters, sorted descending by `sort`."""
    params = dict(filters, sort=sort, limit=min(top, 1000))
    url = f"https://huggingface.co/api/{kind}?" + urllib.parse.urlencode(params) + "".join(f"&expand[]={f}" for f in FIELDS[kind])
    rows = []
    while url and len(rows) < top:
        page, url = get(url)
        rows += page or []
    return [{"rank": i + 1, "id": r["id"], "kind": kind,
             "downloads_30d": r.get("downloads"), "downloads_all_time": r.get("downloadsAllTime"),
             "likes": r.get("likes"), "trending": r.get("trendingScore"),
             "task": r.get("pipeline_tag"), "library": r.get("library_name"),
             "updated": (r.get("lastModified") or "")[:10],
             "url": f"https://huggingface.co/{'datasets/' if kind == 'datasets' else ''}{r['id']}"} for i, r in enumerate(rows[:top])]

on_hf_tab()
out = {}
for kind, filters, sort in QUERIES:
    rows = ranking(kind, filters, sort, TOP)
    key = f"{kind} {filters} by {sort}"
    out[key] = rows
    print(f"\n{key}: {len(rows)} rows")
    print(f"{'#':>2}  {'id':<46}{'dl 30d':>12}{'dl all-time':>14}{'likes':>8}  {'task / updated'}")
    for r in rows:
        print(f"{r['rank']:>2}  {r['id'][:45]:<46}{r['downloads_30d'] or 0:>12,}{r['downloads_all_time'] or 0:>14,}{r['likes'] or 0:>8,}  {r['task'] or '-'} / {r['updated']}")
path = os.path.join(tempfile.gettempdir(), "hf_rankings.json")
json.dump(out, open(path, "w"), indent=1)
print("\nsaved", path)
```

Output observed on 2026-11-03:

```text
models {'pipeline_tag': 'text-generation'} by downloads: 8 rows
 #  id                                                  dl 30d   dl all-time   likes  task / updated
 1  openai-community/gpt2                           29,775,719   963,403,365   3,913  text-generation / 2024-02-19
 2  Qwen/Qwen3-0.6B                                 22,876,234   258,700,026   1,871  text-generation / 2025-07-26
 3  Qwen/Qwen3-14B                                  12,993,294    43,562,530     533  text-generation / 2025-07-26
 4  Qwen/Qwen3-4B                                    8,421,019    93,889,650     783  text-generation / 2025-07-26
 5  Qwen/Qwen3-8B                                    7,537,607   136,516,770   2,165  text-generation / 2025-07-26
 6  deepseek-ai/DeepSeek-V3.2                        6,909,222    33,795,141   1,592  text-generation / 2025-12-01
 7  Qwen/Qwen2.5-7B-Instruct                         6,087,870   192,916,677   2,486  text-generation / 2025-01-12
 8  openai/gpt-oss-20b                               5,957,662   107,580,067   5,266  text-generation / 2025-08-26

models {'search': 'qwen'} by likes: 8 rows
 #  id                                                  dl 30d   dl all-time   likes  task / updated
 1  Qwen/Qwen3.8-27B                                 8,014,877    20,960,828  19,084  image-text-to-text / 2026-08-14
 2  Qwen/Qwen3.8-Flash-Next                          3,867,800     5,818,032   6,750  image-text-to-text / 2026-08-27
 3  abenzerps/Qwen-Image-2.1-Turbo-Quantized         2,508,590     4,128,332   5,624  text-to-image / 2026-11-03
 4  unsloth/Qwen3.8-27B-GGUF                         5,993,784    22,846,350   5,502  - / 2026-08-20
 5  HauhauCS/Qwen3.6-35B-A3B-Uncensored-HauhauCS-    1,145,489    12,969,119   4,085  image-text-to-text / 2026-04-17
 6  Qwen/Qwen-Image-2.1                                230,375       324,051   3,547  text-to-image / 2026-09-30
 7  Qwen/Qwen3.6-35B-A3B                             4,530,442    34,630,996   3,074  image-text-to-text / 2026-04-24
 8  Qwen/QwQ-32B                                        34,836     3,615,501   2,970  text-generation / 2025-03-11

datasets {'filter': 'task_categories:text-generation'} by downloads: 8 rows
 #  id                                                  dl 30d   dl all-time   likes  task / updated
 1  m-a-p/FineFineWeb                                2,207,004    26,829,543     240  - / 2024-12-19
 2  Salesforce/wikitext                              2,089,484    41,058,622     856  - / 2024-01-04
 3  epfml/FineWeb-HQ                                 1,467,803     3,778,992      32  - / 2025-09-30
 4  openai/gsm8k                                       993,185    17,508,033   2,026  - / 2026-03-23
 5  mlfoundations/MINT-1T-HTML                         918,195     4,978,531     124  - / 2024-09-21
 6  Tuxifan/UbuntuIRC                                  804,196     1,933,810       1  - / 2023-06-04
 7  allenai/c4                                         729,254    19,178,537     697  - / 2024-01-09
 8  3dcodeverse/3dcodeverse-2m                         692,413       710,189      47  - / 2026-10-31

datasets {'search': 'math'} by likes: 8 rows
 #  id                                                  dl 30d   dl all-time   likes  task / updated
 1  open-r1/OpenR1-Math-220k                            93,402       844,990     819  - / 2025-02-18
 2  microsoft/orca-math-word-problems-200k              39,917       222,557     518  - / 2024-03-04
 3  meta-math/MetaMathQA                                67,109       781,840     491  - / 2023-12-21
 4  open-web-math/open-web-math                         32,351       437,133     373  - / 2023-10-17
 5  openbmb/UltraData-Math                              25,074       321,029     363  - / 2026-04-15
 6  HuggingFaceH4/MATH-500                             189,963     2,424,510     357  - / 2025-12-15
 7  TIGER-Lab/MathInstruct                              11,766       239,077     320  - / 2024-05-15
 8  SynthLabsAI/Big-Math-RL-Verified                     4,414       162,605     246  - / 2025-03-25

saved <tempdir>/hf_rankings.json
```

### 2. Model and dataset card metadata (browser)

Full repo info plus the two fields it leaves out by default (`downloadsAllTime`, `trendingScore`), and the start of the README body. For datasets it adds row counts per config and split from `cardData.dataset_info`.

```python
import json, os, re, tempfile, time, urllib.parse

REPOS = [   # (kind, repo id)
    ("models",   "Qwen/Qwen3-0.6B"),
    ("models",   "meta-llama/Llama-3.1-8B-Instruct"),   # gated: metadata public, files (README) are not
    ("datasets", "openai/gsm8k"),
    ("models",   "no-such-user/no-such-model"),
]
README_CHARS = 400   # how much of the README body (after the YAML header) to keep; 0 = skip the README call
PAUSE = 0.3

def on_hf_tab():
    """fetch() runs same-origin from a logged-out huggingface.co tab. Reuse the tab if already there."""
    try:
        if js("location.origin") == "https://huggingface.co":
            return
    except Exception:
        pass
    new_tab("https://huggingface.co/robots.txt")   # tiny page; robots.txt: User-agent: * / Allow: /
    wait_for_load()
    if "User-agent" not in (js("document.body.innerText") or ""):
        raise RuntimeError(f"unexpected page at huggingface.co/robots.txt ({js('document.title')!r}): stop, do not retry around it")

FETCH_JS = """(async () => {
  try { const r = await fetch(%s, {credentials: 'omit'});
        return {status: r.status, text: await r.text(), rl: r.headers.get('ratelimit')}; }
  catch (e) { return {status: 0, text: String(e)}; }
})()"""

def get(url, as_json=True, tries=3):
    """GET a huggingface.co URL. None on 401/404 (anonymous callers get 401 for missing, private and
    gated-file paths). Waits out 429 using the RateLimit header, raises on anything else."""
    for attempt in range(tries):
        r = js(FETCH_JS % json.dumps(url))
        if r["status"] in (200, 401, 404):
            time.sleep(PAUSE)
            return (json.loads(r["text"]) if as_json else r["text"]) if r["status"] == 200 else None
        if r["status"] not in (0, 429, 500, 502, 503, 504) or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {r['status']} {r['text'][:200]}; stopping")
        reset = re.search(r";t=(\d+)", r.get("rl") or "")
        time.sleep(int(reset.group(1)) + 1 if r["status"] == 429 and reset else 5 * 2 ** attempt)

def card(kind, repo_id):
    """Model or dataset card metadata (the README's YAML header, parsed by the Hub) plus counts and file list."""
    base = f"https://huggingface.co/api/{kind}/{repo_id}"
    info = get(base)
    if info is None:
        return None
    extra = get(base + "?expand[]=downloadsAllTime&expand[]=trendingScore") or {}   # not in the default response
    cd = info.get("cardData") or {}
    out = {
        "id": info["id"], "kind": kind, "author": info.get("author"), "sha": info.get("sha"),
        "created": info.get("createdAt"), "last_modified": info.get("lastModified"),
        "downloads_30d": info.get("downloads"), "downloads_all_time": extra.get("downloadsAllTime"),
        "likes": info.get("likes"), "trending": extra.get("trendingScore"),
        "gated": info.get("gated"), "private": info.get("private"),
        "license": cd.get("license"), "language": cd.get("language"),
        "task": info.get("pipeline_tag") or cd.get("task_categories"),
        "library": info.get("library_name"), "base_model": cd.get("base_model"),
        "params": (info.get("safetensors") or {}).get("total"),
        "arxiv": [t[6:] for t in info.get("tags", []) if t.startswith("arxiv:")],
        "files": [s["rfilename"] for s in info.get("siblings") or []],
        "card_keys": sorted(cd),
        "card_data": cd,
        "url": f"https://huggingface.co/{'datasets/' if kind == 'datasets' else ''}{repo_id}",
    }
    if kind == "datasets":
        di = cd.get("dataset_info") or []
        di = [di] if isinstance(di, dict) else di   # one config: a dict; several: a list with config_name
        out["rows_by_split"] = {f"{c.get('config_name', 'default')}/{s['name']}": s.get("num_examples")
                                for c in di for s in c.get("splits") or []}
        out["size_category"] = cd.get("size_categories")
    if README_CHARS and "README.md" in out["files"]:
        prefix = "datasets/" if kind == "datasets" else ""
        text = get(f"https://huggingface.co/{prefix}{repo_id}/raw/main/README.md", as_json=False)
        if text is None:
            out["readme"] = None   # gated or private: card_data above is still public
        else:
            body = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S).strip()
            out["readme"] = body[:README_CHARS]
    return out

on_hf_tab()
cards = []
for kind, rid in REPOS:
    c = card(kind, rid)
    if c is None:
        print(f"\n{kind}/{rid}: not found (or private)")
        continue
    cards.append(c)
    print(f"\n{c['id']} [{kind}] {c['url']}")
    print(f"  downloads 30d {c['downloads_30d']:,} | all-time {c['downloads_all_time']:,} | likes {c['likes']:,} | trending {c['trending']} | gated {c['gated']}")
    print(f"  license {c['license']} | task {c['task']} | library {c['library']} | params {c['params']} | base_model {c['base_model']}")
    print(f"  language {c['language']} | arxiv {c['arxiv']} | {len(c['files'])} files | updated {c['last_modified']}")
    print(f"  card keys: {c['card_keys']}")
    if kind == "datasets":
        print(f"  rows by split: {c['rows_by_split']} | size {c['size_category']}")
    if README_CHARS:
        print("  readme:", "not readable anonymously (gated)" if c.get("readme") is None else repr(c["readme"][:160]))
path = os.path.join(tempfile.gettempdir(), "hf_cards.json")
json.dump(cards, open(path, "w"), indent=1)
print("\nsaved", path)
```

Output observed on 2026-11-03:

```text
Qwen/Qwen3-0.6B [models] https://huggingface.co/Qwen/Qwen3-0.6B
  downloads 30d 22,876,234 | all-time 258,700,026 | likes 1,871 | trending 12 | gated False
  license apache-2.0 | task text-generation | library transformers | params 751632384 | base_model ['Qwen/Qwen3-0.6B-Base']
  language None | arxiv ['2505.09388'] | 10 files | updated 2025-07-26T03:46:27.000Z
  card keys: ['base_model', 'library_name', 'license', 'license_link', 'pipeline_tag']
  readme: '# Qwen3-0.6B\n<a href="https://chat.qwen.ai/" target="_blank" style="margin: 2px;">\n    <img alt="Chat" src="https://img.shields.io/badge/%F0%9F%92%9C%EF%B8%8F%2'

meta-llama/Llama-3.1-8B-Instruct [models] https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct
  downloads 30d 4,475,436 | all-time 192,541,517 | likes 8,779 | trending 61 | gated manual
  license llama3.1 | task text-generation | library transformers | params 8030261248 | base_model meta-llama/Meta-Llama-3.1-8B
  language ['en', 'de', 'fr', 'it', 'pt', 'hi', 'es', 'th'] | arxiv ['2204.05149'] | 17 files | updated 2024-09-25T17:00:57.000Z
  card keys: ['base_model', 'extra_gated_button_content', 'extra_gated_description', 'extra_gated_fields', 'extra_gated_prompt', 'language', 'license', 'pipeline_tag', 'tags']
  readme: not readable anonymously (gated)

openai/gsm8k [datasets] https://huggingface.co/datasets/openai/gsm8k
  downloads 30d 993,185 | all-time 17,508,033 | likes 2,026 | trending 2 | gated False
  license ['mit'] | task ['text-generation'] | library None | params None | base_model None
  language ['en'] | arxiv ['2110.14168'] | 7 files | updated 2026-03-23T10:18:13.000Z
  card keys: ['annotations_creators', 'configs', 'dataset_info', 'language', 'language_creators', 'license', 'multilinguality', 'paperswithcode_id', 'pretty_name', 'size_categories', 'source_datasets', 'tags', 'task_categories', 'task_ids']
  rows by split: {'main/train': 7473, 'main/test': 1319, 'socratic/train': 7473, 'socratic/test': 1319} | size ['1K<n<10K']
  readme: '# Dataset Card for GSM8K\n\n## Table of Contents\n- [Dataset Description](#dataset-description)\n  - [Dataset Summary](#dataset-summary)\n  - [Supported Tasks](#supp'

models/no-such-user/no-such-model: not found (or private)

saved <tempdir>/hf_cards.json
```

### 3. A shared listing-page URL -> the same ranking from the API, checked against the page (browser)

Translates `huggingface.co/models?...` or `/datasets?...` into the API call, loads the page, and compares the first cards with the API order. Facets whose API form was not checked are refused instead of guessed.

```python
import json, time, urllib.parse

PAGE_URLS = [   # listing pages as a person would share them
    "https://huggingface.co/models?library=gguf&license=license:mit&sort=downloads",
    "https://huggingface.co/models?pipeline_tag=text-to-image&sort=likes",
    "https://huggingface.co/datasets?task_categories=task_categories:question-answering&sort=trending",
    "https://huggingface.co/models?language=fr&sort=downloads",
    "https://huggingface.co/models?num_parameters=min:0,max:6B&sort=downloads",   # facet not mapped: refused, not guessed
]
CHECK = 5        # first N cards on the page compared with the API ranking
PAUSE = 0.3

SORTS = {"trending": "trendingScore", "likes": "likes", "downloads": "downloads", "modified": "lastModified", "created": "createdAt"}
PASS_THROUGH = {"search", "pipeline_tag", "author"}          # API params with the same name
AS_FILTER = {"library", "license", "language", "task_categories"}   # page facets checked to equal API filter=<value>

def page_url_to_api(url):
    """huggingface.co/models?... or /datasets?... listing URL -> /api/... URL with the same filters and sort.
    The API silently IGNORES unknown params (library=, license=, language=, task_categories=), so facets go to filter=."""
    u = urllib.parse.urlparse(url)
    kind = u.path.strip("/")
    if kind not in ("models", "datasets"):
        raise ValueError(f"not a /models or /datasets listing URL: {url}")
    params = [("sort", SORTS[dict(urllib.parse.parse_qsl(u.query)).get("sort", "trending")])]
    for k, v in urllib.parse.parse_qsl(u.query):
        if k in ("sort", "p"):
            continue
        if k in PASS_THROUGH:
            params.append((k, v))
        elif k in AS_FILTER:
            params.append(("filter", v))
        else:
            raise ValueError(f"page param {k}={v} has no checked API equivalent; not guessing")
    return kind, f"https://huggingface.co/api/{kind}?" + urllib.parse.urlencode(params)

FETCH_JS = """(async () => {
  try { const r = await fetch(%s, {credentials: 'omit'}); return {status: r.status, text: await r.text()}; }
  catch (e) { return {status: 0, text: String(e)}; }
})()"""

def api(url):
    r = js(FETCH_JS % json.dumps(url))
    time.sleep(PAUSE)
    if r["status"] != 200:
        raise RuntimeError(f"{url}: HTTP {r['status']} {r['text'][:200]}; stopping")
    return json.loads(r["text"])

def page_cards(url):
    """Repo ids and the compact counts line of the cards on a listing page, top to bottom."""
    try:
        on_page = js("location.origin") == "https://huggingface.co"
    except Exception:
        on_page = False
    (goto_url if on_page else new_tab)(url)
    wait_for_load()
    for _ in range(20):
        cards = js("""[...document.querySelectorAll('article a[href]')].map(a => [a.getAttribute('href'), a.innerText.replace(/\\s+/g, ' ').trim()])""")
        if cards:
            break
        time.sleep(0.5)
    else:
        raise RuntimeError(f"no repo cards on {url} ({js('document.title')!r}): stop, do not retry around it")
    prefix = "/datasets/" if "/datasets" in url else "/"
    return [(h[len(prefix):], t) for h, t in cards if h.startswith(prefix) and h.count("/") == prefix.count("/") + 1]

for url in PAGE_URLS:
    try:
        kind, api_url = page_url_to_api(url)
    except ValueError as e:
        print(f"\n{url}\n refused: {e}")
        continue
    cards = page_cards(url)[:CHECK]
    rows = api(api_url + f"&limit={CHECK}&expand[]=downloads&expand[]=likes")
    same = [c[0] for c in cards] == [r["id"] for r in rows]
    print(f"\n{url}\n -> {api_url}\n first {CHECK} page cards == API order: {same}")
    for (cid, text), r in zip(cards, rows):
        print(f"   page: {text[:70]:<72} | api: {r['id']}  dl30d {r.get('downloads', 0):,}  likes {r.get('likes', 0):,}")
```

Output observed on 2026-11-03:

```text
https://huggingface.co/models?library=gguf&license=license:mit&sort=downloads
 -> https://huggingface.co/api/models?sort=downloads&filter=gguf&filter=license%3Amit
 first 5 page cards == API order: True
   page: ornith-ai/Ornith-1.5-9B-GGUF Text Generation • 9B • Updated Aug 23 • 5   | api: ornith-ai/Ornith-1.5-9B-GGUF  dl30d 5,481,277  likes 630
   page: ornith-ai/Ornith-1.5-35B-A3B-GGUF Text Generation • 36B • Updated Aug    | api: ornith-ai/Ornith-1.5-35B-A3B-GGUF  dl30d 4,053,550  likes 576
   page: peculiar-ragdoll/Tiel-Coder-35B-A3B-GGUF-MTP Image-Text-to-Text • 0.4B   | api: peculiar-ragdoll/Tiel-Coder-35B-A3B-GGUF-MTP  dl30d 2,988,545  likes 337
   page: ISTA-DASLab/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF Text Generation • 19   | api: ISTA-DASLab/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF  dl30d 2,528,205  likes 579
   page: ornith-ai/Ornith-1.0-9B-GGUF Text Generation • 9B • Updated Jun 25 • 2   | api: ornith-ai/Ornith-1.0-9B-GGUF  dl30d 2,401,354  likes 699

https://huggingface.co/models?pipeline_tag=text-to-image&sort=likes
 -> https://huggingface.co/api/models?sort=likes&pipeline_tag=text-to-image
 first 5 page cards == API order: True
   page: black-forest-labs/FLUX.1-dev Text-to-Image • 12B • Updated Jun 27, 202   | api: black-forest-labs/FLUX.1-dev  dl30d 542,979  likes 15,923
   page: stabilityai/stable-diffusion-xl-base-1.0 Text-to-Image • 3B • Updated    | api: stabilityai/stable-diffusion-xl-base-1.0  dl30d 4,535,587  likes 8,435
   page: CompVis/stable-diffusion-v1-4 Text-to-Image • 0.9B • Updated Aug 23, 2   | api: CompVis/stable-diffusion-v1-4  dl30d 463,642  likes 7,145
   page: black-forest-labs/FLUX.1-schnell Text-to-Image • 12B • Updated Aug 16,   | api: black-forest-labs/FLUX.1-schnell  dl30d 327,985  likes 6,587
   page: abenzerps/Qwen-Image-2.1-Turbo-Quantized Text-to-Image • 7B • Updated    | api: abenzerps/Qwen-Image-2.1-Turbo-Quantized  dl30d 2,508,590  likes 5,624

https://huggingface.co/datasets?task_categories=task_categories:question-answering&sort=trending
 -> https://huggingface.co/api/datasets?sort=trendingScore&filter=task_categories%3Aquestion-answering
 first 5 page cards == API order: True
   page: Vyber07/cyber-security Viewer • Updated Aug 31 • 1 • 9.59k • 643         | api: Vyber07/cyber-security  dl30d 9,588  likes 643
   page: open-index/hacker-news Preview • Updated Aug 23 • 453k • 460             | api: open-index/hacker-news  dl30d 452,719  likes 460
   page: nvidia/Granary-v2 Updated 6 days ago • 5.39k • 45                        | api: nvidia/Granary-v2  dl30d 5,387  likes 45
   page: MoreThought/Fable-5.1-Max-Reasoning-Filtered-10000x Viewer • Updated 2   | api: MoreThought/Fable-5.1-Max-Reasoning-Filtered-10000x  dl30d 6,307  likes 461
   page: Reizxn/HolyCyber Viewer • Updated 4 days ago • 51.8k • 470 • 31          | api: Reizxn/HolyCyber  dl30d 470  likes 31

https://huggingface.co/models?language=fr&sort=downloads
 -> https://huggingface.co/api/models?sort=downloads&filter=fr
 first 5 page cards == API order: True
   page: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 Sentence S   | api: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2  dl30d 28,259,788  likes 1,498
   page: google-t5/t5-small Translation • 60.5M • Updated Jun 29, 2023 • 23.1M    | api: google-t5/t5-small  dl30d 23,130,138  likes 688
   page: intfloat/multilingual-e5-small Sentence Similarity • 0.1B • Updated Ap   | api: intfloat/multilingual-e5-small  dl30d 9,334,707  likes 481
   page: sentence-transformers/paraphrase-multilingual-mpnet-base-v2 Sentence S   | api: sentence-transformers/paraphrase-multilingual-mpnet-base-v2  dl30d 9,032,600  likes 554
   page: FacebookAI/xlm-roberta-base Fill-Mask • 0.3B • Updated Feb 19, 2024 •    | api: FacebookAI/xlm-roberta-base  dl30d 8,515,724  likes 968

https://huggingface.co/models?num_parameters=min:0,max:6B&sort=downloads
 refused: page param num_parameters=min:0,max:6B has no checked API equivalent; not guessing
```

### 4. Same endpoints over plain HTTP (no browser)

```bash
curl -s "https://huggingface.co/api/models?pipeline_tag=text-generation&sort=downloads&limit=3&expand%5B%5D=downloads&expand%5B%5D=likes"; echo
curl -s "https://huggingface.co/api/datasets/openai/gsm8k" \
  | python3 -c 'import json, sys; d = json.load(sys.stdin); c = d["cardData"]; print(d["id"], d["downloads"], d["likes"], c["license"], c["task_categories"], c["size_categories"])'
curl -s -o /dev/null -w "%{http_code} " "https://huggingface.co/api/models/no-such-user/no-such-model"; \
curl -s -o /dev/null -w "%{http_code}\n" "https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct/raw/main/README.md"
```

Output observed on 2026-11-03:

```text
[{"_id":"621ffdc036468d709f17434d","id":"openai-community/gpt2","likes":3913,"downloads":29775719},{"_id":"680da718233834890aa01f51","id":"Qwen/Qwen3-0.6B","likes":1871,"downloads":22876234},{"_id":"680da7b53a9818192728e751","id":"Qwen/Qwen3-14B","likes":533,"downloads":12993294}]
openai/gsm8k 993185 2026 ['mit'] ['text-generation'] ['1K<n<10K']
401 401
```

## Fields

| Field | Source | Notes |
|---|---|---|
| `downloads` | list and repo endpoints | downloads over the last 30 days (huggingface_hub docs, `ModelInfo.downloads`); the page shows it compact (`22.9M`) |
| `downloadsAllTime` | `expand[]=downloadsAllTime` only | cumulative since creation; not in the default list or repo response, and not a valid `sort` |
| `likes`, `trendingScore` | list (`expand[]`) and repo endpoints | `trendingScore` only via `expand[]` |
| `pipeline_tag`, `library_name` | model list and repo endpoints | task and library; datasets have no `pipeline_tag`, use `cardData.task_categories` |
| `cardData` | repo endpoint (and `expand[]=cardData`) | README YAML header as JSON: `license`, `language`, `base_model`, `datasets`, `task_categories`, `size_categories`, `dataset_info`, `extra_gated_*` |
| `safetensors.total` | model repo endpoint | parameter count when weights are safetensors; `None` otherwise |
| `gated` | repo endpoint | `False`, `"auto"` or `"manual"` (huggingface_hub docs); metadata stays public, files do not |
| `siblings[].rfilename` | repo endpoint | file list (names only) |
| `tags` | list and repo endpoints | `arxiv:<id>`, `license:<x>`, `base_model:...`, `region:us`, language codes; this is what `filter=` matches |
| `sha`, `lastModified`, `createdAt` | list (`expand[]`) and repo endpoints | ISO UTC |

## Gotchas

- **Unknown query params are ignored, not rejected.** `library=gguf`, `license=mit`, `language=fr` and `task_categories=...` each returned the same top 3 as no filter. Use `filter=gguf`, `filter=license:mit`, `filter=fr`, `filter=task_categories:question-answering`. `filter=language:fr` returns `[]`: language tags are bare codes. `pipeline_tag=`, `search=` and `author=` are real params.
- **Sort is descending only.** `direction=-1` is accepted and changes nothing; `direction=1` returns HTTP 400 `Invalid sort direction, only descending sort is supported for downloads`. An unknown sort (`downloadsAllTime`, `trending`, `modified`) returns HTTP 400 `Invalid sort parameter: <x>`. The page's `sort=trending|modified|created` map to `trendingScore|lastModified|createdAt`.
- **Missing repos return 401, not 404**, with `{"error":"Invalid username or password."}`, for anonymous callers. Gated repos' files do the same: `meta-llama/Llama-3.1-8B-Instruct/raw/main/README.md` is 401 while `/api/models/meta-llama/Llama-3.1-8B-Instruct` is 200 with full `cardData`. Treat 401 as "not readable logged out", never retry it with credentials.
- **`sort=lastModified` trusts repo timestamps.** On datasets it put `h1testmeow/dsviewer-canary-v1` first with `lastModified` 2028-12-10. Drop future dates if you rank by recency.
- **`search=` is a substring match on the repo id**, not relevance search: `search=qwen` ranked by likes includes third-party quantizations (`unsloth/...-GGUF`, `abenzerps/...`). Add `author=Qwen` for one organization's repos.
- **`expand[]` replaces the default field set.** Ask for every field you need. Without it a model list item has `downloads`, `likes`, `tags`, `pipeline_tag`, `library_name`, `createdAt` but no `lastModified`; dataset items add `lastModified`, `description`, `gated`; neither has `downloadsAllTime` or `trendingScore`. Repo info with `expand[]` returns only `_id`, `id` and the expanded fields, so block 2 makes two calls.
- **`limit` above 1000 is clamped to 1000** (1001 and 5000 both returned 1000 rows). Block 1's pager fetched 1,050 text-generation models in 2 calls, 1,050 unique ids, still sorted by downloads.
- **Page vs API.** The listing page and the API returned the same first 5 repos in the same order for all 4 page URLs in block 3. The page rounds counts (`5.39k`, `453k`); the API gives exact integers. The page count above the list (about 433,000 text-generation models on 2026-11-03; it moves by the hour) has no API equivalent; the API sends no `X-Total-Count` on these lists.
- **Datasets with several configs** list each config in `cardData.dataset_info` (gsm8k: `main` and `socratic`, both 7,473 train / 1,319 test). Block 2 keys rows by `config/split`; a single-config card stores a dict instead of a list.

## What does not work

- **Gated or private files logged out:** README, config and weights of gated repos are 401. Not worked around; the public `cardData` covers the metadata.
- **Ascending sort and all-time sort:** rejected with HTTP 400 (see Gotchas). Sort by `downloads` and read `downloadsAllTime`, or fetch more rows and sort locally.
- **The page's parameter-count slider** (`num_parameters=min:0,max:6B`): its API form was not checked, so block 3 refuses it rather than return an unfiltered ranking. Read `safetensors.total` per repo instead.
