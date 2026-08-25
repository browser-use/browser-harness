# dokument24.dk — document creation wizards

Danish legal-document SaaS. Logged-in account area is under `/konto/...`. Documents are created
through multi-step wizards and delivered by email on order.

## URL patterns
- Catalog: `/konto/opret-dokument` with category pages `/konto/opret-dokument/privatdokumenter`
  and `/konto/opret-dokument/erhvervsdokumenter`.
- Wizards live at `/erhverv/<group>/<name>/lav` (e.g. `/erhverv/aftaler/nda/lav`) and equivalents
  for private docs. Some docs live under odd paths (e.g. `/artikler/guides-medarbejdere/fratraedelsesaftale/lav`).
- Every wizard step has its own URL: `…/lav/<PascalCasePrefix>.<StepName>` (e.g.
  `AgreementNda.Parties.1`, `EmployeeEmploymentContract.SalaryAmount`). You can `goto_url()` a step
  directly to correct an earlier answer. Receipt page is `…/lav/kvittering`.
- URLs sometimes carry a `#fragment` — compare with `url.split('#')[0]`.

## Wizard mechanics
- Card buttons on category pages ("Lav …") are `<button>` without href — click by text. Several
  cards share the text "Lav dokument"; disambiguate via the card title in the surrounding DOM.
- Drafts are saved server-side automatically ("Gemt" badge) — you can leave and resume; answers
  persist across navigation and sessions.
- Steps advance with a "Videre ›" button; validation messages ("Udfyld venligst for at fortsætte")
  appear inline and the URL does not change when blocked.
- Inputs are plain `input[name=…]` / `select[name=…]` / radio groups (`input[name=Type]` etc.).
  Field ids look like `AgreementNda$Parties$1$Name`. Free text is accepted for company names
  (no forced CVR lookup).
- Amount fields (`type=number`) must get PLAIN digits ("10000", not "DKK 10.000,-"); many default
  to `0` which counts as unfilled.
- Date pickers are three `<select>`s (`X_Day`, `X_Month`, `X_Year`) prefilled with today.
- The final info step requires an `ExplicitConsent` checkbox (contact consent) — mandatory, the
  wizard will not proceed without it. **It is often pre-checked on resume: clicking it again
  toggles it OFF.** Only click when unchecked.
- Optional "additional signers" steps can be skipped by just clicking Videre.
- Some steps replace "Videre" with a "Gå til opsummering" button.

## Ordering / payment
- Subscription accounts (e.g. "Tryg24 Erhverv") get a banner "Der er 100% rabat på dit køb" and the
  Buy step shows "Din samlede pris er kun 0 kr." — no payment fields at all for included documents.
- Buy step checkboxes: `AcceptConditions` (required), `AcceptNewsletter` (optional marketing —
  leave unchecked unless asked). Order button text: **"Få Tilsendt"**.
- Receipt shows "Godkendt", an order number `DK…`, and the delivery email. The document arrives by
  email within ~2 minutes; it also appears under `/konto/mine-dokumenter` ("Købte dokumenter").
- Paid docs use "Køb …" buttons linking to `/konto/opret-dokument/koeb?product=…` — do not touch
  these when the goal is free documents only.

## Traps
- `capture_screenshot` (CDP `Page.captureScreenshot`) can time out right after wizard navigations;
  DOM text dumps are reliable and sufficient.
- Standard-data lists that include a `Name` fill will overwrite the OTHER party's name if reused on
  the counterparty's info step — keep separate action lists per party.
- "Normalpris … kr." struck-through with "0,00 kr." means included/free; a card showing a plain
  price (e.g. "255,00 kr." with "Normalpris 295,00 kr.") is still PAID despite the discount look.
