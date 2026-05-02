# Big Bang (bigbang.hr) — Checkout & GTM DataLayer

Big Bang is a Croatian electronics retailer. The site is a **Nuxt.js (Vue 3 SSR) SPA** with jQuery UI for some widgets. GTM container `GTM-5F34ZXDL`, GA4 property `G-QEEZK92T3P`.

## URL patterns

- Homepage: `https://www.bigbang.hr`
- Product: `https://www.bigbang.hr/webshop/<slug>/<sku>`
- Cart: `https://www.bigbang.hr/webshop/kosarica/`
- Checkout: `https://www.bigbang.hr/webshop/kupac/` (all 3 steps live on this URL — SPA routing)

## Checkout flow (3 steps, same URL)

1. **Podaci kupca** (Customer data) — name, address, location, email, phone
2. **Način dostave** (Delivery method) — package, pickup, parcel locker
3. **Odabir plaćanja i završetak kupnje** (Payment selection) — card, KEKS Pay, bank transfer

## Framework quirks — form filling

Vue's reactive data model ignores programmatic `.value =` changes. Two approaches that work:

### Native input value setter (works for most fields)

```javascript
function setVal(id, value) {
    const el = document.getElementById(id);
    const setter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype, "value"
    ).set;
    setter.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
}
setVal("first_name", "Test");
setVal("last_name", "Korisnik");
setVal("address", "Testna ulica 1");
setVal("email", "test@example.com");
setVal("phone", "00385911234567");
```

### Location autocomplete (jQuery UI — needs CDP keyboard input)

The `#location` field uses jQuery UI Autocomplete (`ul.ui-autocomplete.locations-ui-autocomplete`). The native setter trick does NOT work here — it won't trigger the autocomplete dropdown or populate the dependent `#zipcode` and `#city` fields.

Instead, use real keyboard input via CDP:

```python
js("document.getElementById('location').focus()")
cdp("Input.insertText", text="10000")
# Wait for autocomplete dropdown to appear (~500ms)
# Select from dropdown: li.ui-menu-item inside ul.locations-ui-autocomplete
# Use getBoundingClientRect() on the first li, then click_at_xy()
# This auto-populates #zipcode and #city
```

### Stable form field IDs

`#first_name`, `#last_name`, `#address`, `#location`, `#zipcode`, `#city`, `#email`, `#phone`

### Continue buttons

The continue buttons are `button` elements. JS `.click()` works but coordinate clicks can miss due to sidebar layout shifts. Prefer:

```javascript
[...document.querySelectorAll("button")]
    .find(b => b.textContent.includes("Nastavi"))
    .click()
```

Step 1 button text: "Nastavi na odabir načina dostave"
Step 2 button text: "Nastavi na plaćanje"
Final button text: "Potvrdi i naruči"

## GTM dataLayer events

The dataLayer fires standard GA4 ecommerce events:

| Event | When it fires |
|---|---|
| `view_cart` | Cart page load |
| `begin_checkout` | Entering step 1 (customer data) |
| `add_payment_info` | Transitioning from step 2 to step 3 (on "Nastavi na plaćanje" click) |

**`add_payment_info` quirk:** The event fires when the payment step *loads*, before the user selects a payment method. The `payment_type` in the payload reflects the *default* pre-selected option (`"opca_uplatnica_hr"` = bank transfer), not the user's choice. The event also fires multiple times (observed 4x) — likely duplicate GTM triggers.

### DataLayer interceptor pattern

The SPA preserves JS state across checkout steps (client-side routing), so a push interceptor installed once survives all 3 steps:

```javascript
window.__dlEvents = [];
// Seed dataLayer first — GTM may not have loaded yet when the snippet runs,
// in which case window.dataLayer is undefined and .push.bind would throw.
// Seeding with [] is safe: GTM picks up an existing array on init.
window.dataLayer = window.dataLayer || [];
const origPush = window.dataLayer.push.bind(window.dataLayer);
window.dataLayer.push = function() {
    for (let i = 0; i < arguments.length; i++) {
        const entry = arguments[i];
        if (entry && entry.event) {
            window.__dlEvents.push({
                event: entry.event,
                ecommerce: entry.ecommerce
                    ? JSON.stringify(entry.ecommerce).substring(0, 500)
                    : undefined,
                timestamp: new Date().toISOString()
            });
        }
    }
    return origPush.apply(window.dataLayer, arguments);
};
```

Read captured events: `js("JSON.stringify(window.__dlEvents)")`

## Payment methods (step 3)

- **Plaćanje karticama** — card payment
- **KEKS Pay** — mobile payment
- **Virmansko plaćanje** — bank transfer (default, pre-selected)
- **HT vrijednosni bon** — expandable voucher section
