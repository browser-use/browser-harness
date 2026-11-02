# ClinicalTrials.gov - Search Trials by Condition, Location and Status; Read a Study

Field-tested against clinicaltrials.gov on 2026-11-02 using a Browser Use cloud browser, logged out, plus plain HTTP to the official API v2 (`apiVersion` 2.0.5). No key, no login, no cookie wall, no challenge.

robots.txt (checked 2026-11-02, `User-agent: *`): `Disallow: /api/`, `Allow: /api/int/`, `Allow: /api/seo/`, `Disallow: /search?`, `Disallow: /expert-search?`, `Crawl-delay: 1`; block 1 uses `/api/v2/` only under the official-API exception (documented at clinicaltrials.gov/data-api/api, an allowed page), block 2 loads only `/study/<NCT>` (allowed) and re-reads the `/api/int/` JSON that page requests itself.

## Quick summary

- **Use the official API.** `GET https://clinicaltrials.gov/api/v2/studies` with `query.cond` (condition), `filter.overallStatus` (status list) and either `filter.geo=distance(lat,lon,25mi)` (radius) or `query.locn` (location text). `GET /api/v2/studies/<NCT>` returns one full record. JSON, no key, `fields=` trims the payload.
- **Pace 1 s per call, one at a time** (robots.txt `Crawl-delay: 1`). No rate-limit headers and no 429 were seen across about 80 calls. Block 1 waits 60 s once on 429/503, then raises.
- **Pages:** `pageSize` up to 1,000 (spec); follow `nextPageToken` via `pageToken` with the same other parameters. `countTotal=true` returns `totalCount` on the first page only.
- **Filter twice.** `query.cond` also matches derived MeSH terms, so an unrelated study can come back (a colon cancer trial matched "type 1 diabetes"). `filter.overallStatus` is study-level; each site has its own `status`. Block 1 returns only the sites inside the radius, with their own status and distance.
- **Site search UI is off-limits:** `/search?...` is robots-disallowed. Study pages (`/study/<NCT>`) are allowed; block 2 reads one in a browser as a fallback and matches the API.

## What works

### 1. Search by condition, location and status; read study details (official API, plain HTTP)

No browser needed. Runs in about 15 s (15 calls at 1 s pacing).

```python
import json, math, time, urllib.error, urllib.parse, urllib.request

API = "https://clinicaltrials.gov/api/v2"   # official public API; robots.txt disallows /api/ (official-API exception)
UA = "browser-harness-clinicaltrials-skill/1.0 Python-urllib"   # truthful client name, no browser UA
PACE_S = 1.0   # robots.txt Crawl-delay: 1; one request at a time
_last = [0.0]

def api(path, **params):
    """GET a /api/v2 JSON resource. None on 404; one 60 s wait on 429/503, then raise."""
    url = API + path + ("?" + urllib.parse.urlencode(params, safe=",|():") if params else "")
    for attempt in range(2):
        time.sleep(max(0.0, _last[0] + PACE_S - time.time()))
        _last[0] = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read()[:200].decode(errors="replace")
            if e.code == 404:
                return None
            if e.code in (429, 503) and attempt == 0:
                time.sleep(60)
                continue
            raise RuntimeError(f"HTTP {e.code} {body!r} on {url}; stop, do not retry around it") from e

def miles(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(a))

SEARCH_FIELDS = ("NCTId,BriefTitle,OverallStatus,Phase,StudyType,Condition,LeadSponsorName,StartDate,"
                 "EnrollmentCount,LastUpdatePostDate,LocationFacility,LocationCity,LocationState,"
                 "LocationCountry,LocationStatus,LocationGeoPoint")

def search(cond, statuses=("RECRUITING",), near=None, locn=None, page_size=100, max_pages=3):
    """Studies for a condition, filtered by overall status and either a radius (near=(lat, lon, miles)) or
    location text (locn). Returns (rows, total, status), status = complete | truncated_max_pages."""
    params = {"query.cond": cond, "filter.overallStatus": ",".join(statuses), "fields": SEARCH_FIELDS,
              "sort": "LastUpdatePostDate:desc", "pageSize": page_size, "countTotal": "true"}
    if near:
        params["filter.geo"] = f"distance({near[0]},{near[1]},{near[2]}mi)"
    if locn:
        params["query.locn"] = locn
    rows, total, page = [], None, 1
    while True:
        d = api("/studies", **params)
        total = d.get("totalCount", total)
        for s in d["studies"]:
            p = s["protocolSection"]
            st, de = p.get("statusModule", {}), p.get("designModule", {})
            sites = []
            for l in p.get("contactsLocationsModule", {}).get("locations", []):
                g = l.get("geoPoint")
                dist = round(miles(near[0], near[1], g["lat"], g["lon"]), 1) if near and g else None
                if near and (dist is None or dist > near[2]):
                    continue
                if locn and not near and locn.lower() not in " ".join(str(l.get(k, "")) for k in ("facility", "city", "state", "country")).lower():
                    continue
                sites.append({"facility": l.get("facility"), "city": l.get("city"), "state": l.get("state"),
                              "site_status": l.get("status"), "miles": dist})
            sites.sort(key=lambda x: (x["miles"] is None, x["miles"] or 0))
            rows.append({
                "nct": p["identificationModule"]["nctId"], "title": p["identificationModule"].get("briefTitle"),
                "status": st.get("overallStatus"), "phases": de.get("phases", []), "type": de.get("studyType"),
                "conditions": p.get("conditionsModule", {}).get("conditions", []),
                "sponsor": p.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("name"),
                "start": st.get("startDateStruct", {}).get("date"),
                "enrollment": de.get("enrollmentInfo", {}).get("count"),
                "last_update": st.get("lastUpdatePostDateStruct", {}).get("date"),
                "sites_total": len(p.get("contactsLocationsModule", {}).get("locations", [])),
                "matching_sites": sites,
            })
        token = d.get("nextPageToken")
        if not token:
            return rows, total, "complete"
        if page >= max_pages:
            return rows, total, "truncated_max_pages"
        params["pageToken"], page = token, page + 1
        params.pop("countTotal", None)

def count(cond, status, near):
    d = api("/studies", **{"query.cond": cond, "filter.overallStatus": status, "fields": "NCTId",
                           "filter.geo": f"distance({near[0]},{near[1]},{near[2]}mi)", "pageSize": 1, "countTotal": "true"})
    return d["totalCount"]

def study(nct):
    """One study's details, or None if the NCT number does not exist. Contact names, phones and emails are left out."""
    d = api(f"/studies/{nct}")
    if d is None:
        return None
    p = d["protocolSection"]
    idm, st, de, el = p["identificationModule"], p["statusModule"], p.get("designModule", {}), p.get("eligibilityModule", {})
    di = de.get("designInfo", {})
    locs = p.get("contactsLocationsModule", {}).get("locations", [])
    crit = el.get("eligibilityCriteria", "")
    return {
        "nct": idm["nctId"], "title": idm.get("briefTitle"), "official_title": idm.get("officialTitle"),
        "status": st.get("overallStatus"), "why_stopped": st.get("whyStopped"),
        "type": de.get("studyType"), "phases": de.get("phases", []),
        "design": {k: di.get(k) for k in ("allocation", "interventionModel", "primaryPurpose")} | {"masking": di.get("maskingInfo", {}).get("masking")},
        "conditions": p.get("conditionsModule", {}).get("conditions", []),
        "interventions": [(i.get("type"), i.get("name")) for i in p.get("armsInterventionsModule", {}).get("interventions", [])],
        "arms": len(p.get("armsInterventionsModule", {}).get("armGroups", [])),
        "sponsor": p.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("name"),
        "start": st.get("startDateStruct"), "primary_completion": st.get("primaryCompletionDateStruct"),
        "completion": st.get("completionDateStruct"), "enrollment": de.get("enrollmentInfo"),
        "eligibility": {"sex": el.get("sex"), "min_age": el.get("minimumAge"), "max_age": el.get("maximumAge"),
                        "healthy_volunteers": el.get("healthyVolunteers"), "std_ages": el.get("stdAges"),
                        "criteria_chars": len(crit), "criteria_head": crit[:160]},
        "primary_outcomes": len(p.get("outcomesModule", {}).get("primaryOutcomes", [])),
        "primary_outcomes_head": [(o.get("measure"), o.get("timeFrame")) for o in p.get("outcomesModule", {}).get("primaryOutcomes", [])[:2]],
        "secondary_outcomes": len(p.get("outcomesModule", {}).get("secondaryOutcomes", [])),
        "sites": len(locs), "countries": sorted({l.get("country") for l in locs if l.get("country")}),
        "site_statuses": {s: sum(1 for l in locs if l.get("status") == s) for s in sorted({l.get("status") for l in locs if l.get("status")})},
        "has_results": d.get("hasResults"), "last_update": st.get("lastUpdatePostDateStruct", {}).get("date"),
        "url": f"https://clinicaltrials.gov/study/{idm['nctId']}",
    }

print("data version:", api("/version"))

# 1. Search: type 1 diabetes, recruiting, within 25 miles of downtown Boston
BOSTON = (42.3601, -71.0589, 25)
rows, total, status = search("type 1 diabetes", near=BOSTON, page_size=10, max_pages=2)
print(f"radius search: {len(rows)} of {total} ({status})")
for r in rows[:5]:
    near1 = r["matching_sites"][0] if r["matching_sites"] else {}
    print(" ", r["nct"], r["status"], r["phases"], r["last_update"], "|", r["title"][:70])
    print("     nearest site:", near1.get("facility"), near1.get("city"), near1.get("site_status"), near1.get("miles"), "mi |",
          len(r["matching_sites"]), "of", r["sites_total"], "sites in radius")
off = [r["nct"] for r in rows if not any("diabet" in c.lower() for c in r["conditions"])]
print("hits with no 'diabet' in their listed conditions:", off)
for nct in off[:1]:   # why it matched: query.cond also searches the derived MeSH terms
    d = api(f"/studies/{nct}", fields="ConditionMeshTerm")
    print("  ", nct, "derived MeSH:", [m["term"] for m in d["derivedSection"]["conditionBrowseModule"]["meshes"]])

# 2. Same condition, location as text instead of a radius
rows2, total2, status2 = search("type 1 diabetes", locn="Boston", page_size=100, max_pages=1)
print(f"text location search: {len(rows2)} of {total2} ({status2}); overlap with radius search:",
      len({r['nct'] for r in rows2} & {r['nct'] for r in search('type 1 diabetes', near=BOSTON, page_size=100, max_pages=1)[0]}))

# 3. Status filter: counts per overall status in the same radius
for s in ("RECRUITING", "NOT_YET_RECRUITING", "ACTIVE_NOT_RECRUITING", "COMPLETED", "TERMINATED"):
    print(f"  {s:22} {count('type 1 diabetes', s, BOSTON)}")

# 4. Study details: first hit that lists a diabetes condition, a completed study with results, a missing NCT number
top = next(r["nct"] for r in rows if any("diabet" in c.lower() for c in r["conditions"]))
for nct in (top, "NCT04368728", "NCT99999999"):
    s = study(nct)
    print(json.dumps(s, ensure_ascii=False) if s else f"{nct} -> None (404, no such study)")

# 5. Bad parameter values fail loudly (HTTP 400), never as an empty result
try:
    search("type 1 diabetes", statuses=("OPEN",), page_size=1, max_pages=1)
except RuntimeError as e:
    print("bad status ->", str(e)[:80])
```

Output observed on 2026-11-02:

```text
data version: {'apiVersion': '2.0.5', 'dataTimestamp': '2026-11-02T10:00:05'}
radius search: 20 of 27 (truncated_max_pages)
  NCT07808151 RECRUITING ['PHASE2'] 2026-10-27 | Neoadjuvant Pembrolizumab and Porustobart in Resectable pMMR/MSS Colon
     nearest site: Investigator Site Boston NOT_YET_RECRUITING 0.1 mi | 1 of 30 sites in radius
  NCT06919354 RECRUITING ['PHASE1'] 2026-10-20 | A Study of GNTI-122 in Adults Recently Diagnosed With T1D
     nearest site: Joslin Diabetes Center Boston RECRUITING 0.1 mi | 1 of 10 sites in radius
  NCT07676565 RECRUITING [] 2026-10-16 | Safety and Efficacy of Adjunct Therapies in Adults With Type 1 Diabete
     nearest site: Harvard Medical School Boston RECRUITING 0.1 mi | 1 of 17 sites in radius
  NCT07187531 RECRUITING ['PHASE2'] 2026-10-13 | SAFety and Efficacy of Human Anti-thymocyte ImmunoGlobUlin SAB-142 ARr
     nearest site: Harvard Medical School - Joslin Diabetes Center and Joslin Clinical (JDS) Boston RECRUITING 0.1 mi | 1 of 68 sites in radius
  NCT07282639 RECRUITING ['NA'] 2026-09-23 | App-Based Certified Diabetes Education Therapy (AB-CDE)
     nearest site: Joslin Diabetes Center, Harvard School of Medicine Boston RECRUITING 0.1 mi | 1 of 6 sites in radius
hits with no 'diabet' in their listed conditions: ['NCT07808151']
   NCT07808151 derived MeSH: ['Colonic Neoplasms', 'Diabetes Mellitus, Insulin-Dependent, 12', 'Spinocerebellar Degenerations']
text location search: 27 of 27 (complete); overlap with radius search: 27
  RECRUITING             27
  NOT_YET_RECRUITING     1
  ACTIVE_NOT_RECRUITING  17
  COMPLETED              151
  TERMINATED             22
{"nct": "NCT06919354", "title": "A Study of GNTI-122 in Adults Recently Diagnosed With T1D", "official_title": "POLARIS: A Phase 1, Single Dose, Open-label Study of GNTI-122 in Adults With Recently Diagnosed Type 1 Diabetes (T1D)", "status": "RECRUITING", "why_stopped": null, "type": "INTERVENTIONAL", "phases": ["PHASE1"], "design": {"allocation": "NA", "interventionModel": "SINGLE_GROUP", "primaryPurpose": "TREATMENT", "masking": "NONE"}, "conditions": ["Type 1 Diabetes (T1D)", "Type 1 Diabetes Mellitus"], "interventions": [["BIOLOGICAL", "GNTI-122"]], "arms": 1, "sponsor": "GentiBio, Inc", "start": {"date": "2025-09-03", "type": "ACTUAL"}, "primary_completion": {"date": "2028-02", "type": "ESTIMATED"}, "completion": {"date": "2028-02", "type": "ESTIMATED"}, "enrollment": {"count": 16, "type": "ESTIMATED"}, "eligibility": {"sex": "ALL", "min_age": "18 Years", "max_age": "55 Years", "healthy_volunteers": false, "std_ages": ["ADULT"], "criteria_chars": 1369, "criteria_head": "Inclusion Criteria:\n\n1. Male and female participants aged ≥18 to ≤55 years with recently diagnosed (within 180 days of Screening) T1D according to American Diab"}, "primary_outcomes": 1, "primary_outcomes_head": [["Safety and tolerability of GNTI-122 with and without rapamycin in adult participants with recently diagnosed T1D", "Week 78"]], "secondary_outcomes": 3, "sites": 10, "countries": ["United States"], "site_statuses": {"NOT_YET_RECRUITING": 1, "RECRUITING": 9}, "has_results": false, "last_update": "2026-10-20", "url": "https://clinicaltrials.gov/study/NCT06919354"}
{"nct": "NCT04368728", "title": "Study to Describe the Safety, Tolerability, Immunogenicity, and Efficacy of RNA Vaccine Candidates Against COVID-19 in Healthy Individuals", "official_title": "A PHASE 1/2/3, PLACEBO-CONTROLLED, RANDOMIZED, OBSERVER-BLIND, DOSE-FINDING STUDY TO EVALUATE THE SAFETY, TOLERABILITY, IMMUNOGENICITY, AND EFFICACY OF SARS-COV-2 RNA VACCINE CANDIDATES AGAINST COVID-19 IN HEALTHY INDIVIDUALS", "status": "COMPLETED", "why_stopped": null, "type": "INTERVENTIONAL", "phases": ["PHASE2", "PHASE3"], "design": {"allocation": "RANDOMIZED", "interventionModel": "PARALLEL", "primaryPurpose": "PREVENTION", "masking": "TRIPLE"}, "conditions": ["SARS-CoV-2 Infection", "COVID-19"], "interventions": [["BIOLOGICAL", "BNT162b1"], ["BIOLOGICAL", "BNT162b2"], ["OTHER", "Placebo"], ["BIOLOGICAL", "BNT162b2SA"]], "arms": 20, "sponsor": "BioNTech SE", "start": {"date": "2020-04-29", "type": "ACTUAL"}, "primary_completion": {"date": "2023-02-10", "type": "ACTUAL"}, "completion": {"date": "2023-02-10", "type": "ACTUAL"}, "enrollment": {"count": 46969, "type": "ACTUAL"}, "eligibility": {"sex": "ALL", "min_age": "12 Years", "max_age": null, "healthy_volunteers": true, "std_ages": ["CHILD", "ADULT", "OLDER_ADULT"], "criteria_chars": 4979, "criteria_head": "Inclusion Criteria:\n\n• Male or female participants between the ages of 18 and 55 years, inclusive, 65 and 85 years, inclusive, or ≥12 years, inclusive, at rando"}, "primary_outcomes": 64, "primary_outcomes_head": [["Percentage of Participants With Local Reactions Within 7 Days After Dose 1: Phase 1", "Within 7 days after Dose 1"], ["Percentage of Participants With Local Reactions Within 7 Days After Dose 2: Phase 1", "Within 7 days after Dose 2"]], "secondary_outcomes": 31, "sites": 175, "countries": ["Argentina", "Brazil", "Germany", "South Africa", "Turkey (Türkiye)", "United States"], "site_statuses": {}, "has_results": true, "last_update": "2026-03-25", "url": "https://clinicaltrials.gov/study/NCT04368728"}
NCT99999999 -> None (404, no such study)
bad status -> HTTP 400 'Invalid value in parameter `overallStatus`: `OPEN`' on https://clinica
```

`truncated_max_pages` is expected: `page_size=10, max_pages=2` stopped at 20 of 27.

### 2. Study page fallback (browser, reads the page's own data request)

The study page fetches `/api/int/studies/<NCT>?history=true` itself (robots `Allow: /api/int/`). Block 2 loads the page, finds that request in `performance` entries, and re-reads the same URL same-origin. Contact names, phones and emails are not returned. One tab, 4 page loads, about 8 s.

```python
import json, re, time

SITE = "https://clinicaltrials.gov"
PAGE_GAP_S = 1   # robots.txt Crawl-delay: 1

def robots_rules_from_tab():
    """Rules of the `User-agent: *` group, read in the browser tab."""
    goto_url(SITE + "/robots.txt")
    wait_for_load()
    txt = js("document.body ? document.body.innerText : ''") or ""
    if "User-agent" not in txt:
        raise SystemExit(f"robots.txt did not load ({js('document.title')!r}): stop, do not retry around it")
    rules, in_star, prev_ua = [], False, False
    for line in txt.splitlines():
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        k, v = (x.strip() for x in line.split(":", 1))
        k = k.lower()
        if k == "user-agent":
            in_star = (in_star and prev_ua) or v == "*"
            prev_ua = True
            continue
        prev_ua = False
        if in_star and k in ("allow", "disallow") and v:
            rules.append((k == "allow", v))
    return rules

def robots_allowed(rules, path):
    """Google-style: longest matching pattern wins, Allow wins a tie."""
    best, ok = -1, True
    for allow, pat in rules:
        rx = re.escape(pat.rstrip("$")).replace(r"\*", ".*") + ("$" if pat.endswith("$") else "")
        if re.match(rx, path) and (len(pat) > best or (len(pat) == best and allow)):
            best, ok = len(pat), allow
    return ok

# Re-reads the JSON the study page itself requested (performance entry under /api/int/studies/), same origin.
READ_OWN = r"""(async (nct) => {
  const src = performance.getEntriesByType('resource').map(e => e.name)
    .find(n => n.includes('/api/int/studies/' + nct));
  if (!src) return {pending: true};
  const r = await fetch(src);
  if (r.status === 404) return {missing: true, src};
  if (!r.ok) return {error: r.status, src};
  const j = await r.json(), s = j.study, p = s.protocolSection;
  const st = p.statusModule || {}, de = p.designModule || {}, el = p.eligibilityModule || {};
  const locs = (p.contactsLocationsModule || {}).locations || [];
  const by = {};
  for (const l of locs) if (l.status) by[l.status] = (by[l.status] || 0) + 1;
  return {
    src, nct: p.identificationModule.nctId, title: p.identificationModule.briefTitle,
    status: st.overallStatus, phases: de.phases || [], type: de.studyType,
    conditions: (p.conditionsModule || {}).conditions || [],
    sponsor: ((p.sponsorCollaboratorsModule || {}).leadSponsor || {}).name,
    enrollment: de.enrollmentInfo || null,
    eligibility: {sex: el.sex, min_age: el.minimumAge, max_age: el.maximumAge || null, healthy_volunteers: el.healthyVolunteers},
    sites: locs.length, site_statuses: by, has_results: s.hasResults,
    last_update: (st.lastUpdatePostDateStruct || {}).date,
    history_versions: ((j.history || {}).changes || []).length,
  };
})"""

def study_page(rules, nct, timeout=30):
    """Study details from the page's own data request. None for the site's "can't find this study" page."""
    path = f"/study/{nct}"
    if not robots_allowed(rules, path):
        raise PermissionError(f"robots.txt disallows {path}")
    goto_url(SITE + path)
    wait_for_load()
    deadline = time.time() + timeout
    while time.time() < deadline:
        href, title = js("[location.href, document.title]")
        body = js("document.querySelector('main') ? document.querySelector('main').innerText.slice(0, 400) : ''") or ""
        low = (title + " " + body).lower()
        if any(s in low for s in ("just a moment", "verify you are human", "access denied", "captcha", "too many requests")):
            raise SystemExit(f"challenge on {href}: stop and back off, do not retry")
        final = href.replace(SITE, "", 1).split("#")[0]
        if not robots_allowed(rules, final):
            raise PermissionError(f"{path} redirected to disallowed {final}")
        if "can't find this study" in body.lower() or "can’t find this study" in body.lower():
            return None
        d = js(f"{READ_OWN}({json.dumps(nct)})")
        if d and d.get("missing"):
            return None
        if d and d.get("error"):
            raise RuntimeError(f"{d['src']}: HTTP {d['error']}; stop, do not retry around it")
        if d and not d.get("pending"):
            d["nct_in_page_title"] = nct in title
            return d
        time.sleep(0.5)
    raise RuntimeError(f"no study data for {nct} within {timeout} s: {page_info()}")

tab = cdp("Target.createTarget", url="about:blank", background=True)["targetId"]
switch_tab(tab)
try:
    rules = robots_rules_from_tab()
    print("robots: /study/NCT06919354", robots_allowed(rules, "/study/NCT06919354"),
          "| /api/int/studies/NCT06919354", robots_allowed(rules, "/api/int/studies/NCT06919354"),
          "| /api/v2/studies", robots_allowed(rules, "/api/v2/studies"),
          "| /search?cond=x", robots_allowed(rules, "/search?cond=x"))
    for nct in ("NCT06919354", "NCT04368728", "NCT99999999"):
        time.sleep(PAGE_GAP_S)
        d = study_page(rules, nct)
        print(json.dumps(d, ensure_ascii=False) if d else f"{nct} -> None (site's 'can't find this study' page)")
finally:
    close_tab(tab)
```

Output observed on 2026-11-02:

```text
robots: /study/NCT06919354 True | /api/int/studies/NCT06919354 True | /api/v2/studies False | /search?cond=x False
{"src": "https://clinicaltrials.gov/api/int/studies/NCT06919354?history=true", "nct": "NCT06919354", "title": "A Study of GNTI-122 in Adults Recently Diagnosed With T1D", "status": "RECRUITING", "phases": ["PHASE1"], "type": "INTERVENTIONAL", "conditions": ["Type 1 Diabetes (T1D)", "Type 1 Diabetes Mellitus"], "sponsor": "GentiBio, Inc", "enrollment": {"count": 16, "type": "ESTIMATED"}, "eligibility": {"sex": "ALL", "min_age": "18 Years", "max_age": "55 Years", "healthy_volunteers": false}, "sites": 10, "site_statuses": {"RECRUITING": 9, "NOT_YET_RECRUITING": 1}, "has_results": false, "last_update": "2026-10-20", "history_versions": 19, "nct_in_page_title": true}
{"src": "https://clinicaltrials.gov/api/int/studies/NCT04368728?history=true", "nct": "NCT04368728", "title": "Study to Describe the Safety, Tolerability, Immunogenicity, and Efficacy of RNA Vaccine Candidates Against COVID-19 in Healthy Individuals", "status": "COMPLETED", "phases": ["PHASE2", "PHASE3"], "type": "INTERVENTIONAL", "conditions": ["SARS-CoV-2 Infection", "COVID-19"], "sponsor": "BioNTech SE", "enrollment": {"count": 46969, "type": "ACTUAL"}, "eligibility": {"sex": "ALL", "min_age": "12 Years", "max_age": null, "healthy_volunteers": true}, "sites": 175, "site_statuses": {}, "has_results": true, "last_update": "2026-03-25", "history_versions": 53, "nct_in_page_title": true}
NCT99999999 -> None (site's 'can't find this study' page)
```

Values match block 1 for the same NCT numbers (status, phases, enrollment, eligibility, site counts, `has_results`, `last_update`).

## URL patterns (all observed)

| URL | Result |
|---|---|
| `/api/v2/studies?query.cond=...&filter.overallStatus=RECRUITING,NOT_YET_RECRUITING&filter.geo=distance(42.3601,-71.0589,25mi)&fields=...&pageSize=100&countTotal=true` | `{"totalCount": n, "studies": [...], "nextPageToken": "..."}`; last page has no `nextPageToken` |
| `/api/v2/studies?...&query.locn=Boston` | location text search instead of a radius |
| `/api/v2/studies/<NCT>` | one study: `protocolSection`, `derivedSection`, `hasResults`, plus `resultsSection` and `documentSection` when posted (NCT04368728); HTTP 404, body `NCT number NCT99999999 not found`, for a missing id |
| `/api/v2/studies/<NCT>?fields=ConditionMeshTerm` | just the derived condition MeSH terms |
| `/api/v2/version` | `{"apiVersion": "2.0.5", "dataTimestamp": "2026-11-02T10:00:05"}` |
| `/api/oas/v2` | OpenAPI 3.0 spec (YAML) with every parameter and enum |
| `/study/<NCT>` | study page; requests `/api/int/studies/<NCT>?history=true` (`{study, topics, history}`); a missing id shows "Sorry, we can't find this study" and the int call returns 404 |
| `/search?cond=...` | robots-disallowed, never loaded |

## Fields

Paths under `protocolSection` unless noted. `fields=` takes the short names in the first column (or module names like `ProtocolSection`).

| `fields=` name | JSON path | Note |
|---|---|---|
| `NCTId`, `BriefTitle` | `identificationModule.nctId`, `.briefTitle`, `.officialTitle` | |
| `OverallStatus` | `statusModule.overallStatus`, `.whyStopped` | study-level status |
| `StartDate`, `LastUpdatePostDate` | `statusModule.startDateStruct`, `.primaryCompletionDateStruct`, `.completionDateStruct`, `.lastUpdatePostDateStruct` | each `{date, type}`, type `ACTUAL` or `ESTIMATED`; dates can be `YYYY-MM` |
| `Phase`, `StudyType`, `EnrollmentCount` | `designModule.phases`, `.studyType`, `.enrollmentInfo`, `.designInfo` | phases like `PHASE1`, `PHASE2`, `NA`, or empty for observational |
| `Condition` | `conditionsModule.conditions`, `.keywords` | as entered by the sponsor |
| `ConditionMeshTerm` | `derivedSection.conditionBrowseModule.meshes` | derived, searched by `query.cond` |
| `LeadSponsorName` | `sponsorCollaboratorsModule.leadSponsor.name` | |
| (module) | `armsInterventionsModule.armGroups`, `.interventions` | `interventions[].type` like `DRUG`, `BIOLOGICAL` |
| (module) | `eligibilityModule.sex`, `.minimumAge`, `.maximumAge`, `.healthyVolunteers`, `.stdAges`, `.eligibilityCriteria` | criteria is one Markdown string |
| (module) | `outcomesModule.primaryOutcomes`, `.secondaryOutcomes` | `{measure, timeFrame, description}` |
| `LocationFacility`, `LocationCity`, `LocationState`, `LocationCountry`, `LocationStatus`, `LocationGeoPoint` | `contactsLocationsModule.locations[]` | per-site `status` and `geoPoint {lat, lon}`; `centralContacts` and `locations[].contacts` hold names, phones and emails |

Status values (`filter.overallStatus`): `RECRUITING`, `NOT_YET_RECRUITING`, `ENROLLING_BY_INVITATION`, `ACTIVE_NOT_RECRUITING`, `COMPLETED`, `SUSPENDED`, `TERMINATED`, `WITHDRAWN`, plus expanded-access `AVAILABLE`, `NO_LONGER_AVAILABLE`, `TEMPORARILY_NOT_AVAILABLE`, `APPROVED_FOR_MARKETING`, and `WITHHELD`, `UNKNOWN` (OpenAPI spec enum).

## Gotchas

- `query.cond` searches derived MeSH terms too. NCT07808151 (colon cancer) carries the derived term "Diabetes Mellitus, Insulin-Dependent, 12" and matched "type 1 diabetes"; quoting the phrase (`"type 1 diabetes"`) still returned it (25 hits vs 27). Check `conditions` before trusting a hit.
- Overall status and site status differ. NCT07808151 is `RECRUITING` overall but its Boston site is `NOT_YET_RECRUITING`, like 27 of its 30 sites. Completed studies have no per-site status at all (`site_statuses: {}` for NCT04368728).
- Results are unsorted by default (OpenAPI spec). Block 1 sends `sort=LastUpdatePostDate:desc` so pages are stable.
- `pageToken` pages must repeat every other parameter of the first request (OpenAPI spec). Block 1 only adds `pageToken` and drops `countTotal`.
- A bad enum value returns HTTP 400 with a readable body (``Invalid value in parameter `overallStatus`: `OPEN` ``). Block 1 raises instead of returning an empty list.
- Text location search and radius search returned the same 27 studies for "type 1 diabetes" + Boston / 25 mi of downtown Boston. Radius is more precise for a city with suburbs; the per-site `miles` comes from each site's `geoPoint`.
- Data refreshes Monday to Friday, generally by 9 a.m. ET; `/api/v2/version` `dataTimestamp` shows when (docs page).
- Long text fields (`eligibilityCriteria`, descriptions) come back as Markdown by default (`markupFormat=markdown`; `legacy` is the other option).
- Records contain personal contact details (central contacts, site contacts). Both blocks leave them out of their output; read them only when the task needs them.
- In a harness tab, `document.title` starts with the tab marker, so block 2 checks that the NCT number is in the title instead of comparing the whole string.

## What does not work

- The site search UI (`/search?cond=...&locStr=...`) and `/expert-search?`: robots-disallowed, never loaded. Use block 1.
- `/api/v2/` falls under robots `Disallow: /api/`; it is used here only because it is ClinicalTrials.gov's documented public API. Do not use it to bypass anything, and do not parallelize it.
- No key or login exists for higher limits; none is needed for these calls.
- Plain HTTP to `/api/int/studies/<NCT>` returned HTTP 403 with an HTML body (2026-11-02). It answered only inside the study page (block 2). For HTTP without a browser, use block 1.
