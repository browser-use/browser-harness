# Duffel team activation

## Team and country selection

- Dashboard routes are scoped to a team slug: `https://app.duffel.com/<team>/test`.
- Check the team's incorporation country before filling verification details. An Australian team can lead to Stripe Connect forms requiring an ABN/ACN and an Australian address; those country fields may be locked.
- A business incorporated elsewhere needs a team configured for its actual country. The `/create-team` form offers incorporation country and settlement currency separately. Currency availability does not imply incorporation country availability.
- Do not substitute another country's registration identifiers to make a mismatched form pass validation.

## Native activation flow

Observed for a New Zealand team:

1. `/<team>/activation/business` — business, registered address, legal entity, and key contact details.
2. `/<team>/activation/card` — save a payment card, then proceed to review.
3. Final team activation is a separate step; completing the business form does not establish live API access.

The business form uses inputs named `name`, `tradingName`, `registrationNumber`, `taxIdentificationNumber`, and `keyContactFirstName`, `keyContactLastName`, `keyContactJobTitle`, `keyContactEmail`. Address input names begin with `registeredBusinessAddress`. The business-type select is named `type`; the address-country and legal-entity-country selects may be unnamed. Identify each country select by its label/section, and verify both values.

Company registration number and tax identification number are separate required fields. For NZ, use the company's own IRD/GST number in the tax field, verified against a company document; do not substitute an NZBN or a director's personal IRD number.

`Save and continue` advances to payment setup after valid business details are saved. Card details are inside a Stripe iframe titled `Secure card payment input frame`. The review control remains unavailable until a card is saved. Check current UI for any charges or commitments before proceeding.

## Browser mechanics and safe inspection

- Pin the target ID and attach explicitly when other browser work may change the harness's default session.
- For replacing text, focus the input, select its existing contents with `HTMLInputElement.select()`, then use `Input.insertText`. Verify the resulting value; a select-all keyboard shortcut may fail and append text instead.
- SPA navigation can finish after the click returns. Read the resulting route and visible UI in a subsequent call.
- Inspect visible `document.body.innerText`. Do not dump a detached body's `textContent` or page bootstrap JSON: those can include authentication and session data.
- Stripe Connect onboarding may live in nested `connect-js.stripe.com` frames. If the top-level text is only a shell, inspect the frame tree and use the relevant frame context, or interact visually through the compositor.

Official background: [Getting started](https://duffel.com/guides/getting-started). Recheck current country support and activation requirements rather than assuming all teams use the same verification flow.
