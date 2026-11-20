# importyeti.com — supplier lookup

US sea-shipment (bill of lading) database: look up any US company → see its suppliers/manufacturers.

## Access

- **Cloudflare-blocked for plain HTTP** — curl/requests get 403 challenge. Use the real browser (works first try, no stealth needed).
- **No login needed to read** company reports, supplier tables, shipment counts, HS codes, product descriptions. Login is only required to contact suppliers / some CSV exports.

## URL pattern

- Company report: `https://www.importyeti.com/company/<kebab-case-name>` (e.g. `/company/recess-pickleball`). Guessing the slug from the brand name usually works; otherwise use the site search.

## Extraction

Page is long (~7000px). Don't screenshot-scroll — pull `document.body.innerText` and slice from the `"Suppliers"` marker:

```python
r = js("""
(() => {
  const t = document.body.innerText;
  const i = t.indexOf("Suppliers");
  return i >= 0 ? t.slice(i, i + 3000) : "no suppliers section";
})()
""")
```

Supplier entries contain: supplier name, city/country, shipment-activity date range, total shipments, product-category chips, product descriptions, HS codes, and a "See all bills of lading with this supplier" link.

## Traps

- Only **sea** shipments — air-freight-only suppliers won't appear.
- Section order in `innerText`: Customers → … → Suppliers → Recent Sea Shipments; searching for the literal `"Suppliers"` heading is reliable.
