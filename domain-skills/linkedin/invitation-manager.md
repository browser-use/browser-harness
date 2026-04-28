# LinkedIn — Invitation Manager

Accept or ignore pending connection invitations in bulk from
`https://www.linkedin.com/mynetwork/invitation-manager/received/<FILTER>/`.

## URL filters

The trailing slug pre-filters the received invitations. Observed slugs:

- `PEOPLE_WITH_MUTUAL_CONNECTION` — people who share a mutual connection
- `PEOPLE_WITH_MUTUAL_SCHOOL` — people who share a school
- omit the slug (`.../received/`) for all pending invitations

The filter chip at the top of the page mirrors the URL and also renders
`All (N)`, `Mutual Connections (N)`, `Your School (N)` — the `(N)` is the
authoritative remaining-count for the active filter and is what you loop on.

## Button selectors

Each pending-invitation card contains an Accept and an Ignore control.
**The aria-label formats are different** for the two buttons — don't derive
one from the other:

- Accept: `aria-label = "Accept <Name>'s invitation"` (note: curly `’`, not ASCII `'`)
- Ignore: `aria-label = "Ignore an invitation to connect from <Name>"`

```python
# Match either — both are unique per card
accepts = js("Array.from(document.querySelectorAll('button, a')).filter(b => (b.getAttribute('aria-label')||'').startsWith('Accept ')).length")
ignores = js("Array.from(document.querySelectorAll('button')).filter(b => (b.getAttribute('aria-label')||'').toLowerCase().startsWith('ignore')).length")
```

## Trap: "follows you" cards render Accept as `<a>`, not `<button>`

For invitations labeled `<Name> follows you and is inviting you to connect`
(typically Premium users' auto-invites), the Accept control is an `<a href>`,
not a `<button>` — and the `href` points at the **current page URL**.

`<a>.click()` follows the href → same-URL soft-nav → accept never fires.
Dispatched `MouseEvent`s and coordinate `Input.dispatchMouseEvent` clicks
also land on the element (you can see the focus ring appear) but do not
trigger the underlying accept handler. **There is no known way to accept
these via CDP.** Click the Ignore button instead (Ignore is always a
`<button>` and works with a normal coordinate click), or skip the row.

Detect with `element.tagName === 'A'` on the Accept element.

```python
# In your extractor, capture the tag so downstream logic can route these
rows = js(r"""
(() => {
  const accepts = Array.from(document.querySelectorAll('button, a'))
    .filter(b => (b.getAttribute('aria-label')||'').startsWith('Accept ') && !b.disabled);
  return accepts.map(a => ({aria: a.getAttribute('aria-label'), tag: a.tagName}));
})()
""")
```

## Pagination — reload, don't scroll

The list only renders ~10 cards at a time. After you click Accept on the
visible batch, LinkedIn replaces the pending section with a "X is now a
connection" acknowledgment list + "Suggestions for you" — the next batch of
pending invites does **not** auto-mount. Window-scroll does not trigger
lazy-load either.

Pattern:

1. Navigate to the filter URL, `wait_for_load()`, sleep ~2.5s.
2. Extract visible rows, decide, click Accept/Ignore for each (`.click()` via
   JS works for `<button>` Accept and Ignore; coordinate click via
   `Input.dispatchMouseEvent` also works).
3. Reload the URL (`cdp("Page.navigate", url=...)`). Do **not** rely on
   scrolling or clicking a "show more" control.
4. Repeat until the filter chip shows `(0)` or no Accept buttons remain.

Chip count decreases by the number of successful accepts + ignores per
cycle — use it as the loop guard.

## Safety modal: "Take care when connecting"

LinkedIn occasionally interposes a `"Take care when connecting"` dialog
when you click Accept on a connection it considers unfamiliar. The dialog
has `View profile` and `Accept invite` buttons — click `Accept invite` to
proceed. Watch for it between accepts; it's intermittent, not per-row.

## Quick sketch

```python
import time

def chip():
    return js(r"""(() => {
      const el = Array.from(document.querySelectorAll('button, a')).map(e => (e.textContent||'').trim())
        .find(t => /^Mutual Connections \(/.test(t));
      return el || '';
    })()""")

while True:
    cdp("Page.navigate", url="https://www.linkedin.com/mynetwork/invitation-manager/received/PEOPLE_WITH_MUTUAL_CONNECTION/")
    wait_for_load()
    time.sleep(2.5)
    n = int(js(r"""(() => Array.from(document.querySelectorAll('button, a'))
      .filter(b => (b.getAttribute('aria-label')||'').startsWith('Accept ') && !b.disabled).length)()"""))
    if n == 0:
        break
    # click each Accept (route tag === 'A' rows to Ignore — see trap above)
    ...
```
