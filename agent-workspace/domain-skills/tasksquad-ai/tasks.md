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

A `RefreshCw` icon button sits next to the "Inbox" heading. Click it to reload the task list without full navigation. Alternatively, `wait_for_load()` after any state change — the app auto-polls when active tasks exist (interval depends on plan; see Gotchas).

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
import json

def _coords_by_text(label, tag="button"):
    """Find an element by exact innerText and return click coords, or raise."""
    sel = json.dumps(tag)
    txt = json.dumps(label)
    result = js(f"""
      var el = Array.from(document.querySelectorAll({sel}))
                .find(e => (e.innerText || "").trim() === {txt});
      if (!el) return null;
      var r = el.getBoundingClientRect();
      return JSON.stringify({{x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)}});
    """)
    if result is None:
        raise RuntimeError(f"{tag!r} with text {label!r} not found")
    p = json.loads(result)
    return p["x"], p["y"]

def _coords_by_selector(selector):
    """Find an element by CSS selector and return click coords, or raise."""
    sel = json.dumps(selector)
    result = js(f"""
      var el = document.querySelector({sel});
      if (!el) return null;
      var r = el.getBoundingClientRect();
      return JSON.stringify({{x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)}});
    """)
    if result is None:
        raise RuntimeError(f"selector not found: {selector!r}")
    p = json.loads(result)
    return p["x"], p["y"]

# Open the compose dialog
click_at_xy(*_coords_by_text("New message"))
wait(1.0)  # let the dialog mount; agents may still be loading

# Open the agent <Select> trigger and pick an agent.
# The trigger renders the placeholder "Select agent…" until an agent is chosen.
click_at_xy(*_coords_by_text("Select agent…"))
wait(0.5)
# Then click the agent name from the opened dropdown:
click_at_xy(*_coords_by_text("YOUR_AGENT_NAME"))

# Focus the subject input, then type
click_at_xy(*_coords_by_selector('input[id="subject"]'))
type_text("Check the build status")

# (Optional) focus the message textarea and type the body
# click_at_xy(*_coords_by_selector('textarea'))
# type_text("Detailed instructions go here.")

# Submit
click_at_xy(*_coords_by_text("Send"))
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

- **Inbox auto-polls while active tasks exist** (`pending` / `running` / `waiting_input`). Free plan polls every 5 s, Pro every 2 s. For scraping, add a `wait_for_load()` between reads if statuses are changing.
- **`queued` is a derived client-side status** — the server returns `pending`, but the UI shows `queued` when the target agent is itself `running` or `waiting_input`. Filter accordingly.
- **Task list is per-project.** Switching projects (teams) reloads the list. The active project is stored in `localStorage` as `tsq_team_id`.
- **Dialog does not open until agents are loaded.** If "Select agent…" placeholder is missing after clicking "New message", the agents list is still fetching — retry after a short wait.
- **Free plan project limit**: free accounts have a project limit (currently 1).
