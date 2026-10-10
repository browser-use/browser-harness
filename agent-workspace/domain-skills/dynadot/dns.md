# Dynadot — editing DNS records

Dynadot is a domain registrar (dynadot.com). Editing a domain's DNS requires being **logged in** — every account/DNS page behind the login is gated. There is no anonymous path to the DNS editor.

## Hard prerequisites (don't skip)

- **You must be on a Chrome profile that already has a Dynadot session.** The harness's isolated profile (`~/.browser-harness-chrome`) is a clean profile with no Dynadot cookies — it will only ever show the public marketing site. Connect to the user's real Chrome (where they're logged in) or have the user log in first. This is an auth wall: do **not** type credentials from a screenshot.
- There is **no Dynadot API key** in this environment by default. The registrar does offer an API (`https://api.dynadot.com/api3.html`, key-gated) — if a key exists, prefer it over the browser for DNS edits.

## URL / navigation map (durable)

- Marketing/public site is a **Vue SPA**. Header is `div.navbar` (`data-v-*`). The "Login" control is **not a light-DOM text node** — `querySelectorAll`/TreeWalker text searches for "Login" return nothing. Don't hunt for it by text; click it by screenshot coordinates, or just navigate to a deep account URL while authenticated.
- **Guessed login URLs 404.** All of these return the custom "Oops! Page Not Found" page (HTTP 200 SPA shell, not a redirect): `/account/sign_in`, `/account/sign_in.html`, `/account/signin`, `/login`, `/account/index.html`. Do not rely on them. Reach the dashboard via the homepage Login button after auth, or the post-login dashboard URL Dynadot itself lands you on.
- DNS settings live under the **domain's setting page**, reachable from the logged-in domain manager (Manage → the domain → DNS). The bare `/account/domain/setting/dns.html` without a domain context / session renders the 404 SPA shell.

## `js()` helper gotchas (this harness)

- `js()` evaluates a **single expression**. **IIFEs return `null`/None** — `(function(){...})()` will silently come back as `None`. Use expression style: `Array.from(...).map(...).filter(...)`.
- `js()` reliably serializes **arrays of strings / primitives**. Arrays of **objects** tend to come back as `None`. Return joined strings (`...map(e => a+'|'+b).join(' || ')`), not object literals.
- An **empty array** result also surfaces as `None`, so `None` ≠ "query failed" — it may just mean "no matches."
- Screenshots are **DPR 2**: the PNG is 2× CSS pixels. `click_at_xy` uses CSS pixels (match `page_info` `w`/`h`). Scale screenshot-pixel reads down by the devicePixelRatio before clicking.

## Setting a record (once logged in)

1. Open the domain manager, select the target domain, open **DNS / Nameserver Settings**.
2. Dynadot DNS modes: **Dynadot DNS** (per-record A/CNAME/TXT/MX rows) vs **Custom Nameservers**. To point records at a host, use **Dynadot DNS** and add record rows; to delegate the whole zone elsewhere, use **Custom Nameservers**.
3. Add/edit the row(s), **Save**, then verify with `dig +short A <domain>` from a shell (propagation is usually fast on dyna-ns).

## Verify from shell (no login needed)

```bash
dig +short NS example.com     # ns1/ns2.dyna-ns.net == Dynadot-managed DNS
dig +short A  example.com     # current apex target
whois example.com | grep -iE 'Registrar:|Name Server:|Registry Expiry'
```

## Trap log

- The page `<title>` may be prefixed with a `🟢` emoji from a local browser extension — ignore it; not part of Dynadot.
- "default Chrome requires approval; using isolated Chrome profile" in harness output means you are NOT on the user's logged-in Chrome. Stop and resolve the connection before assuming you can reach account pages.
