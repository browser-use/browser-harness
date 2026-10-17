# Slack: Read channel state from the sidebar

URL: `https://app.slack.com/client/<TEAM_ID>/<CHANNEL_ID>`

Verified live on 2026-09-20 and 2026-09-21, except where marked **unverified** below. In particular, the per-channel unread marker is still unverified, so this file is reliable for enumerating rows and their attributes, not yet for unread detection.

## Rule: never open a channel to check it

Opening a channel clears its unread marker. A passive watcher must read state from the **sidebar** only and never click a row.

## Scope and limits

- **The sidebar only exists in the Home view.** `[data-qa="tab_rail_home_button"][aria-selected="true"]` means Home is showing. In other views, for example `https://app.slack.com/client/<TEAM_ID>/dms`, there are zero `data-qa-channel-sidebar-channel-id` rows. Zero rows means "sidebar not rendered", never "nothing unread".
- **The sidebar is a virtual list** (`.c-virtual_list`, one `.c-virtual_list__item` per entry). Only the rows Slack has rendered are in the DOM, so the snapshot below covers the rendered rows, not the whole workspace. Do not treat it as workspace-wide without checking that every section you care about is rendered. Whether a collapsed section keeps its rows in the DOM was not verified.

## Do this first

```python
# Session first: a signed-out page has no Home button either, so check it before the view.
url = js("location.href")
if "/workspace-signin" in url or "slack.com/signin" in url:
    raise RuntimeError("logged_out")

home = js('!!document.querySelector(\'[data-qa="tab_rail_home_button"][aria-selected="true"]\')')
if not home:
    raise RuntimeError("Slack is signed in but not in the Home view: the channel sidebar is not rendered")

rows = js("""(() => {
  const P = 'data-qa-channel-sidebar-';
  return [...document.querySelectorAll('[' + P + 'channel-id]')].map(el => {
    const name = el.querySelector('[data-qa^="channel_sidebar_name_"]');
    return {
      channel_id: el.getAttribute(P + 'channel-id'),
      type: el.getAttribute(P + 'channel-type'),
      name: name ? name.textContent.trim() : null,
      muted: el.getAttribute(P + 'channel-is-muted'),
      selected: el.getAttribute(P + 'channel-is-selected'),
      starred: el.getAttribute(P + 'is-starred'),
      is_you: el.getAttribute(P + 'is-you'),
      section_id: el.getAttribute(P + 'channel-section-id'),
      shared_type: el.getAttribute(P + 'shared-type'),
    };
  });
})()""")
```

## Stable selectors

Every sidebar row has `data-qa-channel-sidebar-channel-id`. These sibling attributes live on the same element:

| Attribute | Meaning |
| --- | --- |
| `data-qa-channel-sidebar-channel-type` | `channel`, `private`, `im` or `mpim` |
| `data-qa-channel-sidebar-channel-is-muted` | muted flag |
| `data-qa-channel-sidebar-channel-is-selected` | currently open row |
| `data-qa-channel-sidebar-is-starred` | starred flag |
| `data-qa-channel-sidebar-is-you` | the user's own DM row |
| `data-qa-channel-sidebar-channel-section-id` | sidebar section the row belongs to |
| `data-qa-channel-sidebar-shared-type` | present only on Slack Connect / externally shared channels |

- Name: descendant `[data-qa^="channel_sidebar_name_"]`.
- Selected row class: `p-channel_sidebar__channel--selected`.

`data-qa-channel-sidebar-shared-type` is a free internal-vs-external signal: if the attribute is present, the channel includes people outside the workspace. Check for presence, not for a specific value.

## Unread and mention markers (unverified)

There is **no verified per-channel unread signal yet**, which is why `rows` above has no `unread` field. No unread row was rendered on either check (2026-09-20, and a second attempt on 2026-09-21), so the following are **expected but NOT verified**. Confirm them against a live unread row, add the confirmed selector to the extraction above, then update this file:

- Unread rows get class `p-channel_sidebar__channel--unread`.
- Mention badge: `[data-qa="mention_badge"]` or `.c-mention_badge`.
- A `! ` prefix on `document.title` was seen on one workspace tab. What it maps to was not verified, so treat it as a coarse hint at most.

Not an unread signal: `.p-unread_dot` with `data-qa="admin_tab_badge_dot"` sits in the tab rail and is unrelated to channels.

## URL shape

```text
https://app.slack.com/client/<TEAM_ID>/<CHANNEL_ID>
https://app.slack.com/client/<TEAM_ID>/dms          (DMs view, no channel sidebar)
```

## Logged out

Either of these means there is no session. Treat both as `logged_out`:

- `app.slack.com/workspace-signin`
- `slack.com/signin`

## Multiple workspaces

Use one tab per workspace, identified by the `<TEAM_ID>` in its URL.

## Traps

- Clicking a row to inspect it clears the unread marker you were trying to observe.
- Zero sidebar rows means either a signed-out page or a view other than Home. Check the session first, then the view, before concluding anything.
- The sidebar is virtualized, so a row that is not rendered is simply missing from the snapshot.
- The unread class and mention badge selectors above are unverified; do not treat their absence as proof of "nothing unread" until confirmed.
