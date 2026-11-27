# Close CRM (app.close.com) — reading data through the logged-in session

Close's public REST API (`/api/v1/...`) answers same-origin requests from a logged-in
`app.close.com` tab using the session cookie. No API key is needed, and it is far faster
than scraping the lead and contact lists, which are virtualised.

## Auth: cookie requests need `organization_id`

A cookie-authenticated call without an organization fails:

```
HTTP 400 {"error": "An 'organization_id' parameter is required for this endpoint when
authenticated via cookie. ..."}
```

The error text itself contains a ready-made example URL with the user's `orga_...` id, and
points at `/api/v1/me/?_fields=organizations` for the full list. Read the id from there at
run time; never hard-code or publish it.

## Bulk export pattern

```python
new_tab("https://app.close.com/"); wait_for_load(); wait(3)

def fetch_all(path, fields, org):
    out, skip = [], 0
    while True:
        url = f"/api/v1/{path}/?_limit=100&_skip={skip}&_fields={fields}&organization_id={org}"
        r = json.loads(js(
            "(async()=>{const r=await fetch(%s,{credentials:'include',"
            "headers:{'Accept':'application/json'}});"
            "return JSON.stringify({status:r.status,body:await r.text()})})()" % json.dumps(url)))
        if r["status"] != 200:
            raise RuntimeError(r["body"][:300])
        body = json.loads(r["body"])
        out += body["data"]
        if not body.get("has_more"):
            return out
        skip += 100

contacts = fetch_all("contact", "id,name,title,lead_id,emails", org)
leads    = fetch_all("lead", "id,display_name,url,status_label,date_created", org)
```

- Response shape is `{"data": [...], "has_more": bool}`. Page with `_skip`; stop when
  `has_more` is false.
- `_fields` trims the payload. Useful ones: contact `id,name,title,lead_id,emails,phones`;
  lead `id,display_name,url,status_label,date_created`.
- A contact's addresses are a list: `emails[].email` (the first is the primary). Join
  contacts to leads on `lead_id`.
- `_limit=100` works for both endpoints; 800 contacts and 750 leads export in a few seconds.

## Notes

- `https://app.close.com/` redirects to `/tasks/inbox/` when logged in, so `page_info()`
  showing that path is a quick logged-in check. A login page instead means stop and ask
  the user.
- Return the JSON to Python and write it to a local file there; don't try to download from
  the page.
