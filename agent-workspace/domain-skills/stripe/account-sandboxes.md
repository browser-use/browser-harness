# Stripe account Test mode and sandboxes

Stripe's new-account onboarding can expose two distinct test environments:

- The account's classic Test mode keeps the main account ID and uses URLs shaped
  like `https://dashboard.stripe.com/{account_id}/test/...`.
- Choosing **Go to sandbox** during onboarding can create an additional sandbox
  with its own account ID and API keys.

Do not assume that the environment opened by the onboarding flow is the main
account's Test mode. Before creating products, prices, or webhooks:

1. Read the account ID from the URL.
2. Open `/{main_account_id}/test/apikeys`.
3. Verify the API key by retrieving `/v1/account` and comparing its `id` with
   the intended main account ID.

Useful stable routes:

- `/{account_id}/test/apikeys` — Test mode API keys
- `/{account_id}/test/settings/account` — account display name
- `/{account_id}/test/settings/payment_methods` — payment method configuration
- `/{account_id}/test/settings/tax` — Stripe Tax settings

The initial **Business name** onboarding field can replace the display name
shown in the account switcher. Restore a product-specific display name under
**Settings → Business → Account details** if the legal name makes sibling
product accounts indistinguishable.
