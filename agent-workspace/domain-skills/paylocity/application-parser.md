# Paylocity recruiting: upload and parser checks

Public routes commonly use `/Recruiting/Jobs/Details/<job-id>` and `/Recruiting/Jobs/Apply/<job-id>`, sometimes followed by an employer slug.

## Upload modal

- `Select Resume to Upload` can first open an **Apply with resume** modal; its **Upload Resume** button opens the file chooser.
- Hidden modal markup may still appear in a DOM snapshot. Check the screenshot or accessibility tree to distinguish the active modal from hidden content.
- Wait for **Analyzing applicant information...** to finish. Confirm the selected filename and then review the parsed application fields.

## Review parsed data

- Employment dates and responsibilities may parse correctly while contact or education fields remain blank.
- City/remote-work strings from a resume can be incorrectly placed in an employer's street-address field. Clear the misclassified street text and place the supported city in the city field; do not invent an employer address.
- A bachelor's degree may parse as **Other**. Verify school, area of study, graduation, degree, city, and state explicitly.
- The modern address state picker uses abbreviations such as **FL**, while the legacy education state dropdown can use full names such as **Florida**. Typing the full name into the abbreviation picker may yield **No Results Found**. Wait for filtering and select the actual option.

## Progress and tenant-specific requirements

- **Next Step** is asynchronous; verify that **Step N of M** changed before proceeding.
- Some employer flows require two named references on step 2. This is not universal. Read the active tenant's requirements and stop if the applicant has not supplied those facts.
- Do not infer that an uploaded resume or a completed first step means an application was submitted. Continue to an explicit receipt, or record the exact unresolved step.
