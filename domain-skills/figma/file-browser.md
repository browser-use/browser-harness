# Figma file browser (figma.com/files)

Field-tested mechanics for driving the Figma file browser and duplicating/renaming files.

## Internal JSON APIs (fetch from page context, cookies ride along)

```python
js("""(async()=>{ const r = await fetch('/api/recent_files?count=40', {credentials:'include'});
const j = await r.json(); return JSON.stringify(j.meta.recent_files.map(f=>({key:f.key,name:f.name,folder:f.folder_id}))); })()""")
```

- `GET /api/recent_files?count=N` — recent files with `key`, `name`, `folder_id`, `team_id`.
- `GET /api/folders/{folder_id}/paginated_files?sort_column=touched_at&sort_order=desc&page_size=50` — project folder contents. The plain `/api/folders/{id}/files` also works but sorts differently.
- `PUT /api/files/{key}` with JSON body `{"name": "New name"}` — **renames a file** (200 with updated meta). Works from page context, no extra CSRF header needed.
- `DELETE /api/files/{key}` — trashes a file, but returns 403 unless the account has delete permission on the project. Plugin API cannot rename files either (`figma.root.name` setter throws "not supported"), so `PUT /api/files/{key}` is the only scriptable rename.
- `POST /api/files/{key}/duplicate` does NOT exist (404). Search endpoints like `/api/search/fuzzy_files` 404 too.

## Duplicating a file

- The `figma.com/<type>/<key>/duplicate` URL trick does **not** work for files you already have access to — it just opens the original.
- In-editor menu: for files you can edit, **File menu has no Duplicate item** (only "Save local copy…"). "Duplicate to your drafts" only appears for view-only files.
- File browser context menu (right-click on tile): items are listed under `[role=menuitem]`-less plain divs, and **do not respond to synthetic CDP clicks or to keyboard Enter** — only telemetry fires.
- **What works: select the tile with a normal left click, then press Cmd+D** (`press_key("d", modifiers=4)`). The copy lands in the same project named `<name> (Copy)`. Confirm via the folder API above — the copy may NOT appear in `/api/recent_files` until touched.
- Beware double-fires: a seemingly dead Enter/click attempt earlier can still complete asynchronously, leaving two `(Copy)` files. Always count copies via the folder API afterwards.

## Traps

- The file browser is an SPA that hijacks `goto()` for `figma.com/files/*` URLs (e.g. `/files/drafts`, `/files/search?q=…` bounce back to recents). Drive it by clicking, or just use the internal APIs.
- File tiles are not `<a href>` anchors and tile titles are not findable via simple leaf-text DOM scans; don't rely on DOM scraping to enumerate files — use `/api/recent_files`.
- The slides/design editor takes 30s+ to load on big files; poll for toolbar buttons before interacting.
