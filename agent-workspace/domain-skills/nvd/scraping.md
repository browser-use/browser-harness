# NVD - Look Up a CVE: Severity Scores, Weakness Type, Affected Products, References (CVE API 2.0)

Field-tested against services.nvd.nist.gov and nvd.nist.gov on 2026-11-05 using a Browser Use cloud browser (logged out) and plain HTTP (Python urllib). About 30 browser requests and 30 plain HTTP calls, all serial at 6.5 s or more spacing: no 403, no 429, no Cloudflare challenge.

robots.txt (checked 2026-11-05): services.nvd.nist.gov/robots.txt is HTTP 404 (no rules); nvd.nist.gov/robots.txt has no rules either (HTTP 200 with the site's app shell, which renders "Page Not Found"). No named AI-agent groups. The CVE API is NVD's documented official API (https://nvd.nist.gov/developers/vulnerabilities), no key needed.

## Quick summary

- **No scraping.** `GET https://services.nvd.nist.gov/rest/json/cves/2.0?cveIds=CVE-A,CVE-B,...` returns full CVE records as JSON: CVSS v4.0/v3.1/v3.0/v2 scores, CWE weaknesses, NVD CPE configurations, CNA `affected` data, references with tags, CISA KEV dates. Up to 100 IDs per call. `cveId=` (single) still works but the docs mark it deprecated.
- **Rate limit: 5 requests per rolling 30 s without a key** (NVD "Start Here" page). The blocks pace 6.5 s per call, serial. With an API key it is 50 per 30 s; keys go in an `apiKey` request header. Batch IDs with `cveIds` instead of one call per CVE.
- **Errors are an empty HTTP 404 with a `message` response header:** `Invalid cveId parameter.`, `Invalid cveIds parameter.`, `resultsPerPage parameter cannot exceed 2000.`
- **A well-formed CVE ID the NVD does not have is not an error.** `cveId=CVE-2099-99999` gives HTTP 200, `totalResults: 0`; in `cveIds` it is dropped silently (5 asked, 4 returned). Diff the IDs.
- **Most new CVEs have no NVD CPE data.** Of 500 CVEs published Oct 25 - Nov 5 2026, 307 were `Deferred` and only 64 had `configurations`; 488 had the CNA's `affected` block. Read both for affected products.
- **Product search:** CPE API `products/cpes/2.0?keywordSearch=` turns a product name into `vendor:product`, then `cves/2.0?virtualMatchString=cpe:2.3:a:<vendor>:<product>` lists its CVEs and `cpeName=<full CPE>&isVulnerable` tests one version.
- **Browser:** nvd.nist.gov pages send a CSP whose `connect-src` blocks services.nvd.nist.gov, so `fetch()` to the API from an NVD page fails (`TypeError: Failed to fetch`). Block 1 reads the CWE/source name list on an nvd.nist.gov page, then moves the same tab to an API URL and reads the API from that origin. **Plain HTTP** (block 2) needs no browser; curl got the same CVE records.

## What works

### 1. Look up CVEs: scores, CWE names, affected products, references, KEV (browser)

Self-contained. One call fetches the CWE and source name list that the NVD CVE page loads itself (`/public/service/rest/json/nvd/vulns/meta`, 668 KB, readable only from the nvd.nist.gov origin), then one `cveIds` call fetches all the CVEs. `fetch_json()` returns parsed JSON on 200, waits 30 s on 403/429/5xx and otherwise raises, so a failure never looks like "no data".

```python
import collections, json, os, tempfile, time

CVES = ["CVE-2021-44228", "CVE-2024-3094", "CVE-2023-4863", "CVE-2026-115997", "CVE-2099-99999"]  # last one does not exist

API = "https://services.nvd.nist.gov/rest/json/cves/2.0"
META = "https://nvd.nist.gov/public/service/rest/json/nvd/vulns/meta"  # CWE names + source names; the CVE page loads it itself
PAUSE = 6.5  # docs: 5 requests per rolling 30 s without an API key; keep calls serial

def on_origin(origin, url):
    """fetch() runs from a logged-out tab on `origin`. nvd.nist.gov pages send a CSP whose connect-src blocks
    services.nvd.nist.gov, and the meta JSON only allows the nvd.nist.gov origin, so each host is read from its own origin."""
    try:
        if js("location.origin") == origin:
            return
    except Exception:
        pass
    if js("location.href").startswith("about:") or js("location.href").startswith("chrome"):
        new_tab(url)
    else:
        goto_url(url)
    wait_for_load()
    time.sleep(3)
    if js("location.origin") != origin or "just a moment" in js("document.title").lower():
        raise RuntimeError(f"tab landed on {js('location.href')}: stop and tell the user; do not retry around it")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__nvd = window.__nvd || {}; const id = String(Math.random()).slice(2); window.__nvd[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__nvd[id] = {status: r.status, msg: r.headers.get('message'), text: await r.text()}; })
    .catch(e => { window.__nvd[id] = {status: 0, msg: String(e), text: ''}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__nvd[%s]; if (v) delete window.__nvd[%s]; return v; })()"""

def fetch_json(url, tries=3, timeout=90):
    """GET url from inside the tab -> parsed JSON. NVD puts errors in a `message` header with an empty 404 body.
    Waits 30 s (one full rate window) on 403/429/5xx, raises on anything else."""
    for attempt in range(tries):
        rid = json.dumps(js(START_JS % json.dumps(url)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"{url}: no answer after {timeout}s")
            time.sleep(0.5)
        time.sleep(PAUSE)
        if r["status"] == 200:
            return json.loads(r["text"])
        if r["status"] not in (0, 403, 429, 500, 502, 503, 504) or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {r['status']} message={r['msg']!r}; stopping")
        time.sleep(30)

def lookup(cve_ids):
    """Up to 100 CVE IDs in one call (cveIds). IDs the NVD does not have are dropped silently, so diff the result."""
    out = []
    for i in range(0, len(cve_ids), 100):
        d = fetch_json(API + "?cveIds=" + ",".join(cve_ids[i:i + 100]))
        out += [v["cve"] for v in d["vulnerabilities"]]
    return out

def cpe_parts(cpe):
    p = cpe.split(":")  # cpe:2.3:part:vendor:product:version:...
    return p[3], p[4], p[5]

def summarize(c, cwe_name, src_name):
    m = c.get("metrics", {})
    scores = []
    for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        for x in m.get(key, []):
            d = x["cvssData"]
            scores.append((d["version"], x["type"], src_name(x["source"]), d["baseScore"], d.get("baseSeverity") or x.get("baseSeverity"), d["vectorString"]))
    cwes = {}
    for w in c.get("weaknesses", []):
        for dsc in w["description"]:
            cwes.setdefault(dsc["value"], set()).add(src_name(w["source"]))
    products = collections.defaultdict(list)  # NVD analyst CPE applicability (configurations)
    for cfg in c.get("configurations", []):
        for node in cfg["nodes"]:
            for cm in node["cpeMatch"]:
                if not cm["vulnerable"]:
                    continue  # "running on/with" platforms, not the vulnerable product
                vendor, product, ver = cpe_parts(cm["criteria"])
                rng = " ".join(f"{k}={cm[k]}" for k in ("versionStartIncluding", "versionStartExcluding", "versionEndIncluding", "versionEndExcluding") if k in cm)
                products[f"{vendor}:{product}"].append(rng or ver)
    cna = [(a.get("vendor") or a.get("collectionURL", "?"), a.get("product") or a.get("packageName", "?"),  # what the CNA/ADP says
            [(v.get("version"), v.get("lessThan") or v.get("lessThanOrEqual"), v.get("status")) for v in a.get("versions", [])])
           for blk in c.get("affected", []) for a in blk.get("affectedData", [])]
    desc = next((d["value"] for d in c["descriptions"] if d["lang"] == "en"), "")
    # products named in the description first (log4j for Log4Shell, not the 140 downstream Cisco/Siemens items)
    products = dict(sorted(products.items(), key=lambda kv: (kv[0].split(":")[1].replace("_", " ") not in desc.lower(), -len(kv[1]))))
    refs = collections.Counter(t for r in c.get("references", []) for t in r.get("tags", []) or ["(untagged)"])
    patches = [r["url"] for r in c.get("references", []) if {"Patch", "Vendor Advisory"} & set(r.get("tags", []))]
    return {"id": c["id"], "status": c["vulnStatus"], "published": c["published"], "lastModified": c["lastModified"],
            "description": desc,
            "scores": scores, "cwes": {k: (cwe_name(k), sorted(v)) for k, v in cwes.items()},
            "nvd_products": products, "cna_affected": cna, "ref_tags": refs, "n_refs": len(c.get("references", [])),
            "patch_or_advisory": patches, "kev": {k: c[k] for k in ("cisaExploitAdd", "cisaActionDue", "cisaRequiredAction") if k in c},
            "tags": [t for x in c.get("cveTags", []) for t in x.get("tags", [])]}

on_origin("https://nvd.nist.gov", "https://nvd.nist.gov/vuln/detail/" + CVES[0])  # the CVE page; it loads META itself
meta = fetch_json(META)["response"][0]
CWE = {x["cweIdentifier"]: x["name"] for x in meta["cwes"]}
SRC = {sid: s["name"] for s in meta["sources"] for sid in s["sourceIdentifiers"]}
print(f"meta: {len(CWE)} CWE names, {len(SRC)} source ids")
cwe_name = lambda k: CWE.get(k, k)  # names are cut at 100 characters; NVD-CWE-noinfo / NVD-CWE-Other are listed too
src_name = lambda s: SRC.get(s, s)

on_origin("https://services.nvd.nist.gov", API + "?cveId=" + CVES[0])  # an API URL is the only page on that host
found = lookup(CVES)
print("not in NVD:", sorted(set(CVES) - {c["id"] for c in found}))
for c in found:
    s = summarize(c, cwe_name, src_name)
    print(f"\n{s['id']} | {s['status']} | published {s['published'][:10]} | modified {s['lastModified'][:10]}")
    print("  ", " ".join(s["description"].split())[:150])
    for sc in s["scores"]:
        print(f"   CVSS {sc[0]:<3} {sc[1]:<9} {sc[2]:<34} {sc[3]:>4} {sc[4]:<8} {sc[5][:60]}")
    for k, (name, by) in s["cwes"].items():
        print(f"   {k}: {name[:70]} ({', '.join(by)})")
    print(f"   NVD CPE products ({len(s['nvd_products'])}):", [(k, v[:2]) for k, v in list(s["nvd_products"].items())[:2]])
    for vendor, product, vers in s["cna_affected"][:2]:
        print(f"   CNA affected: {vendor} / {product}: {vers[:3]}")
    print(f"   references {s['n_refs']}: {s['ref_tags'].most_common(4)}")
    print("   first patch/advisory:", s["patch_or_advisory"][:1])
    if s["kev"]:
        print("   CISA KEV:", s["kev"])
    if s["tags"]:
        print("   cveTags:", s["tags"])
out = os.path.join(tempfile.gettempdir(), "nvd_cves.json")
with open(out, "w") as f:
    json.dump(found, f)
print("\nsaved raw records:", os.path.basename(out), "in tempfile.gettempdir()")
```

Output (from the run on 2026-11-05):

```text
meta: 1397 CWE names, 827 source ids
not in NVD: ['CVE-2099-99999']

CVE-2021-44228 | Analyzed | published 2021-12-10 | modified 2026-08-11
   Apache Log4j2 2.0-beta9 through 2.15.0 (excluding security releases 2.12.2, 2.12.3, and 2.3.1) JNDI features used in configuration, log messages, and 
   CVSS 3.1 Primary   NIST                               10.0 CRITICAL CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H
   CVSS 3.1 Secondary CISA-ADP                           10.0 CRITICAL CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H
   CVSS 2.0 Primary   NIST                                9.3 HIGH     AV:N/AC:M/Au:N/C:C/I:C/A:C
   CWE-20: Improper Input Validation (Apache Software Foundation)
   CWE-400: Uncontrolled Resource Consumption (Apache Software Foundation)
   CWE-502: Deserialization of Untrusted Data (Apache Software Foundation)
   CWE-917: Improper Neutralization of Special Elements used in an Expression Lang (NIST)
   NVD CPE products (143): [('apache:log4j', ['versionStartIncluding=2.0.1 versionEndExcluding=2.3.1', 'versionStartIncluding=2.4.0 versionEndExcluding=2.12.2']), ('cisco:webex_meetings_server', ['versionEndExcluding=3.0', '3.0'])]
   CNA affected: Apache Software Foundation / Apache Log4j2: [('2.0-beta9', 'log4j-core*', 'affected')]
   references 103: [('Third Party Advisory', 95), ('VDB Entry', 32), ('Mailing List', 24), ('Exploit', 22)]
   first patch/advisory: ['https://logging.apache.org/log4j/2.x/security.html']
   CISA KEV: {'cisaExploitAdd': '2021-12-10', 'cisaActionDue': '2021-12-24', 'cisaRequiredAction': 'For all affected software assets for which updates exist, the only acceptable remediation actions are: 1) Apply updates; OR 2) remove affected assets from agency networks. Temporary mitigations using one of the measures provided at https://www.cisa.gov/uscert/ed-22-02-apache-log4j-recommended-mitigation-measures are only acceptable until updates are available.'}

CVE-2023-4863 | Analyzed | published 2023-09-12 | modified 2026-06-17
   Heap buffer overflow in libwebp in Google Chrome prior to 116.0.5845.187 and libwebp 1.3.2 allowed a remote attacker to perform an out of bounds memor
   CVSS 3.1 Primary   NIST                                8.8 HIGH     CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H
   CVSS 3.1 Secondary CISA-ADP                            8.8 HIGH     CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H
   CWE-787: Out-of-bounds Write (CISA-ADP, NIST)
   NVD CPE products (12): [('google:chrome', ['versionEndExcluding=116.0.5845.187']), ('webmproject:libwebp', ['versionEndExcluding=1.3.2'])]
   CNA affected: Google / Chrome: [('116.0.5845.187', '116.0.5845.187', 'affected')]
   CNA affected: Google / libwebp: [('1.3.2', '1.3.2', 'affected')]
   references 92: [('Mailing List', 52), ('Third Party Advisory', 35), ('Exploit', 9), ('Issue Tracking', 6)]
   first patch/advisory: ['https://chromereleases.googleblog.com/2023/09/stable-channel-update-for-desktop_11.html']
   CISA KEV: {'cisaExploitAdd': '2023-09-13', 'cisaActionDue': '2023-10-04', 'cisaRequiredAction': 'Apply mitigations per vendor instructions or discontinue use of the product if mitigations are unavailable.'}

CVE-2024-3094 | Modified | published 2024-03-29 | modified 2026-11-04
   Malicious code was discovered in the upstream tarballs of xz, starting with version 5.6.0. Through a series of complex obfuscations, the liblzma build
   CVSS 3.1 Secondary Red Hat, Inc.                      10.0 CRITICAL CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H
   CVSS 3.1 Primary   NIST                               10.0 CRITICAL CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H
   CWE-506: Embedded Malicious Code (Red Hat, Inc.)
   NVD CPE products (1): [('tukaani:xz', ['5.6.0', '5.6.1'])]
   CNA affected: https://github.com/tukaani-project/xz / xz: [('5.6.0', None, 'affected'), ('5.6.1', None, 'affected')]
   CNA affected: Red Hat / Red Hat Enterprise Linux 10: []
   references 59: [('Third Party Advisory', 24), ('(untagged)', 20), ('Vendor Advisory', 8), ('Issue Tracking', 8)]
   first patch/advisory: ['https://access.redhat.com/security/cve/CVE-2024-3094']

CVE-2026-115997 | Deferred | published 2026-10-25 | modified 2026-10-29
   A flaw has been found in pig-mesh pig up to 4.1.0. This impacts the function orderItem.getColumn of the file pig-common/pig-common-data/src/main/java/
   CVSS 4.0 Secondary VulDB                               2.1 LOW      CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:L/VI:L/VA:L/SC:N/SI:N/S
   CVSS 3.1 Secondary VulDB                               6.3 MEDIUM   CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:L/I:L/A:L
   CVSS 2.0 Secondary VulDB                               6.5 MEDIUM   AV:N/AC:L/Au:S/C:P/I:P/A:P
   CWE-74: Improper Neutralization of Special Elements in Output Used by a Downst (VulDB)
   CWE-89: Improper Neutralization of Special Elements used in an SQL Command ('S (VulDB)
   NVD CPE products (0): []
   CNA affected: pig-mesh / pig: [('4.0', None, 'affected'), ('4.1.0', None, 'affected'), ('4.1.1', None, 'unaffected')]
   references 9: [('(untagged)', 9)]
   first patch/advisory: []

saved raw records: nvd_cves.json in tempfile.gettempdir()
```

### 2. Product name -> CPE -> all its CVEs, and is my version vulnerable? (plain HTTP, no browser)

Python standard library only, truthful User-Agent, 3 calls at 6.5 s spacing (about 20 s). The CVE API matches products by CPE, not by name, so step 1 asks the CPE API which `vendor:product` a keyword means.

```python
import collections, json, time, urllib.error, urllib.parse, urllib.request

KEYWORD, VERSION = "libwebp", "1.3.1"  # product as a person would type it, and the version they run

UA = {"User-Agent": "browser-harness-skill/1.0 (Python urllib)"}
BASE = "https://services.nvd.nist.gov/rest/json/"
PAUSE = 6.5  # docs: 5 requests per rolling 30 s without an API key; keep calls serial

def call(path, flags=(), **params):
    """GET -> parsed JSON. Errors come back as an empty 404 with a `message` header. Waits 30 s on 403/429/5xx, then stops.
    `flags` are value-less parameters such as isVulnerable and noRejected."""
    url = BASE + path + "?" + "&".join([urllib.parse.urlencode(params, safe=":*"), *flags])
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                status, body, msg = r.status, r.read(), None
        except urllib.error.HTTPError as e:
            status, body, msg = e.code, e.read(), e.headers.get("message")
        time.sleep(PAUSE)
        if status == 200:
            return json.loads(body)
        if status not in (403, 429, 500, 502, 503, 504) or attempt == 2:
            raise RuntimeError(f"{url}: HTTP {status} message={msg!r}; stopping")
        time.sleep(30)

def pages(path, key, flags=(), **params):
    """Follow startIndex until totalResults; 2,000 is the page maximum."""
    rows, start = [], 0
    while True:
        d = call(path, flags, resultsPerPage=2000, startIndex=start, **params)
        rows += d[key]
        start += d["resultsPerPage"]
        if not d["resultsPerPage"] or start >= d["totalResults"]:
            return rows

def best_score(c):
    """NVD's own (Primary) score first, newest CVSS version first; else the CNA/ADP (Secondary) one."""
    m = c.get("metrics", {})
    for want in ("Primary", "Secondary"):
        for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            for x in m.get(key, []):
                if x["type"] == want:
                    d = x["cvssData"]
                    return d["baseScore"], d.get("baseSeverity") or x.get("baseSeverity"), d["version"], want
    return None, "NONE", None, None

# 1. keyword -> CPE vendor:product (the CVE API matches products by CPE, not by name)
cpes = call("cpes/2.0", keywordSearch=KEYWORD, resultsPerPage=200)
names = collections.Counter(":".join(p["cpe"]["cpeName"].split(":")[2:5]) for p in cpes["products"] if not p["cpe"]["deprecated"])
print(f"CPE keyword '{KEYWORD}': {cpes['totalResults']} CPE names; part:vendor:product in first page: {names.most_common(5)}")
part, vendor, product = names.most_common(1)[0][0].split(":")

# 2. every CVE whose applicability matches that product (any version)
cves = [v["cve"] for v in pages("cves/2.0", "vulnerabilities", ("noRejected",), virtualMatchString=f"cpe:2.3:{part}:{vendor}:{product}")]
sev = collections.Counter(best_score(c)[1] for c in cves)
cwe = collections.Counter(w["description"][0]["value"] for c in cves for w in c.get("weaknesses", [])[:1])
kev = [c["id"] for c in cves if "cisaExploitAdd" in c]
print(f"\n{vendor}:{product}: {len(cves)} CVEs | best severity {dict(sev)} | in CISA KEV: {kev}")
print("top CWE (first listed per CVE):", cwe.most_common(4))
for c in sorted(cves, key=lambda c: c["published"], reverse=True)[:5]:
    score, s, ver, typ = best_score(c)
    print(f"  {c['id']:<16} {c['published'][:10]} {c['vulnStatus']:<12} {score} {s:<8} (CVSS {ver} {typ})")

# 3. which of them hit the exact version (cpeName needs part, vendor, product and version)
cpe_name = f"cpe:2.3:{part}:{vendor}:{product}:{VERSION}:*:*:*:*:*:*:*"
hit = call("cves/2.0", ("isVulnerable",), cpeName=cpe_name)
print(f"\n{cpe_name} isVulnerable: {hit['totalResults']} CVE")
for v in hit["vulnerabilities"]:
    c = v["cve"]
    score, s, ver, typ = best_score(c)
    for cfg in c.get("configurations", []):
        for node in cfg["nodes"]:
            for m in node["cpeMatch"]:
                if m["vulnerable"] and f":{vendor}:{product}:" in m["criteria"]:
                    rng = {k: m[k] for k in m if k.startswith("version")}
                    print(f"  {c['id']} {score} {s} | {m['criteria']} {rng}")
```

Output (from the run on 2026-11-05):

```text
CPE keyword 'libwebp': 45 CPE names; part:vendor:product in first page: [('a:webmproject:libwebp', 45)]

webmproject:libwebp: 15 CVEs | best severity {'LOW': 1, 'HIGH': 4, 'CRITICAL': 10} | in CISA KEV: ['CVE-2023-4863']
top CWE (first listed per CVE): [('CWE-125', 6), ('CWE-787', 3), ('CWE-416', 2), ('CWE-190', 1)]
  CVE-2023-4863    2023-09-12 Analyzed     8.8 HIGH     (CVSS 3.1 Primary)
  CVE-2023-1999    2023-06-20 Modified     7.5 HIGH     (CVSS 3.1 Primary)
  CVE-2020-36332   2021-05-21 Modified     7.5 HIGH     (CVSS 3.1 Primary)
  CVE-2020-36331   2021-05-21 Modified     9.1 CRITICAL (CVSS 3.1 Primary)
  CVE-2020-36330   2021-05-21 Modified     9.1 CRITICAL (CVSS 3.1 Primary)

cpe:2.3:a:webmproject:libwebp:1.3.1:*:*:*:*:*:*:* isVulnerable: 1 CVE
  CVE-2023-4863 8.8 HIGH | cpe:2.3:a:webmproject:libwebp:*:*:*:*:*:*:*:* {'versionEndExcluding': '1.3.2'}
```

## Fields

| Field | Where | Notes |
|---|---|---|
| `id`, `vulnStatus` | `cve` | `Analyzed`, `Modified`, `Deferred`, `Awaiting Analysis`, `Undergoing Analysis`, `Received`, `Rejected` |
| `published`, `lastModified` | `cve` | ISO without zone (`2021-12-10T10:15:09.143`) |
| `descriptions[]` | `cve` | `{lang, value}`; English plus sometimes Spanish (`es`) |
| `metrics.cvssMetricV40/V31/V30/V2[]` | `cve` | `{source, type, cvssData{version, vectorString, baseScore, baseSeverity, ...}}`; `type` `Primary` = NVD, `Secondary` = CNA or ADP. V2 keeps `baseSeverity` outside `cvssData` |
| `metrics.ssvcV203[]` | `cve` | CISA SSVC decision data; 473 of 500 recent CVEs had it |
| `weaknesses[]` | `cve` | `{source, type, description[{lang, value: "CWE-787"}]}`; one CWE can repeat under two sources |
| `configurations[].nodes[].cpeMatch[]` | `cve` | `{vulnerable, criteria: "cpe:2.3:a:apache:log4j:*...", versionStartIncluding, versionEndExcluding, ...}`; `vulnerable: false` = "running on/with" platform |
| `affected[].affectedData[]` | `cve` | CNA/ADP data: `vendor`, `product` (or only `packageName`/`collectionURL`), `versions[{version, lessThan, status, changes}]`, `defaultStatus`, `cpes` |
| `references[]` | `cve` | `{url, source, tags[]}`; tags such as `Patch`, `Vendor Advisory`, `Exploit`, `Third Party Advisory`; often untagged on unanalyzed CVEs |
| `cisaExploitAdd`, `cisaActionDue`, `cisaRequiredAction`, `cisaVulnerabilityName` | `cve` | present only when the CVE is in CISA KEV |
| `cveTags[]` | `cve` | `{sourceIdentifier, tags[]}`, e.g. `disputed` |
| `source` values | everywhere | an email (`security@apache.org`) or a UUID (`134c704f-...` = CISA-ADP); names come from the meta JSON (block 1) or `rest/json/source/2.0?sourceIdentifier=` |

## Gotchas

- **`cvssV3Severity` / `cvssV4Severity` filters match NVD's own (Primary) score only.** `cveIds=CVE-2021-44228&cvssV3Severity=CRITICAL` returns it; `cveIds=CVE-2026-115997&cvssV3Severity=MEDIUM` returns 0 though the record carries a VulDB v3.1 MEDIUM. `cvssV4Severity=CRITICAL` and `=LOW` each returned 0 CVEs NVD-wide, while 294 of 500 recent CVEs carry a CNA v4.0 score. Filter severity client-side, as block 2 does.
- **`virtualMatchString` / `cpeName` only find CVEs with NVD CPE data.** A `Deferred` CVE such as CVE-2026-115997 has `affected` (pig-mesh / pig) but no `configurations`, so product search does not list it. For recent CVEs also try `keywordSearch=`.
- **NVD CPE lists can be huge and downstream-heavy.** Log4Shell has 143 vulnerable `vendor:product` pairs, most of them Cisco and Siemens products that ship log4j. Block 1 lists products named in the description first.
- **CNA `affected` versions are free-form.** Apache wrote `version 2.0-beta9, lessThan log4j-core*` plus a `changes` list; Google wrote `version 116.0.5845.187, lessThan 116.0.5845.187`. NVD `versionEndExcluding` ranges are cleaner when present.
- **Primary is not always first.** For CVE-2024-3094 the Red Hat Secondary v3.1 comes before the NVD Primary one. Pick by `type`, not by position.
- **CWE names in the meta JSON are cut at 100 characters** (`... Expression Language Statement ('Expression La`); 11 of 1,397 hit the cap.
- **Case:** the docs say parameter names and values are case-insensitive; `nvd.nist.gov/vuln/detail/CVE-...` 301-redirects to the lowercase `cve-...` URL.
- **Pagination:** `resultsPerPage` max 2,000 (also the default), follow `startIndex`. Date-range filters (`pubStartDate`/`lastModStartDate`) need both ends and allow at most 120 days.
- **Tab marker.** The harness prefixes the tab title with a horse emoji; block 1 only reads the title to spot a Cloudflare "Just a moment" page.

## What does not work

- **`fetch()` to services.nvd.nist.gov from an nvd.nist.gov page:** `TypeError: Failed to fetch` (CSP `connect-src 'self' *.google.com ...`). Open an API URL to get a services.nvd.nist.gov origin, as block 1 does.
- **Reading the meta JSON from the services.nvd.nist.gov origin:** it sends `access-control-allow-origin: https://nvd.nist.gov` only.
- **Severity filters for CNA-only scores:** see Gotchas. Not worked around server-side.
- **Not tested:** the CVE Change History API (`cvehistory/2.0`), API keys, rate-limit behaviour past 5 requests per 30 s (never provoked).
