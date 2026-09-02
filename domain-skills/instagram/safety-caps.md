# Instagram safety caps

Apply these limits to `marco__lobo`. Read the engine repository's authoritative
`state/caps.json` before every write. A browser session, screenshot folder, or
task transcript never resets a counter.

## Caps

| Action or rule | Week 1 | Steady state |
|----------------|--------|--------------|
| DMs | 2 per day | 3 per day and 12 per week |
| Same restaurant group | Never DM 2 handles from one group on one day | Same |
| Gap between DMs | At least 20 minutes | Same |
| Follow to DM gap | At least 15 minutes | Same |
| Unfollow | 0 | 0 |
| DM 1 links | 0 | 0 |
| DM 1 length | 2 to 3 lines | 2 to 3 lines |

Instagram DMs should run from 10:00 to 11:30 or 15:00 to 16:30 in the target's
local time. Likes and Story replies may run from 18:00 to 20:00 London time.

## Sequence rules

1. Warm the account with a follow and 2 to 4 likes across 2 days.
2. Prefer a Story reply as the opener.
3. Keep DM 1 to 2 or 3 lines with no link.
4. Send DM 2 only after `Seen` or after 7 days.
5. Send DM 3 with the audit link only after a reply, or after `Seen` plus a
   verified profile visit.
6. Never contact 2 handles from the same restaurant group on the same day.
7. Keep at least 20 minutes between all DMs.
8. Keep at least 15 minutes between a follow and a DM.
9. Never unfollow.

Do not compress these waits to use unused daily capacity. A friction halt
overrides every numeric allowance.

## Authoritative counter state

The engine repository's `state/caps.json` is authoritative. It must hold, at
minimum, the current ramp day, daily and weekly DM counts, per-group activity,
last DM time, last follow time per handle, warm-up history, conversation stage,
eligibility signals for DM 2 and DM 3, and any active action-block halt.

- Read the file before the first action and before each write.
- Record a write only after visible thread or control-state readback and an
  after-screenshot.
- Update it atomically through the engine repository's approved workflow.
- Stop writes if it is missing, stale, malformed, or conflicts with the page.
- After a 72-hour halt, resume at week 1 levels.

## Content and folder rules

- Cold DMs often land in Requests. Do not assume delivery to Primary.
- On business accounts, check Primary, General, and Requests during read sweeps.
- Never send a second copy because the first message is absent from the main
  inbox view.
- Never place a link in DM 1.
- Use a Story reply as the opening action when a relevant Story is available.
- Never unfollow, even when a prospect is dropped or the campaign ends.

