# SVO — Zählerstandsmeldung via WebMCP

SVO's meter-reading form exposes a **WebMCP** tool, so you don't have to drive the DOM. See `interaction-skills/webmcp.md` for the general `navigator.modelContext` mechanics (the `executeTool` arg shape is the part that trips people up).

URL: `https://svo-test.de/service/zaehlerstandsmeldung` (test environment).

## Tool

`report_meter_reading` — fills the existing form's fields. **It never submits**: CAPTCHA + final submit stay a human action, and for privacy it returns no echo of the entered values. So verify by reading the DOM, not by the result text.

### Input schema

Required: `zaehlernummer`, `ablesedatum` (`YYYY-MM-DD`), `vorname`, `nachname`, `e_mail_adresse`, `telefonnummer_49`, `haben_sie_einen_ht_nt_zaehler` (boolean).

Meter-reading fields are **conditional on the tariff flag**:

- `haben_sie_einen_ht_nt_zaehler: true` → two-rate (HT/NT) meter → fill `zaehlerstand_ht` **and** `zaehlerstand_nt`. The single-rate field is hidden.
- `haben_sie_einen_ht_nt_zaehler: false` → single-rate meter → fill `zaehlerstand` only.

Never fill both the single-rate and the HT/NT fields.

## Call it (HT/NT example)

```python
import json
args = {
    "zaehlernummer": "1ESY1160123456",
    "ablesedatum": "2026-06-25",
    "vorname": "Max",
    "nachname": "Mustermann",
    "e_mail_adresse": "max.mustermann@example.com",
    "telefonnummer_49": "0171 2345678",
    "haben_sie_einen_ht_nt_zaehler": True,
    "zaehlerstand_ht": "012345",
    "zaehlerstand_nt": "006789",
}

res = js(r'''(async (argsJson) => {
  const mc = navigator.modelContext;
  let tools = mc.getTools();
  if (tools && typeof tools.then === 'function') tools = await tools;
  const tool = tools.find(t => t.name === 'report_meter_reading');
  let r = mc.executeTool(tool, argsJson);   // RegisteredTool object + JSON STRING
  if (r && typeof r.then === 'function') r = await r;
  return r;
})(%s)''' % json.dumps(json.dumps(args)))
print(res)
```

## Verify

The HT/NT toggle is a radio group `haben_sie_einen_ht_nt_zaehler` (HT/NT vs. "Standardzähler"). After the call, read field values to confirm:

```python
print(js(r'''(() => {
  const out = [];
  document.querySelectorAll('input,select,textarea').forEach(el => {
    if (el.type === 'hidden' || !el.name) return;
    out.push({name: el.name, value: (el.type==='checkbox'||el.type==='radio') ? el.checked : el.value});
  });
  return out;
})()''')
```

## Notes

- There's a `honeypot` text input — leave it empty (spam trap; filling it likely flags the submission).
- The page has a fixed notification banner overlaying the lower viewport; `scrollIntoView`/`window.scrollTo` to bring form fields above it before screenshotting.
- Conversational use: read the tool's `inputSchema.required` first, then ask the user for the tariff type + the matching reading(s) before calling.
