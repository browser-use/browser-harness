# LinkedIn safety caps

These limits protect Marco's real free LinkedIn account. Apply the strictest
limit that covers an action. Before every write, read the authoritative counter
state and refuse the action if any daily, weekly, hourly, session, pending-pool,
or acceptance governor would be exceeded.

## Authoritative counter state

The engine repository's `state/caps.json` is authoritative for all daily and
weekly counters, ramp position, session use, zero-write day, pending pool,
withdrawals, note use, acceptance rate, and active halts. Browser text and a
task transcript are evidence, not the source of truth.

Required contract:

- Read `state/caps.json` before the first action and again before each write.
- Record an action only after visible readback and an after-screenshot.
- Update the state atomically in the engine repository through its own approved
  workflow.
- Never infer unused capacity from a missing run log or a fresh browser session.
- If the file is missing, stale, malformed, or disagrees with visible state,
  stop writes and report the mismatch.

## Week 1 ramp

| Ramp day | Connects | Messages | Notes |
|----------|----------|----------|-------|
| Tonight, pre-send warm-up | 0 | 0 | 0 |
| Thursday | 3 | 2 | Subject to named-founder budget |
| Friday morning | 3 | Within combined caps | Subject to named-founder budget |
| Monday | 4 | Within combined caps | Subject to named-founder budget |
| Tuesday onward | 5 per day, 20 per week | Within combined caps | Subject to named-founder budget |

Tonight's warm-up is follows, likes, and 2 comments with zero connects. Tuesday
through Thursday are the preferred connect days. After any halt, resume at ramp
day 1 levels, not at the previous steady rate.

## Steady caps

| Action or group | Cap |
|-----------------|-----|
| Connects | 5 per day and 20 per week |
| Connects + messages + comments | 7 per day and 30 per week |
| Total actions | 10 per day |
| Profile views | 25 per day |
| Likes | 8 per day |
| Comments | 3 per day, each at least 12 words |
| InMail | 0 |
| Writes in any rolling hour | 3 maximum |
| Time between writes | At least 240 seconds |
| Sessions | 2 per day |
| Session length | 12 to 25 minutes |
| Gap between sessions | At least 3 hours |
| Dwell | At least 40 percent of session time |
| Zero-write weekday | 1 random weekday each week |
| Weekends | Read-only |
| Pending invitations | 40 maximum |
| Withdrawals | Invitations older than 21 days only, 5 per day maximum |

The pending pool cap overrides unused connect capacity. With 61 pending
invitations observed on 2026-09-02, connects remain off until the authoritative
state and live manager show the pool at or below 40.

## Rhythm

- Use a lognormal delay between writes with a median near 6 minutes and a tail
  up to 18 minutes, while always keeping the 240-second minimum.
- Split work into no more than 2 sessions of 12 to 25 minutes, at least 3 hours
  apart.
- Spend at least 40 percent of each session reading, scrolling, or dwelling.
- Use the mandatory feed, scroll, typed search, results, profile, Experience,
  dwell, action, after-screenshot path.
- Keep one random weekday free of all writes. Store the chosen day in
  `state/caps.json` before the week starts.
- Keep weekends read-only.
- Run one tab on Marco's Chrome. Defer if Marco is using LinkedIn or another
  automation process holds the global action-plane lock.

Sessions follow Marco's London clock from 08:00 to 19:30, with these market
biases:

| Market | Preferred London time |
|--------|-----------------------|
| UK | 08:30 to 11:00 or 14:00 to 16:30 |
| Germany | 08:00 to 10:30 or 13:30 to 16:00 |
| US Pacific | 16:00 to 18:30 |
| US Mountain | 15:30 to 18:00 |
| US Central | 14:30 to 17:30 |

## Acceptance governor

Use the 14-day connection acceptance rate from the authoritative state:

| 14-day acceptance | Connect policy |
|-------------------|----------------|
| 30 percent or more | Normal ramp and caps |
| Below 30 percent | Halve the connect allowance |
| Below 20 percent | Stop connects |

Do not round up an allowance. A halt from friction still overrides this table.

## Pending pool and withdrawals

- Keep no more than 40 sent invitations pending.
- Withdraw only invitations older than 21 days.
- Withdraw no more than 5 in one day.
- Read name, age, and action from the same row before each withdrawal.
- Count a withdrawal only after visible readback.
- Do not use withdrawals to create room for a same-session connect burst.

## Personalised-note budget

The account is free and has no Premium. `Try Premium` was visible on
2026-09-02, so the free-account personalised-note quota applies. Read the
current quota and character counter from the live `Add a note` modal on first
use. Those values remain `TO-VERIFY` until observed.

Reserve notes for only these five named founders:

- Blacklock
- BRLO
- Frasca
- Rivaaz
- Dean Banks

Skew the scarce budget toward Germany. Everyone else receives a bare request,
with the pitch held for the post-accept message. If the modal proves the quota
is unlimited, cap notes at 2 per day and 250 characters each. Never assume that
an apparently enabled note button means quota remains.

## Stop precedence

Any friction signal, login route, checkpoint route, IP change, state-file
conflict, or concurrent control stops writes even when all numeric caps have
room. Follow [`friction-detection.md`](friction-detection.md).

