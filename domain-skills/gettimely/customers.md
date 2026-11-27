# Timely (app.gettimely.com) — Customers, appointments, invoices (JSON endpoints)

The customer directory is a Knockout SPA backed by real JSON endpoints. Cookie
auth only; copy the session cookies out of the tab (`Network.getCookies`) and
hit these from Python with a thread pool — ~10 customers/s at 6 workers.

## Endpoints

| What | URL | Notes |
|---|---|---|
| Customer directory | `/CustomerData/CustomersJson?term=&page=N&useAzure=false` | 51 per page, `{hasMore, customers:[{id, fullName}]}`. Empty `term` lists everyone. |
| Customer record | `/Customer/CustomerJson/{customerId}` | Profile + `notes[]` (full text), `invoices[]`, `products[]`, `concessions[]` (packages), `giftVouchers[]`, `credits[]`, counts `totalPastAppointments`, `totalFutureAppointments`, `TotalLogEntries`, `customerImageCount`, `customerDocumentCount`. |
| Past appointments | `/Customer/CustomerPastAppointments?customerId=&pageNumber=0` | 20 per page, 0-based. `StartDate` is `/Date(ms)/`. `IncludedServices[]` has service, staff, price, start/end. Status flags `IsStatusCancelled`, `IsConfirmationDidNotShow`, `IsConfirmationAttended`, `IsInvoiced`, `IsPaid`, `InvoiceId`. |
| Future appointments | `/Customer/CustomerFutureAppointments?customerId=&pageNumber=0` | Same shape. |
| Change log | `/CustomerData/GetCustomerLogs?customerId=&pageNumber=0` | 20 per page; `entryChanges[{propertyName, originalValue, currentValue}]`. |
| Rewards | `/Rewards/GetCustomerTransactions?customerId=` | `customerRewardsTransactions[]`, 10 per page. |
| Messages per customer | `/Message/MessagesByCustomerId?messageTypeId=<1 sent|2 received>&customerId=` | HTML. |
| Invoice list | `POST /Billing/Invoices` form `SalesPageType=ViewInvoices&SelectedDateRange=Specific&StartDate=1 Jan 2015&EndDate=31 Dec 2026&search=` | One HTML table, no paging, every invoice in range (`/Billing/ViewInvoice/{id}` links, status label, amount). No anti-forgery token needed. |
| Invoice detail | `/Billing/ViewInvoice/{invoiceId}` | ~150 KB HTML. Line items are `tr.table-card` rows with `td[data-label]` (Staff, Account, Type, Description, Quantity, Unit price, Tax, Total GBP). Payments appear as text `Payments <date> | <amount> | <method> |`. No JSON variant exists (`/Billing/InvoiceJson`, `/BillingData/*` 404). |

## Traps

- `js()` in-page fetch loops time out; do bulk work from Python with the cookies.
- `/Billing/InvoiceEdit/{id}` is a 150 KB form full of `<select>` service lists — strip `<select>` before text-extracting or you will think the invoice has 100 line items.
- Zero-amount "Paid" invoices (credit redemptions, complimentary) have no Payments block.
- `/promote/smsmarketing` (campaign stats) can be `Error/Unauthorised` even for an admin login; marketing sends still show in Sent messages with `Type=Marketing`.
