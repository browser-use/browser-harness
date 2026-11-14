# GoHighLevel phone numbers

## Location and inventory

Open `/v2/location/{locationId}/settings/phone_system?tab=manage` in the signed-in account. Confirm the location heading before changing its phone configuration. The phone inventory and purchase dialog load asynchronously. An early `No Data` state can precede populated results. Wait for the request to settle before treating the inventory as empty.

## Buying one local number

The Add Number button has ID `btn-add-number`. Choose **Add Phone Number** to open **Buy your Number**.

The number search matches any part of a number by default. Searching an area code can return different area codes and toll-free numbers containing the same digits. Open **Filter** and select the intended type. The type checkboxes have IDs `local` and `tollFree` and expose `aria-checked`. Both types can be selected initially. The search field placeholder is `Search By digit or phrases`. Apply uses `btn-apply`.

Confirm the candidate's complete number, locality, type, capabilities and monthly price in the rendered row. Available number rows use native `input[type=radio]` controls. Exactly one selected number should appear in the purchase summary. `btn-move-numbers` is **Proceed to Buy** and submits the purchase. Use the user's authorized merchant, purpose and spending limit.

A successful purchase shows **Number purchase successful!** and inserts the number into **Manage Numbers**. Reconcile that inventory after a timeout or ambiguous response before attempting another purchase. The dialog can remain visible after the successful purchase.

## Configuration

The newly purchased number may inherit a purchaser-based friendly name. Its row has an actions cell with `data-col-key="phone-numbers-actions"`. Open that action menu and choose **Edit Configuration**.

The friendly-name input has placeholder `Friendly name of the Phone Number`. **See More Options** expands call routing. **External Phone Number** provides a telephone input with placeholder `Input Phone`. Team-member selectors load asynchronously and may initially display a loading indicator. Choose the intended routing destination using the location's available team members or an authorized external destination.

Multiple visible routing panels can contain Save buttons. Scope the action to the intended active configuration panel. Verify the friendly name and forwarding number in the inventory after saving and a fresh load.

## Voice and messaging status

The purchase confirmation can report **A2P Registration in progress**, while the inventory banner reports an incomplete A2P registration. Report SMS readiness after verifying provider registration approval. An actual inbound call is needed to verify the complete voice path.
