# Google Ads manager and API access

## Manager linking flow

- The API Center is available only from a manager account. An advertiser account can have active campaigns while a newly created manager shell correctly shows zero accounts and zero campaigns.
- From the manager, open **Accounts > Sub-account settings**, select **Link existing account**, and enter the advertiser customer ID.
- The link is not active until the advertiser accepts it under **Admin > Access and security > Managers**. Verify the request there instead of treating the manager's empty campaign view as evidence that the advertiser is empty.
- After acceptance, return to the manager and verify both the advertiser name/customer ID and the expected campaign inventory. Google Ads preserves account context through `ocid` and `authuser` query parameters, so confirm the account picker after direct-route navigation.

## API Center and developer token

- Manager API Center route: `https://ads.google.com/aw/apicenter`.
- Apply for a developer token from the manager account. The access tier shown in API Center determines which operations are available.
- Treat the developer token as a secret. Never print it in logs or paste it into durable documentation. If it appears in browser or terminal output, rotate it in API Center before continuing.

## Service-account access

- The Google Cloud project used for authentication must have `googleads.googleapis.com` enabled.
- Create a dedicated service account and key when the automation does not need an interactive user session. Store the private key outside the repository with restrictive file permissions.
- Add the service-account email under the manager's **Admin > Access and security > Users** page. Google Ads recognizes service-account addresses: email-only and Admin access are unavailable, while Standard access supports campaign management.
- The service account is added directly; it does not need to accept an emailed invitation. Verify the success toast and the resulting user row before testing the API.

## API verification sequence

1. Mint an OAuth access token using the service-account key and the `https://www.googleapis.com/auth/adwords` scope.
2. Call `customers:listAccessibleCustomers`. The manager resource should be returned.
3. Query the advertiser through `customers/{advertiserCustomerId}/googleAds:searchStream` with both the `developer-token` and `login-customer-id: {managerCustomerId}` headers. Customer IDs in API paths and headers are digits only.
4. Confirm the returned campaign count/statuses against the Google Ads UI.
5. To verify write authorization without changing production, call the appropriate mutate service with `validateOnly: true`. A successful validation proves permission and request shape; it does not prove a production mutation occurred.

## Common failure signals

- **Manager dashboard is empty:** the advertiser link is still pending, the wrong account context is selected, or the advertiser was not linked. Inspect the advertiser directly before concluding that campaigns are missing.
- **Permission denied for the advertiser:** confirm the manager link is accepted, the service-account user exists on the manager, and `login-customer-id` identifies that manager.
- **API disabled or project permission errors:** inspect the Google Cloud project tied to the service-account key. Enabling the API in an unrelated project does not help.
- **Direct URL opens the wrong account:** preserve or replace the `ocid`/`authuser` context and re-check the visible account name/customer ID before any interaction.
