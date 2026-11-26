# Battlefy — create a tournament (organizer flow)

Verified 2026-09-01 by creating a live Fortnite 5v5 double-elim tournament end-to-end.

## URL patterns

- Organizer hub: sidebar "Organize Tournaments" on battlefy.com → org list. Orgs at `/{org-slug}`.
- Create wizard: `battlefy.com/create-tournament?orgSlug={org-slug}` (game picker) → `battlefy.com/create-tournament-wizard?selectedItem={setup|brackets|streams|publish}&selectedTab=...`. The wizard is an Angular SPA; the draft tournament is created server-side only after Setup completes (it then appears in the org sidebar).
- Admin (after creation): `/{org-slug}/{tournament-slug}/{tournamentId}/admin?selectedItem=...`
- Public page: `/{org-slug}/{tournament-slug}/{tournamentId}/info` — shows "Registration Open", "Join as Team".

## Wizard flow (Setup → Brackets → Streams → Publish)

Setup has three tabs: Basics, Info, Settings. **The tab links at the top do nothing until you advance with the bottom-right "Next" button** — Next validates the current tab and moves you forward; don't fight the tab links.

- **Basics**: game (preselected from picker), tournament name, start date, start time.
  - ⚠️ Date field is **DD/MM/YYYY** (label says so, easy to misread as US format). Sept 5 2026 = `05/09/2026`. Time defaults to 7:00 PM, timezone shown next to the field (EDT for US-East accounts).
- **Info**: "How will your players contact you?" — **required before Next**, red "Contact details are required" otherwise. Dropdown: Discord/Facebook/Twitter/Email/Curse/Teamspeak/IRC/Twitch/Custom. Picking Discord reveals a "non-expiring Discord invite link" textbox. About/Rules/Prizes/Schedule expanders are optional.
  - Next can race form updates — if you get the "fill out all required elements" toast with visibly filled fields, just click Next again.
- **Settings**: Region, Platform (Fortnite offers Cross Platform), Tournament Format: `1v1` / `Pre-Made Teams` / `Free Agent Draft` / `Pre-Mades & Free Agents`. Selecting Pre-Made Teams reveals a players-per-team number input (defaults to 5). Also: check-in toggle, score reporting (default Admins & Players), participant limit (default Unlimited).

## Brackets

"Create an Elimination Bracket" expander → name, start date/time (inherited), Single/Double Elimination radio, bracket size (# of teams; unused slots become byes).

- Fortnite elimination brackets default to **Aggregate** scoring (points across N games). For classic series play switch Scoring Format to **"Best Of" Scoring** — this reveals **per-round Best of 1/3/5/7/9/11 dropdowns** for every round: Winners R1–Rn, Losers R1–R(2n-2), Grand Finals Round 1 and Round 2 (the bracket-reset match), plus a "Best of for all rounds" master dropdown.
- ⚠️ Clicking **Save** after changing scoring format pops a "Reset And Update Bracket" confirm — resets the bracket and unseeds teams. Harmless pre-registration; destructive after seeding.

## Publish

Draft/Published and Private/Public segmented toggles + optional Join Codes.

- ⚠️ These toggles are **non-semantic** (`div.label.right` etc.) — invisible to the accessibility tree and unreliable for coordinate clicks. DOM click works: find leaf element whose `textContent.trim() === 'Published'` (or `'Public'`) and `.click()` it.
- Publishing pops a confirm modal ("players will be able to register… no longer able to edit fields that affect registration") → Publish. Then Finish → "Success!" modal.
- Invite link lives at Share → Invite Players in the admin sidebar (`.../info` URL with copy button).

## Traps

- Battlefy accounts: creation requires login; organizer actions live under an **organization** (create one via "+ New Organization" if the account has none).
- The wizard keeps unsaved SPA state — don't reload mid-wizard before the tournament shows in the org sidebar.
