# Hurun India — Rich Lists

`https://hurunindia.com` is an Angular SPA. All data comes from a private JSON API at `https://api.hurunindia.com/`. The full lists are a paid subscription; the catalogue, pricing and top 10 of each list are free. Do not try to get around the paywall — the auto-mode classifier blocks it and it's a ToS violation anyway. With a paid account the fetch is two API calls.

## Free, no auth (plain `http_get`)

```python
import json
types = json.loads(http_get("https://api.hurunindia.com/hurun-list/type"))["data"]      # catalogue: id, name, pillarIDs
plans = json.loads(http_get("https://api.hurunindia.com/plan/"))["data"]                # pricing (INR / year)
top10 = json.loads(http_get("https://api.hurunindia.com/top10?listTypeID=<typeID>"))["data"][0]["contents"]
```

Also free: `top10/list-types`, `hurun-list/type/`. Everything under `hurun-list/contents`, `hurun-list/dynamic/contents` returns 401 without a token and 403 (`"Please upgrade to view this information"`) with a token but no matching plan.

## Two kinds of list — the ID trap

There are **static** lists (`hurun-list/contents?listID=`) and **dynamic** lists (`hurun-list/dynamic/contents?listID=`). Recent lists (2025 onward) are dynamic. The `id` returned by `/top10` is the top-10 document's own id, **not** the list id — using it against `/contents` gives a 403 that looks like a subscription problem. Get the real list id from the dynamic catalogue:

```python
# GET hurun-list/dynamic?year=2026  (auth required)
# -> data[]: {id, title, year, type, isPublished, tableHeaders[], listTypeID, pillars[]}
```

`hurun-list/?pillarID=...`, `hurun-list/?listTypeID=...` and `hurun-list/dynamic?pillarID=...` all return `{"data": null}` — only `year=` filters work on the dynamic catalogue.

## Auth

The bearer token is in `localStorage["token"]` after login (other keys are Razorpay checkout ids). Calls from inside the logged-in tab via `js()` + `fetch` are the simplest path and are exactly what the page does:

```python
raw = js("""
(async () => {
  const tok = localStorage.getItem("token");
  const r = await fetch("https://api.hurunindia.com/hurun-list/dynamic/contents?listID=<listID>",
    {headers: {"Content-Type": "application/json", "Authorization": "Bearer " + tok}});
  return JSON.stringify({status: r.status, body: await r.text()});
})()
""")
```

Check entitlement with `user/subscription/` (`isActive`, `activePlanIDs`) and `user/profile/`.

## Response shape (dynamic contents)

```
data.headers  : ["Rank","Name","Wealth 2026 (INR Cr)","Company","Industry","City of Residence"]
data.cells[]  : {id, listID, entityType, entityID, rank, name, rowData{<header>: str}, imagePath}
```

- Wealth is a string with Indian digit grouping (`"9,22,800"`) — strip commas before `int()`.
- Ranks tie: several rows share the same `rank` at the bottom of the list.
- One list is ~1,800 rows / ~680 KB in a single response; no pagination.
- `entity/individual/<entityID>` exists but the records are empty shells (no age, born, sourceOfWealth, selfMade). `entity/wealth-history/entity/<id>` and `entity/award/entity/<id>` return 404. Don't plan on per-person enrichment.

## Account gotchas

- Accounts migrated from the old site exist (register says "already exists") but login says "Couldn't find your account" even after a password reset. Registering with a fresh email (a Gmail `+alias` works) is the fast fix.
- Password reset mail comes from `no-reply@hurunindia.com`, link valid 2 hours, often lands in spam.
