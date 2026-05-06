# PubChem — Scraping & Data Extraction

`https://pubchem.ncbi.nlm.nih.gov` — NIH's free chemical compound database. **Never use the browser for PubChem.** All data is reachable via `http_get` against the PUG REST API. No API key required.

## Do this first

**Use the PUG REST API for any compound lookup — one call, JSON response, no auth.**

```python
import json
from helpers import http_get

BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

data = json.loads(http_get(f"{BASE}/compound/name/aspirin/property/MolecularFormula,MolecularWeight,IUPACName,IsomericSMILES,InChIKey,XLogP,TPSA,HBondDonorCount,HBondAcceptorCount,RotatableBondCount,HeavyAtomCount,Complexity,Charge/JSON"))
props = data["PropertyTable"]["Properties"][0]
# {'CID': 2244, 'MolecularFormula': 'C9H8O4', 'MolecularWeight': '180.16',
#  'SMILES': 'CC(=O)OC1=CC=CC=C1C(=O)O', 'InChIKey': 'BSYNRYMUTXBXSQ-UHFFFAOYSA-N',
#  'IUPACName': '2-acetyloxybenzoic acid', 'XLogP': 1.2, 'TPSA': 63.6,
#  'HBondDonorCount': 1, 'HBondAcceptorCount': 4, 'RotatableBondCount': 3,
#  'HeavyAtomCount': 13, 'Complexity': 212, 'Charge': 0}
```

Prefer the properties endpoint over the full compound JSON — it is faster and returns a clean flat dict instead of a deeply nested structure.

## Common workflows

### Lookup by name → get CID and properties

```python
import json
from helpers import http_get

BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
PROPS = "MolecularFormula,MolecularWeight,IUPACName,IsomericSMILES,InChIKey,XLogP,ExactMass,TPSA,HBondDonorCount,HBondAcceptorCount,RotatableBondCount,HeavyAtomCount,Complexity,Charge"

def get_compound(name):
    url = f"{BASE}/compound/name/{name}/property/{PROPS}/JSON"
    try:
        data = json.loads(http_get(url))
        return data["PropertyTable"]["Properties"][0]
    except Exception:
        return None  # 404 if name not found

compound = get_compound("aspirin")
print(compound["CID"], compound["MolecularFormula"], compound["MolecularWeight"])
# Confirmed output (2026-04-18):
# 2244 C9H8O4 180.16
```

### Lookup by CID → properties

```python
import json
from helpers import http_get

BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
PROPS = "MolecularFormula,MolecularWeight,IUPACName,IsomericSMILES,InChIKey,XLogP,ExactMass,TPSA,HBondDonorCount,HBondAcceptorCount,RotatableBondCount,HeavyAtomCount,Complexity,Charge"

data = json.loads(http_get(f"{BASE}/compound/cid/2244/property/{PROPS}/JSON"))
props = data["PropertyTable"]["Properties"][0]
print(props["IUPACName"], props["XLogP"])
# Confirmed output:
# 2-acetyloxybenzoic acid 1.2
```

### Batch CID fetch — multiple compounds in one call

Comma-separate CIDs for a single round-trip. Faster than sequential calls.

```python
import json
from helpers import http_get

BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
PROPS = "MolecularFormula,MolecularWeight,IUPACName,IsomericSMILES"

cids = [2244, 2519, 5090]  # aspirin, caffeine, rofecoxib
url = f"{BASE}/compound/cid/{','.join(str(c) for c in cids)}/property/{PROPS}/JSON"
data = json.loads(http_get(url))
for p in data["PropertyTable"]["Properties"]:
    print(p["CID"], p["MolecularFormula"], p["IUPACName"][:40])
# Confirmed output:
# 2244 C9H8O4 2-acetyloxybenzoic acid
# 2519 C8H10N4O2 1,3,7-trimethylpurine-2,6-dione
# 5090 C17H14O4S 3-(4-methylsulfonylphenyl)-4-phenyl-2H-furan-5-one
```

### Resolve name to CID (ambiguous names return all matching CIDs)

```python
import json
from helpers import http_get

BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

data = json.loads(http_get(f"{BASE}/compound/name/caffeine/cids/JSON"))
cids = data["IdentifierList"]["CID"]
print("CIDs:", cids)
# Confirmed output:
# CIDs: [2519]

# Ambiguous names (common names that map to multiple compounds) return multiple CIDs:
# e.g. "glucose" → [5793], "morphine" → [5288826], etc.
# For common drug names, typically returns a single canonical CID
```

### Synonyms

```python
import json
from helpers import http_get

BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

data = json.loads(http_get(f"{BASE}/compound/name/aspirin/synonyms/JSON"))
info = data["InformationList"]["Information"][0]
cid = info["CID"]
synonyms = info.get("Synonym", [])
print(f"CID {cid} has {len(synonyms)} synonyms")
print("First 5:", synonyms[:5])
# Confirmed output:
# CID 2244 has 695 synonyms
# First 5: ['aspirin', 'ACETYLSALICYLIC ACID', '50-78-2', '2-Acetoxybenzoic acid', '2-(Acetyloxy)benzoic acid']
# Synonyms include: IUPAC names, CAS numbers, trade names, common names
```

### Description / bioactivity summary

```python
import json
from helpers import http_get

BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

data = json.loads(http_get(f"{BASE}/compound/cid/2244/description/JSON"))
infos = data["InformationList"]["Information"]
for info in infos:
    title = info.get("Title", "")
    desc = info.get("Description", "")
    if desc:
        print(f"[{title}] {desc[:200]}")
# Returns compound descriptions from multiple sources (MeSH, NLM, etc.)
# Confirmed: 3 description records for aspirin
```

### Structure image URL (PNG)

```python
BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

# Construct the PNG URL directly — no http_get needed, just use the URL in <img> or download
cid = 2244
img_url = f"{BASE}/compound/cid/{cid}/PNG"
# Returns a 300x300 PNG of the 2D structure
# Confirmed: content-type image/png, HTTP 200

# Can also look up by name:
img_url_by_name = f"{BASE}/compound/name/aspirin/PNG"

# Customize size:
img_url_large = f"{BASE}/compound/cid/{cid}/PNG?image_size=500x500"
```

### Structure data file (SDF) — for cheminformatics tools

```python
from helpers import http_get

BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

sdf = http_get(f"{BASE}/compound/cid/2244/SDF")
# Returns V2000 SDF format with atom coordinates, bonds, and properties
# First line is the CID, usable directly with RDKit, OpenBabel, etc.
```

### Parallel batch fetch (ThreadPoolExecutor)

Use for large lists of CIDs or names. Respect the 5 req/s guideline.

```python
import json, time
from concurrent.futures import ThreadPoolExecutor
from helpers import http_get

BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
PROPS = "MolecularFormula,MolecularWeight,IUPACName,IsomericSMILES,InChIKey"

def fetch_by_name(name):
    try:
        url = f"{BASE}/compound/name/{name}/property/{PROPS}/JSON"
        data = json.loads(http_get(url))
        return data["PropertyTable"]["Properties"][0]
    except Exception:
        return {"name": name, "error": "not found"}

names = ["aspirin", "ibuprofen", "caffeine", "paracetamol", "morphine"]
with ThreadPoolExecutor(max_workers=5) as ex:
    results = list(ex.map(fetch_by_name, names))
for r in results:
    if "error" not in r:
        print(r["CID"], r["MolecularFormula"], r["IUPACName"][:40])
# Keep max_workers <= 5 to stay within the 5 req/s rate limit
```

## URL patterns

```
# Compound by name
https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/JSON
https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/property/{props}/JSON
https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/cids/JSON
https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/synonyms/JSON
https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/PNG

# Compound by CID (batch: comma-separate CIDs)
https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/JSON
https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/property/{props}/JSON
https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/synonyms/JSON
https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/description/JSON
https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/SDF
https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/PNG

# Compound by InChIKey
https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/inchikey/{inchikey}/property/{props}/JSON

# Compound by SMILES
https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/{smiles}/property/{props}/JSON
```

## Available property keys

Pass any comma-separated subset to the `/property/{props}/JSON` endpoint:

| Key | Type | Description |
|---|---|---|
| `MolecularFormula` | string | e.g. `C9H8O4` |
| `MolecularWeight` | string | e.g. `"180.16"` (g/mol) |
| `IUPACName` | string | Preferred IUPAC name |
| `IsomericSMILES` | string | Isomeric SMILES (key is `SMILES` in response) |
| `CanonicalSMILES` | string | Canonical SMILES (key is `ConnectivitySMILES` in response) |
| `InChI` | string | Standard InChI |
| `InChIKey` | string | Standard InChIKey (27-char hash) |
| `XLogP` | float | Octanol/water partition coefficient |
| `ExactMass` | string | Monoisotopic exact mass |
| `MonoisotopicMass` | string | Same as ExactMass |
| `TPSA` | float | Topological polar surface area (A²) |
| `Complexity` | int | Molecular complexity score |
| `Charge` | int | Net formal charge |
| `HBondDonorCount` | int | Hydrogen bond donor count |
| `HBondAcceptorCount` | int | Hydrogen bond acceptor count |
| `RotatableBondCount` | int | Rotatable bond count |
| `HeavyAtomCount` | int | Non-hydrogen atom count |
| `CovalentUnitCount` | int | Number of covalent units (1 for most drugs) |

## Response shape reference

Properties endpoint returns a flat dict per compound — the easiest format to use:

```python
# GET /compound/name/aspirin/property/MolecularFormula,MolecularWeight,IUPACName,IsomericSMILES,InChIKey,XLogP,TPSA,HBondDonorCount,HBondAcceptorCount,RotatableBondCount,HeavyAtomCount,Complexity,Charge/JSON
{
  "PropertyTable": {
    "Properties": [
      {
        "CID": 2244,
        "MolecularFormula": "C9H8O4",
        "MolecularWeight": "180.16",
        "SMILES": "CC(=O)OC1=CC=CC=C1C(=O)O",          # IsomericSMILES
        "InChIKey": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
        "IUPACName": "2-acetyloxybenzoic acid",
        "XLogP": 1.2,
        "TPSA": 63.6,
        "HBondDonorCount": 1,
        "HBondAcceptorCount": 4,
        "RotatableBondCount": 3,
        "HeavyAtomCount": 13,
        "Complexity": 212,
        "Charge": 0
      }
    ]
  }
}
```

Full compound JSON (`/compound/name/{name}/JSON`) returns a deeply nested `PC_Compounds` array with `props` list — only use it if you need fields not available in the properties endpoint (e.g. stereochemistry atom details, bond tables).

## Gotchas

- **Never use the browser for PubChem.** The PUG REST API covers everything: structure, properties, synonyms, images, SDF, descriptions. `http_get` is sufficient for all data retrieval.

- **`IsomericSMILES` is returned as `SMILES` in the response dict**, not `IsomericSMILES`. Similarly, `CanonicalSMILES` is returned as `ConnectivitySMILES`. Always access `props["SMILES"]`, not `props["IsomericSMILES"]`.

- **404 returns a JSON fault, not an HTML error page.** `{"Fault": {"Code": "PUGREST.NotFound", "Message": "No CID found", ...}}`. Wrap `http_get` in a try/except — the 404 status itself raises an exception in `urllib`.

- **Name lookup is case-insensitive but whitespace-sensitive.** `aspirin`, `Aspirin`, `ASPIRIN` all work. URL-encode spaces in multi-word names: `acetylsalicylic+acid` or `acetylsalicylic%20acid`.

- **Rate limit: 5 requests/second.** The API returns an `x-throttling-control` header indicating Green/Yellow/Red status. At Green (normal load), bursts of 5 concurrent requests are safe. For sustained bulk fetching use `ThreadPoolExecutor(max_workers=5)` and stay under 5 req/s. No explicit backoff header is returned — the server just slows down or returns HTTP 503.

- **Batch CID lookup via comma-separated list is the fastest approach for known CIDs.** A single call with 50 CIDs is much faster than 50 sequential calls. Keep batch size under 200 CIDs to avoid request timeouts.

- **`MolecularWeight` is a string, not a float.** The API returns `"180.16"` (string). Cast with `float(props["MolecularWeight"])` if you need arithmetic.

- **Common names map to exactly one CID; ambiguous names may return multiple CIDs** from the `/cids/` endpoint. Use `/cids/` first if you need to verify uniqueness, then fetch properties by CID.

- **InChIKey lookup works for exact structure matching.** If you have an InChIKey from another source, use `/compound/inchikey/{key}/property/.../JSON` to get PubChem data without going through name resolution.

- **SMILES lookup is supported but must be URL-encoded.** Special SMILES characters like `=`, `#`, `(`, `)` must be percent-encoded. Prefer InChIKey for exact structure lookup — it is a safe URL-friendly hash.
