# YouTube Studio uploads

Use the logged-in YouTube Studio uploader at `https://studio.youtube.com/`.

## First-run setup

A channel that has not used Studio before can show a blocking **Welcome to YouTube Studio** dialog.
Click **Continue** before opening the uploader. The dashboard's **Upload videos** button then opens the
upload dialog.

## Uploading a local video

The upload dialog contains one hidden file input. Set it directly with the harness helper instead of
opening the native file picker:

```python
upload_file('input[type="file"]', '/absolute/path/to/video.mp4')
```

The input currently has `name="Filedata"`, `multiple`, and no `accept` value. The generic
`input[type="file"]` selector is sufficient while one uploader is open.

After the file is selected, Studio moves to the metadata wizard and immediately starts upload and
processing. The title defaults to the filename without its extension. Studio may display **Saved as
private** during the wizard, but the final visibility step still requires an explicit selection.

The metadata panel scrolls inside `#scrollable-content`; page-level scrolling does not move it. For a
section that is outside the viewport, locate the visible label and scroll it into view:

```python
js("""(()=>{
  const label = Array.from(document.querySelectorAll('*'))
    .find(e => (e.innerText || '').trim() === 'AI use');
  label.scrollIntoView({block: 'center'});
})()""")
```

## Required disclosures

- **Audience:** Choose **Yes, it's made for kids** or **No, it's not made for kids**. Neither option is
  selected initially.
- **AI use:** Expand **Show more**. Studio now asks a required **Yes** or **No** question about realistic
  altered or synthetic content. The examples are a real person appearing to say or do something they
  did not, altered footage of a real event or place, or a realistic-looking scene that did not occur.
  Both options are initially unselected. Base the answer on the actual video.

The advanced section also contains optional paid-promotion, remixing, category, language, comments,
and other settings. Leave them unchanged unless the task specifies otherwise.

The current radio selectors are stable and more reliable than matching the short **Yes**/**No** labels:

```text
tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_MFK"]
tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]
tp-yt-paper-radio-button[name="VIDEO_HAS_ALTERED_CONTENT_YES"]
tp-yt-paper-radio-button[name="VIDEO_HAS_ALTERED_CONTENT_NO"]
```

After each click, verify the selected element has `aria-checked="true"` before advancing.

## Wizard and verification

1. Complete **Details**, including the two required disclosures.
2. **Video elements** is optional. A new/empty channel may have no related video to add.
3. Wait for **Checks**. Confirm the visible copyright result before continuing. HD processing can keep
   running in parallel and does not block the checks step.
4. On **Visibility**, explicitly choose **Private**, **Unlisted**, or **Public**. Selecting **Public**
   changes the final button from **Save** to **Publish**.
5. After publishing, verify the **Video published** dialog and capture the Shorts/watch link shown
   there. Open that link in a new tab and confirm the title and playback page load.

For a multi-video batch, capture each published URL but defer opening the public pages until every
upload is finished. Switching from Studio to a new public tab and back can leave the default harness
session unable to run `Runtime.evaluate`. If that happens, start a fresh harness invocation, list the
tabs, and explicitly switch to the Studio target before continuing. Verify all captured public URLs in
a separate pass after the batch.

Vertical videos around one minute are presented as Shorts, and the resulting link uses
`https://youtube.com/shorts/<video-id>`.

## Daily upload limit

An unverified or low-history channel can hit **Daily upload limit reached** during a batch. Studio may
show the normal metadata form while the side panel says **Creating link...**; in this state the upload
was rejected, the title can revert to the filename, and the advanced disclosure controls never render.
Treat the limit warning as the cause instead of retrying **Show more** or continuing the wizard.

The warning offers either a 24-hour wait or one-time advanced-feature verification. The current
verification choices are a six-second selfie video, a photo ID, or building channel history (usually
about two months). Video and ID approval can take a few hours and requires the account owner's direct
participation. Do not choose or submit an identity-verification method on the user's behalf. Record the
successfully published links, close the rejected upload, and resume the remaining files only after the
owner completes verification or the daily limit resets.

## Editing an existing video

Open an existing video's details directly at:

```text
https://studio.youtube.com/video/<video-id>/edit
```

The title is the contenteditable `#title-textarea #textbox`. Change it, blur the field, and confirm the
top **Save** button becomes enabled. Audience is visible on the main details page; advanced disclosures
remain behind **Show more**. Expand it, scroll the **AI use** label into view, select the required
**Yes** or **No** radio, and click **Save**. Wait until Studio displays **Changes saved** or **All changes
saved** and the Save button becomes disabled.

For a public video, verify the edit on the live Shorts/watch URL in a new tab. The browser tab title and
the rendered title below the player should both contain the updated title.
