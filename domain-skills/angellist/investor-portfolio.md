# AngelList — Investor / scout portfolio extraction

## URL shape

Fund LP view (the one scouts use to file + review deployments):
```
https://venture.angellist.com/v/lead/<fund-slug>/vehicle/<vehicle-slug>/investing
```

Individual investment detail panel opens **in the same URL** with `/investing/<investment_id>` appended. The panel is a right-side slide-over, not a new page.

## Virtualized row list

The investment table is **virtualized** — only ~40 rows render initially even when the fund has 50+ investments. To load the tail:

```python
for _ in range(8):
    js("window.scrollTo(0, document.documentElement.scrollHeight)")
    wait(0.8)
```

After that, all rows are in the DOM and `document.querySelectorAll('.styles_title__XcP6F')` returns the full list.

## Rows are not anchors

Row `<a>` tags don't exist. The click target is a React div with an `onclick` handler. Coordinate clicks **do not** reliably hit it. Use a DOM click instead:

```python
js("""
(() => {
  const title = Array.from(document.querySelectorAll('.styles_title__XcP6F'))
    .find(el => el.textContent.trim() === 'Berta Systems, Inc.');
  const row = title.closest('.styles_row__M6RnG');
  row.click();
  return 'OK';
})()
""")
```

Stable selectors:
- `.styles_title__XcP6F` — company name cell
- `.styles_row__M6RnG` — the row container with the click handler
- `.styles_rowWrapper__XFda_.styles_clickable__1_n5z` — the outer row wrapper (also clickable, same result)

URL updates to `.../investing/<id>` after the click — a reliable "it worked" signal.

## Detail panel — extraction

The side panel has no stable outer class. Grab it by walking up from the "Investment in <name>" heading:

```python
js("""
(() => {
  const heading = Array.from(document.querySelectorAll('div,span,h1,h2,h3,h4,h5'))
    .find(el => el.textContent?.trim().startsWith('Investment in'));
  let panel = heading;
  for (let i = 0; i < 15; i++) {
    if (!panel.parentElement) break;
    panel = panel.parentElement;
    if (panel.offsetWidth > 300 && panel.offsetWidth < 900) return panel.innerText;
  }
  return panel.innerText;
})()
""")
```

The panel `innerText` is label-newline-value, easy to parse with regexes like:
```python
re.search(r"\nFounders\n(.+?)(?=\n[A-Z][a-zA-Z ?\-]+\n|$)", panel, re.DOTALL)
```

Fields always present: `Investment Amount`, `Fund Thesis Match`, `Investing in` (instrument), `Round`, `Round Size`, `Conversion Cap`, `Discount`, `Pro-rata rights included?`, `Equity warrants ...?`, `Country of Incorporation`, `Type of Incorporation`, `Founders`, `Description`, `Which category does this deal fall into?`, `Please provide the founder's LinkedIn profile URL.`, `Company Website`.

Sometimes present: `Notable Co-Investors` (can be `—`), `Reason for Investing` (can contain pitch deck URL).

## Iteration pattern

To extract all investments, click each row, extract panel, move on. The panel switches content on each click — no need to close it between rows. Sleep ~1.5–2s between clicks for the panel to update.

## Traps

- **Cookie consent dialog** (OneTrust) has a huge hidden `innerText` blob. If you grab `document.body.innerText` without scoping to the panel, you'll get cookie consent copy, not investment data. Always target the panel via the "Investment in" heading.
- **Word-joiner char** `\u2060` sneaks into founder names (esp. when the filer pasted from Slack). Strip before writing: `name.replace('\u2060', '')`.
- **Founder separator** is usually `,` but sometimes `;` — split on `[,;]`.
- **Role annotations** like `"Oliver Gilan (CEO)"` — strip `\s*\(.*?\)\s*` if you want plain names.
- **Currency on round_size varies** (USD default, but also `£`, `€`, `CHF`). Don't assume USD.

## Fund scope

LP view only shows investments made from that specific vehicle. Thomas has multiple scout funds (Fund III, Fund IV) — each has its own URL. The `/investing` endpoint shows "fully deployed" and "no longer accepting submissions" for closed funds but the history remains visible.
