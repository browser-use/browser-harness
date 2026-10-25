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

## Silent failure modes — the write succeeds, the render ignores it

Never trust a settings write by reading it back; it echoes what you wrote while the page renders something else. **Verify with `getComputedStyle` on the rendered front end.** Four field-tested cases:

1. **`typography_typography:'custom'` with `typography_font_family:''`** emits a typography rule with no `font-family`, so the element silently inherits the theme default while *looking* configured. Audits that hunt for "missing custom typography" skip these. Always set both keys together.
2. **Responsive hide controls want the device-suffixed value.** `hide_mobile:'hidden'` produces class `elementor-hidden`, which matches no CSS rule anywhere; the correct value is `'hidden-mobile'`. Read the control first: `elementor.getContainer(id).settings.controls.hide_mobile` exposes `prefix_class` and `return_value`. The hiding rule also requires an `.elementor` ancestor.
3. **`__globals__` outranks the literal value.** A widget carrying `__globals__: {primary_color: "globals/colors?id=accent"}` renders the global color no matter what you write to `primary_color`, and reading the setting back returns your value. Clear the binding alongside the literal: `{__globals__:{primary_color:''}, primary_color:'#...'}`. Applies to any global-bindable control.
4. **Container responsive widths default to empty, not to the desktop value** — a 25% tile stays 25% on phones unless `width_mobile` is set. The tablet value sometimes stores correctly but emits no CSS; verify, and fall back to a media query in the element's `custom_css` (the `selector` prefix scopes it to the element).

## Global fonts and colors (the kit)

The kit is a document: id at `elementor.config.kit_id`, loaded via `$e.run('panel/global/open')`, then `elementor.documents.get(kitId)`. Edit `system_typography` / `system_colors` / site-wide `custom_css` with `document/elements/settings` on `kit.container` and save with `$e.run('document/save/default', {document: kit})`. For `system_colors`, pass the full array of plain attribute objects, not mutated models — model `.set()` calls don't register as document changes. Two traps:

- **Themes can push Customizer values into the kit's `system_colors` on save**, silently reverting your edits (fonts and custom colors persist, system colors revert). The real lever is then **Customizer → General Colors**, which cascades into Elementor's globals.
- Before assuming globals do anything, grep the page CSS for `var(--e-global-color-`: pages built with per-widget colors reference the globals zero times, and changing them is invisible there.

## Column containers invert alignment

With `flex-direction: column`, `flex_align_items` is the **horizontal** axis: `center` horizontally centers every child, which presents as "the text block won't left-align." Use `flex_align_items:'flex-start'` plus `flex_justify_content` for vertical placement. Two related traps: containers created via the API default to `row` (an eyebrow + heading + grid stack comes out side-by-side, headings squeezed to a sliver), and boxed containers wrap children in an `.e-con-inner` div, so inspect computed styles there rather than on the outer element.

## Theme parts and traps

- A widget rendered outside the page content belongs to the document at `el.closest('[data-elementor-id]')` (`dataset.elementorId`/`elementorType`). Ideapark/Goldish themes inject a whole "Footer (pattern)" **page** above the real footer — edit that page, not the footer template.
- REST: `pages`, `media`, `product_cat` read fine anonymously; `elementor_library` returns 401 without a nonce — scrape `/wp-admin/edit.php?post_type=elementor_library` for template IDs instead.
- Sections with `hide_desktop` + `hide_tablet` + `hide_mobile` all set are parked drafts, invisible everywhere — common junk in old client pages.
- Repeater widgets (sliders, running-line marquees) store items as arrays in settings (e.g. `item_list`); replace the whole array via `document/elements/settings`, preserving `_id`s.
