# LinkedIn — recent activity feed

Reading the activity feed of a candidate's profile (posts, comments,
reposts) for outreach hook generation. Used by PhilOS's
`scripts/routines/linkedin_activity.py` to feed `draft_outreach`'s
hook cascade.

**Read-only.** Never use harness sessions to send messages, like, or
follow from someone else's profile — that violates LinkedIn ToS and
PhilOS's `PHILOS_LINKEDIN_READ_ONLY` kill switch is the second line of
defense.

## URL pattern

```
https://www.linkedin.com/in/<handle>/recent-activity/all/
```

Variants (not used by PhilOS yet but documented for future):
- `/recent-activity/posts/`     — posts only
- `/recent-activity/comments/`  — comments only
- `/recent-activity/reactions/` — reactions only

The `all/` view is enough for most outreach hooks since recent comments
often produce the strongest "non-fakeable" signal (someone defending a
position, asking a question, contributing to a discussion).

## Required wait

`wait_for_load()` returns before the SPA finishes rendering activity
items. Scroll-driven lazy-load is the trigger. Reliable sequence:

```python
new_tab(URL)
wait_for_load()
for _ in range(3):
    js("window.scrollBy(0, 800)")
    time.sleep(1.0)
# By now ~10 items are rendered. More scrolls give marginal returns;
# the freshest signals are at the top anyway.
```

## Stable selectors (validated 2026-04-27)

| Selector | Count observed | What it gets you |
|---|---|---|
| `div[data-urn^="urn:li:activity:"]` | 10 | **Canonical item wrapper.** Use this. |
| `div.feed-shared-update-v2`         | 10 | Parallel selector; same set. Either works. |
| `.update-components-text`           | 11 | Post body text (the thing you want to hook on). |
| `.update-components-actor__sub-description` | 11 | Timestamp + visibility (e.g. "4d • Edited • Public"). |
| `time[datetime]`                    | 27 (multi/card) | ISO datetime when present. |
| `a[href*="/feed/update/"]`          | 1 (sparse) | "View post" link — **don't rely on this**, build from data-urn. |

The `data-urn` is the most reliable identifier: every item carries it,
and you can build a public post URL from it:

```js
const urn = item.getAttribute("data-urn");          // "urn:li:activity:7453131213281730560"
const url = `https://www.linkedin.com/feed/update/${urn}/`;
```

## Selectors that don't work (do not use)

These look reasonable but match zero elements on the current LinkedIn
DOM (2026-04-27). They were valid in older versions; LinkedIn renamed
or restructured them.

| Selector | Why it fails |
|---|---|
| `article.feed-shared-update-v2`     | Items are `<div>`, not `<article>`. The 2 `<article>` elements on the page are non-feed (profile header). |
| `.feed-shared-text`                 | Old class — renamed to `.update-components-text`. |
| `.update-components-actor`          | Base class doesn't render; only the `__sub-description` modifier matches anything. |
| `a[href*="/posts/"]`                | LinkedIn uses `/feed/update/` URLs now, not `/posts/`. |

## Kind detection (post vs comment vs reaction vs share)

Heuristic via `.update-components-header` inner text. When present,
it contains phrasing like "Addy commented on", "Addy reposted",
"Addy liked". When ABSENT (the most common case for original posts),
treat as `kind: "post"`.

The hook quality doesn't materially depend on getting kind right —
the model uses `content_text` regardless — so a misclassified comment
labeled "post" is fine. `linkedin_activity.py` falls back to `"post"`
on ambiguity.

## Empty / login-redirect detection

If `data-urn` matches zero items after the scroll sequence, you're
probably hitting the auth wall (Phil's session expired) or the
candidate has no public activity. The harness script returns `[]` and
PhilOS treats empty scrapes silently — no error, no critique, just
"this candidate has no activity hook available, fall back to
work_history."

## Trap: Activity tab on `/talent/profile/`

LinkedIn Recruiter (`/talent/profile/...`) has its own activity surface
that uses different selectors. PhilOS only scrapes the public
(`/in/<handle>/recent-activity/...`) view. Don't substitute the
Recruiter URL — selectors above won't match.

## When LinkedIn breaks this

LinkedIn renames CSS classes ~quarterly. Symptoms when this doc goes
stale:
- `linkedin_activity.py` cron writes empty rows night after night.
- `reflect_health` may flag draft_outreach as stale (no activity hooks
  feeding the cascade).
- `LearningCard.tsx` shows zero accepted/rejected.

Re-run the probe in `scripts/routines/linkedin_activity.py`'s docstring
(or the inline `extract` JS) to refresh counts. Update this doc with
the new selectors and the date of validation.
