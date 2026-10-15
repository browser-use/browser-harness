# Workday candidate application forms

Workday career tenants use hosts such as `<tenant>.wdN.myworkdayjobs.com`. Field labels, upload requirements and account policies are tenant-configurable; inspect the live form rather than assuming another tenant's schema.

## Navigation and loading

- An application chooser may offer Autofill with Resume, Apply Manually and Use My Last Application.
- Autofill can lead to `/apply/autofillWithResume` and an account-creation gate before the upload step.
- With user authorization, successful account creation can sign the candidate in immediately. Verify the displayed account and application step; do not assume every tenant requires a separate verification email.
- These forms are single-page applications. `document.readyState === 'complete'` can precede both the next step and its input fields. Wait for the intended step heading and expected controls, not just load completion.
- After signing in again, check Candidate Home before starting a fresh application. Its active-applications table identifies saved drafts as Not Submitted. The row's Related Actions menu may provide View Application rather than a resume-edit action.
- A saved draft can become read-only when the employer updates the posting. The application drawer explicitly says the job posting has been updated and offers View Job Posting. Preserve the draft; inspect the current posting and its normal application options instead of deleting a draft or assuming it was submitted.

## Resume upload and parsed fields

- Use the current `input[type=file]` with `upload_file`. Confirm the visible filename and successful-upload state before continuing.
- The later Resume/CV section may have a separate multiple-file input. Verify that earlier uploads remain and that each newly added document finishes uploading.
- Audit every parsed employer, job title, date, current-role checkbox and description. A combined company/title line can be parsed as the entire job title; another employer's heading can be appended to the previous role description.
- Current controls commonly have IDs shaped like `workExperience-<generated-id>--jobTitle`, `--companyName`, `--roleDescription` and `--currentlyWorkHere`. Discover generated IDs from the current DOM.
- For native text inputs and textareas, focus and select the existing text before `type_text`. Read back the complete value after editing; a shortcut that failed to select all can silently append new content.
- Parsed education may retain an institution and field of study but leave the required degree unset. Source attendance dates alone do not establish a completed degree.
- An optional Languages section can acquire multiple required proficiency ratings after parsing. Do not invent detailed ratings from a language list. If the section is optional, leaving it out does not remove the language list from the uploaded resume.

## Dropdowns and search controls

- A source-of-application field may look like a text box but require a selected item. Typing a term can leave the control minimized; press Enter to search, wait for Search Results, then select the exact item.
- Verify the resulting selected chip or item count. Text left in the search box is not a committed answer.
- Other selectors, including phone type and degree, can be buttons rather than native selects. Open the menu, re-measure late-rendered option geometry and confirm the button's committed value afterward. Escape can dismiss a menu that remains open.

## Completion

Account creation, a successful upload and an intermediate saved step are not application submission. Recheck required answers and attachments, then verify the final portal confirmation and any independent application receipt. Keep credentials, verification codes and candidate-specific identifiers out of reusable notes and logs.
