# Trip.com - Receipts and Company Invoice Details

Field-tested on `www.trip.com` in September 2026 with a signed-in account.
The hotel and Things to Do/eSIM flows use different receipt systems.

## Useful routes

| Purpose | Route pattern |
| --- | --- |
| All bookings | `https://www.trip.com/order/all` |
| Saved billing details | `https://www.trip.com/passenger/invoice` |
| Hotel booking detail | `/hotels/ctorderdetail?orderid=...` |
| Hotel receipt status/editor | `/cw/hotel/ctOrderDetailPages/ServiceTrackPage.html?orderId=...` |
| Things to Do/eSIM detail | `/xthings-to-do/orderdetail?orderid=...` |

Buttons on the booking list and detail pages frequently open a new tab. After
clicking, inspect `list_tabs()` and switch to the new target instead of waiting
for the current tab to navigate.

## Save company billing details

Open **Account > Receipt & invoice options > New**. For a company profile the
stable labels are:

- `input[aria-label="Company name"]`
- `input[aria-label="Tax ID"]`
- `[contenteditable="true"][aria-label="Company address"]`

The additional-information section must be expanded before the address editor
is present. Phone and bank fields are optional. Saving this profile makes it
available to eligible booking flows, but it does not add company details to
every product-specific receipt automatically.

## Hotel receipts

1. Open the hotel booking detail.
2. Click **E-receipt**. This opens the receipt status page in a new tab.
3. If a receipt was already sent, use **Modify**.
4. Fill the company name, tax ID, address, and delivery email, then submit.

The editor is a React Native Web-style sheet. Its visible text fields have no
useful names or ARIA labels, but their order is stable:

1. Guest name
2. Company name
3. Tax ID
4. Address
5. Email

After submission, the status page shows **Enterprise**, the company details,
the amount, and a new sent timestamp. The delivered PDF contains the seller
identity, booking number, company name/address/tax ID, stay dates, and total
paid.

## Things to Do and eSIM receipts

The Things to Do/eSIM detail page has a **Send e-receipt** action. It opens a
portal modal matching `.atom__modal_comp` and asks only whether the booking
email address is correct. There are no company fields in this flow.

The confirmation action calls:

```text
POST /restapi/soa2/14921/json/sendElectronicReceipt
```

The request body contains the `orderId`; do not record or replay cookies,
tokens, or generated request headers. A successful interaction dismisses the
modal and emails the PDF. In the tested eSIM flow, the PDF contained the
booking number, amount, issue/payment dates, and product description, but no
buyer company name, address, or tax ID. A separate support request was needed
for a company document.

## Interaction quirks

- Booking cards are `div[role="link"]` elements rather than anchors.
- The Taro action buttons use `onMouseDown`/`onMouseUp` wrappers. If an ordinary
  DOM `.click()` appears to do nothing, use compositor input and then inspect
  for `.atom__modal_comp`; the modal text may be appended near the end of
  `document.body.innerText`.
- Receipt actions often open new tabs. Never assume the current page changed.
- Do not expose booking PINs while collecting receipt data.
- Attractions & Tours human chat may have fixed hours. In the tested locale it
  reported `09:00-02:00+1 UTC+8`; outside that window the AI assistant did not
  resolve invoice requests.
