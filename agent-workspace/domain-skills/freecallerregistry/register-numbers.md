# Free Caller Registry: register outbound numbers

`https://www.freecallerregistry.com/fcr/`. One free form that reaches the three call-protection providers behind the big US carriers' "Spam Likely" labels: First Orion, Hiya and TNS. Registering a number again adds nothing.

## Flow

1. **Email code.** Enter a business email (`contactEmail`) and press "Send Verification Code". A 5-digit code arrives by email ("Free Caller Registry : Your Verification…"). Type it into `captcha`, then "verify and continue". The person who owns the inbox usually does this step.
2. **Step 1, `/fcr/Step1`: the business.** The verified email shows read-only as `secondcontactEmail` with a green check.
3. **Step 2: the numbers.** Up to 20 typed in one by one, or a file upload (xlsx or txt, one number per line, under 100 KB; template at `/fcr/public/files/sample-phone-list.xlsx`).
4. **Step 3: review and terms.** The `enableCheckbox` box certifies three things: you are the business that makes the calls (not a BPO, provider or third party registering someone else's numbers), the data is true, and the calls follow consumer-protection law. Then "Submit Your Registration".
5. **Thank-you page** with a Feedback ID. Each provider then emails the contact on its own.

## Page structure

- One page holds the whole wizard (jQuery-steps style). Every step's fields are in the DOM from the start: sections `#feedbackForm-p-0` to `-p-5`, with hidden ones at `offsetParent === null`. The URL changes per step (`/fcr/Step1`…), but nothing reloads.
- **Buttons, by visible text:**
  - "Continue To Next Step" (step 1);
  - "continue to final step" (step 2);
  - "Submit Your Registration" (step 3, a real submit).
  - Several "Back" and "Cancel" buttons exist; only the current step's are visible.
- **Step 1 field names:**
  - `companyName`, `companyAddressLine1`, `companyAddressLine2`, `city`, `state` (select), `zip`, `companyURL`;
  - `contactName`, `contactPhone`;
  - `category` (select, "Call purpose"), `callCount` (select), `explanation` (optional textarea about labelling complaints).
- **Step 2:** `phoneList[0]` to `phoneList[19]`. Only `[0]` is required. File upload goes in `enterpriseFile`.
- **Select options are matched by text:**
  - `state` uses full names ("Washington"), plus DC and the territories.
  - `category`: Attorney / Law, Financial Services, First Responder, Government, Health / Hospital, Informational, Pharmacy / Medical Supply, Political / Campaign, Real Estate, School / College, Survey / Research, Telemarketing.
  - `callCount`: "1 - 100", "101 - 500", "501 - 1000", "1,001 - 5000", "5,001 - 10,000", "10,001 - 50,000", "More than 50,000", "I don't know".

## Filling reliably

- **Text fields:** focus and select the input by `name`, then `type_text(value)`, then dispatch `change` and blur. Validation ("This field is required.", in red) runs on blur and change.
- **Selects:** find the option whose text matches, set `select.value`, then dispatch `input` and `change`.
- **Phone numbers:** exactly 10 digits, with no `+1`, spaces or punctuation. Use the same format for `contactPhone`.
- Check before moving on: list the visible fields' values, and look for visible `.error` / "This field is required." text.

```python
def fill_text(name, value):
    js(f'(() => {{ const e = document.querySelector("[name=\\"{name}\\"]"); e.scrollIntoView({{block: "center"}}); e.focus(); e.select(); }})()')
    type_text(value)
    js(f'(() => {{ const e = document.querySelector("[name=\\"{name}\\"]"); e.dispatchEvent(new Event("change", {{bubbles: true}})); e.blur(); }})()')

def pick(name, text):
    return js(f'(() => {{ const s = document.querySelector("select[name=\\"{name}\\"]"); const o = [...s.options].find(o => o.text.trim() === "{text}"); if (!o) return "missing"; s.value = o.value; s.dispatchEvent(new Event("input", {{bubbles: true}})); s.dispatchEvent(new Event("change", {{bubbles: true}})); s.blur(); return s.options[s.selectedIndex].text; }})()')
```

## Traps

- A password manager's icon can sit inside the "Business name" field. It is harmless; don't click it.
- Pressing "Continue" on a step with an empty required field only shows the red message, so check for errors after each step.
- The terms box and "Submit Your Registration" make a legal certification on the business's behalf. Leave both to the person, or get their explicit go-ahead.
