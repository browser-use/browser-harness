# Programmable Browser Perception

There is no canonical page state. Before repeated interaction or extraction,
decide what facts would make the next action obvious and write the smallest
observer that returns those facts.

Start from the task's contract, not the page. List the required source or
workflow, expected cardinality, required fields, uniqueness rules, exact-match
rules, and deliverables. The observer and collector should make each of those
conditions measurable. A native search or alternate source is not a valid
substitute when the task explicitly requires evidence from a particular site
or interaction sequence.

Use any browser evidence that fits the current subgoal:

- `page_info()` for identity, viewport, and scroll position
- `cdp("Accessibility.getFullAXTree")` for semantic hierarchy, text, roles,
  values, states, and stable backend node IDs
- targeted `js(...)` for DOM or application state missing from accessibility
- `network_events()` and raw CDP for requests and response bodies
- `capture_screenshot(...)` for layout, imagery, canvas, or visual validation

If unsure, begin with the ingredients that make Browser Use's page state
effective: meaningful text, semantic hierarchy, interactive elements,
backend IDs, values, states, viewport context, and an optional screenshot.
This is a starting recipe, not a required schema.

Put reusable task-local observers in
`$BH_AGENT_WORKSPACE/agent_helpers.py`. They may emit any useful format: JSON
for navigation, JSONL or SQLite for large collections, CSV for comparison, or
plain text. Replace or specialize the observer when the page type or subgoal
changes.

Keep raw captures on disk under `$BH_AGENT_WORKSPACE/observations/` and print
only bounded, decision-relevant projections. A projection must make incomplete
work visible by reporting total records observed, records returned, truncation,
missing or malformed records, and browser or extraction errors.

Do not repeatedly pay to recapture stable data. Query saved artifacts locally
with Python, `jq`, `rg`, or SQLite. Recapture after navigation or meaningful DOM
changes because backend node IDs can become stale.

Use a compile-and-check loop for repeated work:

1. Probe only enough of each page type to understand its structure.
2. Write a deterministic collector that performs the repeated browser loop in
   one foreground Browser Harness invocation and checkpoints raw results.
3. Run a local validator over the saved artifacts. It should report exact
   counts, missing fields, duplicates, malformed records, extraction errors,
   and source mismatches.
4. Revisit only the failed invariants. Do not spend a model turn on every page
   or claim completion while a required invariant is false.
