# Workday segmented dates and submission verification

## Segmented date controls

- Candidate self-identification forms can render the date as a `data-automation-id="dateInputWrapper"` group with visible `dateSectionMonth-display`, `dateSectionDay-display`, and `dateSectionYear-display` segments. The underlying spinbutton inputs may be visually hidden, with subpixel rectangles.
- Focusing those hidden inputs and sending an entire value with `Input.insertText` can change the wrong segment or produce a malformed date. Locate the visible segment from a fresh screenshot and click it before keyboard entry.
- Clear the active segment with Backspace, then send each digit once using a native CDP keyDown/keyUp pair. An older helper that sends both keyDown-with-text and an additional char event can duplicate digits and advance to the next segment unexpectedly. Inspect the installed helper rather than assuming all versions behave alike.
- Read back all three visible segments after entry and again on Review. A previously displayed validation message can retain the old invalid value until the next validation pass; the successful next step and Review's rendered date are the authoritative checks.

## Submission and interrupted connections

- Review all saved values and successful-upload filenames before Submit. A submit click or disappearing form is not proof of receipt.
- If the browser connection drops after Submit, check the candidate's authorized inbox for an exact employer-and-role application acknowledgment before retrying anything. An explicit received-application email can independently verify submission even if the portal confirmation could not be captured.
- Preserve the distinction between application receipt, interview, rejection and offer. Record the available evidence without claiming an unseen portal confirmation. Do not resubmit a confirmed application simply to obtain a screenshot.
- Keep candidate information, credentials, private application identifiers and email message IDs out of reusable domain notes.
