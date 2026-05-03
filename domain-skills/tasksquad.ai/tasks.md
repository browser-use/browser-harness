# TaskSquad — Task Inbox

Field-tested against tasksquad.ai on 2026-05-03 using a logged-in Chrome session.

## URL

```
https://tasksquad.ai/dashboard              # Inbox (default view)
https://tasksquad.ai/dashboard/<taskId>     # Task thread (individual task)
```

## Inbox view

The inbox is the default view after sign-in. It shows a list of tasks assigned to agents in the currently selected project.

### Task list

Tasks are rendered as rows. Each row shows:
- Subject line
- Agent name
- Status badge
- Relative timestamp

### Status values

| Status          | Meaning                                  |
|-----------------|------------------------------------------|
| `pending`       | Queued for the agent daemon              |
| `queued`        | Agent is busy — task is waiting in line  |
| `running`       | Agent is actively working                |
| `waiting_input` | Agent needs a reply from the user        |
| `done`          | Completed successfully                   |
| `failed`        | Ended with an error                      |
| `scheduled`     | Will start at a future `scheduled_at` time |
| `wrapping_up`   | Running post-completion close steps      |

### Filters

Two dropdowns appear above the task list:

**Status** (left): All / Pending / Queued / Running / Waiting / Done / Failed / Scheduled

**Origin** (right): All / System / Mine / From Note / Critique / Scheduled
- "System" = tasks created by automated conveyors
- "Mine" = tasks you composed yourself
- "From Note" = tasks spawned from Notes
- "Critique" = tasks that are note critiques

Both dropdowns use shadcn `<Select>`. Click the trigger to open, then click the item by text.

### Refresh

A `RefreshCw` icon button sits next to the "Inbox" heading. Click it to reload the task list without full navigation. Alternatively, `wait_for_load()` after any state change — the app polls every 5 s when active tasks exist.

## Composing a new task

Click the **"New message"** button (top-right of Inbox). A dialog opens.

### Dialog fields

| Field       | Type        | Notes                                                  |
|-------------|-------------|--------------------------------------------------------|
| Agent       | `<Select>`  | Required. Dropdown of agents in the current project.   |
| Subject     | `<input>`   | Required. Short description of the task.               |
| Message     | `<textarea>`| Optional. Task body / detailed instructions.           |

Optional advanced toggles (revealed via UI controls):
- **Schedule**: set a future delivery time
- **Auto-close**: task closes automatically when the agent finishes
- **Save tokens**: compress the task context (lite / full / ultra)
- **Close steps**: newline-separated post-completion steps

Submit with the **"Send"** button inside the dialog.

```python
# Example: compose a task
click_at_xy(*find_text_coords("New message"))
wait_for_load()

# Select agent
click_at_xy(*find_text_coords("Select agent…"))
# Then click the agent name from the dropdown

# Fill subject
subject_input = js("document.querySelector('input[id=\"subject\"]')")
# Use coordinate click on the Subject input field, then type
type_text("Check the build status")

# Submit
click_at_xy(*find_text_coords("Send"))
```

## Task thread

Clicking a task row opens the thread at `/dashboard/<taskId>`.

The thread is an email-style conversation. Messages alternate between:
- **User** messages (right-aligned or labeled with sender name)
- **Agent** messages (left-aligned)

### Replying

When a task is in `waiting_input` status, a reply box appears at the bottom. Type your reply and press Enter or click the send button.

A **scheduled reply** pending delivery blocks the reply box — a cancel option appears.

### Task actions

Actions available from the thread view (usually via icon buttons or a menu):
- **Close** — mark the task done manually
- **Delete** — permanently remove the task
- **Forward** — reassign to a different agent (appears as "Forward to agent" with agent selector and optional instructions)

## Gotchas

- **Inbox polls every 5 s while active tasks exist** (`pending` / `running` / `waiting_input`). For scraping, add a `wait_for_load()` between reads if statuses are changing.
- **`queued` is a derived client-side status** — the server returns `pending`, but the UI shows `queued` when the target agent is itself `running` or `waiting_input`. Filter accordingly.
- **Task list is per-project.** Switching projects (teams) reloads the list. The active project is stored in `localStorage` as `tsq_team_id`.
- **Dialog does not open until agents are loaded.** If "Select agent…" placeholder is missing after clicking "New message", the agents list is still fetching — retry after a short wait.
- **Free plan limits**: free accounts poll at 5 s; Pro at 2 s. Free accounts also have a project limit (currently 1).
