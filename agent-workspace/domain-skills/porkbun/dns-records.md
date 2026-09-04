# Porkbun — editing DNS records

Registrar UI at `porkbun.com`. DNS is "Powered by Cloudflare" but the editing
surface is Porkbun's own drawer, not Cloudflare's.

## Getting to the records

Go to **Domain Management** (`/account/domainsSpeedy`) and click the small
**DNS** badge on the domain's row. The record table loads *inline* in a
right-hand drawer.

**Trap:** the direct `/account/dns/<domain>` URL renders an **empty table** —
it looks like the domain has no records. Always enter through the DNS badge.

**Trap:** the domain row also carries an `NS` badge and the page has a
**Save Nameservers** button sitting near the record-drawer controls. Don't
click it while aiming for a record's Save.

## Drawer structure

Header has a `Filter records…` box and a **+ Add record** button. The footer
shows a live **"N records"** count — the cheapest way to confirm an add or
delete actually landed (snapshot it before and after).

Add/edit form field IDs are stable:

| id | notes |
|---|---|
| `dnsDrawer_type` | `<select>`: A, AAAA, ALIAS, CAA, CNAME, HTTPS, MX, NS, SRV, SSHFP, SVCB, TLSA, TXT |
| `dnsDrawer_host` | subdomain only — the `.<domain>` suffix is a static label, don't type it |
| `dnsDrawer_answer` | `<input>` — used by most types |
| `dnsDrawer_answer_long` | `<textarea>` — **TXT swaps to this id**, `dnsDrawer_answer` won't exist |
| `dnsDrawer_ttl` | defaults 600 |
| `dnsDrawer_priority` | appears for MX/SRV only |
| `dnsDrawer_notes` | private, does not affect DNS |

The form is framework-controlled: set values with the native setter and
dispatch `input` + `change`, or the model won't see them.

```js
function setVal(el, v){
  const proto = el.tagName === "TEXTAREA"
    ? window.HTMLTextAreaElement.prototype
    : window.HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, "value").set.call(el, v);
  el.dispatchEvent(new Event("input",  {bubbles:true}));
  el.dispatchEvent(new Event("change", {bubbles:true}));
}
```

Changing `dnsDrawer_type` re-renders the form — re-query field ids afterwards
rather than caching element handles.

After a successful Add the drawer **resets to type `A`** and returns to the
list with the new row briefly highlighted. Re-select the type for each
additional record.

## Deleting — the important one

Each row has Edit (`.btn-default[title=Edit]`) and Delete
(`.btn-danger[title=Delete]`) buttons.

Delete fires a **native `confirm()`**, which freezes the JS thread. If you
click the button from inside `Runtime.evaluate`, the evaluate call **appears
to time out** — that is the dialog, not a failure. Handle it:

```python
cdp("Page.handleJavaScriptDialog", accept=True)
```

**Trap:** the confirm message is generic — `"Delete the TXT record for
<domain>?\n\nThis cannot be undone."` It does **not** name the record's value.
With several same-type records on the same host (multiple SPF/TXT entries are
common) the dialog gives you nothing to check against.

So resolve the row in the DOM by exact content and guard on a unique match
*before* clicking:

```js
const rows = [...document.querySelectorAll("tr")]
  .filter(r => r.innerText.includes(NEEDLE) && !r.innerText.includes(DECOY));
if (rows.length !== 1) return "ABORT: matched " + rows.length;
rows[0].querySelector(".btn-danger").click();
```

If the guard trips, no dialog opens — a clean, observable abort.

## Verifying

Porkbun's own table is the source of truth for what you saved; public DNS is
the source of truth for what the world sees. TTL 600 records surfaced on
`dns.google/resolve` within a minute in practice.

`dig` is often absent in WSL — use DNS-over-HTTPS instead:

```bash
curl -s "https://dns.google/resolve?name=example.com&type=TXT"
curl -s -H 'accept: application/dns-json' \
  "https://cloudflare-dns.com/dns-query?name=example.com&type=TXT"
```

`Status: 3` in that JSON is NXDOMAIN — the name genuinely does not exist.
