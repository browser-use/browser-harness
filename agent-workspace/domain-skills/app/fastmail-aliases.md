# Fastmail — aliases on an existing custom domain

Applies to `app.fastmail.com`.

- In My email addresses, Add address offers different operations. Choose Create alias
  for an address hosted on a custom domain already attached to the account. Adding an
  address owned elsewhere is a different workflow.
- Select the existing custom domain rather than creating another paid user when the
  requirement is simply another inbound address for the current mailbox.
- Creating an alias can open its details view. Save that view and verify the alias in
  the address listing; reaching the details page alone does not prove it was saved.
- Custom-domain status such as `Active. MX records set.` describes the domain's routing.
  Individual aliases need no separate DNS records. Preserve the domain's root MX,
  SPF, DKIM and DMARC records when configuring another service's sending subdomains.
- Domain routing and a saved alias do not prove inbound delivery. Verify delivery
  separately when authorized; an empty `to:<alias>` search alone is inconclusive.
- The settings UI is asynchronous. Wait for the expected address listing or saved
  notification after navigation and form submission; generated input IDs are unstable.
