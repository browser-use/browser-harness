# Tracing mystery order attributes (`__ref_id`, `shipping-token`, `_om__*`)

Storefront checkouts can carry hidden custom attributes (keys starting with `_`) that show up
on orders under "Additional details". Owners read them as fraud markers. Usually they are
pixels/apps. Known values:

- `__ref_id` (28 random printable-ASCII chars, e.g. `eF*\OUo-:Rk;P!di6\TnlaV,y2cK`) and the
  older `shipping-token` = **Triple Whale pixel**. Theme app embed
  `shopify://apps/triplewhale/blocks/triple_pixel_snippet`; obfuscated code served from
  `https://api.config-security.com/first?host=<shop>.myshopify.com&plat=SHOPIFY` contains
  `attributes:{__ref_id:x}`. Also writes localStorage `refId`, `beacon`, `EVENTS_MAP`,
  `true_rand_gen_sequence.dat_`, `auth-security_rand_salt_`, `di_pmt_wt` as
  `data:application/zip;base92,...` blobs. Harmless; disable the app embed to stop it.

## Traps

- It is applied through the checkout Proposal request, so `/cart.js` shows `attributes: {}`
  while the checkout (and later the order) has it. Don't conclude "not from the storefront".
- Theme grep finds nothing: the loader is an app block (`<!-- BEGIN app block: shopify://apps/... -->`
  in the served HTML), and the payload is fetched + `eval`ed at runtime.
- Extension bisecting is a dead end unless an extension-free context also lacks it (see below).

## Recipe

1. Admin GraphQL: `orders(...) { customAttributes { key value } }` plus
   `abandonedCheckouts` gives the on/off timeline (attribute appears when the app embed is on).
2. Served HTML, not theme files: fetch a product page, search for `BEGIN app block:` and
   `onreadystatechange`/`eval(` to find loaders and their remote URLs.
3. Catch the writer with a stack trace in a clean context:

```python
ctx = cdp("Target.createBrowserContext")["browserContextId"]      # no extensions, no cookies
tid = cdp("Target.createTarget", url="about:blank", browserContextId=ctx)["targetId"]
switch_tab(tid)
cdp("Page.enable")
cdp("Page.addScriptToEvaluateOnNewDocument", source="""
(function(){ window.__log=[]; const o=Storage.prototype.setItem;
  Storage.prototype.setItem=function(k,v){ if(/ref|beacon|EVENTS/i.test(k)) window.__log.push({k,stack:new Error().stack.split("\\n").slice(1,7)}); return o.apply(this,arguments); }; })()
""")
goto_url("https://<shop>/products/<handle>"); wait_for_load(); wait(8)
print(js("JSON.stringify(window.__log)"))       # stack names the inline loader line / eval origin
```

4. Read the checkout's attribute from its server-rendered state (HTML-entity escaped):

```python
import re, html
h = html.unescape(js("document.documentElement.outerHTML"))
re.findall(r'"key":"__ref_id","value":"([^"]+)"', h)
```

5. To see who submits it: `cdp("Network.enable")`, navigate to `/checkout`, then
   `drain_events()` and filter `Network.requestWillBeSent` whose `postData` contains the key
   (`operationName=Proposal` from checkout-web, initiator stack included).

Note: `cdp()` takes CDP params as kwargs (`cdp("Page.navigate", url=...)`), not a dict.
`drain_events()` caps at 500 events; disable Network before relying on Runtime/DOMStorage events.
