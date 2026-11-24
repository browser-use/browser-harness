# Locally retailer inventory administration

Field-tested against the authenticated retailer dashboard at
`https://www.locally.com/station/panel/`.

## Dashboard and inventory routes

The company dashboard accepts a retailer company ID:

```text
https://www.locally.com/station/panel/company_dashboard/index?user_company_id=<company-id>
```

Inventory navigation resolves to these routes:

```text
/station/panel/new_inventory_config/index
/station/panel/inventory_upload/index
/station/panel/inventory_upload_batches/index
/station/panel/inventory_audits/index
/station/panel/credentials/index
```

Their visible labels are, respectively:

- Inventory Feed Setup
- Manual Upload Setup
- Upload History
- In-Stock Reports
- SFTP & API Credentials

Prefer clicking the authenticated navigation links so Locally preserves the
active company context. Do not invent or copy a company ID between accounts.

## Feed-state verification

Do not treat the generic company-dashboard status card as inventory-ingestion
proof. A dashboard may say the retailer is live while **Upload History** says
the store has never uploaded or synced inventory.

Use this verification order:

1. Open **Upload History** and inspect the latest batch or the explicit
   never-synced state.
2. Open **In-Stock Reports** for catalog-match and rejected-identifier results.
3. Compare accepted rows with the source feed's distinct identifier count.
4. Spot-check known in-stock and zero-stock products on the public experience.

## Auto-Sync URL setup

The page still labelled **Manual Upload Setup** contains current integration
methods even though its legacy manual uploader is decommissioned. Expand the
**Auto-Sync URL Method** panel for the hosted-feed option.

Locally's observed workflow requires its support team to register the hosted
URL. The retailer should provide a stable, protected URL that emits a complete
inventory report at least daily. Confirm the exact required columns against
Locally's current documentation and support instructions before enabling it.

After support registers the URL, verify the first import in **Upload History**
and request the first catalog-match or rejected-identifier report. Configuration
alone is not completion.

## Credentials boundary

The credentials page can expose controls that create persistent SFTP or API
access. Inspect existing credential status read-only unless the user explicitly
authorizes generating or rotating credentials. Never place tokens, passwords,
company IDs, feed URLs containing tokens, or customer inventory in a domain
skill, log, screenshot, or model prompt.

## Browser observations

- An accessibility-tree click may focus an inventory-menu link without loading
  it immediately. If the URL does not change, click the same resolved link once
  more, then refresh application state.
- Some inventory pages update the URL before their accessibility tree settles.
  Wait briefly and fetch state again before concluding the page is empty.
- The credentials page may initially expose little accessible text. Use a
  screenshot for orientation, then refresh state; do not use this as a reason
  to generate new credentials.
- Expansion panels on the setup page reveal important method-specific copy that
  is not present in the collapsed accessibility tree.
