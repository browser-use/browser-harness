# LinkedIn — searching first-degree connections + sending personalized messages

Field-tested against a logged-in Premium account on 2026-04-20.
**Requires:** Browser Harness attached to a real Chrome that is signed into
LinkedIn. Logged-out views redirect to `/login` and return no search results
or profile content.

## What this skill is for

1. Filter your first-degree connections by title and institution (e.g.
   "Professors at a university")
2. Harvest each target's research profile (headline, About, Experience) to
   craft a genuine personalized opener
3. Send a templated + personalized direct message to each, with pacing that
   stays under LinkedIn's "obvious automation" radar

It is **NOT** for: connection requests to non-connections, InMail to 2nd/3rd
degree, Sales Navigator workflows, bulk-connecting, or anything that has to
run headless (the account must be the user's real session).

## URL patterns

| What | URL |
|------|-----|
| People search (first-degree only, by keyword) | `https://www.linkedin.com/search/results/people/?network=%5B%22F%22%5D&keywords={Q}&origin=FACETED_SEARCH&page={N}` |
| People search — direct title filter | `&titleFreeText={Q}` is silently dropped when set via URL. **Use `keywords={Q}` instead.** |
| Connections index | `https://www.linkedin.com/mynetwork/invite-connect/connections/` |
| Profile | `https://www.linkedin.com/in/{vanity-or-hash}/` |
| Messaging compose (direct, by profile) | Click the profile's Message button — there is no reliable `?recipient=` URL for 1st-degree that avoids the InMail surface |

`keywords=` searches title + name + company — not title-only. That's fine for
this use case because a first-degree professor will match either way, but
expect false positives (e.g. someone whose *company name* contains "Professor").
Filter again in Python on the title line.

## DOM anchors (verified 2026-04-20)

LinkedIn's React components use hashed class names that rotate frequently.
Anchor on `aria-label`, stable IDs (`#about`, `#experience`), and `role`
attributes instead.

### Search-results page (`/search/results/people/`)

| Anchor | Selector | Notes |
|--------|----------|-------|
| Per-card anchor | `a[aria-label^="Send a message to "]` | The *Message* link on each result card. Its aria-label is always `Send a message to {Full Name}`. Use this as the card anchor. |
| Card container | Walk up from the message link until the smallest ancestor contains exactly one `a[href*="/in/"]` | There is no stable card-level class. The walk-up is reliable. |
| Profile URL | `card.querySelector('a[href*="/in/"]')?.href.split('?')[0]` | Strip query string for dedup. |
| Name | `(card.innerText||'').split('\n')[0]` is the name (first visible line in the card). |
| Title/company line | First line after the connection-degree marker (`• 1st`). Sometimes a more precise line appears as `Current: ...`. Prefer `Current:` when present. |

### Profile page (`/in/{id}/`)

| Anchor | Selector | Notes |
|--------|----------|-------|
| Profile action Message button | `button` with `aria-label^="Message "` AND `getBoundingClientRect().y > 100` | There are typically 2–4 matches: sticky-header (y ≈ 11), main action (y ≈ 500, the target), and tiny "Message" anchors in the right-column "More profiles for you" rail. Filter by `y > 100` to drop the sticky header. |
| About section | `document.querySelector('#about')?.parentElement` | Reading `innerText` on the parent of `#about` gives the full About copy. The anchor is only present if the user filled About. |
| Experience section | `document.querySelector('#experience')?.parentElement` | Same pattern. Always present for real users. Contains all role bullets with institution + duration. |
| Headline | `.text-body-medium.break-words` or `div.text-body-medium` | Short tagline under the name. |

**Doubling:** Many LinkedIn sections have an extra visually-hidden duplicate of
the heading text (accessibility), so `section.innerText` returns strings like
`"About\nAbout\nThe Temenoff Lab..."`. Strip a leading `/^About\s*About\s*/i`
(or `Experience\s*Experience\s*`) before using the text.

### Message composer (bottom-right overlay, opened after clicking Message)

| Anchor | Selector | Notes |
|--------|----------|-------|
| Text input | `[contenteditable="true"]` | Only one visible at a time when the composer is open. Has `aria-label="Write a message…"`. |
| Send button | `button` whose `innerText === "Send"` | Starts disabled (`btn.disabled === true`) until the textbox has content. Re-query after typing — the button element is sometimes re-rendered. |
| Close the compose popup | `button[aria-label^="Close "]` (last visible one) | Useful before moving to the next candidate to avoid stale composer state. |

## The CDP-vs-React click gotcha

**`Input.dispatchMouseEvent` (i.e. `click(x, y)` in helpers) does NOT reliably
fire LinkedIn's React click handlers on every profile's Message button.**

Reproduced on 2026-04-20: the button was correctly positioned, visible,
not covered by an overlay; `document.elementFromPoint(x,y)` returned the
right `<span>Message</span>` inside the right `<button aria-label="Message
{First}">`; yet the compose popup never opened. Calling `btn.click()` via JS
on the exact same button *did* open the composer.

Seen on `/in/brad-l-pentelute-.../`, `/in/laurie-a-boyer-.../`, `/in/ed-crawley.../`
and several others. Worked via coordinate click on `/in/johnna-temenoff-.../`.
The pattern is inconsistent enough that you should treat coordinate clicks on
LinkedIn action buttons as unreliable and use JS `.click()` as the default.

```python
# RELIABLE — JS click via the button's own React-attached handler
js("""
(first) => {
  const esc = first.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&');
  const re = new RegExp('^Message ' + esc, 'i');
  const btns = [...document.querySelectorAll('button')];
  const vh = window.innerHeight;
  const cands = btns.filter(b => {
    if (!re.test(b.getAttribute('aria-label') || '')) return false;
    const r = b.getBoundingClientRect();
    return r.y > 100 && r.width > 20 && r.height > 10 && r.y < vh;
  });
  if (!cands.length) return 'no-match';
  cands.sort((a,b) => a.getBoundingClientRect().y - b.getBoundingClientRect().y);
  cands[0].click();
  return 'ok';
}""" + f"({json.dumps(first_name)})")
```

Coordinate clicks are still fine for the composer textbox (to anchor the
caret) and for the Send button, but *always* have a JS-`.click()` fallback.

## Pagination + lazy loading

Search results show 10 cards per page. To collect across pages, iterate
`&page=1,2,...` and watch for `<10` cards returned as the stop signal (there
is no reliable "last page" indicator in the DOM).

Cards load lazily as you scroll — after `goto` and `wait_for_load()`,
`scroll` ~4 times with 0.3s waits to force all 10 to hydrate:

```python
goto(url); wait_for_load(); wait(2)
for _ in range(4):
    js("window.scrollBy(0, 900)")
    wait(0.3)
```

Same pattern on profile pages, except you need to visit the bottom (About
and Experience are below the fold and virtualized). Scroll in multiple steps
down and back to the top:

```python
for y in (600, 1200, 1800, 2400, 3000, 2000, 1000, 0):
    js(f"window.scrollTo(0, {y})")
    wait(0.35)
```

## Filtering for "PI or Professor at a higher-ed institution"

`keywords=Professor` + `keywords=Principal Investigator` catches most
candidates. Dedupe by stripped profile URL. Then filter in Python on the
title line (headline or the `Current:` line from the search card):

```python
ACADEMIC_HINTS = [
    # English
    "University","College","Polytechnic","Institute of Technology",
    "School of Medicine","School of Engineering","Medical School",
    "Imperial College","NYU","UCL",
    # Common acronyms for top tech schools (expand as needed)
    "MIT","Caltech","EPFL","ETH","KTH","KAUST","IIT ","IISc",
    # Non-English
    "Universität","Universidad","Universidade","Université","Università",
    "Universitet","Universitas","Uniwersytet","École","Fachhochschule",
]
TITLE_HINTS = [
    r"\bProfessor\b", r"\bAssistant Professor\b", r"\bAssociate Professor\b",
    r"\bFull Professor\b", r"\bDistinguished Professor\b",
    r"\bEndowed Professor\b", r"\bChair(?:ed)? Professor\b",
    r"\bProfessor of\b", r"\bPrincipal Investigator\b",
]
EXCLUDE_TITLES = [
    # Strict PI/Faculty interpretation
    r"\bProfessor of Practice\b", r"\bEmerit(?:us|a)\b",
    r"\bAdjunct\b", r"\bVisiting\b", r"\bTeaching Professor\b",
    r"\bLecturer\b", r"\bPostdoc", r"\bResearch Scientist\b",
]
```

**Gap in `ACADEMIC_HINTS`:** strict keyword matching misses legit profiles
where the institution shows only as an acronym or short name — e.g.
`Georgia Tech` (vs. `Georgia Institute of Technology`), `UC Berkeley`,
`UC Davis`, `UVA`, `MD Anderson`. If you want those in scope, add them
explicitly or resolve each short name via a second pass (open the profile
and inspect the Experience section's institution line).

## Research-aware personalization — what the profile actually gives you

Per-candidate signal quality varies enormously:

| Signal | Availability | Quality |
|--------|--------------|---------|
| Headline | Always | Low–medium. "Professor at X" is not specific. |
| About | ~50% | Usually *the* best signal. Lab focus, research program, themes, even lab URL. |
| Experience (first role) | Always | Always has institution + duration + sometimes a one-line summary of the role. |
| Featured posts | Variable | Often auto-generated ("reposted X"). Rarely worth reading. |
| Publications | ~10% | Usually just a link to Google Scholar. |

Practical recipe: use About if present; otherwise combine the Experience
section's first role summary with the institution from the headline. The
goal is one short honest sentence that shows you read their profile.

```
Hook template (works for most):
  "Given {their work on / the {Lab}'s work on / your work leading {Center}} 
   on {research area} at {institution}"

Bad hooks:
  "I admire your amazing research." — generic, reads as spam.
  "Your {exact paper title}" — too narrow; wrong if you pick the wrong one.
  "Given your work at MIT" — no specificity; unsafe default.

Good hooks:
  "Given your work on peptide chemistry and therapeutic delivery at MIT"
  "Given the Folch Lab's work on microfluidics and making cancer drug
   testing more affordable at UW"
  "Given your work at the Koch Institute on intestinal stem cells,
   regeneration, and cancer"
```

## Sending a message (end-to-end)

```python
# first: recipient's first name (from profile h1)
# hook:  one research-aware sentence, no trailing period
goto(profile_url); wait_for_load(); wait(2.5)
js("window.scrollTo(0,0)"); wait(1.2)

# 1) Open the composer via JS click (NOT coordinate click — see gotcha)
ok = js(f"""(first => {{
  const esc = first.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&');
  const re = new RegExp('^Message ' + esc, 'i');
  const b = [...document.querySelectorAll('button')]
    .filter(b => re.test(b.getAttribute('aria-label')||''))
    .filter(b => b.getBoundingClientRect().y > 100)
    .sort((a,b) => a.getBoundingClientRect().y - b.getBoundingClientRect().y)[0];
  if (!b) return 'no-match';
  b.click(); return 'ok';
}})({json.dumps(first)})""")

# 2) Wait for the compose popup — poll, up to ~7s
for _ in range(10):
    wait(0.7)
    r = js("""(() => {
      const box = document.querySelector('[contenteditable="true"]');
      if (!box) return null;
      const r = box.getBoundingClientRect();
      if (r.width < 50 || r.height < 50) return null;
      box.focus();
      return JSON.stringify({x:r.x+r.width/2, y:r.y+r.height/2});
    })()""")
    if r: break
composer = json.loads(r)

# 3) Anchor the caret with a coordinate click, then insert text + Shift+Enter
#    for newlines. Plain Enter can submit in some LinkedIn composers, so use
#    modifiers=8 (Shift) for every line break inside the body.
click(int(composer["x"]), int(composer["y"])); wait(0.6)
for i, part in enumerate(msg.split("\n")):
    if part: type_text(part)
    if i < msg.count("\n"):  # not last
        press_key("Enter", modifiers=8)
wait(1.4)

# 4) Click Send via JS (same rationale as step 1)
for _ in range(6):
    r = js("""(() => {
      const ok = [...document.querySelectorAll('button')]
        .filter(b => /^\\s*Send\\s*$/i.test((b.innerText||'').trim()))
        .filter(b => !b.disabled)[0];
      if (!ok) return 'wait';
      ok.click(); return 'ok';
    })()""")
    if r == "ok": break
    wait(0.8)
wait(4.0)

# 5) Verify — the sent message appears in the thread
frag = f"{hook}, may I interest you"
sent_ok = bool(js(f"(f => (document.body.innerText||'').includes(f))({json.dumps(frag)})"))
```

### Why Shift+Enter, not plain Enter

LinkedIn's composer is a contenteditable, not a form. Plain Enter produces
a new paragraph in the visible composer but in some UI states (threaded
conversations with quick-reply affordances) it can also trigger submit.
`Shift+Enter` reliably inserts a line break in the composed draft. Use it
for every newline in the body; the only Enter you want is the one that
sends (and we use a Send-button click for that, not keyboard).

### Verifying a send

The composer does NOT give you a toast on success. Reliable signals:
1. The thread panel now contains a new bubble whose text includes your
   hook fragment (the cheapest check).
2. The "Write a message…" textbox is cleared and re-rendered.
3. The URL may add a `?replyToHiringEmail=` or similar hash on some surfaces.

Check #1 with a plain `document.body.innerText.includes(...)` — the thread
is in the overlay panel, not a separate frame, so it's visible from the
page's document.

## Rate-limit discipline

LinkedIn's anti-abuse heuristics watch for:

- Many outbound messages in a short window (shadow-throttle starts around
  ~20–30 messages/hour for direct-connection DMs; lower if none are replied to)
- Opening many profiles in rapid succession (a single ~50-profile binge is
  the kind of pattern that triggers "Let's verify it's you" checkpoints)
- Many failed/no-op clicks (scraping signal)

Safe defaults for first-degree messaging campaigns:

- **≥45s between message sends**, randomized to 55–85s
- **≥3s between profile opens** during a harvest pass
- **≤20 messages per session**, ≤50 per day
- **Drop to 0 immediately** if a profile redirects to `/authwall` or the
  nav shows a verification banner
- Do the harvest pass and the send pass on the *same day* (profile views
  without a follow-up message are fine; many views + many messages to
  different people within hours is the pattern that gets flagged)

Symptoms of over-pacing: Message button clicks stop opening the composer
(but the button still looks fine), profile loads start showing stale cached
content, the header nav shows a "Verify you're human" badge. **Stop and
let the user resolve** — never auto-dismiss a LinkedIn challenge.

## Resumable, checkpointed sending

Always checkpoint sent/failed to disk on every iteration so a crash or a
kill mid-batch doesn't lose progress:

```python
SENT_PATH   = "/tmp/li_sent.json"
FAILED_PATH = "/tmp/li_failed.json"

sent   = json.loads(open(SENT_PATH).read())   if os.path.exists(SENT_PATH)   else {}
failed = json.loads(open(FAILED_PATH).read()) if os.path.exists(FAILED_PATH) else {}

for cand in candidates:
    if cand["href"] in sent or cand["href"] in failed:
        continue
    res = send_to(cand)   # returns {"ok": bool, "stage": ...}
    target = sent if res["ok"] else failed
    target[cand["href"]] = {"name": cand["name"], **res, "t": time.strftime("%H:%M:%S")}
    open(SENT_PATH if res["ok"] else FAILED_PATH, "w").write(json.dumps(target, indent=2))
    if res["ok"] and idx < last:
        time.sleep(random.uniform(55, 85))
```

Re-running the script is idempotent — it skips already-sent and
already-failed hrefs. If you want to retry failures, delete
`/tmp/li_failed.json` first.

## Gotchas log

- **2026-04-20:** `Input.dispatchMouseEvent` is inconsistent on LinkedIn's
  React buttons (Message, Send). Use JS `.click()` as the default.
- **2026-04-20:** `titleFreeText=` URL parameter on people search is silently
  dropped — the UI supports title filtering but only via interactive
  filter modal, not via the URL. Use `keywords=` instead.
- **2026-04-20:** Section headers double their text (accessibility). Strip
  `/^About\s*About\s*/` and `/^Experience\s*Experience\s*/` before parsing.
- **2026-04-20:** The `.text-body-medium.break-words` headline selector is
  the most stable non-h1 anchor on a profile. Classes like `_06f6a844`
  rotate — don't hard-code them.
- **Ambient "scope" trap when scripting via `browser-harness <<'PY'`:**
  `run.py` does `exec(sys.stdin.read())`. Module-level `import` statements
  and top-level constants **don't** become globals of any `def`s you
  declare — function bodies cannot see `import random`, `import re`, or
  constants like `FIND_BUTTON_JS` set at the top of stdin. Fix: define
  everything inline at top level (no functions) or pass bindings as
  arguments. This bit us twice during authoring.
- **Multiple concurrent `browser-harness` runs share the same daemon
  socket (default `BU_NAME=default`).** Two scripts trying to drive the
  browser at once will fight and trample each other's state. When
  testing/debugging, `ps -ef | grep browser-harness` before relaunch; use
  distinct `BU_NAME` for parallel workflows.

## Self-inspection block (run when selectors stop matching)

```python
goto("https://www.linkedin.com/in/<some-real-profile>/")
wait_for_load(); wait(2)
for y in (0, 600, 1200, 1800, 2400, 0):
    js(f"window.scrollTo(0, {y})"); wait(0.35)

print(js(r"""(() => ({
  message_buttons_with_aria: document.querySelectorAll('button[aria-label^="Message "]').length,
  message_links_with_aria:   document.querySelectorAll('a[aria-label^="Send a message to "]').length,
  has_about_anchor:          !!document.querySelector('#about'),
  has_experience_anchor:     !!document.querySelector('#experience'),
  contenteditable_boxes:     document.querySelectorAll('[contenteditable="true"]').length,
  send_buttons:              [...document.querySelectorAll('button')].filter(b => /^\s*Send\s*$/i.test((b.innerText||'').trim())).length,
}))()"""))
```

If `message_buttons_with_aria === 0` on a real profile you're a 1st-degree
connection to, LinkedIn has rotated the anchor — update the table above.
