# OpenAI Partner Portal technical assessment

## Route and form structure

The authenticated assessment is at `https://partners.openai.com/technical-assessment`. Reuse an existing user tab because it may contain unsaved answers. The page uses Salesforce Lightning controls; generated `input-*` IDs change on reload. Prefer current semantic labels and scoped row positions.

The production-experience combobox offers No experience, Pilot projects only, Limited production deployments, and Multiple successful production deployments. Do not assume it is a Yes/No field.

## Field constraints

Inspect current limits before entering prepared answers. Observed limits:

| Field | Constraint |
| --- | --- |
| Practice qualifications | 3,000 characters |
| Hyperscaler status | 1,500 characters |
| Delivery methodology | 5,000 characters |
| Governance ownership | 5,000 characters |
| Compliance | 3,000 characters |
| Each recent use case | 1,500 characters; up to 10 entries |
| Deployment customer | 255 characters; up to 10 entries |
| Deployment usage frequency | 500 characters |

User and document counts expose spinbutton semantics even when the underlying input has `type=text`. Supply numeric counts only. Preserve category distinctions in accompanying text, and do not turn integrations or mixed activity metrics into a document count. Native accessibility can report Value 0 while Details and the DOM value show the entered number, so inspect the actual input value.

## Drafts and evidence

`Save Draft` and `Submit Assessment` are separate actions. Wait for `Draft saved.` and Draft status before reloading. Compare the reopened field values, not generated IDs. A checked attestation does not mean the assessment was submitted. Stop at the draft when the user reserves submission.

The upload input supports multiple files. The observed limit is five files, 20 MB each, with PDF, DOC, DOCX, PPT and PPTX accepted. Wait for the upload modal to report every selected file uploaded and enable Done. After Done, verify the Uploaded supporting files list, then save and reopen the draft.

Attachment display names omit the extension and show type and size separately. The visible list can appear in reverse upload order. Preserve requested logical order with numbered filenames. Download links use `/sfc/servlet.shepherd/document/download/<document-id>`; IDs are account-specific and must never be copied into shared examples.

## Verification boundary

Saved form values, attachment titles and displayed sizes verify draft persistence. They do not establish application submission, partner approval, or a byte-for-byte download match. Capture the final draft review view and hand the live tab back to the user.
