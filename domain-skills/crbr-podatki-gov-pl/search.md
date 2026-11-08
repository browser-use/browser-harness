# crbr.podatki.gov.pl — CRBR beneficial-owners search

Poland's Central Register of Beneficial Owners (Centralny Rejestr
Beneficjentów Rzeczywistych). Public search UI at
`https://crbr.podatki.gov.pl/adcrbr/#/wyszukaj` (Angular SPA, PrimeNG).

## Private API — skip the DOM entirely

The SPA calls one endpoint for entity search, and it works from plain
HTTP with `reCaptchaToken: "0"` (the captcha is not enforced server-side
as of 2026-06):

```python
import json
r = http_post(
    "https://crbr.podatki.gov.pl/adcrbr/api/wyszukajSpolke",
    json={
        "kontekstWyszukania": 1,          # 1 = entity search (by NIP/KRS/name)
        "nip": "5213107693",              # or "krs": "0000125836"
        "dataOd": "2026-06-06",           # date range of register entries
        "dataDo": "2026-06-06",
        "reCaptchaToken": "0",
        "czasPobraniaDanych": 1780703336220,  # Date.now() ms; not validated
    },
)
```

- `dataOd == dataDo == today` → the **current** entry only (this is what
  the portal's own "Wyszukaj" does by default).
- `dataOd = "2019-10-13"` (register start) → **full history**, one entry
  per `informacjeOSpolkachIBeneficjentach[]` item, oldest first. Each has
  `dataPoczatkuPrezentacji` / `dataKoncaPrezentacji` and
  `listaBeneficjentow[]`.
- Owner fields: `imiePierwsze`, `nazwisko`, `pesel` (null for foreigners),
  `dataUrodzenia` (set when pesel is null), `obywatelstwo` is an **array
  of `{kodKraju, nazwa}`**, `panstwoZamieszkania` an object of the same
  shape. Control description lives in
  `informacjeOUdzialeLubUprawnieniach[].uprWlasPosrednie` (free text).
- No entry for the NIP → `informacjeOSpolkachIBeneficjentach: []`, still
  HTTP 200.
- Wrong endpoint paths return Spring-style `{"status":404,...}` JSON —
  the backend is alive, your path is wrong.

## UI traps (if you must drive the SPA)

- The search form's radio groups disable competing inputs: filling the
  NIP textbox disables KRS/name/PESEL fields and enables "Wyszukaj".
- **CDP-dispatched compositor clicks on "Wyszukaj" do nothing** (no XHR
  fires). Click the button via JS instead:
  `[...document.querySelectorAll('button')].find(b => b.textContent.includes('Wyszukaj')).click()`.
- In a fresh headless Chromium the search XHR can fail with status 0
  even though the same request succeeds from curl — prefer the API.
- The filing app under the same origin (`api/slownik/*`, `api/address/*`)
  is a different module; the search bundle is lazy-loaded, so grepping
  `main.*.js` for the search endpoint finds nothing.
