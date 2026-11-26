# Vanta — background checks & per-person security tasks

App: `https://app.vanta.com/c/<org-domain>/…` (org domain in path, e.g. `c/browser-use.com`).

## URL patterns

- People list: `/c/<org>/people/people` — query params `status=CURRENTLY_EMPLOYED`, `quickView=overdue`, `taskStatus=TASKS_OVERDUE`, `userId=<id>` (opens the person drawer).
- Certn checks tab: `/c/<org>/people/background-checks` (order history + link flow), purchase at `/people/background-checks/purchase`.
- Evidence documents: `/c/<org>/documents`, e.g. `/documents/bulk-background-check` for "Completed employee background checks".

## The two background-check trackers (they do NOT sync)

1. **Document-level evidence** (Compliance → Documents): file uploads, what auditors review.
2. **Per-person "Background check" task** (Personnel → People → person drawer → Tasks): only cleared by (a) a completed Certn/partner check auto-linking by email, or (b) manually linking a **custom URL + completion date**. Uploading files to the evidence document never clears these.

## Manually completing a person's background check task

1. People list → click the person's row → drawer opens on the right.
2. In "Incomplete security tasks", the Background check card has one icon button on the right:
   - `aria-label="Link"` (no check linked) → opens "Link background check to <name>" modal with a `input[placeholder="https://"]` custom-URL field, a "Choose completion date" picker, and Submit.
   - `aria-label="View"` (a Certn check already linked, even if In Progress) → details modal with only Unlink + a search over *Certn* records. **No custom-URL option exists while any check is linked** — you must Unlink first.
3. Fill URL (a cloud-drive or Vanta-document link; direct file upload is not supported), pick date, Submit. Success toast: "Background check linked to <name>". Task flips to Complete immediately.

## Traps

- **Stale offscreen drawers stay in the DOM** after closing/switching person. When locating drawer elements, filter by bounding rect inside the viewport (`r.x >= 0 && r.x < innerWidth`), otherwise you'll measure a drawer at x>1500 and click into the void (which also dismisses the real drawer).
- **Date-picker popovers stack**: re-opening "Choose completion date" mounts a second calendar at the same coordinates while the old one lingers. Always target the *last* matching month label/calendar in DOM order. Navigate months by re-locating the `<`/`>` buttons (same row as the month label) before every click.
- **JS `el.click()` does not activate most buttons** (Link, date cells) — they need real pointer events; use CDP coordinate clicks. Row clicks and menu buttons via coordinates work fine.
- **Search field is React-controlled**: `fill_input`'s select-all clear can leave residue; clear via the native value setter + `input` event, then type with `clear_first=False`.
- Escape sometimes opens the Vanta Agent AI side panel instead of only closing the modal.
- The person drawer's "…" menu (More actions) has no background-check actions (only email info / leave / groups / service account).
- The People page "Background checks" tab lists **only Certn-sourced records**; manual URL links do not appear there.
