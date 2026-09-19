# San Francisco Assessor-Recorder — property owner lookup (recorder.sfgov.org + SF PIM)

Use this to answer "who owns / who co-owns <address> in San Francisco". Two public sites,
no login needed for the index. Together they give the parcel (block/lot) and every
recorded deed, deed of trust, reconveyance, lien and trust transfer since 1990.

## Step 1 — address → block/lot (SF Planning PIM)

`https://sfplanninggis.org/pim/?search=<url-encoded address>` loads straight into the
Property tab. Wait ~4 s after `wait_for_load()` (the report renders async).

- The "Report for" panel lists **Parcel (Block/Lot)** as `0539/018` and *all* addresses on
  the lot (a corner building has two street addresses on one lot).
- The **Assessor Summary** link is `javascript:void(0)`; click it via JS
  (`Array.from(document.querySelectorAll('a')).find(a=>a.innerText.trim()=='Assessor Summary').click()`)
  and read the modal from `document.body.innerText`. It shows assessed land/structure values,
  **Use Type** (e.g. `TIC Bldg`), **Units**, year built. The unit count can lag the number
  of recorded TIC interests — do not treat it as the owner count.
- **Assessor Recorded Documents** links to `https://recorder.sfgov.org/#!/disclaimer`.

## Step 2 — recorder index (Clearview Records Manager, Avenu; AngularJS SPA)

`https://recorder.sfgov.org/#!/disclaimer` → click **Agree** → `#!/simple` search form.
The form has Block and Lot fields at the bottom; a block/lot search returns every
document indexed against the parcel (1990 → indexed-through date shown on the disclaimer).

### Private API (call it from the page, not from curl)

The UI hits
`https://recorder.sfgov.org/SearchService/api/Search/GetSearchResults?<~90 params>`.
Requests need the `EncryptedKey` and `Password` headers that the app sets on Angular's
`$http` defaults after `GetSecureKey`. A bare `fetch()` returns `null`. Reuse the app's
`$http` instead:

```python
BASE = ("https://recorder.sfgov.org/SearchService/api/Search/GetSearchResults?"
        "DocumentClass=OfficialRecords&ProfileID=Public&IsBasicSearch=false&NameTypeID=0"
        "&MinRecordedDate=12%2F28%2F1989&MaxRecordedDate=12%2F31%2F2099"
        "&Block=0539&LowLot=018&Rows=100&StartRow=0")   # every other param may be empty

js("""
(function(){
  window.__res = null;
  var inj = angular.element(document.body).injector();
  var $http = inj.get('$http'), S = inj.get('SearchResultsService');
  S.GetSecureKey().get(function(k){
    S.SetHeaders(k.EncryptedKey, k.Password);
    $http.get(%s).then(function(r){ window.__res = JSON.stringify(r.data); },
                       function(e){ window.__res = 'ERR '+e.status; });
  });
  return 'started';
})()""" % json.dumps(BASE))
# poll js("window.__res") until non-null
```

Response: `{"ResultCount": N, "SearchResults": [...], "RefinementPanelData": {...}}`.

- `Rows` caps at **100** per call. Page with `StartRow=100`, `200`, …
- Each `SearchResults` row: `ID`, `PrimaryDocNumber`, `DocumentDate`, `FilingCode`
  (`<br/>`-joined titles), `Names` (`<br/>`-joined, **only the first (R) grantor and first
  (E) grantee** — everyone else is omitted).
- `RefinementPanelData.Names` is the facet of **every indexed name across the result set**
  (capped at 100 entries). `FilingCodes` and `Years` facets are also present.

### Getting the full party list for one document (no login)

Document detail (`search/GetDocumentDetails/<ID>`) and the legal-description endpoint
return all-null fields for guests, and the UI pops a login/register modal when you click a
row. Two free alternatives:

**A. Names endpoint (best — gives Grantor/Grantee role per name).** Use the row's internal
`ID` (not the document number):

```
GET https://recorder.sfgov.org/SearchService/api/search/GetNamesForPagination/<ID>/1/20
→ {"NamesForPagination":[{"NameTypeDesc":"Grantor","Fullname":"KILTY FAMILY TRUST 2018",...},
                         {"NameTypeDesc":"Grantee","Fullname":"STAHIHUT ISAAC",...}, ...]}
```

Same `$http` + `GetSecureKey` setup as above. `TotalNamesCount` tells you whether to page.

**B. Doc-number facet.** Run the search scoped to a single document number and read the
names facet (no roles, but no extra endpoint):

```
&DocNumberFrom=2024006653&DocNumberTo=2024006653
```

`RefinementPanelData.Names` then lists every grantor, grantee, trustee and lender on that
one instrument (spouses, co-borrowers, trust names). Fire these in parallel from one
`js()` call — ~40 doc-number queries complete in a few seconds.

### Name-scoped searches

- `LastName=<surname>` works (prefix match on the indexed "LAST FIRST" string, so
  `LastName=DEAN E` matches `DEAN E & NATALIE FOLEY 1997 TRUST`).
- `FirstName` combined with `LastName` returned 0 rows every time; don't rely on it.
- `SearchText` and `NameRefiners` are ignored by the API (they return the unfiltered set).

## How to reconstruct current owners (TIC / multi-owner parcels)

1. Pull all rows (block/lot, paged). Keep `DEED`, `RESCN/REVOC OF DEED`, `AFFIDAVIT OF DEATH`.
2. For every deed, fetch its doc-number facet to get all parties (the index row hides
   spouses and trustees).
3. Walk each chain grantor → grantee to the latest deed. A deed to/from the same person
   is usually a trust transfer or a TIC re-vesting on a group refinance day (many deeds
   recorded the same day with sequential numbers).
4. Cross-check with lender documents: group-loan `MODIF DEED OF TRUST` / `RECONVEYANCE`
   rows list every co-borrower, which is effectively the TIC roster on that date.
5. Recent `DEED OF TRUST` rows confirm who currently holds an interest and whether a
   spouse is on title (both names appear as trustors).

## Which unit does a TIC owner hold?

The index has no unit numbers, and the legal description is behind the paywall. Match the
deed date to a public sale listing instead: search `"<street address>" sold <month year>`
(Compass, Redfin, Zillow, Homes.com). A TIC sale shows up as `<address> Unit N` with the
close date equal to the deed's `DocumentDate`. Redfin also pins the same sale on the
parcel's other street address, so one sale can appear under two addresses.

## Traps

- **Indexing typos are common** and break name searches: `STAHIHUT` for STAHLHUT,
  `MICHAEL 3 ANZENBERGER` for MICHAEL J ANZENBERGER, `KITTY` for KILTY, `KLEEMAN`/`KLEEMANN`.
  Always search by block/lot first, then match names loosely.
- `(R)`/`(E)` in `Names` are the first grantor / first grantee only. "X → X" deeds are
  not errors; get the facet.
- Document images cost money and require registration. Everything above is free index data.
- The harness can silently re-attach to whichever tab the user has focused; the recorder
  tab's Angular state is lost if the tab navigates. `new_tab()` the disclaimer again and
  re-accept — the API calls need only the fresh secure key, not a prior UI search.
- Block/lot input: block is 4 chars (`0539`), lot is 3 (`018`). The API param for lot is
  `LowLot` (a `HighLot` exists for ranges).
