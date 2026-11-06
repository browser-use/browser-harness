# Gmail: Read the inbox from the list view

URL: `https://mail.google.com/mail/u/<N>/#inbox`

Verified live on 2026-09-20.

## Rule: never open a thread to read it

Opening a thread marks it read. A passive watcher (triage, notifier, digest) must read everything it needs from the **list view** and never click into a row. The list view already exposes sender, subject, snippet, timestamp, unread state and thread id.

## Do this first

```python
rows = js("""(() => {
  return [...document.querySelectorAll('div[role="main"] tr.zA')].map(tr => {
    const from = tr.querySelector('span[email]');
    const ts = tr.querySelector('td.xW span[title]');
    const id = tr.querySelector('[data-legacy-thread-id]');
    const snip = tr.querySelector('.y2');
    return {
      thread_id: id ? id.getAttribute('data-legacy-thread-id') : null,
      unread: tr.classList.contains('zE'),
      from_email: from ? from.getAttribute('email') : null,
      from_name: from ? from.getAttribute('name') : null,
      subject: (tr.querySelector('.bog') || {}).textContent || '',
      snippet: snip ? snip.textContent.replace(/^\\s*-\\s*/, '') : '',
      timestamp: ts ? ts.getAttribute('title') : null,
    };
  });
})()""")
```

## Stable selectors

- Rows: `div[role="main"] tr.zA`.
- Unread: the row carries class `zE`.
- Sender: `span[email]`, with the address in the `email` attribute and the display name in `name`.
- Subject: `.bog`.
- Snippet: `.y2`. The text starts with " - ", strip it.
- Timestamp: `td.xW span[title]`. The full datetime is in the `title` attribute.
- Thread id: the `data-legacy-thread-id` attribute on an element inside the row.
- Page size: 50 rows per page by default.

## Change detection without message ids

The list has **no per-message ids**, only thread ids. To detect a new message in an existing thread, key on:

```text
thread_id + hash(timestamp title, snippet)
```

This is **best-effort** detection. The row's timestamp and snippet reflect the latest message, so the key normally changes when a new message lands in the thread. Thread id alone misses replies; unread state alone misses threads the user already read elsewhere.

Known false negative: if a new message arrives with the same timestamp `title` (at whatever granularity the title shows) **and** the same snippet as the previous one, the key is identical and the new message is missed. Identical short replies sent back to back are the realistic case. The list view has nothing finer to key on, so a watcher that cannot tolerate this needs a different source than the list.

## Account detection

`document.title` has the shape:

```text
Inbox (N) - user@domain - Gmail
```

- Workspace accounts end with the org name instead: `... - <Org> Mail`.
- The unread count `(N)` is omitted entirely when it is zero, so do not require it when parsing.

## Logged out

`mail.google.com` redirects to one of two places when there is no session:

- `accounts.google.com` (sign-in)
- the `workspace.google.com` marketing page

Treat **both** as `logged_out`. Checking only for `accounts.google.com` misses the marketing redirect and leaves the agent scraping a landing page.

## Multi-account

`/mail/u/N/` redirects to `/mail/u/0/` when account index `N` does not exist. After navigating, compare the final URL's index to the one requested, then confirm the account from `document.title`. Do not assume the index you asked for is the account you got.

## Traps

- Clicking a row to "get more detail" marks the thread read. Stay in the list.
- Read the timestamp from the `title` attribute, not from the cell's visible text.
- A zero unread count removes `(N)` from the title, it does not render `(0)`.
- An out-of-range `/u/N/` silently lands on account 0 with no error.
