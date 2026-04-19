# Cloudflare — Operator workflows for Cathedral

`https://dash.cloudflare.com`

Use Cloudflare in browser-harness for **dashboard truth** and UI-only operations:
- zone inventory
- DNS verification
- Workers/routes checks
- account / billing / security settings review
- nameserver / registrar / domain-state confirmation

## Default stance

Prefer browser automation for:
- confirming what the dashboard actually shows
- inventorying zones, records, routes, rules, plans, and alerts
- preparing a change and stopping before the final destructive click

Prefer API / terminal / IaC for:
- bulk DNS export
- high-volume mutations
- reproducible deploy flows

Use the browser when the truth is trapped in the UI.

## High-value routes

Start at:
- `https://dash.cloudflare.com/`

Common destinations once a zone is selected:
- DNS
- Workers & Pages
- Rules
- SSL/TLS
- Security
- Analytics
- Domain Registration / Registrar when present

Cloudflare moves fast. Prefer:
- account switcher first
- zone search second
- then left-nav labels by visible text

## Reliable workflow pattern

1. `ensure_real_tab()`
2. `goto("https://dash.cloudflare.com")`
3. `wait_for_load()`
4. `screenshot()` immediately
5. use visible text + links/buttons, not brittle CSS classes
6. after every major navigation, `screenshot()` again

## What to extract every time

For a zone audit, collect:
- selected account name
- selected zone
- plan tier
- nameserver pair
- DNS record table snapshot
- proxy status for key records
- SSL mode / cert status
- Workers routes / Pages custom domains if relevant

## DNS record review

Best practice:
- filter/search by record name
- inspect visible table rows
- read type, name, content/target, proxy state, TTL

For Cathedral work, always verify at least:
- apex
- `www`
- mail records (`MX`, `TXT`, `_dmarc`, DKIM selectors, `autodiscover`)
- app / API subdomains
- challenge / verification records

## Safe actions

Usually safe:
- inventory
- screenshots
- open forms
- review pending values
- compare dashboard state against live DNS

Approval boundary:
- saving DNS edits
- changing nameservers / registrar settings
- changing SSL mode
- deleting records / routes / rules
- billing / subscription changes

## Common traps

- **Wrong account context** — the UI may remember the last account. Confirm account name before every conclusion.
- **Search/filter residue** — Cloudflare tables often persist filters. Clear filters before claiming a record is absent.
- **Proxy misunderstanding** — orange-cloud vs grey-cloud is operationally important; capture it explicitly.
- **Workers/Pages split-brain** — custom domains may be configured under either product surface. Check both when troubleshooting.
- **UI truth vs live truth** — confirm important claims with browser + terminal (`dig`, `curl`, cert check). Cloudflare UI alone is not enough.

## Best Cathedral uses

- domain stack audits
- pre-change screenshots before DNS work
- post-change verification after deploys
- Workers / Pages routing review
- registrar-transfer readiness review

## Output format for Cathedral agents

Return:
- account
- zone
- page visited
- screenshot summary
- exact state observed
- recommended action
- whether action requires approval