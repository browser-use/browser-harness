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
