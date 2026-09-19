# Gmail safe-sender filter

Use only when the user authorized the email-settings change or it is a necessary, narrow step in an authorized workflow. Verify the Gmail account in the page title or account profile first.

- The account's Settings > Filters and Blocked Addresses page provides **Create a new filter**.
- Enter the exact authorized address in **From**, then choose **Create filter** (not Search).
- Select only **Never send it to Spam** for a safe-sender rule. Do not enable forwarding, deletion, archive, mark-as-read, or retroactive changes unless separately requested.
- Confirm the exact sender and checked actions before saving.
- The creation toast can appear while the settings list still shows its earlier empty state. Reopen or reload the filter settings and wait for the saved row. Require both `Matches: from:(...)` and `Do this: Never send it to Spam` as readback evidence, not just the toast.
- Long filter dialogs may place Create filter below a short viewport. Prefer a temporary taller CDP viewport or scrolling the actual container, then recompute geometry. Restore viewport overrides afterward.
- Browser zoom can make screenshot pixels differ from CSS coordinates. Re-read `page_info()` and target bounding rectangles after resizing; do not reuse coordinates from the earlier screenshot.
