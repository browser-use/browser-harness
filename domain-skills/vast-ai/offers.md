# Vast.ai — GPU offer discovery

`https://cloud.vast.ai/create/` is the marketplace search page. Use the page's
same-origin JSON endpoints instead of scraping offer cards.

## Do this first

Open the search page in the user's existing browser session. If it redirects to an
authentication wall, stop and ask the user to log in. Never print cookies, API keys,
the current-user response, or the API-key response.

```python
new_tab("https://cloud.vast.ai/create/")
wait_for_load()
print(page_info())
```

## Canonical GPU names

`GET /api/v0/gpu_types/?status=active` returns `{success, count, gpu_types}`. Use
`canonical_name` in bundle filters; do not guess display names.

```python
import json

raw = js(
    "fetch('/api/v0/gpu_types/?status=active')"
    ".then(r => r.json()).then(x => JSON.stringify(x.gpu_types))"
)
gpu_types = json.loads(raw)
for gpu in gpu_types:
    if gpu["canonical_name"] in {"RTX 5090", "RTX 6000Ada", "L40S"}:
        print(gpu["canonical_name"], gpu["gpu_ram_mb"], gpu["compute_cap"])
```

## Search offers through the bundles endpoint

`GET /api/v0/bundles/?q=<URL-encoded JSON>` returns `{"offers": [...]}`. The query
shape matches the console filters. This avoids card virtualization and gives precise
fields for price, driver, reliability, duration, storage, and networking.

```python
import json, urllib.parse

query = {
    "cpu_arch": {"in": ["amd64"]},
    "gpu_name": {"eq": "RTX 5090"},
    "num_gpus": {"eq": 1},
    "gpu_ram": {"gte": 30000},
    "cpu_cores_effective": {"gte": 16},
    "cpu_ram": {"gte": 64000},
    "disk_space": {"gte": 250},
    "allocated_storage": 250,
    "duration": {"gte": 604800},
    "rentable": {"eq": True},
    "verified": {"eq": True},
    "reliability2": {"gte": 0.99},
    "direct_port_count": {"gte": 1},
    "type": "ask",
    "order": [["dph_total", "asc"]],
    "limit": 64,
    "resource_type": "gpu",
}

url = "/api/v0/bundles/?q=" + urllib.parse.quote(
    json.dumps(query, separators=(",", ":"))
)
raw = js(
    f"fetch({json.dumps(url)}).then(r => r.json())"
    ".then(x => JSON.stringify(x.offers || []))"
)
offers = json.loads(raw)
```

## Important pricing and filter traps

- Set `allocated_storage` to the intended GB before comparing `dph_total`. The default
  console allocation is small, so its displayed total understates a large training
  disk.
- `storage_cost`, `inet_up_cost`, and `inet_down_cost` are separate offer fields. Do
  not compare GPU base price alone.
- `duration` is seconds, not days.
- `reliability2` is a fraction (`0.997` means 99.7%).
- Offers are dynamic and single-use. Re-fetch the chosen offer immediately before a
  state-changing rent call and verify price, driver, availability, and duration again.
- Server-side `driver_version` equality filtering is not reliable: observed responses
  can include other driver versions. Filter driver versions client-side after fetching.
- Keep offer discovery read-only. Renting, stopping, destroying, and creating volumes
  are separate state-changing actions and require explicit task authorization.

## Safe result projection

Project only fields needed for selection. Avoid dumping entire offer/user objects.

```python
fields = [
    "id", "machine_id", "gpu_name", "gpu_ram", "cpu_cores_effective",
    "cpu_ram", "disk_space", "disk_bw", "inet_up", "inet_down",
    "inet_up_cost", "inet_down_cost", "dph_total", "dph_base",
    "reliability2", "duration", "geolocation", "cuda_max_good",
    "driver_version", "direct_port_count", "dlperf",
]
safe_rows = [{key: row.get(key) for key in fields} for row in offers]
```
