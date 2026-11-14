# OpenAI Ads Manager (ads.openai.com)

Beta product for ads shown in ChatGPT. Account-scoped URLs: `/manage/campaigns?act=<ad account id>`.

## Structure

Campaign → Ad group → Ad. Settings live at different levels:

- **Campaign**: name, type (Standard/product feed), objective (Clicks), locations, daily budget (defaults to `100.00`).
- **Ad group**: name, max CPC bid (defaults to `4.00`, shows a live "Strong/Weak Delivery" competitiveness signal), Default Ad Destination URL, context hints textarea (semantic conversation matching, not exact-match keywords).
- **Ad**: name, headline (50 max), description (100 max), destination URL (inherits ad group default), one square image (PNG/JPG ≥256×256).

## Create flows

- `+ Create` button (top right of Campaigns page) → dropdown: Create campaign / Create ad group / Create ad / Upload bulk.
- "Create campaign" opens a 3-step wizard (Campaign → Ad Group & Ads → Review) in a full-screen modal. Final button is **Publish** with an "agree to the Advertising Tool Terms" note; publishing shows "Applying changes / Creating ads… (0/1)" then a toast: "Campaign created successfully with 1 ad group and 1 ad."
- "Create ad" alone opens a small modal that requires picking parent campaign + ad group — no budget/CPC controls there.

## Locating fields

Inputs have no stable ids; locate by placeholder / value:

- Campaign name: placeholder `New traffic campaign`
- Budget: input with value `100.00` (select-all + retype)
- Ad group name: placeholder `New ad group`
- Context hints: textarea whose placeholder contains `context hints`
- Ad name: placeholder `New ad`
- Description: placeholder `Enter ad description`

Headlines >~40 chars trigger "Copy may be truncated in some placements." (soft warning, non-blocking). Same warning appears for long descriptions.

## Trap: stuck image attachment

The "Ad images" slot can show a grey square tile with an X above it. That tile is a **stuck upload** (`_ImageAttachment_` with a frozen `_TrackProgress_` spinner), not an upload button:

- While it exists there is **no `input[type=file]` in the DOM**, and clicking the tile does nothing (no `Page.fileChooserOpened` even with interception enabled).
- Fix: click the tile's X (small button absolutely positioned at its top-right corner). A real `input[type=file]` plus an "Upload image" label appear; then `DOM.setFileInputFiles` on that input works (`upload_file()` helper). Uploaded state: tile shows the image, preview card thumbnail updates.

## Misc

- Table cells (Status, Impressions, …) load async as skeleton placeholders; poll row text until `Serving` appears before reading state.
- Account display name, timezone, and advertiser logo: Settings → General → Account Info (Edit). The logo is the small avatar shown next to the advertiser name on ad preview cards.
- A yellow "Complete business verification to keep ads serving" banner persists account-wide until verification is done; ads serve during the grace period.
- Ad previews render the image as a tiny (~72px) square thumbnail next to the copy — creative is closer to a search-ad favicon than a Meta-style banner.
