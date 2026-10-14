# Miles & More retroactive credit forms

Start from `https://www.miles-and-more.com/{country}/{language}/account/account-statement/retro-credit-intro.html` in the authenticated browser. Check the mileage statement before preparing a request.

## Partner selection

The introduction has searchable inputs `input[name="air"]` and `input[name="non-air"]`. Suggestions are `li[data-value]` entries, rather than ARIA option elements. Select the suggestion before using the corresponding navigation button.

Airline selection navigates to `retro-credit-airline.html?partnerCode=<code>`. Non-airline selection navigates to `retro-credit-non-airline.html?partnerCode=<code>` in the same account-statement directory. These navigation buttons do not submit a completed credit claim.

## Flight form

The form component is `[data-component="retroactivemilagecreditairline"]` (note the spelling). Input names include `flightNumberCode`, `flightNumber`, `date`, `departure`, `arrival`, `compartment`, `ticketNumberCode`, and `ticketNumber`.

The 13-digit ticket is split into a three-digit issuer prefix and a ten-digit serial. Keep both as strings so leading zeroes survive. Cabin and fare booking class are different fields; a boarding-pass cabin code does not establish the earning fare class.

## Non-airline form

The containing component is `[data-component="nonairline"]`, not necessarily a form element. The SIXT rental section uses `pickup`, `dropoff`, `agreement`, and the file input `receipt[]`. Its accepted upload types are PDF, JPEG, and PNG. The component also contains templates for other partner categories; only inspect the selected, visible section.

## Loading and verification

Document readiness can precede component initialization. Wait for visible, enabled fields and populated partner/profile values. Error templates such as receipt rejection or technical failure are present in the DOM before any submission, so hidden text must not be treated as an actual response.

An authenticated overview does not guarantee a later protected action will proceed without reauthentication. If a PIN/password prompt appears, stop at that prompt and let the user authenticate. Keep the final claim submission separate from partner selection and verify a completed submission against the statement or request status.
