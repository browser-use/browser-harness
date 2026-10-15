# DistroKid — Edit a Release (album artwork)

URL: `https://distrokid.com/dashboard/album/edit/?albumuuid=<ALBUM_UUID>`

Artwork on an already-delivered release is not edited in place. You submit an **edit request** that
DistroKid reviews (~1 business day) before anything reaches the stores. The whole surface is one form
POST, and the account — not your tab — holds the resulting state.

## Prerequisites

- Logged into DistroKid in the Chrome profile browser-harness is attached to
- The release's album UUID, from the release's dashboard/album page link
- Replacement image on local disk (`.jpg`/`.png`/`.gif`; page copy says square, 3000×3000 optimal)

## Page map — `/dashboard/album/edit/`

One form covering the whole release, in order:

| Section | Notes |
|---|---|
| Header | `Edit release`, plus `DK UPC: <upc>` and `Uploaded: <date>` as plain text |
| Artist/band name | text input |
| Record label | text input |
| Release date | `<select>`, not a date input |
| Preorder? | radio pair (iTunes and Amazon) |
| **Album cover** | dropzone labeled `Choose new image` / `Or drag it here`, backed by `input#artwork` (`accept="image/*"`) |
| `TRACK n` band, one per track | Song title, featured-artist radios, "version" info radios (`No, this is the normal version` / `Radio Edit` / `Other…`), song title preview, explicit-lyrics radios |
| Footer | `Cancel` button, `#doneButton` labeled **Submit Edit Request** |
| Below the footer | red link **Remove this release from all stores** — destructive, see Gotchas |

There is no price or upsell surface on this page; an artwork edit costs nothing, and the page shows no
re-review or re-delivery warning of its own.

## Replace the artwork

The visible dropzone opens the OS file picker, which blocks the browser's main thread. Never click it —
set files on the hidden input directly:

```python
new_tab("https://distrokid.com/dashboard/album/edit/?albumuuid=" + album_uuid)
wait_for_load()

upload_file("#artwork", "/abs/path/to/cover.jpg")   # CDP DOM.setFileInputFiles

# staged? the input holds the file and the dropzone renders a preview
js("document.querySelector('#artwork').files.length")        # -> 1
js("document.querySelector('#artwork').files[0].name")       # -> cover.jpg
```

**Read back the fields you are not changing before submitting.** Artist, label, release date, preorder,
and every per-track title/version/explicit control post together with the artwork, so a stray edit rides
along silently:

```python
js("document.querySelector('#doneButton').innerText")        # -> Submit Edit Request
# snapshot artist/label/release-date/track-title values here and diff against the album page
```

Submitting is `#doneButton`. On success the page navigates to `/dashboard/album/edit/done/?albumUUID=<ALBUM_UUID>`,
whose copy reads *"Thanks for the edits! We need to review your edits… We'll send you an email when your
edits are approved (or not approved). This will take around 1 business day."*

## Confirm a submission from account state, not tab state

Re-open the edit URL. If an edit request is queued, the server returns a **stub page instead of the form**:

- heading `Review pending`
- `There is already an edit request pending review.`
- `You can submit another edit request once the current one is approved, or you can choose to cancel the current edit request.` (that phrase is a link)
- `If you need more help, please contact Artist Relations.` + a `BACK TO ALBUM PAGE` button
- **`#artwork` and `#doneButton` are absent from the DOM**

```python
js("!!document.querySelector('#doneButton')")   # False -> an edit request is pending
```

This is the strongest available proof that a submission landed, because it survives tab loss and cannot
be faked by a stale render. It also means **one pending edit request per release** — batch every change
into a single submission, because the next one is blocked until this one is approved.

The album page itself is unaffected while review is pending: the release keeps reporting as processed and
delivered, and stores keep serving the old cover.

## Verify which image is live — cover URL signature

Cover CDN URLs embed the byte size of the uploaded original:

```
…--<source file size in bytes>--<source filename, non-alphanumerics stripped>.jpg
```

The byte-size segment is the load-bearing part and matches `os.path.getsize()` on the file you uploaded
(confirmed against three releases). Compare it against the new file's size to tell an approved artwork
swap from a still-cached old cover, without eyeballing thumbnails. The trailing extension appears as
`.jpg` regardless of the source extension, so don't key on it.

## Gotchas

- **Query-param casing flips between the two pages** — the edit form takes `?albumuuid=`, the success page
  comes back as `?albumUUID=`. Match case-insensitively when parsing.
- **A pending edit's contents are exposed nowhere.** Searching the edit page, album page, and success page
  HTML for the uploaded filename or any "pending" detail returns nothing. The server confirms *that* an edit
  is queued, never *what* it changes — so record what you submitted yourself, and confirm the content only
  after approval (cover URL signature above, or the approval email).
- **`Remove this release from all stores`** sits directly under the submit button on the same page.
  Treat it as human-only; nothing about an artwork edit should go near it.
- **`cancel the current edit request`** on the Review pending page is the only escape hatch and it discards
  the queued edit outright. Human-only as well — an agent that hits the pending page should report and stop,
  not clear the lock to retry.
- **Submitting is externally visible and asynchronous.** For a delivered release the request goes to human
  review and then out to the stores, so `#doneButton` is a reasonable hard stop for a human confirmation
  step: stage the file, verify the other fields, and hand off the click.
- **Store propagation lags approval.** Even after approval, `/mymusic` thumbnails and store artwork update on
  their own schedule — an unchanged store thumbnail is not evidence the edit failed.
