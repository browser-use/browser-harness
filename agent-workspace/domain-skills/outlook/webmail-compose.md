# Outlook Web — compose and verify one message

## Route and compose controls

- Mail: `https://outlook.office.com/mail/`.
- Recipient editors: `[contenteditable=true][aria-label="To"]`, with separate `Cc` and `Bcc` editors.
- Subject: `input[aria-label="Subject"]`.
- Body: `[contenteditable=true][aria-label="Message body"]`.
- Recipient entities render as `span._Entity[aria-label]`; inspect each recipient field separately before sending.

## First-use UI and recipient handling

A first-use privacy dialog can appear after the initial inbox has loaded. Dismiss its Continue button before opening compose. A loaded inbox alone does not prove the compose controls are unobstructed.

Typing an address initially leaves the recipient suggestion open. Select the displayed address suggestion and verify that a recipient entity was created before moving to the subject. The popup can cover the subject input.

Do not emit a literal tab character when moving between recipient fields. Some keyboard helpers send a `char` event for Tab as well as key events; Outlook can store that character as an invalid empty recipient. Use raw Tab keyDown/keyUp events without text or char events.

The invalid-address banner offers Remove recipient, but inspect the editor afterward: a raw whitespace character can remain and recreate the invalid entry on the next send attempt. If ordinary editing fails, focus the affected editor. Create `const range = document.createRange()`, then call `range.selectNodeContents(editor)` for that editor. Clear `window.getSelection()` with `removeAllRanges()`, then add the range with `addRange(range)`. Then call `document.execCommand('delete')`. This cleared the editable content in the observed browser. Verify the editor contents afterward. Recheck every recipient field before sending.

## Verification

Successful sending closes compose and removes the draft. Confirm the exact subject and recipient in Sent Items before claiming it was sent or retrying. Sent Items confirms submission; recipient-side delivery and SPF/DKIM/DMARC results require separate recipient-side evidence.
