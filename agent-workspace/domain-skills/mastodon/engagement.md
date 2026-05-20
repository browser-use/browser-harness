# Mastodon — Reply, Favourite, Follow

Field-tested against `mastodon.social` and `fosstodon.org` on 2026-05-15 using a logged-in browser session.
Vouched by SmartSocial — used in production by Bob (https://github.com/drmweyers/SmartSocial/tree/main/agents/bob).

**Prereq:** logged in on the instance you are engaging from. The action bar buttons render but no-op when anonymous. Use `interaction-skills/profile-sync.md` to bring up a logged-in browser if running remote.

**Scope:** reply + favourite + follow. **Boost is intentionally excluded** — boosting amplifies into your followers' timelines and is a different social contract than a quiet reply or fav. If you need boost behaviour, ask first.

## Replying to a status

The reply button on every status opens an inline compose form. The form is the same composer the homepage uses, just pre-populated with the parent author's handle as the first mention.

```python
# Assumes you have already navigated to a status permalink or a timeline
# entry. Click the Reply button on the target article.
clicked = js(r"""
  (() => {
    const art = document.querySelector('article.status[data-id="STATUS_ID_HERE"]');
    if (!art) return false;
    const btn = art.querySelector('button.icon-button[title="Reply"], button.icon-button[aria-label="Reply"]');
    if (!btn) return false;
    btn.click();
    return true;
  })()
""")
if not clicked:
    raise RuntimeError("reply button not found — wrong status id or not yet hydrated")

wait(0.8)  # composer expands inline; ~500ms of CSS transition

# Compose
js(r"""
  (() => {
    const ta = document.querySelector('textarea.autosuggest-textarea__textarea, textarea#status-textarea');
    if (!ta) throw new Error('compose textarea not found');
    const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
    setter.call(ta, 'YOUR_REPLY_TEXT_HERE');
    ta.dispatchEvent(new Event('input', { bubbles: true }));
  })()
""")

# Publish
clicked = js(r"""
  (() => {
    const btn = document.querySelector('button.button.button--block, button[type="submit"].button[class*="primary"]');
    if (!btn || btn.disabled) return false;
    btn.click();
    return true;
  })()
""")
```

**Why the setter dance.** Mastodon's compose box is a React-controlled textarea. Setting `textarea.value = "..."` directly does not fire React's onChange — the publish button stays disabled because internal state still says "empty." Using the native `HTMLTextAreaElement.value` setter + dispatching `input` is the standard React-input bypass.

### Verifying the reply landed

After the publish click, the composer collapses and a new `article.status` is prepended into the thread descendants below the parent. Verify by either:

```python
# Path 1 — wait for the composer to disappear (cheap, instance-agnostic)
import time
for _ in range(15):
    open_composer = js("document.querySelector('textarea#status-textarea') !== null")
    if not open_composer:
        break
    time.sleep(0.2)

# Path 2 — pull the most recent status in the thread and check its author.
# The composer collapses after publish, so read the logged-in handle from the
# top-of-page navigation bar (or the column-link "/@me" href) instead.
my_handle = js(r"""
  (() => {
    const a = document.querySelector('a.column-link[href^="/@"]');
    return a ? a.getAttribute('href').replace(/^\//, '') : null;
  })()
""")
latest = js(r"""
  (() => {
    const arts = Array.from(document.querySelectorAll('article.status'));
    const last = arts[arts.length - 1];
    if (!last) return null;
    return {
      id: last.getAttribute('data-id'),
      author: last.querySelector('.display-name__account')?.innerText?.trim() || null,
      text: last.querySelector('.status__content')?.innerText?.trim() || '',
    };
  })()
""")
# latest.author should match my_handle and latest.text should contain your reply.
```

Path 1 is sufficient for fire-and-forget engagement. Path 2 matters if you need the new `status_id` to persist (e.g. for tracking the engagement outcome 6h later).

## Favourite a status

The favourite (star) icon is the second action-bar button on every status. The button's `aria-pressed` attribute toggles to `true` when the API call succeeds.

```python
ok = js(r"""
  (() => {
    const art = document.querySelector('article.status[data-id="STATUS_ID_HERE"]');
    if (!art) return false;
    const btn = art.querySelector('button.icon-button.star-icon, button[aria-label="Favourite"]');
    if (!btn) return false;
    btn.click();
    return true;
  })()
""")
wait(0.5)

pressed = js(r"""
  (() => {
    const art = document.querySelector('article.status[data-id="STATUS_ID_HERE"]');
    const btn = art?.querySelector('button.icon-button.star-icon, button[aria-label="Favourite"]');
    return btn?.getAttribute('aria-pressed') === 'true';
  })()
""")
```

Favouriting is idempotent in the UI — clicking an already-favourited status un-favourites it. Read `aria-pressed` **before** you click if you only want to set it (not toggle).

## Follow an account

From a profile page (`/@user` on the home instance, or `/@user@remote_instance` for a federated actor):

```python
new_tab("https://mastodon.social/@example_user")
wait_for_load()
wait(1.2)

# The follow button text varies by current state:
#   "Follow" (not following) → click to follow
#   "Following" (already following) → already done, skip
#   "Cancel follow request" (locked account, request pending) → already requested
#   "Unblock" / blocked / muted → stop, account is in a bad state

state = js(r"""
  (() => {
    const btn = document.querySelector('.account__header__tabs__buttons button.button, button.logo-button');
    if (!btn) return 'no-button';
    return (btn.innerText || '').trim().toLowerCase();
  })()
""")
# 'follow' → safe to click
# 'following' → no-op, you are done
# 'cancel follow request' → pending, no-op
# anything else → stop and inspect
```

### Locked accounts

Accounts with `🔒 Locked` next to their display name require the operator to approve the follow request manually. Clicking Follow on a locked account silently changes the button to "Cancel follow request" — there is no toast. The actual follow doesn't happen until the operator approves it on their end, which can take hours or never. For automation: treat "Cancel follow request" as a soft success but do not assume you can DM the account, see their followers list, etc.

## Confidence threshold for auto-engagement

For autonomous engagement workflows (no human in the loop), only send a reply if your generated draft scores `confidence ≥ 0.85` against the parent post's intent. Below that, queue for human approval. Mastodon's culture is small-instance, slow-social — low-quality drive-by replies get reported quickly, and reports stick to your handle, not your IP. This is the threshold Bob uses in production.

Favourite is lower-stakes — favouriting a status that passed your discovery filter is reasonable at any confidence. The signal cost of a wrong favourite is near zero.

## Rate limits

The web UI enforces the same per-account API limits as the REST endpoint (`/api/v1/statuses`, `/api/v1/statuses/:id/favourite`, etc.). On a default `mastodon.social` account that's roughly **300 status creates per 5 hours** and **300 favourites per 5 hours**. Per-instance limits vary; smaller community instances often configure tighter caps.

Symptoms of rate limit:
- Publish button stays disabled after click + a red toast "Failed to publish — please try again."
- Favourite button's `aria-pressed` does not flip to `true` after a click.

When this happens, the response carries an `X-RateLimit-Reset` header (an ISO timestamp). The web UI does not expose it — you'll need to wait the cool-down (5 minutes is enough for most overages, hours for sustained abuse).

For sustained engagement Bob caps at **~10 replies / hour and 50 / day** per account, well under the upstream limit. The cap is account-level, not IP-level, so multiple tabs share one bucket.

## Gotchas

- **Composer setter must use the React bypass.** Plain `textarea.value =` leaves the publish button disabled because the React-controlled state still says empty.
- **Reply landed but no `status_id` in the URL.** The composer does not navigate after publish — it collapses inline. To capture the new status's id you have to scrape the prepended `article.status` in the thread (Path 2 above) or follow up with a profile-page visit.
- **`aria-label` is localized.** Match the action buttons by class (`.star-icon`, `.reblog-icon`, `.icon-button[title="Reply"]`) when supporting non-English locales — the `aria-label` text is translated.
- **Favourite is a toggle.** If you don't read `aria-pressed` first, you may un-favourite something you already favourited from a previous run.
- **Locked accounts swallow follows silently.** Don't assume `button.innerText === "Following"` means the request succeeded — "Cancel follow request" is a different terminal state.
- **Federation latency on replies.** A reply you send from `mastodon.social` to a `fosstodon.org` author will land in fosstodon's notification feed within seconds, but their reply back may not appear in your `mastodon.social` mentions for up to a minute. Don't poll for outcomes faster than once per 60s.
- **Skip `account.bot === true` accounts.** Engaging back creates bot-on-bot loops the community frowns on. See `discovery.md` for the bot-badge selector.
- **Don't boost from automation.** Mechanically identical to favourite, socially very different — boosting puts the post into your own followers' timelines. Stick to reply + favourite.
