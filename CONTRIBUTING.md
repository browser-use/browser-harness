# Contributing to Browser Harness

Pull requests and improvements are welcome. Bug fixes, documentation changes,
helper improvements, and focused domain skills are all useful.

## Development

From a checkout, use `./browser-harness` to run the current working tree instead
of the globally installed command. It rebuilds the Go binary from `go/` when Go is
installed:

```bash
./browser-harness <<'JS'
print(page_info())
JS
```

Run the unit tests with `(cd go && go test ./...)`.

Agent-facing documentation should use `browser-harness`. The `./browser-harness`
launcher is only for testing a local checkout.

## Domain skills

Domain skills teach the agent selectors, flows, and edge cases it would otherwise
have to rediscover. Set `BH_DOMAIN_SKILLS=1` to enable them from the agent
workspace.

- Let the harness write skills while it works. Agent-generated skills reflect
  what actually works in the browser; do not hand-author them.
- Copy the generated `domain-skills/<site>/` folder into this repository's
  [`agent-workspace/domain-skills/`](agent-workspace/domain-skills/) examples.
- Existing examples are Python, from before snippets became JavaScript; write new
  and updated examples in JavaScript.
- Keep contributions small and focused.
- Browse existing examples such as `github/`, `linkedin/`, and `amazon/` to see
  the expected shape.

If you are not sure where to start, open an issue and we will point you toward a
useful contribution.
