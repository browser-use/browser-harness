---
name: mobbin-review-flows
description: Inspect Mobbin app flow libraries and recorded screens in an authenticated browser.
---

# Mobbin flow review

## Routes and discovery

- App libraries use `/apps/<app-slug-and-id>/<version-id>/flows`.
- The version component can be `_`; the site resolves it to a concrete recording version. Cite that resolved URL when recording a review.
- Individual flows use `/flows/<flow-id>?tab=screens`; opening one from a library displays a screen-gallery overlay. Escape returns to the library.
- Discover app and flow identifiers from the page, rather than deriving them from app names.

## Useful selectors

The library sidebar's flow buttons can have empty text content. Their accessible names are in `aria-label`, for example `button[aria-label="Settings"]`. Looking only at `textContent` misses them.

Flow links use `a[href*="/flows/"][aria-label]`. The label describes the flow and its parent (for example, `Plugins from Settings`). Extract both `aria-label` and `href` to keep source attribution attached to observations.

## Loading and verification

- The sidebar contains more flows than the currently mounted screen cards. Clicking a sidebar item scrolls the library to that group; a direct flow link opens its gallery.
- Navigation completion does not establish that the screenshot cards have loaded. Inspect the relevant mounted flow links and capture again after the target cards are present.
- An immediate capture after a long sidebar jump may show a blank content area. Do not interpret that capture as an empty flow or authentication failure.
- Screen images contain much more product detail than the page text. Visually inspect them; distinguish an indexed feature from a screen actually reviewed.
- This is a recording library. Do not claim a recorded feature is available to every current account or infer runtime implementation from a mock screen.

## Shared-browser research

Use a separate harness session and attach to the known Mobbin target. Background page inspection and `Page.captureScreenshot` do not require activating the user's Chrome window. Avoid a helper that also calls `Target.activateTarget` when the user needs to keep browsing elsewhere. Do not switch profiles or inspect unrelated tabs to recover a research screenshot.

Reuse the existing authenticated session. If it reaches a login wall, hand sign-in to the user; do not export cookies or put authentication data in this skill.
