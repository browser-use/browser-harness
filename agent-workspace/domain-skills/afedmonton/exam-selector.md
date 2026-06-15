# AF Edmonton — `/af/exam-selector/` exam catalog (Oncord CMS S8)

The Alliance Française d'Edmonton booking system runs on **Oncord CMS**.
`https://www.afedmonton.com/af/exam-selector/` is the public catalog
listing every upcoming TCF/TEF/DELF/Evalang exam session with structured
columns. **No auth, no cookies, no AJAX required to read it** — the HTML
is server-rendered with all session data inline.

> Note: `afedmonton.ca` and `afedmonton.com` are the same site; `.ca` is a
> redirect alias. Internal links and form actions normalise to `.com`.

## Endpoint

```
GET https://www.afedmonton.com/af/exam-selector/
```

Returns ~97KB HTML. The exam table lives at `table#s8-datatable1` with
columns:

| Col | Header             | Meaning                                            |
|-----|--------------------|----------------------------------------------------|
| 0   | Exam               | "TCF Canada - July 13", "TEF Canada - July 10", … |
| 1   | Schedules          | Written + Oral session dates and times             |
| 2   | Registration Dates | reg-open START — reg-close END (a `<br>` separator) |
| 3   | Location           | Always "Alliance Française of Edmonton - Kingsway" |
| 4   | Spots left         | Integer, "SOLD OUT!", or "—" before opening        |
| 5   | Price              | e.g. "$400.00"                                     |
| 6   | Bookings           | "Open" (clickable Book button) / "Closed" / "—"    |

Asterisk suffix on exam name (e.g. `July 13*`) marks afternoon sessions.

## The cap

The server returns at most **15 rows per request**. `s8-datatable1_rows`
beyond 15 is silently capped. Pagination via `s8-datatable1_start=15/30/…`
on a plain GET is **ignored**; the server-side state is set via the
filter AJAX (see below). For monitoring purposes the 15-row cap rarely
matters because AF Edmonton typically only has one season's batch active
at a time (e.g. 8 TCF + 7 TEF for July 2026, all in view).

## Filter AJAX (when you need >15 rows or specific filters)

The filter form posts to a generic Oncord AJAX gateway:

```
POST https://www.afedmonton.com/_public/Framework/HTTP/AJAX/server.php
Content-Type: application/x-www-form-urlencoded;charset=UTF-8
Referer: https://www.afedmonton.com/af/exam-selector/
X-Requested-With: XMLHttpRequest

_ajaxsenderid=
_ajaxevent=change
_ajaxeventid=exam_filter_ajax_event
_ajaxeventparameter=undefined
_ajaxjs=<js1>|<js2>
_ajaxcss=|<css>
_ajaxurl=/af/exam-selector/
s8-datatable1_rows=15
s8-datatable1_start=0
exam_type_filter_combobox=any|tcf|tef|delf|delf-adults|delf-junior|delf-prim|evalang
exam_year_filter_combobox=any|2026|2027|…
exam_location_filter_combobox=any
exam_filter_form=submit
exam_filter_form_csrf_token=<from initial GET>
```

Get `js1`, `js2`, `css` cache-bust IDs by regex-extracting from the prime
GET response:
```python
js1, js2 = re.findall(r"JavaScript/server\.php\?js=(\d+)", html)[:2]
css = re.search(r"css=(\d+)", html).group(1)
```

`csrf_token` comes from `input[name="exam_filter_form_csrf_token"]`.

**Response:** `text/plain` but the body is JS source. The new table HTML
is embedded as a string literal assigned to `.innerHTML`. Extract with:
```python
m = re.search(r"\.innerHTML\s*=\s*'((?:[^'\\]|\\.)*)'", resp_body, re.S)
html_frag = m.group(1).replace(r"\/","/").replace(r"\'","'").replace(r"\n","\n")
```

The combobox value names — observed valid choices for `exam_type_filter_combobox`:
- `any`, `tcf`, `tef`, `delf`, `delf-adults`, `delf-junior`, `delf-prim`, `evalang`

## Booking intake

Each row's "Book" button submits to:
```
POST /af/exam-selector/order/?exam_id=<N>
```
`exam_id` is a small integer (saw `exam_id=20` for one July 2026 TCF row).
Don't actually submit unless you intend to enter the checkout flow.

## Why this beats sitemap.xml for monitoring new spots

`sitemap.xml` only tells you a URL appeared / `<lastmod>` updated. It
doesn't tell you *whether spots are open*. The exam-selector table is
the authoritative per-session signal:

- **New row appearing** → admin scheduled a session (also surfaces in
  sitemap eventually, but here you see structured row data immediately).
- **Bookings column flipping `Closed` → `Open`** → registration window
  opened. This is the moment that matters.
- **Spots-left column flipping** `SOLD OUT!` → integer, or integer
  decreasing — actionable seat changes.
- **Row disappearing** → session pulled.

Suggested monitor schema (rows keyed by exam name):
```
key:        normalized exam name (e.g. "tcf-canada-july-13")
fields:     spots_left, booking_status, reg_open_ts, reg_close_ts, price, schedule
events:     NEW_ROW | BOOKING_OPEN | SPOTS_DELTA | SOLD_OUT | GONE
```

## Other endpoints under `/_public/`

Discovered but not deeply probed:

- `/_public/Framework/Assets/JavaScript/server.php?js=<hash>` — bundled JS
- `/_public/Framework/Assets/CSS/server.php?css=<hash>` — bundled CSS
- `/_public/Framework/I18N/Addresses/address_layouts.json` — JSON of
  address form layouts per country. The only true JSON endpoint exposed.
- `/_public/Components/Website/_keepalive` — session keepalive ping
- `/_public/Components/Website/t.php` — analytics tracker
- `/_public/Controls/Data/DataControlABC/datacontrol.php` — generic data
  control AJAX endpoint (Oncord internal)
- `/_public/Controls/Forms/DialogBox/dialogbox.php` — dialog control

## Anti-traps

- **`/af/exam-selector/?exam_type_filter_combobox=tcf` does not filter
  via GET.** The combobox values only take effect via POST with CSRF.
- **`s8-datatable1_rows` > 15 is silently capped.** Don't bother asking
  for more — paginate via `s8-datatable1_start`.
- **Schedule column has embedded `<br>` and "▸"**. Be lenient parsing.
- **Registration Dates uses `-` separator**, but the range may also
  contain `-` in the date text — split on `\s+-\s+` not just `-`.
- **`*` suffix** on exam name distinguishes afternoon sessions; don't
  treat as wildcard or trim it.
- **`SOLD OUT!`** is a literal string (with exclamation mark) in the
  Spots column, not "Sold Out" or "0".

## Minimal scraper

```python
import re, httpx
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127.0.0.0 Safari/537.36"

def fetch_sessions():
    with httpx.Client(headers={"User-Agent": UA}, timeout=20) as c:
        r = c.get("https://www.afedmonton.com/af/exam-selector/")
    s = BeautifulSoup(r.text, "html.parser")
    out = []
    for tr in s.select("table tr"):
        if tr.find("th"):
            continue
        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if not cells or len(cells) < 7:
            continue
        name, schedule, regwin, location, spots, price, booking = cells[:7]
        reg_start, reg_end = (None, None)
        m = re.match(r"(.+?)\s+-\s+(.+)", regwin)
        if m:
            reg_start, reg_end = m.group(1).strip(), m.group(2).strip()
        out.append({
            "name": name, "schedule": schedule,
            "reg_start": reg_start, "reg_end": reg_end,
            "location": location, "spots_left": spots,
            "price": price, "booking": booking,
        })
    return out
```
