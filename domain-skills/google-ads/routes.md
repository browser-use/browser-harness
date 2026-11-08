# Google Ads navigation and read-only extraction

## Account routes

- Start from an already authenticated Google Ads tab. Preserve the account context query parameters (`ocid` and `authuser`) when moving between routes.
- Campaigns: `https://ads.google.com/aw/campaigns`.
- A campaign name opens its ad groups at `/aw/adgroups?campaignId=<id>`.
- Campaign ads: `/aw/ads?campaignId=<id>`.
- Campaign keywords: `/aw/keywords?campaignId=<id>`.
- Search terms: `/aw/keywords/searchterms?campaignId=<id>`. The shorter `/aw/searchterms` route returns a Google 404.
- Conversion actions: `/aw/conversions`. If this opens the Goals summary, use `View all conversion actions` for the action table.
- Recommendation auto-apply controls: `/aw/recommendations/autoapply`. The `Manage` tab shows enabled recommendation types; `History` shows prior auto-applies. Cross-check consequential events in Change history.

## Table extraction

- The current tables use `.particle-table-row` rows and `ess-cell[essfield]` cells. Reading each cell's `essfield`, `innerText`, and descendant `aria-label` values yields a stable field-to-value map without relying on column position.
- Campaign enabled/paused state is exposed by an `aria-label` inside the row's `ess-cell[essfield="status"]`. Serving state such as `Limited by budget`, `Eligible`, or `Ended` is in `ess-cell[essfield="primary_status"]`.
- Rows are virtualized. If the footer count exceeds the rendered rows, scroll the main content with `Input.dispatchMouseEvent` (`type="mouseWheel"`) and read the rows again.
- Auto-apply checkboxes expose the current state as `[role="checkbox"]` with `aria-checked="true"` or `"false"`; do not infer selection from icon text alone.

## Interaction notes

- Google Ads can append a `Turn off ad blockers` warning while account data is still present. Wait for the table or summary metrics, then verify the actual data surface instead of treating the warning alone as a failed load.
- Clicking a campaign-name link may update the same target even when the anchor has `target="_blank"`; verify `location.href` after the click instead of assuming a new target was created.
