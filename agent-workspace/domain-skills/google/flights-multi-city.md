# Google Flights — deep-link any search via `tfs` (incl. multi-city)

Use a search URL for routes that fit the schema below.
Use the visible controls for filters that the schema does not cover:

```
https://www.google.com/travel/flights?tfs=<base64 protobuf>&hl=en&curr=USD
```

`tfs` contains a serialized protobuf encoded as URL-safe base64 without padding.

## Schema

```
Query {
  repeated Leg legs   = 3;
  repeated int32 pax  = 8;   // one entry per traveler: 1=adult 2=child 3=infant-in-seat 4=infant-on-lap
  int32 seat          = 9;   // 1=economy 2=premium economy 3=business 4=first
  int32 trip          = 19;  // 1=round trip 2=one way 3=multi-city
}
Leg {
  string date  = 2;          // "YYYY-MM-DD"
  Airport from = 13;
  Airport to   = 14;
}
Airport { string code = 2; }  // IATA airport OR city code
```

Multi-city = `trip=3` plus one `Leg` per segment, in order. Open-jaw is just a
2-leg multi-city where leg2's origin != leg1's destination.

Minimal encoder (no protobuf dep):

```python
import base64
def vint(n):
    o=b""
    while True:
        b_=n&0x7F; n>>=7; o+=bytes([b_|(0x80 if n else 0)])
        if not n: return o
def s(f,v): v=v.encode() if isinstance(v,str) else v; return vint(f<<3|2)+vint(len(v))+v
def v(f,n): return vint(f<<3)+vint(n)
def leg(d,a,b): return s(2,d)+s(13,s(2,a))+s(14,s(2,b))
def tfs(legs, seat=1, trip=3, passengers=(1,)):
    passengers = tuple(passengers)
    if seat not in (1, 2, 3, 4) or trip not in (1, 2, 3):
        raise ValueError("Invalid seat or trip code")
    if not passengers or any(p not in (1, 2, 3, 4) for p in passengers):
        raise ValueError("Use passenger codes 1, 2, 3, or 4")
    body = b"".join(s(3, leg(*item)) for item in legs)
    body += b"".join(v(8, p) for p in passengers) + v(9, seat) + v(19, trip)
    return base64.urlsafe_b64encode(body).decode().rstrip("=")

tfs([("2027-03-10","JFK","LHR"),("2027-03-24","CDG","JFK")])
```

The examples append `&hl=en&curr=USD` for English and US dollars.
Use the user's requested locale and currency when they differ.
The extraction example below assumes US dollars.

Verify the URL parsed correctly by reading `page_info()["title"]` — it echoes
`"<Origin> to <Destination> | Google Flights"`. A malformed `tfs` silently falls
back to a blank search form.

## Reading results

No login needed. Results render ~5-8s after `wait_for_load()`; poll rather than
assuming. Every row is an `<li>`; the whole itinerary is in `li.innerText`:

```python
js("""(()=>{const o=[];document.querySelectorAll('li').forEach(l=>{
  const t=l.innerText; if(t&&/\\$\\d/.test(t)) o.push(t.replace(/\\n+/g,' | '));
});return JSON.stringify(o)})()""")
```

This returns candidate text, including possible nested detail rows.
Inspect the visible flight cards before counting or quoting results.
Do not discard rows by text length because valid itineraries can contain long descriptions.

## Multi-city flow quirks

- The first results page lists **leg 1 only**. The price on each row is labelled
  `entire trip` and is Google's *estimate* of the cheapest complete itinerary
  containing that leg.
- Clicking a leg-1 row navigates (title flips to `"<Leg2 origin> to <Leg2 dest>"`)
  and shows the leg-2 options **compatible with that leg 1** — usually restricted
  to the same alliance, so the set is small (3-6 rows).
- **The leg-1 `entire trip` estimate can be below any actually selectable total.**
  Observed a leg-1 badge of `$1,073` whose cheapest real leg-2 pairing was
  `$1,107`. Always click through and read the leg-2 page for a bookable number.
- After clicking through, the `<li>` list needs another ~6s; an immediate query
  returns `COUNT 0`. Re-query rather than concluding there are no flights.
- `history.back()` returns to the leg-1 list with state intact.

## Sorting / expanding

The observed multi-city pages had no `Show more flights` button.
Check the current page for additional results before treating the visible list as complete.
To sort:

```python
js("[...document.querySelectorAll('button,div[role=button]')].find(x=>/Sorted by/i.test(x.innerText))?.click()")
# then
js("[...document.querySelectorAll('[role=menuitem],li')].find(x=>x.innerText.trim()==='Price')?.click()")
```

Verify the visible sort selection after each click. If the control is absent, wait for rendering and retry.
Menu options: Top flights, Price, Departure time, Arrival time, Duration, Emissions.

## Cabin comparison

Re-request the same legs with `seat=2/3/4` rather than touching the cabin
dropdown. Mixed-cabin itineraries are labelled in-row
(`Economy + Premium Economy`, `Business Class + Economy`) and are frequently the
cheapest hit in a premium search — read that suffix before quoting a fare.

## Multi-city vs. two one-ways

Worth running both; they differ a lot. Same dates/route sampled 2026-07-25:
multi-city open-jaw `$1,107` vs. two separate one-ways `$640 + $844 = $1,484`.
Multi-city won by ~25%. Encode the one-ways with `trip=2` and a single leg.

## Traps

- Chrome's CDP consent dialog can block the harness against the user's main
  profile. Google Flights needs no session state, so launching a throwaway Chrome
  with `--user-data-dir=<tmp> --remote-debugging-port=<port>` and pointing
  `BU_CDP_WS` at it is a clean workaround.
- Verify the displayed passenger count and total before quoting a fare. Check bag fees separately.
