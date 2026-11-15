# NHTSA vPIC - Decode a VIN, then Its Recalls and Complaints (official APIs)

Field-tested against vpic.nhtsa.dot.gov and api.nhtsa.gov on 2026-11-03 using a Browser Use cloud browser (logged out) and plain HTTP (Python urllib). About 190 browser API calls and 70 plain HTTP calls, mostly at 0.5 s spacing: no 429, no CAPTCHA, no block.

robots.txt (checked 2026-11-03): vpic.nhtsa.dot.gov/robots.txt is HTTP 404 (no rules); api.nhtsa.gov has none (its gateway answers `/robots.txt` with 403 `{"message":"Missing Authentication Token"}`) and this skill uses its documented endpoints under the official-API exception (NHTSA's "NHTSA Datasets and APIs" page, https://www.nhtsa.gov/nhtsa-datasets-and-apis, lists them, no key).

## Quick summary

- **No scraping.** Four public JSON endpoints, no key, no cookies:
  - `GET vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/<VIN>?format=json` - one flat record (about 150 string fields): make, model, year, series, trim, body, engine, plant, `ErrorCode`.
  - `GET api.nhtsa.gov/recalls/recallsByVehicle?make=&model=&modelYear=` - recall campaigns.
  - `GET api.nhtsa.gov/complaints/complaintsByVehicle?make=&model=&modelYear=` - owner complaints (ODI).
  - `GET api.nhtsa.gov/products/vehicle/models?modelYear=&make=&issueType=c&max=1000` - the model names those two endpoints know.
- **The vPIC model name is not always the recalls/complaints name.** 2003 Accord: `Accord` works for both. 2013 F-150: recalls are under `F-150`, complaints only under `F-150 REGULAR CAB` / `F-150 SUPER CREW` / `F-150 SUPERCAB` (`F-150` gives HTTP 400). 2014 Silverado 1500: 14 recalls under `SILVERADO` plus 6 different ones under `SILVERADO 1500`; complaints only under `SILVERADO 1500`. The blocks query the vPIC model plus every `MODEL <variant>` name (narrowed by vPIC `Series` when it matches) and merge by campaign number / ODI number.
- **HTTP 400 with `{"count":0,"results":[]}` means "no records under that name"**, not a bad request. Its `message` still says "Results returned successfully".
- **Recall dates are DD/MM/YYYY, complaint dates are MM/DD/YYYY.** `ReportReceivedDate` `24/05/2016` (16V345000) vs `dateComplaintFiled` `06/27/2026`.
- **Complaint lists are big:** 2,796 complaints = 2.7 MB, about 7 s, for the 2013 F-150. The browser block starts the fetch and polls, because `js()` gives up after 5 s.
- **Browser:** `fetch()` from a vpic.nhtsa.dot.gov tab. vPIC sends `access-control-allow-origin: *` and api.nhtsa.gov echoes the caller's origin, so both hosts answer from that tab. **Plain HTTP** works too, with the same results.

## What works

### 1. VIN -> decode -> recalls -> complaints (browser)

Self-contained. `on_vpic_tab()` opens `https://vpic.nhtsa.dot.gov/api/` (vPIC's own API page) once and later calls reuse the tab. `fetch_json()` returns `(status, JSON)` for 200 and 400, backs off on 429/5xx and otherwise raises, so a failure never looks like "no recalls". Calls are serial with a 0.5 s pause.

```python
import collections, json, os, tempfile, time, urllib.parse
from datetime import datetime

VINS = ["1HGCM82633A004352", "1FTFW1ET9DFC10312", "1GCVKREC6EZ123456"]  # 2003 Accord, 2013 F-150, 2014 Silverado 1500

VPIC = "https://vpic.nhtsa.dot.gov/api/vehicles/"
API = "https://api.nhtsa.gov/"
PAUSE = 0.5  # seconds between calls; keep calls serial

def on_vpic_tab():
    """fetch() runs from a logged-out vpic.nhtsa.dot.gov tab. Both API hosts allow that origin (CORS). Reuse the tab if already there."""
    try:
        if js("location.origin") == "https://vpic.nhtsa.dot.gov":
            return
    except Exception:
        pass
    new_tab("https://vpic.nhtsa.dot.gov/api/")  # vPIC's own API docs page
    wait_for_load()
    if js("location.origin") != "https://vpic.nhtsa.dot.gov":
        raise RuntimeError(f"tab landed on {js('location.href')}: stop and tell the user; do not retry around it")

# js() gives up after a few seconds and complaint lists reach several MB, so start the fetch, then poll for it.
START_JS = """(() => { window.__nh = window.__nh || {}; const id = String(Math.random()).slice(2); window.__nh[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__nh[id] = {status: r.status, text: await r.text()}; })
    .catch(e => { window.__nh[id] = {status: 0, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__nh[%s]; if (v) delete window.__nh[%s]; return v; })()"""

def fetch_json(url, tries=4, timeout=90):
    """GET url from inside the tab. Returns (status, parsed JSON). Backs off on 429/5xx; raises on anything else unexpected."""
    for attempt in range(tries):
        rid = json.dumps(js(START_JS % json.dumps(url)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"{url}: no answer after {timeout}s")
            time.sleep(0.5)
        time.sleep(PAUSE)
        if r["status"] in (200, 400):
            return r["status"], json.loads(r["text"])
        if r["status"] not in (0, 429, 500, 502, 503, 504) or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {r['status']} {r['text'][:200]}; stopping")
        time.sleep(5 * 2 ** attempt)

def decode_vin(vin, model_year=None):
    """vPIC flat decode: one dict of ~150 string fields. ErrorCode '0' means a clean decode."""
    url = VPIC + "DecodeVinValues/" + urllib.parse.quote(vin) + "?format=json" + (f"&modelyear={model_year}" if model_year else "")
    status, d = fetch_json(url)
    if status != 200:
        raise RuntimeError(f"{vin}: vPIC HTTP {status}")
    return d["Results"][0]

def api_list(path, **params):
    """api.nhtsa.gov list call. HTTP 400 with an empty list means 'no records under that name', not an error."""
    status, d = fetch_json(API + path + "?" + urllib.parse.urlencode(params))
    if status == 400 and not d.get("results"):
        return None
    if status != 200:
        raise RuntimeError(f"{path} {params}: HTTP {status} {d}")
    return d["results"]

def product_names(make, model, year, series=""):
    """Names to query on api.nhtsa.gov for a vPIC make/model/year: the vPIC model itself plus the API's
    'MODEL <variant>' names for that year (F-150 -> F-150 SUPER CREW, ...), narrowed to the vPIC series when one matches."""
    base = model.upper()
    listed = {m["model"].upper() for m in api_list("products/vehicle/models", modelYear=year, make=make, issueType="c", max=1000) or []}
    variants = sorted(m for m in listed if m.startswith(base + " "))
    if series and any(series.upper() in m.split() for m in variants):
        variants = [m for m in variants if series.upper() in m.split()]
    return [base] + [m for m in variants if m != base]

def _date(s, fmt):
    try:
        return datetime.strptime(s, fmt)
    except (TypeError, ValueError):
        return datetime.min

def vehicle_report(vin):
    v = decode_vin(vin)
    make, model, year, series = v["Make"], v["Model"], v["ModelYear"], v["Series"]
    if not (make and model and year):
        return {"vin": vin, "decode": v, "error": v["ErrorText"]}
    names = product_names(make, model, year, series)
    recalls, complaints, hits = {}, {}, {}
    for name in names:
        r = api_list("recalls/recallsByVehicle", make=make, model=name, modelYear=year)
        c = api_list("complaints/complaintsByVehicle", make=make, model=name, modelYear=year)
        hits[name] = (None if r is None else len(r), None if c is None else len(c))
        for x in r or []:
            recalls.setdefault(x["NHTSACampaignNumber"], x)
        for x in c or []:
            complaints.setdefault(x["odiNumber"], x)
    return {"vin": vin, "decode": v, "names": hits,
            "recalls": sorted(recalls.values(), key=lambda x: _date(x["ReportReceivedDate"], "%d/%m/%Y"), reverse=True),
            "complaints": sorted(complaints.values(), key=lambda x: _date(x["dateComplaintFiled"], "%m/%d/%Y"), reverse=True)}

on_vpic_tab()
for vin in VINS:
    rep = vehicle_report(vin)
    v = rep["decode"]
    print(f"\n{vin}: {v['ModelYear']} {v['Make']} {v['Model']} {v['Series']} {v['Trim']} | {v['BodyClass']} | "
          f"{v['DisplacementL'][:4]} L {v['EngineCylinders']} cyl {v['FuelTypePrimary']} | {v['DriveType']} | "
          f"plant {v['PlantCity']}, {v['PlantCountry']} | ErrorCode {v['ErrorCode']}")
    print("  names queried (recalls, complaints; None = HTTP 400 no records):", rep["names"])
    print(f"  recalls: {len(rep['recalls'])}")
    for x in rep["recalls"][:4]:
        flags = (" PARK IT" if x.get("parkIt") else "") + (" PARK OUTSIDE" if x.get("parkOutSide") else "")
        print(f"    {x['NHTSACampaignNumber']} {x['ReportReceivedDate']} {x['Component'][:60]}{flags} | {x['Summary'][:60]}")
    cs = rep["complaints"]
    comp = collections.Counter(p.strip() for c in cs for p in c["components"].split(","))
    print(f"  complaints: {len(cs)} | crash {sum(c['crash'] for c in cs)} fire {sum(c['fire'] for c in cs)} "
          f"injuries {sum(c['numberOfInjuries'] for c in cs)} deaths {sum(c['numberOfDeaths'] for c in cs)}")
    print("  top components:", comp.most_common(4))
    for c in cs[:2]:
        print(f"    {c['dateComplaintFiled']} ODI {c['odiNumber']} {c['components']} | {c['summary'][:90]}")
    out = os.path.join(tempfile.gettempdir(), f"nhtsa_{vin}.json")
    with open(out, "w") as f:
        json.dump(rep, f)
    print("  saved full report:", os.path.basename(out), "in tempfile.gettempdir()")
```

Output (from the run on 2026-11-03):

```text
1HGCM82633A004352: 2003 HONDA Accord  EX-V6 | Coupe | 2.99 L 6 cyl Gasoline |  | plant MARYSVILLE, UNITED STATES (USA) | ErrorCode 0
  names queried (recalls, complaints; None = HTTP 400 no records): {'ACCORD': (24, 2013)}
  recalls: 24
    19E068000 10/10/2019 VEHICLE SPEED CONTROL:ACCELERATOR PEDAL | Dorman Products, Inc.  (Dorman) is recalling certain Acceler
    19V499000 27/06/2019 AIR BAGS:FRONTAL:DRIVER SIDE:INFLATOR MODULE | Honda (American Honda Motor Co.) is recalling certain 2003 A
    19V501000 27/06/2019 AIR BAGS:FRONTAL:PASSENGER SIDE:INFLATOR MODULE | Honda (American Honda Motor Co.) is recalling certain 2003-2
    19V182000 06/03/2019 AIR BAGS:FRONTAL:DRIVER SIDE:INFLATOR MODULE | Honda (American Honda Motor Co.) is recalling specific 2003 
  complaints: 2013 | crash 158 fire 19 injuries 157 deaths 1
  top components: [('POWER TRAIN', 926), ('AIR BAGS', 324), ('SERVICE BRAKES', 175), ('HYDRAULIC', 146)]
    06/27/2026 ODI 11746949 AIR BAGS | The vehicle was rear-ended on I-5 in Seattle Washington.  The impact drove the subject car
    05/26/2026 ODI 11740104 AIR BAGS | The contact owns a 2003 Honda Accord. The contact stated while attempting to start the veh
  saved full report: nhtsa_1HGCM82633A004352.json in tempfile.gettempdir()

1FTFW1ET9DFC10312: 2013 FORD F-150   | Pickup | 3.5 L 6 cyl Gasoline | 4WD/4-Wheel Drive/4x4 | plant DEARBORN, UNITED STATES (USA) | ErrorCode 0
  names queried (recalls, complaints; None = HTTP 400 no records): {'F-150': (3, None), 'F-150 REGULAR CAB': (None, 2796), 'F-150 SUPER CREW': (None, 2796), 'F-150 SUPERCAB': (None, 2796)}
  recalls: 3
    19V433000 10/06/2019 POWER TRAIN:AUTOMATIC TRANSMISSION | Ford Motor Company (Ford) is recalling certain 2013 F-150 ve
    19V075000 11/02/2019 POWER TRAIN:AUTOMATIC TRANSMISSION:CONTROL MODULE (TCM/PCM/T | Ford Motor Company (Ford) is recalling certain 2011-2013 F-1
    16V345000 24/05/2016 SERVICE BRAKES, HYDRAULIC:FLUID | Ford Motor Company (Ford) is recalling certain model year 20
  complaints: 2796 | crash 74 fire 31 injuries 60 deaths 1
  top components: [('POWER TRAIN', 1212), ('ENGINE', 531), ('SERVICE BRAKES', 354), ('ELECTRICAL SYSTEM', 306)]
    08/07/2025 ODI 11679124 ENGINE | Truck has 91,200 miles and  was well maintained.  Truck has a loud rattle (like rocks in a
    08/07/2025 ODI 11679190 POWER TRAIN | At about [XXX] [XXX], Tuesday, I was N/B on [XXX] , my speed was approximately 60 mph. All
  saved full report: nhtsa_1FTFW1ET9DFC10312.json in tempfile.gettempdir()

1GCVKREC6EZ123456: 2014 CHEVROLET Silverado 1500 LT | Pickup | 5.3 L 8 cyl Gasoline | 4WD/4-Wheel Drive/4x4 | plant ROANOKE, UNITED STATES (USA) | ErrorCode 0
  names queried (recalls, complaints; None = HTTP 400 no records): {'SILVERADO': (14, None), 'SILVERADO 1500': (6, 1561)}
  recalls: 20
    21V245000 08/04/2021 SEAT BELTS:FRONT | General Motors, LLC (GM) is recalling certain 2014-2016 Chev
    19V761000 24/10/2019 SERVICE BRAKES, HYDRAULIC:ANTILOCK/TRACTION CONTROL/ELECTRON | General Motors LLC (GM) is recalling certain 2015-2020 Chevr
    19V645000 06/09/2019 SERVICE BRAKES, HYDRAULIC:POWER ASSIST:VACUUM | General Motors LLC (GM) is recalling certain 2015-2017 Cadil
    17V437000 10/07/2017 AIR BAGS:FRONTAL | General Motors LLC (GM) is recalling certain model year 2014
  complaints: 1561 | crash 75 fire 18 injuries 41 deaths 4
  top components: [('STEERING', 427), ('ELECTRICAL SYSTEM', 361), ('SERVICE BRAKES', 290), ('ENGINE', 207)]
    10/23/2026 ODI 11773234 SEAT BELTS | The contact owns a 2014 Chevrolet Silverado 1500. The contact stated that the front driver
    09/23/2026 ODI 11766505 STEERING | The contact owns a 2014 Chevrolet Silverado 1500. The contact stated that while driving 75
  saved full report: nhtsa_1GCVKREC6EZ123456.json in tempfile.gettempdir()
```

### 2. Same flow over plain HTTP, batch decode, units affected (no browser)

Python standard library only, truthful User-Agent. `DecodeVINValuesBatch` decodes up to 50 VINs in one POST (`data` = `VIN;VIN,year;...`). Units affected is only on `recalls/campaignNumber`, so the block reads it for each vehicle's newest recall.

```python
import json, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime

VINS = ["1HGCM82633A004352", "1FTFW1ET9DFC10312", "1GCVKREC6EZ123456", "1HGCM82633A004353"]  # last one: bad check digit

UA = {"User-Agent": "browser-harness-skill/1.0 (Python urllib)"}
VPIC = "https://vpic.nhtsa.dot.gov/api/vehicles/"
API = "https://api.nhtsa.gov/"
PAUSE = 0.5  # seconds between calls; keep calls serial

def call(url, data=None, tries=4):
    """GET (or form POST) -> (status, JSON). 400 is returned, not raised (api.nhtsa.gov uses it for 'no records').
    Backs off on 429/5xx, raises on anything else."""
    for attempt in range(tries):
        req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode() if data else None, headers=UA)
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                status, body = r.status, r.read()
        except urllib.error.HTTPError as e:
            status, body = e.code, e.read()
        time.sleep(PAUSE)
        if status in (200, 400):
            return status, json.loads(body)
        if status not in (429, 500, 502, 503, 504) or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {status} {body[:200]!r}; stopping")
        time.sleep(5 * 2 ** attempt)

def decode_batch(vins):
    """Up to 50 VINs per POST. Each item is 'VIN' or 'VIN,modelYear'. Returns the flat decode dicts in input order."""
    status, d = call(VPIC + "DecodeVINValuesBatch/", {"format": "json", "data": ";".join(vins)})
    if status != 200:
        raise RuntimeError(f"batch decode: HTTP {status} {d}")
    return d["Results"]

def api_list(path, **params):
    status, d = call(API + path + "?" + urllib.parse.urlencode(params))
    if status == 400 and not d.get("results"):
        return None  # no records under that name
    if status != 200:
        raise RuntimeError(f"{path} {params}: HTTP {status} {d}")
    return d["results"]

def product_names(make, model, year, series=""):
    base = model.upper()
    listed = {m["model"].upper() for m in api_list("products/vehicle/models", modelYear=year, make=make, issueType="c", max=1000) or []}
    variants = sorted(m for m in listed if m.startswith(base + " "))
    if series and any(series.upper() in m.split() for m in variants):
        variants = [m for m in variants if series.upper() in m.split()]
    return [base] + [m for m in variants if m != base]

for v in decode_batch(VINS):
    print(f"\n{v['VIN']}: {v['ModelYear']} {v['Make']} {v['Model']} {v['Series']} | ErrorCode {v['ErrorCode']}: {v['ErrorText'][:70]}")
    if v["ErrorCode"] != "0":
        print("  not a clean decode: check the VIN before trusting the make/model/year above")
        continue
    recalls, complaints = {}, {}
    for name in product_names(v["Make"], v["Model"], v["ModelYear"], v["Series"]):
        for x in api_list("recalls/recallsByVehicle", make=v["Make"], model=name, modelYear=v["ModelYear"]) or []:
            recalls.setdefault(x["NHTSACampaignNumber"], x)
        for x in api_list("complaints/complaintsByVehicle", make=v["Make"], model=name, modelYear=v["ModelYear"]) or []:
            complaints.setdefault(x["odiNumber"], x)
    print(f"  recalls {len(recalls)} | complaints {len(complaints)} "
          f"(crash {sum(c['crash'] for c in complaints.values())}, fire {sum(c['fire'] for c in complaints.values())})")
    # Units affected (PotentialNumberofUnitsAffected) is only on the per-campaign endpoint.
    newest = sorted(recalls.values(), key=lambda x: datetime.strptime(x["ReportReceivedDate"], "%d/%m/%Y"))  # recall dates are DD/MM/YYYY
    camp = newest[-1]["NHTSACampaignNumber"] if newest else None
    if camp:
        full = api_list("recalls/campaignNumber", campaignNumber=camp)
        mine = [r for r in full if r["Model"].upper().startswith(v["Model"].upper()) and r["ModelYear"] == v["ModelYear"]]
        r = (mine or full)[0]
        print(f"  {camp}: {r['Component']} | {r.get('PotentialNumberofUnitsAffected')} units in the campaign, "
              f"{len(full)} make/model/year rows | parkIt {r.get('parkIt')} | received {r['ReportReceivedDate']} (DD/MM/YYYY)")
```

Output (from the run on 2026-11-03):

```text
1HGCM82633A004352: 2003 HONDA Accord  | ErrorCode 0: 0 - VIN decoded clean. Check Digit (9th position) is correct
  recalls 24 | complaints 2013 (crash 158, fire 19)
  19E068000: VEHICLE SPEED CONTROL:ACCELERATOR PEDAL | 3744 units in the campaign, 40 make/model/year rows | parkIt None | received 10/10/2019 (DD/MM/YYYY)

1FTFW1ET9DFC10312: 2013 FORD F-150  | ErrorCode 0: 0 - VIN decoded clean. Check Digit (9th position) is correct
  recalls 3 | complaints 2796 (crash 74, fire 31)
  19V433000: POWER TRAIN:AUTOMATIC TRANSMISSION | 107857 units in the campaign, 1 make/model/year rows | parkIt False | received 10/06/2019 (DD/MM/YYYY)

1GCVKREC6EZ123456: 2014 CHEVROLET Silverado 1500 | ErrorCode 0: 0 - VIN decoded clean. Check Digit (9th position) is correct
  recalls 20 | complaints 1561 (crash 75, fire 18)
  21V245000: SEAT BELTS:FRONT | 2568 units in the campaign, 7 make/model/year rows | parkIt False | received 08/04/2021 (DD/MM/YYYY)

1HGCM82633A004353: 2003 HONDA Accord  | ErrorCode 1: 1 - Check Digit (9th position) does not calculate properly
  not a clean decode: check the VIN before trusting the make/model/year above
```

## Fields

| Field | Source | Notes |
|---|---|---|
| `Make`, `Model`, `ModelYear`, `Series`, `Trim` | DecodeVinValues | `HONDA` / `Accord` / `2003` / `""` / `EX-V6`; all values are strings, missing = `""` |
| `BodyClass`, `DriveType`, `DisplacementL`, `EngineCylinders`, `FuelTypePrimary` | DecodeVinValues | `DisplacementL` is unrounded (`2.998832712`) |
| `PlantCity`, `PlantCountry`, `Manufacturer` | DecodeVinValues | `MARYSVILLE`, `UNITED STATES (USA)`, `AMERICAN HONDA MOTOR CO., INC.` |
| `ErrorCode`, `ErrorText`, `SuggestedVIN` | DecodeVinValues | `0` clean; `1` bad check digit; `6` incomplete VIN; `400` invalid characters; several codes join with commas (`1,400`) |
| `NHTSACampaignNumber` | recalls | `19V182000`; the 2003 Accord list mixes `..V...` vehicle and `..E...` equipment campaigns (13 and 11) |
| `ReportReceivedDate` | recalls | **DD/MM/YYYY** |
| `Component`, `Summary`, `Consequence`, `Remedy`, `Notes` | recalls | `Summary` names every make/model/year the campaign covers |
| `parkIt`, `parkOutSide`, `overTheAirUpdate` | recalls | booleans; missing on all 11 `E` campaigns of the 2003 Accord, read with `.get()` |
| `PotentialNumberofUnitsAffected` | `recalls/campaignNumber` only | `107857` for 19V433000; absent from `recallsByVehicle` |
| `odiNumber` | complaints | NHTSA complaint ID; `complaints/odinumber?odinumber=` returns one |
| `dateComplaintFiled`, `dateOfIncident` | complaints | **MM/DD/YYYY** |
| `crash`, `fire`, `numberOfInjuries`, `numberOfDeaths` | complaints | booleans / integers as filed by the owner |
| `components` | complaints | comma-joined (`"POWER TRAIN,ENGINE"`) |
| `vin` | complaints | first 11 characters only (`JHMCM56323C`) |
| `products[]` | complaints | `{type, productYear, productMake, productModel}`; the 2013 F-150 cab-variant queries all return `productModel` `F-150` |

## Gotchas

- **Model name mismatches are the main trap.** One exact query loses data silently: the 2014 Silverado 1500 has 14 recalls under `SILVERADO` and 6 under `SILVERADO 1500`, with no overlap. Always merge across names.
- **`products/vehicle/models` is incomplete without `max`.** The default answer for FORD 2013 had 18 rows, all `C-`/`E-` models (no F-150). `max` sets the page size: `max=5` gave 5, `max=1000` gave 63 rows / 41 distinct names, the same set as the union of `offset` pages. `max` and `offset` are not in NHTSA's docs. Rows repeat; dedupe them. `issueType=r` and `issueType=c` returned identical lists.
- **That list is not the recall name set either.** It has no `F-150` (only the cab variants) and no `SILVERADO`, yet `recallsByVehicle` finds records under both. Keep the vPIC model in the query list.
- **The F-150 cab variants return one and the same complaint set** (2,796 identical ODI numbers for each), so the block downloads 2.7 MB three times. Merging by `odiNumber` keeps the count right.
- **Equipment recalls show up per vehicle.** The 2003 Accord list includes `19E068000`, a Dorman aftermarket accelerator pedal.
- **Recalls under the base name can be wider than the trim.** `SILVERADO` recalls are not split by 1500/2500/3500; read `Summary` for the covered models.
- **Case-insensitive.** `honda`/`ACCORD` and `HONDA`/`Accord` both returned 24 recalls and 2,013 complaints.
- **A bad check digit still decodes.** `1HGCM82633A004353` decodes as the same Accord with `ErrorCode` `1`. Check `ErrorCode` before trusting the make/model/year. Partial VINs work with `*` (`5UXWX7C5*BA` -> 2011 BMW X3, `ErrorCode` `6`).
- **400 cannot tell a misspelled make from "no records".** Both are an empty 400. Use the decoded `Make` as-is.
- **Rate control.** vPIC's API page says users "will be controlled by an automated traffic rate control mechanism". None was hit at 0.5 s spacing; both blocks back off on 429/5xx and stop after 4 tries.
- **Tab marker.** The harness prefixes the tab title with a horse emoji; the blocks never read the title.

## What does not work

- **Opening `vpic.nhtsa.dot.gov/robots.txt` in the tab** lands on `chrome-error://chromewebdata/` (empty 404 body). Use the `/api/` page as the origin.
- **`fetch()` with `js()` alone for complaint lists:** `Runtime.evaluate timed out after 5s` on the 2003 Accord (2 MB, 4-6 s). Start-and-poll as in block 1.
- **Plain HTTP to www.nhtsa.gov:** `curl` got 403 "Access Denied" (Akamai) on `/robots.txt`. Not worked around. In the browser the same file loaded (`Crawl-delay: 10`, `/vehicle/<year>/<make>/<model>` pages allowed), but this skill does not need www.nhtsa.gov pages; the APIs carry the same data.
- **Per-VIN recall status:** these endpoints take make/model/year, not a VIN, so they cannot say whether one car's recall was repaired. Not attempted elsewhere.
- **Not tested:** the vPIC decoder web form (`/decoder/`), the Safety Ratings and investigations endpoints.
