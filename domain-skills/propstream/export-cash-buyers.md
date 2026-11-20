# PropStream — export cash-buyer list

Drives PropStream's web app to filter by Cash Buyers in a target ZIP / city / county, save the result as a marketing list, then download the XLSX from the list page. Uses the account-holder's existing subscription — no extra credits charged unless the optional skip-trace toggle is checked.

Verified live 2026-05-18: ZIP 63116 → 2,559 cash-buyer rows × 75 columns. **Last Sale Recording Date 100%**, Last Sale Amount 79%, equity / LTV / property type / APN ~95%+. Phones/emails are blank unless skip-trace is run separately.

## URL patterns

| Page | URL |
|---|---|
| Login | `https://login.propstream.com/?prompt=login` |
| Search / map | `https://app.propstream.com/search` |
| Saved-list / "My Properties" | `https://app.propstream.com/property/group/0` |

## Pre-flight

- Browser-harness daemon attached to the user's Chrome (`browser-harness --setup`).
- User is logged into PropStream in the active Chrome profile.
- **Do not auto-fill credentials.** If the active tab lands on `login.propstream.com/...`, stop and ask the user to log in.
- On first visit to `/property/group/0` a "PropStream Updates" modal appears — click the **Close** link (default position ≈ y=738 in 1251×817 viewport).

## Flow

```text
1. new_tab("https://app.propstream.com/search")
2. Click the "Filters" toggle in the top toolbar
     selector: text === "Filters" with width 80–120, near top-right of header
     default coords (1251×817 viewport): (891, 24)
3. The right-side panel opens to "Lead Lists". Click the "Cash Buyers" tile
     selector: walk up from <p|span>Cash Buyers</p> to the parent DIV with
               offsetWidth 150–250 (the clickable tile is the wider ancestor).
     `.click()` works; coordinate click is unreliable because the tile spans
     to the right edge of the viewport.
4. Click the top-left location input and type the target query (ZIP, city, etc),
   then press Enter:
     selector: input[placeholder^="Enter County"]  at ≈ (230, 24)
     query examples: "63116", "Saint Louis MO", "Cuyahoga County OH"
5. Confirm the filter chip + scope changed: the top-right button now reads
   "View N Properties" where N is the count for (ZIP × Cash Buyers).
6. Click "View N Properties" to enter the list view. The panel changes to show
   "N PROPERTIES" with an Actions dropdown.
     coord ≈ (1176, 34)
7. Click the master select-all checkbox at the top of the property cards
     selector: first checkbox-class element with width ≈ 24, y near 199
8. Click "Actions" → "Save" inside the right panel
     Actions DIV at ≈ (1165, 199); Save row at ≈ (1155, 283)
   The "Save" inside Actions opens an "Add to Marketing List" modal — NOT a
   direct export. Direct Export from the search-results view does not exist.
9. In the modal:
     - Click the input "Select or Type to Create a New List" (≈ 615, 382)
     - Type a unique list name (e.g. "cash-buyers-63116-test")
     - Click the "(Create as New List)" suggestion that appears below
     - Do NOT tick "Skip Trace Selected Properties" unless phone enrichment
       is desired — that charges credits.
     - Click "Save" button (≈ 699, 513). Wait for the loading spinner to clear
       (1–10s depending on selection size).
10. **Capture the new list's ID from the Save POST response** via CDP Network
    (see [cdp-list-id-capture.md](cdp-list-id-capture.md)). This is the
    reliable replacement for the old sidebar-clicking step, which fails when
    the account has more than ~9 saved lists (virtual-scroll renders the
    newly-saved list below the fold and `scrollIntoView` doesn't work).
11. Navigate directly to the list:
      goto_url(f"https://app.propstream.com/property/group/{list_id}")
    Close the "PropStream Updates" welcome modal if present.
12. Click the master select-all checkbox on the table header (≈ 422, 191).
    The toolbar "Export" button transitions from disabled (opacity 0.5) to
    enabled (opacity 1).
13. Click "Export" (≈ 593, 151). The file downloads silently to ~/Downloads
    as: `Property Export <list name>.xlsx`. No "save as" prompt appears.
```

## Output

`~/Downloads/Property Export <list-name>.xlsx`

75 columns. The ones that matter for cash-buyer ingestion:

| Column | Coverage | Notes |
|---|---|---|
| Address / City / State / Zip / County / APN | 100% | Property identification |
| Owner 1 First/Last Name | 43% / 100% | First is blank for entities |
| Owner 2 First/Last Name | 18% / 21% | Joint ownership when present |
| Mailing Address / City / State / Zip | 100% | Buyer's mailing — feeds dedup |
| **Last Sale Recording Date** | **100%** | The cash-sale date |
| **Last Sale Amount** | **79%** | The cash-sale price |
| Total Open Loans | 98% | Cash-buyer confirmation (expect 0) |
| Est. Equity / Est. LTV / Est. Value | 88-97% | Buyer balance-sheet signal |
| Bedrooms / Bathrooms / Sqft / Year Built | 52-95% | Buy-box inference |
| Do Not Mail | 99.6% | DNC compliance |
| Phone 1-5 / Email 1-4 | 0% by default | Empty unless skip-trace was run |

## Gotchas

- **The Export button on the search results page does not exist.** The only place to export is the saved-list page (`/property/group/0` → click list name → Actions/Export). Save first, export second.
- **Master select-all is required before Export enables.** Top-of-table checkbox at ≈ (422, 191). Without it the Export button shows opacity 0.5 / `disabled=true`.
- **Two visible "Cash Buyers" labels collide.** After the filter applies, a chip appears at the top of the page (left of the search bar) reading "N Cash Buyers". Don't confuse it with the tile inside the filter panel. The chip's parent class begins `src-components-HeaderSearchItem` — that's *applied*, not a fresh tile.
- **The "View N Properties" count changes when the filter toggles.** If you click the Cash Buyers tile twice, you toggle the filter off and the count jumps back up. Verify the chip is present before proceeding.
- **PropStream Updates welcome modal** shows on `/property/group/0` once per session. Close it with a text-match click on "Close" (default ≈ 625, 738).
- **Save spinner** can take 1–30 seconds depending on list size (2,559 took ~2s). Poll for the "Loading..." text in the header before continuing.
- **Output format is XLSX, not CSV.** Parse with `pandas.read_excel` and `openpyxl`. The PropStream marketing docs call it "Export CSV" but the file extension is `.xlsx`.
- **Skip Trace toggle in the save modal** costs credits per row. Leave unchecked unless phone enrichment is the explicit goal — phone columns will then populate in the exported file.
- **Login wall**: agent must never type credentials. If redirected to `login.propstream.com`, stop and ask the user.

## Replay (rough Python)

Not yet packaged as a one-shot `Replay` block — the workflow is interactive
enough (waits, modal dismiss, list naming) that the next iteration will turn
this into a parameterized `propstream_export(query, list_name)` function. For
now, follow the Flow above by hand with browser-harness.
