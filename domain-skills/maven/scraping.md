# Maven — cohort-based course marketplace (maven.com)

Field-tested 2026-09-02 from a Browser Use cloud browser. `http_get` on maven.com returns 403; use the browser.

## URL patterns

| Goal | URL | Note |
|---|---|---|
| Category listing | `https://maven.com/courses/<category>` e.g. `/courses/ai`, `/courses/leadership` | |
| Audience × topic listing | `https://maven.com/courses/for-leaders/ai`, `/courses/for-leaders/agentic-ai`, `/courses/for-product-managers/agentic-ai`, `/courses/for-engineers/agentic-ai`, `/courses/for-marketers/agentic-ai` | best for "courses aimed at X" |
| Topic × subtopic | `https://maven.com/courses/ai/agentic-ai` | |
| Search | `https://maven.com/courses?search=...` | **ignored** — renders the default Trending list. Use category URLs instead. |
| Course page | `https://maven.com/<instructor-slug>/<course-slug>` | rating, review count, price, cohort dates, syllabus, testimonials all on one page |
| Maven for Business | `https://maven.com/business` | how they sell seats to companies |

## Listing extraction
Cards are `<a href="/...">` elements whose text contains the duration and start date (`"6 weeks · Starts Sep 5"`). Lazy-loaded — scroll first:

```python
navigate("https://maven.com/courses/for-leaders/agentic-ai"); wait_for_load(); wait(4)
for _ in range(6): scroll(700, 400, dy=1500); wait(0.6)
cards = json.loads(js("""JSON.stringify([...document.querySelectorAll('a[href^="/"]')]
  .map(a=>({t:a.innerText.replace(/\\n+/g,' | ').slice(0,220),h:a.href}))
  .filter(x=>/\\$|weeks|Starts/i.test(x.t)))"""))
```
Card text order: `title | duration | · | Starts <date> | instructor(s) | rank`. Prices are on the course page, not the card.

## Gotchas
- The nav's "AI / Product / Engineering / …" links are the category URLs above; "Cohort-based Courses" is the page title on every listing, so don't use `document.title` to verify which listing you're on — check `location.href`.
- Full-page screenshots of listings are ~6k px tall and 1–2 MB; the harness handles it but allow ~20 s per capture on the cloud browser.
- Two harness scripts driving the same `BU_NAME` daemon concurrently will fight over the single tab — run captures sequentially.
