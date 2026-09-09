# SIMchapter DNN custom HTML and asset workflow

Applies to `simchapter.cvsapphire.com` sites that use DNN HTML modules and 2sxc/ADAM-managed assets.

## DNN HTML modules

- Use the core DNN `HTML` module for independent custom-code sections.
- Edit the module with the Basic Text Box, then set **Render Mode** to `Raw` before saving custom HTML, CSS, or JavaScript. `Text` mode inserts `<br>` elements into line breaks and can corrupt scripts and layout.
- Treat a save as published unless the site has workflow enabled. Verify the signed-out page after every save; an authenticated editor view can hide permissions or version-state problems.
- The rich-text editor may sanitize `<style>`, `<script>`, classes, and attributes. Do not paste custom code through the rich-text surface.

## 2sxc edit calls

- When opening a specific entity with the client API, pass entity identifiers inside `params`:

  ```js
  cms.run({ action: 'edit', params: { entityId, entityGuid } })
  ```

- Flattening `entityId` or `entityGuid` at the top level is ignored and can open an empty item editor.

## ADAM image URLs

- The public ADAM URL segment comes from the entity field's internal name, not necessarily the friendly label shown in the editor.
- For a field labeled “Right Side Image” whose internal name is `Image`, the durable public shape is:

  ```text
  /Portals/SDI/adam/Components/<entity-guid>/Image/<filename>
  ```

- Do not manufacture the path from the UI label. Use the upload response or inspect the rendered source, then confirm the exact URL signed out with HTTP 200 and `Content-Type: image/*`.
- Use collision-safe filenames and verify the returned public bytes against the local source hash when migrating legacy Higher Logic images.

## Verification checklist

- Test the target route with no cookies.
- Confirm every migrated image request uses `/Portals/SDI/` and no legacy Higher Logic image URL remains in the custom modules.
- Check the browser console, runtime component counts, and horizontal overflow at desktop and mobile widths.
- Click every source-page CTA signed out; a correct `href` can still appear broken when the destination DNN page does not exist.
