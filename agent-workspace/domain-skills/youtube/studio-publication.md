# YouTube Studio publication mechanics

Observed in the English Studio interface, November 2026. Publication, metadata,
thumbnails and comments require the signed-in browser and explicit task authority.

## Routes and metadata

- Channel content: `https://studio.youtube.com/channel/{CHANNEL_ID}/videos/upload`.
  Verify the channel ID in the loaded URL. Videos and Shorts are separate tabs;
  an unfiltered list includes non-public items. Check pagination before concluding
  that a title is absent.
- Video details: `https://studio.youtube.com/video/{VIDEO_ID}/edit`.
- The upload dialog exposes a hidden `input[type=file][name=Filedata]` suitable
  for CDP `DOM.setFileInputFiles` through `upload_file()`.
- The video link may initially say `Creating link...`. Once the `youtu.be` anchor
  appears, its ID is available even while the upload is still progressing.
- Title and description live in `ytcp-social-suggestions-textbox`, identified by
  `#title-textarea` and `#description-textarea`. Their nested editable is
  `[contenteditable=true]`. For exact verification, inspect the components'
  read-only `getInternalTextValue()` result and verify again after saving.
- Multiline `Input.insertText` can leave an extra trailing newline in the
  description. If exact text matters, compare it rather than trimming it for the
  assertion. A fallback is setting the editable's `textContent` to the exact
  supplied string and dispatching a bubbling `InputEvent('input')`; verify that
  Studio saves the exact value after a reload.
- The upload wizard can show only the video-language control. After the initial
  save, Details > Show more also exposes `Title and description language`.
  Set and save that separately when requested.

## Thumbnail experiments

- `A/B Testing` opens a dialog whose default scope can be `Title and thumbnail`.
  Select `Thumbnail only` when the approved title must remain unchanged.
- Each variant uses a hidden file input inside `ytcp-thumbnail-uploader`.
  The enclosing button labels distinguish the slots: `Upload thumbnail 1`,
  `Upload thumbnail 2`, and `Upload thumbnail 3`. For example:

  ```python
  upload_file(
      'ytcp-thumbnail-uploader:has(button[aria-label="Upload thumbnail 1"]) input[type=file]',
      '/absolute/path/thumbnail.png',
  )
  ```

- After the files finish loading, `Set test` queues the experiment for saving.
  A private video can display `Ineligible` even after this setup. After public
  publication, confirm `A/B Test running` in the channel-content row. The public
  watch page does not display experiment status.

## End screens

- Video elements > End screen opens the editor. Its `Import from video` opens
  a picker containing Shorts as well as long videos. Inspect a card's thumbnail
  URL, which includes `/vi/{VIDEO_ID}/`, to disambiguate similarly named entries.
- Imported elements retain positions, but their start times can be adjusted for
  the new video's duration. Verify each element independently.
- Time inputs are `ytve-formatted-input input`, using minutes:seconds:frames.
  Replace the selected input and click a neutral area to commit; inspect both
  input values and the timeline after the blur. Enter can reset a pending edit.
- Use the selected element's visible corner handles for resizing, and compare
  placement with a late frame showing the actual drawn end card. Save, wait for
  the editor to close, then reopen to verify both timings and placement.

## Keyboard helper caveat

In browser-harness 0.1.0, `press_key()` emits a separate `char` event for printable
characters and some special keys. Ctrl+A with lowercase `a` can insert characters
instead of selecting all; Tab can send text to the newly focused input. For these
controls use raw `Input.dispatchKeyEvent` keyDown/keyUp pairs with `key`, `code`,
`windowsVirtualKeyCode`, and modifiers, without `text` or a separate char event.
Ctrl+A uses `key='a'`, `code='KeyA'`, virtual key 65, and modifiers 2 on Windows.

## Checks and pinned comments

- The wizard's `Initial check` can show separate `Copyright` and
  `Community Guidelines` results, plus `Checks complete. No issues found.`.
  Verify processing and both results before an authorized public change.
- On the watch page, posting does not necessarily update the displayed comment
  count immediately. Inspect the new `ytd-comment-thread-renderer` and its author.
- The comment menu's `Pin` action opens `Pin this comment?`; confirm it and then
  reload to verify `Pinned by @...` and the exact comment text.
- The timestamp anchor in the comment thread supplies the permalink with `&lc=`.
- After watch-page hydration, `window.ytInitialPlayerResponse` provides the title,
  description, channel ID, `videoDetails.isPrivate`,
  `microformat.playerMicroformatRenderer.isUnlisted`, and playability status for
  a read-only cross-check alongside Studio visibility and the visible page.
