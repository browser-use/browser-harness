# Stripe account Test mode and sandboxes

Stripe's new-account onboarding can expose two distinct test environments:

- The account's classic Test mode keeps the main account ID. Its current-account routes use `https://dashboard.stripe.com/test/...`. Account-specific links can include `/{account_id}/test/...`.
- Choosing **Go to sandbox** during onboarding can create an additional sandbox
  with its own account ID and API keys.

Do not assume that the environment opened by the onboarding flow is the main
account's Test mode. Before creating products, prices, or webhooks:

1. Confirm the intended account in the account switcher and read its ID from account settings.
2. Open Test mode and its API keys page. Do not infer account identity from the URL alone.
3. Use the intended Test mode secret key for an authenticated `GET https://api.stripe.com/v1/account` request.
   Send the key in `Authorization: Bearer <test_secret_key>`. Compare the response `id` with the account ID confirmed in step 1, whether main or sandbox.
   Keep the key in memory through an authorized secret source. Do not print it or include it in command history.

Account-specific routes use the verified account ID. Current-account routes omit that prefix:

- `/{account_id}/test/apikeys` — Test mode API keys
- `/{account_id}/test/settings/account` — account display name
- `/{account_id}/test/settings/payment_methods` — payment method configuration
- `/{account_id}/test/settings/tax` — Stripe Tax settings

The initial **Business name** onboarding field can replace the display name
shown in the account switcher. Use account IDs to distinguish sibling accounts. Change the display name only when the user requests that change. Use **Settings → Business → Account details** for an authorized change.
