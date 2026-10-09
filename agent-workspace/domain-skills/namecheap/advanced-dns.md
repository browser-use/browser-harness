# Namecheap — Advanced DNS editor

## Route and selectors

- Domain DNS: `https://ap.www.namecheap.com/domains/domaincontrolpanel/<domain>/advancedns`.
- Host Records and Custom MX each have an `ADD NEW RECORD` link. Scope to the intended section.
- New host rows use `input[placeholder="Host"]`. TXT values use `input[placeholder="Value"]`; CNAME targets use `input[placeholder="Target"]`.
- Record types use Select2. Match the desired `li.select2-result` by text, scroll it into view inside the dropdown, then measure its rectangle and click.
- Host-row save: visible `a.save[data-ng-click="listItem.saveRecord()"]`. An earlier hidden `a.save` belongs to DNS Templates; never use an unfiltered `document.querySelector('a.save')`.

## Saving and verification

The Angular editor saves asynchronously. Blur populated inputs, click the row's save control, and wait until that row leaves editing state before adding another. Verify the saved row's type, host and value. Filling the first Host/Value input while an earlier row remains editable can overwrite that earlier row.

Custom MX has a separate `SAVE ALL CHANGES` control. Changing Mail Settings from Email Forwarding to Custom MX removes the forwarding SPF record; publish the chosen provider's SPF separately.

An expired account session can leave the DNS page rendered while save requests fail after redirecting to login. Reload and check whether authentication is required. Do not assume a filled row was saved.

Use a fresh page load and public DNS resolution to verify persistence. Recent negative DNS responses may remain cached at one recursive resolver after another already returns the new record.
