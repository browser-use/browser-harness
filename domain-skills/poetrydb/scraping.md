# PoetryDB — Scraping & Data Extraction

`https://poetrydb.org` — free REST API with 3 010 poems from 129 public-domain authors. No auth, no rate limits documented, no browser needed. All responses are JSON (always — even the `.text` suffix returns `application/json`).

**Note on Gutenberg poetry**: If you need the full text of a poetry collection as a single file (e.g., all of Whitman's *Leaves of Grass* as one document), see the Gutenberg skill — it covers fetching full ebooks. Use PoetryDB when you need individual poems, author listings, line counts, or text-search within poetry.

## Do this first

**One call gives you all poems for an author — no pagination, no auth.**

```python
import json, urllib.parse
from helpers import http_get

# Get all Emily Dickinson poems
poems = json.loads(http_get('https://poetrydb.org/author/Emily%20Dickinson'))
# poems = list of 362 dicts, each with: title, author, lines (list[str]), linecount (str)

for p in poems:
    print(p['title'], '-', p['linecount'], 'lines')
    print('\n'.join(p['lines'][:4]))
    print()
```

## Common workflows

### List all authors

```python
import json
from helpers import http_get

data = json.loads(http_get('https://poetrydb.org/author'))
authors = data['authors']   # list of 129 strings, exact names
# ['Adam Lindsay Gordon', 'Alan Seeger', 'Alexander Pope', ..., 'William Shakespeare']
print(len(authors))  # 129
```

### List all titles

```python
import json
from helpers import http_get

data = json.loads(http_get('https://poetrydb.org/title'))
titles = data['titles']     # list of 3010 strings
print(len(titles))          # 3010
```

### Fetch a poem by exact title

```python
import json
from helpers import http_get

poems = json.loads(http_get('https://poetrydb.org/title/Ozymandias'))
# Returns a list — usually 1 item, may be more for shared titles
p = poems[0]
print(p['title'])           # Ozymandias
print(p['author'])          # Percy Bysshe Shelley
print(p['linecount'])       # '14'  ← always a string, not int
print('\n'.join(p['lines']))
# I met a traveller from an antique land
# Who said: Two vast and trunkless legs of stone
# ...
```

### Search by line content

```python
import json
from helpers import http_get

# Exact substring match within any line of any poem
poems = json.loads(http_get('https://poetrydb.org/lines/Shall%20I%20compare%20thee'))
print(len(poems))           # 1
print(poems[0]['title'])    # Sonnet 18: Shall I compare thee to a summer's day?
print(poems[0]['author'])   # William Shakespeare
```

### Get sonnets (14-line poems)

```python
import json
from helpers import http_get

sonnets = json.loads(http_get('https://poetrydb.org/linecount/14'))
print(len(sonnets))         # 450
# Each item has: title, author, lines, linecount
print(sonnets[0]['title'])  # On the Death of Robert Browning
print(sonnets[0]['author']) # Algernon Charles Swinburne
```

### Random poems

```python
import json
from helpers import http_get

# Get N random poems in one call
poems = json.loads(http_get('https://poetrydb.org/random/5'))
for p in poems:
    print(f"{p['title']} — {p['author']} ({p['linecount']} lines)")
# Sonnet 132: Thine eyes I love...  — William Shakespeare (14 lines)
# THE ARSENAL AT SPRINGFIELD        — Henry Wadsworth Longfellow (48 lines)
# ...
```

### Combined field search (AND logic)

Combine up to two search fields with comma-separated names and semicolon-separated values. All fields must match.

```python
import json
from helpers import http_get

# Emily Dickinson poems with exactly 4 lines
poems = json.loads(http_get('https://poetrydb.org/author,linecount/Emily%20Dickinson;4'))
print(len(poems))   # 33

# Shakespeare's Sonnet 18 (exact title match + author)
poems = json.loads(http_get(
    'https://poetrydb.org/author,title/William%20Shakespeare;Sonnet%2018'
))
print(poems[0]['title'])    # Sonnet 18: Shall I compare thee to a summer's day?
```

### Select output fields (reduce payload)

Add a third path segment with a comma-separated field list to return only those fields.

```python
import json
from helpers import http_get

# Just titles for all Dickinson poems — much smaller payload
titles = json.loads(http_get('https://poetrydb.org/author/Emily%20Dickinson/title'))
# [{'title': 'Not at Home to Callers'}, {'title': 'After! When the Hills do'}, ...]
print(len(titles))          # 362

# Title + linecount for all 14-line poems
items = json.loads(http_get('https://poetrydb.org/linecount/14/title,author'))
# [{'title': 'On the Death of Robert Browning', 'author': 'Algernon Charles Swinburne'}, ...]
```

Available output fields: `title`, `author`, `lines`, `linecount`

### Bulk download all poems (parallel by author)

```python
import json, urllib.parse
from helpers import http_get
from concurrent.futures import ThreadPoolExecutor

def fetch_author(author):
    url = f"https://poetrydb.org/author/{urllib.parse.quote(author)}"
    r = json.loads(http_get(url))
    return r if isinstance(r, list) else []

authors = json.loads(http_get('https://poetrydb.org/author'))['authors']
# 129 authors — safe to fetch all in parallel at max_workers=10
with ThreadPoolExecutor(max_workers=10) as ex:
    all_poems = []
    for batch in ex.map(fetch_author, authors):
        all_poems.extend(batch)

print(len(all_poems))   # 3010
```

## URL schema

```
https://poetrydb.org/{input_field}/{search_term}[/{output_fields}][.json]
```

| Pattern | Example | What it returns |
|---|---|---|
| `/author` | `/author` | `{"authors": [...]}` — all 129 author names |
| `/title` | `/title` | `{"titles": [...]}` — all 3010 titles |
| `/author/{name}` | `/author/Emily%20Dickinson` | All poems by that author (exact match, case-sensitive) |
| `/title/{title}` | `/title/Ozymandias` | Poems with that exact title |
| `/lines/{text}` | `/lines/I%20met%20a%20traveller` | Poems containing that substring in any line |
| `/linecount/{n}` | `/linecount/14` | All poems with exactly N lines |
| `/random/{n}` | `/random/5` | N random poems |
| `/f1,f2/{v1};{v2}` | `/author,linecount/Dickinson;14` | AND search across two fields |
| `/{search}/{term}/{fields}` | `/author/Dickinson/title,linecount` | Return only the named fields |

## Response schema

Every poem is the same shape:

```json
{
  "title": "Ozymandias",
  "author": "Percy Bysshe Shelley",
  "lines": [
    "I met a traveller from an antique land",
    "Who said: Two vast and trunkless legs of stone",
    "..."
  ],
  "linecount": "14"
}
```

Author/title list endpoints return a single-key dict:

```json
{"authors": ["Adam Lindsay Gordon", "Alan Seeger", ...]}
{"titles": [" Thoughts On The Works Of Providence", "\"All Is Vanity...\"", ...]}
```

Error response (status stays 200, body is JSON):

```json
{"status": 404, "reason": "Not found"}
```

## Gotchas

- **`linecount` is always a string, not an integer.** `p['linecount']` returns `'14'`, not `14`. Use `int(p['linecount'])` if you need numeric comparison.

- **Author names are exact and case-sensitive.** `Shakespeare` matches `William Shakespeare` (substring match seems to work for the author path), but `shakespeare` (lowercase) returns 404. Use the name exactly as it appears in the `/author` list. Always URL-encode spaces as `%20`.

- **The `/title/` endpoint is exact-match only.** `https://poetrydb.org/title/Because%20I` returns 404 even though "Because I could not stop for Death" exists. You must supply the full title exactly as listed in `/title`. The `:abs` suffix works for some title searches but inconsistently — avoid relying on it.

- **Combined search uses semicolons as separators, not commas.** URL: `/author,linecount/Emily%20Dickinson;4` — the comma separates field names, the semicolon separates values. Swapping them gives 404.

- **`.text` and `.json` output suffixes both return `application/json`.** The `.text` suffix does NOT return a plain text poem — it still returns the standard JSON array. Always parse with `json.loads()` regardless of suffix.

- **Empty lines in poems are real array entries.** `p['lines']` may contain `''` (empty string) to represent stanza breaks. Filter with `[l for l in p['lines'] if l]` if you only want the text lines.

- **`status` in error responses is a string, not an int.** The 404 body is `{"status": "404", ...}` in some endpoints and `{"status": 404, ...}` in others — always check with `isinstance(data, list)` rather than parsing the status field.

- **No pagination — all results returned at once.** A call for `linecount/14` returns all 450 sonnets in a single response. No `page`, `limit`, or `offset` parameters exist.

- **Max random poems per call is not documented.** In practice, `random/100` and higher work fine. No hard cap was observed.

- **The `poemcount` input field is not listable.** `GET /poemcount` returns a 405 error. Only `author` and `title` support the bare list call.
