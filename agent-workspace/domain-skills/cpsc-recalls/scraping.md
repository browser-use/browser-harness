# CPSC Recalls (SaferProducts.gov Recall API) - Check Whether a Product Has a US Recall, With the Recall Number, Date, Hazard, Units and Remedy (REST API, no key)

Field-tested against www.saferproducts.gov on 2026-11-17 (US Pacific afternoon; 23:31-23:44 UTC) using a fresh Browser Use cloud browser (logged out; two short sessions, 23:34-23:41 and 23:43 UTC, the second to re-run block 1 with shorter printouts) plus Python `urllib` and `curl` from a Linux machine. 14 browser page loads (SaferProducts.gov, both robots files, CPSC's API page, its Privacy and Security Notice and one recall notice) and 30 in-page `fetch()` calls, 80 curl calls (40 to the Recall API, 40 to robots.txt and HTML pages, recording which user agents got HTTP 403; see Gotchas) and 16 urllib calls (4 of them robots.txt), all serial. Every Recall API call was HTTP 200, including the deliberate bad-date probe (an error record inside HTTP 200, see Gotchas). robots.txt and HTML pages answered HTTP 200, 404 (SaferProducts.gov has no robots.txt) or, for some user agents from this datacenter IP, HTTP 403 (see Gotchas). No 429, no challenge, no key, no login.

robots.txt (checked 2026-11-17, cloud browser, curl and urllib): https://www.saferproducts.gov/robots.txt answers HTTP 404 with the site's HTML "not found" page, so the API host has no rules and no named AI-agent groups; under RFC 9309 (section 2.3.1.3) an unavailable robots.txt (4xx) means a crawler "MAY access any resources". https://www.cpsc.gov/robots.txt (the host of the recall notices the API links to) is a Drupal default with one `User-agent: *` group and no named AI-agent groups, so GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider fall under `*`. That group allows the notice pages (`/Recalls/2026/...`) and disallows query URLs on the cpsc.gov recall search (`Disallow: /*recalls?*`, `Disallow: /*Recalls?*`), so use the API, not the website search; block 3 checks all 11 agents with an RFC 9309 matcher. Terms: CPSC's API page (https://www.cpsc.gov/Recalls/CPSC-Recalls-Application-Program-Interface-API-Information) says the recall information "is publicly available to consumers and businesses as well as software and application developers" and "The API provides machine readable access to publicly available recall information visible on cpsc.gov". The CPSC Privacy and Security Notice (https://www.cpsc.gov/About-CPSC/Policies-Statements-and-Directives/Privacy-Policy, section "Copyright") says "Web page text, brochures, and posters presented on CPSC websites are public information. You may freely distribute, copy, or link to any of this information. However, the information may not be used in a way that states or implies CPSC endorsement. If you distribute, copy or link to any of this information, please credit CPSC." and "You may freely copy and distribute recall notices, including photographs of recalled items, without permission" and "Any other use of photographs found in recall notices and elsewhere on CPSC websites may require permission from a copyright holder." The Programmer's Guide (CPSC Recalls Retrieval Web Services Programmer's Guide, Version 1.3, October 31, 2017, linked from the API page) gives the root URI, the parameters and "Data is returned as XML, or optionally as JSON". No key or registration, no published rate limit, and no AI/ML, scraping, automated-access or non-commercial clause on these pages. Naming: "CPSC recalls (SaferProducts.gov Recall API)" as plain text; no CPSC logo or seal. This skill is not affiliated with or endorsed by CPSC.

**Attribution:** the notice asks you to "please credit CPSC": "Source: CPSC recalls (SaferProducts.gov Recall API)", plus the recall's notice URL. Blocks 1 and 3 print that line.

## Quick summary

- **No scraping.** `GET https://www.saferproducts.gov/RestWebServices/Recall?format=json&ProductName=stroller&RecallDateStart=2025-01-01` returns a JSON list of full recall records. No key, `access-control-allow-origin: *`. Without `format=json` you get XML.
- **Answer (run 2026-11-17 23:43 UTC, block 1):** **stroller: yes.** `ProductName=stroller` since 2025-01-01 gives 6 recalls; the newest is **26639 on 2026-07-23, Peony Design personalized baby bibs and stroller bags, "About 52" units, choking hazard (the snap can detach), remedy: refund**. Asking `RecallTitle` too adds 3 more, among them **26094 (2025-11-20), AliExpress convertible strollers, "About 15", fall hazard, refund**, whose product name ("4-in-1 Baby Safety Cart Carriage") does not contain "stroller". **fire pit: yes**, 3 recalls since 2025; the newest is **27082 on 2026-11-12, Sharper Image tabletop and infinity fire pits (Allstar), "About 265,000", burn and fire hazards, refund**.
- **Ask two fields and merge.** `ProductName` and `RecallTitle` each miss recalls the other finds (above). `RecallDescription` also matches toy strollers and dolls, so it is noisier.
- **Unknown parameter names are ignored silently.** `Title=stroller` (the field is `RecallTitle`) returns all 941 recalls since 2025-01-01, 2.9 MB. Blocks 1 and 3 only send names from the Programmer's Guide.
- **Some records carry another recall's `Title`.** 26569 (CooCooBaby baby loungers) is titled "Joolz Recalls Aer2 Car Seat Adapters for Strollers ..." in the API, while its notice page's heading and URL name the loungers (block 2). Block 1 flags titles that do not match the notice URL.
- **Rate limit:** none published and none hit (no 429 in 82 API calls, no rate-limit headers, `cache-control: no-cache`). The blocks stay serial with a 1 s pause.

## What works

### 1. Does this product have a CPSC recall? Number, date, hazard, units, remedy (browser)

`on_spg_tab()` opens the logged-out SaferProducts.gov home page once, so `fetch()` of the API is same-origin. `recalls()` refuses parameter names the Programmer's Guide does not list, always asks for JSON, retries once (after `Retry-After` when sent, else 60 s after 429 and 10 s after 5xx or a network error; over 120 s it stops), and raises on a non-JSON answer or on the API's error record. Each product is asked by `ProductName` and by `RecallTitle`, merged by recall number and sorted newest first. 4 `fetch()` calls.

```python
import json, re, time, unicodedata, urllib.parse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

PRODUCTS = ["stroller", "fire pit"]  # any words; the API matches them as a case-insensitive substring
SINCE = "2025-01-01"                 # RecallDateStart, YYYY-MM-DD; "" for every recall back to the 1970s

SITE = "https://www.saferproducts.gov"
API = SITE + "/RestWebServices/Recall"
# Parameter names from the Programmer's Guide v1.3 (2017) plus format. The server silently ignores any other name
# (Title=stroller returns every recall), so refuse unknown names here instead.
PARAMS = {"RecallID", "RecallNumber", "RecallDateStart", "RecallDateEnd", "LastPublishDateStart", "LastPublishDateEnd",
          "RecallURL", "RecallTitle", "ConsumerContact", "RecallDescription", "ProductName", "ProductDescription",
          "ProductModel", "ProductType", "InconjunctionURL", "ImageURL", "Injury", "Manufacturer", "Retailer",
          "Importer", "Distributor", "ManufacturerCountry", "UPC", "Hazard", "Remedy", "RemedyOption", "format"}

def on_spg_tab():
    """fetch() runs same-origin from a logged-out saferproducts.gov page. Reuse the tab if it is already there."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(SITE + "/")
    wait_for_load()
    if js("location.origin") != SITE:
        raise RuntimeError(f"SaferProducts.gov did not load (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__o = window.__o || {}; const id = String(Math.random()).slice(2); window.__o[id] = null;
  fetch(%s, {credentials: 'omit', cache: 'no-store'})
    .then(async r => { window.__o[id] = {status: r.status, type: r.headers.get('content-type'),
                                         ra: r.headers.get('retry-after'), text: await r.text()}; })
    .catch(e => { window.__o[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__o[%s]; if (v) delete window.__o[%s]; return v; })()"""

def retry_after(v, default):
    """Retry-After in seconds (a number or an HTTP date); default when absent or unreadable; at least 1.
    Over 120 s: stop rather than hammer or hang."""
    try:
        sec = float(v)
    except (TypeError, ValueError):
        try:
            sec = (parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError):
            sec = default
    if sec != sec:  # 'nan'
        sec = default
    if sec > 120:
        raise RuntimeError(f"server asks to wait {sec:.0f} s (over 120 s): stopping")
    return max(sec, 1)

def recalls(timeout=90, **params):
    """GET /Recall?format=json&... -> list of recall dicts. Retries once, after Retry-After when sent (else 60 s
    after 429, 10 s after 5xx or a network error). Raises on an unknown parameter, a non-JSON answer, or the API's
    in-band error record (HTTP 200). format is always json, whatever the caller passes."""
    bad = set(params) - PARAMS
    if bad:
        raise ValueError(f"unknown parameter(s) {sorted(bad)}: the API would ignore them and return everything")
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    for attempt in range(2):
        rid = json.dumps(js(START_JS % json.dumps(url)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"no answer after {timeout}s: {url}")
            time.sleep(0.3)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(retry_after(r.get("ra"), 60 if r["status"] == 429 else 10))
            continue
        if r["status"] != 200 or "json" not in (r["type"] or ""):
            raise RuntimeError(f"HTTP {r['status']} {r['type']} {r['text'][:200]!r}: {url}")
        data = json.loads(r["text"])
        if not isinstance(data, list):
            raise RuntimeError(f"expected a JSON list, got {type(data).__name__}: {url}")
        # A bad value (RecallDateStart=not-a-date) is HTTP 200 with one record: RecallID 0, Title "Error retrieving ...".
        if len(data) == 1 and data[0].get("RecallID") == 0 and str(data[0].get("Title")).startswith("Error"):
            raise RuntimeError(f"API error: {data[0]['Title']}: {url}")
        time.sleep(1.0)  # no published rate limit; stay serial and gentle
        return data

def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return "".join(w for w in re.split(r"[^a-z0-9]+", s.replace("&", " ")) if w and w != "and")

def title_ok(r):
    """Title should start with the notice URL's first two words. 5 of 941 records since 2025 carry another recall's
    title (26569 CooCooBaby loungers is titled 'Joolz Recalls Aer2 Car Seat Adapters ...'); older notices (before
    about 2010) often have differently worded URLs, so a mismatch there means 'read the notice', not 'wrong'."""
    words = [w for w in re.split(r"[^a-z0-9]+", urllib.parse.unquote((r["URL"] or "").rstrip("/").rsplit("/", 1)[-1]).lower())
             if w and w != "and"]
    return norm(r["Title"] or "").startswith(norm(" ".join(words[:2])))

def us_units(text):
    """'About 3,840 (In addition, about 148 were sold in Canada)' -> 3840; 'About 5.9 million' -> 5900000; else None."""
    m = re.match(r"\s*(?:about|approximately|more than|over)?\s*([\d][\d,]*(?:\.\d+)?)\s*(million)?", text or "", re.I)
    if not m:
        return None
    n = float(m[1].replace(",", ""))
    return int(round(n * 1_000_000)) if m[2] else int(n)

def fix_url(u):
    return re.sub(r"^https:/(?!/)", "https://", u or "")  # one record since 2025 has 'https:/www.cpsc.gov/...'

on_spg_tab()
for product in PRODUCTS:
    # ProductName misses some (26094 'AliExpress Recalls Convertible Strollers' is named '4-in-1 Baby Safety Cart
    # Carriage'), RecallTitle misses others; ask both and merge by RecallNumber.
    hits = {}
    for field in ("ProductName", "RecallTitle"):
        q = {field: product, **({"RecallDateStart": SINCE} if SINCE else {})}
        for r in recalls(**q):
            hits.setdefault(r["RecallNumber"], (r, set()))[1].add(field)
    # The Guide promises no order; every list in this run came newest first, but sort anyway.
    rows = sorted(hits.values(), key=lambda x: (x[0]["RecallDate"] or "", x[0]["RecallNumber"]), reverse=True)
    print(f"\n'{product}' since {SINCE or 'the start'}: {len(rows)} recalls "
          f"({sum('ProductName' in f for _, f in rows)} by ProductName, {sum('RecallTitle' in f for _, f in rows)} by RecallTitle)")
    for r, fields in rows:
        p = r["Products"][0] if r["Products"] else {}
        units = "; ".join(x.get("NumberOfUnits", "") for x in r["Products"])
        n = us_units(r["Products"][0]["NumberOfUnits"]) if r["Products"] else None
        hz = " | ".join(h["Name"] for h in r["Hazards"]) or "(no hazard text)"
        rem = " | ".join(x["Name"] for x in r["Remedies"]) or "(no remedy text)"
        opts = ", ".join(o["Option"] for o in r["RemedyOptions"] if len(o["Option"]) < 40)
        firm = (r["Manufacturers"] or r["Importers"] or r["Distributors"] or r["Retailers"] or [{"Name": "?"}])[0]["Name"]
        print(f"- {r['RecallNumber']} {r['RecallDate'][:10]} [{'+'.join(sorted(fields))}] {p.get('Name')}")
        print(f"    title:  {r['Title'].strip()}" + ("" if title_ok(r) else "  <- DOES NOT MATCH THE NOTICE URL, read the notice"))
        print(f"    firm:   {firm}")
        print(f"    units:  {units!r}" + (f" -> {n:,} in the US" if n is not None else ""))
        print(f"    hazard: {hz[:140]}")
        print(f"    remedy: {opts or '?'}: {rem[:140]}")
        print(f"    notice: {fix_url(r['URL'])}")
    if rows:
        r = rows[0][0]
        p = r["Products"][0] if r["Products"] else {}
        print(f"ANSWER '{product}': yes, newest {r['RecallNumber']} on {r['RecallDate'][:10]}: {p.get('Name')}, "
              f"{p.get('NumberOfUnits')} units, remedy {', '.join(o['Option'] for o in r['RemedyOptions'])}")
    else:
        print(f"ANSWER '{product}': no CPSC recall matched since {SINCE} (no match is not proof of safety)")

print(f"\nSource: CPSC recalls (SaferProducts.gov Recall API), accessed {time.strftime('%d %B %Y %H:%M', time.gmtime())} UTC. "
      "Not affiliated with or endorsed by CPSC.")
```

Output (from the run on 2026-11-17, 23:43 UTC):

```text

'stroller' since 2025-01-01: 9 recalls (6 by ProductName, 9 by RecallTitle)
- 26639 2026-07-23 [ProductName+RecallTitle] Personalized Baby Bibs and Stroller Bags
    title:  Peony Design Recalls Personalized Baby Bibs and Stroller Bags Due to Risk of Serious Injury or Death from Choking Hazard
    firm:   Peony Design Co., of Howell, MI
    units:  'About 52' -> 52 in the US
    hazard: The snap can detach from the recalled bibs and stroller bags, posing a risk of serious injury or death from a choking hazard to young childr
    remedy: Refund: Consumers should take the recalled baby bibs and stroller bags away from children immediately, stop using them, and contact Peony Design to 
    notice: https://www.cpsc.gov/Recalls/2026/Peony-Design-Recalls-Personalized-Baby-Bibs-and-Stroller-Bags-Due-to-Risk-of-Serious-Injury-or-Death-from-Choking-Hazard
- 26569 2026-06-18 [RecallTitle] CooCooBaby Baby Loungers
    title:  Joolz Recalls Aer2 Car Seat Adapters for Strollers Due to Risk of Serious Injury or Death from Suffocation and Fall Hazards; Violates Mandatory Standard for Infant Sleep Products  <- DOES NOT MATCH THE NOTICE URL, read the notice
    firm:   CooCooBaby, of China
    units:  'About 2,355' -> 2,355 in the US
    hazard: The baby loungers violate the mandatory standard for Infant Sleep Products because the sides are shorter than the minimum side height limit 
    remedy: Refund: Consumers should stop using the baby loungers immediately and contact CooCooBaby for a full refund. Consumers should remove the sleeping pad
    notice: https://www.cpsc.gov/Recalls/2026/CooCooBaby-Baby-Loungers-Recalled-Due-to-Risk-of-Serious-Injury-or-Death-from-Suffocation-and-Fall-Hazards-Violates-Mandatory-Standard-for-Infant-Sleep-Products
- 26568 2026-06-18 [ProductName+RecallTitle] Joolz Aer2 Car Seat Adapters for Joolz Aer 2 Stroller
    title:  Joolz Recalls Aer2 Car Seat Adapters for Strollers Due to Risk of Serious Injury from Fall Hazard
    firm:   Joolz USA Inc., of New York, New York
    units:  'About 3,840 (In addition, about 148 were sold in Canada)' -> 3,840 in the US
    hazard: The recalled car seat adapters can fail to properly attach to the stroller, which may allow the car seat to fall, posing a risk of serious i
    remedy: Refund: Consumers should stop using the Joolz Aer2 Car Seat Adapters immediately, detach them from the stroller and go to http://joolzcarseatadapter
    notice: https://www.cpsc.gov/Recalls/2026/Joolz-Recalls-Aer2-Car-Seat-Adapters-for-Strollers-Due-to-Risk-of-Serious-Injury-from-Fall-Hazard
- 26561 2026-06-18 [ProductName+RecallTitle] BABESIDE Doll and Stroller Toys
    title:  BABESIDE Doll and Stroller Children's Toys Recalled Due to Risk of Serious Injury or Death from Choking Hazard; Violate Small Parts Ban; Sold on Amazon by HYBDOLLS
    firm:   Huizhou Huitong Crafts Co. Ltd., of China
    units:  'About 2,200' -> 2,200 in the US
    hazard: The recalled toys violate the small parts ban because they are intended for children under three and the small pacifier poses a deadly choki
    remedy: Repair: Consumers should stop using the recalled toys' plush bear and pacifier immediately, take them away from children and contact HYBDOLLS for fr
    notice: https://www.cpsc.gov/Recalls/2026/BABESIDE-Doll-and-Stroller-Childrens-Toys-Recalled-Due-to-Risk-of-Serious-Injury-or-Death-from-Choking-Hazard-Violate-Small-Parts-Ban-Sold-on-Amazon-by-HYBDOLLS
- 26094 2025-11-20 [RecallTitle] 4-in-1 Baby Safety Cart Carriage
    title:  AliExpress Recalls Convertible Strollers Due to Risk of Serious Injury or Death from Fall Hazard; Violates Mandatory Standard for Strollers
    firm:   AliExpress, of San Mateo, California
    units:  'About 15' -> 15 in the US
    hazard: The stroller violates the mandatory standard for strollers because the restraint system can fail, posing a risk of serious injury or deadly 
    remedy: Refund: Consumers should immediately stop using the recalled stroller and contact AliExpress to receive a full refund. Consumers will be required to
    notice: https://www.cpsc.gov/Recalls/2026/AliExpress-Recalls-Convertible-Strollers-Due-to-Risk-of-Serious-Injury-or-Death-from-Fall-Hazard-Violates-Mandatory-Standard-for-Strollers
- 26044 2025-10-23 [RecallTitle] Pack-N-Stroll Premium Folding Utility Wagon
    title:  Olympia Tools International Recalls Pack-N-Stroll Utility Wagons Due to Risk of Serious Injury or Death from Entrapment and Falls; Violates Mandatory Standard for Strollers
    firm:   Olympia Tools International, Inc. of Covina, California
    units:  'About 530' -> 530 in the US
    hazard: The utility wagon violates the mandatory standard for strollers because an opening between the organizational tray and the sidewall may caus
    remedy: Refund: Consumers should stop using the utility wagons immediately and return the item to Costco to receive a full refund.
    notice: https://www.cpsc.gov/Recalls/2026/Olympia-Tools-International-Recalls-Pack-N-Stroll-Utility-Wagons-Due-to-Risk-of-Serious-Injury-or-Death-from-Entrapment-and-Falls-Violates-Mandatory-Standard-for-Strollers
- 25476 2025-09-25 [ProductName+RecallTitle] Hoovy Cooling Gel Insert Pads for Car Seats and Strollers
    title:  AMTRADING Recalls Hoovy Cooling Gel Insert Pads for Car Seats and Strollers Due to Burn Hazard
    firm:   AMTRADING LLC, of Brielle, NJ
    units:  'About 20,000' -> 20,000 in the US
    hazard: The cooling gel pads can become hot if left in the sun or a hot car, posing a burn hazard to young children.
    remedy: Refund: Consumers should immediately stop using the recalled Cooling Gel Insert Pad and contact AMTRADING for instructions on receiving a full refun
    notice: https://www.cpsc.gov/Recalls/2025/AMTRADING-Recalls-Hoovy-Cooling-Gel-Insert-Pads-for-Car-Seats-and-Strollers-Due-to-Burn-Hazard
- 25215 2025-04-10 [ProductName+RecallTitle] Brunch & Go Stroller Toys
    title:  Fisher-Price Recalls Brunch & Go Stroller Toys Due to Choking Hazard
    firm:   Fisher-Price Inc., of East Aurora, New York
    units:  'About 253,000 (In addition, about 4,500 were sold in Canada)' -> 253,000 in the US
    hazard: The yolk of the toy egg can crack and create small parts, posing a choking hazard to young children.
    remedy: Replace: Consumers should immediately stop using the recalled stroller toys, keep them away from children, and contact Fisher-Price to receive a free
    notice: https://www.cpsc.gov/Recalls/2025/Fisher-Price-Recalls-Brunch-Go-Stroller-Toys-Due-to-Choking-Hazard
- 25160 2025-03-06 [ProductName+RecallTitle] Nuby Stroller Fans
    title:  Luv n' care Recalls Nuby Stroller Fans Due to Laceration Injury Hazard
    firm:   Luv n' care, of Monroe, Louisiana
    units:  'About 33,600' -> 33,600 in the US
    hazard: The stroller fan's housing allows consumers' fingers to contact the fan's blade, posing a laceration injury hazard to small children.
    remedy: Replace: Consumers should stop using the stroller fan immediately and contact Luv n' care for information on how to return the product to obtain a fr
    notice: https://www.cpsc.gov/Recalls/2025/Luv-n-care-Recalls-Nuby-Stroller-Fans-Due-to-Laceration-Injury-Hazard
ANSWER 'stroller': yes, newest 26639 on 2026-07-23: Personalized Baby Bibs and Stroller Bags, About 52 units, remedy Refund

'fire pit' since 2025-01-01: 3 recalls (3 by ProductName, 3 by RecallTitle)
- 27082 2026-11-12 [ProductName+RecallTitle] Sharper Image Tabletop Fire Pits and Sharper Image Tabletop Infinity Fire Pits
    title:  Allstar Recalls Sharper Image Tabletop and Infinity Fire Pits Due to Risk of Serious Injury from Burn and Fire Hazards
    firm:   Allstar Marketing Group, LLC, of Winston-Salem, North Carolina
    units:  'About 265,000' -> 265,000 in the US
    hazard: Ignited flammable liquid can escape from the recalled fire pits or trigger flame jetting from the fuel containers, posing a risk of serious 
    remedy: Refund: Consumers should stop using the recalled fire pits immediately and contact Allstar for a full refund. Consumers will be asked to register at
    notice: https://www.cpsc.gov/Recalls/2027/Allstar-Recalls-Sharper-Image-Tabletop-and-Infinity-Fire-Pits-Due-to-Risk-of-Serious-Injury-from-Burn-and-Fire-Hazards
- 26687 2026-08-13 [ProductName+RecallTitle] Brookstone-branded Tabletop Fire Pits
    title:  Southern Telecom Recalls Brookstone-Branded Tabletop Fire Pits Due to Risk of Serious Burn Injury or Death from Flame Jetting and Fire Hazards
    firm:   Southern Telecom Inc., of Brooklyn, New York
    units:  'About 48,700' -> 48,700 in the US
    hazard: Use of the fire pits can result in uncontrolled pool fires where flames burn across the surface of pooled or spilled alcohol, as well as fla
    remedy: Refund: Consumers should stop using the Brookstone-branded Tabletop Fire Pits immediately and contact Southern Telecom to receive a full refund. Con
    notice: https://www.cpsc.gov/Recalls/2026/Southern-Telecom-Recalls-Brookstone-Branded-Tabletop-Fire-Pits-Due-to-Risk-of-Serious-Burn-Injury-or-Death-from-Flame-Jetting-and-Fire-Hazards
- 25467 2025-09-18 [ProductName+RecallTitle] Tabletop Fire Pits
    title:  Five Below Recalls Tabletop Fire Pits Due to Risk of Serious Burn Injury from Flame Jetting and Fire Hazards
    firm:   1616 Holdings Inc., of Philadelphia, Pennsylvania
    units:  'About 66,000' -> 66,000 in the US
    hazard: Alcohol fuel can splash or leak out of the fire pit reservoir during use and/or ignition, causing a flash fire that can spread and create la
    remedy: Refund: Consumers should immediately stop using the recalled tabletop fire pits and contact Five Below to receive a full refund equal to the purchas
    notice: https://www.cpsc.gov/Recalls/2025/Five-Below-Recalls-Tabletop-Fire-Pits-Due-to-Risk-of-Serious-Burn-Injury-from-Flame-Jetting-and-Fire-Hazards
ANSWER 'fire pit': yes, newest 27082 on 2026-11-12: Sharper Image Tabletop Fire Pits and Sharper Image Tabletop Infinity Fire Pits, About 265,000 units, remedy Refund

Source: CPSC recalls (SaferProducts.gov Recall API), accessed 17 November 2026 23:43 UTC. Not affiliated with or endorsed by CPSC.
```

### 2. robots.txt, terms, the notice behind a wrong title, and query mistakes (browser)

6 page loads and 11 in-page `fetch()` calls in the same tab. The cpsc.gov pages are read in the browser, as a person reads them; the skill makes no scripted requests to cpsc.gov pages.

```python
import json, re, time

SITE = "https://www.saferproducts.gov"
API = SITE + "/RestWebServices/Recall"
CPSC = "https://www.cpsc.gov"

START_JS = """(() => { window.__o = window.__o || {}; const id = String(Math.random()).slice(2); window.__o[id] = null;
  fetch(%s, {credentials: 'omit', cache: 'no-store'})
    .then(async r => { const t = await r.text(); let n = null; try { const d = JSON.parse(t); if (Array.isArray(d)) n = d.length; } catch (e) {}
      window.__o[id] = {status: r.status, type: r.headers.get('content-type'), bytes: t.length, n, text: t.slice(0, 20000)}; })
    .catch(e => { window.__o[id] = {status: 0, type: '', bytes: 0, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__o[%s]; if (v) delete window.__o[%s]; return v; })()"""

def raw(query):
    """One in-page GET of the Recall API -> status, type, size, body. No retries: this block only inspects answers."""
    rid = json.dumps(js(START_JS % json.dumps(API + "?" + query)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 90:
            raise RuntimeError(f"{query}: no answer after 90s")
        time.sleep(0.3)
    time.sleep(1.0)
    return r

def page(url, wait=4):
    goto_url(url)
    wait_for_load()
    time.sleep(wait)  # cpsc.gov pages finish rendering after load
    return (js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus"),
            js("document.body ? document.body.innerText : ''") or "")

def quote(text, start, n=260):
    i = text.find(start)
    return re.sub(r"\s+", " ", text[i:i + n]) if i >= 0 else f"NOT FOUND: {start!r}"

# 1. robots.txt on both hosts, as the browser sees them
st, txt = page(SITE + "/robots.txt", wait=1)
print(f"saferproducts.gov/robots.txt HTTP {st}: {re.sub(chr(10), ' | ', txt.strip())[:110]!r}")
st, txt = page(CPSC + "/robots.txt", wait=1)
groups = re.findall(r"(?im)^user-agent:\s*(.+)$", txt)
print(f"cpsc.gov/robots.txt HTTP {st}: {len(txt)} chars, User-agent groups {groups}; recall lines: "
      f"{[l for l in txt.splitlines() if 'ecall' in l]}")

# 2. CPSC's API page and copyright notice (terms)
st, txt = page(CPSC + "/Recalls/CPSC-Recalls-Application-Program-Interface-API-Information")
print(f"\nAPI page HTTP {st}: {quote(txt, 'CPSC provides accessibility', 330)!r}")
guide = js("[...document.querySelectorAll('a')].filter(a => /Programmer/i.test(a.innerText)).map(a => a.href)")
print(f"Programmer's Guide link: {guide}")
st, txt = page(CPSC + "/About-CPSC/Policies-Statements-and-Directives/Privacy-Policy")
print(f"Privacy and Security Notice HTTP {st}:")
print(f"  {quote(txt, 'Web page text, brochures', 330)!r}")
print(f"  {quote(txt, 'You may freely copy and distribute recall notices', 200)!r}")

# 3. The official notice for 26569: the API's Title field belongs to another recall (26568)
st, txt = page(CPSC + "/Recalls/2026/CooCooBaby-Baby-Loungers-Recalled-Due-to-Risk-of-Serious-Injury-or-Death-from-"
               "Suffocation-and-Fall-Hazards-Violates-Mandatory-Standard-for-Infant-Sleep-Products")
h1 = js("(document.querySelector('h1') || {}).innerText")
print(f"\nnotice 26569 HTTP {st}: h1 {h1!r}; units line {quote(txt, 'Units', 40)!r}")

# 4. Query behaviour, from a saferproducts.gov page (same origin)
page(SITE + "/", wait=1)
def show(label, q):
    r = raw(q)
    body = r["text"]
    if r.get("n") is None:  # not a JSON list (XML)
        info = repr(re.sub(r"\s+", " ", body[:80]))
    else:
        first = re.search(r'"RecallID":(\d+),"RecallNumber":("?[^,]*"?),"RecallDate":("?[^,]*"?)', body)
        info = f"{r['n']:,} recalls" + (f", first {first[2].strip('"')} {first[3].strip('"')[:10]}" if first and r["n"] else "")
        if first and first[1] == "0":
            info = f"error record: {json.loads(body)[0]['Title'][:95]!r}"
    print(f"{label:<34} HTTP {r['status']} {(r['type'] or '').split(';')[0]:<16} {r['bytes']:>9,} chars  {info}")

show("ProductName=stroller (2025+)", "format=json&ProductName=stroller&RecallDateStart=2025-01-01")
show("productname=STROLLER (case)", "format=json&productname=STROLLER&RecallDateStart=2025-01-01")
show("RecallTitle=stroller (2025+)", "format=json&RecallTitle=stroller&RecallDateStart=2025-01-01")
show("Title=stroller (not a parameter)", "format=json&Title=stroller&RecallDateStart=2025-01-01")
show("only RecallDateStart=2025-01-01", "format=json&RecallDateStart=2025-01-01")
show("Hazard=choking", "format=json&Hazard=choking")
show("RecallNumber=26639", "format=json&RecallNumber=26639")
show("RecallNumber=2663 (substring)", "format=json&RecallNumber=2663&RecallDateStart=2025-01-01")
show("RecallDateStart=not-a-date", "format=json&ProductName=stroller&RecallDateStart=not-a-date")
show("ProductName=zzqxv (no match)", "format=json&ProductName=zzqxv")
show("no format (XML default)", "ProductName=stroller&RecallDateStart=2025-01-01")
```

Output (from the run on 2026-11-17, 23:39 UTC; `chars` counts JavaScript string length, so the 2.9 MB answer shows 2,923,073 chars against 2,924,873 bytes in curl):

```text
saferproducts.gov/robots.txt HTTP 404: 'Skip to main content |  | An official website of the United States government |  | \xa0 | Here’s how you know |  '
cpsc.gov/robots.txt HTTP 200: 3254 chars, User-agent groups ['*']; recall lines: ['Disallow: /*product_recalls_download?*', 'Disallow: /*Product_Recalls_Download?*', 'Disallow: /*recalls?*', 'Allow: /*recalls?page*', 'Disallow: /*Recalls?*', 'Allow: /*Recalls?page*']

API page HTTP 200: 'CPSC provides accessibility to recalls via a recall database. The information is publicly available to consumers and businesses as well as software and application developers. The Commission recently worked towards a new and improved recalls API implemented as REST web services. The recall data can be retrieved in XML or in JSO'
Programmer's Guide link: ['https://www.cpsc.gov/s3fs-public/RecallRetrievalWebServicesProgrammersGuide20171031.pdf?n_FtdOGyf5GGSKF5qhIMnlCuJTFaKNS7']
Privacy and Security Notice HTTP 200:
  'Web page text, brochures, and posters presented on CPSC websites are public information. You may freely distribute, copy, or link to any of this information. However, the information may not be used in a way that states or implies CPSC endorsement. If you distribute, copy or link to any of this information, please credit CPSC. '
  'You may freely copy and distribute recall notices, including photographs of recalled items, without permission. Any other use of photographs found in recall notices and elsewhere on CPSC websites may '

notice 26569 HTTP 200: h1 'CooCooBaby Baby Loungers Recalled Due to Risk of Serious Injury or Death from Suffocation and Fall Hazards; Violates Mandatory Standard for Infant Sleep Products'; units line 'Units: About 2,355 Consumer Contact E'
ProductName=stroller (2025+)       HTTP 200 application/json    17,303 chars  6 recalls, first 26639 2026-07-23
productname=STROLLER (case)        HTTP 200 application/json    17,303 chars  6 recalls, first 26639 2026-07-23
RecallTitle=stroller (2025+)       HTTP 200 application/json    25,172 chars  9 recalls, first 26639 2026-07-23
Title=stroller (not a parameter)   HTTP 200 application/json 2,923,073 chars  941 recalls, first 27082 2026-11-12
only RecallDateStart=2025-01-01    HTTP 200 application/json 2,923,073 chars  941 recalls, first 27082 2026-11-12
Hazard=choking                     HTTP 200 application/json         2 chars  0 recalls
RecallNumber=26639                 HTTP 200 application/json     3,247 chars  1 recalls, first 26639 2026-07-23
RecallNumber=2663 (substring)      HTTP 200 application/json    27,939 chars  9 recalls, first 26632 2026-07-30
RecallDateStart=not-a-date         HTTP 200 application/json       510 chars  error record: "Error retrieving Recalls: An error occurred while reading from the store provider's data reader"
ProductName=zzqxv (no match)       HTTP 200 application/json         2 chars  0 recalls
no format (XML default)            HTTP 200 application/xml     20,069 chars  '<Recalls xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.o'
```

### 3. Same answer with Python urllib, robots check for every agent, exact recall number, what is new (no browser)

8 requests. `robots_rules()`/`allowed()` implement RFC 9309 matching (`*`, `$`, longest rule wins), because cpsc.gov uses wildcard rules. `units_us()` reads the leading US figure out of the free-text `NumberOfUnits`.

```python
import json, re, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

PRODUCTS = ["stroller", "fire pit"]
SINCE = "2025-01-01"
NEW_DAYS = 14  # also list every recall announced in the last N days

API = "https://www.saferproducts.gov/RestWebServices/Recall"
UA = "cpsc-recalls-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"  # says who is asking; one fixed UA"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]

def retry_after(v, default):
    """Retry-After in seconds (a number or an HTTP date); default when absent or unreadable; at least 1.
    Over 120 s: stop rather than hammer or hang."""
    try:
        sec = float(v)
    except (TypeError, ValueError):
        try:
            sec = (parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError):
            sec = default
    if sec != sec:  # 'nan'
        sec = default
    if sec > 120:
        sys.exit(f"server asks to wait {sec:.0f} s (over 120 s): stopping")
    return max(sec, 1)

def get(url, ok=(200,)):
    """GET -> (status, content-type, text). One retry: after Retry-After when sent, else 60 s after 429 and 10 s
    after 5xx or a network error. Statuses in ok are returned; anything else exits."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, r.headers.get("Content-Type", ""), r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code in ok:
                return e.code, e.headers.get("Content-Type", ""), e.read().decode("utf-8", "replace")
            if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(retry_after(e.headers.get("Retry-After"), 60 if e.code == 429 else 10))
                continue
            sys.exit(f"HTTP {e.code} {url}: {e.read()[:200]!r}")
        except OSError as e:  # URLError, timeouts, resets
            if attempt == 0:
                time.sleep(10)
                continue
            sys.exit(f"{url}: {e}")

def recalls(**params):
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    st, ctype, text = get(url)
    if "json" not in ctype:
        sys.exit(f"not JSON ({ctype}): {url}")
    data = json.loads(text)
    if not isinstance(data, list) or (len(data) == 1 and data[0].get("RecallID") == 0):
        sys.exit(f"API error: {str(data)[:200]}: {url}")
    time.sleep(1)
    return data

def robots_rules(text):
    """RFC 9309 groups -> {agent(lower): [(allow?, pattern)]}."""
    groups, cur, in_rules = {}, [], False
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        k, v = (x.strip() for x in line.split(":", 1))
        k = k.lower()
        if k == "user-agent":
            if in_rules:
                cur, in_rules = [], False
            cur.append(v.lower())
            groups.setdefault(v.lower(), [])
        elif k in ("allow", "disallow") and cur:
            in_rules = True
            for a in cur:
                groups[a].append((k == "allow", v))
    return groups

def allowed(groups, agent, path):
    """Longest matching rule wins, Allow on a tie; '*' and '$' as in RFC 9309. No group for the agent -> '*' group."""
    rules = groups.get(agent.lower(), groups.get("*", []))
    best = (-1, True)
    for allow, pat in rules:
        if not pat:
            continue
        rx = "^" + re.escape(pat).replace(r"\*", ".*").replace(r"\$", "$")
        if re.match(rx, path) and (len(pat) > best[0] or (len(pat) == best[0] and allow)):
            best = (len(pat), allow)
    return best[1]

# robots.txt: saferproducts.gov has none (404 = no rules, RFC 9309 2.3.1.3); cpsc.gov has one '*' group.
for host, paths in (("https://www.saferproducts.gov", ["/RestWebServices/Recall"]),
                    ("https://www.cpsc.gov", ["/Recalls/2026/Peony-Design-Recalls-Personalized-Baby-Bibs-and-Stroller-Bags",
                                              "/Recalls/CPSC-Recalls-Application-Program-Interface-API-Information",
                                              "/Recalls?search=stroller"])):
    st, ctype, text = get(host + "/robots.txt", ok=(200, 403, 404))
    if st == 404:
        print(f"{host}/robots.txt HTTP 404: no rules, every agent allowed")
        continue
    if st == 403:  # blocked here: do not retry with another user agent; read it in the browser (block 2)
        print(f"{host}/robots.txt HTTP 403: not readable from here, check it in the browser (block 2)")
        if "saferproducts" in host:
            sys.exit("cannot confirm robots.txt for the API host: stop")
        continue
    g = robots_rules(text)
    print(f"{host}/robots.txt HTTP 200, groups {sorted(g)}")
    for p in paths:
        ok = all(allowed(g, a, p) for a in AGENTS)
        print(f"  {p[:60]:<62} {'allowed' if ok else 'DISALLOWED'} for all {len(AGENTS)} agents")
    time.sleep(1)

def units_us(text):
    m = re.match(r"\s*(?:about|approximately)?\s*(\d[\d,]*(?:\.\d+)?)\s*(million)?", text or "", re.I)
    return None if not m else int(round(float(m[1].replace(",", "")) * (1e6 if m[2] else 1)))

for product in PRODUCTS:
    hits = {}
    for field in ("ProductName", "RecallTitle"):
        for r in recalls(**{field: product, "RecallDateStart": SINCE}):
            hits.setdefault(r["RecallNumber"], r)
    rows = sorted(hits.values(), key=lambda r: (r["RecallDate"], r["RecallNumber"]), reverse=True)
    print(f"\n'{product}' since {SINCE}: {len(rows)} recalls (ProductName or RecallTitle match; check each product name)")
    for r in rows:
        p = r["Products"][0] if r["Products"] else {"Name": "(no product)", "NumberOfUnits": ""}
        n = units_us(p["NumberOfUnits"])
        print(f"  {r['RecallNumber']} {r['RecallDate'][:10]} {p['Name'][:52]:<52} "
              f"{'?' if n is None else f'{n:,}':>8} US units  {'/'.join(o['Option'][:12] for o in r['RemedyOptions'])}")

# Exact recall number: the RecallNumber filter is a substring match ('2663' returns 26630-26639), so compare.
r = [x for x in recalls(RecallNumber="26639") if x["RecallNumber"] == "26639"]
if len(r) != 1:
    sys.exit(f"expected exactly one recall 26639, got {len(r)}")
r = r[0]
print(f"\n26639: {r['RecallDate'][:10]}, {r['Products'][0]['NumberOfUnits']} units, hazard: {r['Hazards'][0]['Name'][:90]}...")

# What is new: recalls announced in the last NEW_DAYS days, newest first.
since = (date.today() - timedelta(days=NEW_DAYS)).isoformat()
new = sorted(recalls(RecallDateStart=since), key=lambda r: (r["RecallDate"], r["RecallNumber"]), reverse=True)
print(f"\n{len(new)} recalls with RecallDate >= {since}; newest 3:")
for r in new[:3]:
    print(f"  {r['RecallNumber']} {r['RecallDate'][:10]} {r['Title'][:100]}")

print(f"\nSource: CPSC recalls (SaferProducts.gov Recall API), accessed {time.strftime('%d %B %Y %H:%M', time.gmtime())} UTC. "
      "Not affiliated with or endorsed by CPSC.")
```

Output (from the run on 2026-11-17, 23:40 UTC):

```text
https://www.saferproducts.gov/robots.txt HTTP 404: no rules, every agent allowed
https://www.cpsc.gov/robots.txt HTTP 200, groups ['*']
  /Recalls/2026/Peony-Design-Recalls-Personalized-Baby-Bibs-an   allowed for all 11 agents
  /Recalls/CPSC-Recalls-Application-Program-Interface-API-Info   allowed for all 11 agents
  /Recalls?search=stroller                                       DISALLOWED for all 11 agents

'stroller' since 2025-01-01: 9 recalls (ProductName or RecallTitle match; check each product name)
  26639 2026-07-23 Personalized Baby Bibs and Stroller Bags                   52 US units  Refund
  26569 2026-06-18 CooCooBaby Baby Loungers                                2,355 US units  Refund
  26568 2026-06-18 Joolz Aer2 Car Seat Adapters for Joolz Aer 2 Strolle    3,840 US units  Refund
  26561 2026-06-18 BABESIDE Doll and Stroller Toys                         2,200 US units  Repair
  26094 2025-11-20 4-in-1 Baby Safety Cart Carriage                           15 US units  Refund
  26044 2025-10-23 Pack-N-Stroll Premium Folding Utility Wagon               530 US units  Refund
  25476 2025-09-25 Hoovy Cooling Gel Insert Pads for Car Seats and Stro   20,000 US units  Refund
  25215 2025-04-10 Brunch & Go Stroller Toys                             253,000 US units  Replace
  25160 2025-03-06 Nuby Stroller Fans                                     33,600 US units  Replace

'fire pit' since 2025-01-01: 3 recalls (ProductName or RecallTitle match; check each product name)
  27082 2026-11-12 Sharper Image Tabletop Fire Pits and Sharper Image T  265,000 US units  Refund
  26687 2026-08-13 Brookstone-branded Tabletop Fire Pits                  48,700 US units  Refund
  25467 2025-09-18 Tabletop Fire Pits                                     66,000 US units  Refund

26639: 2026-07-23, About 52 units, hazard: The snap can detach from the recalled bibs and stroller bags, posing a risk of serious inj...

19 recalls with RecallDate >= 2026-11-03; newest 3:
  27088 2026-11-12 Boshengya Recalls Rugs Due to Risk of Serious Injury or Death from Fire Hazard; Violate Mandatory St
  27087 2026-11-12 Cummins Recalls Portable Generators Due to Risk of Serious Injury from Fire and Burn Hazards
  27086 2026-11-12 Huffy Recalls Buzz Bicycles Cerana T2 E-Trikes Due to Risk of Serious Injury from Fall Hazard

Source: CPSC recalls (SaferProducts.gov Recall API), accessed 17 November 2026 23:40 UTC. Not affiliated with or endorsed by CPSC.
```

### 4. curl, headers and mistakes

```bash
R=https://www.saferproducts.gov/RestWebServices/Recall
UA='cpsc-recalls-skill-example/1.0 (+https://github.com/browser-use/browser-harness)'
# the answer: recalls whose product name contains "fire pit" since 2025, newest first
curl -sS --fail -A "$UA" "$R?format=json&ProductName=fire%20pit&RecallDateStart=2025-01-01" | python3 -c 'import json, sys
d = sorted(json.load(sys.stdin), key=lambda r: r["RecallDate"], reverse=True)
print(len(d), "recalls")
for r in d: print(r["RecallNumber"], r["RecallDate"][:10], r["Products"][0]["NumberOfUnits"], "|", r["Hazards"][0]["Name"][:70], "|", r["RemedyOptions"][0]["Option"])'
sleep 1
# headers: JSON, CORS open, no cache, no rate-limit headers
curl -sS -A "$UA" -D - -o /dev/null "$R?format=json&RecallNumber=27082" | tr -d '\r' | grep -iE '^(HTTP/|content-type|access-control-allow-origin|cache-control|etag|last-modified|x-ratelimit|retry-after)'
sleep 1
# mistakes: Title is not a parameter (ignored: every recall since the date comes back); a bad date is HTTP 200 with an error record
curl -sS -A "$UA" -o /dev/null -w 'Title=fire pit -> HTTP %{http_code} %{size_download} B\n' "$R?format=json&Title=fire%20pit&RecallDateStart=2025-01-01"
sleep 1
curl -sS -A "$UA" "$R?format=json&RecallDateStart=2025-13-45" | head -c 150; echo

```

Output (from the run on 2026-11-18, 00:46 UTC):

```text
3 recalls
27082 2026-11-12 About 265,000 | Ignited flammable liquid can escape from the recalled fire pits or tri | Refund
26687 2026-08-13 About 48,700 | Use of the fire pits can result in uncontrolled pool fires where flame | Refund
25467 2025-09-18 About 66,000 | Alcohol fuel can splash or leak out of the fire pit reservoir during u | Refund
HTTP/2 200 
content-type: application/json; charset=utf-8
access-control-allow-origin: *
cache-control: no-cache
Title=fire pit -> HTTP 200 2924873 B
[{"RecallID":0,"RecallNumber":null,"RecallDate":null,"Description":null,"URL":null,"Title":"Error retrieving Recalls: An error occurred while reading 
```

## Fields (Recall API, format=json)

Each record has these single values and arrays (all arrays are present, possibly empty):

| Field | Example (26639) | Notes |
|---|---|---|
| `RecallNumber` | `"26639"` | string, 5 digits; the first two follow an October-September year (25xxx: 2025-01-02 to 2025-09-25, 26xxx: 2025-10-02 to 2026-09-24, 27xxx: from 2026-10-01), like the year folder in `URL` |
| `RecallID` | `10880` | internal id; `0` only on the error record |
| `RecallDate` | `"2026-07-23T00:00:00"` | date of the recall; no time zone, time always 00:00:00 |
| `LastPublishDate` | `"2026-07-24T00:00:00"` | not defined in the Guide; `LastPublishDateStart=2026-11-10` returned 20 records recalled as far back as 1998, all with `LastPublishDate` 2026-11-10 or later, so use it to catch recently republished old recalls |
| `Title` | `"Peony Design Recalls ... Due to Risk of Serious Injury or Death from Choking Hazard"` | can be another recall's title (5 of 941 since 2025); the notice page's heading is authoritative |
| `URL` | `https://www.cpsc.gov/Recalls/2026/Peony-Design-Recalls-...` | the official notice; host `www.cpsc.gov` or `cpsc.gov`, and one record has `https:/www.cpsc.gov` |
| `Description`, `ConsumerContact` | free text | |
| `Products[]` | `Name` `"Personalized Baby Bibs and Stroller Bags"`, `NumberOfUnits` `"About 52"`, `Model`, `Type`, `CategoryID`, `Description` | exactly 1 product in each of the 941 records since 2025; `Model` was empty in all of them |
| `Hazards[]` | `Name` "The snap can detach ...", `HazardType`, `HazardTypeID` | `HazardType` was empty in every record checked |
| `Remedies[]` | `Name` "Consumers should ... contact Peony Design to receive a full refund ..." | the instructions |
| `RemedyOptions[]` | `Option` `"Refund"` | since 2025: Refund 628, Repair 197, Replace 161, a few others; 45 records have 2 or 3 options |
| `Injuries[]` | `Name` "The firm received three reported incidents ... No injuries have been reported." | |
| `Manufacturers[]`, `Importers[]`, `Distributors[]`, `Retailers[]` | `Name` `"Peony Design Co., of Howell, MI"` | `Retailers[].Name` is a sentence with where, when and price ("Online at Etsy.com from October 2025 through July 2026 for between $15 and $45.") |
| `Images[]` | `URL`, `Caption` | recall photos on cpsc.gov; may be copied with the notice |
| `ManufacturerCountries[]`, `ProductUPCs[]`, `Inconjunctions[]` | `Country` `"United States"` | UPCs on 28 of 941 records since 2025 |

## Gotchas

- **Two search fields, merge them.** For "stroller" since 2025, `ProductName` gives 6 and `RecallTitle` 9; `RecallTitle` adds a real stroller recall (26094), a wagon that "Violates Mandatory Standard for Strollers" (26044) and one false hit through a wrong title (26569). Print the product name and let the reader judge (block 1).
- **Matching is a case-insensitive substring, on parameter names too.** `productname=STROLLER` works; `stroll` would also match "Pack-N-Stroll". `RecallNumber=2663` returns 26630-26639: compare the number exactly (block 3).
- **Unknown names are ignored, not rejected.** `Title=` and `Foo=` return everything for the other filters. `Hazard=choking` returns `[]` (0 records, also without a date filter) even though 62 hazard texts since 2025 mention choking. The Programmer's Guide (p. 3) documents `RecallTitle=stroller&Hazard=pinch` as the list of recalls with `hazard containing "pinch"`, but that exact query returns `[]` too, although 4 `RecallTitle=stroller` records (17057, the Guide's own sample record, 16163, 15032, 01056) have "pinch" in `Hazards[].Name`. It seems to match the empty `HazardType`, so filter `Hazards[].Name` yourself.
- **Errors are HTTP 200.** `RecallDateStart=not-a-date` and `2025-13-45` return a one-element list with `RecallID` 0 and `Title` "Error retrieving Recalls: An error occurred while reading from the store provider's data reader ...". `01/01/2025` was accepted as a date.
- **Order.** The Programmer's Guide promises no order. All 17 multi-record lists in this run (up to 941 records, back to 1977) came newest first by `RecallDate`, with no fixed order within one day; the blocks sort anyway.
- **`NumberOfUnits` is text.** 730 of 941 since 2025 are "About N"; others read "About 3,840 (In addition, about 148 were sold in Canada)", "5.9 million" (27055), "About 2.3 million", "4,726 (In addition, 2,261 were sold in Canada)" or note units recalled before. Keep the text; parse only the leading figure for the US count.
- **Wrong titles.** Since 2025, 26569, 26554, 26227, 26069 and 25236 have a `Title` that belongs, wholly or partly, to another recall (26227 is pools, titled as Hobby Lobby plush toys). The `URL` and the product fields are right. Block 1's `title_ok()` also flags 26334, whose URL has a typo ("RecallAmazon"), and many pre-2010 notices whose URLs were worded differently.
- **HTTP 403 on the HTML pages.** From this Linux server, cpsc.gov robots.txt and notice pages, and SaferProducts.gov HTML, answered HTTP 403 "Access Denied" to some user agents (browser-like ones among them); the Recall API answered 200 to every user agent tried. Treat a 403 as blocked: do not switch user agents to get past it. The urllib and curl blocks (3 and 4) send one fixed, descriptive user agent to the API and to robots.txt; the browser blocks (1 and 2) use the browser's own user agent, and cpsc.gov pages are read only in the browser (block 2).
- **Big answers.** All recalls since 2025-01-01 is 941 records, 2.9 MB, 0.1 to 0.9 s in 3 curl calls from this Linux server (2026-11-17, 23:44-23:50 UTC). Narrow by date and name.
- **Tab marker.** The harness sets the tab title to a horse emoji; the blocks check `location.origin`, never the title.

## What does not work

- **`Hazard=`** as a text search (returns nothing, see Gotchas), and server-side sorting or paging (no such parameters in the Guide; none tried).
- **The cpsc.gov recall search** (`/Recalls?search=...`): robots.txt disallows those query URLs for every agent. Use the API.
- **Not tested:** the `/RestWebServices/RecallDelimited` variant the Guide describes (collections flattened into pipe-separated values), a request with no filter at all (the whole database), rate-limit behaviour (never provoked), and the other filters (`UPC`, `Manufacturer`, `Retailer`, `ProductModel` and more) beyond what block 2 shows.
- **No match is not proof of safety.** The API holds CPSC recalls only. CPSC's "Products Under the Jurisdiction of Other Federal Agencies" page (https://www.cpsc.gov/Regulations-Laws--Standards/Products-Outside-CPSCs-Jurisdiction) says "automobiles, trucks, and motorcycles are under the jurisdiction of the Department of Transportation; food, drugs (except for child resistant-packaging for these products), and cosmetics are mainly covered by the Food and Drug Administration".
