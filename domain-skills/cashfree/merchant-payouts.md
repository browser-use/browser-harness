# Cashfree Merchant Dashboard — Payouts (merchant.cashfree.com)

React SPA. DOM selectors work, but custom selects don't respond to plain coordinate clicks reliably — dispatch `mousedown`/`mouseup`/`click` on the option element.

## Getting a statement / transfer data

There is no inline date-filtered transaction table worth scraping. Use **Reports**:

1. Sidebar → `Reports` (`/payouts/reports`).
2. `Report Type` select → e.g. **Account Statement** (all credits + debits + per-txn service charge & tax — best single export). `Transfer` = payouts only.
3. **Date Range** select → `Custom Date Range` opens a dual-month calendar. Click start day, end day, then `Apply`.
4. **Fund Source is required.** The `Generate Report` button is styled active but stays `disabled=true` until a Fund Source is chosen from its dropdown. If clicks seem ignored, check `button.disabled` via JS.
5. Report lands in the "Generated Reports" table (status `Processing` → ready in ~1 min). Download via the `⋮` actions menu → `Download`. CSV downloads directly.

## Account Statement CSV shape

Columns: `Added On, Debit/Credit, Particulars, Charged Amount (INR), Amount (INR), Service Charge (INR), Service Tax (INR), Closing Balance (INR), Event Id, Remarks`.

- `Particulars` values: `PAYOUT_TRANSFER` (user payouts), `SELF_WITHDRAWAL` (money pulled back to bank).
- Wallet loads appear as credits; payouts as debits. Service charge + tax are per-transfer (flat ₹ per IMPS/UPI transfer, so fee % is large on small tickets).

## Traps

- The date-picker dropdown closes on stray clicks and the click can land on checkboxes *behind* the (transparent-edged) popover — re-verify checkbox state after any miss.
- "Choose Columns" checkboxes: `Show All` re-checks everything in one click.
