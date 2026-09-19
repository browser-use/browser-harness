# Lever applications

## Routing and uploads

- Employer career pages can open `https://jobs.lever.co/<employer>/<posting-id>/apply` in a new tab. Inspect `list_tabs()` after clicking Apply instead of assuming navigation in the original tab. Preserve observed source query parameters.
- The resume file input is `#resume-upload-input`. After `upload_file`, wait for the visible "Analyzing resume" state to finish. Resume parsing can fill name, email, phone, current company, LinkedIn, and location; inspect the resulting values before correcting them.
- Location uses `#location-input` plus a hidden `#selected-location` record. Read the latter to verify that a canonical location was committed. Never set the hidden record yourself.
- Employer-specific questions use names like `cards[<card-id>][field0]`. Inspect each label and available option; do not copy card IDs or assume questions are the same across postings.
- Some postings have no cover-letter field. Do not report an independently prepared cover letter as submitted when only the resume and custom answers were supplied.

## Sticky header trap

The employer logo can remain fixed above scrolled form content. A checkbox with a positive `getBoundingClientRect().y` can still be covered by the logo/header. Clicking its rectangle may navigate away to the employer home page.

Scroll the actual target into the center of the viewport, take a fresh screenshot, and confirm the visible target or `document.elementFromPoint` before clicking. Verify the resulting checkbox state and URL immediately; do not continue a batch of form edits after an unexpected navigation. If navigating back, re-read every value and the uploaded file before continuing.

## Next-step acknowledgments

An employer may require acknowledgment that its recruiting sender was marked safe. Do not check a compound statement until the safe-sender step is actually complete in the applicant's authorized email account. Keep any mail rule narrow, with no forwarding, deletion, or unrelated label changes. Verify saved mail settings before returning to the application.

## Completion

Read back the selected resume filename, parsed contacts, canonical location, each required answer, and voluntary self-ID options. Optional future-opportunity marketing consent is separate from submitting the current application. A submit click is not evidence of receipt: inspect the final page and, when available, an exact-role email confirmation.

On macOS, focusing a native select and sending arrow keys may leave its committed value unchanged. Native popup contents may not appear in a CDP screenshot. Avoid blindly following these attempts with `press_key('Enter')`: this helper emits both keyDown text and a char event, and Enter can submit the surrounding form. Recheck the select value before any further key action. If submission happens, look for authoritative receipt evidence before retrying; do not create a duplicate merely to repair optional self-ID fields.
