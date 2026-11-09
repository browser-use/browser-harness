# Uber Eats Manager — items and selected-item offers

## Item editor

- Menu Maker routes: `/manager/menumaker/<restaurant-id>/items`, `/items/create?uuid=<item-id>`, and `/items/<item-id>`.
- Name: `input[name=name]`; description: `textarea[name=description]`; price: `input[type=number]`; suspension: `input[name=itemSuspensionState]`; photo upload: `input[type=file]`.
- Category input is a combobox. Type a category and choose the exact visible option; typing alone does not assign it.
- Photo upload can outlast the page load. Verify a loaded image with nonzero `naturalWidth` before saving. A saved photo can remain under review.
- Save can change the route and show success while leaving a beforeunload handler attached. Open the saved item URL in a new tab for independent readback; navigating the just-saved editor can trigger Chrome's Leave site dialog. Do not dismiss such dialogs until unsaved changes have been accounted for.

## Percent-off-items offer

- Marketing creation route: `/manager/marketing/create/offers/discounted-items`.
- Add items opens a selector with per-item discount menus. The observed default was 30%, regardless of the requested discount.
- Await each React update before opening the next item's discount selector. Rapid click loops can repeatedly operate on a stale row. Verify every item name, original price, discounted price and percentage afterward.
- The initial selector uses semantic buttons and `[role=option]`. The main form's discount control may not expose a button role; use a fresh screenshot to locate it.
- Dynamic audience discounts can be checked by default. Verify both dynamic-discount controls when the owner requested a fixed discount for everyone.
- Inspect actual dates, audience, redemption fee and terms before launch. A configured form is not an active offer; reopen the resulting campaign independently.
