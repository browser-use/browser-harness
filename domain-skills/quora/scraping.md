# Quora — Data Extraction

`https://www.quora.com` — Q&A platform. One reliable access path: `http_get` with a Chrome UA against question, answer, topic, and profile pages. Quora SSR-renders all public data into `window.ansFrontendGlobals.data.inlineQueryResults` via `.push()` calls. No browser needed for read-only tasks.

## Do this first: pick your access path

| Goal | Best approach | Latency |
|------|--------------|---------|
| Question metadata + first ~3 ranked answers | `http_get` question page + parse push payloads | ~600ms |
| Single answer (full text + upvotes + views) | `http_get` answer permalink | ~400ms |
| Answer count for a question | question page, payload with `answerCount` | same request as above |
| Topic metadata (id, name, follower count) | `http_get` topic page + parse push payloads | ~400ms |
| User profile (name, follower/following, credential) | `http_get` profile page + parse push payloads | ~500ms |
| Keyword search results | NOT available via http_get — server returns no result data | N/A |

**Never use a browser for read-only Quora tasks.** All question, answer, topic, and profile data is server-rendered. Browser is only needed for authenticated actions (posting, upvoting, following) or for getting more than the first ~3 answers on a question page (the rest load via XHR pagination).

---

## UA requirement: Chrome or Firefox — NOT bare Mozilla/5.0

```
bare "Mozilla/5.0"  -> HTTP 403
Googlebot UA        -> HTTP 403
Chrome UA           -> HTTP 200  (confirmed working)
Firefox UA          -> HTTP 200  (confirmed working)
```

Use this header bundle for all requests:

```python
import urllib.request, gzip, json, re

CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)

def quora_get(url):
    """Fetch any public Quora page. Returns HTML string.
    Requires Chrome/Firefox UA — bare Mozilla/5.0 returns 403.
    """
    req = urllib.request.Request(url, headers={
        "User-Agent": CHROME_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        return data.decode()
```

---

## The data format: `ansFrontendGlobals.data.inlineQueryResults`

Quora SSR embeds all page data as a series of `.push("...")` calls inside `<script>` blocks. Each call pushes a JSON-encoded string (with escaped quotes) into `inlineQueryResults`. There are no JSON-LD blocks, no `__NEXT_DATA__`, no React hydration state — only these push calls.

```python
def extract_quora_payloads(html):
    """Extract and parse all push() payloads from a Quora page.
    Returns list of dicts (already decoded from double JSON encoding).
    """
    raw_payloads = re.findall(r'\.push\("((?:[^"\\]|\\.)*)"\)', html)
    results = []
    for raw in raw_payloads:
        try:
            # Two levels of encoding: outer JS string escape, inner JSON
            inner = json.loads('"' + raw + '"')   # decode JS string escaping
            results.append(json.loads(inner))      # decode actual JSON
        except Exception:
            pass
    return results
```

A question page returns **16 payloads**. A profile or topic page returns **3 payloads**. The payloads that matter are identified by their `data` keys, not by position (positions are stable across requests for the same page type, but best to key on content).

---

## Path 1: Question page — metadata + first answers (fastest)

```python
def quora_question(url):
    """
    Scrape a Quora question page.
    Returns:
      question: {qid, id, title, url, slug, topics}
      answers:  list of answer dicts (first ~3 ranked answers only)
      answer_count: total answer count (all answers, not just loaded)
      related_questions: list of question title strings
    Only the first ~3 highest-ranked answers are SSR'd.
    The rest require XHR pagination (browser or session cookies needed).
    """
    html = quora_get(url)
    payloads = extract_quora_payloads(html)

    def spans_to_text(json_str):
        """Quora stores all text as serialized span objects."""
        try:
            doc = json.loads(json_str)
            parts = []
            for sec in doc.get('sections', []):
                for span in sec.get('spans', []):
                    if span.get('text'):
                        parts.append(span['text'])
                parts.append('\n')
            return ''.join(parts).strip()
        except Exception:
            return json_str

    def author_display_name(author_dict):
        names = author_dict.get('names', [])
        if names:
            n = names[0]
            return f"{n.get('givenName', '')} {n.get('familyName', '')}".strip()
        return None

    result = {'question': {}, 'answers': [], 'answer_count': None, 'related_questions': []}

    for payload in payloads:
        data = payload.get('data', payload)

        # Question metadata — keyed by presence of 'qid' inside 'question'
        if 'question' in data and isinstance(data['question'], dict):
            q = data['question']
            if q.get('qid') and not result['question']:
                result['question'] = {
                    'qid':   q.get('qid'),
                    'id':    q.get('id'),
                    'title': spans_to_text(q.get('title', '')),
                    'url':   q.get('url'),
                    'slug':  q.get('slug'),
                    'topics': [t['name'] for t in q.get('navigationTopics', [])],
                }

        # Total answer count — keyed by 'answerCount'
        if 'answerCount' in data:
            result['answer_count'] = data['answerCount']
            rq = (data.get('bottomRelatedQuestionsInfo') or {}).get('relatedQuestions', [])
            result['related_questions'] = [spans_to_text(r['title']) for r in rq]

        # Answer nodes — keyed by node.__typename == 'QuestionAnswerItem2'
        node = data.get('node', {})
        if isinstance(node, dict) and node.get('__typename') == 'QuestionAnswerItem2':
            answer = node.get('answer', {})
            if answer.get('aid'):
                a_author = answer.get('author') or {}
                cred = answer.get('authorCredential') or {}
                result['answers'].append({
                    'aid':              answer.get('aid'),
                    'index':            node.get('index'),
                    'author_name':      author_display_name(a_author),
                    'author_profile':   a_author.get('profileUrl'),
                    'author_uid':       a_author.get('uid'),
                    'author_credential': cred.get('translatedString'),
                    'num_upvotes':      answer.get('numUpvotes'),
                    'num_views':        answer.get('numViews'),
                    'num_shares':       answer.get('numShares'),
                    'num_comments':     answer.get('numDisplayComments'),
                    'creation_time_us': answer.get('creationTime'),  # microseconds since epoch
                    'viewer_has_access': answer.get('viewerHasAccess'),
                    'perma_url':        answer.get('permaUrl'),
                    'text':             spans_to_text(answer.get('content', '{}')),
                })

    return result
```

### Example output

```python
result = quora_question("https://www.quora.com/What-is-the-meaning-of-life")

# result['question']:
# {
#   'qid': 2861,
#   'id': 'UXVlc3Rpb25AMDoyODYx',
#   'title': 'What is the meaning of life?',
#   'url': '/What-is-the-meaning-of-life',
#   'slug': 'What-is-the-meaning-of-life',
#   'topics': ['Philosophy', 'The Big Unanswered Questions', 'Meaning of Life', ...]
# }

# result['answer_count']:  413

# result['answers'][0]:
# {
#   'aid': 2779675,
#   'index': 1,
#   'author_name': 'Shubhankar Srivastava',
#   'author_profile': '/profile/Shubhankar-Srivastava',
#   'author_uid': 5381038,
#   'author_credential': 'works at D. E. Shaw',
#   'num_upvotes': 589,
#   'num_views': 24085,
#   'num_shares': 0,
#   'num_comments': 8,
#   'creation_time_us': 1373364681312036,   # divide by 1e6 for seconds
#   'viewer_has_access': True,
#   'perma_url': '/What-is-the-meaning-of-life/answer/Shubhankar-Srivastava',
#   'text': 'Every morning in Africa, a deer wakes up...'
# }
```

### Convert creation_time_us to datetime

```python
from datetime import datetime, timezone
ts_sec = result['answers'][0]['creation_time_us'] / 1_000_000
dt = datetime.fromtimestamp(ts_sec, tz=timezone.utc)
# datetime(2013, 7, 9, 9, 31, 21, tzinfo=timezone.utc)
```

---

## Path 2: Single answer permalink

Fetching `quora.com/{question-slug}/answer/{author-slug}` directly returns only that one answer's full data in 3 payloads instead of 16. Use this when you already know the answer URL.

```python
def quora_answer(answer_url):
    """
    Fetch a single answer by its permalink.
    URL format: https://www.quora.com/{question-slug}/answer/{author-profile-slug}
    Returns answer dict with: aid, num_upvotes, num_views, text, author info.
    """
    html = quora_get(answer_url)
    payloads = extract_quora_payloads(html)

    for payload in payloads:
        data = payload.get('data', {})
        if 'answer' in data and isinstance(data['answer'], dict):
            a = data['answer']
            author = a.get('author') or {}
            names = author.get('names', [{}])
            n = names[0] if names else {}
            return {
                'aid':          a.get('aid'),
                'num_upvotes':  a.get('numUpvotes'),
                'num_views':    a.get('numViews'),
                'author_name':  f"{n.get('givenName','')} {n.get('familyName','')}".strip(),
                'author_uid':   author.get('uid'),
                'text':         _spans_to_text(a.get('content', '{}')),
            }
    return {}

# Example:
# quora_answer("https://www.quora.com/What-is-the-meaning-of-life/answer/Pararth-Shah")
# -> {'aid': 4734237, 'num_upvotes': 234, 'num_views': 100643, 'author_name': 'Pararth Shah', ...}
```

---

## Path 3: Topic page

```python
def quora_topic(topic_url):
    """
    Fetch topic metadata from a Quora topic page.
    URL format: https://www.quora.com/topic/{topic-slug}
    Returns: tid, name, num_followers, url, is_following, has_leaderboard.
    NOTE: The topic page itself only renders topic metadata, NOT the question feed.
    Question feed requires browser (XHR-loaded via React).
    """
    html = quora_get(topic_url)
    payloads = extract_quora_payloads(html)

    for payload in payloads:
        data = payload.get('data', {})
        if 'topic' in data and isinstance(data['topic'], dict):
            t = data['topic']
            return {
                'tid':           t.get('tid'),
                'id':            t.get('id'),
                'name':          t.get('name'),
                'url':           t.get('url'),
                'num_followers': t.get('numFollowers'),
                'is_following':  t.get('isFollowing'),
                'has_leaderboard': t.get('hasLeaderboard'),
                'photo_url':     t.get('photoUrl'),
                'is_locked':     t.get('isLocked'),
            }
    return {}

# Example:
# quora_topic("https://www.quora.com/topic/Python-programming-language")
# -> {'tid': 13292, 'name': 'Python Programming Language', 'num_followers': 10, ...}
```

---

## Path 4: User profile page

```python
def quora_profile(profile_url):
    """
    Fetch user profile data from https://www.quora.com/profile/{username}
    Returns: uid, name, credential, follower_count, following_count, profile_image_url.
    """
    html = quora_get(profile_url)
    payloads = extract_quora_payloads(html)

    for payload in payloads:
        data = payload.get('data', {})
        if 'user' in data and isinstance(data['user'], dict):
            u = data['user']
            names = u.get('names', [{}])
            n = names[0] if names else {}
            cred = u.get('profileCredential') or {}
            return {
                'uid':             u.get('uid'),
                'id':              u.get('id'),
                'name':            f"{n.get('givenName','')} {n.get('familyName','')}".strip(),
                'profile_url':     u.get('profileUrl'),
                'follower_count':  u.get('followerCount'),
                'following_count': u.get('followingCount'),
                'profile_image':   u.get('profileImageUrl'),
                'credential':      cred.get('experience'),
                'is_verified':     u.get('isVerified'),
                'is_anon':         u.get('isAnon'),
                'is_ai_account':   u.get('isAiAccount'),
                'deactivated':     u.get('deactivated'),
            }
    return {}

# Example:
# quora_profile("https://www.quora.com/profile/Pararth-Shah")
# -> {'uid': 4683832, 'name': 'Pararth Shah', 'follower_count': 5154,
#     'following_count': 83, 'credential': 'Unfinished symphony.', ...}
```

---

## Gotchas

- **Bare Mozilla/5.0 UA returns HTTP 403** — Always use a full Chrome or Firefox UA string. The default `http_get` helper's `"User-Agent": "Mozilla/5.0"` will be blocked. Do not use `http_get` directly; use the `quora_get` wrapper above.

- **Googlebot UA returns HTTP 403** — Quora blocks crawler UAs. Only real browser UAs work.

- **Double JSON encoding** — Each `.push()` argument is a JavaScript string literal containing JSON. To parse: first `json.loads('"' + raw + '"')` to decode the JS string escaping (converts `\\"` to `"`), then `json.loads(inner)` to parse the actual JSON object. Skipping either step produces parse errors.

- **All text fields are serialized span objects** — `question.title`, `answer.content`, `user.descriptionQtextDocument.legacyJson`, etc. are all JSON strings containing a `{"sections": [{"spans": [...]}]}` document, not plain text. Always parse through `spans_to_text()`.

- **Question page only SSR's the first ~3 answers** — The `answers` list in the result will contain at most 3 entries (the top-ranked answers). The `answer_count` field shows the true total (e.g. 413). To get more answers you need browser-based XHR pagination (Quora sends additional answers via GraphQL calls that require session auth in practice).

- **`viewer_has_access: false` still includes full content** — Even when `viewerHasAccess` is `False` (answers from Quora+ Spaces / tribe-only content), the `content` field is still present in the SSR payload and the full text is readable. The flag only controls client-side gating in the browser.

- **`creation_time_us` is microseconds, not milliseconds** — Divide by `1_000_000` (not `1_000`) to get a Unix timestamp in seconds. Confirmed: `1373364681312036 / 1e6 = 1373364681.3` (July 2013).

- **`numFollowers` on topic pages may be 0 even for major topics** — The field reflects the logged-in user's follow state for some topics and appears to undercount. Treat as approximate.

- **Search pages do not yield result data** — `https://www.quora.com/search?q=...` returns 3 payloads with viewer/network info only — no search results in the SSR payload. Search results are loaded client-side and are not accessible via http_get.

- **Profile pages do not include the user's answer list** — The profile page SSR payload returns user metadata only. The list of a user's answers is loaded via XHR pagination. To get answers for a specific question, use the question URL directly.

- **IDs are base64-encoded Relay global IDs** — `id: "UXVlc3Rpb25AMDoyODYx"` decodes to `"Question@0:2861"`. The numeric `qid`/`uid`/`aid`/`tid` fields are more useful for constructing URLs and deduplication. Use `qid` and `aid` as stable identifiers.

- **`permaUrl` may be an absolute URL for Spaces answers** — Most answers have `permaUrl: "/Question-slug/answer/Author-Name"` (relative). Answers posted in a Quora Space have a full absolute URL like `"https://spacename.quora.com/Question-slug"`. Handle both forms.

- **No public REST or GraphQL API** — Quora's internal `graphql/gql_para_POST` endpoint requires a valid `quora-formkey` header derived from the session, making it inaccessible without a real authenticated session. The SSR push-payload approach is the only reliable unauthenticated path.
