# Capterra Public Listing Audit

Field-tested against https://www.capterra.com on 2026-08-14.

## Access pattern

Capterra may return a Cloudflare block to curl, headless browsers, or separate browser clients while loading normally in an established visible Chrome profile on the same machine. Treat this as client-specific access behavior, not proof that the site or listing is unavailable. Do not bypass a CAPTCHA or security challenge; switch to an already-authorized established browser profile when available.

```python
tid = new_tab("https://www.capterra.com/search/?query=Exact%20Product%20Name")
wait_for_load(30)
wait(3)  # listing cards continue rendering after the load event
print(page_info())
```

## Find the canonical product page

Search results expose ordinary product links. Match exact visible product text before opening because broad names can return many near-matches.

```python
results = js("""
Array.from(document.querySelectorAll('a[href*="/p/"]'))
  .map(a => ({text:(a.innerText||'').trim(), href:a.href}))
  .filter(x => x.text)
""")
```

Product URLs follow:

```text
https://www.capterra.com/p/<numeric-id>/<product-slug>/
```

After opening a result, read the canonical URL from `link[rel="canonical"]`; do not guess the numeric ID.

## Audit a live listing

Capture both visible text and structured page state:

```python
meta = js("""
({
  title: document.title,
  description: document.querySelector('meta[name=description]')?.content,
  canonical: document.querySelector('link[rel=canonical]')?.href,
  ogTitle: document.querySelector('meta[property="og:title"]')?.content,
  ogDescription: document.querySelector('meta[property="og:description"]')?.content
})
""")

jsonld = js("""
Array.from(document.querySelectorAll('script[type="application/ld+json"]'))
  .map(s => s.textContent)
""")

links = js("""
Array.from(document.querySelectorAll('a[href]'))
  .map(a => ({text:(a.innerText||a.getAttribute('aria-label')||'').trim(), href:a.href, rel:a.rel}))
""")

images = js("""
Array.from(document.images)
  .map(i => ({alt:i.alt, src:i.currentSrc||i.src, width:i.naturalWidth, height:i.naturalHeight}))
""")
```

Also take a full-page screenshot. The visual presentation distinguishes selected options from unavailable ones; a plain `innerText` dump can list both without preserving check/X state.

Audit at least:

- product and vendor branding;
- category, short description, and long description;
- pricing and plan features;
- selected category features;
- support, training, deployment, and typical-user choices;
- logo plus screenshot count/captions;
- canonical public URL;
- buyer-facing Website or Visit Website link.

## Backlink trap

A product-site URL can appear only inside Capterra's `Manage this product listing` / claim URL query parameters. That is not a buyer-facing backlink to the product site. Count a backlink only when an actual visible buyer CTA or anchor resolves to the product domain. Inspect both anchors and buttons; do not infer a backlink from raw HTML string occurrence alone.

## Verification rule

A publication email or vendor-dashboard status proves publication, but not the quality or backlink value of the live page. Before asking support for a correction, open the public listing and compare the current visible state to the intended request. If branding is already correct, narrow the request to the remaining issue instead of sending a stale broad correction.
