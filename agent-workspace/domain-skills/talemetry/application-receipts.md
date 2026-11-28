# Talemetry application flow and receipt verification

Observed on a Meltwater careers tenant. Other employers may configure different steps.

## Routes and frames

- A public posting on an employer's `*.ttcportals.com` site can redirect from a legacy role slug to a newer canonical posting. Read the current title rather than deriving it from the URL.
- The application can be embedded in `#talemetry_apply_iframe`, with an iframe source shaped like `https://apply.talemetry.com/application/<application-id>`.
- Capture that source from the live DOM for the current application. The ID is candidate-specific: do not guess, reuse it for another applicant, or publish it in examples.

## Wizard state

- `Next` advances asynchronously. Wait for the step heading or progress indicator to change before filling the next section. A click followed by an unchanged snapshot is not a completed transition.
- Upload a document, wait for its filename to appear, and verify the actual selected file before continuing.
- Short free-text questions can impose character limits; inspect the active field's limit rather than pasting a full cover letter.

## Submission result

- On this tenant, successful submission redirected the parent page to the general job search, without leaving a useful confirmation there.
- Reopening the exact application URL showed **“The requested application has already been completed.”** The page title said **“Application Error”** despite this explicit completion message. Read the message body, not just the title.
- An employer email then independently acknowledged the same role. Match employer, role, recipient, and date before recording it as evidence.
- Do not submit again merely because the parent page returned to search. A generic search page alone is not evidence of success or failure.
- A receipt means the application was received, not that the applicant was selected or offered a job.
