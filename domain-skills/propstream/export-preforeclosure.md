# PropStream — export Pre-Foreclosure / NOD list

Mirrors the cash-buyer flow exactly — only the **lead-list tile** changes. The output XLSX has the same 75-column shape; the semantic shift is from *cash buyers* (deal exits) to *motivated sellers* (deal sources).

Verified live 2026-05-18: ZIP 63116 → 15 rows × 75 columns. 87% sale-date coverage. **Open loans avg 1.6, zero-loan count 0/15** — every pre-foreclosure record has an active mortgage, as expected.

## URL patterns

Same as [export-cash-buyers.md](export-cash-buyers.md).

## Pre-flight

Same as cash-buyers. Plus: be aware that the **PropStream Updates welcome modal** fires on *every* navigation between `/search` and `/property/group/0`, not just first visit. Dismiss it (Close link, default ≈ y=738) at every transition.

## Flow

Steps 1, 2, 4, 5 are identical to cash-buyers. The differences:

```text
3. Lead Lists tile → "Pre-Foreclosures" (instead of "Cash Buyers")
     selector: <p|span>Pre-Foreclosures</p> → walk up to ancestor with offsetWidth 150–250
6. View N Properties — for ZIP 63116, expect a much smaller N (15 vs 2,559 cash buyers)
9. List name in the modal — use a distinct name like "pre-foreclosure-63116-<run>"
```

## Output

`~/Downloads/Property Export pre-foreclosure-63116-test.xlsx`

Same 75 columns. Key distinguishing fields for foreclosure ingestion:

| Column | Coverage | Notes |
|---|---|---|
| **Foreclosure Factor** | High | PropStream's distress score |
| **Lien Amount** | High | Outstanding lien total |
| **Pre-Foreclosure Type / Recording Date / Auction Date** | High | Available in the Filter side-panel; not in the default export but accessible via "Customize Columns" before export |
| **Total Open Loans** | 100% | Expect ≥1 for valid pre-foreclosure rows |
| **Owner / Mailing Address** | 100% / 100% | Same as cash-buyers — direct outreach target |

Note: the **default export columns are cash-buyer-oriented**. To get the pre-foreclosure-specific fields (Default Amount, Auction Date, Recording Date), customize columns before clicking Export. The customization control is in the toolbar near Export.

## Gotchas

- All cash-buyers gotchas apply.
- **Welcome modal repeats on every nav** (didn't show up on first sample because the cash-buyers run happened all in one tab without leaving `/search`). Plan for dismissal between each export.
- **Open-loan count is the inverse signal** vs cash buyers: cash-buyer ingest rejects rows with `Total Open Loans > 0`; pre-foreclosure ingest should *require* `Total Open Loans > 0` (otherwise it's not a pre-foreclosure).

## Replay

Not yet packaged. Same parameterization opportunity as cash-buyers — once `propstream_export(query, list_name, lead_list_tile)` exists, this becomes one function call with `lead_list_tile="Pre-Foreclosures"`.
