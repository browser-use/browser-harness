# LinkedIn — Scrape someone's connections list via keyword-filtered People search

Mine a target user's network (1st-degree connections, plus optionally 2nd-degree via the asker's graph) by paginating the People-search results with the `connectionOf` filter pre-applied. Keyword sweep beats blanket-scrape — narrows from thousands of connections to ~hundreds of relevant hits, and stays well under LinkedIn's anti-scrape thresholds.

## When to use this

Use this when you have a 1st-degree connection (e.g. a parent, partner, or co-founder) whose own network you want to mine for warm-intro candidates. LinkedIn's People-search lets you filter by "Connections of X" — that returns the intersection of (your 1st+2nd graph) ∩ (X's 1st-degree connections). For a parent or close colleague the overlap is usually broad enough to be useful.

Don't use this for full graph dumps — use the Voyager profile API (`/voyager/api/identity/dash/profiles?q=memberIdentity`) for that. This skill is for **targeted relevance search across someone else's network.**

## The URL pattern

```
https://www.linkedin.com/search/results/people/
  ?connectionOf=%5B%22<MEMBER_URN>%22%5D
  &network=%5B%22F%22%2C%22S%22%5D
  &keywords=<KEYWORD>
  &page=<N>
  &origin=MEMBER_PROFILE_CANNED_SEARCH
```

- `connectionOf` is a JSON-array-encoded list of `MEMBER_URN` strings (just one URN in practice). Format: `ACoAA...` — get it from the target's `/in/<handle>/` profile page (see "Getting the member URN" below).
- `network=["F","S"]` = 1st + 2nd degree (relative to the *asker's* graph). Drop `"F"` to exclude direct connections; drop `"S"` to scope to direct only.
- `keywords=<KW>` is a free-text filter applied across name, headline, current company, past company, education. The same single-keyword caveats apply as anywhere on LinkedIn — narrow keywords beat broad ones.
- `page=<N>` is 1-indexed. LinkedIn caps People-search at **100 pages × 10 results = 1000 max per query**. Plan keyword sweeps so each keyword returns <1000 hits.
- `origin=MEMBER_PROFILE_CANNED_SEARCH` is what LinkedIn sets when the user clicks "See all" on a profile's connections — using it identifies the search shape as a legitimate UI flow and reduces friction.

## Getting the member URN

Open the target's profile (`/in/<handle>/`) while logged in, then run:

```python
js("""(() => {
    // The URN is embedded in many places. Most reliable:
    // 1. Look for a 'urn:li:fsd_profile:ACoAA...' in any DOM attribute
    const m = document.body.innerHTML.match(/urn:li:fsd_profile:([\\w-]+)/);
    return m ? m[1] : null;
})()""")
```

Returns the URN string (`ACoAA...` plus ~30 characters). Use that as `<MEMBER_URN>` in the search URL.

## Result-card extraction — the key DOM pattern

LinkedIn's 2026 People-search DOM uses obfuscated CSS-module class names (e.g. `_83309bd4 _6e63fa0b d343d86c`) that rotate per build. **Don't selector-hunt for cards** — go straight to the profile anchors and use their `innerText` to read the whole card payload.

Each result card has at least one anchor pointing to `/in/<handle>/` whose `innerText` contains the full card payload joined by `\n`:

```
<Name> • <Degree>

<Headline>

<Location>

Connect

[Past: ...]  | [Summary: ...]  | [Current: ...]   (optional)

<Mutuals>  e.g. "<Mutual Name> and N other mutual connections"
```

Multiple anchors point at the same profile (image link + name link + headline link); dedupe by `URL.pathname`.

The minimum filter:

```python
items = js("""(() => {
    const anchors = Array.from(document.querySelectorAll('a[href*="/in/"]'));
    const out = [];
    const seen = new Set();
    for (const a of anchors) {
        const u = new URL(a.href);
        if (!u.pathname.match(/^\\/in\\/[^/]+\\/?$/)) continue;  // strict /in/<handle> only
        if (!a.innerText.includes('•')) continue;                // skip thumbnail-only links
        const href = u.pathname.replace(/\\/$/, '');
        if (seen.has(href)) continue;
        seen.add(href);
        out.push({href, text: a.innerText});
    }
    return out;
})()""")
```

Then parse `text` line-by-line. The first line is `"<Name> • <Degree>"` (split on `•`). The line containing `"mutual connection"` is the mutuals. Lines `"Connect" / "Message" / "Follow"` are buttons — skip. Lines starting `"Past:" / "Summary:" / "Current:"` are auto-generated keyword highlights — useful for relevance scoring. Lines starting `"Select all" / "Add N people to folk"` are list-controls — skip.

## Pagination

Scroll-load won't help — LinkedIn paginates server-side. After landing on `&page=1`, navigate to `&page=2`, etc. Each page returns at most 10 results.

Stopping conditions:
- A page returns 0 new (deduped) results → keyword exhausted, move on
- A page returns fewer than ~5 cards → last page of results
- `page=100` reached → LinkedIn cap; if the keyword is broader than 1000 hits you need a tighter keyword

Sleep ~2s per page-load via `time.sleep(2)` after `wait_for_load`. Sleep ~1s between keywords. LinkedIn does not aggressively rate-limit People-search at this pace from a real logged-in session.

## Anti-bot

**Use a real signed-in Chrome session, not headless.** LinkedIn fingerprints heavily. The `feedback_real_chrome_beats_headless_for_anti_bot` lesson applies — `start_remote_daemon` with a clean profile gets you 1-3 results then a soft-block. The user's actual Chrome with all cookies + extensions + real navigator fingerprint sails through.

No `stealth_patch()` needed when on real-Chrome — only useful in headless/cloud mode.

## Tab management gotcha

`new_tab(url)` creates a new tab but `switch_tab()` is required to make subsequent `js()` / `goto()` calls target it. If the user manually switches tabs between calls, the daemon may follow their focus — list tabs and explicitly switch back:

```python
tabs = list_tabs(include_chrome=False)
linkedin_tab = next((t for t in tabs if 'linkedin.com/search' in t.get('url','')), None)
if linkedin_tab:
    switch_tab(linkedin_tab['targetId'])
```

## Keyword strategy

Hit-rate per keyword varies wildly. Sample patterns from a real run against a target with a regional emerging-markets business network (39 keywords, ~380 unique results, ~10 min wall-time):

| Keyword type | Example | Typical hits |
|---|---|---|
| **Geographic country** | a target-region country name | 50-80 |
| **Geographic city** | a target-region city name | 0-20 |
| **Broad industry** | `engineering`, `trading`, `logistics` | 50-100 (high noise) |
| **Specific company** | a named target company | 0-3 (high precision) |
| **Industry term** | `manufacturing`, `procurement`, `mining` | 5-15 |
| **Niche term** | a specific product or technology | 0 (target may not have these) |

**Geo-keywords yield best per-query precision for finding "people in X country who do Y."** Company-name keywords are highest precision but often return 0 because exact-employer-match is rare in a non-overlapping network. Industry terms are middle — broad enough to surface candidates, narrow enough to filter noise.

## End-to-end runnable script

Self-contained. Replace `CONN_OF` with the target's URN (see "Getting the member URN" above) and `TARGET_LABEL` + `KEYWORDS` for your search. Run via `browser-harness < scrape.py` from a real-Chrome session signed into LinkedIn. Re-runnable + resume-safe — dedupes against prior output, appends only.

```python
import time, json, urllib.parse
from pathlib import Path

# === EDIT THESE ===
CONN_OF = "ACoAA<...REPLACE WITH TARGET URN...>"
TARGET_LABEL = "target_label"   # used in output filename
KEYWORDS = [
    # broad industry
    "engineering", "trading", "logistics", "manufacturing",
    # named companies you care about
    "AcmeCorp", "TargetCo",
    # geographies
    "Country1", "City1",
]
MAX_PAGES_PER_KEYWORD = 10  # LinkedIn caps at 100; 10 is usually plenty per keyword

# === END EDIT ===

BASE = (f"https://www.linkedin.com/search/results/people/"
        f"?connectionOf=%5B%22{CONN_OF}%22%5D"
        f"&network=%5B%22F%22%2C%22S%22%5D"
        f"&origin=MEMBER_PROFILE_CANNED_SEARCH")

OUT = Path(f"/tmp/{TARGET_LABEL}_connections.jsonl")
OUT.parent.mkdir(parents=True, exist_ok=True)

seen = set()
if OUT.exists():
    for line in OUT.read_text().splitlines():
        try:
            r = json.loads(line)
            seen.add(r.get("href", ""))
        except Exception:
            pass

def parse_card(text, href):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines: return None
    parts = lines[0].split("•")
    name = parts[0].strip()
    degree = parts[1].strip() if len(parts) > 1 else ""
    headline = lines[1] if len(lines) > 1 else ""
    location, mutuals, summary = "", "", ""
    for l in lines[2:]:
        if l in ("Connect","Message","Follow") or l.startswith("Select all") or l.startswith("Add "):
            continue
        if "mutual connection" in l.lower() or " is a mutual" in l.lower():
            mutuals = l
        elif l.startswith(("Past:","Summary:","Current:")):
            summary += (" | " + l) if summary else l
        elif not location:
            location = l
    return {"href": href, "name": name, "degree": degree, "headline": headline,
            "location": location, "summary": summary, "mutuals": mutuals}

def scrape_current_page():
    for _ in range(3):
        js("window.scrollBy(0, 1200)")
        time.sleep(0.6)
    js("window.scrollTo(0, document.body.scrollHeight)"); time.sleep(1.2)
    js("window.scrollTo(0, 0)"); time.sleep(0.4)
    return js("""(() => {
        const anchors = Array.from(document.querySelectorAll('a[href*="/in/"]'));
        const out = [], seen = new Set();
        for (const a of anchors) {
            const u = new URL(a.href);
            if (!u.pathname.match(/^\\/in\\/[^/]+\\/?$/)) continue;
            if (!a.innerText.includes('•')) continue;
            const href = u.pathname.replace(/\\/$/, '');
            if (seen.has(href)) continue;
            seen.add(href);
            out.push({href, text: a.innerText});
        }
        return out;
    })()""") or []

for kw in KEYWORDS:
    url = BASE + "&keywords=" + urllib.parse.quote(kw)
    goto(url); wait_for_load(timeout=20); time.sleep(2.5)
    for page in range(1, MAX_PAGES_PER_KEYWORD + 1):
        if page > 1:
            goto(url + f"&page={page}"); wait_for_load(timeout=20); time.sleep(2)
        cards = scrape_current_page()
        if not cards: break
        new = 0
        with OUT.open("a") as f:
            for c in cards:
                if c["href"] in seen: continue
                rec = parse_card(c["text"], c["href"])
                if not rec: continue
                rec["keyword"] = kw
                f.write(json.dumps(rec, ensure_ascii=True) + "\n")
                seen.add(c["href"]); new += 1
        print(f"  [{kw}] page {page}: {len(cards)} cards, {new} new")
        if new == 0 and page > 1: break
        if len(cards) < 5: break
    time.sleep(1.0)

print(f"DONE — total unique: {len(seen)}, output: {OUT}")
```

## Post-processing — scoring for relevance

Raw output is high-recall, low-precision. Run a scoring pass with regex tiers for:
- **Tier 1 (50pt)** named target companies — exact-match to the specific employers you're hunting
- **Tier 2 (25pt)** industry vocab — domain-relevant role and function keywords
- **Tier 3 (20pt)** adjacent-industry vocab — named market participants, related sectors
- **Geography (15pt)** target-region location strings
- **Government (10pt)** `minister`, `ambassador`, `consul` when paired with geography (if you're hunting through diplomatic/state channels)
- **Noise penalty (-15pt)** disqualifying terms relevant to the target's adjacent industries (e.g. for a B2B sourcing search, penalize `tourism`, `hotel`, `fashion`, `media`, `advertising`, `software engineer` — these flood broad networks)

Sort descending. Cut at score ≥ a threshold matched to your tolerance for noise (15 is reasonable when geography alone qualifies).

## What this does NOT give you

- **Email addresses.** Profile anchors don't carry them. Use `voyager_scrape_2026-04-25.py` per-handle for full profile dumps if you need positions/education/etc.
- **3rd-degree connections of the target.** The `network` parameter is relative to the asker's graph, not the target's. To enumerate the target's full 1st-degree network you'd need to log in as the target.
- **Hidden profiles.** People who set their connections to private won't appear regardless of the filter.

## Watch out for

- **The URL must use percent-encoded JSON in `connectionOf` and `network`.** `%5B` = `[`, `%5D` = `]`, `%22` = `"`. Bare brackets will silently 400 or redirect to an empty result page.
- **Profile-card anchor `innerText` includes a trailing `Connect` / `Message` / `Follow` button label.** Filter it out during parsing.
- **The first profile anchor on a card has the full payload; subsequent same-`/in/`-handle anchors have just the name.** Dedupe by pathname before parsing.
- **Some profiles render `<Name> \n  • <Degree>` with the bullet on a separate line.** Split on `•` not on `\n` for the first parse.
