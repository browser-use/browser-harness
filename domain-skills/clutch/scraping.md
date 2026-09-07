# Clutch — B2B service-provider directory (agencies, dev shops, consultancies)

Field-tested 2026-09-02 from a Browser Use cloud browser (US proxy). Browser required; `http_get` is not needed once you know the URL.

## URL patterns (the obvious ones 404)

| Works | 404 |
|---|---|
| `https://clutch.co/developers/artificial-intelligence` | `/agencies/artificial-intelligence`, `/agencies/corporate-training` |
| `https://clutch.co/developers/<category-slug>` (e.g. `/developers/mobile-application`) | `/it-services/ai-consulting`, `/hr/corporate-training`, `/hr/training`, `/business-services/corporate-training` |

The 404 page title is `404 - Not Found` — check `document.title` before extracting.

## Extraction: innerText is enough (no DOM selectors needed)

Each provider renders as a fixed block of lines in `document.body.innerText`:

```
<Name>
<rating float>          e.g. 4.8
<N> reviews
[Premier Verified|Verified]   (optional)
$<min project>+         e.g. $25,000+
$<lo> - $<hi> / hr      e.g. $50 - $99 / hr
<size>                  e.g. 50 - 249
<City, ST | City, Country>
SERVICES PROVIDED
<pct>% <service>        (repeated; last one may end "+N services")
<AI-generated review summary paragraph>
See all N projects / View Profile / Visit Website
```

Parser that worked on the first page (52 providers):

```python
import re, json
lines = [l.strip() for l in js("document.body.innerText").split("\n") if l.strip()]
rows, i = [], 0
while i < len(lines) - 8:
    if re.fullmatch(r"\d\.\d", lines[i+1]) and re.fullmatch(r"\d+ reviews?", lines[i+2]):
        j = i + 3; badge = ""
        if "Verified" in lines[j]: badge = lines[j]; j += 1
        minp = lines[j] if lines[j].startswith("$") else "";  j += bool(minp)
        rate = lines[j] if "/ hr" in lines[j] else "";        j += bool(rate)
        size = lines[j] if re.fullmatch(r"[\d,]+ - [\d,]+|[\d,]+\+|Freelancer", lines[j]) else ""; j += bool(size)
        loc = lines[j]; j += 1
        services = []
        if lines[j] == "SERVICES PROVIDED":
            j += 1
            while j < len(lines) and re.match(r"\d+% ", lines[j]): services.append(lines[j]); j += 1
        rows.append({"name": lines[i], "rating": float(lines[i+1]), "reviews": int(lines[i+2].split()[0]),
                     "badge": badge, "min_project": minp, "hourly": rate, "size": size, "location": loc, "services": services})
        i = j
    else:
        i += 1
```

## Notes
- First page = ~50 providers, sorted by Clutch's sponsored/"Premier Verified" ranking; use `?page=2` for more.
- Locations are `City, ST` for US and `City, Country` elsewhere — filter US with `re.search(r", [A-Z]{2}$", loc)`.
- Full-page screenshot of the listing is ~17k px tall; take viewport shots per block if you need images.
- Wait `wait(4)` after `wait_for_load()`; the page is server-rendered but the review summaries hydrate late.
