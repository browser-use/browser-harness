# Instagram web messaging

## Routes and conversation surfaces

- Profiles use `https://www.instagram.com/<handle>/`.
- The profile's **Message** button can open a docked conversation without changing the profile URL. Do not assume a thread navigation is required.
- Some profiles expose **Send message** inside the **Options** menu instead of a visible Message button. Inspect the rendered menu before concluding that messaging is unavailable.
- Full conversations use `/direct/t/<thread-id>/`; the inbox uses `/direct/inbox/`. Use observed thread IDs, never construct them from usernames.

## Readiness and selectors

- Find the rendered `button` or `[role=button]` with exact text `Message`, then click its measured centre. The options button can contain `svg[aria-label=Options]`.
- A button can appear before its interaction is ready. Verify that the conversation actually opened, wait for its contents, and take a screenshot before proceeding.
- The composer has `[role=textbox]`. An empty composer may have `innerText === '\n'`; trim whitespace when checking for an existing draft.
- Confirm the conversation header and handle, inspect existing history, and verify the exact inserted text before a user-authorised send. Initial loading state does not establish an empty history.

## Sending and delayed rejection

- Record a pending attempt before sending. Enter submits the composer. Verify the outgoing bubble, cleared draft, and absence of a **Sending** indicator, then save evidence.
- An outgoing bubble is not delivery confirmation. Instagram can subsequently display: “This account can't receive your message because they don't allow new message requests from everyone.” This failure may also appear as the inbox preview.
- Reconcile delayed failures separately from initial UI-confirmed sends. Preserve the attempt; do not resend or switch channels to bypass message settings.
- Booking auto-replies and message reactions are not human expressions of interest. Inspect actual reply text before classifying a conversation.

## Background work in a shared browser

- For a user who requests unfocused operation, raw CDP `Target.createTarget` with `background=True`, `focus=False`, `newWindow=False`, and the existing browser context can create a separate background tab. Attach with `Target.attachToTarget(flatten=True)` and pass that explicit session to every Page, Runtime and Input call.
- Check `document.visibilityState === 'hidden'` before navigation and interaction. Do not activate targets or call helpers that switch visible tabs. If the user starts using the agent tab, leave it alone and create a fresh background target.
- Background rendering and virtualised inbox lists can lag behind scrolling. An attempted wheel or changed scrollTop does not prove more conversations loaded. Reinspect the DOM and screenshot; use known profile conversations when pagination is inconclusive.

Keep recipient records, drafts, screenshots, handles and session identifiers in the private task workspace, outside shared domain documentation.
