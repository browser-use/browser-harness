# Salesforce Setup — permission sets (Lightning + classic-in-iframe)

Field-tested on a Lightning Enterprise org with the enhanced setup domain
(`*.my.salesforce-setup.com`). Everything below is about *locating* things —
no pixel coordinates.

## URL patterns

- `/lightning/setup/PermSets/home` can render "Page not found" even for a
  System Administrator on some orgs. The classic list is always reachable
  via the address-wrapper route:
  `https://<org>.my.salesforce-setup.com/lightning/setup/PermissionSetListView/page?address=%2F0PS`
- A specific set: `...PermissionSetListView/page?address=%2F<0PS-id>`;
  its object settings: `...?address=%2F<0PS-id>%3Fs%3DEntityPermissions%26o%3DAccount`.
- "Page not found" with a working left nav usually means the *user* lacks
  the admin perm for that node (e.g. Manage Profiles and Permission Sets) —
  verify with a page that needs only View Setup (Company Information) before
  blaming the URL. Setup quick-find still lists nodes you cannot open.

## The classic iframe is same-origin but hidden in shadow DOM

Setup content pages render the classic UI in an iframe that
`document.querySelectorAll('iframe')` does NOT find — it sits inside nested
shadow roots. Walk shadow roots recursively; the frame is same-origin, so
once found you can script `contentDocument` directly:

```python
frame_js = """
(() => {
  let frames = [];
  const walk = (root, depth) => {
    if (depth > 25) return;
    for (const el of root.querySelectorAll('*')) {
      if (el.tagName === 'IFRAME') { try { if (el.contentDocument) frames.push(el); } catch(e) {} }
      if (el.shadowRoot) walk(el.shadowRoot, depth + 1);
    }
  };
  walk(document, 0);
  window.__sfFrame = frames[0];   // re-find after EVERY navigation — it is replaced
  return frames.length;
})()"""
```

The frame element is replaced on every in-frame navigation; a cached
reference goes stale silently (js() returns null). Re-run the walk before
each step.

## Classic UI mechanics (inside the frame)

- Buttons are `input[type=button]`/`input[type=submit]` with **padded
  values** (`" Nieuw "`), and some "buttons" are `a.btn` anchors (the
  Edit button on field-permission pages is `a.btn.pc_buttonLink`).
  Always compare `(el.value || el.textContent).trim()`.
- Field-permission rows: find checkboxes via
  `input[type=checkbox][id*="fls_read_ck"]` / `fls_edit_ck`, then match the
  row by the field-API-name cell (`tr.children[1].textContent.trim()`).
  Plain `.click()` on these classic checkboxes works fine.
- Form fills: set `.value` then dispatch `input` + `change` events; the
  setup quick-find tree also needs an `input` event after CDP
  `Input.insertText` before it filters.

## Lightning (non-iframe) pages: virtual checkboxes

The "Manage Assignments → Add Assignment" user picker is Aura
(`forceVirtualCheckbox`): a hidden `input[type=checkbox]` plus a
`span.slds-checkbox--faux`. JS `.click()` on the input does NOT stick
(state is re-rendered away). What works: compositor-click the faux span at
its `getBoundingClientRect()` center:

```python
pos = js("(() => { const r = document.querySelector('...faux-selector...').getBoundingClientRect(); return JSON.stringify({x: r.x + r.width/2, y: r.y + r.height/2}); })()")
click(pos["x"], pos["y"])   # CSS pixels — see below
```

`Volgende`/`Toewijzen` buttons stay disabled until the selection actually
registers — verify `input.checked` via JS before proceeding.

## CDP clicks are CSS pixels, not screenshot pixels

`Input.dispatchMouseEvent` coordinates live in the `window.innerWidth`
space. On a HiDPI session the PNG from `screenshot()` is
`devicePixelRatio ×` larger — coordinates read off the image miss silently.
Derive click targets from `getBoundingClientRect()` (as above), never from
screenshot pixel offsets.

## Person accounts: PersonEmail FLS lives on Contact

In the permission-set UI, orgs may not list person-account fields
("Person: Email") under **Accounts** at all. Field-level security for
`Account.PersonEmail` is controlled by **Contact → Email**: grant read
there and the API describe shows `PersonEmail` on Account. Verify with a
describe call rather than the UI field list.

## Traps

- Profile changes (e.g. being granted System Administrator) require a
  fresh login before Setup honours them.
- The login page may not autofill passwords for CDP-driven focus — treat
  it as an auth wall and hand it to the user.
- Dashboards/list views show "as of" cached data with a running-user
  banner; don't read org facts from a dashboard when Setup pages disagree.
