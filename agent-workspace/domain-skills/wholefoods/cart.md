# Whole Foods Market (on Amazon) — Storefront, Search & Cart

Field-tested against amazon.com on 2026-10-16 in the user's Chrome (Chrome 155), not signed in to Amazon.
Storefront navigation, search, and product-page selectors below are verified. Add-to-cart and
cart-page selectors are **not** verified: the storefront hides the add button for guest sessions
(see Traps). Read `amazon/product-search.md` first for the general Amazon result-card selectors.

## URL patterns

```python
# Storefront landing (vanity URL; Amazon redirects to the alm storefront)
new_tab("https://www.amazon.com/wholefoods")
# -> https://www.amazon.com/alm/storefront?almBrandId=VUZHIFdob2xlIEZvb2Rz&ref_=vanity_url_wfm_m5_aug
# Page title: "Amazon Whole Foods Groceries"

# Search scoped to the Whole Foods storefront. `i=wholefoods` is the only required param.
goto_url("https://www.amazon.com/s?k=yellow+onions&i=wholefoods")
wait_for_load()
wait(2)  # result cards render after readyState=complete, same as regular Amazon

# Product page links from a storefront result keep the storefront context:
#   /dp/{ASIN}/...?almBrandId=VUZHIFdob2xlIEZvb2Rz&fpw=alm&s=wholefoods
# Keep almBrandId when you build a /dp/ URL by hand, or the page may fall back to the
# regular Amazon buy box.
```

`almBrandId=VUZHIFdob2xlIEZvb2Rz` is base64 for `WFM Whole Foods` and is stable. Amazon Fresh
uses a different `almBrandId`; do not mix them.

## Confirm you are inside the storefront

Check all three. A plain amazon.com search page passes none of them.

```python
ok = js("""
  ({
    scope: document.querySelector('#searchDropdownBox')?.value,          // 'search-alias=wholefoods'
    scopeText: document.querySelector('#searchDropdownBox option:checked')?.text,  // 'Whole Foods Market'
    logo: !!document.querySelector('a[href*="alm/storefront"] img[alt="Whole Foods Market"], img[alt="Whole Foods Market"]'),
    subnav: /Past Purchases|Shop Aisles|Catering/.test(document.body.innerText)
  })
""")
```

The green Whole Foods Market sub-nav (Past Purchases, Repeat Items, Alexa Lists, Save, Explore,
Shop Aisles, Catering) sits under the main Amazon nav on every storefront page, including search
results and product pages.

## Delivery location

The header shows `Delivering to <city> <zip>` with an `Update location` link
(`#contextualIngressPtLink` on product pages). The storefront picks a location from the session
before any sign-in. If the header shows `Choose your location` or a zip prompt instead, stop and
ask the user; do not type an address.

## Search results

Same card container as regular Amazon: `[data-component-type="s-search-result"]` with `data-asin`.
About 22 cards per page. Differences from regular Amazon:

- Cards have **no add-to-cart button**. The only interactive element is the rating popover.
  You must open the product page to add.
- Weight-priced produce shows `est. $1.39 /each ($1.99 /lb)`. `.a-price .a-offscreen` returns
  the per-unit estimate (`$1.39`), not the per-lb price.
- Every card shows `$9.95 delivery Today <window> with Prime`; this line is a storefront marker.
- Sponsored cards do appear (`.puis-sponsored-label-text`), and sponsored items can be regular
  Amazon items. Check the product page badge before you add.

```python
cards = js("""
  Array.from(document.querySelectorAll('[data-component-type="s-search-result"]')).map(el => ({
    asin: el.getAttribute('data-asin'),
    title: el.querySelector('h2 span')?.innerText?.trim(),
    price: el.querySelector('.a-price .a-offscreen')?.innerText,
    url: el.querySelector('h2 a, a.a-link-normal')?.href,
    sponsored: !!el.querySelector('.puis-sponsored-label-text')
  })).filter(c => c.asin)
""")
```

## Product page

Storefront product pages use the `alm` buy box, not the regular Amazon one.

```python
detail = js("""
  (function(){
    var q = s => document.querySelector(s);
    return {
      title: q('#productTitle')?.innerText?.trim(),
      price: q('.a-price .a-offscreen')?.innerText,
      asin: q('input[name="ASIN"]')?.value,
      almBuyBox: !!q('#desktop_almBuyBox'),                                 // storefront buy box
      wfmBadge: !!q('#rightCol img[alt="Whole Foods Market"]'),             // the badge
      seller: (document.body.innerText.match(/Ships from and sold by [^\\n.]+/) || [''])[0],
      availability: q('#almAvailability_feature_div')?.innerText?.trim(),
      addToCartButton: !!q('#add-to-cart-button'),
      signInWall: /Sign in to get started/.test(q('#desktop_almBuyBox')?.innerText || ''),
      cartCount: q('#nav-cart-count')?.innerText
    };
  })()
""")
```

- `#desktop_almBuyBox` and `#almLogoAndDeliveryMessage_feature_div` exist only on storefront
  items. The regular Amazon buy box (`#buybox` without `#desktop_almBuyBox`) means the item is not
  a Whole Foods item even if you reached it from a storefront search.
- `Ships from and sold by WFMOA_<StoreName>_STO_<id>` names the physical Whole Foods store that
  fulfils the order (for example `WFMOA_Stonestown_STO_10717`). Amazon Fresh items do not use the
  `WFMOA_` prefix.
- `#almAddToCart_feature_div` is the container for the add control. `#addToCart` is present
  even when the button is not.
- Cart count: `#nav-cart-count` (header), on every page.

## Add to cart (not verified)

The signed-in storefront buy box is expected to render `#add-to-cart-button` and a `#quantity`
select inside `#almAddToCart_feature_div`, like regular Amazon. Verify on a signed-in session
before you rely on it, and add the verified selectors here.

## Traps

- **Guest session has no add-to-cart.** When the Chrome profile is not signed in to Amazon
  (`Hello, sign in` in the header), every storefront product page replaces the add control with
  `Sign in to get started` and a yellow `Sign In` button that links to `/ap/signin`. `Add to
  List` links to sign-in too. There is no guest cart for Whole Foods delivery. Stop and ask the
  user to sign in; do not type credentials.
- **Sign-in detection:** `#desktop_almBuyBox` text contains `Sign in to get started` and
  `#add-to-cart-button` is null.
- **Sponsored banner above the product title** is a regular Amazon ad (not a Whole Foods item).
  Ignore it.
- **`Page.captureScreenshot` hangs** (the harness raises after 60 s) when the Chrome window is
  behind other windows or the tab is not active. Chrome does not paint an occluded tab. Fix:
  `activate_tab(current_tab())` and, if still stuck, `open -a "Google Chrome"` from the shell,
  then capture again. `js(...)` and `page_info()` keep working while screenshots hang.
- **Chrome with zero windows denies CDP.** Chrome running with `--no-startup-window` (no
  visible window) answered the daemon handshake with an immediate 403 and never showed the
  per-connection `Allow remote debugging?` sheet. Opening one window first with
  `open -a "Google Chrome" "https://www.amazon.com/wholefoods"` made the sheet appear and the
  connection succeed after Allow.
