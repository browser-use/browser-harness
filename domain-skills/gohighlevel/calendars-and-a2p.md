# GoHighLevel calendars and A2P review

## Calendar access and availability

Existing private integrations are under `/v2/location/{locationId}/settings/private-integrations`. Edit from the integration action menu, move from Basic info to Scopes, then Update. Calendar reading needs `calendars.readonly` and `calendars/events.readonly`. Calendar configuration updates need `calendars.write`. Remove temporary write access after the approved repair and read the saved selection again.

Public API requests use the existing integration Bearer token and a supported Version header. `GET /calendars/?locationId=...` lists calendars. Verify each selected calendar belongs to the intended location. `GET /calendars/events` reads appointments, `/calendars/blocked-slots` reads calendar or user blocks, and `/calendars/{id}/free-slots` reads provider availability. The free-slot window is limited to 31 days. An active calendar with no team member can return `No users found in the calendar`.

A connected Google account still needs a linked calendar and conflict calendar selected in GHL's Connections page. Verify both selections and the assigned booking host. An OAuth connection alone does not establish those selections.

Calendar PUT updates require careful read-back. Omitted `slotDuration` can reset to 30 minutes. A one-hour duration was successfully saved with `slotDuration: 60` and `slotDurationUnit: "mins"`. Supplying 1 with the hours unit produced 0.02 hours in an observed update. Preserve timing fields explicitly, inspect the response, then verify the public booking widget. Invalid redirect placeholders can be replaced through `formSubmitType: "ThankYouMessage"` and `formSubmitThanksMessage`.

## A2P rejection details and resubmission

Trust Center is under `/v2/location/{locationId}/settings/phone_system?tab=trust-center-v2`. Clicking the rejected status badge exposes the reason and View required fixes dialog. The separate campaign table can show only Failed with no useful reason.

Code 30919 can report insufficient business information on the website. Its correction dialog asks for company identity, concrete services, contact details, multiple pages or an About section, and linked Privacy and Terms. Match the submitted website and business identity to the actual live pages.

Changing the age-gated checkbox in GHL's pre-built widget setup can generate a different widget ID. Copy the current generated snippet and verify the deployed page uses that ID before running checks. The copy-code step may require a real clipboard gesture. Verify the live optional consent checkbox and disclosures without sending a message.

Final submission can require a separate acknowledgement that rejected non-compliant submissions may incur charges. Treat that acknowledgement as its own approval step. Passing GHL's widget and multiple-opt-in checks does not establish carrier approval. Submit once after authorization and reconcile the resulting campaign status before retrying.

## Background scope dropdowns

The virtualized scopes list may render no option rows in a hidden browser window, even while filtering updates its internal count. Filtering the scopes input to the exact permission label and using ArrowDown then Enter can select the option. Read the selected tags before Update and abort if any unintended permission appears. Avoid Select all.
