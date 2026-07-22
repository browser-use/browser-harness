# Notion — read a database's full layout schematic (v3 API)

Given any Notion database URL, extract the complete page-layout schematic — pinned properties (in order), standalone/dedicated property modules, module order, named property groups + membership + order, property visibility, sub-items wiring, and automation ids — none of which the public REST API exposes.

**Mechanism:** call Notion's internal v3 API from inside the user's logged-in tab via `js()` fetch. The session cookie rides along in-browser; no token is ever extracted, stored, or logged. Read-only endpoint (`syncRecordValues`).

## Where layout state lives (internal data model)

- **`block`** (the DB page, type `collection_view_page`) → `format.collection_pointer` → the collection id + spaceId. Use this to resolve a URL to a collection.
- **`collection`** (= public API "data source") → `schema` (property id → {name, type}) and `format`:
  - `property_groups`: `[{id, title, propertyIds[]}]` — named groups, ordered, with ordered membership.
  - `layout_pointer`: `{table: "layout", id, spaceId}` — present **only when the page layout was customized**; absent = default layout.
  - `property_visibility`: `[{property, visibility: show|hide|hide_if_empty}]`.
  - `collection_page_properties`: ordered `[{property, visible}]` (legacy page-property list; keeps **ghost entries for deleted properties**).
  - `collection_page_sections`, `page_section_visibility` (comments/backlinks config), `subitem_property` (sub-items relation id), `automation_ids[]`.
- **`layout`** (own record type, parent = collection) → `modules.page_layout_schema`: ordered module list:
  - `{type: "titleWithIcon", propertyIds[]}` — **the pinned chips, in display order**.
  - `{type: "property", propertyId, config}` — a **standalone/dedicated property module** (e.g. `property_file` with style).
  - `{type: "properties"}` — the property section; `relationsGroup`, `cover`, `discussions`, `editor`.
- **`automation`** (own record type, ids from `automation_ids`) → `trigger`, `action_ids`, `status`, `properties` — DB automations ARE readable here (the public API has none of this).

## Recipe

1. `new_tab('https://app.notion.com')` — must be app.notion.com; `notion.so` bounces logged-out visitors to the marketing site. If you land on a workspace page, the session is live. Auth wall → stop and ask the user.
2. Resolve the URL's page id (32-hex in the path, dashed form) to the collection:

```python
browser-harness -c "
import json
r = js('''(async () => {
  const bid = '<dashed-page-id>';
  const sync=async(reqs)=>(await fetch('/api/v3/syncRecordValues',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({requests:reqs})})).json();
  let j=await sync([{pointer:{table:'block',id:bid},version:-1}]);   // spaceId optional for block lookup
  const blk=j.recordMap.block[bid].value.value;
  return JSON.stringify(blk.format.collection_pointer || (blk.format.collection_pointers||[])[0]);
})()''')
print(r)
"
```

3. Fetch collection (+ layout when `layout_pointer` exists) and render the schematic:

```python
browser-harness -c "
import json
r = js('''(async () => {
  const SPACE='<spaceId>', COLL='<collection-id>';
  const sync=async(reqs)=>(await fetch('/api/v3/syncRecordValues',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({requests:reqs})})).json();
  let j=await sync([{pointer:{table:'collection',id:COLL,spaceId:SPACE},version:-1}]);
  const coll=j.recordMap.collection[COLL].value.value;
  const nameOf=id=>coll.schema[id]?.name||('<'+id+'>');
  const f=coll.format||{};
  let out=['DB: '+coll.name[0][0]];
  if(f.layout_pointer){
    j=await sync([{pointer:f.layout_pointer,version:-1}]);
    const lay=j.recordMap.layout[f.layout_pointer.id].value.value;
    out.push('PAGE LAYOUT (module order):');
    for(const m of lay.modules.page_layout_schema){
      if(m.type==='titleWithIcon') out.push('  [title] pinned: '+(m.propertyIds||[]).map(nameOf).join(' | '));
      else if(m.type==='property') out.push('  [module] standalone: '+nameOf(m.propertyId)+(m.config?' '+JSON.stringify(m.config):''));
      else out.push('  ['+m.type+']');
    }
  } else out.push('PAGE LAYOUT: default (no layout record)');
  out.push('PROPERTY GROUPS:');
  for(const g of f.property_groups||[]) out.push('  '+g.title+' ('+g.propertyIds.length+'): '+g.propertyIds.map(nameOf).join(', '));
  if(f.subitem_property) out.push('SUB-ITEMS via: '+nameOf(f.subitem_property));
  const hidden=(f.property_visibility||[]).filter(p=>p.visibility!=='show');
  out.push('HIDDEN PROPS: '+(hidden.length?hidden.map(p=>nameOf(p.property)).join(', '):'none'));
  out.push('AUTOMATIONS: '+((f.automation_ids||[]).length));
  return JSON.stringify(out);
})()''')
print(chr(10).join(json.loads(r)))
"
```

4. Automations detail (optional): `sync([{pointer:{table:'automation',id:<id>,spaceId:SPACE},version:-1}])` → `trigger`, `action_ids`, `status`.

## Traps

- **Double envelope:** records are at `recordMap.<table>[id].value.value` — the first `.value` wraps `{value, role}`.
- **`layout_pointer` absent ≠ error** — it means the DB uses the default layout (nothing was customized).
- **Ghost properties:** `collection_page_properties` and even layout `propertyIds` can reference deleted properties — `nameOf` misses resolve to `<id>`; report, don't crash.
- **Escaping:** never put `\n` inside the `js('''…''')` string (bash+python eat backslashes → JS syntax error → `js()` returns `None`). Return `JSON.stringify(array)` and join in Python.
- **Ids:** URLs use bare 32-hex; v3 pointers need the dashed UUID form.
- **This is Notion's private, unversioned API** — shapes can change without notice. Field names above verified 2026-07-22.
- Do not write via v3 (`saveTransactions`) from this recipe — read-only.
