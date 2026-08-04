# Elementor (WordPress) — programmatic page editing, no SSH needed

Everything below runs through an authenticated wp-admin session in the user's Chrome. Field-tested on Elementor 3.x with flexbox containers.

## Read a page's full layout JSON

Open the editor `/wp-admin/post.php?post=<ID>&action=elementor`, wait until
`typeof $e !== 'undefined' && elementor.getPreviewContainer && elementor.getPreviewContainer()`,
then `JSON.stringify(elementor.config.initial_document.elements)`. This is the same data as the protected `_elementor_data` post meta.

Find a page's ID from the front end: `document.body.className.match(/page-id-(\d+)/)[1]`.

## Insert complex nested elements (the clipboard trick)

`$e.run('document/elements/create')` is unreliable for deep trees. Instead:

```js
elementorCommon.storage.set('clipboard', {type:'elementor', siteurl: location.origin, elements: [model]});
$e.run('document/elements/paste', {container: elementor.getPreviewContainer(), options:{at: 0, rebuild: true}});
```

Handles arbitrary nesting and regenerates all ids. **Paste applies asynchronously** — re-read `elementor.getPreviewContainer().children.map(c=>c.id)` after a beat before concluding it failed.

## Delete / move / edit settings

```js
$e.run('document/elements/delete', {container: elementor.getContainer(id)});
$e.run('document/elements/move', {container: elementor.getContainer(id), target: elementor.getPreviewContainer(), options:{at: 1}});
$e.run('document/elements/settings', {container: elementor.getContainer(id), settings: {...}, options:{external: true}});
```

`move` with `options.at` can land off-by-one when the element is already in the same parent (index computed after removal) — verify order and re-move if needed.

Save with `$e.run('document/save/default')`; confirm via `elementor.documents.getCurrent().editor.isChanged === false`.

## Media uploads without SSH

Go to `/wp-admin/media-new.php`, then CDP `DOM.setFileInputFiles` with multiple local paths on the first `input[type=file]` (plupload's hidden html5 input) — uploads all files automatically. Collect attachment IDs afterward from `/wp-json/wp/v2/media?search=<slug>` (public read, no nonce).

## WooCommerce category thumbnails

The `wc-categories` widget renders product-category term thumbnails; empty gray circles mean the terms lack images. Set programmatically without the media modal: open `term.php?taxonomy=product_cat&tag_ID=<N>&post_type=product`, set hidden input `#product_cat_thumbnail_id` to the attachment ID, and `document.getElementById('edittag').submit()`.

## Theme parts and traps

- A widget rendered outside the page content belongs to the document at `el.closest('[data-elementor-id]')` (`dataset.elementorId`/`elementorType`). Ideapark/Goldish themes inject a whole "Footer (pattern)" **page** above the real footer — edit that page, not the footer template.
- REST: `pages`, `media`, `product_cat` read fine anonymously; `elementor_library` returns 401 without a nonce — scrape `/wp-admin/edit.php?post_type=elementor_library` for template IDs instead.
- Sections with `hide_desktop` + `hide_tablet` + `hide_mobile` all set are parked drafts, invisible everywhere — common junk in old client pages.
- Repeater widgets (sliders, running-line marquees) store items as arrays in settings (e.g. `item_list`); replace the whole array via `document/elements/settings`, preserving `_id`s.
