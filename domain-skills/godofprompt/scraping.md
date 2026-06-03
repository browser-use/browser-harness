# God of Prompt — Scraping the Prompt Library

`https://godofprompt.ai/prompt-library` — a paid prompt marketplace (~12k AI prompts).
**Never use the browser.** The site is a React SPA whose data lives in a **public,
unauthenticated Directus CMS**. Everything (including the full prompt body of premium
prompts) is reachable with `http_get`. No API key, no cookies.

## Do this first

The SPA calls a Directus proxy. Base URL (found in the JS bundle, constant `MS`):

```
https://api.godofprompt.dev/api/directus/public/items/<collection>
```

Collections: `prompts`, `categories`, `recommended_tools`, `products`.

```python
import json, urllib.parse
from helpers import http_get

API = "https://api.godofprompt.dev/api/directus/public/items/prompts"
# total count -> ~12,270 and growing daily
meta = json.loads(http_get(f"{API}?limit=1&meta=filter_count"))
print(meta["meta"]["filter_count"])
```

Standard Directus query params all work: `limit` (**max 500**), `offset`, `fields`,
`sort` (e.g. `-date_created`), `filter[...][_op]=...`, `meta=filter_count`.
Responses are `{"meta": {...}, "data": [...]}`.

## The prompt object

Request only the fields you need (the default response is huge). The fields that make
up the on-page prompt card:

```python
FIELDS = ",".join([
    "id", "slug", "page_name", "prompt_name", "icon",
    "category", "sub_category",          # integer ids -> resolve via /items/categories
    "is_premium", "output_type_id",      # output_type_id: 1=text, 2=image
    "what_this_prompt_does",             # "What this prompt does" bullets
    "tips",                              # "Tips for this prompt"
    "how_to_use_the_prompt",             # "How to use the prompt"
    "description", "seo_description",
    "input_body", "prompt_body",         # THE PROMPT TEXT — see note below
    "input_format", "prompt_format",
    "likes_count", "views_count", "bookmarks_count",
    "date_created", "date_published",
    # recommended AI tool(s): M2M junction, expand the nested name
    "recommended_tools.recommended_tools_id.web_name",
    "recommended_tools.recommended_tools_id.name",
])

def q(params): return urllib.parse.urlencode(params, safe="[]")

page = json.loads(http_get(f"{API}?{q({'limit':500,'offset':0,'fields':FIELDS,'sort':'slug'})}"))
for p in page["data"]:
    body = p.get("prompt_body") or p.get("input_body")   # one of the two is always set
    tools = [t["recommended_tools_id"].get("web_name") for t in (p.get("recommended_tools") or [])]
    print(p["slug"], "|", tools, "|", len(body or ""), "chars")
```

Public page for any prompt: `https://godofprompt.ai/prompt-library/<slug>`.

### Traps (field-tested)

- **`input_body` vs `prompt_body`** — the prompt text lives in *one* of these, not both.
  `input_body` is null ~34% of the time; `prompt_body` ~99% populated. Always fall back:
  `body = prompt_body or input_body`.
- **`recommended_tools` is a M2M junction.** Raw values are junction-row ids
  (`[32380, 32381, ...]`), not tool ids. To get names you must expand the nested relation:
  `fields=recommended_tools.recommended_tools_id.web_name`. `web_name` is the clean label
  ("ChatGPT", "Claude", "Gemini", "Grok", "DeepSeek", "Midjourney"…); `name` is the
  versioned model ("Claude Sonnet 4.5"). Only ~9 tools exist (`/items/recommended_tools`).
- **`category` / `sub_category` are integer ids**, often `null` in the source — ~41% of
  prompts (≈5k) have **no category assigned** (this is the source's data, not a fetch bug;
  verify with `filter[category][_null]=true&meta=filter_count`). Resolve ids via
  `/items/categories` (199 rows, each with `parent` → build a `Parent > Child` path).
- **No `date_updated` field** (it 403s). You can detect *new* prompts via `date_created`
  but **not edits** to existing ones. For edits you must re-pull in full periodically.
- **`limit` caps at 500.** Paginate with `offset`; full library ≈ 25 pages.
- The site's own search hits `POST {base}/api/qdrant/search` with `{"search": "..."}`
  (vector search). For bulk extraction, paginate `/items/prompts` instead.

## Bulk pull (all ~12k prompts, parallel)

```python
import json, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from helpers import http_get

API="https://api.godofprompt.dev/api/directus/public/items/prompts"
def q(p): return urllib.parse.urlencode(p, safe="[]")

total = json.loads(http_get(f"{API}?limit=1&meta=filter_count"))["meta"]["filter_count"]
offsets = range(0, total, 500)
def page(off):
    return json.loads(http_get(f"{API}?{q({'limit':500,'offset':off,'fields':FIELDS,'sort':'slug'})}"))["data"]
with ThreadPoolExecutor(max_workers=8) as ex:
    all_prompts = [r for chunk in ex.map(page, offsets) for r in chunk]
```

## Incremental refresh

`date_created` is monotonic and filterable, so a re-sync only needs the new tail:

```python
since = "2026-06-03T00:00:00.000Z"   # last sync boundary
url = f"{API}?{q({'limit':500,'fields':FIELDS,'sort':'date_created','filter[date_created][_gte]':since})}"
new = json.loads(http_get(url))["data"]   # then union into your DB by id
```

A ready-made incremental syncer (full DB + category/tool enrichment + state file) lives
outside this repo at `~/Documents/godofprompt-scrape/sync_prompts.py`
(`python3 sync_prompts.py` = incremental, `--full` = complete re-pull).
