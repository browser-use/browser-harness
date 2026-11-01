# itch.io — optional-payment asset downloads

Verified on 2026-11-01 against the public CraftPix mirror for [Free Winter Nature Pixel Game Backgrounds](https://free-game-assets.itch.io/free-winter-nature-pixel-game-backgrounds). These observations apply to that free, optional-payment product; do not infer that every itch.io product has a free download route.

## Optional payment is a separate step

The public product page's `a.button.buy_btn` links to the product URL plus `/purchase`, even though the pack can be downloaded without payment. The purchase form offers an explicit link with the visible text **“No thanks, just take me to the downloads”**. Its semantic selector is `a.direct_download_btn`.

Use that offered link when obtaining the free download. This product required neither an account nor payment. Do not fill payment fields merely because the page is called “purchase.” If the current product does not offer a free route, that is a different workflow.

## Download controls need their page behavior

- The optional-payment link has an empty `href`; extracting its URL alone does not advance to the download page.
- On the resulting download page, file controls are `a.button.download_btn[data-upload_id]`. The observed `href` was `javascript:void(0);`, not an archive URL.
- Read the desired filename beside its control, then activate the control in the browser and verify the resulting download. Upload IDs are product-specific; discover them from the current page rather than reusing an ID from another pack.
- A public product URL, a purchase page and an actual download page are distinct states. Verify the current page and download result instead of treating the product link as a direct ZIP URL.

The acquisition also used the site's free-download request flow, but a reproducible endpoint/payload was not preserved in these notes. No API recipe is claimed here. Inspect current page/network behavior if an HTTP route is needed, and do not store session tokens or temporary download links in shared documentation.

## Confirm the package

Record the product/creator URL, downloaded filename, byte length and SHA-256. Check the downloaded pack's own license/source information separately from the purchase UI. The fact that a file is available without payment does not describe its license terms.
