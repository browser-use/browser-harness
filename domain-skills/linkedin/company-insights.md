# LinkedIn — exact company headcount from the Insights tab

Field-tested against linkedin.com on 2026-08-28, signed in with a free (non-Premium) account.

The company **header** only ever shows a self-reported bucket — `201-500 employees`. The **exact**
headcount lives on the company's Insights tab. It is not Premium-walled on a free account.

## The trap: the number lazy-hydrates, and the stale value looks real

This is the whole reason this file exists. Read the Insights tab as soon as it opens and you get a
number that is **wrong, plausible, and silent** — nothing throws, nothing looks stale.

For `/company/langchain/`:

| when you read | "Functional distribution" says |
|---|---|
| immediately after the tab opens | `133` |
| after scrolling to the bottom | `423`  ← correct |

Same DOM node, same selector. The first render is a partial-data placeholder that is replaced once
the lazy sections below the fold hydrate. `wait_for_load()` does **not** cover this — the document is
complete long before the figure settles.

**Always scroll the whole page before extracting**, then read the value under the `Total employee
count` heading (see below), not the first number you can match.

## Route: navigate directly. Do not click the tab.

`https://www.linkedin.com/company/<slug>/insights/` loads fine. Verified across companies, with and
without the trailing slash — no redirect.

```python
new_tab("https://www.linkedin.com/company/langchain/insights/")
wait_for_load()
wait(6)

for _ in range(12):             # force the lazy sections to render
    scroll(0, 900)
    wait(0.6)
wait(2.5)                       # let the figures settle after the last scroll
```

**Clicking the `Insights` nav link is the fragile path**, and it's the one that eventually breaks.
The anchor is in the DOM and `visible` before its handler is wired, so the click lands, does
nothing, and leaves you scraping the overview page — with the URL unchanged and no error. Three
consecutive clicks on a present, visible anchor failed this way on `/company/mem0/`.

Verify you landed: the URL should end in `/insights/`.

## Extraction anchors

Page order, top to bottom, in `main`'s innerText:

```
Total employee count
Based on LinkedIn data.
423     71%                     <- the exact headcount
total employees  6m growth  1y growth  2y growth
...
Functional distribution
423
Function | Number of employees | Percentage of total headcount | 6 month growth | 1 year growth
Engineering | 161 | 38 | 96%
```

Anchor on **`Total employee count`** — it is the labelled authoritative figure:

```python
m = re.search(r"Total employee count[\s\S]{0,120}?([\d,]{2,})", txt, re.I)
```

Note the value sits *before* the literal `total employees` header row — that row is the growth
table's header, not the figure. Don't anchor on it.

`Functional distribution` reports the same number once hydrated, but it's a weaker anchor: it's a
chart label, and it's the node that shows the placeholder value if you read too early.

## Free tripwire: range-check against the header

The `201-500 employees` bucket in the company header is **server-rendered above the fold and never
hydrates late**. Capture it before leaving the company home and assert the Insights figure falls
inside it. Costs nothing and turns the silent lazy-hydration failure into a loud one — `133` is
outside `201-500`, so the bad read raises instead of being recorded as fact.

```python
lo, hi = map(int, re.search(r"([\d,]+)\s*-\s*([\d,]+)\s+employees", home).groups())
assert lo <= n <= hi, f"{n} outside {lo}-{hi} — read before hydration finished"
```

## Trap: profiles often have no Experience section

LinkedIn serves a server-driven layout in which many profiles render **no Experience section at
all**. Do not derive someone's employer from their profile page.

`a[href*="/company/"]` is actively misleading there — the only company links present come from
activity posts and ads. On `/in/christian-bromann` it returns `programmier-bar`, a podcast, rather
than LangChain. If you have the company name from another source, trust that instead.

## Company name → slug

The obvious slug usually resolves, once you strip parenthetical suffixes:

```python
slug = re.sub(r"\(.*?\)", "", name).strip().lower()
slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
```

`Mem0 (YC S24)` → `mem0` ✓. Verify by loading it and checking the title isn't `Page not found`;
fall back to `/search/results/companies/?keywords=<name>` when it misses.

## Auth note: Google cookies rotate, LinkedIn's don't

If you drive LinkedIn via exported-and-injected Chrome cookies, LinkedIn's session survives for
days. Worth knowing if the same run also touches Google: Google rotates `__Secure-1PSIDTS` within
hours, so a shared cookie export that still works fine on LinkedIn will already be dead on Google —
and Google fails by rendering an account chooser listing every account as "Signed out" at HTTP 200,
which reads as a working page.
