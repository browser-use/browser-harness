# Cloudflare dash — R2 API tokens

Creating an R2 S3-compatible credential pair (Access Key ID + Secret) via
the dashboard. Needed whenever you want `rclone` / `aws s3` against R2,
because the S3 endpoint requires a key pair that `wrangler login`'s OAuth
token cannot provide.

## Prefer wrangler where you can

Bucket lifecycle does **not** need the dashboard — do it on the CLI:

```bash
CLOUDFLARE_ACCOUNT_ID=<acct> wrangler r2 bucket create <name> --location oc
CLOUDFLARE_ACCOUNT_ID=<acct> wrangler r2 bucket list
CLOUDFLARE_ACCOUNT_ID=<acct> wrangler r2 bucket dev-url get <name>   # public r2.dev on/off
CLOUDFLARE_ACCOUNT_ID=<acct> wrangler r2 bucket domain list <name>   # custom domains
```

Only the **key pair** requires the browser. There is no wrangler command
that mints S3 credentials.

## URL patterns

- Token list: `https://dash.cloudflare.com/<accountId>/r2/api-tokens`
- Create (account-scoped): `.../r2/api-tokens/create?type=account`
- Create (user-scoped): `.../r2/api-tokens/create?type=user`
- Post-create reveal: `.../r2/api-tokens/success`

`<accountId>` is the 32-char hex from `wrangler whoami`. Navigating
straight to the `create?type=account` URL skips the list page.

Account tokens vs user tokens: account tokens survive the creating user
leaving the org; user tokens die with them. Prefer account tokens for
anything long-lived.

## Stable selectors

- Token name field: `#cf-form-input1` (a React controlled input — see quirks).
- Permission radios, addressed by `value`, which is stable and readable:
  - `input[value="admin-write"]` — Admin Read & Write
  - `input[value="admin-read"]`  — Admin Read only
  - `input[value="object-write"]` — Object Read & Write
  - `input[value="object-read"]`  — Object Read only (**the default**)
- Bucket scope radios: `input[value="all"]` (default) / `input[value="some"]`
- Bucket combobox (appears only after `some` is selected):
  `#react-select-2-input`, options `#react-select-2-option-<n>`
- Submit: the `<button>` whose `innerText` is `Create Account API Token`.

The radios have no `name` or `id` — `value` is the only stable handle.

## Framework / interaction quirks

**The name field is a React controlled input.** `Input.insertText` and
coordinate typing get reverted on the next render. Use the native setter:

```js
const inp = document.querySelector('#cf-form-input1');
const set = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
set.call(inp, 'my token name');
inp.dispatchEvent(new Event('input',  {bubbles:true}));
inp.dispatchEvent(new Event('change', {bubbles:true}));
```

**The radios respond fine to `.click()` in JS** — no native-setter dance
needed, unlike the text input.

**The bucket picker is react-select and commits on `mousedown`, not on
Enter.** CDP `Input.dispatchKeyEvent` for Enter does *not* select the
focused option even when the aria-live region says "option focused, 1 of 1".
Typing to filter works; committing does not. What works is a real
coordinate click on the option's *live* rect:

```python
r = js("""(()=>{const o=document.querySelector('#react-select-2-option-0');
const b=o.getBoundingClientRect();
return JSON.stringify({x:Math.round(b.x+b.width/2),y:Math.round(b.y+b.height/2)});})()""")
p = json.loads(r); click(p["x"], p["y"])
```

Re-measure the rect *after* filtering — the option list re-renders and a
coordinate captured from an earlier screenshot lands on a stale row.

**1Password (and similar) inject an autofill overlay** over the Permissions
block the moment the name field takes focus. It covers the radios in
screenshots and can swallow clicks. `press_key("Escape")` dismisses it.
Prefer JS `.click()` on the radios so the overlay is irrelevant.

## Waits

`wait_for_load()` is sufficient for the create page. After clicking submit,
allow ~5 s before reading `/success` — the page swaps client-side and
`wait_for_load()` can return while the old DOM is still mounted.

## Traps

- **The default permission is `object-read`, and the default scope is all
  buckets.** Both defaults are wrong for an upload token. Always assert the
  final state before submitting.
- **`Apply to specific buckets only` renders an empty combobox with the
  validation error "At least one bucket is required" already visible.** That
  error string persists until a bucket is genuinely committed, which makes it
  a reliable success check: re-read it after selecting.
- **Secrets are shown exactly once** on `/success`. There is no way to
  re-reveal; a lost secret means minting a new token.
- **R2 is not a separate OAuth scope in wrangler.** `wrangler whoami` lists
  no `r2` permission, but `wrangler r2 bucket list` works anyway — R2 rides
  along with the account-level Workers scopes. Don't diagnose a missing `r2`
  scope from the whoami output; just try the command.

## Reading the credentials without leaking them

The reveal page puts all three secrets in `body.innerText`. To inspect page
structure safely (e.g. in a logged agent transcript), mask them first:

```python
js(r"""document.body.innerText.replace(/[A-Za-z0-9_\-]{20,}/g,
      m => '<REDACTED:'+m.length+'chars>')""")
```

To extract for real, pull by label and hand straight to the consumer without
printing. Lengths are a useful assertion: Access Key ID is 32 chars, Secret
Access Key is 64, the API token value is 53.

```python
raw = js(r"""(()=>{const t=document.body.innerText;
const ak=t.match(/Access Key ID\s+([A-Za-z0-9]{32})/);
const sk=t.match(/Secret Access Key\s+([A-Za-z0-9]{64})/);
return JSON.stringify({ak:ak?ak[1]:null, sk:sk?sk[1]:null});})()""")
d = json.loads(raw)
subprocess.run(["rclone","config","create","r2","s3",
    "provider=Cloudflare",
    f"access_key_id={d['ak']}", f"secret_access_key={d['sk']}",
    f"endpoint=https://{ACCOUNT_ID}.r2.cloudflarestorage.com",
    "region=auto","acl=private","no_check_bucket=true"],
    capture_output=True)   # never echo stdout
```

Note `\s+` not `\s` between label and value — the DOM puts a blank line there.

## rclone against R2 — settings that matter

- Endpoint is `https://<accountId>.r2.cloudflarestorage.com`, `region=auto`.
- `no_check_bucket=true` is **required** for a bucket-scoped token. Without
  it rclone attempts a bucket create/head on first write, which an
  `object-write` token is not permitted to do, and the whole transfer fails
  on object one.
- A bucket-scoped token also cannot list buckets, so `rclone lsd r2:` fails
  while `rclone lsf r2:<bucket>` succeeds. That is expected, not a
  misconfiguration — verify connectivity against the bucket, not the root.
- `wrangler r2 object put` is single-object and size-capped; it is the wrong
  tool for bulk. Use rclone for anything beyond a handful of files.
