# X (Twitter) — Reading Articles & Tweets

Field-tested 2026-06-30 against an X **Article** (long-form post) using a
**logged-in** browser profile. A *"See what's happening"* login modal still
rendered on top of the page, but the full article text was in the DOM behind
it — the modal blocked clicks, not reads. **Logged-out behavior is
unverified**: X removed guest access years ago, so a truly anonymous browser
may hit a real wall. If you land on a login modal, try the DOM read below
before concluding you need auth — and never type credentials yourself
(auth wall → stop and ask the user).

---

## TL;DR

X **Articles** (long-form posts) live at the **same URL shape as a tweet** —
`https://x.com/{handle}/status/{id}` — there is no `/article/` path. Read the
body via `document.body.innerText`; the login modal that may overlay the page
does not block DOM reads.

The one trap that wastes time: **navigate and extract in the same
`browser-harness -c` invocation.** A second, separate call can re-attach to a
stale or different tab and you read the wrong page (see Gotchas).

---

## Approach (Recommended): innerText read

```python
# ONE invocation — navigate + hydrate + extract together.
new_tab('https://x.com/mvanhorn/status/2070966613994795489')
wait_for_load()
wait(4)                             # JS hydration; article body is lazy
title = js('document.title')        # '<Author> on X: "<headline>" / X'
body  = js('return document.body.innerText')
open('/tmp/x_article.txt', 'w').write(body)
print(title)
print(len(body))                    # full article ~18K chars
```

- `document.title` carries the headline cleanly:
  `Matt Van Horn on X: "Your AI's Memory Is Quietly Making It Dumber (...)" / X`.
  Strip the `<Author> on X: "` prefix and `" / X` suffix to get the title.
  ⚠️ If the title starts with `🟢 ` that is the **harness's own tab marker**
  (added by `new_tab()`), not part of X's title — strip it first.
- `document.body.innerText` contains the whole page. Layout, top → bottom:
  1. **Left-nav chrome** — `Home / Explore / Notifications / ... / Profile / More / Post`
     (when logged in, followed by the account's name/handle).
  2. **Article header** — `Article`, author name + `@handle`, `Subscribe`,
     then the **headline**, then bare engagement counts.
  3. **Article body** — the actual prose (this is what you want).
  4. **Footer** — the timestamp line (`2:24 PM · Jun 27, 2026`), view count,
     reply/repost/like counts, `Relevant people`, `Trending now`, `Terms · Privacy …`.

### Slicing the body out of the chrome

The body sits between the headline and the timestamp line. Cheap, robust cut:

```python
import re
def x_article_body(full_text, headline):
    # start just after the headline's first occurrence in the content area
    i = full_text.find(headline)
    start = full_text.find('\n', i) if i != -1 else 0
    # end at the post timestamp ("H:MM AM/PM · Mon DD, YYYY") — search AFTER
    # start, or a timestamp-shaped string earlier in the page truncates the body
    m = re.search(r'\d{1,2}:\d{2}\s*[AP]M\s*·\s*\w+ \d{1,2}, \d{4}',
                  full_text[start:])
    end = start + m.start() if m else len(full_text)
    return full_text[start:end].strip()
```

Note: a timestamp-shaped string *inside the article prose* would still end the
slice early — if the result looks short vs. `len(full_text)`, fall back to the
footer anchors (`Relevant people` / `Trending now`) as the end marker.

---

## Regular tweets (not Articles)

For an ordinary tweet, the body is in `[data-testid="tweetText"]`:

```python
js('var e=document.querySelectorAll("[data-testid=tweetText]");'
   'var a=[]; for(var i=0;i<e.length;i++){a.push(e[i].innerText)}'
   'return a.join("\\n====\\n")')
```

A thread returns multiple `tweetText` nodes — join them. Scroll to load more
replies (see `interaction-skills/scrolling.md`).

⚠️ **`[data-testid="tweetText"]` is EMPTY for X Articles** — long-form Articles
render in a different container, so this selector returns nothing. For Articles,
use `document.body.innerText` (above), not `tweetText`.

---

## Gotchas (field-tested)

- **Tab drift between calls.** The daemon may attach to a stale or different
  tab on a *separate* `-c` invocation — a follow-up `js('document.title')`
  came back as an unrelated page. Fix: do `new_tab(url)` → `wait_for_load()` →
  `js(...)` **all in one invocation**; `ensure_real_tab()` is the canonical
  remedy when you're already attached to a stale/internal tab.
- **Login modal blocks clicks, not DOM reads.** The *"See what's happening /
  Continue with phone/Google/Apple"* overlay covers the page, but the article
  is fully hydrated underneath and `innerText` reads straight through it.
  (Observed with a logged-in profile; a fully logged-out session is untested.)
- **X Articles share the tweet URL.** `x.com/{handle}/status/{id}` serves both;
  there is no distinct article route. `document.title` tells you which (an
  Article has a prose headline; a tweet has the tweet text).
- **Hydration is lazy.** `wait_for_load()` alone is not enough — add
  `wait(3)`–`wait(4)` or the body comes back short/empty.
- **`js()` returns `None` on a JS error.** If extraction returns `None`, the
  expression threw (often a quoting issue through the shell) — simplify to
  `js('document.body.innerText.length')` to confirm the tab is alive first.
- **Engagement counts are ambiguous in innerText** — bare numbers
  (`35 / 49 / 388 / 114K`) appear right after the headline AND again in the
  footer. Anchor on the timestamp regex for the body end, not on the counts.

---

## What does NOT work / untested

- **No unauthenticated API.** The old public/guest-token JSON endpoints are
  gone; `http_get` on the status URL returns a JS shell, not content. The DOM
  read above is the reliable path.
- **Fully logged-out reading is untested** (see header) — the modal-is-cosmetic
  finding was observed with an authenticated profile.
- **Bookmarks, following feed, DMs** — all require a logged-in session
  (real auth wall, not a cosmetic modal). Out of scope here.
