---
name: wordpress-zion-builder
description: Legacy WordPress Kallyas/Zion Builder draft inspection and UID-level saving through the authenticated front-end builder.
---

# WordPress Kallyas / Zion Builder

Legacy Kallyas sites commonly keep page-builder content outside normal `post_content`. The WordPress REST page response can therefore report an empty content body even though the page renders a large Zion layout.

## Useful routes

```text
/wp-admin/post.php?post=<POST_ID>&action=edit
/?page_id=<POST_ID>&preview=true
/?page_id=<POST_ID>&preview=true&zn_pb_edit=1
```

The normal WordPress edit screen exposes an `Edit this page with pagebuilder` link with ID `#zn_edit_page`. Its target is the authenticated front-end builder route above.

On the builder page, wait for:

```javascript
typeof window.ZnPbData === 'object' && window.ZnPbData.postId === POST_ID
```

Do not rely on `wait_for_load()` alone. Old theme pages can remain in `interactive` or stall on third-party scripts long after Zion data and the visible layout are ready.

## Builder data

`window.ZnPbData` includes:

- `current_layout`: a UID-indexed view of the layout;
- `page_options`: page-level Zion settings;
- `postId`: the page/post ID;
- element metadata and saved-element catalogs.

For inspection, `ZnPbData.current_layout[uid].data.options` is convenient. For saving, build the canonical nested map from the live editor DOM:

```javascript
const map = jQuery.page_builder.build_map(
  jQuery('.zn_pb_wrapper > .zn_pb_section'),
);
```

The result is an object with numeric top-level keys and nested `content` arrays. Walk it recursively and match the exact `uid`; do not edit every matching string. The UID-indexed `current_layout` view repeats child objects through parent `content`, so naive recursive string counts can overstate the number of distinct elements.

## Safe UID-level patch pattern

Before a mutation:

1. Confirm `ZnPbData.postId` is the expected unpublished draft.
2. Confirm the exact UID exists once in the canonical map.
3. Confirm the old option value matches the recorded baseline.
4. Change only the intended option.
5. Keep a separate fresh readback; an in-memory map can remain changed after a failed save.

Example recursive lookup:

```javascript
const matches = [];
function walk(value) {
  if (!value || typeof value !== 'object') return;
  if (value.uid === targetUid) matches.push(value);
  for (const child of Object.values(value)) {
    if (child && typeof child === 'object') walk(child);
  }
}
walk(map);
if (matches.length !== 1) {
  throw new Error(`Expected one ${targetUid}; found ${matches.length}`);
}
```

Typical button options are:

```javascript
element.options.text
element.options.link = { url, target, title }
```

Typical text-box HTML is:

```javascript
element.options.stb_content
```

## Zion draft save endpoint

The editor's own save control posts to WordPress AJAX:

```javascript
const result = await new Promise((resolve) => {
  jQuery.ajax({
    url: ZnAjax.ajaxurl,
    method: 'POST',
    timeout: 120000,
    data: {
      action: 'znpb_publish_page',
      template: JSON.stringify(map),
      post_id: window.ZnPbData.postId,
      security: ZnAjax.security,
      page_options: window.ZnPbData.page_options,
    },
    success: (data, _status, xhr) => resolve({
      ok: true,
      http: xhr.status,
      response: String(data),
    }),
    error: (xhr, status) => resolve({
      ok: false,
      http: xhr.status,
      status,
    }),
  });
});
```

Despite the action name `znpb_publish_page`, this handler saves Zion builder metadata; it does not by itself change a WordPress draft to published status. Still, prove status after every save rather than trusting the name or UI message.

Never print or persist `ZnAjax.security`, REST nonces, cookies, or authenticated request headers.

## Status and fresh readback

The standard edit page usually exposes `wpApiSettings.nonce`. Use it only inside the page context to confirm the server record without returning the nonce:

```javascript
const response = await fetch(
  `/wp-json/wp/v2/pages/${POST_ID}?context=edit`,
  {
    credentials: 'include',
    headers: { 'X-WP-Nonce': wpApiSettings.nonce },
  },
);
const page = await response.json();
return {
  http: response.status,
  id: page.id,
  status: page.status,
  modified: page.modified,
};
```

For rendered-server readback without waiting for third-party scripts, fetch the authenticated preview HTML from an admin page and parse it:

```javascript
const response = await fetch(
  `/?page_id=${POST_ID}&preview=true&fresh=${Date.now()}`,
  { credentials: 'include' },
);
const html = await response.text();
const documentCopy = new DOMParser().parseFromString(html, 'text/html');
```

Use that copy to count exact links, legacy embeds, and stale values. For visual proof, open a real authenticated preview and verify desktop/mobile overflow and screenshots.

## Guardrails

- Work on an explicitly identified draft or staging copy unless publication is separately authorized.
- Record the draft ID, status, exact UIDs, before values, and intended replacements.
- Treat global headers, menus, footers, Smart Areas, and templates as public surfaces even while reviewing a draft page.
- After saving, fresh-read the builder or rendered HTML, confirm the server record is still `draft`, confirm anonymous draft access fails, and verify the public source page is unchanged.
- If an AJAX save has an indeterminate client result, check the server `modified` value and fresh content before retrying. Do not assume either success or failure from a stalled browser process.
