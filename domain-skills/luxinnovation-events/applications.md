# events.luxinnovation.lu — grant / accelerator application forms

Luxinnovation runs its programme applications (Fit 4 Start, etc.) on a multi-section
form at `events.luxinnovation.lu/e/<programme>/...`. The application is a long server-saved
draft. These notes are for *filling* it reliably.

## Structure

- Two top tabs: **Information** (the long form) and **Team members** (separate member records).
- Left nav lists sections (Eligibility, Company details, Project, Value proposition,
  Development stage, Team & collaboration, Financing, Additional Information, Disclaimer, …).
- Each section has its own **Save** button (bottom centre). Save is per-section, not global.
- A section shows a **warning triangle** in the left nav until all its required fields are
  filled. The tab badge (e.g. "Team members 1") counts incomplete records.
- Status stays **Draft** until you hit **Submit your application** (top right). Saving a
  section does not submit.

## The trap that will waste your time

**Setting input/textarea values with the React-style synthetic pattern**
(`Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set` + dispatch
`input`/`change`) **makes the field look filled but the value is dropped on Save** — the
section reloads empty and the warning triangle never clears. The form's framework only
commits values it received through real key events.

Fill instead with **compositor-level typing**: focus the element, select-all, then CDP
`Input.insertText`:

```python
el = ...  # the target input/textarea (tag it with a data attr to re-find it)
js("(()=>{const e=document.querySelector('[data-fidx=\"3\"]'); e.focus(); e.select&&e.select(); document.execCommand('selectAll');})()")
cdp("Input.insertText", text="my value")
js("document.activeElement && document.activeElement.blur()")
```

**Always verify persistence by reload, not by reading the DOM you just wrote.** Switch to
another section and back (or `location.reload()` and wait), then re-read the field / check
whether the nav triangle cleared. The on-screen state right after a JS write lies; the
server-saved state is the truth.

## Custom dropdowns (country, stage, gender, counts)

Not native `<select>`. Two shapes:

- **Searchable popup** (countries, etc.): the placeholder reads "Click to select an item".
  Click it, type a filter into the search box that appears (`Input.insertText`), then
  **coordinate-click the matching rendered option**. Selecting by JS `.click()` on the option
  often does not stick — click the rendered element. Re-verify after Save+reload.
- **Short enum/number list** (e.g. count 0/1/2/3, stage Idea/Concept/MVP/Market launch):
  click the field, then click the option in the dropdown that drops below it.

`scrollIntoView` the placeholder before reading its rect — the list virtualises and the
element's coordinates shift after scrolling.

## Other field types

- **Date** (e.g. incorporation): a typed text input, placeholder "Type your date, ex:
  MM/DD/YYYY". Fill with `Input.insertText` in `MM/DD/YYYY`; verify after reload.
- **File upload** (e.g. budget table): the `input[type=file]` is hidden (`offsetParent`
  null). Use CDP `DOM.setFileInputFiles` on its node id; watch the page text go
  "Upload in progress..." → "Upload completed!" before Save.
- **Conditional fields** appear *after* a radio/count choice: selecting "1" major
  shareholder reveals name + country + ">25% elsewhere" fields; answering "Yes" to a
  Dealroom-profile radio reveals a profile-URL field. Re-inventory the section after each
  radio/select change, then fill the new fields.

## Reattach / recovery

The draft lives at a stable
`.../callforpaper/<id>/submission/<submission-id>` URL — reopen it in a new tab (the user's
session cookie carries the auth) and everything previously Saved is still there. The bare
`/registration/register` URL is the start page, not the draft; do not confuse the two.
