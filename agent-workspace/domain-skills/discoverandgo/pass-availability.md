# Discover & Go — library museum passes (`<library>.discoverandgo.net`)

Quipu ePASS white-label sites, e.g. `https://sfpl.discoverandgo.net/`. Everything sits behind a library-card login (barcode + PIN). Stop and let the user sign in; never type card numbers from a screenshot.

## Do this first

**After the user signs in, call the site's own JSON API through its request helper instead of clicking the calendar.** The page exposes `ePASS` (config) and `ePASSAPIRequest(url, params, callback)`, which adds the CSRF token and the `x-epass-*` headers the server requires. A plain `fetch` of `epass_server.php` returns `{"status":"Failed","message":"Not valid library"}`.

```python
# wrap the callback-style helper in a Promise; js() awaits promises
r = js("""new Promise(res => {
  ePASSAPIRequest(ePASS.apiURL, {dataType:'json', method:'AttractionsSearchInit',
    functionFile:'Attractions', date:'All', language:ePASS.language}, resp => res(JSON.stringify(resp)));
})""")
```

## Methods (all GET `epass_server.php`, params below plus `dataType=json`, `functionFile=Attractions`, `language`)

| `method` | Extra params | Returns |
|---|---|---|
| `AttractionsSearchInit` | `date=All` | `attractionNames[]` → `{attractionID, name}` |
| `ePASS_Search` | `searchType=Attractions`, `dateSelected=None`, `limits=''` | Every attraction with `city`, `patronLimitQuantity/Frequency`, `reservationsUnavailableMessage`, and `offerList[]` (`offerID`, `offerTitle`, `libraryQuantity`, `dates[]` = the offer's valid open days, `date` = first reservable day) |
| `ePASS_Search` | `searchType=Offers`, `dateSelected=YYYY-MM-DD` or `firstAvailable` | Only attractions with a reservable pass on that date |
| `OfferDatesAvailability` | `year`, `month`, optional `attractionID`, `offerID` | `dates[]` of reservable days across the whole display window (`monthsToDisplay`, 3 for SFPL), not just the month passed |

`attractionList` comes back as a list or a dict keyed by position; handle both. `ajaxStatus:"success"` plus `status:"Passed"` means OK. `blockService:"Y"` means the session died; reload the page and ask the user to sign in again.

## Traps

- **An offer's `dates[]` is the open-day calendar, not availability.** Use `OfferDatesAvailability` with `attractionID` for what can actually be reserved.
- **Sold-out attractions have `attractionOffersCount: 0`** and `reservationsUnavailableMessage` = "All reservations have been reserved at this time. Check back on the 1st of each month." Passes are released monthly on the 1st.
- Reservation limits: two active reservations per card; unused passes count against it. Do not reserve without explicit instruction.
- The listing page after login is `Discover & Go - Offer Listing` for one date; the `All Attractions` link switches to `Attraction Listing` (every attraction, `#ePASSAttractionDiv<N>` blocks).
