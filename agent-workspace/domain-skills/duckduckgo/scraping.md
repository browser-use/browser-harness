# DuckDuckGo — Instant Answer API

`https://api.duckduckgo.com` — completely public, no auth, no API key. Returns Wikipedia-sourced abstracts, infoboxes, and instant answers for well-known entities, calculations, and utility queries. Not a search engine — it does not return a list of web results for arbitrary queries.

## Do this first: pick your query type

| Query type | Example | `Type` | Returns |
|------------|---------|--------|---------|
| Named entity (specific) | `apple inc` | A | Full abstract + infobox |
| Ambiguous term | `python` | D | Disambiguation list in `RelatedTopics` |
| Instant answer | `random number` | E | Direct answer in `Answer` field |
| No match | `how to cook pasta` | `""` | All fields empty |

**Use `skip_disambig=1` and `no_html=1` in almost every call.** `skip_disambig=1` upgrades D→A when there's an obvious primary result (e.g., `elon musk` goes from disambiguation to full article). `no_html=1` removes `<b>` tags from the `Answer` field and strips bold markup from `Result` HTML strings.

**Never use a browser.** Everything is a single `http_get` JSON call, 183–320ms.

---

## Fastest path: entity lookup

```python
import json, urllib.parse
from helpers import http_get

def ddg_instant(query: str) -> dict:
    q = urllib.parse.quote(query)
    raw = http_get(
        f"https://api.duckduckgo.com/?q={q}&format=json&no_html=1&skip_disambig=1"
    )
    return json.loads(raw)

# Entity with Wikipedia abstract + infobox
data = ddg_instant("openai")
# data['Type'] == 'A'
print(data['Heading'])        # 'OpenAI'
print(data['AbstractText'])   # 'OpenAI is an American artificial intelligence research...'
print(data['AbstractURL'])    # 'https://en.wikipedia.org/wiki/OpenAI'
print(data['OfficialWebsite'])# 'https://openai.com/'
print(data['Entity'])         # 'company'

# Person lookup (skip_disambig resolves D→A automatically)
data = ddg_instant("elon musk")
print(data['Type'])           # 'A' (was 'D' without skip_disambig)
print(data['AbstractText'][:100])  # 'Elon Reeve Musk is a businessman...'
print(data['Image'])          # '/i/be2a8644.jpg' — prepend https://duckduckgo.com

# Full image URL
img_url = f"https://duckduckgo.com{data['Image']}" if data['Image'] else None
```

---

## Instant answers (Type = E)

```python
import json, urllib.parse
from helpers import http_get

def ddg_answer(query: str) -> tuple[str, str]:
    """Returns (answer_text, answer_type). answer_text is '' if no result."""
    q = urllib.parse.quote(query)
    raw = http_get(
        f"https://api.duckduckgo.com/?q={q}&format=json&no_html=1&no_redirect=1"
    )
    data = json.loads(raw)
    ans = data.get('Answer', '')
    # Answer can be a dict when it's a widget (calculator, converter) — only string Answers are usable
    return (ans if isinstance(ans, str) else '', data.get('AnswerType', ''))

# Confirmed working instant answers:
text, kind = ddg_answer("random number")
# text='0.245013228691281 (random number)', kind='rand'

text, kind = ddg_answer("generate password")
# text='ZCsbe8iY (random password)', kind='pw'

text, kind = ddg_answer("ip address")
# text='Your IP address is 73.158.74.222 in San Francisco, California, United States (94121)', kind='ip'

text, kind = ddg_answer("base64 encode hello")
# text='Base64 encode d: aGVsbG8=', kind='base64_conversion'

text, kind = ddg_answer("md5 hash hello")
# text='5d41402abc4b2a76b9719d911017c592', kind='md5'

text, kind = ddg_answer("pi")
# text='3.14159', kind='constants'

text, kind = ddg_answer("today date")
# text='\nS M T W T F S      April 2026\n...|18|...', kind='calendar'

text, kind = ddg_answer("timer 5 minutes")
# text='300', kind='timer'   — returns raw seconds

text, kind = ddg_answer("lorem ipsum")
# text='Ea hic quia corporis. Minus consequuntur...', kind='lorem_ipsum'

# Color lookup — must URL-encode the # sign:
text, kind = ddg_answer("color #FF5733")
# text='Hex: #FF5733 ~ RGBA(255, 87, 51, 1) ~ RGB(100%, 34%, 20%) ~ HSL(11, 100%, 60%) ~ CMYB(0%, 66%, 80%, ...', kind='color_code'
```

**Widget answers return a dict, not a string** — `sqrt(144)`, `1 mile in km`, `100 USD in EUR`, and `stopwatch` all return `Answer` as a dict like `{'from': 'calculator', 'id': 'calculator', 'result': '', ...}`. The `result` key is empty — the actual computation happens client-side in a JS widget. Treat dict `Answer` values as "not usable via API".

---

## Full response schema

Every response has exactly these 21 top-level keys (all always present):

```
Abstract         # same as AbstractText (redundant, use AbstractText)
AbstractSource   # "Wikipedia" when present, "" otherwise
AbstractText     # Wikipedia-sourced summary paragraph (up to ~1000 chars)
AbstractURL      # Wikipedia article URL
Answer           # string or dict — instant answer result (see above)
AnswerType       # string key identifying the answer plugin (e.g. "rand", "ip")
Definition       # almost always "" — not reliably populated
DefinitionSource # almost always ""
DefinitionURL    # almost always ""
Entity           # entity type: "company", "programming language", "person", etc.
Heading          # entity display name
Image            # relative path e.g. "/i/4d83768732377cf3.png" — prepend https://duckduckgo.com
ImageHeight      # int or "" when no image
ImageIsLogo      # 0 or 1 integer when image present; "" otherwise
ImageWidth       # int or "" when no image
Infobox          # dict with "content" and "meta" lists, or "" if no infobox
OfficialDomain   # e.g. "openai.com" — only for entities with a known website
OfficialWebsite  # e.g. "https://openai.com/" — only when DDG knows it
Redirect         # target URL when query is a bang (e.g. !g python) with no_redirect=1
RelatedTopics    # list — see below
Results          # list — official site links (usually 0 or 1 item)
Type             # "A", "D", "C", "N", "E", or ""
meta             # API plugin metadata — rarely needed
```

### `RelatedTopics` item structure

Each item is one of two shapes:

**Plain topic** (the common case):
```python
{
    "FirstURL": "https://duckduckgo.com/Deep_learning",
    "Icon": {"Height": "", "URL": "/i/abc123.png", "Width": ""},  # URL often ""
    "Result": "<a href=\"...\">Deep learning</a>— branch of ML...",  # HTML
    "Text": "Deep learning — branch of ML concerned with artificial neural networks."
}
```

**Section** (disambiguation pages only — when `Type` is `D` without `skip_disambig`):
```python
{
    "Name": "Science & Technology",   # section heading
    "Topics": [                        # list of plain topic objects
        {"FirstURL": "...", "Icon": {...}, "Result": "...", "Text": "..."},
        ...
    ]
}
```

For A-type results, `RelatedTopics` are Wikipedia category links (e.g. `"American aerospace engineers"` pointing to `https://duckduckgo.com/c/...`). These are not web search results — they are DDG topic pages.

### `Results` item structure

Usually 0 or 1 item. When present, it's the official website:
```python
{
    "FirstURL": "https://www.apple.com/",
    "Icon": {"Height": 16, "URL": "/i/apple.com.ico", "Width": 16},
    "Result": "<a href=\"https://www.apple.com/\">Official site</a>...",
    "Text": "Official site"
}
```
Icon URLs in `Results` are relative — prepend `https://duckduckgo.com`.

### `Infobox` structure

```python
ib = data['Infobox']  # dict or "" (empty string when absent)
if isinstance(ib, dict):
    content = ib['content']  # list of structured fields
    # Each content item:
    # {"data_type": "string", "label": "Founded", "value": "December 08, 2015"}
    # {"data_type": "string", "label": "Founders", "value": "Sam Altman, Elon Musk, ..."}
    
    meta = ib['meta']    # list of metadata items
    # {"data_type": "string", "label": "article_title", "value": "OpenAI"}
    # {"data_type": "string", "label": "template_name", "value": "infobox company"}

# Extract infobox as flat dict:
if isinstance(data['Infobox'], dict):
    fields = {item['label']: item['value'] for item in data['Infobox']['content']}
    # fields['Founded'] == 'December 08, 2015'
    # fields['Products'] == 'ChatGPT, GPT-5...'
```

`Infobox` is `""` (empty string, not `None`, not `{}`) when absent. Always check with `isinstance(data['Infobox'], dict)`.

---

## Query parameters

| Parameter | Values | Effect |
|-----------|--------|--------|
| `q` | URL-encoded query | The search query |
| `format` | `json` | Required — omit for HTML response |
| `no_redirect` | `1` | Returns redirect URL in `Redirect` field instead of HTTP 302; required for bang queries (`!g`, `!yt`) |
| `no_html` | `1` | Strips `<b>` from `Answer`; strips bold markup from `Result` HTML; use in almost every call |
| `skip_disambig` | `1` | Resolves ambiguous D-type queries to the primary result; upgrades D→A when unambiguous |
| `t` | any string | Source identifier tag (e.g. `t=myapp`); has no effect on results |
| `callback` | function name | Wraps response in JSONP: `mycallback({...})` |

---

## Type field values

| Type | Meaning | AbstractText | RelatedTopics |
|------|---------|--------------|---------------|
| `A` | Article — specific Wikipedia entity | Full paragraph | Category links |
| `D` | Disambiguation — ambiguous term | Empty `""` | List of possible meanings (may include sections) |
| `C` | Categories | Varies | Category items |
| `N` | Name | Varies | Name-related items |
| `E` | Exclusive — instant answer widget | Empty `""` | Empty `[]` |
| `""` | No result | Empty `""` | Empty `[]` |

In practice, C and N types are rare. A, D, E, and empty cover nearly all queries.

---

## What returns useful results vs empty

**Returns AbstractText (A type):**
- Named companies: `apple inc`, `openai`, `google`
- Specific technologies: `python programming language`, `javascript`, `linux kernel`
- Well-known people with `skip_disambig=1`: `elon musk`, `ada lovelace`
- Scientific concepts: `machine learning`, `photosynthesis`, `circumference`
- Specific software: `vim`, `postgresql`, `nginx`

**Returns RelatedTopics only (D type):**
- Ambiguous single words: `python`, `linux`, `react`, `programming`
- Ambiguous names: `apple` (returns empty — too ambiguous even for D), `new york`

**Returns empty (Type = ""):**
- How-to queries: `how to cook pasta`, `how to learn python`
- Opinion/listicle: `best laptops 2024`, `top 10 programming languages`
- Current events: `weather london`, `bitcoin price`
- Site search operators: `site:example.com`
- Multi-word specifics not in DDG's dataset: `numpy python library`, `javascript tutorial`

**Returns instant answer (E type):**
- Random: `random number`, `generate password`, `lorem ipsum`
- Math: `pi`, `timer 5 minutes`
- Network: `ip address`
- Encoding: `base64 encode <text>`, `md5 hash <text>`
- Color lookup: `color #RRGGBB` (must URL-encode the `#`)

---

## Gotchas

**`Infobox` is `""` not `None` when absent.** Always check with `isinstance(data['Infobox'], dict)` — `if data['Infobox']` also works since `""` is falsy.

**Image and Icon URLs are relative.** `data['Image']` is `/i/abc123.png`. Prepend `https://duckduckgo.com` to make it absolute. Same for Icon URLs in `RelatedTopics` and `Results`.

**`Answer` can be a dict (widget), not a string.** Queries like `1 mile in km`, `100 USD in EUR`, `sqrt(144)`, and `stopwatch` return `Answer` as a dict with `{'from': 'calculator', 'result': '', ...}`. The `result` key is empty — the widget computes client-side. Only string `Answer` values are usable via the API.

**`color #RRGGBB` requires URL encoding of `#`.** Using `q=color+#FF5733` returns an HTML page (HTTP redirect). Use `urllib.parse.quote("color #FF5733")` which encodes to `color+%23FF5733`.

**Bang queries without `no_redirect=1` return HTML, not JSON.** `!g python` (without `no_redirect=1`) causes an HTTP 302 to `google.com/search?q=python`. The `http_get` helper follows the redirect and returns Google's HTML — `json.loads` fails. Always add `no_redirect=1` when the query might contain bangs.

**`skip_disambig=1` can add latency for truly ambiguous terms.** For `apple` (no "inc"), DDG returns Type `""` even with `skip_disambig=1` — it's so ambiguous it gives nothing. For `elon musk`, `skip_disambig=1` switches from D to A and adds `RelatedTopics` (39 items vs 4), which means a larger response (~5x).

**`AbstractText` is empty for D-type results.** When `Type == 'D'`, DDG only returns `RelatedTopics` (the disambiguation list). The abstract is only filled for `Type == 'A'`.

**`RelatedTopics` for A-type are Wikipedia categories, not related searches.** For `openai`, the 4 `RelatedTopics` are `"American artificial intelligence companies"`, `"Companies in San Francisco"`, etc. — these are DDG category page links, not useful web search results.

**`Definition` / `DefinitionSource` / `DefinitionURL` are always empty** in observed responses. These fields are part of the schema but not reliably populated by any current DDG plugin.

**No rate limiting observed.** 15 rapid sequential requests completed in 3.11s (~208ms avg) with no throttling, no 429, and consistent response structure throughout. DDG does not publish rate limits; the API is designed for "reasonable" use with a `t=` source identifier.

**`OfficialWebsite` is only set for a subset of A-type results.** `machine learning` (Type A) has no `OfficialWebsite`. `openai`, `python programming language`, and `linux kernel` all have one. Always check with `data.get('OfficialWebsite', '')`.

**No_html does not affect the `Result` HTML string.** `Results[0]['Result']` still contains `<a href="...">` tags with `no_html=1`. The `no_html` flag only removes `<b>` bold tags. Use `Results[0]['Text']` for the plain-text version, or `Results[0]['FirstURL']` for just the URL.

---

## Complete working example

```python
import json, urllib.parse
from helpers import http_get

def ddg_entity(query: str) -> dict | None:
    """
    Fetch a DuckDuckGo Instant Answer for a named entity.
    Returns structured data or None if no result.
    """
    q = urllib.parse.quote(query)
    raw = http_get(
        f"https://api.duckduckgo.com/?q={q}&format=json&no_html=1&skip_disambig=1"
    )
    data = json.loads(raw)
    if not data.get('AbstractText') and not data.get('Answer'):
        return None

    result = {
        'type': data['Type'],
        'heading': data['Heading'],
        'abstract': data['AbstractText'],
        'abstract_url': data['AbstractURL'],
        'entity': data['Entity'],
        'official_website': data['OfficialWebsite'],
        'image': f"https://duckduckgo.com{data['Image']}" if data['Image'] else None,
        'answer': data['Answer'] if isinstance(data['Answer'], str) else None,
        'answer_type': data['AnswerType'],
    }

    # Extract infobox as flat dict
    if isinstance(data['Infobox'], dict):
        result['infobox'] = {
            item['label']: item['value']
            for item in data['Infobox']['content']
        }

    # Official site URL (from Results)
    if data['Results']:
        result['official_site_url'] = data['Results'][0]['FirstURL']

    return result

# Example outputs (validated 2026-04-18):
r = ddg_entity("openai")
# r['type']            == 'A'
# r['heading']         == 'OpenAI'
# r['abstract'][:50]   == 'OpenAI is an American artificial intelligence res'
# r['entity']          == 'company'
# r['official_website']== 'https://openai.com/'
# r['image']           == 'https://duckduckgo.com/i/fb410946942ab334.png'
# r['infobox']['Founded'] == 'December 08, 2015'
# r['infobox']['Products'] == 'ChatGPT, GPT-5...'

r = ddg_entity("python programming language")
# r['type']            == 'A'
# r['entity']          == 'programming language'
# r['official_website']== 'https://www.python.org/'
# r['infobox']['Paradigm'] == 'Multi-paradigm: object-oriented,...'
```
