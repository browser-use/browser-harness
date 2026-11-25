# Camara dos Deputados - Find the Newest Brazilian Bills (PL) on a Topic Such as "inteligencia artificial", With Number, Year, Ementa, Date Presented and Latest Procedural Step, Then How Each Party Voted in the Most Recent Roll-Call Vote (Dados Abertos REST API JSON, no key)

Field-tested against the Dados Abertos da Camara dos Deputados API v2 (dadosabertos.camara.leg.br) on 2026-11-24 (US Pacific afternoon; 23:31-23:45 UTC, which was 20:31-20:45 the same evening in Brasilia) using a fresh Browser Use cloud browser `ka-camara-deput-1124` (logged out; one session, 23:33:18-23:44:26 UTC, confirmed `stopped` through the Browser Use API) plus Python `urllib` and `curl` from a Linux machine. 19 browser page loads (1 smoke test that opened the API docs page, which block 1's three runs reused; 6 in each of block 2's three runs) and 89 in-page `fetch()` calls (block 1: 15, 16 and 16; block 2: 14 per run), 53 curl calls (33 while exploring the API and its OpenAPI document, 10 in each of block 4's two runs) and 77 urllib calls (block 3 ran 8 times: 17, 10, 9 and 2 calls before a paging fix, then 18 with an empty cache, 10 warm, 9 for `deepfake` and 2 for a keyword with no match), all serial and at least 1 s apart. Every call was HTTP 200 except the deliberate probes below: HTTP 400 (`ordenarPor=dataApresentacao` and unknown parameters such as `foo=1` and `x=1`) and HTTP 404 (unknown ids). curl timed 22 answers at 0.59-2.34 s (2.34 s for the newest 100 votes of all bodies). No 429, no challenge, no key, no login, no cookie. Every answer inspected (the 21 saved exploration headers, all 13 block 2 probes, block 4's search) carried `retry-after: 30`, 200s included (see Gotchas). Before the change at the end of this paragraph, block 1's last run was its third (23:36 UTC; the first run used the `idOrgao=180` filter and picked a stale vote, which is how the filter lag in Gotchas was found; the second added the `siglaOrgao` filter, the third the federation orientations), block 2's output below is the verifier's re-run described next (the author's last was its third, 23:39; the first searched the FAQ with `innerText` and missed the collapsed answers, the second quoted a sentence with a dash in it); block 3's last runs were its fifth (empty cache) and sixth (warm), and block 4's its second (the first had a quoting error in one Python one-liner). An independent verifier re-ran all 4 blocks verbatim at 23:48-23:52 UTC (fresh cloud browser `kv-camara-deput-1124`, confirmed `stopped`) with the same output apart from times and the gzip size of one answer, then fixed the terms section and re-ran block 2 at 23:57 UTC in a second session of the same name (also confirmed `stopped`). On 2026-11-25, block 1 was changed to read every page of the search and sort by date presented, blocks 1 and 3 to follow the vote list's pages until a roll-call is found, and block 4 to keep the votes in a `mktemp` file removed on exit; they re-ran on 2026-11-25 at 01:00-01:03 UTC (block 1 in a new cloud browser, stopped and confirmed `stopped`), and the outputs shown for blocks 1, 3 and 4 come from those runs.

robots.txt (checked 2026-11-24, curl, the cloud browser and block 3): https://dadosabertos.camara.leg.br/robots.txt answers HTTP 200 `text/html` with the portal's own HTML page (title "Dados Abertos da Câmara dos Deputados", no `User-agent` or `Disallow` line). That is not a robots file, so it sets no rules, and every agent, including GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Claude-Web, Google-Extended, PerplexityBot, CCBot and Bytespider, may fetch every path this skill uses (`/api/v2/proposicoes`, `/proposicoes/{id}`, `/proposicoes/{id}/tramitacoes`, `/votacoes`, `/votacoes/{id}`, `/votacoes/{id}/votos`, `/votacoes/{id}/orientacoes`, `/deputados`, `/api/v2/api-docs` and the docs pages; block 3 checks 13 agents on its 6 API paths before any call and stops if the host ever publishes rules that disallow one). Apart from block 2, which reads www.camara.leg.br/robots.txt and the terms page on www2.camara.leg.br (whose robots.txt has only a `*` group and does not disallow that page), the skill does not fetch www.camara.leg.br. Its robots.txt (read by block 2) has a group for GPTBot, ChatGPT-User, Google-Extended, anthropic-ai, Claude-Web, CCBot and PerplexityBot (plus Omgilibot, Omgili and FacebookBot) under the comment "BLOQUEIO DE BOTS DE INTELIGÊNCIA ARTIFICIAL (LLMs)" / "Evita que o conteúdo do site seja usado para treinar IAs.", but that group disallows the same paths as its `*` group: admin, login and comment pages, list pages and pages with certain query strings, the bill tree pages, `/deputados/*/*` and files such as `/*.pdf`; the `urlInteiroTeor` links the API returns point there and are printed, not fetched. Terms: the "Termos de uso" link in the www.camara.leg.br footer goes to https://www2.camara.leg.br/termo-de-uso-e-politica-de-privacidade (https://www.camara.leg.br/termos-de-uso is HTTP 404). It applies "ao acessar o portal da Câmara dos Deputados (www.camara.leg.br)" and says (clause 29): "Todas as informações publicadas no Portal da Câmara são de domínio público, gratuitas e podem ser reproduzidas desde que citada a fonte "Câmara dos Deputados" e a autoria da informação, quando houver." So name the source: every block's output ends with a "Source: Dados Abertos da Camara dos Deputados ..." line. Its one bot clause (22), "Podemos coibir a participação de sistemas automatizados ou robôs (scripts, bots, entre outros) que tentem imitar pessoas.", reserves the right to curb bots that pose as people in the portal's participation features; it bans neither automated reading nor this skill's API calls, and this skill posts nothing. Its one AI clause (37) is about the Camara's own use of AI to produce content. No non-commercial-only wording. The official FAQ, https://dadosabertos.camara.leg.br/faq/faq-home.html: "É totalmente de graça" ... "os dados são públicos! E não, não é preciso se cadastrar, nem se identificar para baixar qualquer dos conjuntos de dados." and, to "Posso cobrar por um aplicativo ou serviço que use os dados da Câmara?": "Sim, pode. Não há qualquer restrição quanto ao isso." (paid apps allowed, no restriction). It describes the data as formatted for "processamento por softwares de diversos tipos", and https://dadosabertos.camara.leg.br/howtouse/sobre-dados-abertos.html says "Serviços de dados abertos são feitos para máquinas e programas (softwares)" and lists "Livres de licenças" among the open-data criteria it follows. No AI/ML, scraping, crawling, robot or non-commercial-only wording on either page (block 2 scans both; its one hit is that "Livres de licenças" line; on the terms page its hits are clauses 22 and 37 above). The OpenAPI document: "Por padrão, todos os serviços de listagens retornam 15 itens, e o limite por requisição é de 100 itens." and "Esta versão é ainda incompleta, sujeita a mudanças". The FAQ also says personal and family information of deputies and staff is restricted ("Existem restrições às informações que podem ser divulgadas, especialmente as de caráter pessoal e/ou familiar."), which is one more reason the blocks print only a deputy's name, party, state and vote. Naming: this skill writes "Camara dos Deputados" and "Dados Abertos da Camara dos Deputados" in plain text and shows no coat of arms or logo; it is not affiliated with or endorsed by the Camara dos Deputados. Every block's output names the source and says what was computed.

## Quick summary

- **No scraping needed.** `GET https://dadosabertos.camara.leg.br/api/v2/proposicoes?keywords=inteligencia%20artificial&siglaTipo=PL&itens=100&ordem=DESC&ordenarPor=id` with `Accept: application/json` -> the matching PL bills, highest id first (`id`, `numero`, `ano`, `ementa`, `dataApresentacao`); `ordenarPor=dataApresentacao` is HTTP 400, so read every page and sort by `dataApresentacao` yourself (blocks 1 and 3). `GET /proposicoes/{id}` -> `statusProposicao` = the latest procedural step (`dataHora`, `siglaOrgao`, `descricaoTramitacao`, `descricaoSituacao`, `despacho`); `/proposicoes/{id}/tramitacoes` = every step in one answer (no paging: its only parameters are `dataInicio` and `dataFim`, and `itens=5` is HTTP 400). `GET /votacoes?ordem=DESC&ordenarPor=dataHoraRegistro&itens=100` -> the newest votes of every body; `/votacoes/{id}/votos` -> one row per deputy who voted (empty for symbolic votes); `/votacoes/{id}/orientacoes` -> each leadership's recommended vote. JSON, gzip, no key, 100 rows per page at most, paging in `links` (`rel="next"`, `"last"`) and the `Link` / `X-Total-Count` headers.
- **Answers (block 1, 24 November 2026 23:36 UTC = 20:36 in Brasilia):** 105 PL bills matched "inteligencia artificial" in the default 30-day window. Newest by date presented (the same five as the highest ids; block 1 re-ran at 2026-11-25 01:03 UTC with the same bills): **PL 5928/2026** (presented 2026-11-23 15:26 Brasilia; protection of workers against automated decisions and AI surveillance at work; amends the CLT and the LGPD), **PL 5864/2026** (2026-11-16; voice and image replicas generated by AI), **PL 5826/2026** (2026-11-11; AI in food advertising and delivery platforms), **PL 5813/2026** (2026-11-10; precision medicine in paediatric oncology, matched through the indexing keywords only) and **PL 5729/2026** (2026-11-03; "Lei Anticrime Deepfake"). All five were still at their first step, "Apresentação de Proposição" at the MESA (four "Aguardando Autorização do Despacho" or "Aguardando Chancela e Publicação do Despacho").
- **Most recent roll-call vote:** plenary vote **2332174-59** at 2026-11-24 17:52:28 Brasilia, "Aprovado o Substitutivo ao Projeto de Lei nº 1.969, de 2022 ... Sim: 292; Não: 147; Abstenção: 2; Total: 441." (PL 1969/2022, the Acari case). 442 vote rows; **PL 80 Não / 5 Sim, NOVO 5 Não, MDB 17 Não / 11 Sim; PT 63 Sim, UNIÃO 27-15, PSD 33-5, PP 27-9, REPUBLICANOS 29-6** and every other party a Sim majority except CIDADANIA and MISSÃO (1 Não each). The newer plenary vote 2332174-62 (the final wording, 17:53:39) was symbolic (0 rows) and was skipped.
- **Rate limits: none published, no rate-limit headers.** `retry-after: 30` comes on every answer, so it cannot signal throttling; honour it only on a 429 or 5xx. Lists carry `Cache-Control: public, max-age=360` (proposicoes) or `1800` (deputados); details and votes carry none, and there is no `ETag`. Serial, 1 s apart; the whole task is 12-18 calls.

## What works

### 1. Topic -> newest PL bills with their latest step; most recent plenary roll-call -> vote by party (browser)

`on_api_tab()` opens the logged-out API docs page on dadosabertos.camara.leg.br and `fetch()` calls the API on the same host with `Accept: application/json`. `get()` returns parsed JSON on HTTP 200, waits once on 429/5xx or a network error and otherwise raises. 17 `fetch()` calls in the run shown: every page of the search (2 of 100; `MAX_PAGES` caps it), 2 per bill (detail and step history), the vote list (following `rel="next"` pages while no roll-call is found), the votes of each plenary vote until one has at least `MIN_ROWS` rows, the chosen vote's detail and its orientations.

```python
import email.utils, json, re, textwrap, time, unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

KEYWORDS = "inteligencia artificial"   # matched against the ementa and the indexing keywords; accents optional
N_BILLS = 5                            # newest PL bills to show
ORGAO = "PLEN"                         # siglaOrgao of the floor (Plenario); None = every body, committees included
MIN_ROWS = 20                          # this skill's cut-off: fewer vote rows = symbolic vote with a few registered positions
MAX_SCAN = 15                          # votes to check, newest first, before giving up
MAX_PAGES = 5                          # pages of 100 to read from the bill search and from the vote list
PAGE = "https://dadosabertos.camara.leg.br/swagger/api.html"
API = "https://dadosabertos.camara.leg.br/api/v2"
BRT = timezone(timedelta(hours=-3))    # API times are Brasilia local without an offset; no daylight saving since 2019
PAUSE = 1.0                            # serial, 1 s apart

def on_api_tab():
    """fetch() from the logged-out API docs page on the same host, so no CORS question arises."""
    try:
        if js("location.href").startswith(PAGE) and "proposicoes" in js("document.body.innerText"):
            return
    except Exception:
        pass
    new_tab(PAGE)
    wait_for_load()
    for _ in range(30):
        if "/proposicoes" in (js("document.body ? document.body.innerText : ''") or ""):
            return
        time.sleep(0.5)
    raise RuntimeError(f"Dados Abertos API page did not load (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for the answer
START_JS = """(() => { window.__p = window.__p || {}; const id = String(Math.random()).slice(2); window.__p[id] = null;
  fetch(%s, {credentials: 'omit', headers: {'Accept': 'application/json'}})
    .then(async r => { window.__p[id] = {status: r.status, type: r.headers.get('content-type') || '',
                                         retry: r.headers.get('retry-after'), total: r.headers.get('x-total-count'),
                                         link: r.headers.get('link') || '', text: await r.text()}; })
    .catch(e => { window.__p[id] = {status: 0, type: '', retry: null, total: null, link: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__p[%s]; if (v) delete window.__p[%s]; return v; })()"""

def retry_wait(value, default):
    v = (value or "").strip()
    if v.isdigit():
        return int(v)
    try:
        return max(0, int((email.utils.parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()) + 1)
    except (TypeError, ValueError):
        return default

def get(url):
    """-> (parsed JSON, response dict) on HTTP 200. Every answer carries 'retry-after: 30', even 200s, so it is only
    read on 429/5xx or a network error: then wait once (over 120 s stops). Raises on anything else."""
    for attempt in range(2):
        rid = json.dumps(js(START_JS % json.dumps(url)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > 90:
                raise RuntimeError(f"{url}: no answer after 90s")
            time.sleep(0.2)
        time.sleep(PAUSE)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            wait = retry_wait(r["retry"], 30)
            if wait > 120:
                raise RuntimeError(f"{url}: server asks to wait {wait} s: stopping")
            time.sleep(wait)
            continue
        break
    if r["status"] != 200 or "json" not in r["type"]:
        raise RuntimeError(f"{url}: HTTP {r['status']} {r['type']} {' '.join(r['text'].split())[:160]!r}; stopping")
    return json.loads(r["text"]), r

brt = lambda s: datetime.fromisoformat(s).replace(tzinfo=BRT)          # "2026-11-24T17:52:28" -> aware
when = lambda s: f"{s.replace('T', ' ')} Brasilia ({brt(s).astimezone(timezone.utc):%H:%M} UTC)"
fold = lambda s: re.sub(r"[\u0300-\u036f]", "", unicodedata.normalize("NFD", s or "")).lower()
wrap = lambda s, ind: textwrap.fill(" ".join((s or "-").split()), 110, initial_indent=ind, subsequent_indent=ind)

on_api_tab()
now = datetime.now(timezone.utc)
print(f"Dados Abertos da Camara dos Deputados API v2, checked {now:%Y-%m-%d %H:%M} UTC ({now.astimezone(BRT):%H:%M} Brasilia)")

# every PL matching the keywords (default window: presented or moved in the last 30 days), 100 per page.
# ordenarPor=dataApresentacao is HTTP 400, so read the pages and sort by date presented here
url, found, pages, total = f"{API}/proposicoes?keywords={quote(KEYWORDS)}&siglaTipo=PL&itens=100&ordem=DESC&ordenarPor=id", [], 0, None
while url and pages < MAX_PAGES:
    d, r = get(url)
    found += d["dados"]
    pages, total = pages + 1, total or r["total"]
    url = next((l["href"] for l in d.get("links", []) if l["rel"] == "next"), None)
if not found:
    raise RuntimeError(f"no PL matches {KEYWORDS!r} in the default 30-day window; add dataApresentacaoInicio=...: stop")
bills = sorted(found, key=lambda b: (b["dataApresentacao"], b["id"]), reverse=True)[:N_BILLS]
print(f"\nPL bills matching {KEYWORDS!r}: X-Total-Count {total} (presented or moved in the last 30 days), "
      f"read {len(found)} in {pages} page(s) of 100; newest {len(bills)} by date presented:")
if url:
    print(f"  PARTIAL: stopped at MAX_PAGES = {MAX_PAGES}; the newest by date may be on a later page ({url})")

# 2 calls per bill: the bill (statusProposicao = latest step) and its full step history
for b in bills:
    d, _ = get(f"{API}/proposicoes/{b['id']}")
    steps, _ = get(f"{API}/proposicoes/{b['id']}/tramitacoes")
    d, st = d["dados"], d["dados"]["statusProposicao"]
    newest = max(steps["dados"], key=lambda t: (t["dataHora"], t["sequencia"]), default=None)
    agree = "matches" if newest and newest["sequencia"] == st["sequencia"] else "DIFFERS from"
    words = [w for w in fold(KEYWORDS).split() if w]
    where = "ementa" if all(w in fold(d["ementa"]) for w in words) else "indexing keywords only (not in the ementa)"
    print(f"\n  PL {d['numero']}/{d['ano']}  (id {d['id']}; presented {when(d['dataApresentacao'])}; match: {where})")
    print(wrap(d["ementa"], "    ementa: "))
    print(f"    latest step #{st['sequencia']} {when(st['dataHora'])} at {st['siglaOrgao']}: {st['descricaoTramitacao']}"
          + (f" / situacao: {st['descricaoSituacao']}" if st["descricaoSituacao"] else "")
          + f"; regime {st['regime']!r}, apreciacao {st['apreciacao']}")
    print(wrap(st["despacho"][:300] + ("..." if len(st["despacho"]) > 300 else ""), "      despacho: "))
    print(f"    {len(steps['dados'])} tramitacao step(s); newest {agree} statusProposicao; text: {d['urlInteiroTeor'] or '-'}")

# votes, newest first, 100 per page; the first with >= MIN_ROWS individual votes is the most recent roll-call (nominal)
# vote. Pages are followed (links rel="next") until one is found, MAX_SCAN votes were checked or MAX_PAGES were read.
# Filter by siglaOrgao here: the idOrgao=180 parameter lagged a day behind (see Gotchas)
url, vpages, pick, skipped = f"{API}/votacoes?ordem=DESC&ordenarPor=dataHoraRegistro&itens=100", 0, None, []
while url and pick is None and len(skipped) < MAX_SCAN and vpages < MAX_PAGES:
    votes, _ = get(url)
    vpages += 1
    for v in votes["dados"]:
        if ORGAO and v["siglaOrgao"] != ORGAO:
            continue
        if len(skipped) >= MAX_SCAN:
            break
        rows, _ = get(f"{API}/votacoes/{v['id']}/votos")
        if len(rows["dados"]) >= MIN_ROWS:
            pick, rows = v, rows["dados"]
            break
        skipped.append(f"{v['id']} ({len(rows['dados'])} rows)")
    url = next((l["href"] for l in votes.get("links", []) if l["rel"] == "next"), None)
if not pick:
    raise RuntimeError(f"no roll-call vote among the newest {len(skipped)} {ORGAO or ''} votes in {vpages} page(s) of 100 "
                       f"({'MAX_SCAN or MAX_PAGES reached' if url else 'no more pages'}): stop")
detail, _ = get(f"{API}/votacoes/{pick['id']}")
orient, _ = get(f"{API}/votacoes/{pick['id']}/orientacoes")
detail = detail["dados"]
print(f"\nMost recent roll-call vote{' in ' + pick['siglaOrgao'] if ORGAO else ''}: {pick['id']} at {when(pick['dataHoraRegistro'])}")
print(f"  skipped {len(skipped)} newer symbolic vote(s): {', '.join(skipped) or 'none'}")
print(wrap(pick["descricao"], "  "))
for p in detail.get("proposicoesAfetadas", []):
    print(f"  bill: {p['siglaTipo']} {p['numero']}/{p['ano']} (id {p['id']}): {p['ementa'][:150]}")

kinds = ["Sim", "Não", "Abstenção", "Obstrução", "Artigo 17"]
by_party = defaultdict(Counter)
for x in rows:
    by_party[x["deputado_"]["siglaPartido"] or "(none)"][x["tipoVoto"]] += 1
total = Counter(x["tipoVoto"] for x in rows)
others = sorted(set(total) - set(kinds))
ori = {o["siglaPartidoBloco"]: o["orientacaoVoto"] or "(blank)" for o in orient["dados"]}
for fed, said in list(ori.items()):   # "Fdr PT-PCdoB-PV": the federation's line also applies to its parties
    if fed.startswith("Fdr "):
        for member in fed[4:].split("-"):
            ori.setdefault(member, f"{said} (via {fed})")
print(f"\n  {len(rows)} individual votes (absent deputies are not listed); by party, largest first:")
print(f"  {'party':<14}{'votes':>6}{'Sim':>5}{'Não':>5}{'Abst':>5}{'Obstr':>6}{'Art17':>6}{'other':>6}  {'majority':<10} leader said")
for party, c in sorted(by_party.items(), key=lambda kv: (-sum(kv[1].values()), kv[0])):
    top = c.most_common()
    lead = top[0][0] if len(top) == 1 or top[0][1] > top[1][1] else "tie"
    print(f"  {party:<14}{sum(c.values()):>6}{c['Sim']:>5}{c['Não']:>5}{c['Abstenção']:>5}{c['Obstrução']:>6}{c['Artigo 17']:>6}"
          f"{sum(c[k] for k in others):>6}  {lead:<10} {ori.get(party, '(none listed)')}")
print(f"  {'all':<14}{len(rows):>6}{total['Sim']:>5}{total['Não']:>5}{total['Abstenção']:>5}{total['Obstrução']:>6}"
      f"{total['Artigo 17']:>6}{sum(total[k] for k in others):>6}" + (f"  other = {others}" if others else ""))
m = re.search(r"Sim:\s*(\d+);\s*Não:\s*(\d+)", pick["descricao"])
if m:
    ok = (int(m[1]), int(m[2])) == (total["Sim"], total["Não"])
    print(f"  check vs descricao: Sim {m[1]}, Não {m[2]} -> {'match' if ok else 'MISMATCH, trust the descricao and re-fetch later'}")
blocs = {k: v for k, v in ori.items() if k not in by_party and "(via " not in v}
if blocs:
    print("  orientations by blocs, federations and leaderships:", "; ".join(f"{k} {v}" for k, v in blocs.items()))
print(f"\nSource: Dados Abertos da Camara dos Deputados (API v2), accessed {now:%d %B %Y %H:%M} UTC. "
      "Tallies and majorities computed here; deputies' names, e-mails and photos not printed.")
```

Output (re-run on 2026-11-25, 01:03 UTC = 22:03 Brasilia, in a new cloud browser; it now reads both search pages and sorts by date presented, which gave the same five bills as the newest by id in the 23:35 and 23:36 UTC runs on 2026-11-24, and the same vote):

```text
Dados Abertos da Camara dos Deputados API v2, checked 2026-11-25 01:03 UTC (22:03 Brasilia)

PL bills matching 'inteligencia artificial': X-Total-Count 105 (presented or moved in the last 30 days), read 105 in 2 page(s) of 100; newest 5 by date presented:

  PL 5928/2026  (id 2658843; presented 2026-11-23 15:26 Brasilia (18:26 UTC); match: ementa)
    ementa: Institui normas de proteção do trabalhador frente a decisões automatizadas e à vigilância por
    ementa: sistemas de inteligência artificial nas relações de trabalho, disciplina a dispensa coletiva
    ementa: motivada por automação e altera a Consolidação das Leis do Trabalho, aprovada pelo Decreto-Lei nº
    ementa: 5.452, de 1º de maio de 1943, e a Lei nº 13.709, de 14 de agosto de 2018 (Lei Geral de Proteção de
    ementa: Dados Pessoais).
    latest step #1 2026-11-23 15:26 Brasilia (18:26 UTC) at MESA: Apresentação de Proposição; regime '.', apreciacao Indefinida
      despacho: Apresentação do PL n. 5928/2026 (Projeto de Lei), pelo Deputado Rubens Pereira Júnior (PT/MA
      despacho: -Fdr PT-PCdoB-PV), que "Institui normas de proteção do trabalhador frente a decisões
      despacho: automatizadas e à vigilância por sistemas de inteligência artificial nas relações de trabalho,
      despacho: disciplina a dispensa colet...
    1 tramitacao step(s); newest matches statusProposicao; text: https://www.camara.leg.br/proposicoesWeb/prop_mostrarintegra?codteor=3203100

  PL 5864/2026  (id 2654170; presented 2026-11-16 14:30 Brasilia (17:30 UTC); match: ementa)
    ementa: Veda a criação e o uso comercial de réplicas de voz ou de imagem de pessoa natural geradas por
    ementa: inteligência artificial sem autorização expressa do titular e dispõe sobre os deveres dos
    ementa: provedores de aplicações de internet que disponibilizam modelos de geração de voz ou de imagem.
    latest step #1 2026-11-16 14:30 Brasilia (17:30 UTC) at MESA: Apresentação de Proposição / situacao: Aguardando Autorização do Despacho; regime '.', apreciacao Indefinida
      despacho: Apresentação do PL n. 5864/2026 (Projeto de Lei), pelo Deputado Rubens Pereira Júnior (PT/MA
      despacho: -Fdr PT-PCdoB-PV), que "Veda a criação e o uso comercial de réplicas de voz ou de imagem de
      despacho: pessoa natural geradas por inteligência artificial sem autorização expressa do titular e
      despacho: dispõe sobre os deveres do...
    1 tramitacao step(s); newest matches statusProposicao; text: https://www.camara.leg.br/proposicoesWeb/prop_mostrarintegra?codteor=3196499

  PL 5826/2026  (id 2652995; presented 2026-11-11 18:06 Brasilia (21:06 UTC); match: ementa)
    ementa: Altera a Lei nº 8.078, de 11 de setembro de 1990, para vedar a utilização de sistemas de
    ementa: inteligência artificial na publicidade, oferta, apresentação e divulgação comercial de produtos
    ementa: alimentícios em estabelecimentos comerciais e plataformas de delivery.
    latest step #1 2026-11-11 18:06 Brasilia (21:06 UTC) at MESA: Apresentação de Proposição / situacao: Aguardando Autorização do Despacho; regime '.', apreciacao Indefinida
      despacho: Apresentação do PL n. 5826/2026 (Projeto de Lei), pela Deputada Erika Hilton (PSOL/SP -Fdr
      despacho: PSOL-REDE), que "Altera a Lei nº 8.078, de 11 de setembro de 1990, para vedar a utilização de
      despacho: sistemas de inteligência artificial na publicidade, oferta, apresentação e divulgação
      despacho: comercial de produtos aliment...
    1 tramitacao step(s); newest matches statusProposicao; text: https://www.camara.leg.br/proposicoesWeb/prop_mostrarintegra?codteor=3194080

  PL 5813/2026  (id 2652517; presented 2026-11-10 18:28 Brasilia (21:28 UTC); match: indexing keywords only (not in the ementa))
    ementa: Altera a Lei nº 14.308, de 8 de março de 2022, para estabelecer diretrizes de medicina de
    ementa: precisão, diagnóstico molecular e genômico, avaliação multidisciplinar especializada, utilização
    ementa: responsável de tecnologias avançadas e monitoramento de resultados na atenção à oncologia
    ementa: pediátrica.
    latest step #1 2026-11-10 18:28 Brasilia (21:28 UTC) at MESA: Apresentação de Proposição / situacao: Aguardando Autorização do Despacho; regime '.', apreciacao Indefinida
      despacho: Apresentação do PL n. 5813/2026 (Projeto de Lei), pelo Deputado Bibo Nunes (PL/RS), que
      despacho: "Altera a Lei nº 14.308, de 8 de março de 2022, para estabelecer diretrizes de medicina de
      despacho: precisão, diagnóstico molecular e genômico, avaliação multidisciplinar especializada,
      despacho: utilização responsável de tecnologi...
    1 tramitacao step(s); newest matches statusProposicao; text: https://www.camara.leg.br/proposicoesWeb/prop_mostrarintegra?codteor=3193165

  PL 5729/2026  (id 2649761; presented 2026-11-03 13:46 Brasilia (16:46 UTC); match: ementa)
    ementa: Institui a Lei Anticrime Deepfake, estabelece medidas penais, processuais e de investigação
    ementa: destinadas à repressão de fraudes, extorsões e organizações criminosas que utilizem inteligência
    ementa: artificial, deepfakes, clonagem de voz ou manipulação artificial de identidade, dispõe sobre
    ementa: mecanismos de preservação e rastreabilidade de evidências digitais, cria protocolo nacional de
    ementa: resposta emergencial a fraudes tecnológicas e estabelece medidas de bloqueio, recuperação e perda
    ementa: de ativos relacionados a esses crimes.
    latest step #1 2026-11-03 13:46 Brasilia (16:46 UTC) at MESA: Apresentação de Proposição / situacao: Aguardando Chancela e Publicação do Despacho; regime '.', apreciacao Indefinida
      despacho: Apresentação do PL n. 5729/2026 (Projeto de Lei), pelo Deputado José Medeiros (PL/MT), que
      despacho: "Institui a Lei Anticrime Deepfake, estabelece medidas penais, processuais e de investigação
      despacho: destinadas à repressão de fraudes, extorsões e organizações criminosas que utilizem
      despacho: inteligência artificial, deepfak...
    1 tramitacao step(s); newest matches statusProposicao; text: https://www.camara.leg.br/proposicoesWeb/prop_mostrarintegra?codteor=3188112

Most recent roll-call vote in PLEN: 2332174-59 at 2026-11-24 17:52:28 Brasilia (20:52 UTC)
  skipped 1 newer symbolic vote(s): 2332174-62 (0 rows)
  Aprovado o Substitutivo ao Projeto de Lei nº 1.969, de 2022, da Comissão de Direitos Humanos, Minorias e
  Igualdade Racial. Sim: 292; Não: 147; Abstenção: 2; Total: 441.
  bill: PL 1969/2022 (id 2332174): Reconhece a responsabilidade do Estado pelo desaparecimento forçado das 11 vítimas de Acari e estabelece Medidas de Reparação e Não-Repetição para vít

  442 individual votes (absent deputies are not listed); by party, largest first:
  party          votes  Sim  Não Abst Obstr Art17 other  majority   leader said
  PL                85    5   80    0     0     0     0  Não        Não
  PT                64   63    0    0     0     1     0  Sim        Sim (via Fdr PT-PCdoB-PV)
  UNIÃO             42   27   15    0     0     0     0  Sim        (none listed)
  PSD               39   33    5    1     0     0     0  Sim        (none listed)
  PP                36   27    9    0     0     0     0  Sim        (none listed)
  REPUBLICANOS      35   29    6    0     0     0     0  Sim        (none listed)
  MDB               29   11   17    1     0     0     0  Não        (none listed)
  PODE              24   20    4    0     0     0     0  Sim        (none listed)
  PSB               16   15    1    0     0     0     0  Sim        Sim
  PSDB              15   14    1    0     0     0     0  Sim        (none listed)
  PSOL              13   13    0    0     0     0     0  Sim        Sim (via Fdr PSOL-REDE)
  PCdoB             10   10    0    0     0     0     0  Sim        Sim (via Fdr PT-PCdoB-PV)
  PDT                7    7    0    0     0     0     0  Sim        Sim
  PV                 6    6    0    0     0     0     0  Sim        Sim (via Fdr PT-PCdoB-PV)
  NOVO               5    0    5    0     0     0     0  Não        Não
  AVANTE             4    4    0    0     0     0     0  Sim        (blank)
  SOLIDARIEDADE      4    3    1    0     0     0     0  Sim        (blank)
  PRD                3    2    1    0     0     0     0  Sim        (blank)
  REDE               3    3    0    0     0     0     0  Sim        Sim (via Fdr PSOL-REDE)
  CIDADANIA          1    0    1    0     0     0     0  Não        (none listed)
  MISSÃO             1    0    1    0     0     0     0  Não        (blank)
  all              442  292  147    2     0     1     0
  check vs descricao: Sim 292, Não 147 -> match
  orientations by blocs, federations and leaderships: Oposição Não; Minoria Não; Bl UniPpPsd... Liberado; Fdr PT-PCdoB-PV Sim; Fdr PSOL-REDE Sim; Governo Sim; Maioria Liberado

Source: Dados Abertos da Camara dos Deputados (API v2), accessed 25 November 2026 01:03 UTC. Tallies and majorities computed here; deputies' names, e-mails and photos not printed.
```

### 2. robots.txt, the FAQ and docs quotes, and what the API does with mistakes (browser)

6 page loads (2 robots.txt files, the FAQ, the "sobre" page, the portal's terms page, back to the API docs) and 14 in-page `fetch()` calls (the OpenAPI document and 13 probes) in the same tab.

```python
import json, re, time

API = "https://dadosabertos.camara.leg.br/api/v2"
SITE = "https://dadosabertos.camara.leg.br"

START_JS = """(() => { window.__p = window.__p || {}; const id = String(Math.random()).slice(2); window.__p[id] = null;
  const h = %s; fetch(%s, {credentials: 'omit', headers: h})
    .then(async r => { window.__p[id] = {status: r.status, type: r.headers.get('content-type') || '',
                                         retry: r.headers.get('retry-after'), total: r.headers.get('x-total-count'),
                                         text: await r.text()}; })
    .catch(e => { window.__p[id] = {status: 0, type: '', retry: null, total: null, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__p[%s]; if (v) delete window.__p[%s]; return v; })()"""

def raw(url, accept="application/json"):
    """One in-page GET, no retries: inspection only. accept=None sends the browser's default fetch() Accept (*/*)."""
    rid = json.dumps(js(START_JS % (json.dumps({"Accept": accept} if accept else {}), json.dumps(url))))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 90:
            raise RuntimeError(f"{url}: no answer after 90s")
        time.sleep(0.2)
    time.sleep(1)
    return r

def page(url, wait_for=None):
    """Load a page, wait for a phrase, return (HTTP status, final URL, whitespace-collapsed text). textContent, not
    innerText: the FAQ answers sit in collapsed panels that innerText leaves out."""
    goto_url(url)
    wait_for_load()
    for _ in range(30):
        txt = js("(document.body || document.documentElement).textContent || ''") or ""
        if not wait_for or wait_for in " ".join(txt.split()):
            break
        time.sleep(0.5)
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    return st, js("location.href"), " ".join(txt.split())

# robots.txt: the API host answers with its portal page (no rules); www.camara.leg.br is not used by this skill
st, final, txt = page(f"{SITE}/robots.txt")
print(f"robots.txt dadosabertos.camara.leg.br HTTP {st}: user-agent lines {len(re.findall(r'(?i)user-agent:', txt))}; "
      f"disallow lines {len(re.findall(r'(?i)disallow:', txt))}; {txt[:70]!r}")
st, final, txt = page("https://www.camara.leg.br/robots.txt", "User-agent")
groups = re.findall(r"(?im)^user-agent:\s*(\S+)", js("document.body.innerText"))
print(f"robots.txt www.camara.leg.br (not used) HTTP {st}: {len(groups)} user-agent lines; "
      f"AI group: {[g for g in groups if g in ('GPTBot', 'ChatGPT-User', 'Google-Extended', 'anthropic-ai', 'Claude-Web', 'CCBot', 'PerplexityBot')]}")
for needle in ("BLOQUEIO DE BOTS DE INTELIGÊNCIA ARTIFICIAL", "Evita que o conteúdo do site seja usado para treinar IAs.",
               "Disallow: /deputados/*/*", "Disallow: /*.pdf"):
    print(f"  {'found' if needle in txt else 'MISSING'}: {needle!r}")

checks = [
    ("/faq/faq-home.html", [
        "É totalmente de graça",
        "os dados são públicos! E não, não é preciso se cadastrar, nem se identificar para baixar qualquer dos conjuntos de dados.",
        "Posso cobrar por um aplicativo ou serviço que use os dados da Câmara?",
        "Sim, pode. Não há qualquer restrição quanto ao isso.",
        "os tornam mais adequados ao processamento por softwares de diversos tipos",
        "Existem restrições às informações que podem ser divulgadas, especialmente as de caráter pessoal e/ou familiar."]),
    ("/howtouse/sobre-dados-abertos.html", [
        "Serviços de dados abertos são feitos para máquinas e programas (softwares)",
        "Livres de licenças"]),
]
words = r"intelig[eê]ncia artificial|\bIA\b|\bAI\b|aprendizado de m[aá]quina|scrap\w*|raspagem|rob[oô]s?\b|crawl\w*|n[aã]o comercia\w*|licen[cç]a\w*"
for path, needles in checks:
    st, final, txt = page(SITE + path, needles[0][:30])
    print(f"\n{path} -> HTTP {st} {final}")
    for needle in needles:
        print(f"  {'found' if ' '.join(needle.split()) in txt else 'MISSING'}: {needle[:100]!r}")
    for m in re.finditer(words, txt, re.I):
        print(f"  word {m[0]!r} in: ...{txt[max(0, m.start() - 45):m.end() + 30]}...")
    print(f"  words /{words}/: {len(re.findall(words, txt, re.I))} hit(s)")
# the portal's terms (footer link "Termos de uso" on www.camara.leg.br); they cover www.camara.leg.br
st, final, txt = page("https://www2.camara.leg.br/termo-de-uso-e-politica-de-privacidade", "Termos gerais")
print(f"\nterms -> HTTP {st} {final}")
for needle in (
        "Você concorda com o Termo de uso e política de privacidade abaixo ao acessar o portal da Câmara dos Deputados (www.camara.leg.br).",
        'Todas as informações publicadas no Portal da Câmara são de domínio público, gratuitas e podem ser reproduzidas desde que citada a fonte "Câmara dos Deputados" e a autoria da informação, quando houver.',
        "Podemos coibir a participação de sistemas automatizados ou robôs (scripts, bots, entre outros) que tentem imitar pessoas.",
        "A Câmara dos Deputados pode usar ferramentas de Inteligência Artificial (IA) para gerar conteúdos, sempre com supervisão humana."):
    print(f"  {'found' if needle in txt else 'MISSING'}: {needle[:100]!r}")
for m in re.finditer(words, txt, re.I):
    print(f"  word {m[0]!r} in: ...{txt[max(0, m.start() - 45):m.end() + 30]}...")

# the API's own docs (the OpenAPI document the docs page loads)
page(SITE + "/swagger/api.html", "/proposicoes")
spec = json.loads(raw(f"{API}/api-docs")["text"])
print(f"\nOpenAPI {spec['info']['description'][:50]!r}")
for path, needles in (
    ("/proposicoes", ["Por padrão, são retornadas todas as proposições que foram apresentadas ou tiveram alguma mudança de situação nos últimos 30 dias."]),
    ("/votacoes", ["são retornados dados sobre todas as votações ocorridas nos últimos 30 dias, em eventos de todos os órgãos.",
                   "é **necessário** que as duas datas sejam de um mesmo ano"]),
    ("/votacoes/{id}/votos", ["O resultado é uma lista vazia se `{id}` foi uma votação _simbólica_",
                              "Não são listados parlamentares ausentes à votação."]),
):
    desc = " ".join(spec["paths"][path]["get"]["description"].split())
    for needle in needles:
        print(f"  {path}: {'found' if needle in desc else 'MISSING'}: {needle[:100]!r}")
itens = [p for p in spec["paths"]["/votacoes"]["get"]["parameters"] if p["name"] == "itens"][0]["description"]
print(f"  /votacoes itens: {itens!r}")
print()

def brief(r):
    out = f"HTTP {r['status']} {r['type'].split(';')[0] or '-'} {len(r['text']):,} chars retry-after={r['retry']}"
    if "json" not in r["type"]:
        return out + f" {' '.join(r['text'].split())[:70]!r}"
    d = json.loads(r["text"])
    if "dados" not in d:
        return out + " " + json.dumps(d, ensure_ascii=False)[:120]
    rows = d["dados"] if isinstance(d["dados"], list) else [d["dados"]]
    first = rows[0] if rows else {}
    label = (f"{first.get('siglaTipo')} {first.get('numero')}/{first.get('ano')}" if "numero" in first
             else f"{first.get('id')} {first.get('dataHoraRegistro', '')}" if first else "")
    return out + f" total={r['total']} rows={len(rows)} first={label!r}"

P = f"{API}/proposicoes?siglaTipo=PL&ordem=DESC&ordenarPor=id&itens=1"
for label, url, accept in (
    ("keywords without accents          ", f"{P}&keywords=inteligencia%20artificial", "application/json"),
    ("keywords with accents             ", f"{P}&keywords=intelig%C3%AAncia%20artificial", "application/json"),
    ("keywords + ano=2026 (no 30 days)  ", f"{P}&keywords=inteligencia%20artificial&ano=2026", "application/json"),
    ("no Accept header (fetch default)  ", f"{P}&keywords=inteligencia%20artificial", None),
    ("browser page Accept (text/html..) ", f"{P}&keywords=inteligencia%20artificial", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
    ("itens=200 (max is 100)            ", f"{API}/proposicoes?siglaTipo=PL&keywords=inteligencia%20artificial&itens=200", "application/json"),
    ("ordenarPor=dataApresentacao       ", f"{API}/proposicoes?siglaTipo=PL&ordenarPor=dataApresentacao&itens=1", "application/json"),
    ("unknown parameter foo=1           ", f"{P}&foo=1", "application/json"),
    ("siglaTipo=XX                      ", f"{API}/proposicoes?siglaTipo=XX&itens=1", "application/json"),
    ("unknown bill id                   ", f"{API}/proposicoes/999999999", "application/json"),
    ("newest vote, any body             ", f"{API}/votacoes?ordem=DESC&ordenarPor=dataHoraRegistro&itens=1", "application/json"),
    ("newest vote, idOrgao=180 (PLEN)   ", f"{API}/votacoes?idOrgao=180&ordem=DESC&ordenarPor=dataHoraRegistro&itens=1", "application/json"),
    ("votacoes dataInicio/Fim 2 years   ", f"{API}/votacoes?dataInicio=2025-12-01&dataFim=2026-01-31&itens=1", "application/json"),
):
    print(f"{label} {brief(raw(url, accept))}")
print("\nSource: Dados Abertos da Camara dos Deputados; answers shortened to the fields shown.")
```

Output (verifier's re-run, 2026-11-24 23:57 UTC, after the terms check was added; byte-identical to the author's third run at 23:39 apart from the terms lines, which replaced a probe of the HTTP 404 www.camara.leg.br/termos-de-uso; the author's second run printed the same apart from the one FAQ quote that was split to leave out its dash; the first run read the page with `innerText` and reported four FAQ quotes MISSING because the answers sit in collapsed panels):

```text
robots.txt dadosabertos.camara.leg.br HTTP 200: user-agent lines 0; disallow lines 0; 'Ir para o conteúdo. Toggle navigation HOME FAQ CONTATO Página de consu'
robots.txt www.camara.leg.br (not used) HTTP 200: 28 user-agent lines; AI group: ['GPTBot', 'ChatGPT-User', 'Google-Extended', 'anthropic-ai', 'Claude-Web', 'CCBot', 'PerplexityBot']
  found: 'BLOQUEIO DE BOTS DE INTELIGÊNCIA ARTIFICIAL'
  found: 'Evita que o conteúdo do site seja usado para treinar IAs.'
  found: 'Disallow: /deputados/*/*'
  found: 'Disallow: /*.pdf'

/faq/faq-home.html -> HTTP 200 https://dadosabertos.camara.leg.br/faq/faq-home.html
  found: 'É totalmente de graça'
  found: 'os dados são públicos! E não, não é preciso se cadastrar, nem se identificar para baixar qualquer do'
  found: 'Posso cobrar por um aplicativo ou serviço que use os dados da Câmara?'
  found: 'Sim, pode. Não há qualquer restrição quanto ao isso.'
  found: 'os tornam mais adequados ao processamento por softwares de diversos tipos'
  found: 'Existem restrições às informações que podem ser divulgadas, especialmente as de caráter pessoal e/ou'
  words /intelig[eê]ncia artificial|\bIA\b|\bAI\b|aprendizado de m[aá]quina|scrap\w*|raspagem|rob[oô]s?\b|crawl\w*|n[aã]o comercia\w*|licen[cç]a\w*/: 0 hit(s)

/howtouse/sobre-dados-abertos.html -> HTTP 200 https://dadosabertos.camara.leg.br/howtouse/sobre-dados-abertos.html
  found: 'Serviços de dados abertos são feitos para máquinas e programas (softwares)'
  found: 'Livres de licenças'
  word 'licenças' in: ... o seu processamento automatizado. Livres de licenças - Os dados não devem ser suje...
  words /intelig[eê]ncia artificial|\bIA\b|\bAI\b|aprendizado de m[aá]quina|scrap\w*|raspagem|rob[oô]s?\b|crawl\w*|n[aã]o comercia\w*|licen[cç]a\w*/: 1 hit(s)

terms -> HTTP 200 https://www2.camara.leg.br/termo-de-uso-e-politica-de-privacidade
  found: 'Você concorda com o Termo de uso e política de privacidade abaixo ao acessar o portal da Câmara dos '
  found: 'Todas as informações publicadas no Portal da Câmara são de domínio público, gratuitas e podem ser re'
  found: 'Podemos coibir a participação de sistemas automatizados ou robôs (scripts, bots, entre outros) que t'
  found: 'A Câmara dos Deputados pode usar ferramentas de Inteligência Artificial (IA) para gerar conteúdos, s'
  word 'robôs' in: ... a participação de sistemas automatizados ou robôs (scripts, bots, entre outros)...
  word 'Inteligência Artificial' in: ...âmara dos Deputados pode usar ferramentas de Inteligência Artificial (IA) para gerar conteúdos, se...
  word 'IA' in: ...usar ferramentas de Inteligência Artificial (IA) para gerar conteúdos, sempre...
  word 'IA' in: ... Quando isso ocorrer, você será informado. A IA também pode ser utilizada par...

OpenAPI '**Versão: 0.4.362 - 11/23/2026 11:19 AM** - _confi'
  /proposicoes: found: 'Por padrão, são retornadas todas as proposições que foram apresentadas ou tiveram alguma mudança de '
  /votacoes: found: 'são retornados dados sobre todas as votações ocorridas nos últimos 30 dias, em eventos de todos os ó'
  /votacoes: found: 'é **necessário** que as duas datas sejam de um mesmo ano'
  /votacoes/{id}/votos: found: 'O resultado é uma lista vazia se `{id}` foi uma votação _simbólica_'
  /votacoes/{id}/votos: found: 'Não são listados parlamentares ausentes à votação.'
  /votacoes itens: 'Número máximo de itens na página que se deseja obter com esta requisição. O valor padrão e máximo para este endpoint é 100, e valores maiores serão ignorados.'

keywords without accents           HTTP 200 application/json 1,278 chars retry-after=30 total=105 rows=1 first='PL 5928/2026'
keywords with accents              HTTP 200 application/json 1,298 chars retry-after=30 total=105 rows=1 first='PL 5928/2026'
keywords + ano=2026 (no 30 days)   HTTP 200 application/json 1,314 chars retry-after=30 total=110 rows=1 first='PL 5928/2026'
no Accept header (fetch default)   HTTP 200 application/json 1,278 chars retry-after=30 total=105 rows=1 first='PL 5928/2026'
browser page Accept (text/html..)  HTTP 200 application/xml 1,515 chars retry-after=30 '<xml><dados><proposicao_><id>2658843</id><uri>https://dadosabertos.cam'
itens=200 (max is 100)             HTTP 200 application/json 46,599 chars retry-after=30 total=105 rows=100 first='PL 759/2023'
ordenarPor=dataApresentacao        HTTP 400 application/json 131 chars retry-after=30 {"status": 400, "title": "Requisição inválida", "detail": "Parâmetro(s) inválido(s).", "instance": "ordenarPor=dataApres
unknown parameter foo=1            HTTP 400 application/json 107 chars retry-after=30 {"status": 400, "title": "Requisição inválida", "detail": "Parâmetro(s) inválido(s).", "instance": "foo", "code": 5}
siglaTipo=XX                       HTTP 200 application/json 121 chars retry-after=30 total=0 rows=0 first=''
unknown bill id                    HTTP 404 application/json 208 chars retry-after=30 {"status": 404, "title": "Recurso não encontrado", "detail": "A URL passada se refere a um recurso que não existe no sis
newest vote, any body              HTTP 200 application/json 1,005 chars retry-after=30 total=2245 rows=1 first='2332174-62 2026-11-24T17:53:39'
newest vote, idOrgao=180 (PLEN)    HTTP 200 application/json 1,039 chars retry-after=30 total=406 rows=1 first='2655570-60 2026-11-24T00:35:14'
votacoes dataInicio/Fim 2 years    HTTP 200 application/json 1,062 chars retry-after=30 total=1585 rows=1 first='2593430-3 2026-07-01T15:14:21'

Source: Dados Abertos da Camara dos Deputados; answers shortened to the fields shown.
```

### 3. The same task with Python urllib: robots check for every agent, all result pages, seats per party, two CSV files (cache by max-age, no browser)

`python3 block3.py ["KEYWORDS" [N]]` (default `"inteligencia artificial" 5`). With an empty cache: robots.txt, every page of the search (2 pages of 100 for 105 hits), one detail per bill shown, the vote list, the votes of each plenary vote until a roll-call, its orientations and the 6 pages of deputies in office (513, for the "seats" column): 18 calls. Writes `camara-pl-<keywords>.csv` (one row per bill shown) and `camara-votos-<id>.csv` (name, party, UF and vote only).

```python
import csv, email.utils, gzip, hashlib, json, os, re, sys, time, unicodedata, urllib.error, urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlsplit

KEYWORDS = sys.argv[1] if len(sys.argv) > 1 else "inteligencia artificial"
N_BILLS = int(sys.argv[2]) if len(sys.argv) > 2 else 5
ORGAO = "PLEN"       # siglaOrgao; "" = any body
MIN_ROWS = 20        # this skill's cut-off for a roll-call (nominal) vote; symbolic votes have 0 or a few rows
MAX_SCAN = 15        # votes to check, newest first
MAX_PAGES = 5        # pages of 100 to read from a search or the vote list (the deputies list, 513 rows, always reads all 6)
UA = "camara-deputados-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
HOST = "dadosabertos.camara.leg.br"
API = f"https://{HOST}/api/v2"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai", "Claude-Web",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider", "camara-deputados-skill-example"]  # last = this UA
CACHE_DIR = "~/.cache/camara-deputados-skill"
CACHE = os.path.expanduser(CACHE_DIR)
BRT = timezone(timedelta(hours=-3))   # Brasilia local time; the API strings carry no offset
PAUSE = 1.0                           # serial, 1 s apart
calls = []

def retry_wait(value, default):
    v = (value or "").strip()
    if v.isdigit():
        return int(v)
    try:
        return max(0, int((email.utils.parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()) + 1)
    except (TypeError, ValueError):
        return default

def http(url, accept="application/json", ok=(200,)):
    """GET with gzip -> (status, headers, body). 'retry-after: 30' comes on every answer, so it is only read on
    429/5xx: wait once (over 120 s exits). Network errors wait 30 s once. Exits on anything else."""
    for attempt in range(2):
        time.sleep(PAUSE)
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept, "Accept-Encoding": "gzip"})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                body = r.read()
                calls.append(r.status)
                return r.status, r.headers, gzip.decompress(body) if r.headers.get("Content-Encoding") == "gzip" else body
        except urllib.error.HTTPError as e:
            calls.append(e.code)
            if e.code in ok:
                return e.code, e.headers, e.read()
            if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                wait = retry_wait(e.headers.get("Retry-After"), 30)
                if wait > 120:
                    sys.exit(f"{url}: server asks to wait {wait} s: stopping")
                time.sleep(wait)
                continue
            sys.exit(f"HTTP {e.code} {url}: {' '.join(e.read().decode(errors='replace').split())[:200]}")
        except OSError as e:
            if attempt == 0:
                time.sleep(30)
                continue
            sys.exit(f"{url}: {e}")

def get(url):
    """-> (JSON, headers). Lists that send Cache-Control max-age (proposicoes 360 s, deputados 1800 s) are reused from
    the cache while fresh; everything else is fetched."""
    f = os.path.join(CACHE, hashlib.sha256(url.encode()).hexdigest() + ".json")
    try:
        with open(f) as fh:
            old = json.load(fh)
        if time.time() < old["until"]:
            return old["data"], old["headers"]
    except (OSError, ValueError, KeyError):
        pass
    st, h, body = http(url)
    if "json" not in (h.get("Content-Type") or ""):
        sys.exit(f"{url}: {h.get('Content-Type')} instead of JSON: stop")
    data, keep = json.loads(body), {k: h.get(k) for k in ("Link", "X-Total-Count")}
    m = re.search(r"max-age=(\d+)", h.get("Cache-Control") or "")
    if m:
        os.makedirs(CACHE, exist_ok=True)
        with open(f, "w") as fh:
            json.dump({"until": time.time() + int(m[1]), "data": data, "headers": keep}, fh)
    return data, keep

def all_pages(url, limit=MAX_PAGES):
    """Follow links rel="next" (itens max 100) up to `limit` pages -> (rows, X-Total-Count, pages read, next URL)."""
    rows, pages, total = [], 0, None
    while url and pages < limit:
        d, h = get(url)
        rows += d["dados"]
        pages += 1
        total = total or h.get("X-Total-Count")
        nxt = [l["href"] for l in d.get("links", []) if l["rel"] == "next"]
        url = nxt[0] if nxt else None
    return rows, int(total or len(rows)), pages, url

# robots.txt groups and RFC 9309 matching (longest pattern wins, Allow on a tie); a non-robots answer means no rules
def robots_groups(text):
    groups, agents, in_rules = {}, [], False
    for line in text.splitlines():
        k, _, v = line.split("#")[0].partition(":")
        k, v = k.strip().lower(), v.strip()
        if k == "user-agent":
            agents, in_rules = (agents if not in_rules else []) + [v.lower()], False
            for a in agents:
                groups.setdefault(a, [])
        elif k in ("allow", "disallow") and agents:
            in_rules = True
            for a in agents:
                if v:
                    groups[a].append((k == "allow", v))
    return groups

def allowed(groups, agent, path):
    rules = groups.get(agent.lower(), groups.get("*", []))
    hits = [(len(p), ok) for ok, p in rules
            if re.match(re.escape(p.rstrip("$")).replace(r"\*", ".*") + ("$" if p.endswith("$") else ""), path)]
    return max(hits, default=(0, True))[1]

fold = lambda s: re.sub(r"[\u0300-\u036f]", "", unicodedata.normalize("NFD", s or "")).lower()
slug = lambda s: re.sub(r"[^a-z0-9]+", "-", fold(s)).strip("-")
utc = lambda s: f"{datetime.fromisoformat(s).replace(tzinfo=BRT).astimezone(timezone.utc):%d %b %H:%M} UTC"
now = datetime.now(timezone.utc)
print(f"Dados Abertos da Camara dos Deputados API v2, {now:%Y-%m-%d %H:%M} UTC")

# 1) robots.txt: every path below, for every agent
paths = ["/api/v2/proposicoes", "/api/v2/proposicoes/1", "/api/v2/votacoes", "/api/v2/votacoes/1-1/votos",
         "/api/v2/votacoes/1-1/orientacoes", "/api/v2/deputados"]
st, h, body = http(f"https://{HOST}/robots.txt", accept="text/plain", ok=(200, 404))
text = body.decode(errors="replace")
is_robots = st == 200 and "text/plain" in (h.get("Content-Type") or "") and re.search(r"(?im)^user-agent:", text)
groups = robots_groups(text) if is_robots else {}
bad = [(a, p) for a in AGENTS for p in paths if not allowed(groups, a, p)]
print(f"robots.txt {HOST}: HTTP {st} {h.get('Content-Type')}"
      + ("" if is_robots else " (an HTML page, no robots rules: everything allowed)")
      + f"; {len(paths)} paths x {len(AGENTS)} agents: {len(paths) * len(AGENTS) - len(bad)} allowed")
if bad or st >= 500:
    sys.exit(f"robots.txt disallows {bad[:3]} (or could not be read): stop")

# 2) every PL matching the keywords (presented or moved in the last 30 days), newest presented first
bills, total, pages, more = all_pages(f"{API}/proposicoes?keywords={quote(KEYWORDS)}&siglaTipo=PL&itens=100&ordem=DESC&ordenarPor=id")
if not bills:
    sys.exit(f"no PL matches {KEYWORDS!r} in the last 30 days: stop")
if len(bills) < total:
    print(f"  PARTIAL: read {len(bills)} of {total} ({pages} pages; raise MAX_PAGES to read on from {more})")
bills.sort(key=lambda b: (b["dataApresentacao"], b["id"]), reverse=True)
year = now.astimezone(BRT).year
print(f"\n{total} PL bills match {KEYWORDS!r} ({pages} page(s) of 100); numbered {year}: "
      f"{sum(b['ano'] == year for b in bills)}; older bills that moved recently: {sum(b['ano'] < year for b in bills)}. Newest {N_BILLS}:")
out_b = f"camara-pl-{slug(KEYWORDS)}.csv"
with open(out_b, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["pl", "id", "presented_brasilia", "latest_step_brasilia", "orgao", "step", "situacao", "ementa", "api_uri"])
    for b in bills[:N_BILLS]:
        d, _ = get(f"{API}/proposicoes/{b['id']}")
        d = d["dados"]
        s = d["statusProposicao"]
        name = f"PL {d['numero']}/{d['ano']}"
        print(f"  {name:<14} presented {d['dataApresentacao'].replace('T', ' ')} | latest {s['dataHora'].replace('T', ' ')} "
              f"{s['siglaOrgao']}: {s['descricaoTramitacao']}" + (f" ({s['descricaoSituacao']})" if s["descricaoSituacao"] else ""))
        print(f"  {'':<14} {' '.join(d['ementa'].split())[:150]}{'...' if len(d['ementa']) > 150 else ''}")
        w.writerow([name, d["id"], d["dataApresentacao"], s["dataHora"], s["siglaOrgao"], s["descricaoTramitacao"],
                    s["descricaoSituacao"] or "", " ".join(d["ementa"].split()), d["uri"]])
print(f"  -> {out_b}")

# 3) the most recent roll-call vote (newest first; filter on siglaOrgao, not idOrgao, see Gotchas)
#    100 per page, following links rel="next" until one is found, MAX_SCAN votes were checked or MAX_PAGES were read
url, vpages, pick, symbolic = f"{API}/votacoes?ordem=DESC&ordenarPor=dataHoraRegistro&itens=100", 0, None, 0
while url and pick is None and symbolic < MAX_SCAN and vpages < MAX_PAGES:
    votes, _ = get(url)
    vpages += 1
    for v in votes["dados"]:
        if ORGAO and v["siglaOrgao"] != ORGAO:
            continue
        if symbolic >= MAX_SCAN:
            break
        rows, _ = get(f"{API}/votacoes/{v['id']}/votos")
        if len(rows["dados"]) >= MIN_ROWS:
            pick, rows = v, rows["dados"]
            break
        symbolic += 1
    url = next((l["href"] for l in votes.get("links", []) if l["rel"] == "next"), None)
if not pick:
    sys.exit(f"no roll-call vote among the newest {symbolic} {ORGAO} votes in {vpages} page(s) of 100 "
             f"({'MAX_SCAN or MAX_PAGES reached' if url else 'no more pages'}): stop")
orient, _ = get(f"{API}/votacoes/{pick['id']}/orientacoes")
ori = {o["siglaPartidoBloco"]: o["orientacaoVoto"] or "(blank)" for o in orient["dados"]}
for fed, said in list(ori.items()):
    if fed.startswith("Fdr "):
        for member in fed[4:].split("-"):
            ori.setdefault(member, f"{said} (via {fed})")

# 4) seats per party now (all deputies in office, 100 per page), to set turnout against the bench
deps, ndeps, dpages, _ = all_pages(f"{API}/deputados?itens=100", limit=10)
if len(deps) != ndeps:
    sys.exit(f"deputies list: read {len(deps)} of {ndeps} in {dpages} pages: stop")
seats = Counter(d["siglaPartido"] for d in deps)
print(f"\nRoll-call {pick['id']} ({pick['siglaOrgao']}) {pick['dataHoraRegistro'].replace('T', ' ')} Brasilia = {utc(pick['dataHoraRegistro'])}; "
      f"{symbolic} newer symbolic vote(s) skipped")
print(f"  {' '.join(pick['descricao'].split())[:220]}")
by = defaultdict(Counter)
for x in rows:
    by[x["deputado_"]["siglaPartido"]][x["tipoVoto"]] += 1
print(f"  {'party':<14}{'seats':>6}{'voted':>6}{'Sim':>5}{'Não':>5}{'other':>6}  {'party line':<10}{'with line':>10}  leader said")
for party, c in sorted(by.items(), key=lambda kv: -sum(kv[1].values())):
    n = sum(c.values())
    line, k = c.most_common(1)[0]
    print(f"  {party:<14}{seats.get(party, 0):>6}{n:>6}{c['Sim']:>5}{c['Não']:>5}{n - c['Sim'] - c['Não']:>6}  "
          f"{line:<10}{k / n:>9.0%}  {ori.get(party, '(none listed)')}")
tot = Counter(x["tipoVoto"] for x in rows)
print(f"  {'all':<14}{ndeps:>6}{len(rows):>6}{tot['Sim']:>5}{tot['Não']:>5}{len(rows) - tot['Sim'] - tot['Não']:>6}  "
      + ", ".join(f"{k} {v}" for k, v in tot.items() if k not in ("Sim", "Não")))
m = re.search(r"Sim:\s*(\d+);\s*Não:\s*(\d+)", pick["descricao"])
if m and (int(m[1]), int(m[2])) != (tot["Sim"], tot["Não"]):
    print(f"  MISMATCH with the descricao (Sim {m[1]}, Não {m[2]}): the vote list may still be loading; re-run later")
elif m:
    print(f"  Sim/Não match the descricao ({m[1]}/{m[2]})")
out_v = f"camara-votos-{pick['id']}.csv"
with open(out_v, "w", newline="") as fh:   # name, party, UF and vote only: the rows also carry e-mail and photo URL
    w = csv.writer(fh)
    w.writerow(["nome", "partido", "uf", "voto"])
    for x in sorted(rows, key=lambda x: (x["deputado_"]["siglaPartido"], fold(x["deputado_"]["nome"]))):
        w.writerow([x["deputado_"]["nome"], x["deputado_"]["siglaPartido"], x["deputado_"]["siglaUf"], x["tipoVoto"]])
print(f"  -> {out_v} ({len(rows)} rows: nome, partido, uf, voto)")
print(f"\ncalls this run: {len(calls)} ({', '.join(map(str, calls))}); cache {CACHE_DIR}")
print("Source: Dados Abertos da Camara dos Deputados (API v2). Seats = deputies in office today, as the API lists them; "
      "tallies, party lines and shares computed here.")
```

Output (re-run on 2026-11-25, 01:00 UTC, empty cache; the same bills, vote and tallies as the 23:42 UTC run on 2026-11-24; the first run at 23:40 read only 500 of the 513 deputies, because the deputies list was capped by `MAX_PAGES`; the fix reads it to the end and stops if the count still differs):

```text
Dados Abertos da Camara dos Deputados API v2, 2026-11-25 01:00 UTC
robots.txt dadosabertos.camara.leg.br: HTTP 200 text/html; charset=utf-8 (an HTML page, no robots rules: everything allowed); 6 paths x 13 agents: 78 allowed

105 PL bills match 'inteligencia artificial' (2 page(s) of 100); numbered 2026: 76; older bills that moved recently: 29. Newest 5:
  PL 5928/2026   presented 2026-11-23 15:26 | latest 2026-11-23 15:26 MESA: Apresentação de Proposição
                 Institui normas de proteção do trabalhador frente a decisões automatizadas e à vigilância por sistemas de inteligência artificial nas relações de trab...
  PL 5864/2026   presented 2026-11-16 14:30 | latest 2026-11-16 14:30 MESA: Apresentação de Proposição (Aguardando Autorização do Despacho)
                 Veda a criação e o uso comercial de réplicas de voz ou de imagem de pessoa natural geradas por inteligência artificial sem autorização expressa do tit...
  PL 5826/2026   presented 2026-11-11 18:06 | latest 2026-11-11 18:06 MESA: Apresentação de Proposição (Aguardando Autorização do Despacho)
                 Altera a Lei nº 8.078, de 11 de setembro de 1990, para vedar a utilização de sistemas de inteligência artificial na publicidade, oferta, apresentação ...
  PL 5813/2026   presented 2026-11-10 18:28 | latest 2026-11-10 18:28 MESA: Apresentação de Proposição (Aguardando Autorização do Despacho)
                 Altera a Lei nº 14.308, de 8 de março de 2022, para estabelecer diretrizes de medicina de precisão, diagnóstico molecular e genômico, avaliação multid...
  PL 5729/2026   presented 2026-11-03 13:46 | latest 2026-11-03 13:46 MESA: Apresentação de Proposição (Aguardando Chancela e Publicação do Despacho)
                 Institui a Lei Anticrime Deepfake, estabelece medidas penais, processuais e de investigação destinadas à repressão de fraudes, extorsões e organizaçõe...
  -> camara-pl-inteligencia-artificial.csv

Roll-call 2332174-59 (PLEN) 2026-11-24 17:52:28 Brasilia = 24 Nov 20:52 UTC; 1 newer symbolic vote(s) skipped
  Aprovado o Substitutivo ao Projeto de Lei nº 1.969, de 2022, da Comissão de Direitos Humanos, Minorias e Igualdade Racial. Sim: 292; Não: 147; Abstenção: 2; Total: 441.
  party          seats voted  Sim  Não other  party line with line  leader said
  PL                98    85    5   80     0  Não             94%  Não
  PT                67    64   63    0     1  Sim             98%  Sim (via Fdr PT-PCdoB-PV)
  UNIÃO             50    42   27   15     0  Sim             64%  (none listed)
  PSD               48    39   33    5     1  Sim             85%  (none listed)
  PP                47    36   27    9     0  Sim             75%  (none listed)
  REPUBLICANOS      43    35   29    6     0  Sim             83%  (none listed)
  MDB               38    29   11   17     1  Não             59%  (none listed)
  PODE              27    24   20    4     0  Sim             83%  (none listed)
  PSB               17    16   15    1     0  Sim             94%  Sim
  PSDB              17    15   14    1     0  Sim             93%  (none listed)
  PSOL              13    13   13    0     0  Sim            100%  Sim (via Fdr PSOL-REDE)
  PCdoB             10    10   10    0     0  Sim            100%  Sim (via Fdr PT-PCdoB-PV)
  PDT                9     7    7    0     0  Sim            100%  Sim
  PV                 6     6    6    0     0  Sim            100%  Sim (via Fdr PT-PCdoB-PV)
  NOVO               5     5    0    5     0  Não            100%  Não
  SOLIDARIEDADE      4     4    3    1     0  Sim             75%  (blank)
  AVANTE             5     4    4    0     0  Sim            100%  (blank)
  PRD                3     3    2    1     0  Sim             67%  (blank)
  REDE               3     3    3    0     0  Sim            100%  Sim (via Fdr PSOL-REDE)
  MISSÃO             1     1    0    1     0  Não            100%  (blank)
  CIDADANIA          2     1    0    1     0  Não            100%  (none listed)
  all              513   442  292  147     3  Abstenção 2, Artigo 17 1
  Sim/Não match the descricao (292/147)
  -> camara-votos-2332174-59.csv (442 rows: nome, partido, uf, voto)

calls this run: 18 (200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200); cache ~/.cache/camara-deputados-skill
Source: Dados Abertos da Camara dos Deputados (API v2). Seats = deputies in office today, as the API lists them; tallies, party lines and shares computed here.
```

The warm run a few seconds later printed the same lines with 10 calls instead of 18 (both search pages and the 6 deputies pages came from the cache):

```text
Dados Abertos da Camara dos Deputados API v2, 2026-11-25 01:00 UTC
robots.txt dadosabertos.camara.leg.br: HTTP 200 text/html; charset=utf-8 (an HTML page, no robots rules: everything allowed); 6 paths x 13 agents: 78 allowed

105 PL bills match 'inteligencia artificial' (2 page(s) of 100); numbered 2026: 76; older bills that moved recently: 29. Newest 5:
  PL 5928/2026   presented 2026-11-23 15:26 | latest 2026-11-23 15:26 MESA: Apresentação de Proposição
                 Institui normas de proteção do trabalhador frente a decisões automatizadas e à vigilância por sistemas de inteligência artificial nas relações de trab...
  PL 5864/2026   presented 2026-11-16 14:30 | latest 2026-11-16 14:30 MESA: Apresentação de Proposição (Aguardando Autorização do Despacho)
                 Veda a criação e o uso comercial de réplicas de voz ou de imagem de pessoa natural geradas por inteligência artificial sem autorização expressa do tit...
  PL 5826/2026   presented 2026-11-11 18:06 | latest 2026-11-11 18:06 MESA: Apresentação de Proposição (Aguardando Autorização do Despacho)
                 Altera a Lei nº 8.078, de 11 de setembro de 1990, para vedar a utilização de sistemas de inteligência artificial na publicidade, oferta, apresentação ...
  PL 5813/2026   presented 2026-11-10 18:28 | latest 2026-11-10 18:28 MESA: Apresentação de Proposição (Aguardando Autorização do Despacho)
                 Altera a Lei nº 14.308, de 8 de março de 2022, para estabelecer diretrizes de medicina de precisão, diagnóstico molecular e genômico, avaliação multid...
  PL 5729/2026   presented 2026-11-03 13:46 | latest 2026-11-03 13:46 MESA: Apresentação de Proposição (Aguardando Chancela e Publicação do Despacho)
                 Institui a Lei Anticrime Deepfake, estabelece medidas penais, processuais e de investigação destinadas à repressão de fraudes, extorsões e organizaçõe...
  -> camara-pl-inteligencia-artificial.csv

Roll-call 2332174-59 (PLEN) 2026-11-24 17:52:28 Brasilia = 24 Nov 20:52 UTC; 1 newer symbolic vote(s) skipped
  Aprovado o Substitutivo ao Projeto de Lei nº 1.969, de 2022, da Comissão de Direitos Humanos, Minorias e Igualdade Racial. Sim: 292; Não: 147; Abstenção: 2; Total: 441.
  party          seats voted  Sim  Não other  party line with line  leader said
  PL                98    85    5   80     0  Não             94%  Não
  PT                67    64   63    0     1  Sim             98%  Sim (via Fdr PT-PCdoB-PV)
  UNIÃO             50    42   27   15     0  Sim             64%  (none listed)
  PSD               48    39   33    5     1  Sim             85%  (none listed)
  PP                47    36   27    9     0  Sim             75%  (none listed)
  REPUBLICANOS      43    35   29    6     0  Sim             83%  (none listed)
  MDB               38    29   11   17     1  Não             59%  (none listed)
  PODE              27    24   20    4     0  Sim             83%  (none listed)
  PSB               17    16   15    1     0  Sim             94%  Sim
  PSDB              17    15   14    1     0  Sim             93%  (none listed)
  PSOL              13    13   13    0     0  Sim            100%  Sim (via Fdr PSOL-REDE)
  PCdoB             10    10   10    0     0  Sim            100%  Sim (via Fdr PT-PCdoB-PV)
  PDT                9     7    7    0     0  Sim            100%  Sim
  PV                 6     6    6    0     0  Sim            100%  Sim (via Fdr PT-PCdoB-PV)
  NOVO               5     5    0    5     0  Não            100%  Não
  SOLIDARIEDADE      4     4    3    1     0  Sim             75%  (blank)
  AVANTE             5     4    4    0     0  Sim            100%  (blank)
  PRD                3     3    2    1     0  Sim             67%  (blank)
  REDE               3     3    3    0     0  Sim            100%  Sim (via Fdr PSOL-REDE)
  MISSÃO             1     1    0    1     0  Não            100%  (blank)
  CIDADANIA          2     1    0    1     0  Não            100%  (none listed)
  all              513   442  292  147     3  Abstenção 2, Artigo 17 1
  Sim/Não match the descricao (292/147)
  -> camara-votos-2332174-59.csv (442 rows: nome, partido, uf, voto)

calls this run: 10 (200, 200, 200, 200, 200, 200, 200, 200, 200, 200); cache ~/.cache/camara-deputados-skill
Source: Dados Abertos da Camara dos Deputados (API v2). Seats = deputies in office today, as the API lists them; tallies, party lines and shares computed here.
```

Another topic (`python3 block3.py deepfake 3`, 01:00 UTC; the deputies list still fresh in the cache) and a keyword with no match (`"xyzzy quantum"`, which stops):

```text
Dados Abertos da Camara dos Deputados API v2, 2026-11-25 01:01 UTC
robots.txt dadosabertos.camara.leg.br: HTTP 200 text/html; charset=utf-8 (an HTML page, no robots rules: everything allowed); 6 paths x 13 agents: 78 allowed

15 PL bills match 'deepfake' (1 page(s) of 100); numbered 2026: 13; older bills that moved recently: 2. Newest 3:
  PL 5864/2026   presented 2026-11-16 14:30 | latest 2026-11-16 14:30 MESA: Apresentação de Proposição (Aguardando Autorização do Despacho)
                 Veda a criação e o uso comercial de réplicas de voz ou de imagem de pessoa natural geradas por inteligência artificial sem autorização expressa do tit...
  PL 5729/2026   presented 2026-11-03 13:46 | latest 2026-11-03 13:46 MESA: Apresentação de Proposição (Aguardando Chancela e Publicação do Despacho)
                 Institui a Lei Anticrime Deepfake, estabelece medidas penais, processuais e de investigação destinadas à repressão de fraudes, extorsões e organizaçõe...
  PL 4849/2026   presented 2026-07-31 15:18 | latest 2026-11-23 16:26 CCJC: Apensação (Tramitando em Conjunto)
                 Altera o Decreto-Lei nº 2.848, de 7 de dezembro de 1940 (Código Penal), para tipificar a falsidade de identidade praticada mediante conteúdo gerado ou...
  -> camara-pl-deepfake.csv

Roll-call 2332174-59 (PLEN) 2026-11-24 17:52:28 Brasilia = 24 Nov 20:52 UTC; 1 newer symbolic vote(s) skipped
  Aprovado o Substitutivo ao Projeto de Lei nº 1.969, de 2022, da Comissão de Direitos Humanos, Minorias e Igualdade Racial. Sim: 292; Não: 147; Abstenção: 2; Total: 441.
  party          seats voted  Sim  Não other  party line with line  leader said
  PL                98    85    5   80     0  Não             94%  Não
  PT                67    64   63    0     1  Sim             98%  Sim (via Fdr PT-PCdoB-PV)
  UNIÃO             50    42   27   15     0  Sim             64%  (none listed)
  PSD               48    39   33    5     1  Sim             85%  (none listed)
  PP                47    36   27    9     0  Sim             75%  (none listed)
  REPUBLICANOS      43    35   29    6     0  Sim             83%  (none listed)
  MDB               38    29   11   17     1  Não             59%  (none listed)
  PODE              27    24   20    4     0  Sim             83%  (none listed)
  PSB               17    16   15    1     0  Sim             94%  Sim
  PSDB              17    15   14    1     0  Sim             93%  (none listed)
  PSOL              13    13   13    0     0  Sim            100%  Sim (via Fdr PSOL-REDE)
  PCdoB             10    10   10    0     0  Sim            100%  Sim (via Fdr PT-PCdoB-PV)
  PDT                9     7    7    0     0  Sim            100%  Sim
  PV                 6     6    6    0     0  Sim            100%  Sim (via Fdr PT-PCdoB-PV)
  NOVO               5     5    0    5     0  Não            100%  Não
  SOLIDARIEDADE      4     4    3    1     0  Sim             75%  (blank)
  AVANTE             5     4    4    0     0  Sim            100%  (blank)
  PRD                3     3    2    1     0  Sim             67%  (blank)
  REDE               3     3    3    0     0  Sim            100%  Sim (via Fdr PSOL-REDE)
  MISSÃO             1     1    0    1     0  Não            100%  (blank)
  CIDADANIA          2     1    0    1     0  Não            100%  (none listed)
  all              513   442  292  147     3  Abstenção 2, Artigo 17 1
  Sim/Não match the descricao (292/147)
  -> camara-votos-2332174-59.csv (442 rows: nome, partido, uf, voto)

calls this run: 9 (200, 200, 200, 200, 200, 200, 200, 200, 200); cache ~/.cache/camara-deputados-skill
Source: Dados Abertos da Camara dos Deputados (API v2). Seats = deputies in office today, as the API lists them; tallies, party lines and shares computed here.
Dados Abertos da Camara dos Deputados API v2, 2026-11-25 01:01 UTC
robots.txt dadosabertos.camara.leg.br: HTTP 200 text/html; charset=utf-8 (an HTML page, no robots rules: everything allowed); 6 paths x 13 agents: 78 allowed
no PL matches 'xyzzy quantum' in the last 30 days: stop
```

### 4. curl, headers and mistakes

```bash
A=https://dadosabertos.camara.leg.br/api/v2
UA='camara-deputados-skill-example/1.0 (+https://github.com/browser-use/browser-harness)'
J='Accept: application/json'
# the 3 highest-id PL bills on "inteligencia artificial" (last 30 days; blocks 1 and 3 sort every match by date), with the paging and cache headers
H=$(mktemp); V=$(mktemp); trap 'rm -f "$H" "$V"' EXIT
curl -sS --fail --compressed -A "$UA" -H "$J" -D "$H" "$A/proposicoes?keywords=inteligencia%20artificial&siglaTipo=PL&itens=3&ordem=DESC&ordenarPor=id" \
  | python3 -c 'import sys, json
for b in json.load(sys.stdin)["dados"]: print("PL %s/%s id %s presented %s: %s..." % (b["numero"], b["ano"], b["id"], b["dataApresentacao"], b["ementa"][:90]))'
tr -d '\r' < "$H" | grep -iE '^(HTTP/|(content-type|x-total-count|cache-control|retry-after):)'
tr -d '\r' < "$H" | sed -n 's/^link: //Ip' | tr ',' '\n' | grep -oE 'pagina=[0-9]+&itens=[0-9]+>; rel="(next|last)"'
sleep 1
# latest procedural step of the newest one
curl -sS --fail --compressed -A "$UA" -H "$J" "$A/proposicoes/2658843" \
  | python3 -c 'import sys, json; s = json.load(sys.stdin)["dados"]["statusProposicao"]; print("latest step:", s["dataHora"], s["siglaOrgao"], s["descricaoTramitacao"], "|", s["descricaoSituacao"])'
sleep 1
# party tally of plenary roll-call 2332174-59 (name, party, UF and vote are all this prints; rows also hold e-mail and photo URL)
curl -sS --fail --compressed -A "$UA" -H "$J" -w '%{size_download} bytes gzip, %{time_total} s\n' -o "$V" "$A/votacoes/2332174-59/votos"
python3 -c 'import sys, json, collections
v = json.load(open(sys.argv[1]))["dados"]; c = collections.defaultdict(collections.Counter)
for x in v: c[x["deputado_"]["siglaPartido"]][x["tipoVoto"]] += 1
print(len(v), "votes;", "; ".join(f"{p} {dict(k)}" for p, k in sorted(c.items(), key=lambda i: -sum(i[1].values()))[:5]), "...")' "$V"
sleep 1
# mistakes
curl -sS -A "$UA" -H 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8' -o /dev/null -w 'browser-style Accept -> HTTP %{http_code} %{content_type}\n' "$A/votacoes/2332174-59/votos"; sleep 1
curl -sS -A "$UA" -H "$J" "$A/proposicoes?siglaTipo=PL&keywords=inteligencia&itens=200" | python3 -c 'import sys, json; print("itens=200 ->", len(json.load(sys.stdin)["dados"]), "rows")'; sleep 1
curl -sS -A "$UA" -H "$J" -w ' <- foo=1, HTTP %{http_code}\n' "$A/proposicoes?siglaTipo=PL&foo=1"; sleep 1
curl -sS -A "$UA" -H "$J" -w ' <- unknown id, HTTP %{http_code}\n' "$A/proposicoes/999999999"; sleep 1
curl -sS -A "$UA" -H "$J" "$A/votacoes?idOrgao=180&ordem=DESC&ordenarPor=dataHoraRegistro&itens=1" | python3 -c 'import sys, json; v = json.load(sys.stdin)["dados"][0]; print("idOrgao=180 newest:", v["id"], v["dataHoraRegistro"])'; sleep 1
curl -sS -A "$UA" -H "$J" "$A/votacoes?ordem=DESC&ordenarPor=dataHoraRegistro&itens=100" | python3 -c 'import sys, json; v = [x for x in json.load(sys.stdin)["dados"] if x["siglaOrgao"] == "PLEN"][0]; print("siglaOrgao PLEN newest:", v["id"], v["dataHoraRegistro"])'; sleep 1
curl -sS -A "$UA" -o /dev/null -w 'robots.txt -> HTTP %{http_code} %{content_type}\n' https://dadosabertos.camara.leg.br/robots.txt
echo "Source: Dados Abertos da Camara dos Deputados (API v2), accessed $(date -u '+%d %B %Y %H:%M') UTC; tallies computed here; lists cut to the rows shown."
```

Output (re-run on 2026-11-25, 01:01 UTC; the same lines as the 23:44 UTC run on 2026-11-24 apart from the access time and the gzip size of the votes, 19,802 bytes; the first run at 23:43 had a quoting error in one Python one-liner):

```text
PL 5928/2026 id 2658843 presented 2026-11-23T15:26: Institui normas de proteção do trabalhador frente a decisões automatizadas e à vigilância ...
PL 5864/2026 id 2654170 presented 2026-11-16T14:30: Veda a criação e o uso comercial de réplicas de voz ou de imagem de pessoa natural geradas...
PL 5826/2026 id 2652995 presented 2026-11-11T18:06: Altera a Lei nº 8.078, de 11 de setembro de 1990, para vedar a utilização de sistemas de i...
HTTP/2 200
content-type: application/json
x-total-count: 105
cache-control: public, max-age=360
retry-after: 30
pagina=2&itens=3>; rel="next"
pagina=35&itens=3>; rel="last"
latest step: 2026-11-23T15:26 MESA Apresentação de Proposição | None
19802 bytes gzip, 0.805720 s
442 votes; PL {'Não': 80, 'Sim': 5}; PT {'Sim': 63, 'Artigo 17': 1}; UNIÃO {'Sim': 27, 'Não': 15}; PSD {'Sim': 33, 'Não': 5, 'Abstenção': 1}; PP {'Sim': 27, 'Não': 9} ...
browser-style Accept -> HTTP 200 application/xml
itens=200 -> 100 rows
{"status":400,"title":"Requisição inválida","detail":"Parâmetro(s) inválido(s).","instance":"foo","code":5} <- foo=1, HTTP 400
{"status":404,"title":"Recurso não encontrado","detail":"A URL passada se refere a um recurso que não existe no sistema.","instance":"https://dadosabertos.camara.leg.br/api/v2/proposicoes/999999999","code":6} <- unknown id, HTTP 404
idOrgao=180 newest: 2655570-60 2026-11-24T00:35:14
siglaOrgao PLEN newest: 2332174-62 2026-11-24T17:53:39
robots.txt -> HTTP 200 text/html; charset=utf-8
Source: Dados Abertos da Camara dos Deputados (API v2), accessed 25 November 2026 01:01 UTC; tallies computed here; lists cut to the rows shown.
```

## Fields

| Field | Value (24 Nov 2026) | Notes |
|---|---|---|
| proposicao `id` | `2658843` | stable numeric id used in every path; `ordenarPor=id` with `ordem=DESC` lists the newest first |
| `siglaTipo`, `numero`, `ano` | `PL`, `5928`, `2026` | cite as "PL 5928/2026"; `siglaTipo=XX` (unknown) returns `[]`, not an error |
| `ementa` | "Institui normas de proteção do trabalhador frente a decisões automatizadas ..." | official summary; the detail adds `keywords` (the indexing terms the search also matches) and `ementaDetalhada` (often `null`) |
| `dataApresentacao` | `2026-11-23T15:26` | Brasilia local time, no offset, no seconds |
| `statusProposicao.dataHora`, `.sequencia` | `2026-11-23T15:26`, `1` | the latest step; equals the newest row of `/tramitacoes` (block 1 checks it) |
| `statusProposicao.siglaOrgao`, `.descricaoTramitacao`, `.descricaoSituacao` | `MESA`, `Apresentação de Proposição`, `null` or `Aguardando Autorização do Despacho` | `.despacho` is the free-text order; `.regime`, `.apreciacao` (`Indefinida` until it is dispatched) |
| `urlInteiroTeor` | `https://www.camara.leg.br/proposicoesWeb/prop_mostrarintegra?codteor=3203100` | full text on www.camara.leg.br; printed, not fetched by this skill |
| votacao `id` | `2332174-59` | a string; the part before the dash was the id of the bill concerned in all 17 of the newest 100 votes that carry `uriProposicaoObjeto` and in 2332174-59's `proposicoesAfetadas`; `dataHoraRegistro` `2026-11-24T17:52:28` (Brasilia, seconds) |
| votacao `siglaOrgao`, `uriOrgao` | `PLEN`, `.../orgaos/180` | plenary; committees such as `CCJC` (2003) vote too, many of them symbolically |
| votacao `descricao`, `aprovacao` | "... Sim: 292; Não: 147; Abstenção: 2; Total: 441.", `1` | plenary roll-calls end with the official count; `aprovacao` was 1 on every "Aprovado/Aprovada ..." vote seen |
| `/votacoes/{id}` `proposicoesAfetadas`, `objetosPossiveis` | PL 1969/2022; PPP, PRLP, REQ ... | the bill affected, and the documents that may have been the object of the vote |
| votos `tipoVoto` | `Sim`, `Não`, `Abstenção`, `Obstrução`, `Artigo 17` | one row per deputy present; absent deputies are not listed |
| votos `deputado_.nome`, `.siglaPartido`, `.siglaUf` | `Gilvan da Federal`, `PL`, `ES` | party at the time of the vote; the row also holds `id`, `email` and `urlFoto` (not printed here) |
| orientacoes `siglaPartidoBloco`, `codTipoLideranca`, `orientacaoVoto` | `PL`, `P`, `Não`; `Fdr PT-PCdoB-PV`, `B`, `Sim`; `Governo`, `B`, `Sim` | `P` party, `B` bloc, federation or leadership (Governo, Oposição, Maioria, Minoria); `""` = no orientation; `Liberado` = free vote |
| `/deputados` row | `nome`, `siglaPartido`, `siglaUf`, `idLegislatura` 57 | without a date parameter: the deputies in office at the time of the request (513 on 24 Nov) |
| error body | `{"status":404,"title":"Recurso não encontrado",...,"code":6}`, `{"status":400,"title":"Requisição inválida","detail":"Parâmetro(s) inválido(s).","instance":"foo","code":5}` | JSON when `Accept: application/json` is sent |
| headers | `Content-Type: application/json`, `Link`, `X-Total-Count`, `Cache-Control: public, max-age=360` (proposicoes list) or `1800` (deputados), `retry-after: 30` on every answer, `Access-Control-Expose-Headers: Link, X-Total-Count, X-Validation-Error` | no `ETag`, no `X-RateLimit-*` |

## Gotchas

- **Send `Accept: application/json`.** A browser-style `Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8` gets HTTP 200 `application/xml` (`<xml><dados>...`), which is what opening an API URL in a tab shows. `fetch()` and curl defaults (`*/*`) happened to get JSON, but do not rely on it.
- **The search has a 30-day window by default.** The docs: "Por padrão, são retornadas todas as proposições que foram apresentadas ou tiveram alguma mudança de situação nos últimos 30 dias." So the 105 hits included 29 bills numbered before 2026 that moved recently (the first row of `itens=200` without `ordenarPor` was PL 759/2023, "Regulamenta os sistemas de Inteligência Artificial"). `ano=2026` switches the window off (110 hits). For "newest", sort by `id` (or by `dataApresentacao` yourself); `ordenarPor=dataApresentacao` is HTTP 400, the allowed fields are `id`, `codTipo`, `siglaTipo`, `numero` and `ano`.
- **`keywords` also matches the indexing terms, not just the ementa.** PL 5813/2026 (paediatric oncology) matched "inteligencia artificial" although its ementa does not say it; its `keywords` field does. Block 1 labels each hit "match: ementa" or "indexing keywords only". Accents are optional (`inteligencia` and `inteligência` both gave 105). Words separated by a space are matched as a phrase, in that order: `artificial inteligencia` gave 1 hit (PL 6708/2025, whose keywords run "Inteligência artificial, Inteligência artificial generativa") and `inteligencia dados` 0, although `inteligencia` alone gave 114. A comma separates alternatives: `inteligencia,artificial` gave 117, more than `inteligencia` (114) or `artificial` (108) alone (verifier, 23:53 UTC).
- **"Newest" PL bills are almost always at step 1.** All five newest AI bills sat at "Apresentação de Proposição" at the MESA, waiting for the dispatch to committees; `apreciacao` stays `Indefinida` until then. For bills that have moved, the latest step is `statusProposicao`; `/tramitacoes` gives the history (block 1 checks the two agree).
- **Most votes are symbolic, and their `/votos` is empty.** Of the newest 100 votes at 23:35 UTC, 60 were in the CCJC committee and 17 in the plenary; 64 read just "Aprovado o Parecer." or "Aprovado o Requerimento." and the plenary's newest (the final wording of PL 1969/2022) had 0 vote rows. The docs: "O resultado é uma lista vazia se `{id}` foi uma votação _simbólica_", but some symbolic votes list a few deputies who asked to have their position recorded, so blocks 1 and 3 treat a vote as roll-call only from `MIN_ROWS` = 20 rows (this skill's cut-off, not a Camara term). Roll-calls also happen in committees (CCJC vote 2601150-29 had 39 rows); set `ORGAO = None` / `""` to include them.
- **`idOrgao=180` lagged a day behind.** At 23:35 UTC the newest plenary vote with `idOrgao=180` was 2655570-60 (24 Nov 00:35 Brasilia), while the unfiltered list already held 7 plenary votes of event 85464 from 16:59-17:53 that day with `uriOrgao .../orgaos/180`; `idOrgao=180&dataInicio=2026-11-24` returned 0 rows and `idEvento=85464` returned all 7. The blocks fetch the newest 100 votes of every body and filter on `siglaOrgao == "PLEN"` themselves.
- **Date ranges must stay inside one calendar year, and the API does not say when they do not.** `/votacoes?dataInicio=2025-12-01&dataFim=2026-01-31` returned HTTP 200 with 1,585 votes running to 2026-07-01T15:14, past `dataFim`; the docs say "é **necessário** que as duas datas sejam de um mesmo ano". Split the range by year.
- **`Total` in the descricao leaves out `Artigo 17`.** Vote 2332174-59 had 442 rows: 292 Sim, 147 Não, 2 Abstenção and 1 `Artigo 17`; the descricao says "Total: 441". Compare your Sim/Não with the descricao (block 1 and block 3 do), and report `Artigo 17` separately rather than as a vote.
- **Vote rows carry personal contact data.** Each `deputado_` has `email` and `urlFoto` next to the name. These are public office data, but the task needs none of it; the blocks print only name, party, UF and vote, and the CSV has those 4 columns.
- **Party in a vote row is the party on that day.** `/deputados` (no date) gives today's party and the 513 deputies in office; the seats column in block 3 counts those, so a deputy who changed party after an older vote would appear under different parties in the two columns. In plenary vote 2196833-390 (2023-07-07), 133 of the 430 voters still in office had a different party in the vote row than in today's `/deputados` (for example PATRIOTA, a party no longer listed, against PL today; verifier, 23:56 UTC).
- **Orientations are given by parties, federations, blocs and leaderships.** For vote 2332174-59, PT, PCdoB and PV had no orientation of their own; "Fdr PT-PCdoB-PV" said Sim. The bloc name was truncated in the data (`Bl UniPpPsd...`, "Liberado"), so its member parties cannot be read from it; blocks 1 and 3 map only `Fdr` names, which spell out their parties, and print "(none listed)" for the rest. `orientacaoVoto` came back empty for AVANTE, PRD, SOLIDARIEDADE and MISSÃO; blocks print it as "(blank)".
- **`retry-after: 30` is on every answer.** It came on all 21 saved exploration headers and on every block 2 probe, 400 and 404 included, so it does not mean "slow down". The blocks read it only on 429 or 5xx (none was seen).
- **Paging.** `itens` is capped at 100 ("valores maiores serão ignorados"; `itens=200` gave 100 rows, no error), the default is 15. Follow `links` `rel="next"` until it is missing; `rel="last"` and `X-Total-Count` give the size (105 hits = 2 pages of 100; 513 deputies = 6 pages). `/votacoes/{id}/votos` is not paged (442 rows in one answer, about 20 KB gzip, only a `self` link).
- **Unknown parameters are errors, unknown values are not.** `foo=1` and `ordenarPor=dataApresentacao` are HTTP 400 "Parâmetro(s) inválido(s)."; `siglaTipo=XX` is HTTP 200 with `[]`; an unknown id is HTTP 404 "Recurso não encontrado".
- **Times are Brasilia local without an offset** (`2026-11-24T17:52:28`). Brazil has had no daylight saving time since 2019, so the blocks attach UTC-03:00; at 23:3x UTC the API's "today" was still 24 November.
- **The API is marked incomplete and subject to change** ("Esta versão é ainda incompleta, sujeita a mudanças"); the OpenAPI document was version 0.4.362 of 23 November 2026. `/tramitacoes` is described as provisional ("Esta representação das tramitações ainda é provisória.").
- **Tab marker.** The harness may set the tab title to a horse emoji; the blocks check the URL and the page text, not the title.

## What does not work

- **Sorting the bill search by date presented** (`ordenarPor=dataApresentacao`): HTTP 400; sort by `id` or locally.
- **`idOrgao=180` for today's plenary votes**: lagged behind the unfiltered list (see Gotchas).
- **Individual votes for symbolic votes**: `/votos` is empty or holds only the deputies who asked to be recorded.
- **Vote date ranges across two years**: silently wrong (see Gotchas).
- **Absent deputies in `/votos`**: "Não são listados parlamentares ausentes à votação."; compare with `/deputados` if you need them.
- **Not tested:** the 429 response (never provoked), the XML format beyond the probe, `/proposicoes/{id}/votacoes`, `/eventos`, the bulk files on the portal, committee roll-calls beyond one probe, the older "Dados Abertos" version linked from the docs, and anything on www.camara.leg.br.
