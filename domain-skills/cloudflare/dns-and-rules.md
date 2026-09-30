# Cloudflare dash — DNS records & Configuration Rules

Adding a DNS record and a scoped Configuration Rule through the dashboard.
Needed because `wrangler login`'s OAuth token carries only `zone:read`, which
is zone *metadata* — it lists zones but cannot read or write DNS records or
zone settings. Both return `10000 Authentication error` / `9109 Unauthorized`.
There is no wrangler command for DNS; the browser (or a real API token with
`Zone → DNS → Edit`) is the only route.

## URL patterns

- DNS records: `https://dash.cloudflare.com/<accountId>/<zone>/dns/records`
  - `?search=<term>&page=1` — the search box is reflected in the URL.
- SSL/TLS overview: `.../<zone>/ssl-tls` — shows **Current encryption mode**.
- Rules overview: `.../<zone>/rules/overview?type=http_config_settings`
- New configuration rule: `.../<zone>/rules/configuration-rules/new`
  (`/rules/configuration-rules` redirects to the filtered overview, not a list.)

Find `<accountId>` and the zone id without the dashboard:

```bash
TOK=$(grep -m1 '^oauth_token' ~/Library/Preferences/.wrangler/config/default.toml | sed -E 's/.*= *"([^"]*)".*/\1/')
curl -s -H "Authorization: Bearer $TOK" \
  "https://api.cloudflare.com/client/v4/zones?account.id=<acct>&per_page=50"
```

That endpoint *does* work on the OAuth token — it is the one useful read.

## Stable selectors

The dash is React + Base UI. Element ids are generated per render
(`base-ui-:rh7:`, `base-ui-:rhs:`) and **change between renders** — never key
off them. `name` attributes are stable:

**Add DNS record modal**
- Type: a Base UI custom select, *not* a `<select>`. Its state is mirrored in
  `input[id$="-hidden-input"]` (read it to assert; writing it does nothing).
  Change it by clicking the trigger and then the option.
- Name: `input[name="name"]`
- CNAME target: `textarea[name="target"]` — a **textarea**, not an input, so
  use the `HTMLTextAreaElement` native setter.
- A-record target: `input[name="ipv4_address"]` (replaced by the textarea the
  moment Type flips to CNAME).
- Proxy status defaults to **Proxied** — correct for most cases, assert anyway.

**Configuration Rule builder**
- Rule name: the only wide `input[type="text"]` above the match section.
- `Edit expression` link swaps the field builder for
  `textarea[name="filterExpression"]` — far more reliable than driving the
  Field/Operator/Value dropdowns. Write the expression directly, e.g.
  `http.host eq "sub.example.com"`.
- Each setting row has a `+ Add` button; clicking it reveals the control.

## Framework quirks

**Every text field is a React controlled input.** `Input.insertText` and
coordinate typing get reverted on the next render. Use the native setter and
fire both events:

```js
const set = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
set.call(el, 'value');
el.dispatchEvent(new Event('input',  {bubbles:true}));
el.dispatchEvent(new Event('change', {bubbles:true}));
```

For a `<textarea>` use `HTMLTextAreaElement.prototype` — the `HTMLInputElement`
setter silently no-ops on a textarea.

**Custom-select options carry no `role="option"`.** Querying `[role="option"]`
returns an empty list even while the dropdown is visibly open, which reads as
"the dropdown failed to open" and sends you round the loop a second time.
Screenshot to confirm the open state rather than trusting that query.

**Custom-select options commit on a real click.** Measure the option's *live*
rect and click it; do not rely on Enter.

```python
r = js("""(()=>{const o=[...document.querySelectorAll('[role="option"],li,div')]
  .find(e=>e.innerText.trim()==='CNAME'
    && e.getBoundingClientRect().width>0
    && e.getBoundingClientRect().width<300);
const b=o.getBoundingClientRect();
return JSON.stringify({x:Math.round(b.x+b.width/2),y:Math.round(b.y+b.height/2)});})()""")
p=json.loads(r); click(p["x"],p["y"])
```

The `width<300` guard matters — without it the selector matches a huge
ancestor `div` whose `innerText` is also just the option label, and the click
lands in dead space.

**The Type listbox can report zero-size rects while visibly open.** On some
renders every `[role="listbox"] [role="option"]` returns a 0×0
`getBoundingClientRect()` even though the screenshot shows the popover with
all 21 types. When that happens, `scrollIntoView` does nothing either —
screenshot, read the option's position off the image, and coordinate-click
it. Do not re-click the trigger to "reopen" it: that toggles the popover
closed and the outside-click also dismisses the whole Add record modal.

**Proxy status is a Base UI `[role="switch"]`, not the checkbox.** The
`input[type=checkbox]` mirrors are 1px and off-screen (rect ~`{x:835,y:64}`),
so clicking their rect misses. Locate the switch with
`document.querySelector('[role=dialog] [role="switch"]')`, click its live
rect, and assert `aria-checked="false"` plus the summary sentence dropping
"and has its traffic proxied through Cloudflare". Flatten is the second
checkbox in the dialog and defaults off.

**After Save the modal stays open with a blank form** for the next record
(the dash's "add another" behaviour). `Cancel` closes it. A stale
`[role=dialog]` node with a non-zero rect can linger in the DOM after
closing — screenshot to confirm rather than trusting the query.

**Verify with `dig @1.1.1.1`, not the table.** The records list can take a
few seconds to re-render after Save, and the row-scraping query may return
nothing while public DNS already has the record.

**AAAA records and a more reliable path through the modal.** For AAAA the
target is `textarea[name="ipv6_address"]`. Driving the modal with element
`.click()` calls avoids the coordinate problems above: `.click()` the Type
trigger (the dialog `button` whose `innerText` is the current type), then
`.click()` the `[role=option]` whose text is `AAAA`. Then `.focus()`
`input[name=name]` / the textarea and use `type_text()`. On current renders
`Input.insertText` after a programmatic `focus()` sticks. Assert the summary
sentence ("<host> points to 100:: and has its traffic proxied…") before Save.

**Never press Escape or click outside the dialog to dismiss a password-manager
overlay.** Both close the whole Add record modal. The overlay (e.g. Dashlane
"Identity" on the Name field) disappears once focus moves to another field
programmatically.

## Waits

`wait_for_load()` returns while the dash is still hydrating; the whole app is
client-rendered. After navigating, allow ~5 s before reading `innerText` or
the sidebar nav is all you get back. After **Deploy** allow ~8 s before
asserting on the rules list.

## Traps

- **The Recommendations banner at the top of the DNS page contains links
  ("Review SPF records") that open an inline *edit* form on a real production
  record.** The banner also shifts page height as it loads, so a coordinate
  captured from an earlier screenshot can land on one. Nothing is written
  until Save, but always locate buttons by `innerText` at click time rather
  than reusing coordinates, and click `Cancel` if a form appears unexpectedly.
- **The SSL setting in a Configuration Rule defaults to `Off`**, which means
  no TLS between browser and edge — not "leave alone". Always set it
  explicitly. Options are `Off | Flexible | Full | Strict`.
- **Zone SSL mode may be under "Automatic mode"** (`Automatic mode enabled ·
  N days ago` on the SSL/TLS overview). Cloudflare can then change the
  zone-wide mode on its own. A Configuration Rule scoped to a hostname
  overrides it for that hostname and is the safe way to make one subdomain
  differ from the zone.
- **A proxied record in front of an origin with no 443 listener returns 522
  after ~117 s** when the zone is Full/Strict — the edge dials the origin on
  443 and hangs. It is not a DNS or certificate problem; check the encryption
  mode first.
- **Universal SSL covers `*.example.com`**, so a new subdomain gets a valid
  edge cert immediately — verify with `curl --resolve` before suspecting certs.
- **`dig @1.1.1.1` can show the record while the local stub resolver still
  returns NXDOMAIN for A.** Use `curl --resolve <host>:443:<edge-ip>` to test
  rather than waiting on the local cache. Note `--resolve` and its argument
  must be separate shell words; a quoted `"$R"` variable containing both is
  passed as one arg and curl rejects it.
