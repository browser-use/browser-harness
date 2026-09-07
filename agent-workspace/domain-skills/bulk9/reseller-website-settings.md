# bulk9 — reseller white-label website settings

bulk9.com is a white-label bulk-SMS platform. A reseller account gets a
Laravel panel at `https://bulk9.com/reseller/...` that drives a customer-facing
site served on the reseller's own subdomain. This maps the
`/reseller/website-settings` page, which is where that whole public site is
authored.

## URL patterns

- Panel: `https://bulk9.com/reseller/website-settings`
- After any save the app redirects to `?tab=slideN`, reloading the whole
  page. The tab is restored from that query param, so a save is a full
  round-trip — re-read the DOM afterwards, don't reuse stale node handles.
- The public site lives at the reseller's own subdomain (CNAME → `bulk9.com`).
  Routes on it: `/` (landing), `/login`, `/signup`.

## Page structure

Five Bootstrap tab panes, switched by `a[href="#slideN"]`:

| Pane | Tab | Contents |
|---|---|---|
| `#slide1` | General Setting | display name, logo, favicon, panel colours, payment + contact rich text |
| `#slide2` | Domain Setting | subdomain add/verify, domain list |
| `#slide3` | Signup Setting | signup on/off, free credits, per-SMS price, validity |
| `#slide4` | Landing Setting | the entire public landing page |
| `#slide5` | Contact Query | read-only inbox of landing-page contact-form submissions |

Each pane has its own save button and posts independently:

- `#save-general-setting` (an `<a>`, not a button)
- `#add-domain-form` → its own submit
- `#save-signup-setting`
- `#save-landing-setting` (an `<a>`)

## The big trap: fields are not inside `<form>`

Only `add-domain-form` and `signup-settings-form` are real forms. The General
and Landing panes keep their inputs **outside** any `<form>` and the save
anchors collect values by name at click time. So:

- Don't try `form.submit()` or enumerate fields via `document.forms` — you
  will find the CKEditor toolbars' internal forms and almost nothing else.
- Enumerate by pane instead: `document.querySelectorAll('#slide4 input, ...')`.
- Filter out `el.closest('.ck')`, or CKEditor's own toolbar inputs
  ("Media URL" etc.) pollute every listing.

## Conditional fields

Most content fields do not exist in the DOM until their toggle is checked.
Check the toggle, wait ~1s, *then* read or write the revealed inputs.

- `#slide3`: `free_credits`, `sms_price`, `default_validity` appear only after
  `input[name="free_credit_on_signup"]` is checked.
- `#slide4`: each section is gated by its own checkbox — `show_about`,
  `show_social_media`, `show_contact`, `show_pricing`, `show_payment`,
  `show_client_logos`.

## Landing Setting field map (`#slide4`)

Plain inputs: `header_title`, `theme_color` (native colour picker),
`about_title`, `help_line_number`, `support_email`,
`twitter` / `instagram` / `linkedin` / `facebook` / `skype`.

File inputs: `header_banner`, `about_us_banner`.

CKEditor-backed textareas: `header_subtitle`, `about_description`,
`contact_description`, `contact_address`, `pricing_description`,
`payment_description`.

Repeaters (array fields, each row has a `.remove-detail` button):

- `#add-more-pricing` → `sms_quantity[]`, `per_sms_rate[]`, `amount[]`
- `#add-more-payment` → `bank[]`, `ifsc[]`, `account_no[]`, `name[]`
- `#add-logo` → client logo image rows

## CKEditor 5, not a plain textarea

The textareas are `display:none` and replaced by CKEditor 5. Setting
`textarea.value` alone is silently discarded on save. Reach the editor
through the DOM node CK created:

```python
js("""
(() => {
  const t = document.querySelector('#slide4 textarea[name="pricing_description"]');
  const ed = t.nextElementSibling.querySelector('.ck-editor__editable');
  const inst = ed.ckeditorInstance;          // CK5 exposes the editor here
  inst.setData("<h3>Hello</h3>");
  t.value = inst.getData();                  // keep the textarea in sync
})()
""")
```

The editor element is always inside `textarea.nextElementSibling`
(`div.ck.ck-reset.ck-editor`). The table plugin is enabled, so
`<figure class="table"><table>…` survives round-tripping; `<h3>`, `<ul>`,
`<strong>`, `<br>` and HTML entities all survive too.

## Rendering quirks on the public site

- An enabled section with empty content still renders its chrome. Enabling
  `show_pricing` with no `#add-more-pricing` rows renders a bare
  `SMS Quantity | Per SMS Rate | Amount` header bar with no body — looks
  broken. Either fill the repeater or leave the toggle off.
- Same for `about_us_banner`: the About section always emits an `<img>`, so
  with no upload you get a 0×0 broken image and a blank half-width column.
- The landing sections centre their text. A `<ul>` in `payment_description`
  renders bullets flush-left against centred text and reads as broken —
  prefer `<p>` there. In `about_description` (a left-aligned column) `<ul>`
  is fine.
- The `amount[]` column is displayed with a `₹` prefix added by the site;
  don't type the symbol into the field.

## Domain setting

Subdomains only — the hint text is "We accept only subdomain. Please create
CNAME on your sub domain to → bulk9.com". The domains table shows a
`Verification Status` column; it must read `Approved` before the public site
serves. Adding is `#add-domain-form` with a single `domain` input.

## Known platform bugs

- `select[name="default_validity"]` has duplicate option values: the options
  are `1,2,3,3,3` for *1–5 Years*. Anything above 3 Years is unselectable —
  picking "4 Years" or "5 Years" stores 3.
- There is a page-level hidden `input[name="sms_price"]` (the reseller's own
  buy rate) that collides by name with the Signup pane's `sms_price`. Always
  scope to `#slide3` when reading or writing the sell price, or you will pick
  up the wrong one.

## Verification

`page_info()['title']` on both the panel and the public site is
`🟢 <Page> - <display_name>`, so it flips to the new display name right after
a successful General Setting save — the cheapest confirmation that a save
landed. Beyond that, reload the public subdomain and diff `document.body.innerText`;
the page height jumps substantially once landing sections are populated.
