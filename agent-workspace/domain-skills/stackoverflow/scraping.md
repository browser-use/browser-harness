# Stack Overflow — Scraping & Data Extraction

`https://stackoverflow.com` — all public read-only data is available via the Stack Exchange API v2.3. No auth, no browser required for any read operation. API is fast, returns gzip-compressed JSON, and works transparently with `http_get`.

## Do this first: pick your access path

| Goal | Best approach | Notes |
|------|--------------|-------|
| Top/hot questions by tag | `GET /2.3/questions` | Add `filter=withbody` for question text |
| Answers for a question | `GET /2.3/questions/{id}/answers` | Add `filter=withbody` for answer text |
| Search by keyword + tag | `GET /2.3/search/advanced` | More filters than `/search` |
| Simple title keyword search | `GET /2.3/search` | `intitle=` param |
| Fetch by known question IDs | `GET /2.3/questions/{id1};{id2};...` | Semicolon-delimited batch, up to 100 |
| User profile + reputation | `GET /2.3/users/{id}` | Public fields only |
| User activity timeline | `GET /2.3/users/{id}/timeline` | Events: badges, answers, questions |
| User's questions / answers | `GET /2.3/users/{id}/questions` or `/answers` | Standard listing |
| Comments on a post | `GET /2.3/questions/{id}/comments` | Needs `filter=withbody` for body |
| Related questions | `GET /2.3/questions/{id}/related` | Returns linked/similar questions |
| Answer by ID directly | `GET /2.3/answers/{id}` | One or more semicolon-separated IDs |
| Popular tags | `GET /2.3/tags` | Sort by `popular`, `activity`, or `name` |
| Site-wide statistics | `GET /2.3/info` | Total questions, quota, etc. |
| Question HTML page | `http_get` with User-Agent | Returns 777KB HTML; prefer API |

**Use the API for all data tasks.** The HTML page is 777KB, lacks clean structure, and the JSON-LD block only contains `WebSite` and `Organization` objects (no `QAPage` or `Question` schema). The API returns the same data in milliseconds, fully structured.

---

## Quota limits

The API is unauthenticated-friendly but strictly quota-capped per IP per day:

| Auth level | Daily quota | Burst |
|------------|-------------|-------|
| No key (unauthenticated) | **300 requests/day** | No enforced burst limit observed |
| With API key | **10,000 requests/day** | Same |

Check your remaining quota in every response envelope:

```python
import json
data = json.loads(http_get("https://api.stackexchange.com/2.3/info?site=stackoverflow"))
print("Quota remaining:", data.get('quota_remaining'))  # e.g. 273
print("Quota max:", data.get('quota_max'))              # 300 unauthenticated, 10000 with key
# Confirmed: quota_max=300, quota_remaining decrements per call
```

Every API response includes `quota_remaining` in the envelope. Monitor it. When it hits 0, all calls return HTTP 400 with `error_id: 502` (throttle_violation). There is no retry-after header — wait until midnight UTC.

**If you have an API key**, append `&key=YOUR_KEY` to any URL to use the 10,000/day quota.

---

## Response envelope

Every response from the Stack Exchange API is wrapped in a consistent envelope:

```python
{
  "items": [...],          # list of result objects
  "has_more": True/False,  # whether more pages exist
  "quota_max": 300,        # total daily quota
  "quota_remaining": 273,  # calls left today
  "backoff": None          # seconds to wait before next call (rare)
}
```

Always check `data.get('backoff')` — if it returns an integer, sleep that many seconds before the next call. Ignoring it causes throttle errors.

Error responses raise `urllib.error.HTTPError` (not a JSON envelope):
- HTTP 400 — invalid parameter (e.g. bad site name) — raises exception
- HTTP 400 with JSON body — quota exhausted or throttle_violation

```python
try:
    data = json.loads(http_get("https://api.stackexchange.com/2.3/questions?site=stackoverflow&pagesize=1"))
except Exception as e:
    print("API error:", e)   # HTTPError HTTP Error 400: Bad Request
```

---

## `filter=withbody` — required for post content

By default, the API strips the `body` field from all responses. You **must** add `filter=withbody` to get question or answer text. This applies to questions, answers, and comments alike.

```python
import json

# WITHOUT filter=withbody — body field is ABSENT
data = json.loads(http_get("https://api.stackexchange.com/2.3/questions?order=desc&sort=votes&tagged=python&site=stackoverflow&pagesize=1"))
q = data['items'][0]
print("Has body:", 'body' in q)   # False
print("Keys:", sorted(q.keys()))
# ['accepted_answer_id', 'answer_count', 'content_license', 'creation_date',
#  'is_answered', 'last_activity_date', 'last_edit_date', 'link', 'owner',
#  'protected_date', 'question_id', 'score', 'tags', 'title', 'view_count']

# WITH filter=withbody — body field is PRESENT
data = json.loads(http_get("https://api.stackexchange.com/2.3/questions?order=desc&sort=votes&tagged=python&site=stackoverflow&pagesize=1&filter=withbody"))
q = data['items'][0]
print("Has body:", 'body' in q)   # True
print("Body preview:", q['body'][:60])
# '<p>What functionality does the <a href="https://do...'
```

---

## HTML encoding in API responses

The API returns HTML in two contexts, and plain text in a third:

- **`body` field** (questions, answers, comments) — full HTML markup. Headings, code blocks, links, blockquotes, lists. Strip with `html.parser` for plain text.
- **`title` field** — HTML-entity-encoded plain text. Quotes, angle brackets, and ampersands are escaped (`&quot;`, `&lt;`, `&amp;`). Decode with `html.unescape()`.
- **`display_name`, `link`, `tags`** — plain text, no encoding.

```python
import json, html
from html.parser import HTMLParser

data = json.loads(http_get("https://api.stackexchange.com/2.3/questions/231767?site=stackoverflow&filter=withbody"))
q = data['items'][0]

# Title has HTML entities
print("Raw title:", q['title'])
# 'What does the &quot;yield&quot; keyword do in Python?'
print("Decoded:", html.unescape(q['title']))
# 'What does the "yield" keyword do in Python?'

# Body is full HTML — strip for plain text
class Stripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
    def handle_data(self, d):
        self.text.append(d)
    def get_text(self):
        return ''.join(self.text)

s = Stripper()
s.feed(q['body'])
print(s.get_text()[:200])
# 'What functionality does the yield keyword do in Python?\nWhat is the ...'
```

---

## Common workflows

### Top questions by tag (API)

```python
import json, html
data = json.loads(http_get(
    "https://api.stackexchange.com/2.3/questions"
    "?order=desc&sort=votes&tagged=python&site=stackoverflow&pagesize=5&filter=withbody"
))
for q in data['items']:
    print(q['question_id'], q['score'], html.unescape(q['title'])[:60])
    print("  Tags:", q['tags'][:3], "Answers:", q['answer_count'])
print("Quota remaining:", data.get('quota_remaining'))
# 231767 13133 What does the "yield" keyword do in Python?
#   Tags: ['python', 'iterator', 'generator'] Answers: 51
# 419163 8438 What does if __name__ == "__main__": do?
#   Tags: ['python', 'namespaces', 'program-entry-point'] Answers: 40
# Quota remaining: 299
```

Sort options for `/questions`: `activity`, `votes`, `creation`, `hot`, `week`, `month`.

### Answers for a question

```python
import json
data = json.loads(http_get(
    "https://api.stackexchange.com/2.3/questions/231767/answers"
    "?order=desc&sort=votes&site=stackoverflow&filter=withbody&pagesize=3"
))
for a in data['items']:
    print(f"Score: {a['score']}, Accepted: {a.get('is_accepted')}")
    print(f"  Body preview: {a['body'][:150]}")
# Score: 18307, Accepted: True
#   Body preview: <p>To understand what <a href="...">yield</a> does, ...
# Score: 2596, Accepted: False
# Score: 802, Accepted: False
```

Answer fields (with `filter=withbody`): `answer_id`, `question_id`, `score`, `is_accepted`, `body`, `owner`, `creation_date`, `last_activity_date`, `content_license`.

### Fetch questions by ID (batch)

Fetch up to 100 questions in one call using semicolons:

```python
import json
data = json.loads(http_get(
    "https://api.stackexchange.com/2.3/questions/231767;419163;394809"
    "?site=stackoverflow&filter=withbody"
))
print("Fetched:", len(data['items']))   # 3
for q in data['items']:
    print(q['question_id'], q['score'], q['title'][:50])
# 231767 13133 What does the &quot;yield&quot; keyword do in Pyth
# 419163 8438  What does if __name__ == &quot;__main__&quot;: do?
# 394809 8125  Does Python have a ternary conditional operator?
```

### Search — `search/advanced` vs `search`

Use `/search/advanced` when you need combined keyword + tag filtering. Use `/search` when searching only by title keyword (`intitle=`).

```python
import json

# search/advanced: keyword in body OR title, filtered by tag, sorted by relevance
data = json.loads(http_get(
    "https://api.stackexchange.com/2.3/search/advanced"
    "?q=asyncio+event+loop&tagged=python&site=stackoverflow&pagesize=5&order=desc&sort=relevance"
))
for q in data['items']:
    print(q['score'], q['answer_count'], q['title'][:70])
# 137 3  "Asyncio Event Loop is Closed" when getting loop
# 47  3  Can an asyncio event loop run in the background without suspending the

# search: title-only keyword search via intitle=
data = json.loads(http_get(
    "https://api.stackexchange.com/2.3/search"
    "?intitle=asyncio+event+loop&site=stackoverflow&pagesize=5&order=desc&sort=relevance"
))
```

`search/advanced` additional params: `accepted=True` (only questions with accepted answers), `answers=1` (minimum answer count), `body=` (keyword in body), `user=` (filter by owner user ID), `views=` (minimum view count), `fromdate=`/`todate=` (Unix timestamps).

### User profile

```python
import json

# Basic user info
user = json.loads(http_get("https://api.stackexchange.com/2.3/users/1?site=stackoverflow"))
u = user['items'][0]
print("User:", u['display_name'], "Rep:", u['reputation'], "Badges:", u['badge_counts'])
# User: Jeff Atwood  Rep: 64159  Badges: {'bronze': 153, 'silver': 153, 'gold': 48}

# Fields: user_id, display_name, reputation, badge_counts, location, link,
#         creation_date, last_access_date, is_employee, account_id,
#         accept_rate, profile_image, website_url

# Timeline (badge, question, answer events)
data = json.loads(http_get("https://api.stackexchange.com/2.3/users/1/timeline?site=stackoverflow&pagesize=5"))
print("Event types:", set(i['timeline_type'] for i in data['items']))
# {'badge'}

# User's top answers
answers = json.loads(http_get("https://api.stackexchange.com/2.3/users/1/answers?site=stackoverflow&pagesize=5&order=desc&sort=votes"))
for a in answers['items']:
    print("Score:", a['score'], "Question ID:", a.get('question_id'))

# User's questions
questions = json.loads(http_get("https://api.stackexchange.com/2.3/users/1/questions?site=stackoverflow&pagesize=3&order=desc&sort=votes"))
for q in questions['items']:
    print(q['question_id'], q['score'], q['title'][:60])
# 9  2273  How do I calculate someone&#39;s age based on a DateTime typ
# 11 1656  Calculate relative time in C#
```

### Comments (requires `filter=withbody`)

```python
import json
data = json.loads(http_get(
    "https://api.stackexchange.com/2.3/questions/231767/comments"
    "?site=stackoverflow&pagesize=5&order=desc&sort=creation&filter=withbody"
))
for c in data['items']:
    print("Score:", c['score'], "Body:", c.get('body','')[:80])
# Comment keys (without filter): comment_id, content_license, creation_date,
#   edited, owner, post_id, reply_to_user, score
# With filter=withbody: adds 'body' field (HTML-encoded)
```

### Related questions

```python
import json
related = json.loads(http_get(
    "https://api.stackexchange.com/2.3/questions/231767/related?site=stackoverflow&pagesize=5"
))
for q in related['items']:
    print(q['question_id'], q['score'], q['title'][:60])
# 25232350 15 how generators work in python
# 28880095 11 What does a plain yield keyword do in Python?
```

### Popular tags

```python
import json
tags = json.loads(http_get("https://api.stackexchange.com/2.3/tags?order=desc&sort=popular&site=stackoverflow&pagesize=5"))
for t in tags['items']:
    print(f"{t['name']}: {t['count']:,} questions")
# javascript: 2,531,995 questions
# java: 1,921,907 questions
# c#: 1,626,728 questions
# python: (check live — grows daily)
```

---

## Pagination

Use `page=` (1-indexed) and `pagesize=` (max 100). Check `has_more` in the envelope to know whether a next page exists.

```python
import json

def fetch_all_pages(url_base, max_pages=5):
    """Fetch multiple pages from any Stack Exchange API endpoint."""
    results = []
    for page in range(1, max_pages + 1):
        data = json.loads(http_get(f"{url_base}&page={page}"))
        results.extend(data['items'])
        if not data.get('has_more'):
            break
        if data.get('backoff'):
            import time; time.sleep(data['backoff'])
    return results

questions = fetch_all_pages(
    "https://api.stackexchange.com/2.3/questions?order=desc&sort=votes"
    "&tagged=python&site=stackoverflow&pagesize=10",
    max_pages=3
)
print("Total fetched:", len(questions))  # up to 30
```

Note: `page=2` with `pagesize=3` returns the 4th–6th items. Confirmed working — `has_more: True` on page 2 of top Python questions.

---

## Parallel fetching (multiple questions or answers)

```python
import json
from concurrent.futures import ThreadPoolExecutor

def fetch_top_answer(qid):
    data = json.loads(http_get(
        f"https://api.stackexchange.com/2.3/questions/{qid}/answers"
        "?order=desc&sort=votes&site=stackoverflow&filter=withbody&pagesize=1"
    ))
    if data['items']:
        a = data['items'][0]
        return {"qid": qid, "top_score": a['score'], "accepted": a.get('is_accepted')}
    return {"qid": qid, "top_score": 0}

qids = [231767, 419163, 394809, 100003, 82831]
with ThreadPoolExecutor(max_workers=3) as ex:
    results = list(ex.map(fetch_top_answer, qids))

for r in results:
    print(r)
# {'qid': 231767, 'top_score': 18307, 'accepted': True}
# {'qid': 419163, 'top_score': 9051, 'accepted': True}
# {'qid': 394809, 'top_score': 9355, 'accepted': True}
# {'qid': 100003, 'top_score': 9334, 'accepted': False}
# {'qid': 82831, 'top_score': 6793, 'accepted': False}
```

Keep `max_workers` at 3 or below when unauthenticated — parallel calls consume quota simultaneously. At 3 workers, 5 questions used 5 quota units (expected).

---

## HTML page scraping (avoid for data tasks)

The HTML page works but returns 777KB and has no clean `QAPage` JSON-LD. Use it only when you need something not in the API (e.g. rendered MathJax, ads context).

```python
import re, html as htmllib
headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
page = http_get("https://stackoverflow.com/questions/231767/what-does-the-yield-keyword-do-in-python", headers=headers)
print("HTML length:", len(page))   # 777138

# Page title (includes site suffix)
title_m = re.search(r'<title>([^<]+)</title>', page)
if title_m:
    print(htmllib.unescape(title_m.group(1)))
# 'iterator - What does the "yield" keyword do in Python? - Stack Overflow'

# Answer count via itemprop
ans_count = re.search(r'itemprop="answerCount"[^>]*>(\d+)<', page)
if ans_count:
    print("Answers:", ans_count.group(1))   # '51'

# Score via itemprop (has whitespace around number)
score_m = re.search(r'itemprop="upvoteCount"[^>]*>\s*(-?\d+)\s*<', page)
if score_m:
    print("Score:", score_m.group(1))   # '13133'

# JSON-LD is present but only has WebSite and Organization — NOT QAPage/Question
ld_match = re.search(r'<script type="application/ld\+json">(.*?)</script>', page, re.DOTALL)
if ld_match:
    d = json.loads(ld_match.group(1))
    types = [item.get('@type') for item in d.get('@graph', [])]
    print("JSON-LD types:", types)   # ['WebSite', 'Organization'] — no QAPage
```

---

## Gotchas

- **300 req/day unauthenticated is per IP, resets at midnight UTC.** 6 tests consumed ~27 quota units in one session. With parallel workers and loops, you can burn through 300 in minutes. Always check `quota_remaining` in responses.

- **`filter=withbody` is required for body content.** Without it, `body` is simply absent from the response — no error, no empty string, just a missing key. Applies to questions, answers, AND comments.

- **Title field has HTML entities, body field has full HTML markup.** They need different decoding strategies: `html.unescape()` for titles, `HTMLParser` stripping for bodies. Don't confuse them.

- **Titles in API responses contain `&quot;`, `&lt;`, `&amp;`, `&#39;`** — raw output is `What does the &quot;yield&quot; keyword do in Python?`. Always call `html.unescape()` before displaying or comparing.

- **Batch IDs with semicolons, not commas.** `/questions/231767;419163;394809` fetches 3 questions in one API call. Using commas returns a 400 error.

- **`search/advanced` includes body text in results; `/search` only searches titles.** Use `search/advanced` with `q=` for full-text search. Use `/search` with `intitle=` for title-only.

- **HTTP errors are raised as exceptions, not returned as JSON.** A bad `site=` param causes `urllib.error.HTTPError: HTTP Error 400: Bad Request` — there's no JSON body accessible from `http_get`. Wrap API calls in try/except.

- **`backoff` in the response envelope must be respected.** If `data.get('backoff')` returns an integer (rare, typically 10–30 seconds), sleep that duration before the next call. Ignoring it will cause throttle errors on subsequent requests.

- **`/info` endpoint wraps stats inside `items[0]`**, not directly in the envelope. Access as `data['items'][0]['total_questions']`.

- **JSON-LD on the HTML page is NOT QAPage schema.** The `<script type="application/ld+json">` block only contains `WebSite` and `Organization` objects in the `@graph` array. There is no `Question`, `Answer`, or `QAPage` type — confirmed on the most-voted Python question (231767). Don't rely on structured data from the HTML page.

- **User timeline `timeline_type` can be `badge`, `question`, `answer`, `comment`, `revision`, `suggested_edit`, `accepted`.** For very old/inactive users, all recent events may be `badge` only.

- **Multi-site support.** Change `site=stackoverflow` to any Stack Exchange site: `site=superuser`, `site=serverfault`, `site=askubuntu`, `site=unix`, `site=datascience`, `site=math`. Same API, same quota pool per IP.

- **`pagesize` max is 100.** Requesting more returns a 400 error. For bulk fetching, loop with `page=` and check `has_more`.
