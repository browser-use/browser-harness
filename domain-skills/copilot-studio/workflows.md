---
name: copilot-studio-workflows
description: Microsoft Copilot Studio new-experience workflow automation — recurrence schedules, existing-agent nodes, connection setup, safe tests, and publishing.
---

# Copilot Studio — scheduled workflows

Copilot Studio's new agent experience uses one Build surface with the tabs **Build**, **Preview**, **Evaluate**, and **Monitor**. It does not expose the classic agent's Overview > Triggers section. To run a new-experience agent on a schedule, create a **Workflow** with a Recurrence start node and an Agent action.

## URL shapes

- Agent: `https://copilotstudio.microsoft.com/environments/<environment-id>/agents/<agent-id>`
- Workflow list: `https://copilotstudio.microsoft.com/environments/<environment-id>/workflows`
- New workflow: `/environments/<environment-id>/flows/new?creationMechanism=WorkflowsNew`
- Saved workflow: `/environments/<environment-id>/flows/<workflow-id>`

The site is a single-page application. Navigation can be delayed while the agent editor has unsaved changes. Save the agent before leaving its Build page; otherwise Copilot Studio opens a **Leave without saving?** prompt.

## Create a scheduled workflow

1. Open **Workflows** from the left navigation and select **New workflow**.
2. Rename `Untitled workflow` from the title in the top-left.
3. Select the Start node. Change **Trigger type** from Manual to **Recurrence**.
4. Configure frequency, interval, days, hours, minutes, and time zone.
5. Add an **Agent** action. If the Start node is selected, clicking Agent in the Add rail inserts and connects it after Start.
6. Create or choose the Agent connection. Creating a connection opens a Microsoft OAuth popup with the Power Platform Agent connector. Stop for human authentication if the popup reaches an account picker or credential prompt.
7. In the Agent dropdown, select an existing published agent. Unpublished agents are listed separately and cannot be used.
8. Enter the natural-language Message that the workflow sends to the agent for each run.
9. Save, test, and publish.

## UI details that matter

- The recurrence frequency dropdown supports Minute, Hour, Day, Week, and Month.
- Week exposes seven checkbox inputs in Sunday-through-Saturday order.
- Hours and minutes accept comma-separated numbers.
- The time-zone and agent dropdowns are long portal listboxes. All options can be in the DOM but outside the viewport. Locate the desired `[role=option]`, call `scrollIntoView({block: 'center'})`, re-read its rectangle, then click it by coordinates.
- The Agent action defaults to **New agent for this workflow**. Open its Agent combobox to choose a published existing agent.
- Multiple Copilot Studio tabs with the same title are common. Attach to the exact target whose URL contains `/flows/` and use `Target.activateTarget` before coordinate interaction.

## Test without producing side effects

For an agent that can send messages or modify data, temporarily replace the Message with a test instruction that explicitly forbids those actions. Use **Run node**, verify `status: Completed`, then restore the production Message before saving and publishing.

For rich token-input editors, select all text without emitting a character:

```python
click_at_xy(x, y)
press_key("Home", modifiers=2)       # Ctrl+Home
press_key("End", modifiers=10)       # Ctrl+Shift+End
press_key("Backspace")
type_text(production_message)
```

Do not use `press_key("a", modifiers=2)` with this harness version: the helper also emits the character and can corrupt the field.

## Publishing verification

After Save, select **Publish** and wait until:

- the top-level status changes from Draft to **Published**;
- the URL changes from `/flows/new?...` to `/flows/<workflow-id>`;
- reopening the Recurrence node still shows the intended frequency, selected days, time, and time zone.

Node-level tests appear separately from scheduled workflow run history, so an empty Activity list immediately after publication is expected.
