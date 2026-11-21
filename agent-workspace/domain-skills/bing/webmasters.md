# Bing Webmaster Tools — add a site, import from Google Search Console

Host: `www.bing.com/webmasters`. The skill lookup uses `bing`.

## URL patterns

- Home: `https://www.bing.com/webmasters`
- Per-site pages take `?siteUrl=<url-encoded site URL>`:
  - `https://www.bing.com/webmasters/sitemaps?siteUrl=...`
  - `https://www.bing.com/webmasters/urlinspection?siteUrl=...`
  - `https://www.bing.com/webmasters/indexnow?siteUrl=...`

## Sign-in

Bing accepts a Microsoft, Google or Facebook account. If the site is already
verified in Google Search Console, sign in with that same Google account.
Google may show its own account chooser or a re-authentication step; stop and
ask the user if it asks for a password.

## Fastest path: import from Google Search Console

1. On the "Add your site" screen, choose "Import your sites from GSC".
2. Approve the Google OAuth consent for Search Console read access.
3. Select the sites to import, then click "Import".

The import does all of this:

- The site arrives as verified, with the Administrator role. You need no Bing meta tag, XML file or DNS record.
- The sitemaps registered in GSC are imported too. Their status starts as "Processing" and can stay so for a day or more.

Only properties that the Google account owns or fully manages in GSC show up in the import list.

## Manual path

"Add site manually" offers three methods: an XML file (`BingSiteAuth.xml`), a
`<meta name="msvalidate.01">` tag, or a DNS CNAME record. Use it only when GSC import is not possible.

## IndexNow

IndexNow is separate from verification. It needs two things:

1. A key file at `https://<host>/<key>.txt` whose body is the key. Bing shows the key on the IndexNow page.
2. A ping on each deploy, for example `GET https://api.indexnow.org/indexnow?url=<changed URL>&key=<key>`, or a POST with a URL list.

Without the key file on the site, every ping fails. A sitemap alone works without IndexNow; IndexNow only speeds up re-crawls.

## URL inspection

URL Inspection shows the index state of one URL and offers "Request indexing".
Like GSC, it has a daily quota per site.
