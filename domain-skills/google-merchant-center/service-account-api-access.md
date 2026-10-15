# Merchant Center service-account API access

## What is non-obvious

Enabling the Merchant API in Google Cloud and adding the service account as a Merchant Center user are both necessary, but the first API call can still fail with `401` until the Cloud project is registered to the Merchant Center account.

## Reliable setup sequence

1. Enable `merchantapi.googleapis.com` in the intended Google Cloud project.
2. In Merchant Center, open **Settings → People and access** and add the service-account email.
3. Give it the product roles needed by the use case. Reporting requires **Performance and insights**; account/product operations may need **Standard** or **Admin**.
4. Authenticate as that service account with the `https://www.googleapis.com/auth/content` scope.
5. Register the Cloud project once:

```http
POST https://merchantapi.googleapis.com/accounts/v1/accounts/{ACCOUNT_ID}/developerRegistration:registerGcp
Content-Type: application/json

{"developerEmail":"owner-or-developer@example.com"}
```

6. Allow several minutes for registration to propagate, then retry the read canary:

```http
GET https://merchantapi.googleapis.com/accounts/v1/accounts/{ACCOUNT_ID}
```

## Useful read canaries

Processed products and their item-level issues:

```http
GET https://merchantapi.googleapis.com/products/v1/accounts/{ACCOUNT_ID}/products?pageSize=1000
```

Aggregated product eligibility and issue counts:

```http
GET https://merchantapi.googleapis.com/issueresolution/v1/accounts/{ACCOUNT_ID}/aggregateProductStatuses?pageSize=100
```

Product performance uses the Reports sub-API and MCQL:

```http
POST https://merchantapi.googleapis.com/reports/v1/accounts/{ACCOUNT_ID}/reports:search
Content-Type: application/json

{
  "query": "SELECT impressions, clicks, click_through_rate FROM product_performance_view WHERE date DURING LAST_30_DAYS"
}
```

## Operational cautions

- The API may intermittently return `500`/`502`/`503`; retry bounded read calls with short backoff.
- A successful account read does not prove product or reporting roles. Test the exact API family you intend to use.
- Do not print service-account keys or access tokens in logs or screenshots.
- Treat product writes, feed changes, shipping/return settings, and destination changes as production mutations; verify the exact account and product IDs first.

