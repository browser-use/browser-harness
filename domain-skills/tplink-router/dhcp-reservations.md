# TP-Link router admin (VX420-G2v, Archer-family UI)

Web UI at `http://192.168.1.1`. Session is cookie-based; the user must log in — never
type router credentials.

## Page structure

- Two top tabs: **Basic** / **Advanced**. Almost everything useful is under Advanced.
- DHCP reservations: **Advanced → Network → LAN Settings**. The page holds four
  stacked sections: DHCP Server, Client List, Address Reservation, Condition Pool.
- Left menu items are `div`/`li`, not `<a>`. `element.click()` works for menu
  navigation, but the *submenu* only renders after clicking the parent group
  (e.g. "Network") — read the DOM again before looking for "LAN Settings".

## The trap that costs the most time

**The page body does not scroll.** `page_info()` reports `ph == h` and `scrollY`
is always `0`; an inner panel scrolls instead. So:

- `scroll(x, y, dy=...)` on the body does nothing.
- Fixed pixel coordinates are never stable across iterations.
- `element.scrollIntoView({block:'center'})` *does* work (it scrolls the inner
  container) — but read `getBoundingClientRect()` in a **separate** `js()` call
  afterwards. Combining scroll + rect-read in one call returns pre-scroll
  coordinates and every subsequent click misses.

## The other trap: the Add control

`Add` / `Delete` are `div.add-icon-wrap` containing `span.add-icon` (the glyph)
and `label.table-icon-text` (the word). The click handler is bound to the
**icon span only**. Clicking the wrapper's centre — which is what
`getBoundingClientRect()` on the wrapper gives you — lands between the two
children and silently does nothing.

```python
ICON = "document.querySelectorAll('.add-icon-wrap')[0].querySelector('.add-icon')"
# click the centre of ICON, not of .add-icon-wrap
```

Verify the form actually opened before filling — the reservation form contains a
`Scan` button, so its presence is a reliable open/closed signal:

```python
SCAN = "(()=>[...document.querySelectorAll('button,input')]" \
       ".filter(e=>e.offsetParent&&/scan/i.test(e.value||e.innerText||'')).length)()"
```

## Filling the reservation form

MAC and IP are split into separate octet inputs (6 + 4), unnamed and unlabelled.
Locate them relative to the `Scan` button: the six inputs *before* it are the MAC,
the four *after* it are the IP. Set values through the native setter and dispatch
`input`/`change`/`blur`, or the framework ignores them:

```python
const p = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
p.call(el, v);
el.dispatchEvent(new Event('input',{bubbles:true}));
el.dispatchEvent(new Event('change',{bubbles:true}));
```

Then click `OK`. Each saved row grows the table ~42px and pushes `OK` below the
fold on later iterations — re-check the rect and `scrollIntoView` when it returns
null.

## Reading the full client list

The Client List paginates at 5 rows. Rather than clicking through pages, the
**DHCP Server page's own table** renders every lease at once — query all `tr`
and filter rows that contain both a MAC-shaped and an IP-shaped cell.

## Useful identification detail

- Tuya/ESP smart bulbs appear with client name `lwip0` (the LwIP stack) or
  `ESP_xxxxxx`. That is often the only way to tell bulbs from other IoT gear.
- These devices frequently **do not answer ICMP**, so a ping sweep undercounts
  them badly. Probe TCP 6668 (Tuya local) with a ≥3s timeout instead.
- Some Tuya device IDs embed the MAC as their last 12 hex characters (older
  numeric-style IDs). Newer `bf...`-prefixed IDs do **not** — do not assume it,
  and beware `bf...` IDs whose tail happens to be valid hex.
