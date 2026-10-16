# Google Search Console — verify a site, submit a sitemap, inspect a URL

Host: `search.google.com/search-console`. The skill lookup uses the first host
label, so this file lives in `domain-skills/search/`.

## URL patterns

- Home / property picker: `https://search.google.com/search-console`
- Pick a Google account by index: `https://search.google.com/u/<N>/search-console`
- Add a property: `https://search.google.com/search-console/welcome`
- Open one property: `https://search.google.com/search-console?resource_id=<url-encoded property>`
  - URL-prefix property: `resource_id=https%3A%2F%2Fwww.example.com%2F`
  - Domain property: `resource_id=sc-domain%3Aexample.com`
- Sitemaps: `https://search.google.com/search-console/sitemaps?resource_id=...`
- URL inspection: `https://search.google.com/search-console/inspect?resource_id=...&id=<url-encoded page URL>`
- Pages (index coverage): `https://search.google.com/search-console/index?resource_id=...`

The `resource_id` must match the property exactly, including the scheme,
`www.` and the trailing slash. A mismatch shows an empty "property not found" page.

## Accounts and sessions

- Google sessions are per Chrome profile. Open the tab in the profile that
  owns the property (see `interaction-skills/tabs.md`, "Background tab in a
  specific profile").
- With several Google accounts in one profile, `/u/<N>/` and `?authuser=<N>`
  select the account. `N` is the sign-in order in that profile, not a stable ID.
  Read the account email from the avatar menu before you act.
- Search Console can ask for re-authentication ("Verify it's you") even when
  Gmail in the same profile is signed in. Stop and ask the user. Do not type
  credentials.

## Verification: URL-prefix property with the HTML meta tag

The domain property needs a DNS TXT record. The URL-prefix property accepts an
HTML meta tag, which is the fastest path when you control the site source.

1. Open `/search-console/welcome` and use the right-hand "URL prefix" box.
2. Type the full URL with scheme and trailing slash, then continue.
3. Expand "HTML tag" in the verification dialog and copy the `<meta name="google-site-verification" ...>` tag.
4. Add the tag inside `<head>` of the home page and deploy.
5. Confirm the tag is live with `http_get(url)` before you click "Verify".
6. Click "Verify". On success, the dialog says "Ownership verified".

Traps:

- Prerendered / SSG sites: put the tag in the static HTML template, outside any
  block that the framework replaces per route. Otherwise the deployed HTML may lose it.
- Keep the tag forever. Google re-checks it and drops the ownership if the tag disappears.
- Verification fails if the deploy is still propagating. Check the live HTML first, then click.

## Sitemaps

1. Open the Sitemaps page for the property.
2. Type the sitemap path relative to the property (for example `sitemap.xml`) in "Add a new sitemap".
3. Submit. The table row shows a status and "Discovered pages".

The status can show "Couldn't fetch" for a few minutes after the submit. Reload
before you treat it as a failure.

## URL inspection

- Use the `inspect?...&id=` deep link, or type the URL in the top search bar.
- The result says "URL is on Google" or "URL is not on Google".
- "Request indexing" runs a live test first (about 1 minute). Wait for the
  dialog "Indexing requested" before you leave the page.
- Indexing requests have a daily quota per property. Do not loop it over every URL; submit a sitemap instead.

## Reading data

The page is a heavy client-rendered SPA. `wait_for_load()` returns before the
report data renders. Poll for the visible text you need (for example
"Discovered pages" or "URL is on Google") with `js(...)` before you read it.
