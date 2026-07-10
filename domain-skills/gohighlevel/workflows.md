# GoHighLevel Workflow Email Actions

## Two Separate Email Layers

HighLevel workflow emails keep subject metadata in two places:

1. The reusable email template stores its body, template-level subject and
   preview text.
2. The workflow email action stores its own `attributes.subject`,
   `attributes.preHeader`, `attributes.previewUrl` and `attributes.template_id`.

Updating a template through the public Email Templates API does not necessarily
update the workflow action. A published workflow can therefore send a new body
under an old subject line.

## Private Workflow Endpoint

The workflow editor reads and saves the complete workflow object through:

```text
GET/PUT https://backend.leadconnectorhq.com/workflow/{locationId}/{workflowId}
```

This endpoint requires an authenticated HighLevel UI token with access to the
target location. A public/private-integration API token is not sufficient.
Likewise, a valid UI token for a different HighLevel location returns `401`.

Before saving, preserve the current workflow `status`, `version`, timing actions,
triggers and non-email steps. Limit changes to the intended email action fields.
Re-read the workflow after the PUT and verify its status and email-action count.

## Auth And Blank Editor Trap

The HighLevel shell exposes a Firebase ID token through `window.getToken()` once
its application scripts have initialized. The token's decoded claims can be
checked for target-location access without printing the token itself.

If the workflow URL renders a blank canvas and the token's location claims do
not include the requested location, the browser is signed into the wrong
HighLevel account/location. Do not attempt a PUT with that token. Switch to a
browser profile authenticated for the target location.

## Sent-Subject Verification

The public Conversations API provides an independent way to confirm the subject
that a workflow actually used. Fetch the contact's conversation messages and
inspect:

```text
message.meta.email.subject
```

This is more authoritative than the template metadata when diagnosing an old
workflow-action subject overriding a newly updated template.
