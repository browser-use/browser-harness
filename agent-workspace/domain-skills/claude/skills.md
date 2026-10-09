# Claude: replace an uploaded skill and verify the saved version

## Routes and scope

- `https://claude.ai/customize/skills` opens Skills > Yours.
- An existing skill has a route shaped like `/customize/skills/<skill_id>`; its files are under the `/contents` suffix. Discover the ID from the current page rather than retaining an old ID indefinitely.
- Claude Desktop's **Chat and Cowork** mode exposes uploaded account skills. **Code** mode can instead show project/local skills under an “In this project” heading. An absent uploaded skill in that view does not establish that the upload is missing.
- Update the existing named skill. The row/detail overflow menu has **Replace**; **Add** can create a duplicate.

## Replacement

1. Open the existing skill and record the current name and version.
2. Choose **Replace** from its overflow menu.
3. The replacement page has one `input[type=file]`, accepting `.zip`, `.skill`, and `.md`. Use a complete archive when the skill has references or scripts. With the harness, `upload_file('input[type=file]', absolute_archive_path)` works after verifying the current form.
4. Check the preview's name and description, then save. The security scan runs on save. Wait for the saved Contents page and inspect any error instead of assuming the upload finished.
5. Reload and reopen Contents before declaring success. The UI can continue displaying an older version after a successful replacement, including in a separately running Desktop client.

Screenshot after navigation and actions. Content can reflow after reload, so locate the current buttons again rather than reusing coordinates from an earlier layout.

## Readback that proves the update

The Contents page provides a version selector such as **Name vN · current**, a file count, a file tree, and a download button. Verify:

- The new version is marked current.
- The actual changed instruction and any newly added reference are present.
- The downloaded saved files match the intended local source.

The saved-version download may be a **plugin archive**, even when the input was a single-skill archive. The observed saved layout contains `.claude-plugin/plugin.json` and `skills/<skill-name>/...`. Compare file bytes by relative path under that skill directory; comparing the two entire zip files would fail because the packaging differs. Use the observed archive member list rather than assuming this layout can never change.

Browser-triggered downloads emit `Browser.downloadWillBegin` and `Browser.downloadProgress` when CDP download events are enabled. The suggested filename can contain spaces. A `completed` event and a readable saved archive are stronger evidence than clicking the download icon alone. Restore temporary download-behavior overrides after readback.

When Desktop verification matters, refresh the Chat and Cowork skill view and inspect the changed Contents there too. A legacy on-disk cache can remain older than the current named plugin, so its contents alone do not identify the active uploaded version.

Successful upload and readback establish the stored instructions. They do not establish that an already-running conversation has reloaded them, that a fresh Cowork task has executed them, or that their behavioral results improved.

Verified against the current UI in September 2026. No account IDs, session tokens, or user skill contents are needed for this procedure.
