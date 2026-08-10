# Forgepoint Investor Portal — Admin and Deck Publishing

`https://invest.forgepoint.ai` is a Next.js investor portal with an authenticated admin at `/admin`. Public share links are tokenized under `/d/{token}` and may require an allowed-domain email before opening.

## Deck publishing workflow

Decks are repository content, not blob uploads. Add each immutable version to the portal repository at:

```text
content/decks/{document-slug}/v{version}/index.html
```

Keep every relative asset beneath that version directory. Deploy the repository change before registering the version, because the admin API checks that the directory exists on the running server.

From an authenticated `/admin` tab, create a document with:

```javascript
await fetch('/api/admin/documents', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    slug: 'document-slug',
    title: 'Document Title',
    type: 'deck'
  })
}).then(r => r.json())
```

After deployment succeeds, register the version:

```javascript
await fetch('/api/admin/documents', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    action: 'add_version',
    documentId: 123,
    version: 1,
    contentPath: 'content/decks/document-slug/v1',
    changelogNote: 'Initial version'
  })
}).then(r => r.json())
```

The `contentPath` must exactly match `content/decks/{slug}/v{version}`. The server returns `Deck content directory does not exist` if the deploy has not completed.

## Important trap: the upload form is not the deck publisher

`POST /api/admin/upload` stores a blob-backed document version with no deck `contentPath`. Using it for a deck can create a numbered version that renders as `Not found` in the viewer. If those versions already exist, publish the repository directory using the next available version number, then call `add_version` with that matching number and path.

Check the current version numbers before publishing:

```javascript
const data = await fetch('/api/admin/documents').then(r => r.json())
const document = data.documents.find(d => d.slug === 'document-slug')
console.log(document.versions)
```

## Rooms and public routes

Admin room membership is managed through `/api/admin/rooms`. Its `set_documents` action takes the room ID and the ordered document ID list; preserve the existing order and append or insert the new document deliberately.

```javascript
await fetch('/api/admin/rooms', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    action: 'set_documents',
    roomId: 1,
    documentIds: [1, 2, 3]
  })
}).then(r => r.json())
```

Stable public paths:

- Room selector: `/d/{token}`
- Document viewer: `/d/{token}/f/{documentId}`
- Deck entry point: `/d/{token}/content/{documentId}/index.html`
- Deck assets: `/d/{token}/content/{documentId}/{relative-path}`

The viewer page wraps a same-origin deck in an `iframe`. For verification, inspect `document.querySelector('iframe').contentDocument` and confirm the expected title, slide count, and that all images have a nonzero `naturalWidth`.

## Link lookup and email gates

Authenticated admins can inspect link metadata through `GET /api/admin/links`. Select links by exact `label` plus `targetType`; labels may overlap between document links and room links. Never log or persist the returned token.

When a share link requires email collection, use an address in its `allowedEmailDomain`. The form has `input[type=email]` and a submit button. After submission, the portal records the viewer session and displays the room or document.
