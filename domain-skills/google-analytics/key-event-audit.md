# Google Analytics 4 key-event audit

Use the current GA4 Admin state and a short Data API report together when
checking whether reported "key events" are genuine business outcomes.

## Open the authoritative Admin view

The stable property route is:

```text
https://analytics.google.com/analytics/web/#/a{account_id}p{property_id}/admin/events/hub
```

Including both the account and property IDs matters. Property-only admin URLs
can redirect to Analytics Home instead of the requested settings page.

The Events hub lists the events currently marked as key events and whether each
has received stream data in the last 28 days. In the DOM, the Admin card links
are anchors such as `a.admin-events`; report-card links such as "View events"
may be buttons without an `href`, so click the matching element rather than
trying to copy a URL from it.

## Do not equate key events with completed conversions

The Data API metric `keyEvents`, segmented by `eventName`, can contain counts
for an event that was marked as a key event earlier in the requested period but
is no longer marked in Admin. A 28- or 30-day report can therefore disagree
with the current Events hub without either surface being broken.

For a current-state audit:

1. Record the key-event list from `/admin/events/hub`.
2. Query a short recent range (for example, the last seven complete days) with
   `eventName`, `eventCount`, and `keyEvents`.
3. Treat starts, previews, page views, and funnel steps as diagnostic events,
   not completed leads, unless the business explicitly defines them otherwise.
4. Cross-check any GA4 event imported into Google Ads. In Google Ads, inspect
   `conversion_action.primary_for_goal`,
   `conversion_action.include_in_conversions_metric`, and
   `conversion_action.counting_type`, plus the campaign bidding strategy.

This catches the risky combination where a campaign uses Maximize Conversions
while an intermediate funnel event is a primary conversion. The UI may show
strong conversion volume even though no final form submission, purchase, or
qualified offline outcome was recorded.

## Useful read-only Data API request

Call `properties/{property_id}:runReport` with:

```json
{
  "dateRanges": [{"startDate": "7daysAgo", "endDate": "yesterday"}],
  "dimensions": [{"name": "eventName"}],
  "metrics": [{"name": "eventCount"}, {"name": "keyEvents"}],
  "orderBys": [{"metric": {"metricName": "eventCount"}, "desc": true}]
}
```

Use aggregate output only, and never print service-account keys or access
tokens while testing access.
