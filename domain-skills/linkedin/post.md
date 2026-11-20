# LinkedIn — publishing & scheduling your OWN posts

Posting Phil's own text posts to his own feed, and scheduling them with
LinkedIn's **native** scheduler. Used by the LinkedIn post-queue automation
(`~/Projects/linkedin-content/queue/queue.json`).

**This is your OWN feed.** Distinct from `activity.md`, which is read-only
scraping of *other people's* profiles for outreach hooks. The read-only ToS
rule (no liking/following/messaging from someone else's profile) is about
acting on third parties. Publishing your own content to your own account is a
normal account action. Still: keep cadence human (3x/week, mornings), never
auto-fire without a veto window at first.

## The one hard gotcha: the composer is an IFRAME

The "Start a post" composer body — the editor, the toolbar, the schedule
clock, the Post/Schedule button — renders **inside an iframe**. Top-document
`document.querySelector` sees `[role=dialog]` wrappers but **zero** of the
controls (validated 2026-06-19: 4 dialogs, 0 editors, 0 buttons found via DOM).

So **do not drive this with CSS selectors.** Drive it with coordinate clicks +
keyboard + screenshots — which pass through the iframe at the compositor level
(the harness's whole design). Re-screenshot after every action to verify state.
Because positions shift with viewport, **locate each control from a fresh
screenshot at post time** rather than hardcoding pixels. Reference window is
1920x992; the composer is a centered modal.

The ONE stable top-document anchor (outside the iframe) is the trigger button:
```python
# "Start a post" — findable by aria/text in the top document
js(r"""(() => { for (const b of document.querySelectorAll('button,[role=button]')) {
  const a=(b.getAttribute('aria-label')||'')+'|'+(b.textContent||'').trim();
  if(/start a post/i.test(a) && b.offsetParent){const r=b.getBoundingClientRect();
  return {x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)};}} return null; })()""")
# ~ (940, 111) at 1920x992. Click it to open the composer.
```

## Validated flow — schedule a post (2026-06-19)

1. **Open composer.** Click the "Start a post" trigger (anchor above). Wait ~2s.
   Screenshot to confirm the modal ("Share your thoughts...") is open.
2. **Type the post.** Click the editor body (center of the modal, "Share your
   thoughts..." placeholder), then `type_text(post)`. Newlines in the text
   become line breaks. Screenshot — confirm the text and that the char counter
   moved off 0.
3. **Open the scheduler.** Click the **clock icon** immediately to the LEFT of
   the Post button, bottom-right of the modal. A **"Schedule post"** dialog opens.
4. **Set date + time.** The dialog has:
   - a **Date** field formatted `M/D/YYYY` (e.g. `6/23/2026`),
   - a **Time** dropdown (e.g. `10:00 AM`, 30-min granularity, local tz —
     it states "...Central Daylight Time, based on your location"),
   - a "View all scheduled posts →" link, and **Back / Next** buttons.
   Set the date and a morning time. LinkedIn requires the time be in the future
   (schedule >= ~1hr out for the veto window).
5. **Next.** Click **Next** — returns to the composer; the **Post** button is
   now a **Schedule** button.
6. **Schedule.** Click **Schedule**. The post is now in LinkedIn's server-side
   scheduled queue — **it fires even if this Mac is asleep.**
7. **Verify.** Reopen composer → clock → "View all scheduled posts" to confirm
   it's queued. Or just screenshot the success toast.

To **abort/map without publishing:** opening the schedule dialog does NOT
publish. Press `Escape` twice (schedule dialog, then composer). An empty editor
closes with no discard prompt.

## Schedule-with-veto pattern (the automation's default "notify" mode)

Goal: a human can stop a bad post, but doing nothing still ships it.

- On post morning, schedule the next `pending` queue item ~1 hour out (steps
  above), then send Phil an iMessage preview: *"Scheduling for 9:30am: <first
  line>… reply STOP to cancel."* Mark the item `queued` in queue.json.
- If Phil replies STOP within the window, reopen "View all scheduled posts" and
  delete that scheduled post; mark it `skipped`.
- Otherwise LinkedIn fires it natively. Mark `posted`.

**Graduate to full auto:** set `queue.json -> _meta.mode = "auto"` to skip the
iMessage/veto step entirely. Circuit breaker for auto mode: the runner checks
`_meta.paused` (a one-line kill switch) before scheduling anything.

## Why native scheduler over "post immediately"

Scheduling ~1hr out (vs posting on the spot) gives the veto window AND means a
mid-run harness crash can't lose or double-post the content — once it's in
LinkedIn's queue, it's safe. Mac only needs to be awake at *scheduling* time,
not at *post* time.

## Runner shape (cheap, model-in-the-loop, DOM-change resilient)

The trigger (Mac launchd on Tue/Wed/Thu, or a cloud routine) invokes a small
Claude run that *follows this file* via the harness: it screenshots, clicks, and
verifies adaptively. That absorbs LinkedIn's ~quarterly DOM/layout churn without
a code change — no brittle hardcoded coordinates to maintain. The expensive,
fragile alternative (a pure pixel-coordinate Python script) is deliberately NOT
used here.

## When LinkedIn breaks this

Symptoms: the "Start a post" anchor returns null (renamed aria), or the modal
layout moves so the clock/Post click misses. Fix: re-run the map (open composer,
screenshot, relocate controls), update the "validated" date above. The iframe
fact and the step order are stable; only positions drift.
