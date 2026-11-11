# Oracle Recruiting Candidate Experience forms

## Routes and flow

- Public job routes commonly use `/hcmUI/CandidateExperience/<locale>/sites/<site>/job/<job-id>`.
- Applying can enter `/job/<job-id>/apply/email`, then `/apply/section/1`.
- The email step may create a candidate profile without requiring a password. A terms link may open a long modal with its own Agree button. Inspect the actual terms and the checkbox's committed state.
- Do not assume the first form's Submit is the end: tenants may have further sections or email verification. Require a received/submitted confirmation before reporting success.

## Resume import and attachments

- The top resume-import file input and the supporting-document file inputs serve different purposes. Inspect labels before choosing an input; do not blindly upload to every file input.
- A successful import can populate contact and location fields while leaving education and employment history empty. Check each section independently.
- Supporting uploads show filenames after processing. Wait for the actual filename, not only an intermediate Saved indicator.
- Avoid hardcoding generated numeric suffixes in field IDs across page visits or edits.

## Comboboxes use grids, not listbox options

Controls such as countries, months, years, and salary ranges can be text inputs with `role="combobox"`, `aria-haspopup="grid"`, and `aria-controls` pointing to a `role="grid"` popup. Choices are `role="gridcell"` descendants.

1. Inspect the current input and read its `aria-controls` attribute.
2. Click the input and type a filter, if supported.
3. Find the matching gridcell **inside that input's controlled grid**. A global search for visible matching text can find another control's stale popup.
4. Calculate the current option's rectangle and click its center.
5. Verify the input's value, collapsed popup, and eventually the saved tile or section. Typed filter text alone is not a committed selection.

Example inspection, after locating a real input from the page:

```javascript
const input = document.querySelector(observedSelector);
const grid = document.getElementById(input.getAttribute('aria-controls'));
const candidates = Array.from(grid.querySelectorAll('[role="gridcell"]'));
```

Postal-code suggestions can include several cities for one code. Choose the full canonical entry matching the applicant's address. Changes to parent address fields may clear dependent selections.

## Inline history editing

- Saved entries use `.apply-flow-profile-item-tile` containers. Locate a tile by its employer or school text, then its `button[aria-label="Edit"]`.
- Clicking a tile's summary can merely reveal its edit affordance; it need not open the form.
- Add Experience saves a newly entered item; editing an existing item can use a separate Save button.
- Add, save, and edit operations can remount fields and move the viewport after an initial delay. Reinspect after the transition instead of reusing a rectangle or scrolling a stale element immediately.
- Check saved date ranges. A year filter that was never committed can leave a date absent even though its month briefly appeared filled.

## Tenant-specific questions and consent

- A voluntary disability section may include an additional required category dropdown even after a No response. Inspect the actual options and use only the applicant's authorized answer; do not infer a condition.
- Salary ranges, travel willingness, relationships to employees, and legal declarations are applicant decisions. Leave unknown answers pending.
- Marketing and job-alert checkboxes are separate from the application itself. Do not opt in without authorization.
- Screenshots, email codes, applicant identifiers, and form answers belong in private task records, not shared domain documentation.
