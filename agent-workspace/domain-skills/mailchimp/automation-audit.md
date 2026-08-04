# Mailchimp automation-flow audits

Use this workflow to inspect an existing Mailchimp automation without creating
contacts, triggering a journey, sending test messages, or changing live state.

## Prefer GET requests for structure and evidence

The Marketing API exposes enough read-only data for most audits even when the
browser is at a login wall. Authenticate without putting the API key in command
arguments or output. Build the Basic Authorization header in-process from a
secret file or environment variable.

Useful endpoints:

```text
GET /3.0/customer-journeys/journeys
GET /3.0/customer-journeys/journeys/{journey_id}
GET /3.0/customer-journeys/journeys/{journey_id}/steps?count=100
GET /3.0/campaigns/{campaign_id}
GET /3.0/campaigns/{campaign_id}/content
GET /3.0/reports/{campaign_id}
GET /3.0/reports/{campaign_id}/click-details?count=100
GET /3.0/reports/{campaign_id}/sent-to?count=100
GET /3.0/lists/{list_id}/segments?count=1000
GET /3.0/lists/{list_id}/segments/{segment_id}/members?count=100
```

The customer-journey collection and step reads may not appear in the public
API reference even when they are available for an account. Treat them as a
read-only capability probe and fall back to the app if they return an error.

Never probe the documented journey trigger with POST. That endpoint enrolls a
real contact.

## Reconstruct the journey graph

`steps` is ordered. The durable fields are:

- `step_type`, `status`, `display_text`, and `stats`
- `trigger_details.tag.tag_name` for tag-entry triggers
- `delay_time` in seconds for delays
- `action_details.email.id` for send-email campaign IDs
- `action_details.email.settings` and `report_summary` for a quick audit

Sum consecutive delay values to describe the customer-facing schedule. Check
`can_contacts_reenter` and `journey_wide_exit_condition` on the journey itself;
an active series with no exit condition can keep emailing after a lead converts
or replies.

## Verify content and rendering

Use `/campaigns/{id}/content` for the actual HTML, not just the subject line.
Look for:

- placeholder headings, lorem ipsum, and unexpanded merge tags
- hard-coded prices, dates, warranties, or promotions
- CTA text that is not wrapped in a link
- default social links such as generic Mailchimp, Facebook, or X URLs
- missing image alt text

The campaign object exposes `archive_url` and `long_archive_url`. Open the
public archive in the browser and take a screenshot to verify the rendered
email. This is safe: viewing an archive does not send or enroll anyone.

## Interpret reports carefully

Automation samples are often tiny. Use aggregate reports first. Mask recipient
addresses if `/sent-to` is needed for bounce or merge-field diagnosis.

- `emails_sent` includes recipients who later hard-bounced.
- A high open or click rate from only two or three delivered contacts is not a
  stable performance result.
- Security scanners may click every footer/social link. Compare tracked URLs
  and `unique_subscriber_clicks` before treating clicks as buyer intent.
- Check whether merge fields are populated. `Hi *|FNAME|*,` renders poorly when
  every enrolled member has an empty `FNAME`.

## Read-only safety boundary

Do not call journey trigger, campaign send, test-send, pause/resume, member
create/update, tag mutation, or delete/archive endpoints during an audit. Do not
create a test contact. Record the exact GET evidence and request approval before
making any live change.
