# Discord — channel scraping

Read full message history from a Discord channel in the logged-in web app. No API token needed — this drives the user's authenticated session. Channel access requires the account to be a member of the server.

## URL pattern

```
https://discord.com/channels/<guildId>/<channelId>
```

Tab title shows unread count + channel name: `🟢 (224) Discord | #channel-name | ServerName`.

## Site structure

- React app, fully virtualized message list — only the messages near the viewport exist in the DOM. To read history you must scroll up in a loop and merge.
- Message list: `ol[data-list-id="chat-messages"]`, items `li[id^="chat-messages-"]`.
- Item id format: `chat-messages-<channelId>-<messageId>`. The message id is a snowflake — sort on it for chronological order across merged batches.
- Scroll container: `main div[class*="scroller_"]`. Set `scrollTop = 0` to trigger loading older messages; wait ~1.5s for the lazy fetch, then re-extract.
- Start-of-channel marker: the scroller's top renders "Welcome to #channel!" / "This is the start of the … channel." Test the scroller's leading `innerText` for `/Welcome to|This is the (start|beginning) of/`. Stop when the marker is present AND an extract pass yields no new ids.
- Timestamps: `time[datetime]` inside the item — absolute ISO, no parsing of "Yesterday at…" needed.
- Embeds (link previews, tweets, GitHub cards): `article` elements; `innerText` gives a usable text rendering.
- Reactions: `div[class*="reaction"] img` — `alt` holds the emoji or custom-emoji name.

## Traps

- **Reply previews duplicate the content id.** A reply message contains the quoted preview of the parent, and that preview div ALSO matches `div[id^="message-content-"]`. `querySelector` returns the preview, so you silently scrape the quoted text instead of the actual reply body. Select all matches and keep the one not inside `div[class*="repliedMessage"]`:

  ```js
  const contentEl = [...li.querySelectorAll('div[id^="message-content-"]')]
    .find(el => !el.closest('div[class*="repliedMessage"]'));
  ```

- **Grouped messages have no author node.** Consecutive messages from the same author within ~7 minutes render without the `h3` header. Author selector `h3 span[class*="username"]` returns null for them — forward-fill from the previous message after sorting.
- **`h3` innerText is polluted.** Grabbing the whole `h3` text concatenates username + server tag + timestamp tooltip ("kaue [STBR], Server Tag: STBR — 7/17/26…"). Use the `span[class*="username"]` child only.
- **Edited messages append the edit tooltip** ("(edited)\nSunday, July 19 …") to `innerText` of the content div. Strip trailing date lines if exact text matters.
- Message links include internal `https://discord.com/channels/...` jump links — filter them if you only want external references.

## Extraction loop shape

Per pass: collect `{id, author, time, text, replyTo, links, embeds, reactions}` for every `li`, merge into a dict keyed by id, scroll top, sleep ~1.5s, repeat until start marker + zero new ids. A ~25-message channel takes 2–3 passes at a full-height viewport.

## Pinned messages

Open with `document.querySelector('[aria-label*="Pin"]').click()`; the popout is `div[class*="messagesPopout"]` — read its `innerText`. Empty state renders "This channel doesn't have any pinned messages... yet."
