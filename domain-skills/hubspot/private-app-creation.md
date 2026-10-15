# HubSpot — creating a Private App

For generating a long-lived access token (`pat-<region>-<uuid>`) against `api.hubapi.com`. Takes ~60 seconds of clicks if you drive it via DOM.

## URL map

- `https://app-<region>.hubspot.com/legacy-apps/{portalId}` — **start here**. Private Apps live under "Legacy Apps" now.
- `https://app-<region>.hubspot.com/private-apps/{portalId}` — **dead route** for dev portals; it renders "Your private apps have moved" with a redirect button. Don't start here.
- `https://app-<region>.hubspot.com/settings/{portalId}/integrations/private-apps` — **404**. HubSpot's docs still reference the Settings path, but it's gone from the UI in the dev-portal/standard-portal case.
- After creation, HubSpot redirects to `https://app-<region>.hubspot.com/private-apps/{portalId}/{appId}` — that IS a valid URL post-creation (it's the app-detail page).

`<region>` is `na1`, `na2`, `eu1`, etc. — read it off the current `location.hostname` or from the portal's own settings.

## Flow

1. Land on `/legacy-apps/{portalId}`.
2. Click the orange "Create legacy app" button (top-right).
3. A modal appears: "Public" (for many accounts) vs "Private" (for one account). Clicking "Private" enters the creation form.
4. Fill **Basic Info** tab: name + description. Logo is optional.
5. Click **Scopes** tab → **Add new scope** → scope picker drawer opens from the right.
6. Check the scope checkboxes you want → **Update** at the bottom of the drawer.
7. Click **Create app** (top-right) → confirmation modal warns about token sharing.
8. Click **Continue creating** → redirect to app detail page.
9. **Auth** tab has the access token. Click **Show token** to unmask.

The app detail page is also where you rotate the token or delete the app later.

## Gotchas

### Text content is in `<I18N-STRING>` custom elements, not regular text

Standard `[...document.querySelectorAll('button')].find(b => b.innerText === 'Scopes')` often **fails** because the button's innerText is composed from a custom `<I18N-STRING>` child element whose text walkers/selectors may not traverse the same way as `<span>`. Work around it with a `TreeWalker`:

```js
const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
let node;
while ((node = walker.nextNode())) {
  if (node.nodeValue.trim() === 'Scopes') {
    let cur = node.parentElement;
    for (let i = 0; i < 6; i++) {
      if (!cur) break;
      if (cur.tagName === 'A' || cur.tagName === 'BUTTON' || cur.getAttribute('role') === 'tab') {
        cur.click();
        break;
      }
      cur = cur.parentElement;
    }
    break;
  }
}
```

This pattern (text-node → walk up to clickable ancestor) works for basically every tab, button, and card in the HubSpot developer UI.

### Form inputs are React-controlled

Setting `input.value = 'x'` doesn't register. Use the native setter + dispatch `input` event:

```js
const desc = Object.getOwnPropertyDescriptor(el.constructor.prototype, 'value');
desc.set.call(el, 'AO MCP');
el.dispatchEvent(new Event('input', { bubbles: true }));
el.dispatchEvent(new Event('change', { bubbles: true }));
```

### Scope rows have direct checkboxes — click them, not the row

The scope picker renders each scope as a row. The checkbox is a real `<input type="checkbox">`. Walk up from the scope's code-name text node to find the checkbox in the same row:

```js
let cur = scopeCodeTextNode.parentElement;
for (let i = 0; i < 8; i++) {
  if (!cur) break;
  const cb = cur.querySelector('input[type="checkbox"]');
  if (cb) { if (!cb.checked) cb.click(); break; }
  cur = cur.parentElement;
}
```

### Two-step confirmation before token issuance

After clicking "Create app," a "Create a new private app" warning modal appears with a "Continue creating" button. Don't stop after the first click — look for the modal.

### Show token ≠ one-time reveal

Unlike some credential systems, the HubSpot Private App token is re-revealable indefinitely from the Auth tab → Show token. Not capturing it on first click is fine.

### Token format

`pat-{region}-{uuid-v4}` — 44 characters total. Regex: `^pat-na[0-9]+-[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$`. The 5-char hex prefix shown in the masked view (e.g. `pat-na2-abcde**-...`) is the start of the UUID's first group — useful for confirming a revealed token matches what you're looking at without printing the full value.

## Verification

After capturing the token, a 200 from `/account-info/v3/details` confirms both validity and the `portalId` the token is bound to:

```bash
curl -sS -H "Authorization: Bearer $TOKEN" https://api.hubapi.com/account-info/v3/details
# => {"portalId":..., "uiDomain":"app-na2.hubspot.com", "dataHostingLocation":"na2", ...}
```

The `uiDomain` / `dataHostingLocation` fields tell you which `<region>` to use for future Auth-tab URLs.

## What doesn't apply to Private Apps

- No OAuth flow, no client_id/client_secret exchange for getting a token
- No "verify your app" / "unverified-app banner" (those are Public App concerns)
- No redirect URI configuration
- No user consent screen — token is account-scoped, not user-scoped
- No marketplace review
- Client secret shown on the Auth page is for **webhook signature validation**, not API auth
