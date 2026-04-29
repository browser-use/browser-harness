# Can I Use — Browser Compatibility Data

`https://caniuse.com` — browser feature compatibility database. **Never use the browser.** All data is available as a single JSON file with no auth, no rate limiting, and no API key. The full dataset is ~4.5MB gzipped.

## Do this first: pick your source

| Source | URL | Notes |
|--------|-----|-------|
| GitHub raw (preferred) | `https://raw.githubusercontent.com/Fyrd/caniuse/main/data.json` | ~200ms, updated on each caniuse release |
| caniuse.com direct | `https://caniuse.com/data.json` | ~270ms, slightly more current (updated between releases) |
| Single feature file | `https://raw.githubusercontent.com/Fyrd/caniuse/main/features-json/{feature-id}.json` | Lighter if you only need one feature |

Both sources require an SSL bypass on macOS (same as NVD). Use GitHub raw for most tasks — it is faster and cacheable.

---

## Fetch the full dataset

```python
import urllib.request, ssl, gzip, json

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE

def caniuse_fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=30, context=_ctx) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        return json.loads(raw.decode())

# Full dataset — ~200ms, 554 features
obj = caniuse_fetch("https://raw.githubusercontent.com/Fyrd/caniuse/main/data.json")
# obj keys: eras, agents, statuses, cats, updated, data
# obj["data"]   — dict of {feature_id: feature_object}  (554 features)
# obj["agents"] — dict of {browser_id: agent_object}    (19 browsers)
# obj["updated"] — unix timestamp of last update
```

---

## Data structure

### Top-level keys

```python
obj["eras"]     # mapping of era names to date ranges (cosmetic, rarely needed)
obj["statuses"] # W3C spec status codes: {"rec": "W3C Recommendation", "cr": ..., "wd": ..., "ls": ..., "other": ..., "unoff": ...}
obj["cats"]     # category groupings: {"CSS": ["CSS2","CSS3","CSS"], "JS API": [...], ...}
obj["updated"]  # unix timestamp (int)
```

### Feature object (`obj["data"]["css-grid"]`)

```python
feat = obj["data"]["css-grid"]
# feat["title"]          – human name: "CSS Grid Layout (level 1)"
# feat["description"]    – one-sentence HTML description
# feat["spec"]           – spec URL
# feat["status"]         – "rec" | "cr" | "wd" | "ls" | "other" | "unoff"
# feat["links"]          – list of {"url": ..., "title": ...}
# feat["categories"]     – list of strings, e.g. ["CSS"]
# feat["stats"]          – {browser_id: {version_string: support_code}}
# feat["notes"]          – prose HTML notes (may be empty)
# feat["notes_by_num"]   – {"1": "note text", "2": "..."} referenced by #N in support codes
# feat["usage_perc_y"]   – float: % of global users with full support (pre-computed)
# feat["usage_perc_a"]   – float: % of global users with partial support (pre-computed)
# feat["keywords"]       – comma-separated search terms
# feat["parent"]         – parent feature ID (e.g. "css-grid" is parent of "css-subgrid"), or ""
```

### Support codes (`feat["stats"][browser_id][version]`)

Support codes are **space-separated tokens**. The first token is the base status; additional tokens are modifiers.

| Token | Meaning |
|-------|---------|
| `y` | Supported |
| `n` | Not supported |
| `a` | Partial support (see notes) |
| `p` | Supported via polyfill |
| `u` | Unknown / untested |
| `x` | Requires vendor prefix (e.g. `-webkit-`) |
| `d` | Disabled by default (must be enabled in flags) |
| `#N` | References note number N in `notes_by_num` |

Codes compose: `"a x #2"` = partial support, requires prefix, see note 2. `"p d #3"` = polyfill only, disabled by default, see note 3. `"y #4"` = supported but with caveat in note 4.

```python
import re

def parse_support(code):
    """Parse a support code string into components."""
    base = re.match(r"^([yanpu])", code)
    return {
        "code":     base.group(1) if base else "?",   # y/a/n/p/u
        "prefix":   "x" in code,                       # needs vendor prefix
        "disabled": "d" in code,                       # off by default
        "notes":    [int(n) for n in re.findall(r"#(\d+)", code)],
    }

parse_support("a x #2")  # {'code': 'a', 'prefix': True, 'disabled': False, 'notes': [2]}
parse_support("p d #3")  # {'code': 'p', 'prefix': False, 'disabled': True, 'notes': [3]}
parse_support("y")       # {'code': 'y', 'prefix': False, 'disabled': False, 'notes': []}
```

### Agent object (`obj["agents"]["chrome"]`)

```python
agent = obj["agents"]["chrome"]
# agent["browser"]       – display name: "Chrome"
# agent["long_name"]     – "Google Chrome"
# agent["abbr"]          – "Chr."
# agent["prefix"]        – CSS vendor prefix: "webkit"
# agent["type"]          – "desktop" | "mobile"
# agent["versions"]      – ordered list of version strings; None = placeholder for future/unreleased
# agent["usage_global"]  – {version: float} global usage percentage per version
```

**Browser IDs:** `ie`, `edge`, `firefox`, `chrome`, `safari`, `opera`, `ios_saf`, `op_mini`, `android`, `bb`, `op_mob`, `and_chr`, `and_ff`, `ie_mob`, `and_uc`, `samsung`, `and_qq`, `baidu`, `kaios`

---

## Common workflows

### Look up current support for a feature across major browsers

```python
def current_support(obj, feature_id, browser_ids=None):
    """Return {browser_id: {browser, version, support}} for current stable versions."""
    feat = obj["data"].get(feature_id)
    if not feat:
        raise KeyError(f"Unknown feature: {feature_id!r}. Search obj['data'].keys().")

    agents = obj["agents"]
    result = {}
    for bid, stats in feat["stats"].items():
        if browser_ids and bid not in browser_ids:
            continue
        agent = agents.get(bid, {})
        # Current stable = last non-None entry in versions list
        current = next((v for v in reversed(agent.get("versions", [])) if v is not None), None)
        if current and current in stats:
            result[bid] = {
                "browser": agent.get("browser", bid),
                "version": current,
                "support": stats[current],
            }
    return result

# Example
support = current_support(obj, "css-grid", ["chrome", "firefox", "safari", "edge", "ie"])
for bid, info in support.items():
    print(f"{info['browser']:15} v{info['version']:6} {info['support']}")
# Chrome          v150   y
# Firefox         v152   y
# Safari          vTP    y
# Edge            v146   y
# IE              v11    a x #2
```

### Search features by keyword

```python
def find_features(obj, query, category=None):
    """Search feature IDs, titles, and descriptions. Returns [(id, title, usage_perc_y)]."""
    q = query.lower()
    results = []
    for fid, feat in obj["data"].items():
        if category and category not in feat.get("categories", []):
            continue
        if q in fid or q in feat.get("title", "").lower() or q in feat.get("keywords", "").lower():
            results.append((fid, feat["title"], feat["usage_perc_y"]))
    return sorted(results, key=lambda x: x[2], reverse=True)

find_features(obj, "grid")
# [('css-grid', 'CSS Grid Layout (level 1)', 96.08), ('css-subgrid', 'CSS Subgrid', 92.5), ...]

find_features(obj, "fetch")
# [('fetch', 'Fetch', 96.6), ...]

find_features(obj, "animation", category="CSS")
# CSS-only results
```

### Get full version history for a feature in one browser

```python
def version_history(obj, feature_id, browser_id):
    """Return [(version, support_code)] in chronological order, skipping 'u' (unknown)."""
    feat = obj["data"].get(feature_id, {})
    stats = feat.get("stats", {}).get(browser_id, {})
    agent_versions = obj["agents"].get(browser_id, {}).get("versions", [])
    ordered = [(v, stats[v]) for v in agent_versions if v and v in stats and stats[v] != "u"]
    return ordered

version_history(obj, "css-grid", "firefox")
# [('19', 'p'), ('20', 'p'), ... ('52', 'y #4'), ('53', 'y #4'), ...]
```

### Fetch only a single feature (lightweight)

```python
# ~50-100KB instead of 4.5MB — good when you only need one feature
feat = caniuse_fetch("https://raw.githubusercontent.com/Fyrd/caniuse/main/features-json/css-grid.json")
# Same structure as obj["data"]["css-grid"] with one extra field:
# feat["shown"] – bool, whether shown on the main caniuse.com listing
```

### Check global usage coverage

```python
# Pre-computed: fastest approach
feat = obj["data"]["css-grid"]
print(feat["usage_perc_y"])  # 96.08 — % of global users with full support
print(feat["usage_perc_a"])  # 0.29  — % with partial support

# Compute yourself from usage_global (matches stored value exactly):
total_y = sum(
    obj["agents"][bid]["usage_global"].get(v, 0)
    for bid, stats in feat["stats"].items()
    if bid in obj["agents"]
    for v, code in stats.items()
    if code.startswith("y")
)
# total_y ≈ 96.08
```

### Enumerate all features with low support (find things not yet safe to use)

```python
low_support = [
    (fid, feat["title"], feat["usage_perc_y"])
    for fid, feat in obj["data"].items()
    if feat["usage_perc_y"] < 70
]
low_support.sort(key=lambda x: x[2])
# Most experimental features at the top
```

---

## Browser IDs and types reference

| ID | Name | Type |
|----|------|------|
| `chrome` | Chrome | desktop |
| `firefox` | Firefox | desktop |
| `safari` | Safari | desktop |
| `edge` | Edge | desktop |
| `ie` | IE | desktop |
| `opera` | Opera | desktop |
| `ios_saf` | Safari on iOS | mobile |
| `and_chr` | Chrome for Android | mobile |
| `samsung` | Samsung Internet | mobile |
| `android` | Android Browser | mobile |
| `and_ff` | Firefox for Android | mobile |
| `op_mini` | Opera Mini | mobile |
| `op_mob` | Opera Mobile | mobile |
| `ie_mob` | IE Mobile | mobile |
| `and_uc` | UC Browser for Android | mobile |
| `and_qq` | QQ Browser | mobile |
| `baidu` | Baidu Browser | mobile |
| `kaios` | KaiOS Browser | mobile |
| `bb` | Blackberry Browser | mobile |

---

## Gotchas

- **SSL fails on macOS with plain `http_get`.** GitHub raw uses a cert chain that isn't trusted by the macOS system store. Use the `ssl.create_default_context()` bypass shown above. Same issue affects `caniuse.com/data.json`. Do not modify helpers.py.

- **`None` in `agent["versions"]` means unreleased/future slots**, not missing data. Edge has `['145', '146', None, None, None]` — the last three are placeholders. Use `next((v for v in reversed(versions) if v is not None), None)` to get current stable.

- **`u` (unknown) is common for old/obscure browsers.** Baidu, KaiOS, QQ Browser have `"u"` for most features. Filter with `if code != "u"` when building support matrices.

- **Support codes are strings, not single characters.** `"a x #2"` is one value. Never compare with `== "a"` — use `.startswith("a")` or the `parse_support()` helper above.

- **`usage_perc_y` and `usage_perc_a` are pre-computed and authoritative.** Don't recompute unless you need custom browser subsets. The stored values match computing from `usage_global` exactly.

- **`notes_by_num` keys are strings, not ints.** `notes_by_num["1"]` not `notes_by_num[1]`. Note references in support codes are `#1`, `#2`, etc.

- **`parent` field chains sub-features.** `css-subgrid` has `"parent": "css-grid"`. Features with a parent are subsets — their stats describe support for the sub-feature only.

- **`feat["stats"]` always contains all 19 browser IDs**, even if all versions are `"u"`. Never assume a browser is absent — check the values, not the key presence.

- **`safari` desktop `vTP` is Safari Technology Preview**, not a stable release. Its support code is real data but indicates upcoming support, not current shipping support.

- **`caniuse.com/data.json` is slightly more current** than the GitHub raw file (updated between repo releases), but both are refreshed frequently. For automation, prefer GitHub raw (no CORS issues, stable URL, CDN-cached).

- **Feature IDs are kebab-case and stable** (e.g. `css-grid`, `fetch`, `arrow-functions`). They do not change. Use them as stable keys for caching or cross-referencing.
