# Resend — sending domains and scoped API keys

Applies to `resend.com`.

## Domain setup

- Domain inventory is `/domains`; creation starts at `/domains/add`.
- Review Advanced options, including the selected region and tracking switches.
- The DNS step offers Auto configure and Manual setup. Manual setup exposes the exact
  records without delegating broader DNS changes to the provider.
- Use the records currently shown for that domain. New sending infrastructure can use
  CNAME records rather than the older MX/TXT return-path examples.
- DNS values are visually truncated and their `textContent` can contain an ellipsis
  marker plus hidden text. The copy control's `aria-label="Copy <full-value>"` carries
  the complete value. Do not publish the displayed ellipsis as DNS content.
- `#sending-toggle` and `#receiving-toggle` expose `aria-checked`. Verify receiving
  stays disabled for a sending-only integration. Add only its DKIM/sending records;
  preserve the existing mailbox provider's root MX/SPF/DKIM/DMARC records.
- `I've already added the records` starts verification. Public DNS resolution and the
  domain's verified status are distinct checks; verification is asynchronous.

## API keys

- `/api-keys` → Create API key opens Add API Key. Permission defaults to Full access;
  explicitly select Sending access and the intended domain before Add.
- Searchable options may render after the combobox opens. Re-measure after opening.
- The result opens a second View API Key dialog while the first dialog remains in the
  DOM. `document.querySelector('[role=dialog]')` can select the stale creation form.
  The once-only generated value is in `input#apiKey` (type password).
- Preflight secret storage before Add, store and read-verify the value without logging
  or screenshots, then close/navigate away from the result.
- A sending-only key's failure on a domain-management endpoint does not by itself
  establish that the key is invalid. Check its intended permission and domain scope.
