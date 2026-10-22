# Strava API application settings

The authenticated application page is `https://www.strava.com/settings/api`.
An unauthenticated session redirects to sign-in; let the user complete sign-in.

The settings page can contain client secrets and athlete access/refresh tokens.
Do not capture the whole page or extract its complete text. Inspect public
labels and DOM structure first, then use private comparisons for secrets.

## Application details

- Match the public Client ID to the consuming application's configuration before
  rotating a secret. Labels vary with the account's language.
- In the observed Chinese layout, the Client ID label is `客户 ID`; Client
  Secret is `客户端密钥`.
- Detail rows were `div.nlmog`, with a label as their first child and a value
  container `.WO00S`. The secret text was in that container's `p` element.
  These CSS classes are implementation details: confirm the matching label
  before relying on them, and expect them to change.
- The client secret has a Show/Hide control (`显示`/`隐藏`) and a separate
  Generate new client secret control (`生成新的客户端密钥`). Revealing the current
  secret is a read-only action; generation changes credentials. Do not confuse
  the neighboring athlete access/refresh tokens with the application secret.
- During a private transfer handoff, verify the destination value exactly and
  check that its editor was submitted. Re-hide the source secret afterward.

## Webhook verification token

Strava manages webhook subscriptions through `/api/v3/push_subscriptions`.
Each application supports one subscription. The `verify_token` is chosen by
the application owner and checked during subscription creation's GET challenge;
it is not sent on event POST deliveries. Rotating that application setting does
not by itself establish a newly validated subscription or authenticate event
POST requests. Inspect the consumer's implementation before changing or
recreating its subscription.

Sources: [Authentication](https://developers.strava.com/docs/authentication/),
[Webhooks](https://developers.strava.com/docs/webhooks/).
