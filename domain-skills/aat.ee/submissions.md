# aat.ee product submissions

- `/projects/submit` redirects unauthenticated users to `/sign-in`; `/dashboard` links to `/settings` for profile changes.
- Google sign-in imports the Google name. If the intended public maker identity is a brand, edit the profile in `/settings` before submission and verify the resulting Maker section. Profile modal input is `#name`.
- The four-step wizard covers project information, details, launch date, and review. Website/name/tagline IDs are `websiteUrl`, `name`, and `tagline`.
- Description editor loads on demand: first click `[data-rich-text-editor="deferred"]`, then wait for `.tiptap[contenteditable="true"]`. Use trusted input to update editor state.
- Upload inputs disappear after successful upload. Re-query file inputs before the next upload; positional indexes can change.
- Tags use a Radix popover. Opening it can move focus away from the input. Existing tag choices expose `[role=option][data-value]`. Close the popup before clicking the wizard navigation; its overlay can intercept a click intended for Next.
- Date select exposes `[role=option]` and `aria-disabled`. The text of disabled dates can still mention free slots: choose an enabled option instead of inferring availability from text alone.
- The free route can schedule a public product page without installing a website badge. Paid distribution plans and badge acceleration are separate options.
- After submission, verify `/projects/<slug>`, the scheduled UTC date, public maker identity, website anchors and their actual `rel` values. Scheduled free profiles can be public with `nofollow` website links. Dofollow eligibility may require both a top-three daily ranking and a reciprocal badge.
