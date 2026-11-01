# Miles & More retroactive credit forms

Start from `https://www.miles-and-more.com/{country}/{language}/account/account-statement/retro-credit-intro.html` in the authenticated browser. Check the mileage statement before preparing a request.

## Partner selection

The introduction has searchable inputs `input[name="air"]` and `input[name="non-air"]`. Suggestions are `li[data-value]` entries, rather than ARIA option elements. Select the suggestion before using the corresponding navigation button.

Airline selection navigates to `retro-credit-airline.html?partnerCode=<code>`. Non-airline selection navigates to `retro-credit-non-airline.html?partnerCode=<code>` in the same account-statement directory. These navigation buttons do not submit a completed credit claim.

## Flight form

The form component is `[data-component="retroactivemilagecreditairline"]` (note the spelling). Input names include `flightNumberCode`, `flightNumber`, `date`, `departure`, `arrival`, `compartment`, `ticketNumberCode`, and `ticketNumber`.

The 13-digit ticket is split into a three-digit issuer prefix and a ten-digit serial. Keep both as strings so leading zeroes survive. Cabin and fare booking class are different fields; a boarding-pass cabin code does not establish the earning fare class.

The airport fields use an autocomplete list referenced by the input's `aria-controls`; select the `li[data-value]` whose first airport-code component matches the actual airport. The selected airport is stored in the input's `data-value` attribute.

Open the flight date picker with the calendar icon button inside `.retroactivemilagecreditairline__date`, then choose an active `button[data-calendar-date]` and Confirm. Merely focusing the date input does not open the live picker. Hidden calendar markup can still respond to DOM clicks without committing the date. The submission reads `data-calendar-date`, not only the visible input value; wait for its ISO date to match the selected date before submitting. Pasting a complete date through synthetic input events can be rejected by the formatter.

## Non-airline form

The containing component is `[data-component="nonairline"]`, not necessarily a form element. The SIXT rental section uses `pickup`, `dropoff`, `agreement`, and the file input `receipt[]`. Its accepted upload types are PDF, JPEG, and PNG. The component also contains templates for other partner categories; only inspect the selected, visible section.

## Loading and verification

Document readiness can precede component initialization. Wait for visible, enabled fields and populated partner/profile values. Error templates such as receipt rejection or technical failure are present in the DOM before any submission, so hidden text must not be treated as an actual response.

An authenticated overview does not guarantee a later protected action will proceed without reauthentication. If a PIN/password prompt appears, stop at that prompt and let the user authenticate. Keep the final claim submission separate from partner selection and verify a completed submission against the statement or request status.

Flight submissions navigate to `retro-response.html?partnerCode=<code>`. A credited response specifies the number of miles; a forwarded response means the request was received for partner review. These are distinct outcomes. Save the confirmation and check the statement before retrying an ambiguous or technical response. Avoid treating navigation or a submit click as proof of acceptance.
