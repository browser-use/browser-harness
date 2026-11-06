# LinkedIn: Sales Navigator and profile editing

UI observations for one authorized action at a time. Inspect the current page
before using a selector; labels and available controls can vary by account.

## Routes and result rendering

- Lead search: `https://www.linkedin.com/sales/search/people`.
- A saved search uses the `savedSearchId` query parameter. Preserve the URL
  returned by the UI instead of constructing a saved-search identifier.
- Sales Navigator lead profile: `/sales/lead/<lead-id>`.
- Standard member profile: `/in/<profile-slug>`.

Lead result cards use `[data-x-search-result="LEAD"]`. Results render lazily:
the cards currently in the DOM may be only part of the page. Read the visible
cards, scroll the results area, then capture the newly rendered cards. Do not
treat a single DOM count as the page's total or assume offscreen cards persist.
Loading the route is not proof that filters and results have finished updating.
If placeholders remain, use ordinary wheel scrolling over the visible results
pane and inspect the newly rendered cards. Changing a guessed container's
scroll offset is not evidence that the application loaded the next cards.

A search headcount filter is a discovery aid, not current staffing proof. A
company page's company-size field can disagree with the filter match. Counts
of associated LinkedIn member profiles are a separate measure, not headcount.

## Filters and typeahead

An option's accessible label can look like
`Include “<label (count)>” in <filter> filter`. Counts change as filters change,
so inspect the current label rather than hardcoding the entire string. Scope
the option to its filter and match the intended value; similar values can
appear in different filters.

Selected values expose removal controls with removal-specific accessible
labels. Inspect those labels separately instead of reusing an Include selector.
After selecting or removing a value, verify the resulting filter chip and wait
for the results to update.

`type_text()` can fill a typeahead input without refreshing its suggestions.
An ordinary ArrowRight keyDown/keyUp pair on the focused input triggered the
refresh in the observed UI. Inspect the new suggestions before selecting one;
the text in the input alone does not establish a selected filter.

To replace an input's text, focus the observed input, call its ordinary
`select()` method, then type through CDP. This also works for the saved-search
name input. Avoid assigning a React-controlled input's `.value` or manipulating
framework state: the visible text can change while the application retains the
previous value.

## Saving and naming a search

The Save search toggle creates the saved search. The observed naming flow was
separate: open Saved searches, choose Edit for that search, then edit
`#edit-saved-search-name-input` and click Save.

Verify the saved name in Saved searches and reopen the search to check its
filters. A toggle change alone does not confirm the intended name or filters
were persisted.

## Invitations and authoritative state

On a Sales Navigator lead profile, the overflow control has
`aria-label="Open actions overflow menu"`. Connect opens the dialog named
Send invitation. Scope the textarea and Send Invitation control to that named
dialog; other dialogs and controls may exist in the DOM.

The invitation note is optional. An empty textarea is valid when an invitation
without a note is intended. Inspect the recipient and dialog contents before
the final action. Send Invitation sends externally and requires the user's
authorization; opening the menu or dialog does not itself authorize sending.

Some recipients require an email address in the invitation dialog, exposed as
a textbox labeled `<name>'s email is required to connect`. Treat this as a
recipient-specific requirement. If a verified address is unavailable, cancel
and record that no invitation was sent; do not guess an address or treat the
presence of Send Invitation as proof that submission is possible.

After sending, verify the profile's connection state. The observed authoritative
state was `Connect — Pending`. `Saved` only means the lead was saved in Sales
Navigator and is not evidence that an invitation was sent. If the result is
unclear, re-read the profile state before considering a retry.

## Accepted connections and message verification

The standard connections route is `/mynetwork/invite-connect/connections/`.
The observed default sort was Recently added, with a connection date on each
card. Check this list when an accepted invitation has not appeared in the
notification feed; an absent notification is not proof of no acceptance.

Each card's Message link has a recipient-specific accessible label such as
`Send a message to <name>`. Follow the actual link supplied by the page rather
than constructing recipient identifiers. It opens the messaging composer and
may resolve to an existing conversation. Inspect the recipient, connection
degree and any history before typing. A Message link can open a docked overlay
while other old overlays remain visible. Navigating the same task tab to the
actual composer href provides a full conversation view; verify its selected
recipient again before entering text.

In the observed standard messaging UI, `.msg-convo-wrapper` contains the
active conversation and `[contenteditable="true"][role="textbox"]` is the
message editor. Scope to the active conversation and confirm only one intended
recipient. After an authorized send, verify the sender, recipient and exact
message in the conversation, an empty editor and the resulting
`/messaging/thread/<thread-id>/` route. Text in the composer alone is not send
evidence. Preserve an uncertain outcome for inspection instead of retrying.

## Editing the account owner's profile

On the standard `/in/<profile-slug>` route, Edit profile and Edit about open
editing dialogs. The observed About editor was a contenteditable element with
`role="textbox"`. Scope selection to the active dialog's intended editor.

For replacing its contents, focus the editor, create a DOM Range with
`range.selectNodeContents(editor)`, clear the current selection with
`window.getSelection().removeAllRanges()`, and add that range. Then enter the
replacement with ordinary CDP typing. This selects the text for normal editing;
it does not mutate the editor's HTML or framework state. Verify the complete
text in the editor, save, reload the profile, and read back the saved text.

## Changing the profile cover

The observed menu flow was Edit background, Edit cover image, Change photo,
then Upload single photo. The upload uses a hidden `input[type="file"]`;
locate it in the active upload flow and use CDP `DOM.setFileInputFiles` with the
intended local image. Do not rely on a file input being visually clickable.

Wait for the uploaded image to appear in the editor before clicking Save
changes. Then reload the profile and inspect the displayed cover. Choosing a
file or seeing an upload preview does not confirm that the cover was saved.
