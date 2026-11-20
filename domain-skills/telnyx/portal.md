# Telnyx Customer Portal

## URL patterns (hash-routed SPA)

- My Numbers: `https://portal.telnyx.com/#/numbers/my-numbers`
- Number editor: `#/numbers/my-numbers/<numeric-id>` (tabs: Settings, Messaging, Voice, Emergency Service)
- SIP connections: `#/voice/connections`, editor `#/voice/connections/<id>`
  (tabs: Configuration, Authentication and routing, Inbound, Outbound, Recording, Numbers, WebRTC)

## Structure and quirks

- The numbers table is NOT `<table>/<tr>` markup — row queries via `tr` return
  nothing. Use coordinate clicks on the row's pencil icon (rightmost controls)
  or navigate to the editor URL directly by id.
- Numbers in "Port pending" status show a pencil, but clicking it does not
  open the editor — number-level settings appear locked until the number is
  Active.
- Selected dropdown values (e.g. "Destination number format" on a SIP
  connection's Inbound tab) are not in `body.innerText`; read the nearest
  `input`/`[class*=singleValue]` value near the label instead.
- Useful facts surfaced there: "Destination number format: E.164" means DIDs
  arrive WITHOUT the plus (11-digit `1NPANXXXXXX`); "+E.164" is a separate
  option. CNAM Listing toggle + Caller ID Name live on the number's Voice
  tab; "Active Services" checklist on the Settings tab mirrors them.
- Tables/lists render a few seconds after `wait_for_load()` reports done —
  screenshot again before concluding a list is empty.
