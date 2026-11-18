# RxNorm API (rxnav.nlm.nih.gov) - Normalize a Drug Name to Its RxCUI and List Its Brands, Strengths and Dose Forms (REST API, no key)

Field-tested against rxnav.nlm.nih.gov on 2026-11-15 (US Pacific; the logged run was 04:35-04:40 UTC on 2026-11-16) using a fresh Browser Use cloud browser (logged out) plus Python `urllib` and `curl` from a Linux machine. 7 browser page loads (API JSON pages and both robots files) and 94 in-page `fetch()` calls (block 1 was also run for Lipitor, atorvastatin calcium, Caduet, metformin, acetaminophen and ibuprofen while building it), 58 curl calls and 25 urllib calls (2 of them robots.txt) to rxnav.nlm.nih.gov, all serial at 0.25 s or more spacing: every call was HTTP 200 except the deliberate HTTP 400 probes and the HTTP 404 of rxnav's robots.txt. No 429, no challenge, no key, no login.

robots.txt (checked 2026-11-15, curl, the cloud browser and `urllib.robotparser`): https://rxnav.nlm.nih.gov/robots.txt answers HTTP 404 `Not found`, so the API host has no rules and no named AI-agent groups; under RFC 9309 (section 2.3.1.3) an unavailable robots.txt (4xx) means a crawler "MAY access any resources", and Python's parser treats it as allow-all for GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider (block 3 checks all 11 agents). The docs host https://lhncbc.nlm.nih.gov/robots.txt has one group, `User-agent: *`, disallowing only file patterns (`/*.txt$`, `/*.sort$`, `/*.jout$`, `/*.out$`, `/*.xml$`, `/*.data$`); 0 named AI groups; the HTML doc pages linked here are allowed. Terms: https://lhncbc.nlm.nih.gov/RxNav/TermsofService.html says "RxNav and the RxNorm API provide non-proprietary content from RxNorm, developed by the National Library of Medicine" and "With one exception, no license is needed to use these APIs." The exception is SNOMED CT content in RxClass and the RxClass API ("subject to the SNOMED CT Affiliate license provisions"); this skill never calls RxClass. "The APIs (RxNorm, RxTerms, Prescribable RxNorm, and RxClass) may be used free-of-charge." "We invite you to develop computer and mobile applications using National Library of Medicine (NLM) resources, including our APIs". No AI/ML, scraping, automated-access or non-commercial clause. The same page: "DISCLAIMER: It is not the intention of NLM to provide specific medical advice ... NLM urges you to consult with a qualified physician for advice about medications." Naming: the terms say "Developers may not use the NLM name and/or logo in conjunction with their applications", so this skill names the source only as "RxNorm API (rxnav.nlm.nih.gov)" in plain text plus the statement NLM requests, uses no NLM, NIH or HHS logo or branding, and is not affiliated with or endorsed by NLM.

**Required statement:** the terms "request that any application that makes use of NLM data include the following statement": "This product uses publicly available data from the U.S. National Library of Medicine (NLM), National Institutes of Health, Department of Health and Human Services; NLM is not responsible for the product and does not endorse or recommend this or any other product." Blocks 1 and 3 print it; block 1 adds a source line (RxNorm data set version, the call, the access time) and a not-medical-advice line.

## Quick summary

- **No scraping.** `GET https://rxnav.nlm.nih.gov/REST/rxcui.json?name=atorvastatin&search=2` -> `{"idGroup":{"rxnormId":["83367"]}}`. `GET /REST/rxcui/83367/related.json?tty=BN+SCD` returns the brand names and clinical drugs in one call. `/REST/drugs.json?name=atorvastatin` gives the same products grouped as branded (SBD) and clinical (SCD). No key, `access-control-allow-origin: *`.
- **Answer (RxNorm data set 02-Nov-2026, API 3.1.357; run 2026-11-16, 04:38 UTC):** atorvastatin is **RxCUI 83367** (term type IN, ingredient). **Brand names: Lipitor (153165), Atorvaliq (2631862) and Caduet (404914)**; Caduet is a combination with amlodipine. **19 clinical drugs (SCD)**: 5 are atorvastatin alone, **Oral Tablet 10, 20, 40 and 80 MG and Oral Suspension 4 MG/ML**; 14 are combinations (11 amlodipine / atorvastatin tablets, 3 atorvastatin / ezetimibe tablets). Branded: Lipitor 10/20/40/80 MG Oral Tablet, Atorvaliq 4 MG/ML Oral Suspension, 8 Caduet tablets (13 SBD).
- **Ingredient lists include combinations.** `related.json?tty=BN` for an ingredient returns every brand that contains it (Caduet) and `tty=SCD` every clinical drug that contains it. Split them: block 1 treats an SCD or SBD name with " / " as a combination and checks each single-ingredient strength against RxNorm's own strength components (SCDC) and dose forms (DF).
- **Names normalize to different concept types.** "Lipitor" is BN 153165, "atorvastatin calcium" is PIN 83366 (precise ingredient), "paracetamol" is IN 161 (acetaminophen), and all map to one ingredient with `related.json?tty=IN`. "Caduet" maps to 2 ingredients; block 1 stops and asks for one.
- **Silent failure:** a typo (`atorvastatn`) is HTTP 200 `{"idGroup":{}}` with the default `search=0` and with `search=2`; only `search=9` (approximate) finds 83367. An unknown RxCUI is HTTP 200 with an empty group. A missing name or unknown `tty` is a plain-text HTTP 400 `Path or Query Parameter error`.
- **Rate limit:** the terms say "no more than 20 requests per second per IP address"; above it, "Requests ... may not be serviced, and service will not be restored until the request rate falls beneath the limit." NLM "recommends caching results for a 12-24 hour period". An optional UMLS (UTS) API key sent as `Authorization: Bearer <key>` raises the limit to 100 requests per second; it is not needed here. All blocks pace 0.25 s per call, serial; blocks 1 and 3 wait 60 s once on 429/5xx; block 3 caches answers on disk for 12 h.

## What works

### 1. Name -> RxCUI -> brands, strengths and dose forms (browser)

`on_rxnav_tab()` opens one logged-out rxnav.nlm.nih.gov JSON page (`/REST/version.json`), so `fetch()` is same-origin. `get()` returns parsed JSON and headers on HTTP 200, waits 60 s once on 429/500/502/503/504 and otherwise raises. `normalize()` tries exact-or-normalized matching first and approximate matching only as a flagged fallback, then maps a brand or salt to its one ingredient. One `related.json` call fetches brands (BN), branded drugs (SBD), clinical drugs (SCD), strength components (SCDC) and dose forms (DF); `parse_scd()` cuts each SCD name with those DF and SCDC names and stops if one does not fit. 4 `fetch()` calls for atorvastatin.

```python
import json, re, time, urllib.parse
from datetime import datetime, timezone

NAME = "atorvastatin"   # any drug name: ingredient, salt ("atorvastatin calcium") or brand ("Lipitor")

SITE = "https://rxnav.nlm.nih.gov"
API = SITE + "/REST"
PAUSE = 0.25  # NLM: "no more than 20 requests per second per IP address". Stay serial and far below it.
TTYS = "BN+SBD+SCD+SCDC+DF"  # brand names, branded drugs, clinical drugs, their strengths, dose forms

def on_rxnav_tab():
    """fetch() runs same-origin from a logged-out rxnav.nlm.nih.gov JSON page. Reuse it."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(API + "/version.json")
    wait_for_load()
    body = js("document.body ? document.body.innerText : ''") or ""
    if js("location.origin") != SITE or '"apiVersion"' not in body:
        raise RuntimeError(f"rxnav.nlm.nih.gov did not serve /REST/version.json (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit', headers: {Accept: 'application/json'}})
    .then(async r => { const h = {}; r.headers.forEach((v, k) => { h[k] = v; });
      window.__u[id] = {status: r.status, url: r.url, headers: h, text: await r.text()}; })
    .catch(e => { window.__u[id] = {status: 0, url: '', headers: {}, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

def get(path, timeout=60):
    """GET API+path from inside the tab -> (parsed JSON, headers). Waits 60 s once on 429/500/502/503/504 or a network
    error, raises on anything else (400 = "Path or Query Parameter error", plain text)."""
    for attempt in range(2):
        rid = json.dumps(js(START_JS % json.dumps(API + path)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"{path}: no answer after {timeout}s")
            time.sleep(0.2)
        time.sleep(PAUSE)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(60)
            continue
        if r["status"] != 200 or "json" not in r["headers"].get("content-type", ""):
            raise RuntimeError(f"{path}: HTTP {r['status']} {' '.join(r['text'].split())[:200]!r}; stopping")
        return json.loads(r["text"]), r["headers"]

def related(rxcui, ttys):
    """/rxcui/<rxcui>/related.json?tty=... -> {tty: [concept, ...]} (a tty with no concepts maps to [])."""
    d, _ = get(f"/rxcui/{rxcui}/related.json?tty={ttys}")
    return {g["tty"]: g.get("conceptProperties", []) for g in (d.get("relatedGroup") or {}).get("conceptGroup") or []}

def normalize(name):
    """Drug name -> (ingredient concept, the chain of steps). search=2 is exact, then normalized (salts, word order);
    only if that finds nothing, search=9 (approximate) is tried and flagged, because it can pick the wrong drug."""
    steps = []
    for search, how in ((2, "exact or normalized"), (9, "APPROXIMATE, check it")):
        d, _ = get("/rxcui.json?" + urllib.parse.urlencode({"name": name, "search": search}))
        ids = d["idGroup"].get("rxnormId", [])
        if ids:
            break
    if not ids:
        raise RuntimeError(f"{name!r}: no RxCUI, not even an approximate one: check the spelling")
    if len(ids) > 1:
        steps.append(f"{len(ids)} RxCUIs {ids}, best first; using {ids[0]}")
    p = get(f"/rxcui/{ids[0]}/properties.json")[0]["properties"]
    steps.append(f"{name!r} -> RxCUI {p['rxcui']} ({how} match), tty {p['tty']} {p['name']!r}")
    if p["tty"] == "IN":
        return p, steps
    ins = related(p["rxcui"], "IN").get("IN", [])
    if len(ins) != 1:
        raise RuntimeError(f"{p['name']!r} ({p['tty']}) maps to {len(ins)} ingredients {[c['name'] for c in ins]}: "
                           "pick one ingredient name and run again")
    steps.append(f"{p['tty']} {p['rxcui']} -> ingredient RxCUI {ins[0]['rxcui']} {ins[0]['name']!r}")
    return ins[0], steps

def strength_key(s):
    """Sort "4 MG/ML" and "10 MG" by unit, then by number."""
    num, unit = s.split(" ")[:2]
    return unit, float(num), s

on_rxnav_tab()
now = datetime.now(timezone.utc)
ver = get("/version.json")[0]

ing, steps = normalize(NAME)
rx, iname = ing["rxcui"], ing["name"]
g = related(rx, TTYS)
for tty in TTYS.split("+"):
    if tty not in g:
        raise RuntimeError(f"related.json left out tty {tty}: the response shape changed, stop")
dfs = sorted((c["name"] for c in g["DF"]), key=len, reverse=True)       # longest first: "Extended Release Oral Tablet"
comps = sorted((c["name"] for c in g["SCDC"]), key=len, reverse=True)  # "atorvastatin 10 MG", "metformin hydrochloride 500 MG"
STRENGTH = r"[\d.]+ \S+"                                                 # 10 MG, 4 MG/ML, 100 UNT/ML, 20 MEQ: unit = one token

def parse_scd(name, strict=True):
    """SCD name = [prefix ]<component>[ / <component> ...] <dose form>. The prefix is a release time or pack volume
    ("24 HR", "Osmotic 24 HR", "2 ML"); a component is "<ingredient or its salt> <strength>". Uses RxNorm's own dose
    forms (DF) and components (SCDC) to cut the name, and stops if they do not fit."""
    df = next((f for f in dfs if name.endswith(" " + f)), None)
    if df is None:
        raise RuntimeError(f"SCD {name!r} ends in no dose form RxNorm listed {dfs}: stop")
    parts = name[: -len(df) - 1].split(" / ")
    ings = [m[1] if (m := re.search(rf"\b([a-z][^/]*?) {STRENGTH}$", p.strip())) else p for p in parts]
    if len(parts) > 1 or not strict:
        return df, None, None, ings
    comp = next((c for c in comps if parts[0] == c or parts[0].endswith(" " + c)), None)
    if comp is None:
        raise RuntimeError(f"SCD {name!r}: no SCDC component of {iname!r} fits: stop")
    return df, parts[0][: -len(comp)].strip(), comp, ings

single, combos, used = {}, {}, set()
for c in g["SCD"]:
    df, prefix, comp, ings = parse_scd(c["name"])
    if comp is None:
        combos.setdefault((" / ".join(ings), df), []).append(c["rxcui"])
        continue
    used.add(comp)
    m = re.search(STRENGTH + "$", comp)
    if m is None:
        raise RuntimeError(f"SCDC {comp!r} does not end in '<number> <unit>': stop")
    strength = m[0]
    single.setdefault(df, []).append((strength + (f" ({prefix})" if prefix else ""), c["rxcui"]))

# Brands: a brand name (BN) is single-ingredient if its branded drugs (SBD, "... [Lipitor]") have no " / ".
brands = []
for b in g["BN"]:
    sbd = [c for c in g["SBD"] if c["name"].endswith(f" [{b['name']}]")]
    other = sorted({i for c in sbd for i in parse_scd(c["name"][: -len(b["name"]) - 3], strict=False)[3]
                    if not i.startswith(iname)})  # drop the ingredient itself and its salt ("metformin hydrochloride")
    brands.append((b, other, sorted(c["synonym"] or c["name"] for c in sbd)))

print(f"RxNorm data set {ver['version']} (API {ver['apiVersion']}), queried {now:%Y-%m-%d %H:%M} UTC")
for s in steps:
    print("  " + s)
n1 = sum(len(v) for v in single.values())
print(f"\nBrand names (BN): {len(g['BN'])}, {sum(1 for x in brands if x[2] and not x[1])} of them {iname} only")
for b, other, sbd in sorted(brands, key=lambda x: (bool(x[1]), x[0]["name"].lower())):  # single-ingredient first
    kind = "no branded drug (SBD) listed" if not sbd else "single ingredient" if not other else "combination with " + ", ".join(other)
    print(f"  {b['name']:<10} RxCUI {b['rxcui']:<8} {kind}; {len(sbd)} branded drug(s) (SBD)")
    if sbd and not other:
        for s in sbd:
            print(f"    {s}")
print(f"\nClinical drugs (SCD): {len(g['SCD'])} = {n1} {iname} only + {len(g['SCD']) - n1} combination products")
for df in sorted(single):
    v = sorted(single[df], key=lambda x: strength_key(x[0]))
    print(f"  {df}: " + ", ".join(f"{s} [{r}]" for s, r in v))
for (ings, df), ids in sorted(combos.items(), key=lambda kv: (-len(kv[1]), kv[0])):
    print(f"  {ings} {df}: {len(ids)} strength combination(s)")
print(f"  {len(used)} of {len(comps)} strength components (SCDC) occur in {iname}-only drugs"
      + ("" if len(used) == len(comps) else f"; {sorted(set(comps) - used)} only in combinations"))
print(f"\nSource: RxNorm API (rxnav.nlm.nih.gov), RxNorm {ver['version']}, {API}/rxcui/{rx}/related.json?tty={TTYS}, "
      f"accessed {now:%d %B %Y %H:%M} UTC.")
print("This product uses publicly available data from the U.S. National Library of Medicine (NLM), National Institutes "
      "of Health, Department of Health and Human Services; NLM is not responsible for the product and does not endorse "
      "or recommend this or any other product.")
print("Drug vocabulary, not medical advice: ask a physician or pharmacist about any medication.")
```

Output (from the run on 2026-11-16, 04:38 UTC):

```text
RxNorm data set 02-Nov-2026 (API 3.1.357), queried 2026-11-16 04:38 UTC
  'atorvastatin' -> RxCUI 83367 (exact or normalized match), tty IN 'atorvastatin'

Brand names (BN): 3, 2 of them atorvastatin only
  Atorvaliq  RxCUI 2631862  single ingredient; 1 branded drug(s) (SBD)
    Atorvaliq 4 MG/ML Oral Suspension
  Lipitor    RxCUI 153165   single ingredient; 4 branded drug(s) (SBD)
    Lipitor 10 MG Oral Tablet
    Lipitor 20 MG Oral Tablet
    Lipitor 40 MG Oral Tablet
    Lipitor 80 MG Oral Tablet
  Caduet     RxCUI 404914   combination with amlodipine; 8 branded drug(s) (SBD)

Clinical drugs (SCD): 19 = 5 atorvastatin only + 14 combination products
  Oral Suspension: 4 MG/ML [2630760]
  Oral Tablet: 10 MG [617312], 20 MG [617310], 40 MG [617311], 80 MG [259255]
  amlodipine / atorvastatin Oral Tablet: 11 strength combination(s)
  atorvastatin / ezetimibe Oral Tablet: 3 strength combination(s)
  5 of 5 strength components (SCDC) occur in atorvastatin-only drugs

Source: RxNorm API (rxnav.nlm.nih.gov), RxNorm 02-Nov-2026, https://rxnav.nlm.nih.gov/REST/rxcui/83367/related.json?tty=BN+SBD+SCD+SCDC+DF, accessed 16 November 2026 04:38 UTC.
This product uses publicly available data from the U.S. National Library of Medicine (NLM), National Institutes of Health, Department of Health and Human Services; NLM is not responsible for the product and does not endorse or recommend this or any other product.
Drug vocabulary, not medical advice: ask a physician or pharmacist about any medication.
```

The same block with `NAME = "metformin"` (same day) shows why the parser uses SCDC and DF instead of a fixed pattern: SCD names there carry a prefix and the salt name, for example "Osmotic 24 HR metformin hydrochloride 500 MG Extended Release Oral Tablet". It printed 14 brand names (3 metformin only: Glucophage, Glumetza, Riomet), 76 SCD = 12 metformin only + 64 combinations, and "6 of 7 strength components (SCDC) occur in metformin-only drugs; ['metformin hydrochloride 250 MG'] only in combinations". A brand or salt input adds one mapping step before the same answer: blocks 2 and 3 show "Lipitor" (BN 153165) and "atorvastatin calcium" (PIN 83366) both mapping to ingredient 83367, and block 3 gets 3 BN and 19 SCD for each.

### 2. robots.txt, name variants and query mistakes (browser)

3 page loads and 18 in-page `fetch()` calls in the same tab.

```python
import json, time

SITE = "https://rxnav.nlm.nih.gov"
API = SITE + "/REST"

START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { const t = await r.text(); window.__u[id] = {status: r.status, type: r.headers.get('content-type') || '',
      bytes: t.length, text: t}; })
    .catch(e => { window.__u[id] = {status: 0, type: '', bytes: 0, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

def raw(path):
    """One in-page GET -> status, content type, size and body. No retries: this block only inspects answers."""
    rid = json.dumps(js(START_JS % json.dumps(API + path)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{path}: no answer after 60s")
        time.sleep(0.2)
    time.sleep(0.25)
    return r

def brief(r):
    out = f"HTTP {r['status']}"
    if "json" not in r["type"]:
        return out + f" {r['type'].split(';')[0]} {' '.join(r['text'].split())[:70]!r}"
    d = json.loads(r["text"])
    if "idGroup" in d:
        return out + f" rxnormId {d['idGroup'].get('rxnormId', 'MISSING (no match)')}"
    if "properties" in d:
        p = d["properties"]
        return out + f" {p['rxcui']} tty {p['tty']} {p['name']!r}"
    if "relatedGroup" in d:
        gs = d["relatedGroup"].get("conceptGroup") or []
        return out + " " + ", ".join(f"{g['tty']}: {[c['name'] for c in g.get('conceptProperties', [])][:3]}" for g in gs)
    if "suggestionGroup" in d:
        return out + f" suggestions {((d['suggestionGroup'].get('suggestionList') or {}).get('suggestion'))}"
    if "drugGroup" in d:
        gs = d["drugGroup"].get("conceptGroup") or []
        return out + " " + (", ".join(f"{g['tty']} {len(g.get('conceptProperties', []))}" for g in gs) or "no conceptGroup")
    return out + " " + r["text"][:80]

def page(url):
    goto_url(url)
    wait_for_load()
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    return st, js("document.body ? document.body.innerText : ''")

try:
    on_site = js("location.origin") == SITE
except Exception:
    on_site = False
if not on_site:
    new_tab(API + "/version.json")
    wait_for_load()

for url in (SITE + "/robots.txt", "https://lhncbc.nlm.nih.gov/robots.txt"):
    st, txt = page(url)
    lines = [l for l in txt.strip().splitlines() if l.strip() and not l.startswith("#")]
    print(f"{url} HTTP {st}: " + (" | ".join(lines) if len(lines) < 12 else f"{len(lines)} lines"))
page(API + "/version.json")  # back to an rxnav JSON page for same-origin fetch()
print()

for label, path in (
    ("exact, any case: ATORVASTATIN     ", "/rxcui.json?name=ATORVASTATIN"),
    ("salt: atorvastatin calcium        ", "/rxcui.json?name=atorvastatin%20calcium&search=2"),
    ("  -> its ingredient               ", "/rxcui/83366/related.json?tty=IN"),
    ("brand: Lipitor                    ", "/rxcui.json?name=Lipitor&search=2"),
    ("  -> its ingredient               ", "/rxcui/153165/related.json?tty=IN"),
    ("combination brand: Caduet         ", "/rxcui/404914/related.json?tty=IN"),
    ("non-US name: paracetamol          ", "/rxcui.json?name=paracetamol&search=2"),
    ("typo atorvastatn, search=0 (def.) ", "/rxcui.json?name=atorvastatn"),
    ("typo atorvastatn, search=2        ", "/rxcui.json?name=atorvastatn&search=2"),
    ("typo atorvastatn, search=9 approx ", "/rxcui.json?name=atorvastatn&search=9"),
    ("typo, spellingsuggestions         ", "/spellingsuggestions.json?name=atorvastatn"),
    ("typo, drugs.json                  ", "/drugs.json?name=atorvastatn"),
    ("drugs.json?name=atorvastatin      ", "/drugs.json?name=atorvastatin"),
    ("drugs.json?name=Lipitor           ", "/drugs.json?name=Lipitor"),
    ("empty name                        ", "/rxcui.json?name="),
    ("unknown tty=XYZ                   ", "/rxcui/83367/related.json?tty=XYZ"),
    ("unknown rxcui 99999999            ", "/rxcui/99999999/related.json?tty=BN"),
    ("no .json suffix                   ", "/rxcui?name=atorvastatin"),
):
    print(f"{label} {brief(raw(path))}")
```

Output (from the run on 2026-11-16, 04:39 UTC):

```text
https://rxnav.nlm.nih.gov/robots.txt HTTP 404: Not found
https://lhncbc.nlm.nih.gov/robots.txt HTTP 200: User-agent: * | Disallow: /*.txt$ | Disallow: /*.sort$ | Disallow: /*.jout$ | Disallow: /*.out$ | Disallow: /*.xml$ | Disallow: /*.data$

exact, any case: ATORVASTATIN      HTTP 200 rxnormId ['83367']
salt: atorvastatin calcium         HTTP 200 rxnormId ['83366']
  -> its ingredient                HTTP 200 IN: ['atorvastatin']
brand: Lipitor                     HTTP 200 rxnormId ['153165']
  -> its ingredient                HTTP 200 IN: ['atorvastatin']
combination brand: Caduet          HTTP 200 IN: ['amlodipine', 'atorvastatin']
non-US name: paracetamol           HTTP 200 rxnormId ['161']
typo atorvastatn, search=0 (def.)  HTTP 200 rxnormId MISSING (no match)
typo atorvastatn, search=2         HTTP 200 rxnormId MISSING (no match)
typo atorvastatn, search=9 approx  HTTP 200 rxnormId ['83367']
typo, spellingsuggestions          HTTP 200 suggestions ['atorvastatin']
typo, drugs.json                   HTTP 200 no conceptGroup
drugs.json?name=atorvastatin       HTTP 200 BPCK 0, GPCK 0, SBD 13, SCD 19
drugs.json?name=Lipitor            HTTP 200 BPCK 0, SBD 4
empty name                         HTTP 400 text/plain 'Path or Query Parameter error'
unknown tty=XYZ                    HTTP 400 text/plain 'Path or Query Parameter error'
unknown rxcui 99999999             HTTP 200 BN: []
no .json suffix                    HTTP 200 application/xml '<?xml version="1.0" ?><rxnormdata><idGroup><rxnormId>83367</rxnormId><'
```

### 3. Same lookup with Python urllib, robots check for every agent, 12 h disk cache (no browser)

Python's default `urllib` User-Agent was not tried for API calls; this block sends a descriptive one (the robots fetch inside `rp.read()` uses the default). The cache is a plain JSON file per URL, because NLM recommends caching for 12-24 hours. Run with an empty cache.

```python
import hashlib, json, os, sys, time, urllib.error, urllib.parse, urllib.request, urllib.robotparser

API = "https://rxnav.nlm.nih.gov/REST"
UA = "rxnorm-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]
CACHE_DIR = "~/.cache/rxnorm-skill"
CACHE = os.path.expanduser(CACHE_DIR)  # NLM "recommends caching results for a 12-24 hour period"
TTL = 12 * 3600
calls = hits = 0

def get(path):
    """GET API+path -> parsed JSON, from the disk cache when younger than TTL. One 60 s wait on 429/500/502/503/504 or
    a network error; exits on anything else (400 is a plain-text "Path or Query Parameter error")."""
    global calls, hits
    f = os.path.join(CACHE, hashlib.sha256(path.encode()).hexdigest() + ".json")
    try:
        if time.time() - os.path.getmtime(f) < TTL:
            hits += 1
            return json.load(open(f))
    except (OSError, ValueError):
        pass
    for attempt in range(2):
        time.sleep(0.25)  # limit is 20 requests/s per IP; stay serial and far below
        calls += 1
        try:
            req = urllib.request.Request(API + path, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(60)
                continue
            sys.exit(f"HTTP {e.code} {path}: {e.read().decode()[:200]}")
        except OSError as e:  # URLError (DNS, refused connection), timeouts, resets
            if attempt == 0:
                time.sleep(60)
                continue
            sys.exit(f"{path}: {e}")
    os.makedirs(CACHE, exist_ok=True)
    json.dump(d, open(f, "w"))
    return d

def related(rxcui, ttys):
    d = get(f"/rxcui/{rxcui}/related.json?tty={ttys}")
    return {g["tty"]: g.get("conceptProperties", []) for g in (d.get("relatedGroup") or {}).get("conceptGroup") or []}

def to_ingredient(name):
    """name -> (ingredient rxcui, ingredient name, note). Exact-or-normalized first, approximate only as a flagged
    fallback; a brand or salt is mapped to its single ingredient, a combination brand is refused."""
    for search in (2, 9):
        ids = get("/rxcui.json?" + urllib.parse.urlencode({"name": name, "search": search}))["idGroup"].get("rxnormId", [])
        if ids:
            break
    if not ids:
        return None, None, "no match"
    p = get(f"/rxcui/{ids[0]}/properties.json")["properties"]
    note = f"{p['tty']} {p['rxcui']} {p['name']!r}" + (" (APPROXIMATE)" if search == 9 else "")
    if p["tty"] == "IN":
        return p["rxcui"], p["name"], note
    ins = related(p["rxcui"], "IN").get("IN", [])
    if len(ins) != 1:
        return None, None, note + f" -> {len(ins)} ingredients {[c['name'] for c in ins]}: refused"
    return ins[0]["rxcui"], ins[0]["name"], note

# robots.txt: rxnav.nlm.nih.gov answers 404. RobotFileParser.read() treats a 4xx other than 401/403 as "allow all"
# (RFC 9309, section 2.3.1.3: unavailable robots.txt, the crawler MAY access any resources).
rp = urllib.robotparser.RobotFileParser("https://rxnav.nlm.nih.gov/robots.txt")
try:
    urllib.request.urlopen(urllib.request.Request(rp.url, headers={"User-Agent": UA}), timeout=30)
    print("rxnav robots.txt now exists: read it before going on")
except urllib.error.HTTPError as e:
    print(f"rxnav robots.txt: HTTP {e.code}")
rp.read()
paths = ["/REST/rxcui.json?name=x", "/REST/drugs.json?name=x", "/REST/rxcui/83367/related.json?tty=BN+SCD"]
for p in paths:
    ok = all(rp.can_fetch(a, "https://rxnav.nlm.nih.gov" + p) for a in AGENTS)
    print(f"robots {p:<44} {'allowed' if ok else 'DISALLOWED'} for all {len(AGENTS)} agents")
    if not ok:
        sys.exit("robots.txt now disallows a path this skill uses: stop")

print(f"\nRxNorm data set {get('/version.json')['version']}")
for name in ["atorvastatin", "Lipitor", "atorvastatin calcium", "paracetamol", "Tylenol", "atorvastatn", "Caduet", "xyzzy"]:
    rx, iname, note = to_ingredient(name)
    if rx is None:
        print(f"  {name!r:<24} {note}")
        continue
    g = related(rx, "BN+SCD")
    one = [c for c in g.get("SCD", []) if " / " not in c["name"]]
    print(f"  {name!r:<24} {note} -> IN {rx} {iname!r}: {len(g.get('BN', []))} BN, {len(g.get('SCD', []))} SCD "
          f"({len(one)} single-ingredient)")

n1 = calls
for name in ["atorvastatin", "Lipitor", "atorvastatin calcium"]:
    to_ingredient(name)
print(f"\nnetwork calls {n1}, then {calls - n1} more for 3 repeated names (cache hits so far: {hits}, cache {CACHE_DIR})")
print("This product uses publicly available data from the U.S. National Library of Medicine (NLM), National Institutes "
      "of Health, Department of Health and Human Services; NLM is not responsible for the product and does not endorse "
      "or recommend this or any other product.")
```

Output (from the run on 2026-11-16, 04:39 UTC):

```text
rxnav robots.txt: HTTP 404
robots /REST/rxcui.json?name=x                      allowed for all 11 agents
robots /REST/drugs.json?name=x                      allowed for all 11 agents
robots /REST/rxcui/83367/related.json?tty=BN+SCD    allowed for all 11 agents

RxNorm data set 02-Nov-2026
  'atorvastatin'           IN 83367 'atorvastatin' -> IN 83367 'atorvastatin': 3 BN, 19 SCD (5 single-ingredient)
  'Lipitor'                BN 153165 'Lipitor' -> IN 83367 'atorvastatin': 3 BN, 19 SCD (5 single-ingredient)
  'atorvastatin calcium'   PIN 83366 'atorvastatin calcium' -> IN 83367 'atorvastatin': 3 BN, 19 SCD (5 single-ingredient)
  'paracetamol'            IN 161 'acetaminophen' -> IN 161 'acetaminophen': 79 BN, 400 SCD (55 single-ingredient)
  'Tylenol'                BN 202433 'Tylenol' -> IN 161 'acetaminophen': 79 BN, 400 SCD (55 single-ingredient)
  'atorvastatn'            IN 83367 'atorvastatin' (APPROXIMATE) -> IN 83367 'atorvastatin': 3 BN, 19 SCD (5 single-ingredient)
  'Caduet'                 BN 404914 'Caduet' -> 2 ingredients ['amlodipine', 'atorvastatin']: refused
  'xyzzy'                  no match

network calls 23, then 0 more for 3 repeated names (cache hits so far: 13, cache ~/.cache/rxnorm-skill)
This product uses publicly available data from the U.S. National Library of Medicine (NLM), National Institutes of Health, Department of Health and Human Services; NLM is not responsible for the product and does not endorse or recommend this or any other product.
```

### 4. curl, headers and mistakes

```bash
R=https://rxnav.nlm.nih.gov/REST
# name -> RxCUI (search=2: exact, then normalized)
curl -sS --fail "$R/rxcui.json?name=atorvastatin&search=2"; echo
sleep 0.25
# brands and clinical drugs in one call; tty is a "+"-separated list
curl -sS --fail "$R/rxcui/83367/related.json?tty=BN+SCD" \
  | python3 -c 'import json,sys; g={x["tty"]: x.get("conceptProperties", []) for x in json.load(sys.stdin)["relatedGroup"]["conceptGroup"]}; print("BN:", ", ".join(c["name"] for c in g["BN"])); print(len(g["SCD"]), "SCD, single-ingredient:", "; ".join(sorted(c["name"] for c in g["SCD"] if " / " not in c["name"])))'
sleep 0.25
# drugs.json groups the same products by term type (SBD = branded, SCD = clinical)
curl -sS --fail "$R/drugs.json?name=atorvastatin" \
  | python3 -c 'import json,sys; print({g["tty"]: len(g.get("conceptProperties", [])) for g in json.load(sys.stdin)["drugGroup"]["conceptGroup"]})'
sleep 0.25
# data set version, caching and CORS headers
curl -sS "$R/version.json"; echo
sleep 0.25
curl -sS -D - -o /dev/null "$R/rxcui/83367/related.json?tty=BN+SCD" | tr -d '\r' \
  | grep -iE '^(HTTP/|(content-type|cache-control|etag|access-control-allow-origin|x-rate-tier):)'
sleep 0.25
# mistakes: a typo is a silent HTTP 200 with no rxnormId; a bad parameter is a plain-text 400
curl -sS -w ' <- HTTP %{http_code}\n' "$R/rxcui.json?name=atorvastatn&search=2"
sleep 0.25
curl -sS -w ' <- HTTP %{http_code}\n' "$R/rxcui/83367/related.json?tty=XYZ"
```

Output (from the run on 2026-11-16, 04:40 UTC):

```text
{"idGroup":{"rxnormId":["83367"]}}
BN: Lipitor, Atorvaliq, Caduet
19 SCD, single-ingredient: atorvastatin 10 MG Oral Tablet; atorvastatin 20 MG Oral Tablet; atorvastatin 4 MG/ML Oral Suspension; atorvastatin 40 MG Oral Tablet; atorvastatin 80 MG Oral Tablet
{'BPCK': 0, 'GPCK': 0, 'SBD': 13, 'SCD': 19}
{"version":"02-Nov-2026","apiVersion":"3.1.357"}
HTTP/2 200 
content-type: application/json;charset=utf-8
etag: W/"20AA_261102F;1793130400;3.1.357"
cache-control: public, max-age=300, must-revalidate
access-control-allow-origin: *
x-rate-tier: std
{"idGroup":{}} <- HTTP 200
Path or Query Parameter error <- HTTP 400
```

## Fields (rxcui, related, drugs, version)

| Call | JSON path | Notes |
|---|---|---|
| `/REST/rxcui.json?name=...&search=2` | `idGroup.rxnormId[]` | RxCUIs as strings, best match first; key missing when nothing matched (HTTP 200). `search`: 0 exact (default, case ignored), 1 normalized ("Word order, punctuation, suffixes ... and salts forms are ignored"), 2 exact then normalized, 9 approximate (https://lhncbc.nlm.nih.gov/RxNav/APIs/api-RxNorm.findRxcuiByString.html) |
| `/REST/rxcui/<rxcui>/properties.json` | `properties.{rxcui,name,tty,synonym,suppress}` | tells you what the name matched: IN 83367 atorvastatin, PIN 83366 atorvastatin calcium, BN 153165 Lipitor |
| `/REST/rxcui/<rxcui>/related.json?tty=A+B` | `relatedGroup.conceptGroup[].{tty, conceptProperties[]}` | one group per requested tty; a group with no concepts has no `conceptProperties` key. Each concept: `rxcui`, `name`, `synonym`, `tty`, `language`, `suppress`, `umlscui`; `&expand=psn` adds `psn` (Prescribable Name) to concepts that have one (each SCD here; no BN concept got it) |
| tty `IN`, `PIN`, `MIN` | | ingredient, precise ingredient (salt), multiple ingredients (the term types named on the getDrugs doc page) |
| tty `BN` | | brand name (Lipitor). Includes combination brands (Caduet) |
| tty `SCD`, `SBD` | | clinical drug "atorvastatin 10 MG Oral Tablet"; branded drug "atorvastatin 10 MG Oral Tablet [Lipitor]" with `synonym` "Lipitor 10 MG Oral Tablet" |
| tty `SCDC`, `DF`, `SCDF` | | strength component "atorvastatin 10 MG"; dose form "Oral Tablet"; clinical drug form "atorvastatin Oral Tablet" |
| `/REST/drugs.json?name=...` | `drugGroup.conceptGroup[]` | groups BPCK, GPCK, SBD, SCD for an ingredient name (13 SBD, 19 SCD here); for a brand name only BPCK and SBD (4 for Lipitor); `{"drugGroup":{"name":null}}` for a typo |
| `/REST/version.json` | `version`, `apiVersion` | "02-Nov-2026", "3.1.357"; the `etag` header carries `261102` and `3.1.357` too |
| response headers | `cache-control`, `etag`, `access-control-allow-origin`, `x-rate-tier` | `public, max-age=300, must-revalidate`; `W/"20AA_261102F;1793130400;3.1.357"`; `*`; `std` (keyless here) |

## Gotchas

- **Quote the data set version.** RxNorm content changes with each release; `version.json` said 02-Nov-2026 here, and NLM's Technical Bulletin lists "RxNorm November 2026 Monthly Release" dated 2026-11-02. Concepts are added and retired between releases: `/REST/rxcui/2631862/historystatus.json` shows Atorvaliq active since `042023` (April 2023), atorvastatin (83367) since `042005`. Store the version with every answer.
- **Brands and clinical drugs of an ingredient include combinations.** For atorvastatin, 1 of 3 brands and 14 of 19 SCDs contain another ingredient. Say "19 clinical drugs, 5 atorvastatin alone" or filter; do not call all 19 "atorvastatin strengths".
- **SCD names are not one fixed pattern.** They can start with a release time or pack volume ("24 HR", "Osmotic 24 HR", "2 ML ... Injection") and name the salt ("metformin hydrochloride 500 MG"). Branded synonyms are looser still ("Glumetza 1000 MG 24HR Extended Release Oral Tablet", "Caduet 10/80 Oral Tablet"). Cut names with the DF and SCDC concepts, as block 1 does, and keep the RxCUI as the key.
- **Pick the search mode on purpose.** The default `search=0` is exact (case ignored). `search=2` adds normalized matching. `search=9` is approximate and returns "a few concepts ... best guess first": it turned `atorvastatn` into 83367, but a guess can be a different drug, so blocks 1 and 3 flag it. `xyzzy` matched nothing even with `search=9`. `/REST/spellingsuggestions.json?name=atorvastatn` returned `["atorvastatin"]`.
- **Map to the ingredient before asking for brands.** The getRelatedByType doc says that when `tty` is the concept's own term type, "that RxCUI is returned as the sole result", so `tty=BN` on a brand gives back only that brand. Go name -> RxCUI -> `tty=IN` -> brands. A combination brand (Caduet) has 2 ingredients; choose one.
- **Mistakes are mostly silent.** Typos, unknown names and unknown RxCUIs are HTTP 200 with empty groups. Only a missing parameter or unknown tty is HTTP 400, as plain text, not JSON. Without `.json` the API answers XML (`/REST/rxcui?name=atorvastatin` -> `application/xml`).
- **Caching.** The server sends `cache-control: max-age=300`, but NLM asks clients to cache for 12-24 hours. Block 3's disk cache answered 3 repeated lookups with 0 network calls.
- **Rename in early 2027.** The terms page banner says "On February ##, 2027, the RxNav suite will be renamed to “RxNorm Tools.” ... the URL for this website will change to https://lhncbc.nlm.nih.gov/RxNorm-Tools on January ##, 2027. Functionality of the existing tools will not be impacted". NLM's Technical Bulletin of November 12, 2026 (https://www.nlm.nih.gov/pubs/techbull/nd26/nd26_rxnorm_tools.html) gives February 10, 2027 for the rename, maps lhncbc.nlm.nih.gov/RxNav to lhncbc.nlm.nih.gov/RxNorm-Tools and the mor.nlm.nih.gov tools to new paths, and says old URLs "will automatically redirect to the new URLs until May 11, 2027". rxnav.nlm.nih.gov is not in its table, and neither page says whether the REST host changes. Re-check the doc and terms links after February 10, 2027; the blocks stop loudly if `/REST/version.json` stops answering.
- **Not medical advice.** RxNorm is a drug vocabulary. Availability, approval and prescribing questions need a pharmacist or physician; the terms page says so too.
- **Tab marker.** The harness sets the tab title to a horse emoji; the blocks check `location.origin` and the JSON, not the title.

## What does not work

- **RxClass and its SNOMED CT content**: the one part of the suite that needs a licence ("subject to the SNOMED CT Affiliate license provisions"). Not used.
- **Bulk pulls through the public API**: over 20 requests per second per IP "may not be serviced". The terms point high-volume users to RxNav-in-a-Box (a local Docker install) or a UMLS key (100 per second). Neither was tried.
- **Not tested:** rate-limit behaviour (never provoked), the UMLS key tier, XML parsing, NDC, history and RxTerms endpoints, and `allsrc=1`/`srclist` filtering.
