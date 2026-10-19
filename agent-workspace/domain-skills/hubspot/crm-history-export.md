# HubSpot: CRM property and engagement history

Prefer the HubSpot connector for schema discovery, full record inventories and supported searches. Paginate to the reported total. The authenticated HubSpot app exposes additional raw history through same-origin endpoints.

## Raw records

Include `portalId` in the query string and an `X-HubSpot-CSRF-hubspotapi` header containing the `hubspotapi-csrf` cookie, read inside the page. Keep cookie values in the browser.

- Contact: `/api/contacts/v1/contact/vid/{id}/profile`
- Deal: `/api/deals/v1/deal/{id}`
- Company: `/api/companies/v2/companies/{id}`
- Engagement: `/api/engagements/v1/engagements/{id}`

These responses can preserve property versions, provenance, identity profiles, list membership or engagement metadata that a connector's current-property view does not expose. Engagement metadata can contain sender details and RFC message IDs, but their presence is not guaranteed. Missing source fields must remain distinguishable from inferred values.

## Complete association coverage

The app's `EngagementAssociationsRpc/getEngagementAssociationSummary` gateway accepts `objectId`, `objectTypeId` and `limitPerAssociationType`. Capture the exact gateway URL from the current app's network traffic. Its response maps object type IDs to associated object IDs.

A working request with `limitPerAssociationType: 100` can return capped activity lists on busy contacts, companies or deals. Do not treat that as a complete export. Enumerate every engagement separately and recover its reverse relationships to core records. Check for missing referenced records and any reverse lists that also reach the cap.

A contact may have multiple company associations. Inspect the associated-object results for the `Primary` label rather than choosing the first company in an unordered list.

## Original attachments

`/api/filemanager/api/v2/files/{id}` returns file metadata; `/api/filemanager/api/v2/files/{id}/signed-url` returns a temporary download URL. Download the original bytes, compare the size with source metadata and record a checksum. Use temporary URLs internally; they are unsuitable as permanent migration links.

## Snapshot checks

Refresh counts and modification timestamps before declaring a migration complete. A new synced meeting can update its linked contact, company and deal without changing any of their record counts. Import the new engagement and refresh those changed properties and raw histories as one delta.
