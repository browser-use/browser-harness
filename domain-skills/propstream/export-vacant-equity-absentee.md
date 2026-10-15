# PropStream — multi-filter export (Vacant + High Equity + Absentee)

Demonstrates **stacking multiple Lead-List tiles + at least one Owner-Info filter** in a single export run. The "easy deal" combo for wholesalers: a property that is *vacant* (nobody living there), *high-equity* (owner has skin in the game), and *absentee* (owner doesn't live nearby, so they're less attached / more willing to sell).

Verified live 2026-05-18 on ZIP 63116 — partial validation: Vacant filter applied cleanly, exported 1,437 records (92% sale-date coverage). High Equity tile toggling proved state-sticky (see gotchas). Multi-tile mechanics work; the SOP below captures the deterministic sequence.

## URL patterns

Same as [export-cash-buyers.md](export-cash-buyers.md).

## Flow

```text
1. new_tab("https://app.propstream.com/search")
2. **HARD RESET FIRST.** Click "Clear All" before opening Filters. If filters
   from a previous run are sticky in the session, tile clicks will TOGGLE
   them (re-clicking turns them off). Clear All guarantees a known state.
3. Enter the ZIP / city in the location bar (≈ 230, 24) and press Enter.
   Wait for the "View N Properties" header to populate with the unfiltered
   total. This is the baseline.
4. Click "Filters" (≈ 891, 24). The Lead Lists panel opens.
5. Click "Vacant" tile. Verify View N Properties drops to the Vacant count.
   selector: <p|span>Vacant</p> → ancestor with offsetWidth 150–250 → click()
6. Click "High Equity" tile. Verify View N Properties drops again — to the
   *intersection*. If it does NOT drop further, the tile toggled the previous
   filter off; check by looking at the count header chips at the top of the
   page (you should see "N High Equity" highlighted, not "0 High Equity").
7. Scroll down inside the filter panel to "Owner Information & Occupancy"
   section → "Absentee Owner Location". Toggle "Out of State" and/or
   "Out of County" (multi-select). The View N count narrows further.
     selector strategy: find a text node "Absentee Owner Location" via
     querySelectorAll then scrollIntoView; then locate "Out of State" text
     within the same parent.
8. Click "View N Properties" to load the list.
9. Master select-all (≈ 865, 199).
10. Actions (≈ 1165, 199) → Save (≈ 1155, 283).
11. In modal: type "vacant-equity-absentee-<zip>-<run>" → click
    "(Create as New List)" → click Save (≈ 699, 513) → wait for spinner.
12. goto_url("https://app.propstream.com/property/group/0")
13. Dismiss "PropStream Updates" welcome modal (click "Close" ≈ 625, 738).
14. Click the sidebar magnifying-glass at ≈ (299, 453) → type list name into
    "Enter Search Name" input that appears at ≈ (260, 497). The list filters
    to the matching list, bringing it into view at ≈ (215, 610).
15. Click the list at the new visible position.
16. Master select-all on the list page (≈ 422, 191) → Export (≈ 593, 151).
    File downloads silently to ~/Downloads.
```

## Output

`~/Downloads/Property Export <list-name>.xlsx`

Same 75-column shape. Useful distinguishing fields for the "easy deal" combo:

| Column | What it tells you |
|---|---|
| Total Open Loans | Should be 0 most of the time (high-equity → free-and-clear or near-free) |
| Est. Equity / Est. LTV | Confirms the high-equity filter |
| Owner Occupied | Should be **No** (absentee filter) |
| Mailing State vs State | Absentee = mailing state ≠ property state |
| Vacant | (PropStream's vacancy flag — should be **Yes**) |

## Gotchas — multi-filter specific

- **Tile clicks TOGGLE**, they don't guarantee ON. If a filter was on from a previous interaction, clicking it again turns it OFF. Always do **Clear All before applying** the desired stack.
- **Verify each step by reading View N Properties.** It should drop monotonically as filters narrow. If N stays the same or goes UP after a click, that click toggled OFF a previous filter — un-toggle it.
- **Header count chips at the top of the page** (the "264 MLS | 15 Pre-Foreclosures | …" strip) are *unfiltered totals* for the current ZIP scope. They are not applied-filter indicators. The applied-filter signal is the "View N Properties" button at the top-right.
- **Absentee Owner Location lives in "Owner Information & Occupancy"**, not in Lead Lists. You have to scroll the filter panel down. The Lead Lists section is the top-most; Owner Info is several sections below.
- **PropStream Updates welcome modal** fires on every navigation to `/property/group/0`. Close it before any sidebar / table interaction.
- **Marketing Lists sidebar is virtualized.** A newly-created list may be below the visible 9-or-so items and not reachable by scroll. Use the in-sidebar search (magnifying-glass icon next to "Marketing Lists" header) to filter the sidebar to your list name.

## Replay

Not yet packaged. The multi-filter combinatorics make a generic
`propstream_export(query, list_name, lead_list_tiles=[...], owner_filters={...})`
the natural next iteration of the harness skill.
