# agents.aiki.as

## Public widget gallery

- `https://agents.aiki.as/` opens the Beauty widget test gallery.
- Select an agent with `?agent=<slug>` and a widget with `?variant=spotlight|classic`.
- Supported public agent slugs are `beauty-technology`, `dermapen`, `genosys`, `innoaesthetics`, `melineskin`, and `noonaesthetics`.
- The selected links have `aria-current="true"`; all selectors are `.picker a` links, so direct URL navigation is more stable than coordinate clicking.
- The widget host is `[data-aiki-widget]`; its UI is inside an open shadow root.

## Routes and waits

- `/studio` is the internal Agent Studio shell. Its data calls prompt for an admin key and send it as `X-Admin-Key`; never put that key in a URL.
- The public hostname is behind a strict Cloudflare Tunnel path allowlist. A route can work against the origin yet return tunnel-level `404` in production until its exact path is added to the allowlist.
- `wait_for_load()` only covers page load. Wait about 500 ms after opening or closing a widget before taking a screenshot because the panel uses opacity, transform, and blur transitions.
