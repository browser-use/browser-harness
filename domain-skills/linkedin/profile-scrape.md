# LinkedIn — Profile Scrape

Extract a profile's full work history (and other detail sections) from a LinkedIn member profile.

## URL pattern

LinkedIn renders a paginated, fully-expanded view of each profile section at:

```
https://www.linkedin.com/in/<vanity>/details/<section>/
```

Observed sections:

- `experience` — full chronological work history, including roles grouped under a single company
- `education`
- `skills`
- `certifications`
- `projects`
- `volunteering-experiences`

Prefer `/details/<section>/` over scraping the main `/in/<vanity>/` profile page:

- The main profile collapses long sections behind a "Show all N experiences" link and lazy-loads on scroll.
- `/details/experience/` returns the entire list rendered server-side, including roles nested under a parent company entry, in chronological order (newest → oldest).

## Extraction — use `main.innerText`, not selectors

The fastest reliable extraction is to dump `document.querySelector("main").innerText` and parse the resulting plaintext. Each role is separated by blank lines, and the rendered text is already in the order LinkedIn shows the user.

```python
text = js('(() => document.querySelector("main").innerText)()')
```

Output shape (real example, abbreviated):

```
Experience

nCino, Inc.
Full-time · 3 yrs 7 mos

Associate Manager | Solution Architecture
Jun 2025 - Present · 11 mos
London Area, United Kingdom · Hybrid

Senior Implementation Consultant
Dec 2024 - Jun 2025 · 7 mos
...

Salesforce Administrator
Leading Energy Firm · Contract
Mar 2022 - Oct 2022 · 8 mos
...
```

Two card shapes show up in the same list:

1. **Single-role card** — first line is the role title, second line is `<Company> · <EmploymentType>`, third line is the date range.
2. **Multi-role card** — first line is the company, second is `<EmploymentType> · <TotalTenure>`, then one block per role (title / dates / location) until the next company appears.

A simple parser walks the lines and treats any line followed by a `<dates> · <duration>` line as a role; the company is whichever was most recently seen as a standalone heading.

## Trap — DOM `<li>` selectors miss top-level cards

Every plausible "give me the experience cards" selector silently returns only the *nested* roles of the first company:

```js
// WRONG — returns only the 4 nCino sub-roles, not the 5 standalone companies below
document.querySelectorAll("main li")
document.querySelector("main section.artdeco-card ul").children
document.querySelectorAll("main ul > li")
```

Top-level company cards and nested role rows are both `<li>` elements but live in different sibling subtrees. There is no single selector that picks up exactly one entry per role across both shapes — the class names are obfuscated CSS modules and reshuffle frequently.

If you need structured fields beyond what `innerText` gives you, walk `main` element-by-element and group by visual order rather than trying to find one master selector.

## Lazy loading

`/details/experience/` usually renders the full list on first paint, but on long profiles the tail can be virtualized. Before extraction, scroll to the bottom and back to the top:

```python
import time
js("window.scrollTo(0, document.body.scrollHeight)")
time.sleep(1)
js("window.scrollTo(0, 0)")
```

Then re-read `main.innerText`. If the line count changed, re-scroll until stable.

## Auth

This view requires the user to be logged in. The harness attaches to the user's existing Chrome session, so as long as the user is signed in when you navigate, you'll land on the populated page. If you see a login wall instead, stop and ask the user — don't try to authenticate.

## Anti-noise

`main.innerText` on a profile detail page also includes a "Who your viewers also viewed" sidebar at the bottom. Cut everything from that heading onward before parsing experience entries.
