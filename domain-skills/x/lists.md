# X (x.com) — Lists: create, add members, scrape members, unfollow

React SPA. Coordinate clicks work everywhere; the traps are in routing, the search input, and result-row matching.

## URL patterns

- Your lists: `x.com/<handle>/lists`. List rows are NOT anchors — they're `[data-testid="listCell"]` divs; click one and read `location.href` to learn the list id.
- List page: `x.com/i/lists/<id>`.
- Members: `x.com/i/lists/<id>/members` — hard navigation works and renders the members UI as a modal over Home.
- Edit dialog: the "Edit List" button is an anchor to `/i/lists/<id>/info`, but hard-navigating there does NOT open the dialog (renders the plain list page). Click the anchor client-side from the list page. Inside it, "Manage members" opens a dialog with **Members (n)** / **Suggested** tabs; the add-search lives under Suggested ("Search people" placeholder).
- Create list: anchor `/i/lists/create` on the lists page (client-side click). Two-step dialog: name/private → Next → "Add to your List" (same Suggested search UI) → Done.

## Search input (member add) — the big trap

The "Search people" input is a React controlled input that silently ACCUMULATES text:

- Cmd+A does not select, so type-over doesn't clear it.
- The visual clear (x) button is unreliable to hit; if the clear fails, every subsequent search is garbage ("handle1handle2handle3") and returns zero results with no error.
- Reliable clear: native setter + input event, then verify before scanning results:

```js
const i = [...document.querySelectorAll('[role="dialog"] input')]
  .find(e => e.getAttribute('placeholder') === 'Search people');
i.focus();
Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(i, '');
i.dispatchEvent(new Event('input', {bubbles: true}));
```

Always assert `input.value === handle` after typing (via `type_text`) before reading rows. Results take ~2s to populate.

## Matching the right result row

Row `textContent` concatenates name + handle + button label with no separators: `"Noah Smith@NoahpinionAdd"`, `"James Surowiecki@JamesSurowieckiFollowing"`. Substring or regex-with-lookahead on row text misfires on near-identical handles. Instead walk text nodes for an EXACT `@handle` match, then walk up to the ancestor that contains the Add/Remove button:

```js
const walker = document.createTreeWalker(dialog, NodeFilter.SHOW_TEXT);
// find node.textContent.trim().toLowerCase() === '@handle', then climb
// parents until [...n.querySelectorAll('button')] has one with text 'Add'/'Remove'
```

`Add` → not a member; `Remove` → already a member. Click the button by coordinates (`getBoundingClientRect`).

## Add errors and rate limiting

- Failure surfaces only as a toast: `[data-testid="toast"]` / `[role="alert"]` with "You aren't allowed to add this member to this List." The button does not change state. Always read the toast after each add.
- That error can be ACCOUNT-LEVEL, not per-member or per-list: after ~100 adds across two days it fired for every member on every list, including a brand-new list, and persisted into the next day. Test one add before bulk-adding; if it errors, stop — retrying other handles just burns quota.

## Scraping a list's members

On `/i/lists/<id>/members`, each member row is a `[data-testid="cellInnerDiv"]`. Take only the FIRST `a[href]` of each cell whose href matches `^/[A-Za-z0-9_]+$` — bio @mentions are also profile links, so later anchors are false positives. Virtualized list: scroll the dialog's scrollable descendant (`scrollHeight > clientHeight`) by ~800px per step, recollect, stop after ~4 stall rounds. 169 members ≈ 30s.

## Unfollowing

- Normal profiles: `[data-testid$="-unfollow"]` button → `[data-testid="confirmationSheetConfirm"]`.
- Profiles with a purple Subscribe button: there is NO `-unfollow` testid. The following state is the person icon next to Subscribe — a `button[aria-label^="Following"]` without a data-testid → opens a menu → click the `[role="menuitem"]` whose text starts with "Unfollow". No confirmation sheet. Never click Subscribe.
- Verify state before acting: presence of `[data-testid$="-follow"]` means already not following. Verify after: same check.
- Pace ~2s between actions; stop the session at the first "Try again" page. ~30 unfollows per day avoids spam heuristics on accounts you care about.
