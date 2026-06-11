# ads.google.com — navigation & conversion-action auditing (2026 UI)

## URL patterns that work (deep-link with the account query string)

Every authenticated page needs the account params — copy them from whatever
Ads tab is already open: `?ocid=...&euid=...&__u=...&uscid=...&__c=...&authuser=0`.
`campaignId=...` scopes campaign pages.

- `/aw/overview?campaignId=...&ocid=...` — campaign overview + diagnostics panel
- `/aw/campaigns?ocid=...` — campaign table (status, budget, bid strategy column)
- `/aw/changehistory?ocid=...` — full change history (who paused/edited what, when)
- `/aw/conversions?ocid=...` — conversions Summary (goals view)
- `/aw/datamanager?ocid=...` — shows linked GTM container + GA4 property

URL guesses that 404 or dead-end — navigate via the UI instead:
- `/aw/conversions/summary` (404), `/aw/tag` (404), `/aw/settings?campaignId=` ("page doesn't exist")

## Conversion actions table is buried

Goals → Conversions → Summary shows **goal-group cards** — the action names
inside the cards are NOT links (clicking does nothing). The real table:

1. Scroll the Summary page past the goal cards to the **"All your goals"** section.
2. Click **"View all conversion actions"** (top-right of that section).
3. The table shows source (Website tag vs "Website (Google Analytics (GA4))" import),
   Tracking status, Primary/Secondary, counts.
4. Default filter is `Status: All enabled` — **Removed actions are hidden**. Click the
   status chip → "All" to reveal removed website-tag actions (a gtag `send_to`
   label pointing at a Removed action silently drops conversions — worth checking
   when client code fires conversions but the account shows zero).

## Campaign settings

No standalone settings URL — open `/aw/overview?campaignId=...` and click
**"Campaign settings"** in the top bar. It opens a slide-in panel (takes a few
seconds to render; first screenshot may show an empty panel with a progress bar).
Rows (Bidding, Budget, …) expand in place; "Change bid strategy" → focus dropdown
(Conversions / Conversion value / Clicks / Impression share) → optional max-CPC
checkbox → Save button appears at the row's bottom-right.

## Traps

- **AI chips hijack clicks**: pages embed "Ask Advisor" suggestion chips
  ("What were my most impactful changes?"). A misclick opens a right-side chat
  panel that starts running a query. Its Close button is a Material icon button
  (`aria-label="Close"`) — find it via DOM, don't guess coordinates.
- **Notifications bell dropdown** sits where panel close buttons tend to be;
  Escape closes it.
- **Screenshot scale varies**: `Page.captureScreenshot` may return a 0.5×-scaled
  PNG of the CDP viewport (e.g. 756px-wide image for a 1512px viewport). Always
  compare against `page_info()` w/h and multiply click coordinates accordingly.
- Much of the UI is Angular with obfuscated classes and text split across
  elements — `textContent.trim()===...` matching on leaf nodes often fails;
  prefer coordinate clicks guided by screenshots, or search for `aria-label`s.
- Change-history row chevrons are finicky; the row data (who/when/what) is
  readable from the collapsed table anyway.
