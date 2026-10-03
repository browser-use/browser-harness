# humanbenchmark.com — product scope scraping

Field-tested 2026-07-24.

## Full test catalog lives on the homepage, not a `/tests` index

There is no `/tests` listing route — `https://humanbenchmark.com/tests` is a 404. The complete list of tests is rendered as cards directly on the homepage (`https://humanbenchmark.com/`), no pagination, no lazy-load/infinite-scroll (a `querySelectorAll` scan on first paint already captures all cards — scrolling isn't required).

Extraction (real DOM, works via `js()`):

```js
Array.from(document.querySelectorAll("a")).filter(a => a.querySelector("h3, h2")).map(a => ({
  title: a.querySelector("h3, h2").innerText.trim(),
  href: a.href,
  desc: a.querySelector("p") ? a.querySelector("p").innerText.trim() : "",
}))
```

As of this scrape, Human Benchmark ships exactly **8 tests**: Reaction Time (`/tests/reactiontime`), Sequence Memory (`/tests/sequence`), Aim Trainer (`/tests/aim`), Number Memory (`/tests/number-memory`), Verbal Memory (`/tests/verbal-memory`), Chimp Test (`/tests/chimp`), Visual Memory (`/tests/memory`), Typing (`/tests/typing`). URL slugs are inconsistent (`reactiontime` no hyphen vs `number-memory` hyphenated) — don't guess slugs, read them off the cards.

Notably absent (useful for competitive-gap analysis): no Schulte Table, no Visual Search test, no Multiple Object Tracking (MOT) test — these are classic cognitive-science paradigms Human Benchmark has never shipped, despite otherwise covering most "attention/reflex" benchmark territory.

## Site is a fast static-ish SPA

`wait_for_load()` after `new_tab()` is sufficient — no extra sleep needed for the homepage card grid to be queryable.
