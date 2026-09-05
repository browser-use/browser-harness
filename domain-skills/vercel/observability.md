# Vercel — project identity, visitor analytics and request traffic

## Resolve the actual project first

- Team overview: `/{team_slug}`.
- Project overview: `/{team_slug}/{project_slug}`.
- A repository can be linked to multiple Vercel projects. Match the live domain
  on the project's Production Deployment card, not just a similar project name.
- The production card shows its source commit. A newer failed deployment does
  not replace the live commit. Record web and separately hosted backend revisions
  independently.

## Visitor analytics versus operational traffic

- Project **Analytics** links to the visitor dashboard. An **Enable** button and
  **Demo Data** label mean the sample chart is not measured visitor activity.
- Project **Observability → Edge Requests** provides operational request counts
  even when visitor analytics is not enabled.
- The edge-request view supports **Routes**, **Paths**, and **Bot Name** groupings.
  Inspect the exact time range and environment (e.g. Production).
- Page hits, sign-in route requests, function invocations and edge requests are
  not counts of people, successful sign-ins or conversions. The requesting agent,
  bots, scanners, static assets and prefetches may contribute.
- Named-bot counts do not imply the unclassified remainder is human.
- Longer lookback choices can be gated behind an observability plan. Do not
  enable/upgrade a paid feature just to answer a traffic question.

## UI traps

- **Edge Requests** may be both a sidebar link and a card link with identical
  destinations. Scope to the known navigation region or disambiguate the links.
- Client-side navigation may return a stale previous-page snapshot immediately
  after clicking. Check URL/next state rather than repeating the click blindly.
- A deployment's **Logs** page may show runtime request logs, not build logs.
  No runtime entries does not explain why a build failed.

Keep account names, customer domains, project IDs and traffic measurements out
of reusable public skills.
