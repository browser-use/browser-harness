# Google Ads — UI operations

Field-tested against ads.google.com on 2026-04-21.
**Requires:** Browser Harness attached to a real Chrome profile that is already signed into the target Google Ads account.

Use this for:

- campaign, ad group, ad, and keyword views
- ad edits
- assets and sitelink associations
- conversion-action inspection and edits
- Google tag settings inside Ads
- change-history verification

It is not for: budget changes, bidding strategy decisions, or anything that needs product judgment rather than UI mechanics.

## URL patterns

All views live under `https://ads.google.com/aw/`. Keep both `ocid` and `authuser=0` in deep links.

| View | Pattern |
|---|---|
| Overview | `/aw/overview?ocid=<ocid>&authuser=0` |
| Campaigns | `/aw/campaigns?ocid=<ocid>&authuser=0` |
| Campaign -> Ads | `/aw/ads?ocid=<ocid>&campaignId=<cid>&authuser=0` |
| Campaign -> Ad groups | `/aw/adgroups?ocid=<ocid>&campaignId=<cid>&authuser=0` |
| Campaign -> Keywords | `/aw/keywords/search?ocid=<ocid>&campaignId=<cid>&authuser=0` |
| Campaign -> Settings | `/aw/settings?ocid=<ocid>&campaignId=<cid>&authuser=0` |
| Assets | `/aw/assets?ocid=<ocid>&authuser=0` |
| Asset associations | `/aw/assets/associations?ocid=<ocid>&authuser=0` |
| Conversions summary | `/aw/conversions/summary?ocid=<ocid>&authuser=0` |
| Change history | `/aw/changehistory?ocid=<ocid>&authuser=0` |

Observed Ads quirk:

- `assetFieldType=31` in the URL is the sitelink-associations view key. Treat that as observed behavior, not a public Google constant.
- `ocid` is not the customer ID. It is session-scoped and can change across logins. Re-read it from `current_tab()["url"]` when deep links stop working.

Grab `ocid` from the current URL:

```python
from urllib.parse import urlparse, parse_qs

def current_ocid():
    return parse_qs(urlparse(current_tab()["url"]).query).get("ocid", [None])[0]
```

## Stable selector strategy

Google Ads is an Angular SPA with generated classes everywhere. Prefer:

- `aria-label`
- visible button text
- `role="row"` and visible cell text
- stable semantic classes like `particle-table-row`

Avoid:

- `_nghost-*`
- `_ngcontent-*`
- `mat-mdc-*` ids
- suffix-heavy `ess-*` / `aw-*` classes unless there is no better anchor

## Read tables as text first

The campaigns and ads tables are usually easier to read as one text blob than as a forest of nested divs.

```python
txt = cdp(
    "Runtime.evaluate",
    expression="document.body.innerText",
    returnByValue=True,
)["result"]["value"]
```

Useful cases:

- finding a campaign row and extracting its campaign ID
- checking status text such as `Eligible`, `Not eligible`, `Removed`
- confirming whether the visible table matches the route you think you opened

## Ads tab trap: "1 - 1 of 1" but no visible row

If the footer says `1 - 1 of 1` but the body looks empty, the status filter chip is hiding the row.

Default trap:

- fresh Ads views often come up filtered to `Ad status: Enabled, Paused`
- that hides `Removed`, `Disapproved`, `Under review`, and `Limited by policy`

Fix:

- expand the visible status chip and add `All`
- do not trust the row count alone

## Editing an ad

Each ad row has an edit button whose `aria-label` starts with `Edit this Ad,`. The icon is visually transparent until hover, but compositor-level clicks still land on it.

```python
info = cdp(
    "Runtime.evaluate",
    expression="""
(() => {
  const btn = document.querySelector('[aria-label^="Edit this Ad,"]');
  if (!btn) return null;
  btn.scrollIntoView({block: 'center'});
  const r = btn.getBoundingClientRect();
  return {
    x: Math.round(r.x + r.width / 2),
    y: Math.round(r.y + r.height / 2),
    aria: btn.getAttribute('aria-label'),
  };
})()
""",
    returnByValue=True,
)["result"]["value"]
click(info["x"], info["y"])
wait_for_load()
```

Useful selectors in the ad editor:

| Field | Selector |
|---|---|
| Final URL | `input[aria-label="Final URL"]` |
| Path 1 | `input[aria-label="Path 1"]` |
| Path 2 | `input[aria-label="Path 2"]` |
| Business name | `input[aria-label="Business name"]` |
| Description | `textarea[aria-label="Description"]` |
| Headline | `.headline` in DOM order |

### Ad-editor text entry

For the ad editor, the native setter plus `input` / `change` / `blur` works reliably enough on normal text inputs:

```python
def set_input_value(selector, value):
    return cdp(
        "Runtime.evaluate",
        expression=f"""
(() => {{
  const el = document.querySelector({selector!r});
  if (!el) return "missing";
  const proto = el.tagName === "TEXTAREA"
    ? HTMLTextAreaElement.prototype
    : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
  setter.call(el, {value!r});
  el.dispatchEvent(new Event("input", {{bubbles: true}}));
  el.dispatchEvent(new Event("change", {{bubbles: true}}));
  el.dispatchEvent(new Event("blur", {{bubbles: true}}));
  return el.value;
}})()
""",
        returnByValue=True,
    )["result"]["value"]

set_input_value('input[aria-label="Final URL"]', 'https://example.com/new-url')
```

Do not rely on `Cmd+A` plus typing in the ad editor. In Google Ads, `press_key("a", modifiers=4)` is often swallowed at the document level and the new text lands in the middle of the old value.

## Asset forms and sitelinks: silent-save trap

Asset creation is stricter than ad editing. Sitelink forms can look filled, let you click Save, route back to the associations table, and still create nothing.

Symptoms:

- fields visibly contain the new values
- Save appears to work
- no new row shows up in Associations
- no corresponding event appears in Change history

Most likely cause:

- Angular accepted the displayed value but did not treat the control as a true user edit
- the form stayed effectively pristine, so the save pipeline no-op'd

Preferred entry pattern for sitelink and similar asset forms:

1. focus the real input
2. enter text through Chrome input primitives, not plain `.value =`
3. blur or tab out of the field
4. read the field value back
5. verify in Change history after save

Practical pattern:

```python
js("""(() => {
  const el = document.querySelector('input[aria-label="Sitelink text"]');
  if (!el) return "missing";
  el.focus();
  return "focused";
})()""")
type_text("Airport transfers")
press_key("Tab")
```

If `type_text(...)` appends instead of replacing, fall back to a field-specific clear strategy first, then retype. Prefer real text entry and blur over setter-only writes for asset forms.

### Sitelink associations view

Use `Assets -> Associations` as the primary verification surface.

Checks that matter:

- visible chip or heading says `Sitelink`
- the scope column matches account or campaign as intended
- the row actually exists after save

Do not trust the URL alone. Ads can keep stale filter chips while the query string says you are in a different asset view.

## Conversion actions

Main view: `/aw/conversions/summary`

Operations that behave predictably:

- open an existing conversion row by name
- read category, source, status, and optimization state from the list
- edit settings
- archive or remove when the UI exposes it

Stable anchors:

- row text containing the conversion action name
- visible column text such as `Category`, `Source`, `Status`
- buttons or menu items labeled `Edit`, `Save`, `Archive`, `Remove`

Destructive changes often confirm in dialogs. After any conversion edit:

1. return to the list and reread the row
2. confirm the edit in Change history

## Google tag settings inside Ads

Ads has a Google-tag settings surface that is distinct from GTM.

Use it for:

- enhanced conversions
- user-provided data capability
- tag details
- diagnostics around tag coverage

Stable anchors:

- `Goals`
- `Settings`
- `Enhanced conversions`
- `Tag details`
- `Allow user-provided data capabilities`

Important trap:

- Ads can accept a tag-layer setting while GTM still has unpublished changes. The two systems are related, but they are not the same deployment boundary.

## Change history is the source of truth

For Google Ads UI work, Change history is the durable proof that a change landed.

Use it to verify:

- asset creation or edits
- conversion-action edits
- ad edits when the list view is ambiguous

If a save looked successful but Change history never shows a matching event, treat the save as failed.

## Confirm-it's-you modal

Sensitive edits can trigger a `Confirm it's you` prompt.

Observed behavior:

- CDP-driven clicks on `Confirm` can bounce into a Google auth flow that does not complete cleanly under automation
- a manual click by the user in the real browser window is more reliable
- later saves in the same session may proceed without another prompt, but do not hard-code that assumption

Protocol:

1. detect the prompt by visible text
2. have the user confirm in the real browser if needed
3. retry the save
4. verify in Change history

## Dismissing popups

Ads throws recurring overlays such as AI suggestions, disapproval nudges, app prompts, and advisor panels.

Cheap cleanup:

```python
cdp(
    "Runtime.evaluate",
    expression="""
document.querySelectorAll('[aria-label*="dismiss" i], [aria-label*="close" i]')
  .forEach(el => el.offsetParent && el.click());
""",
)
```

Re-run this when a visible target becomes unclickable for no obvious reason.

## RTL / Hebrew accounts

Hebrew accounts flip the layout RTL.

- selectors still work
- table column order is mirrored
- if you compute click coordinates from table structure, check `document.dir`

## Known traps

- `ocid` is session-scoped and can change after login churn
- deep links without `authuser=0` can silently land in the wrong Google account
- URL state and visible chip state can disagree
- successful-looking navigation after Save is not proof of persistence
- Ads table filters hide rows without making the footer count obviously wrong
- ad-editor inputs and asset forms do not always respond to the same text-entry strategy

## Related

- `interaction-skills/dialogs.md` for confirmation flows
- `interaction-skills/dropdowns.md` for Angular comboboxes and chips
- `interaction-skills/network-requests.md` if you want to inspect Ads XHR traffic instead of scraping the DOM
