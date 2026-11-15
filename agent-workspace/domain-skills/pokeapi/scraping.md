# PokeAPI - Pokemon Stats, Types, Abilities and Evolution Chains (official REST API)

Field-tested against pokeapi.co on 2026-11-05 using a Browser Use cloud browser (logged out) plus `curl` from a laptop. About 270 browser API calls (78 in the final verbatim run of blocks 1 and 2) and about 20 curl calls, all serial: no 429, no CAPTCHA, no challenge. Non-200 answers: JSON 404 for unknown names, and HTTP 403 only on the two firewall-rule probes and the default-urllib User-Agent probe described below.

robots.txt (pokeapi.co/robots.txt, read in the browser 2026-11-05): only Cloudflare's commented content-signal notice; no `User-agent`, `Disallow` or `Content-Signal` lines and no named AI-agent groups, so nothing is disallowed, and `/api/v2/` is PokeAPI's documented public API (https://pokeapi.co/docs/v2: "No authentication is required").

## Quick summary

- **No scraping.** One public JSON API, GET only, no key, no cookies. Five endpoints cover the task:
  - `GET /api/v2/pokemon/<name or id>/` - types, base stats, abilities (with hidden flag), height, weight, `past_types`, `past_abilities`. About 370 KB, mostly `moves`.
  - `GET /api/v2/pokemon-species/<name or id>/` - genus, generation, legendary/mythical, `varieties` (forms), `evolution_chain.url`.
  - `GET /api/v2/evolution-chain/<id>/` - the whole family as a tree, with how each step happens.
  - `GET /api/v2/ability/<name>/` - effect text (`effect_entries`, `flavor_text_entries`, many languages).
  - `GET /api/v2/type/<name>/` - `damage_relations` (2x / 0.5x / 0x, to and from).
- **Species is not Pokemon.** `pokemon-species/deoxys` exists, `pokemon/deoxys` is 404; the default Pokemon is `deoxys-normal`. Always go species -> `varieties[is_default]` -> pokemon. 1,025 species, 1,351 pokemon (forms such as `charizard-mega-x`, id 10034).
- **Never send display names.** PokeAPI's firewall answers HTTP 403 with a Cloudflare HTML page for any URL containing `. , * % ; : ' ! @ + [` and for query parameters other than `limit` / `offset` (docs "Active policies"; `pokemon/mr.mime` and `pokemon?name=pikachu` were 403, `pokemon/mr-mime` 200). Block 1 maps `Mr. Mime` -> `mr-mime` and matches it against the official name lists before calling.
- **Evolution details are per game.** A step can have several `evolution_details` entries: one per game group where the method changed (leafeon: 6), plus one per regional form (`raichu-alola`, `perrserker` from `meowth-galar`). Block 1 groups them by (from form, into form) and shows the entry flagged `is_default`.
- **Cache.** PokeAPI's fair use policy: "Locally cache resources whenever you request them"; rate limiting "has been removed entirely, but we still encourage you to limit the frequency of requests". Responses carry `cache-control: public, max-age=86400`. The blocks cache each URL in the page and pause 0.25 s between calls, serially.

## What works

### 1. Stats, types, matchups, abilities and evolution chain for any name (browser)

`on_pokeapi_tab()` opens `https://pokeapi.co/robots.txt` (small, allowed) once and later calls reuse that tab; `fetch()` there is same-origin. `get(url, pick)` keeps the parsed JSON in `window.__poke` and returns only what the JS `pick` function selects, `None` on 404, backs off on 429/5xx and otherwise raises, so a 403 never looks like "no such Pokemon".

```python
import json, time, unicodedata

POKEMON = ["charizard", "eevee", "Mr. Mime", "deoxys", "toxel", "Flabébé", "pikachu-no-such-form"]   # species, display or form names

PAUSE = 0.25   # seconds between API calls, serial; PokeAPI asks clients to keep request volume low and to cache
API = "https://pokeapi.co/api/v2/"
ATTACK_TYPES = ["normal", "fire", "water", "electric", "grass", "ice", "fighting", "poison", "ground",
                "flying", "psychic", "bug", "rock", "ghost", "dragon", "dark", "steel", "fairy"]

def on_pokeapi_tab():
    """fetch() runs from a logged-out pokeapi.co tab (same origin as the API). Reuse the tab if already there."""
    try:
        if js("location.origin") == "https://pokeapi.co":
            return
    except Exception:
        pass
    new_tab("https://pokeapi.co/robots.txt")   # small and allowed: the file has no User-agent or Disallow lines
    wait_for_load()
    if "content signals" not in (js("document.body.innerText.slice(0, 300)") or ""):
        raise RuntimeError(f"pokeapi.co did not serve robots.txt (title {js('document.title')!r}): stop, do not retry around it")

START_JS = """(() => { const u = %s; window.__poke = window.__poke || {};
  if (window.__poke[u] && window.__poke[u].status === 200) return 'cached';
  window.__poke[u] = null;
  fetch(u, {credentials: 'omit'}).then(async r => { const t = await r.text(); let d = null; try { d = JSON.parse(t); } catch (e) {}
      window.__poke[u] = {status: r.status, data: d, text: t.slice(0, 200)}; })
    .catch(e => { window.__poke[u] = {status: 0, data: null, text: String(e)}; });
  return 'started'; })()"""

def get(url, pick="d => d", timeout=60, tries=3):
    """fetch() url in the page, keep the parsed JSON there (one /pokemon/ record is ~370 KB, mostly moves) and
    return pick(json). pick is a JS arrow function. None on 404 (unknown name); backs off on 429/5xx; else raises."""
    url = url if url.startswith("http") else API + url
    u = json.dumps(url)
    for attempt in range(tries):
        if js(START_JS % u) == "started":
            t0 = time.time()
            while js("(() => { const x = window.__poke[%s]; return x ? x.status : null; })()" % u) is None:
                if time.time() - t0 > timeout:
                    raise RuntimeError(f"{url}: no response in {timeout}s")
                time.sleep(0.2)
            time.sleep(PAUSE)
        st = js("window.__poke[%s].status" % u)
        if st == 200:
            return js("(%s)(window.__poke[%s].data)" % (pick, u))
        if st == 404:
            return None
        if st not in (0, 429, 500, 502, 503, 504) or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {st} {js('window.__poke[%s].text' % u)!r}; stopping")
        time.sleep(5 * 2 ** attempt)

def slug(name):
    """Display name -> API name: 'Mr. Mime' -> 'mr-mime', "Farfetch'd" -> 'farfetchd', 'Flabébé' -> 'flabebe', 'Nidoran♀' -> 'nidoran-f'."""
    s = name.lower().strip().replace("♀", "-f").replace("♂", "-m")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    for ch in ".'’:":
        s = s.replace(ch, "")
    return "-".join(s.split())

def names(kind):
    """Every API name of a list endpoint in one call (pokemon-species: 1,025; pokemon: 1,351 incl. forms)."""
    return get(f"{kind}/?limit=100000", "d => d.results.map(r => r.name)")

def resolve(name):
    """(species name, pokemon name), or None. Matches against the official name lists first, so no request ever
    carries a character PokeAPI's firewall blocks ('.', '%', ':', "'", ...)."""
    s = slug(name)
    if s in SPECIES:
        return s, get(f"pokemon-species/{s}/", "d => d.varieties.find(v => v.is_default).pokemon.name")
    if s in POKES:
        return get(f"pokemon/{s}/", "d => d.species.name"), s
    return None

POKEMON_PICK = """d => ({id: d.id, name: d.name, height_m: d.height / 10, weight_kg: d.weight / 10,
  types: d.types.map(t => t.type.name),
  past_types: d.past_types.map(p => [p.generation.name, p.types.map(t => t.type.name)]),
  stats: Object.fromEntries(d.stats.map(s => [s.stat.name, s.base_stat])),
  abilities: d.abilities.map(a => ({name: a.ability.name, hidden: a.is_hidden}))})"""

SPECIES_PICK = """d => ({genus: (d.genera.find(g => g.language.name === 'en') || {}).genus, generation: d.generation.name,
  legendary: d.is_legendary, mythical: d.is_mythical, chain: d.evolution_chain && d.evolution_chain.url,
  varieties: d.varieties.map(v => v.pokemon.name)})"""

ABILITY_PICK = """d => { const e = d.effect_entries.find(x => x.language.name === 'en');
  const f = d.flavor_text_entries.filter(x => x.language.name === 'en').pop();
  return (e ? e.short_effect : (f ? f.flavor_text : '')).replace(/\\s+/g, ' '); }"""

# Tree -> flat list. Each node keeps its evolution_details with empty fields dropped and named refs reduced to names.
CHAIN_PICK = """d => { const out = [];
  const strip = e => Object.fromEntries(Object.entries(e)
      .filter(([k, v]) => v !== null && v !== '' && v !== false && !(Array.isArray(v) && !v.length))
      .map(([k, v]) => [k, Array.isArray(v) ? v.map(x => x.name || x) : (v.name !== undefined ? v.name : v)]));
  const walk = (n, depth, from) => { out.push({depth, species: n.species.name, from, baby: n.is_baby, details: n.evolution_details.map(strip)});
    n.evolves_to.forEach(c => walk(c, depth + 1, n.species.name)); };
  walk(d.chain, 0, null); return out; }"""

SKIP = {"trigger", "version_group", "is_default", "required_pokemon_form", "evolved_pokemon_form"}

def routes(node):
    """One line per distinct (from form -> into form) route. evolution_details has one entry per game group;
    keep the entry flagged is_default, else the newest, and say how many entries the route has."""
    groups = {}
    for d in node["details"]:
        groups.setdefault((d.get("required_pokemon_form"), d.get("evolved_pokemon_form")), []).append(d)
    lines = []
    for (req, into), ds in groups.items():
        x = next((d for d in ds if d.get("is_default")), ds[-1])
        parts = [x["trigger"]]
        for k, v in x.items():
            if k in SKIP:
                continue
            if k == "allowed_natures":
                v = f"{len(v)} natures ({', '.join(v[:3])}, ...)"
            elif k == "condition_expression":
                v = f"{v.get('percentage_chance')}% chance"
            elif isinstance(v, list):
                v = ",".join(map(str, v))
            parts.append(f"{k}={v}")
        label = (f"from {req} " if req and req != node["from"] else "") + (f"into {into} " if into and into != node["species"] else "")
        lines.append(f"{label}{' '.join(parts)} ({x['version_group']}{f', {len(ds)} entries' if len(ds) > 1 else ''})")
    return lines

def defensive(types):
    """Damage multiplier of each attacking type against this type combination (current type chart, abilities ignored)."""
    mult = {t: 1.0 for t in ATTACK_TYPES}
    for t in types:
        rel = get(f"type/{t}/", "d => Object.fromEntries(Object.entries(d.damage_relations).map(([k, v]) => [k, v.map(x => x.name)]))")
        for a in rel["double_damage_from"]: mult[a] *= 2
        for a in rel["half_damage_from"]: mult[a] *= 0.5
        for a in rel["no_damage_from"]: mult[a] *= 0
    return mult

def report(name):
    hit = resolve(name)
    if not hit:
        return None
    sp_name, pk_name = hit
    p = get(f"pokemon/{pk_name}/", POKEMON_PICK)
    sp = get(f"pokemon-species/{sp_name}/", SPECIES_PICK)
    for a in p["abilities"]:
        a["effect"] = get(f"ability/{a['name']}/", ABILITY_PICK)
    chain = get(sp["chain"], CHAIN_PICK) if sp["chain"] else []
    return {"pokemon": p, "species": sp_name, "info": sp, "chain": chain, "defense": defensive(p["types"])}

on_pokeapi_tab()
SPECIES, POKES = set(names("pokemon-species")), set(names("pokemon"))
print(f"{len(SPECIES)} species, {len(POKES)} pokemon (forms included)")
for q in POKEMON:
    r = report(q)
    if r is None:
        print(f"\n{q!r}: not a PokeAPI species or pokemon name ({slug(q)})")
        continue
    p, sp, d = r["pokemon"], r["info"], r["defense"]
    print(f"\n{q!r} -> #{p['id']} {p['name']} | {sp['genus']} | {sp['generation']} | {'/'.join(p['types'])}"
          + "".join(f" (until {g}: {'/'.join(t)})" for g, t in p["past_types"])
          + f" | {p['height_m']} m, {p['weight_kg']} kg" + (" | legendary" if sp["legendary"] else "") + (" | mythical" if sp["mythical"] else ""))
    print("  base stats:", " ".join(f"{k}={v}" for k, v in p["stats"].items()), "| total", sum(p["stats"].values()))
    for a in p["abilities"]:
        print(f"  ability {a['name']}{' (hidden)' if a['hidden'] else ''}: {a['effect'][:110]}")
    print("  takes 2x+:", {t: m for t, m in d.items() if m > 1}, "| resists:", {t: m for t, m in d.items() if 0 < m < 1},
          "| immune:", [t for t, m in d.items() if m == 0])
    print("  evolution chain:")
    for n in r["chain"]:
        pad, how = "    " + "  " * n["depth"], routes(n)
        print(pad + n["species"] + (" [baby]" if n["baby"] else "") + (f"  <- {how[0]}" if len(how) == 1 else ""))
        for line in how if len(how) > 1 else []:
            print(pad + "  <- " + line)
    if len(sp["varieties"]) > 1:
        print("  varieties:", ", ".join(sp["varieties"]))
```

Output (from the run on 2026-11-05):

```text
1025 species, 1351 pokemon (forms included)

'charizard' -> #6 charizard | Flame Pokémon | generation-i | fire/flying | 1.7 m, 90.5 kg
  base stats: hp=78 attack=84 defense=78 special-attack=109 special-defense=85 speed=100 | total 534
  ability blaze: Strengthens Fire moves to inflict 1.5× damage at 1/3 max HP or less.
  ability solar-power (hidden): Increases Special Attack to 1.5× but costs 1/8 max HP after each turn during strong sunlight.
  takes 2x+: {'water': 2.0, 'electric': 2.0, 'rock': 4.0} | resists: {'fire': 0.5, 'grass': 0.25, 'fighting': 0.5, 'bug': 0.25, 'steel': 0.5, 'fairy': 0.5} | immune: ['ground']
  evolution chain:
    charmander
      charmeleon  <- level-up min_level=16 (red-blue)
        charizard  <- level-up min_level=36 (red-blue)
  varieties: charizard, charizard-mega-x, charizard-mega-y, charizard-gmax

'eevee' -> #133 eevee | Evolution Pokémon | generation-i | normal | 0.3 m, 6.5 kg
  base stats: hp=55 attack=55 defense=50 special-attack=45 special-defense=65 speed=55 | total 325
  ability run-away: Ensures success fleeing from wild battles.
  ability adaptability: Increases the same-type attack bonus from 1.5× to 2×.
  ability anticipation (hidden): Notifies all trainers upon entering battle if an opponent has a super-effective move, Self-Destruct, Explosion
  takes 2x+: {'fighting': 2.0} | resists: {} | immune: ['ghost']
  evolution chain:
    eevee
      vaporeon  <- use-item item=water-stone (red-blue)
      jolteon  <- use-item item=thunder-stone (red-blue)
      flareon  <- use-item item=fire-stone (red-blue)
      espeon  <- level-up min_happiness=160 time_of_day=day (gold-silver)
      umbreon  <- level-up min_happiness=160 time_of_day=night (gold-silver)
      leafeon  <- use-item item=leaf-stone (sword-shield, 6 entries)
      glaceon  <- use-item item=ice-stone (sword-shield, 6 entries)
      sylveon  <- level-up known_move_type=fairy min_happiness=160 (sword-shield, 2 entries)
  varieties: eevee, eevee-starter, eevee-gmax

'Mr. Mime' -> #122 mr-mime | Barrier Pokémon | generation-i | psychic/fairy (until generation-v: psychic) | 1.3 m, 54.5 kg
  base stats: hp=40 attack=45 defense=65 special-attack=100 special-defense=120 speed=90 | total 460
  ability soundproof: Protects against sound-based moves.
  ability filter: Decreases damage taken from super-effective moves by 1/4.
  ability technician (hidden): Strengthens moves of 60 base power or less to 1.5× their power.
  takes 2x+: {'poison': 2.0, 'ghost': 2.0, 'steel': 2.0} | resists: {'fighting': 0.25, 'psychic': 0.5} | immune: ['dragon']
  evolution chain:
    mime-jr [baby]
      mr-mime
        <- level-up known_move=mimic (diamond-pearl)
        <- into mr-mime-galar level-up known_move=mimic region=galar (sword-shield)
        mr-rime  <- from mr-mime-galar level-up min_level=42 (sword-shield)
  varieties: mr-mime, mr-mime-galar

'deoxys' -> #386 deoxys-normal | DNA Pokémon | generation-iii | psychic | 1.7 m, 60.8 kg | mythical
  base stats: hp=50 attack=150 defense=50 special-attack=150 special-defense=50 speed=150 | total 600
  ability pressure: Increases the PP cost of moves targetting the Pokémon by one.
  takes 2x+: {'bug': 2.0, 'ghost': 2.0, 'dark': 2.0} | resists: {'fighting': 0.5, 'psychic': 0.5} | immune: []
  evolution chain:
    deoxys
  varieties: deoxys-normal, deoxys-attack, deoxys-defense, deoxys-speed

'toxel' -> #848 toxel | Baby Pokémon | generation-viii | electric/poison | 0.4 m, 11 kg
  base stats: hp=40 attack=38 defense=35 special-attack=54 special-defense=35 speed=40 | total 242
  ability rattled: Raises Speed one stage upon being hit by a Dark, Ghost, or Bug move.
  ability static: Has a 30% chance of paralyzing attacking Pokémon on contact.
  ability klutz (hidden): Prevents the Pokémon from using its held item in battle.
  takes 2x+: {'ground': 4.0, 'psychic': 2.0} | resists: {'electric': 0.5, 'grass': 0.5, 'fighting': 0.5, 'poison': 0.5, 'flying': 0.5, 'bug': 0.5, 'steel': 0.5, 'fairy': 0.5} | immune: []
  evolution chain:
    toxel [baby]
      toxtricity
        <- into toxtricity-amped level-up min_level=30 allowed_natures=13 natures (hardy, docile, hasty, ...) (sword-shield)
        <- into toxtricity-low-key level-up min_level=30 allowed_natures=12 natures (bold, modest, calm, ...) (sword-shield)

'Flabébé' -> #669 flabebe | Single Bloom Pokémon | generation-vi | fairy | 0.1 m, 0.1 kg
  base stats: hp=44 attack=38 defense=39 special-attack=61 special-defense=79 speed=42 | total 303
  ability flower-veil: Protects friendly Grass Pokémon from having their stats lowered by other Pokémon.
  ability symbiosis (hidden): Passes the bearer's held item to an ally when the ally uses up its item.
  takes 2x+: {'poison': 2.0, 'steel': 2.0} | resists: {'fighting': 0.5, 'bug': 0.5, 'dark': 0.5} | immune: ['dragon']
  evolution chain:
    flabebe
      floette
        <- from flabebe-red into floette-red level-up min_level=19 (x-y)
        <- from flabebe-yellow into floette-yellow level-up min_level=19 (x-y)
        <- from flabebe-orange into floette-orange level-up min_level=19 (x-y)
        <- from flabebe-blue into floette-blue level-up min_level=19 (x-y)
        <- from flabebe-white into floette-white level-up min_level=19 (x-y)
        florges
          <- from floette-red into florges-red use-item item=shiny-stone (x-y)
          <- from floette-yellow into florges-yellow use-item item=shiny-stone (x-y)
          <- from floette-orange into florges-orange use-item item=shiny-stone (x-y)
          <- from floette-blue into florges-blue use-item item=shiny-stone (x-y)
          <- from floette-white into florges-white use-item item=shiny-stone (x-y)

'pikachu-no-such-form': not a PokeAPI species or pokemon name (pikachu-no-such-form)
```

### 2. Base stats across a whole evolution line, regional forms included (browser)

Self-contained (same helpers). Walks the chain and adds every form the chain's `evolution_details` name (`raichu-alola`, `meowth-galar`, `perrserker`). Form names that have no `/pokemon/` record of their own (`flabebe-red` is only a `/pokemon-form/`) are skipped; they share the default's stats.

```python
import json, time

LINES = ["pikachu", "meowth", "flabebe"]   # any species in the family, as API names (block 1 maps display names)

PAUSE = 0.25
API = "https://pokeapi.co/api/v2/"
STATS = ["hp", "attack", "defense", "special-attack", "special-defense", "speed"]

def on_pokeapi_tab():
    try:
        if js("location.origin") == "https://pokeapi.co":
            return
    except Exception:
        pass
    new_tab("https://pokeapi.co/robots.txt")
    wait_for_load()
    if "content signals" not in (js("document.body.innerText.slice(0, 300)") or ""):
        raise RuntimeError(f"pokeapi.co did not serve robots.txt (title {js('document.title')!r}): stop, do not retry around it")

START_JS = """(() => { const u = %s; window.__poke = window.__poke || {};
  if (window.__poke[u] && window.__poke[u].status === 200) return 'cached';
  window.__poke[u] = null;
  fetch(u, {credentials: 'omit'}).then(async r => { const t = await r.text(); let d = null; try { d = JSON.parse(t); } catch (e) {}
      window.__poke[u] = {status: r.status, data: d, text: t.slice(0, 200)}; })
    .catch(e => { window.__poke[u] = {status: 0, data: null, text: String(e)}; });
  return 'started'; })()"""

def get(url, pick="d => d", timeout=60, tries=3):
    """Same helper as block 1: pick(json) from an in-page fetch(), None on 404, backoff on 429/5xx, else raise."""
    url = url if url.startswith("http") else API + url
    u = json.dumps(url)
    for attempt in range(tries):
        if js(START_JS % u) == "started":
            t0 = time.time()
            while js("(() => { const x = window.__poke[%s]; return x ? x.status : null; })()" % u) is None:
                if time.time() - t0 > timeout:
                    raise RuntimeError(f"{url}: no response in {timeout}s")
                time.sleep(0.2)
            time.sleep(PAUSE)
        st = js("window.__poke[%s].status" % u)
        if st == 200:
            return js("(%s)(window.__poke[%s].data)" % (pick, u))
        if st == 404:
            return None
        if st not in (0, 429, 500, 502, 503, 504) or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {st} {js('window.__poke[%s].text' % u)!r}; stopping")
        time.sleep(5 * 2 ** attempt)

# Every species in the chain, with the form names its evolution_details mention (raichu-alola, meowth-galar, ...).
CHAIN_PICK = """d => { const out = [];
  const walk = (n, depth) => {
    const forms = new Set();
    n.evolution_details.forEach(e => e.evolved_pokemon_form && forms.add(e.evolved_pokemon_form.name));
    n.evolves_to.forEach(c => c.evolution_details.forEach(e => e.required_pokemon_form && forms.add(e.required_pokemon_form.name)));
    out.push({depth, species: n.species.name, forms: [...forms]});
    n.evolves_to.forEach(c => walk(c, depth + 1)); };
  walk(d.chain, 0); return out; }"""

STAT_PICK = """d => ({name: d.name, types: d.types.map(t => t.type.name).join('/'),
  stats: Object.fromEntries(d.stats.map(s => [s.stat.name, s.base_stat])), species: d.species.name})"""

def family(species):
    chain_url = get(f"pokemon-species/{species}/", "d => d.evolution_chain && d.evolution_chain.url")
    if chain_url is None:
        return None
    rows = []
    for node in get(chain_url, CHAIN_PICK):
        default = get(f"pokemon-species/{node['species']}/", "d => d.varieties.find(v => v.is_default).pokemon.name")
        for name in dict.fromkeys([default] + node["forms"]):
            p = get(f"pokemon/{name}/", STAT_PICK)
            if p is None:   # a /pokemon-form/ name without its own /pokemon/ record (e.g. flabebe-red): same stats as the default
                continue
            rows.append((node["depth"], p))
    return chain_url, rows

on_pokeapi_tab()
for sp in LINES:
    fam = family(sp)
    if fam is None:
        print(f"\n{sp}: unknown species")
        continue
    url, rows = fam
    print(f"\n{sp} family ({url})")
    print(f"  {'stage pokemon':<26}{'types':<17}" + "".join(f"{h:>5}" for h in ("hp", "atk", "def", "spa", "spd", "spe")) + f"{'total':>7}")
    for depth, p in rows:
        print(f"  {depth} {p['name']:<24}{p['types']:<17}" + "".join(f"{p['stats'][s]:>5}" for s in STATS) + f"{sum(p['stats'].values()):>7}")
```

Output (from the run on 2026-11-05):

```text

pikachu family (https://pokeapi.co/api/v2/evolution-chain/10/)
  stage pokemon             types               hp  atk  def  spa  spd  spe  total
  0 pichu                   electric            20   40   15   35   35   60    205
  1 pikachu                 electric            35   55   40   50   50   90    320
  2 raichu                  electric            60   90   55   90   80  110    485
  2 raichu-alola            electric/psychic    60   85   50   95   85  110    485

meowth family (https://pokeapi.co/api/v2/evolution-chain/22/)
  stage pokemon             types               hp  atk  def  spa  spd  spe  total
  0 meowth                  normal              40   45   35   40   40   90    290
  0 meowth-alola            dark                40   35   35   50   40   90    290
  0 meowth-galar            steel               50   65   55   40   40   40    290
  1 persian                 normal              65   70   60   65   65  115    440
  1 persian-alola           dark                65   60   60   75   65  115    440
  1 perrserker              steel               70  110  100   50   60   50    440

flabebe family (https://pokeapi.co/api/v2/evolution-chain/344/)
  stage pokemon             types               hp  atk  def  spa  spd  spe  total
  0 flabebe                 fairy               44   38   39   61   79   42    303
  1 floette                 fairy               54   45   47   75   98   52    371
  2 florges                 fairy               78   65   68  112  154   75    552
```

### 3. Same data with curl (no browser)

curl's default User-Agent gets HTTP 200. Three calls: pokemon, species, chain.

```bash
curl -sS https://pokeapi.co/api/v2/pokemon/gengar/ | python3 -c '
import json, sys
d = json.load(sys.stdin)
print(d["id"], d["name"], "/".join(t["type"]["name"] for t in d["types"]), {s["stat"]["name"]: s["base_stat"] for s in d["stats"]})
print("abilities:", [a["ability"]["name"] + (" (hidden)" if a["is_hidden"] else "") for a in d["abilities"]])
print("past abilities:", [(p["generation"]["name"], [a["ability"]["name"] if a["ability"] else None for a in p["abilities"]]) for p in d["past_abilities"]])'
sleep 1
CHAIN=$(curl -sS https://pokeapi.co/api/v2/pokemon-species/gengar/ | python3 -c 'import json, sys; print(json.load(sys.stdin)["evolution_chain"]["url"])')
echo "$CHAIN"
sleep 1
curl -sS "$CHAIN" | python3 -c '
import json, sys
def walk(n, depth=0):
    ds = n["evolution_details"]
    d = next((e for e in ds if e["is_default"]), ds[-1] if ds else None)
    how = "" if d is None else "  <- " + d["trigger"]["name"] + (" min_level=" + str(d["min_level"]) if d["min_level"] else "")
    print("  " * depth + n["species"]["name"] + how)
    for c in n["evolves_to"]:
        walk(c, depth + 1)
walk(json.load(sys.stdin)["chain"])'
```

Output (from the run on 2026-11-05):

```text
94 gengar ghost/poison {'hp': 60, 'attack': 65, 'defense': 60, 'special-attack': 130, 'special-defense': 75, 'speed': 110}
abilities: ['cursed-body']
past abilities: [('generation-vi', ['levitate'])]
https://pokeapi.co/api/v2/evolution-chain/40/
gastly
  haunter  <- level-up min_level=25
    gengar  <- trade
```

## Fields

| Field | Endpoint | Notes |
|---|---|---|
| `stats[].base_stat`, `stats[].stat.name` | pokemon | six stats: `hp`, `attack`, `defense`, `special-attack`, `special-defense`, `speed`; `effort` = EV yield |
| `types[].type.name`, `types[].slot` | pokemon | current types, slot 1 first |
| `past_types[]` | pokemon | types up to and including that generation: clefairy `generation-v` -> `normal` (fairy since gen VI) |
| `abilities[].ability.name`, `.is_hidden`, `.slot` | pokemon | hidden ability is slot 3 |
| `past_abilities[]` | pokemon | abilities up to that generation: gengar `generation-vi` -> `levitate`; charizard `generation-iv` -> slot 3 `null` (no hidden ability before gen V) |
| `past_stats[]` | pokemon | old stat values: charizard `generation-i` -> `special` 85 |
| `height`, `weight` | pokemon | **decimetres and hectograms**: charizard 17 / 905 = 1.7 m / 90.5 kg |
| `species.name`, `forms[]`, `is_default` | pokemon | `charizard-mega-x`: id 10034, `is_default` false, fire/dragon, total 634 |
| `varieties[].pokemon.name`, `.is_default` | species | `deoxys-normal` (default), `deoxys-attack`, ... |
| `evolution_chain.url` | species | chain ids are not species ids: charmander -> chain 2, eevee -> 67, pikachu -> 10 |
| `genera[]`, `flavor_text_entries[]`, `names[]` | species | all languages; filter `language.name == "en"` |
| `is_legendary`, `is_mythical`, `is_baby`, `generation.name` | species | deoxys mythical; mime-jr, toxel baby |
| `chain.species`, `chain.evolves_to[]`, `chain.is_baby` | evolution-chain | tree; eevee has 8 children |
| `evolution_details[]` | evolution-chain | `trigger`, `version_group`, `is_default`, `min_level`, `item`, `min_happiness`, `time_of_day` (`""` when unused), `known_move`, `known_move_type`, `location`, `region`, `required_pokemon_form`, `evolved_pokemon_form`, `allowed_natures[]`, `condition_expression` (wurmple: `percentage_chance` 50), ... |
| `effect_entries[].short_effect`, `.effect` | ability | per language; block 1 falls back to the newest English `flavor_text_entries` |
| `pokemon[]` | ability, type | every Pokemon with that ability or type (blaze: 32) |
| `damage_relations` | type | `double_damage_from`, `half_damage_from`, `no_damage_from` and the `_to` lists; `past_damage_relations[]` for older charts |
| `count`, `next`, `previous`, `results[]` | any list | default page 20; `?limit=100000` returns the full list in one call |

## Gotchas

- **Two lists, two name spaces.** `pokemon-species` (1,025, last `pecharunt`) and `pokemon` (1,351, last `meowstic-female-mega`, id 10326). `pokemon-form` names are a third set: `flabebe-red` is a form of pokemon `flabebe`, and `pokemon/flabebe-red/` is 404.
- **Several `evolution_details` entries can all be `is_default: true`.** Pikachu -> raichu has one for `red-blue` and one for `sun-moon` with `evolved_pokemon_form: raichu-alola`; toxel -> toxtricity has two (amped, low-key) that differ only in `allowed_natures` (13 and 12 natures). Group by form before picking one.
- **Some entries have no `is_default` at all** for older games (leafeon: 6 entries, only `sword-shield` is default; earlier games evolve by `near_special_rock` at a location such as `eterna-forest`).
- **`required_pokemon_form` repeats the species for ordinary steps** (`eevee` -> vaporeon). Block 1 prints it only when it names another form (`from mr-mime-galar` -> mr-rime).
- **Matchups ignore abilities.** The multiplier table is pure type chart; levitate, filter and the like are not applied. `/type/` lists 21 types; `stellar` has empty `damage_relations`, and the blocks use the 18 battle types.
- **Case does not matter in paths** (`pokemon/Charizard` = `pokemon/charizard`), and the trailing slash is optional.
- **404 is JSON** (`{"status":404,"message":"Not Found"}`, `cache-control: max-age=432000`); **403 is a Cloudflare HTML page**, which means the URL broke a firewall rule, not that the Pokemon is missing.
- **Text keeps game line breaks.** `flavor_text` contains `\n` (charizard's shield entry); collapse whitespace.
- **Tab marker.** The harness prefixes the tab title with a horse emoji; the blocks never read the title.

## What does not work

- **Display names, URL-encoded names, `?name=` filters:** HTTP 403 (firewall rule, see Quick summary). Use list names (`mr-mime`, `farfetchd`, `flabebe`, `nidoran-f`).
- **`pokemon/<species>` for species whose default form has a suffix:** `pokemon/deoxys/` is 404; read `varieties` on the species first.
- **Python `urllib` with its default User-Agent** (`Python-urllib/3.12`): HTTP 403 from Cloudflare, while curl's default User-Agent got 200. Not worked around here; block 3 uses curl.
- **No search endpoint.** Only `limit` and `offset` are accepted; filter the full name list yourself.
- **Not tested:** the GraphQL beta (`beta.pokeapi.co/graphql/v1beta`), moves, items, locations, encounters, sprites and cries (`cries` URLs point to raw.githubusercontent.com, not pokeapi.co).
