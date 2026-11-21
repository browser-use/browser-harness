# DoorDash merchant menu and promotion picker

## Menu items

- Menu route: `/merchant/menu-editor/<menu-id>?store_id=<store-id>`.
- `.category-header` expands a category. Scope Add Item to that category's container; multiple categories can be expanded at once.
- New-item fields: `input[name=name]`, `textarea`, `input[name=inStorePrice]`, `input[name=deliveryPrice]`, and a native category `select`.
- Prices are formatted React controls. Focus, select the existing value, enter the amount, blur, and read back both prices. Do not assume the marketplace amount follows the in-store amount.
- Create and add photo saves the item first, then opens a photo-library dialog. Wait for the saved editor, not merely disappearance of the create button. Its photo upload displays a Merchant Media Addendum.
- Reopen a fresh menu tab and the individual item editor to verify price, description, category and availability. Library photo moderation is separate from item availability.

## Item promotion

- Observed route: `/merchant/marketing/bogo/create?store_id=<store-id>&merchandising=free_item`.
- The shared wizard supports BOGO and Free or discounted items. Under Customer incentive select Item discount to reveal percentage settings. Free item mode can default to a minimum subtotal.
- In the observed UI, 20%, 25%, 30% and Custom were available; the menu did not expose `[role=option]`. Use its screenshot-visible controls.
- Newly saved, in-stock items may be absent from the promotion picker even after a fresh wizard load. This is not proof that the menu save failed. Verify the menu separately, then retry the picker after propagation. Do not substitute other items or report an active campaign while the intended selection is unavailable.
- Recheck exact selected items, percentage, audience, schedule, ongoing/end-date setting and fees before accepting terms. A preview or prepared wizard is not launch evidence.

## Diagnosing picker/catalog mismatch

- The item picker can retrieve its full candidate list from POST `/unified-gateway-dash/ax_portal/ads/v1/products/search`, then filter search text locally. Its request includes `PRODUCT_CLASSIFICATION_MENU_ITEM`, search-term and merchant-PDRN filters, and menu-item search options. Inspect the actual observed request; do not invent eligibility or overwrite responses to inject missing products.
- A fresh successful backend search can still omit a new item that is already visible on the public storefront. Treat marketing search and menu publication as separate systems; escalate or wait for indexing rather than recreating the item.
- Public store search may require Enter; item cards are lazy-rendered when scrolled into view.
- Photo upload may report Uploaded before the preview editor appears. Wait for Preview and adjust your photo, inspect framing, then Done. A later editor message can say the photo is visible while continuing moderation remains active. Preserve that distinction in completion reports.

- A candidate can be present but marked Ineligible. Hover its status to reveal the reason; “Missing item photo” was observed. This differs from a newly created item being entirely absent. The corresponding marketing product record can have an empty `details.display_info.photo_url` even when Menu Manager reports a visible photo. Record missing candidates and ineligible candidates separately, and recheck after moderation/catalog propagation.

## Fixed-date offer verification

- Post-creation success language may say the campaign is live even when it starts in the future. Reopen campaign Details and verify Scheduled, exact selected item/percentage and start/end dates.
- Detailed times may explicitly use PT. Preserve the displayed timezone in evidence and compare the actual restaurant opening hours before interpreting the requested date window.
- Changing the first date can rerender the second field; obtain fresh UI state before editing the end date.
