# SVO — Bestellstrecke (Tarifrechner Strom/Gas)

Die Bestellstrecke auf svo.de ist ein eingebettetes **wlp.cloud Journey-Engine-Widget** (React im Shadow DOM), kein Eigenbau. Die Site selbst ist Statamic/Laravel (Livewire).

## URLs & Einstieg

- Strecke: `https://www.svo.de/service/tarifrechner-strom?step=1` … `?step=5` (analog `-gas`). `?step=N` spiegelt den Wizard-State.
- Prefill per URL-Parameter: `plz, ort, strasse, hnr, verbrauch, produkt, anrede, vorname, nachname, geburtsdatum, email, telefon, zaehlernummer, anbieter, wechselgrund, lieferbeginn, iban, zahlungsart, kundennummer`.
- Homepage-Widget: `<experience-engine-widget-price-finder tenant="svo">` mit `tab-1-consumptions="1500,2500,3500,4250"` (Strom) / `tab-2-consumptions="5000,12000,18000,25000"` (Gas).

## Journey-Definition (komplette Struktur ohne Klicken!)

`<experience-engine-journey journey-id=…>`: Strom `c7947c55-5964-49f4-b1a5-4445613a1eaf`, Gas `d1a58b59-3094-4e0c-bd51-0f3dbf20eef0`.

Die **gesamte Step-/Feld-/Text-/Logik-Struktur** als JSON (ohne die Strecke durchzuklicken):

```
GET https://experiences-bff.production.wlp.cloud/svo/customer_journey/journeys/{journey-id}
```

→ `journey.data.steps[].blocks[]` mit `settings.type` (`condensed-pricefinder`, `energy-product-choice`, `contract-change`, `meter-information`, `market-location`, `personal-information`, `contact`, `address`, `generic-request`, `payment`, `info-box`, `summary`) und `content` (alle Labels, Pflichtlogik, Konditionen `dependentResults`, Prefill-Keys).

## Private APIs (Gateway: `https://gw.production.wlp.cloud/svo`, KrakenD)

- `GET /api/v2/zips/{plz}?type=electricity|gas` — Regionalstruktur: `{zip, specificity: {electricity: "address"|"city"|"zip", gas: …}, address: {Ort: [Straßen…]}}`. Liefert auch für PLZ außerhalb des Kerngebiets Straßen (z. B. 10115 Berlin); ob lieferbar, entscheidet erst die Produktantwort.
- `GET /api/v2/products/prices?zip_code&usage&energy_type&vp_nr=10000&campaign=HOMEPAGE&city&street&house_number&product_codes=["PSE00008",…]` — Preise. Rechenweg: **netto** (`base_price_netto + usage × working_price_netto/100`), dann ×1,19, dann runden.
- `GET /api/v1/providers?energyType=electricity|gas` — ~1.300 Vorversorger `{id, name, codeNumber}` (BDEW-Nummer).
- `GET /encore_tools/market_communication/dates?energy=…` — `provider_change_dates.next_with_cancelation/.next_without_cancelation`, `relocation_dates.earliest_possible`.
- Submit: `POST https://experiences-bff.production.wlp.cloud/svo/customer_journey/submissions`.
- **Kein CORS-Header** auf gw.production.wlp.cloud → fremde Origins brauchen einen Proxy; `fetch` im Seitenkontext (js()) funktioniert.
- Direkter `http_get` auf die BFF gibt teils 406 → `Accept: application/json` Header nötig (im Seitenkontext fetchen ist am robustesten).

Produktcodes: Strom `PSE00008` (dynamisch), `PSE00004` (natürlich), `PSE00002` (Blühstrom); Gas `PSG00003` (natürlich), `PSG00002` (fest).

## Interaktion mit dem Widget (Shadow DOM)

- Alle Felder liegen im `shadowRoot` von `experience-engine-journey`. Feldnamen: `{block-uuid}.zipCode|city|street|houseNumber|usage|reason|previousProviderName|meter_number|maloId|salutation|firstName|lastName|dateOfBirth|email|phone|iban|…` → mit `input[name$=".feldname"]` selektieren.
- Koordinaten-Klicks gehen durch (compositor-level). Muster: per `js()` Element im shadowRoot finden → `scrollIntoView({block:"center"})` → Rect holen → `click_at_xy()`. **Immer im selben Aufruf** scrollen und frisch messen — Layout-Shifts machen alte Koordinaten wertlos.
- Comboboxen (Straße, Vorversorger): tippen → Optionsliste (`li`/`[role=option]`) erscheint → Option anklicken. Wert geht bei Fokusverlust ohne Auswahl wieder verloren.
- Natives Date-Input (`dateOfBirth`) nimmt `type_text` nicht an → nativen Setter nutzen:
  `Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value").set.call(el,"1990-01-01")` + `input`/`change` Events.
- Tarifkarten: „Jetzt bestellen"-Buttons per Text matchen; der mittlere/n-te Button entspricht der Kartenreihenfolge.
- MaLo-ID ist **Pflicht bei Anliegen „Anbieterwechsel"**, sonst optional. Zählernummer immer Pflicht (ohne Format-Check).
- Letzter Step: Submit heißt „Zahlungspflichtig bestellen" — in Tests NICHT klicken (echte Bestellung, keine Testumgebung auf www.svo.de; Testsystem: svo-test.de).

## Traps

- **react-aria-Checkboxen (generell auf react-aria-Seiten): `click_at_xy` togglet sie NICHT.** react-arias `usePress` reagiert nicht auf die von `Input.dispatchMouseEvent` synthetisierten Klicks (auch nicht mit `mouseMoved` davor oder `buttons=1`) — die Events kommen im DOM an (pointerdown/up/click, korrektes Target), aber es feuert kein Toggle/`change`. Native Buttons/Inputs derselben Seite funktionieren normal. Workarounds: `js('el.click()')` togglet zuverlässig; für echte Klick-Verifikation Playwright nutzen. Nicht als App-Bug fehldiagnostizieren — hat hier eine halbe Stunde Fehlersuche gekostet.
- Beim ersten Laden erscheint ein CleverPush-Push-Dialog und ein Eye-Able-Overlay (rechts) — beide stören Koordinaten-Klicks am Rand kaum, den Push-Dialog ignorieren oder wegklicken.
- Netzwerk-Mitschnitt: `drain_events()` verpasst schnelle Requests zwischen Aufrufen; zuverlässiger ist `performance.getEntriesByType("resource")` im Seitenkontext.
- CI-Theme des Widgets (alle `--ks-*` Design-Tokens inkl. SVO-Farben `#008df7/#001e62/#79d97c`): `https://journeyengine.production.wlp.cloud/journeys/svo.css`.
