# Greenhouse hosted application forms

## Routes and page structure

- Hosted boards use `https://job-boards.greenhouse.io/<board>/jobs/<job-id>`.
- A listing can include the full application form below the job description. The top Apply button scrolls to the form rather than opening another route. That scroll can still be animating when an immediate screenshot is taken; re-measure after it settles.
- Employer-specific question IDs differ across jobs. Inspect labels and current controls rather than reusing another employer's IDs or answers.

## Selects and education fields

- Modern forms use React Select combobox inputs (`[role="combobox"]`), not native `<select>` elements. Options use `[role="option"]` with IDs such as `react-select-<field-id>-option-<index>`.
- Read only visible options: the phone component can also keep a hidden full country list in the DOM.
- A typed search string is not a committed choice. After choosing an option, the searchable input can be empty while its surrounding `.select__container` displays the selected label. Verify that label after blur as well as the screenshot.
- A multi-line question label can occupy the center of the select container. Clicking that center may focus the input without opening options. Locate the actual input or dropdown indicator and check `aria-expanded`; ArrowDown on the focused combobox opens its menu.
- Location and school choices may load asynchronously. `document.readyState` does not indicate completion of their option requests. Wait for the matching visible option before selecting it.
- Open the dropdown and re-measure its option geometry before clicking. If a filter yields no options even though the unfiltered list contains the desired item, clear the search with focused input selection plus Backspace, reopen the menu if needed, and scroll the option container. Do not insert an arbitrary value into hidden inputs.
- Education taxonomy can be coarser than the candidate's actual degree. Use the closest truthful available category and keep the exact discipline in the attached resume.

## Attachments

- Typical file input selectors are `#resume` and `#cover_letter`; verify their presence first.
- `upload_file(selector, absolute_path)` works with these inputs. During processing, the input can disappear and the UI can show a progress bar. Querying the old file input immediately after upload is not reliable evidence of failure.
- Verify the expected filename in the completed attachment UI after the progress indicator disappears. Uploaded documents are not evidence of a submitted application.

## Screening and verification

- Custom questions can be checkbox groups even when their wording asks for the single best statement. Follow the actual question, not assumptions based on control type.
- Generic employer form questions can mention hybrid office expectations even on a remote listing. Preserve the candidate's real location and constraints instead of answering as if every listing were interchangeable.
- Optional race and ethnicity questions may appear conditionally. Do not infer one sensitive answer from another.
- Re-read committed select labels, text values, checked choices and attachment filenames before submission. A populated input or click alone does not prove a saved choice.
- A reCAPTCHA widget on the page does not itself mean a challenge is blocking submission. If a human-verification challenge actually appears, hand it to the user without bypassing it.
- Submit can reveal an additional email-code step instead of navigating to a confirmation page. The observed flow sends an eight-character code and then requires another submit action. This intermediate state is not a submitted application.
- Verification mail may come from `no-reply@us.greenhouse-mail.io`, not the `greenhouse.io` domain. Search by the security-code subject and employer as well as the sender, use only the intended mailbox, and never persist the code in notes or logs.
- The email-code UI may use eight separate `#security-input-0` through `#security-input-7` controls, each with `maxlength="1"`. Preserve the code's exact case and use normal input actions. Verify completion without logging the values. An invalid-code error is not a submission receipt, and the observed form did not provide a resend button.
- Submission requires an actual confirmation or receipt. Keep incomplete drafts distinct from submitted applications.
