# Mastodon — Hashtag Discovery

Field-tested against `mastodon.social`, `fosstodon.org`, and `hachyderm.io` on 2026-05-15.
Vouched by SmartSocial — used in production by Bob (https://github.com/drmweyers/SmartSocial/tree/main/agents/bob).

**Federation caveat.** Mastodon is not one site. Every instance ships its own (server-side rendered) theme on top of the same `tootsuite/mastodon` upstream, so DOM hashes and CSS class names diverge between instances. Anchor on the **semantic class names** (`.status`, `.account`, `.detailed-status`) and `data-*` attributes that the upstream Rails app emits — those are stable across instances. Avoid layout-shell selectors (sidebar widths, navigation chrome) — those are themed per-instance.

## URL patterns

| What | URL |
|------|-----|
| Hashtag timeline (federated) | `https://<instance>/tags/<tag>` |
| Hashtag timeline (local-only) | `https://<instance>/tags/<tag>?local=true` |
| Single status (canonical, instance-local) | `https://<instance>/@<user>/<status_id>` |
| Remote status (forwards through home instance) | `https://<instance>/@<user>@<remote_instance>/<status_id>` |
| Public local timeline | `https://<instance>/public/local` |
| Account profile | `https://<instance>/@<user>` |

`<tag>` is the hashtag **without** the `#`. `#climate` → `/tags/climate`.

## DOM anchors

| Target | Selector | Notes |
|---|---|---|
| Status container | `article.status, article.detailed-status` | Detailed = the focused status on a permalink page. Both carry `data-id="<status_id>"`. |
| Status text body | `.status__content, .e-content` | Server-rendered HTML — `<p>` paragraphs, `<a class="mention">`, `<a class="hashtag">`. Read `.innerText` for plain text, or `.innerHTML` if you need links/mentions. |
| Author handle | `.display-name__account` | Always the federated form (`@user@instance.tld`). Even on the home instance, this is rendered with the full handle once the status is from a remote actor. |
| Author display name | `.display-name__html` | May contain custom emojis as `<img class="emojione">` — strip if you need plain text. |
| Status timestamp | `time.formatted-date` | The `datetime` attribute is an ISO 8601 string; the visible text is a relative-time renderer (e.g. "3h"). Always read `datetime`, never `innerText`. |
| Status permalink | `a.status__relative-time` | `href` is the canonical URL of the status on its origin instance. |
| Reply button | `button.status__action-bar__button.icon-button[aria-label="Reply"]` | aria-label is localized — match by `title` or by position in `.status__action-bar` (first icon button) if the user's locale isn't English. |
| Favourite button | `button.icon-button.star-icon[aria-label="Favourite"]` | Aria-pressed flips to `true` after click. |
| Boost button | `button.icon-button.reblog-icon[aria-label="Boost"]` | Same pattern as favourite. Do not boost as part of automated engagement — boosts amplify into your followers' timelines and look spammy. |
| Bot badge | `.display-name .bot, .account__header__bot` | Present when `account.bot === true`. **Skip these accounts.** See gotcha below. |

## Bot accounts

**Skip statuses authored by accounts flagged as bots.** Mastodon convention is that bot operators set `bot: true` on their account; engaging back creates bot-on-bot loops that the community considers low-quality. The UI surfaces this as a small "BOT" badge next to the display name (`.account__header__bot` on profile pages, `.display-name .bot` in timelines).

```python
is_bot = js("""(() => {
  const el = document.querySelector('article.status .display-name .bot');
  return !!el;
})()""")
if is_bot:
    # skip — do not extract this status for engagement
    pass
```

## Pulling a hashtag timeline

The federated timeline at `/tags/<tag>` is the canonical discovery surface — it includes posts from the entire fediverse that the home instance has cached, not just locals. The local-only variant (`?local=true`) is fine for niche instances (`fosstodon.org/tags/python`) where you want only that community's voice.

```python
new_tab("https://mastodon.social/tags/climate")
wait_for_load()
wait(1.5)  # SSR is fast but action-bar buttons hydrate after first paint

statuses = js(r"""
  Array.from(document.querySelectorAll('article.status')).map(el => {
    const time = el.querySelector('time.formatted-date');
    const link = el.querySelector('a.status__relative-time');
    const body = el.querySelector('.status__content');
    const acct = el.querySelector('.display-name__account');
    const isBot = !!el.querySelector('.display-name .bot');
    return {
      status_id: el.getAttribute('data-id'),
      url: link?.href || null,
      author: acct?.innerText?.trim() || null,
      created_at: time?.getAttribute('datetime') || null,
      text: body?.innerText?.trim() || '',
      is_bot: isBot,
    };
  }).filter(s => s.status_id && !s.is_bot)
""")
```

## Lazy load — scroll, don't paginate

The timeline is an infinite scroll. There is no "Next page" control. The DOM keeps mounted statuses (~50 visible at a time) and prepends new ones at the top via a small "Show new toots" banner when polling discovers them.

```python
# Collect up to TARGET statuses by scrolling
TARGET = 30
seen = {}
for _ in range(10):  # cap scrolls
    batch = js(...)  # the JS block above
    for s in batch:
        seen.setdefault(s["status_id"], s)
    if len(seen) >= TARGET:
        break
    scroll(640, 400, dy=900)
    wait(1.0)
```

`wait(1.0)` is enough on `mastodon.social` and `fosstodon.org`. On smaller instances with slower hardware (single VPS), bump to `wait(2.0)` if the batch returns the same IDs twice.

## Login wall on remote-status pages

When you click a status that originated on a **different** instance from the one you're browsing, Mastodon may render a federated-actor stub page rather than the full thread. If you are logged in, a "Sign in to participate" interstitial does **not** appear — the page renders with the action bar enabled. If you are anonymous, every action button is replaced with a "You need to be logged in" tooltip and clicking does nothing.

Detect with:

```python
auth_wall = js("""
  (() => {
    const interstitial = document.querySelector('.sign-in-banner, .columns-area__panels__main .activity-stream-tabs');
    const replyBtn = document.querySelector('button[aria-label="Reply"]:not([disabled])');
    return !!interstitial && !replyBtn;
  })()
""")
if auth_wall:
    # stop and ask the user to log in
    pass
```

## Rate-limit signals

Per the upstream Mastodon REST contract, anonymous browse has soft per-IP limits (varies by instance, typically ~300 requests / 5min). The web UI surfaces overage as a generic red toast: "Failed to fetch — please try again." Screenshot to verify; the toast lives in `.notification-bar` and auto-dismisses after 5s.

Don't try to "fix" this with retries — back off and revisit the hashtag in 5-10 minutes. Browsing the same hashtag every <60s for an extended period is a heuristic the operator may flag.

## Gotchas

- **Federation lag.** A status posted on `fosstodon.org` 30 seconds ago may not appear in `mastodon.social/tags/python` for another 30-90 seconds. If you are polling for fresh content, query the origin instance directly when you know it.
- **`time.formatted-date.innerText` is relative**, not ISO. Always read the `datetime` attribute for sortable timestamps.
- **Hashtag is case-insensitive in the URL but case-preserved in the DOM.** `/tags/Python` and `/tags/python` resolve to the same timeline; matched-tag text in the status body keeps the author's original casing.
- **Custom emoji in display names.** `.display-name__html` may render `:emoji_shortcode:` as `<img class="emojione">`. Strip these for plain-text author labels.
- **Detailed-status pages have a different selector.** The permalink page (`/@user/status_id`) uses `article.detailed-status` for the focused status and `article.status` for the surrounding thread context. Match both with `article.status, article.detailed-status` if you want to scrape a thread.
- **Don't boost from automation.** The boost button works the same as favourite mechanically, but boosting amplifies into your own followers' timelines — it's a different social contract. Stick to reply + favourite for engagement workflows.
