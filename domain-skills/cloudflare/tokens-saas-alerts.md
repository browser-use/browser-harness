# Cloudflare dash — account API tokens, Cloudflare for SaaS, usage alerts

Editing an existing API token's permissions, turning on Custom Hostnames
(Cloudflare for SaaS) with a fallback origin, and creating usage-based billing
alerts. None of these are available through `wrangler` (its OAuth token is
`account:read`, `zone:read`, `ssl_certs:write`), so they need the dashboard or a
real API token.

## Reading through the dash session

While logged in, same-origin `fetch('/api/v4/...', {credentials:'include'})`
from the dash tab works for **reads** (zones, DNS records, token policies):

```python
js("""(async()=>{const r=await fetch('/api/v4/zones?name=example.com',{credentials:'include'});
return JSON.stringify((await r.json()).result.map(z=>[z.id,z.account.name]));})()""")
```

**Do not use it for writes.** A `POST` with `x-atok: window.bootstrap.atok`
gets an HTML `403 Attention Required` from Cloudflare's own WAF. Use the UI, or
a real API token.

## Which token is "the one the app uses"

Account API tokens and user API tokens are separate lists:
- User tokens: `https://dash.cloudflare.com/profile/api-tokens`
- Account tokens: `https://dash.cloudflare.com/<accountId>/api-tokens`

To find which one a deployed secret is without printing it, verify it at both
endpoints and read only the id:

```bash
curl -s https://api.cloudflare.com/client/v4/user/tokens/verify -H "Authorization: Bearer $T" | jq -c '{success,id:.result.id}'
curl -s https://api.cloudflare.com/client/v4/accounts/<acct>/tokens/verify -H "Authorization: Bearer $T" | jq -c '{success,id:.result.id}'
```

An account token returns `Invalid API Token` from the `/user/` endpoint. Its
current policies are readable with
`GET /api/v4/accounts/<acct>/tokens/<id>` through the dash session.

## Editing a token's permissions

- Edit page: `https://dash.cloudflare.com/<accountId>/api-tokens/tokens/<tokenId>`
  (this URL is already the edit form, with no summary page first).
- `Add policy` appends an "Edit policy" block whose scope defaults to
  **Entire Account**. The scope trigger is a button whose `innerText` is the
  current scope. Options are `[role=option]`: Entire Account, All Domains,
  Specified Domains, Specified Workers, … . After `Specified Domains` a second
  trigger (`Select domains…`) lists zone names as `[role=option]`.
- The previous listbox's options stay in the DOM hidden, so filter with
  `offsetParent !== null` when you look an option up by text.
- Permission search: the input whose placeholder starts with
  `Search for permission`. Each permission row has `Read` / `Edit` checkboxes.
  Coordinate-click them from a screenshot, then re-search to confirm the tick
  held. The group counter (`1/12`) is a quick check.
- Names in the UI differ from the API: "Zone SSL & Certificates → Edit" shows
  as `SSL and Certificates Write` on review. Custom hostnames need exactly this
  permission.
- `Review token` → `Update token`. **Updating a token keeps its secret**, so
  deployed copies keep working. Only "Roll" changes it.

## Cloudflare for SaaS (Custom Hostnames)

- Page: `.../<zone>/ssl-tls/custom-hostnames`. Before enabling it shows
  `Enable Cloudflare for SaaS`. Until then the custom hostnames API answers
  `403 No quota has been allocated for this zone` even with the right
  permission. That is a different error from the permission 403.
- Enabling goes to `.../<accountId>/checkout/payment`: $0/month, 100 hostnames
  included, and **two unticked checkboxes** (Terms of Service; authorize the
  card on file for overage). `Activate` is enabled but does nothing until both
  are ticked. On success the URL becomes `/checkout/confirmation` ("Purchase
  complete"). It commits a card to billing, so get the owner's explicit OK first.
- Fallback origin must be a **proxied** record in the zone. A placeholder
  `AAAA <name> 100::` (proxied) is the usual choice. Setting it by API is
  simpler than the form:
  `PUT /zones/<zone>/custom_hostnames/fallback_origin {"origin":"<host>"}` goes
  from `initializing` to `active` within seconds.

## Usage-based billing alerts

- Create URL: `https://dash.cloudflare.com/<accountId>/notifications/create/billing_usage_alert`
  (the list at `/notifications` → `Add` → row "Usage Based Billing" → `Select`).
- **One product per alert.** Workers requests, Workers CPU, D1 reads and D1
  writes are four separate alerts.
- Fields: `input[name=name]`, `input[name=description]`, then the product
  react-select, then `input[name="filters.limit[0]"]` (number; appears only
  after a product is picked), then `Add email recipient` →
  `input[name="emails.recipients.0"]`.
- The product react-select is **not searchable**. Typing filters it to nothing.
  Focus its `input[id^=react-select][id$=-input]`, press `ArrowDown` to open,
  then click the option by id (`react-select-N-option-M`). The `N` changes
  between page loads, so look it up by `innerText` every time.
- Product values (`filters.product[0]`): `worker_standard_request`,
  `worker_standard_cpu_ms`, `d1_rows_read`, `d1_rows_written`,
  `ssl_for_saas_custom_hostnames`, among 20 others including R2 and Durable
  Objects.
- A password-manager overlay covers the Save button after the email is typed.
  Click it through JS: `[...document.querySelectorAll('button[type=submit]')].find(b=>b.innerText.trim()==='Save').click()`.
  Success redirects to `/notifications` with the new row listed.
