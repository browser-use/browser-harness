# Lulu account currency and Print API quotes

## Currency is a support-managed account preference

Lulu's official [account basics](https://help.lulu.com/en/support/solutions/articles/64000255301-lulu-account-the-basics) says that a preferred account currency cannot be changed through account settings; the account owner must contact support.

The storefront's currency selector is not evidence that authenticated Print API calculations or supplier billing changed currency. The account settings and identity-provider profile screens do not expose the billing-currency change. In testing, requesting USD in a cost-calculation body still produced the account's existing currency. Inspect the actual currency in a fresh authenticated calculation after support confirms the change.

## Support workflow

- Start at `https://help.lulu.com/en/support/tickets/new`.
- Choose **Lulu Print API** when offered, then **Account** and **Updating Account Information** for an account preference request.
- Include the registered account email and ask whether the change also applies to production Print API calculations and billing. Obtain the account owner's authorization before transmitting an account-change request.
- Do not treat a form clearing or reloading as proof of submission. Verify a ticket number, acknowledgment email, or the authenticated ticket list. If submission is uncertain, check those before retrying to avoid duplicate requests.
- The help site's suggested-answer panel can contradict the official article by suggesting a settings-page change. Prefer the article and observed account controls.

## Credentials

`https://developers.lulu.com/api-keys` may render client credentials in accessible text fields. Avoid full accessibility/DOM dumps of that page. Retrieve only the required credential into private storage when authorized; do not include credentials in screenshots, logs, domain notes or source control.
