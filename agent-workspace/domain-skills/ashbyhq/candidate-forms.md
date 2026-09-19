# Ashby candidate application forms

Ashby public listings commonly use `https://jobs.ashbyhq.com/<company>/<posting-id>`. The Application tab links to the same route with `/application` appended. Prefer the live employer page over search snippets: an indexed role may now render Job not found.

## Form discovery and uploads

- Forms are employer-configured. Inspect required labels and active controls rather than reusing another employer's question set.
- An Autofill from resume upload can be separate from the required Resume field. The latter may use `input#_systemfield_resume`; confirm the actual live selector and the displayed attachment name after upload.
- Some forms have no cover-letter attachment field but provide an optional free-text statement. Preserve the distinction between an uploaded document and text entered in a field.
- Location fields can require a canonical autocomplete result. Select the exact visible suggestion and verify the committed full location, not just the typed search term.
- Yes/No questions may render as buttons backed by a checkbox. Inspect `aria-pressed` and the visible selected state rather than assuming an ordinary checkbox is the intended click target.

## Text values and committed state

Visible text is not sufficient proof of a committed form answer. A form can still report Missing entry for required field after native text insertion, even when the input's DOM value contains the expected text.

If validation identifies this discrepancy:

1. Re-read the actual required field label and current value.
2. Scroll the field into view and focus it with a native click.
3. Select existing text, clear with a native key event, then insert the complete value.
4. Allow the UI update to settle and blur the field before proceeding.
5. Re-read the value and validation state. Do not patch framework state or bypass validation.

Submission can finish after the first post-click screenshot. Wait for the explicit successful-submission message, capture a fresh screenshot of that message, and verify an independent receipt where available. A submit-button click or a Submitting state is not confirmation.
