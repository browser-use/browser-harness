# Lichess - Daily Puzzle: Position, Solution, Rating, Themes (HTML page)

Field-tested against lichess.org on 2026-11-08 using fresh Browser Use cloud browsers (logged out) plus `curl`. All loads of `/training/daily` and its same-origin HTML re-read were serial with 2 s or more between them: HTTP 200, no 429, no CAPTCHA, no Cloudflare challenge, no `cf_clearance` cookie set. Player pages (`/@/<user>`) are different: see "What does not work".

robots.txt (lichess.org/robots.txt, read 2026-11-08): one `User-agent: *` group, `Allow: /`, disallows `/game/`, `/@/*/download`, `/games/export/`, `/api/`, `/opening/config/`, `/study/search`, `/study/embed/`, `/embed/`, `/video?*`, `/training/of-player`, then allows `/game/export/gif/thumbnail/`; no named AI-agent groups, so the `*` group applies to all of them. So `/api/puzzle/daily` is off limits here and the block reads only `/training/daily`. Terms (Terms of Service, last modified 01 August 2026): no scraping, bot or AI/ML clause; "You can use our services for your own personal or commercial use, such as in your own applications, projects, research, or products", subject to "reasonable caps, limits"; the fair play rules ban computer help in your own games, so never use this skill during a live game.

## Quick summary

- **Daily puzzle:** `https://lichess.org/training/daily` renders from a `<script id="page-init-data">` JSON block that the puzzle app removes after it boots. Block 1 loads the page, then reads the same URL's HTML once more from inside the tab (`fetch`, same origin, no cookies) and parses that block: puzzle `id`, `rating`, `plays`, `solution` (UCI), `themes`, `initialPly`, and the source game (`id`, players with ratings, `perf`, `clock`, `pgn` up to the puzzle).
- **No FEN in the page data.** The position is the game's `pgn` replayed to the end (`initialPly + 1` plies). Block 1 carries a ~175-line stdlib chess board (no install) that replays SAN, prints the FEN and turns the UCI solution into SAN. It matched python-chess on 300 random games (25,144 plies: legal moves, SAN, FEN), and block 1 also checks it against the board lichess drew (`cg-board piece` elements carry their square in `el.cgKey`).
- **No player pages.** `/@/<user>` serves a Cloudflare "Just a moment..." challenge to a fresh browser, so this skill does not read player ratings or games.
- **Pace:** serial, 2 s after each request. The lichess API docs (lichess-org/api spec, "Rate limiting") say "Only make one request at a time" and to wait about a minute after a 429; the block keeps pages to one at a time and stops on any challenge page or non-200 HTML read.

## What works

### 1. Today's daily puzzle: position (FEN), solution, rating, plays, themes, source game (browser)

Self-contained. Prints the puzzle and its solution for the agent; the solution is a spoiler, so pass it on to the user only when they ask for it.

```python
import json, re, time

PAUSE = 2.0   # seconds after each lichess.org request, all serial (lichess API docs: "Only make one request at a time")
DAILY = "https://lichess.org/training/daily"

def open_lichess(url):
    """Load a lichess.org page in the attached tab (first call opens a new tab) and stop on any challenge."""
    try:
        here = js("location.origin") == "https://lichess.org"
    except Exception:
        here = False
    (goto_url if here else new_tab)(url)
    wait_for_load()
    time.sleep(PAUSE)
    title = (js("document.title") or "").lower()
    if any(s in title for s in ("just a moment", "attention required", "access denied", "too many requests")):
        raise SystemExit(f"challenge or block page on {js('location.href')}: stop and back off, do not retry around it")

# The page renders from <script id="page-init-data">, which the puzzle app removes once it boots, so read the
# same URL's HTML once more from inside the tab (same origin, no cookies) and parse that block.
# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = r"""(() => { window.__li = window.__li || {}; const id = String(Math.random()).slice(2); window.__li[id] = null;
  fetch(%s, {credentials: 'omit'}).then(async r => { const t = await r.text();
    const m = t.match(/<script[^>]*id="page-init-data"[^>]*>([\s\S]*?)<\/script>/);
    window.__li[id] = {status: r.status, init: m ? m[1] : null}; })
  .catch(e => { window.__li[id] = {status: 0, init: null, error: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__li[%s]; if (v) delete window.__li[%s]; return v; })()"""

def page_init(path, timeout=60):
    rid = json.dumps(js(START_JS % json.dumps(path)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > timeout:
            raise RuntimeError(f"{path}: no answer after {timeout}s; stopping")
        time.sleep(0.3)
    time.sleep(PAUSE)
    if r["status"] != 200 or not r["init"]:
        raise RuntimeError(f"{path}: HTTP {r['status']}, page-init-data {'found' if r['init'] else 'missing'} {r.get('error', '')}; stopping")
    return json.loads(r["init"])

# ---- minimal chess board: replays the game's SAN moves to get the puzzle FEN, turns the UCI solution into SAN ----
FILES = "abcdefgh"
KNIGHT = [(1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2)]
KING = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
LINES = {"b": [(1, 1), (1, -1), (-1, 1), (-1, -1)], "r": [(1, 0), (-1, 0), (0, 1), (0, -1)]}
LINES["q"] = LINES["b"] + LINES["r"]

def sq(name):
    return FILES.index(name[0]) + 8 * (int(name[1]) - 1)

def sqname(i):
    return FILES[i % 8] + str(i // 8 + 1)

def white(p):
    return p.isupper()

class Board:
    def __init__(self):
        back = "RNBQKBNR"
        self.b = [None] * 64
        for f in range(8):
            self.b[f], self.b[8 + f], self.b[48 + f], self.b[56 + f] = back[f], "P", "p", back[f].lower()
        self.turn_white, self.castling, self.ep, self.half, self.full = True, set("KQkq"), None, 0, 1

    def copy(self):
        c = Board.__new__(Board)
        c.b, c.turn_white, c.castling, c.ep, c.half, c.full = self.b[:], self.turn_white, set(self.castling), self.ep, self.half, self.full
        return c

    def attacks(self, i):
        """Squares the piece on i attacks (pawns: diagonal captures only)."""
        p, f, r = self.b[i], i % 8, i // 8
        kind, out = p.lower(), []
        if kind == "p":
            d = 1 if white(p) else -1
            return [(r + d) * 8 + f + df for df in (-1, 1) if 0 <= f + df < 8 and 0 <= r + d < 8]
        if kind in "nk":
            for df, dr in (KNIGHT if kind == "n" else KING):
                if 0 <= f + df < 8 and 0 <= r + dr < 8:
                    out.append((r + dr) * 8 + f + df)
            return out
        for df, dr in LINES[kind]:
            ff, rr = f + df, r + dr
            while 0 <= ff < 8 and 0 <= rr < 8:
                out.append(rr * 8 + ff)
                if self.b[rr * 8 + ff]:
                    break
                ff, rr = ff + df, rr + dr
        return out

    def in_check(self, white_king):
        k = self.b.index("K" if white_king else "k")
        return any(p and white(p) != white_king and k in self.attacks(i) for i, p in enumerate(self.b))

    def pseudo(self):
        """(from, to, promo) for the side to move; castling only when the path is empty, checks tested in legal()."""
        out = []
        for i, p in enumerate(self.b):
            if not p or white(p) != self.turn_white:
                continue
            if p.lower() == "p":
                d, f, r = (8 if white(p) else -8), i % 8, i // 8
                last = 7 if white(p) else 0
                targets = [t for t in self.attacks(i) if (self.b[t] and white(self.b[t]) != white(p)) or t == self.ep]
                if not self.b[i + d]:
                    targets.append(i + d)
                    if r == (1 if white(p) else 6) and not self.b[i + 2 * d]:
                        targets.append(i + 2 * d)
                for t in targets:
                    out += [(i, t, q) for q in "qrbn"] if t // 8 == last else [(i, t, None)]
            else:
                out += [(i, t, None) for t in self.attacks(i) if not self.b[t] or white(self.b[t]) != white(p)]
                if p.lower() == "k" and i == (4 if white(p) else 60):
                    for side, rook, path in (("K", 7, [5, 6]), ("Q", 0, [1, 2, 3])):
                        right = side if white(p) else side.lower()
                        if right in self.castling and all(not self.b[i - 4 + s] for s in path):
                            out.append((i, i + (2 if side == "K" else -2), None))
        return out

    def legal(self):
        res = []
        for m in self.pseudo():
            fr, to, _ = m
            if self.b[fr].lower() == "k" and abs(to - fr) == 2:   # castling: not out of, through or into check
                mid = (fr + to) // 2
                if self.in_check(self.turn_white) or \
                   any(mid in self.attacks(i) for i, p in enumerate(self.b) if p and white(p) != self.turn_white):
                    continue
            if not self.push(m).in_check(self.turn_white):
                res.append(m)
        return res

    def push(self, m):
        fr, to, promo = m
        n, p = self.copy(), self.b[fr]
        capture = self.b[to] is not None
        if p.lower() == "p" and to == self.ep:
            n.b[to + (-8 if white(p) else 8)] = None
            capture = True
        if p.lower() == "k" and abs(to - fr) == 2:
            rf, rt = (fr + 3, fr + 1) if to > fr else (fr - 4, fr - 1)
            n.b[rt], n.b[rf] = n.b[rf], None
        n.b[to], n.b[fr] = (promo.upper() if white(p) else promo) if promo else p, None
        if p.lower() == "k":
            n.castling -= {"K", "Q"} if white(p) else {"k", "q"}
        for corner, right in ((0, "Q"), (7, "K"), (56, "q"), (63, "k")):
            if corner in (fr, to):
                n.castling.discard(right)
        n.ep = (fr + to) // 2 if p.lower() == "p" and abs(to - fr) == 16 else None
        n.half = 0 if p.lower() == "p" or capture else self.half + 1
        n.full = self.full + (0 if self.turn_white else 1)
        n.turn_white = not self.turn_white
        return n

    def san(self, m):
        fr, to, promo = m
        p = self.b[fr]
        if p.lower() == "k" and abs(to - fr) == 2:
            s = "O-O" if to > fr else "O-O-O"
        else:
            capture = self.b[to] is not None or (p.lower() == "p" and to == self.ep)
            if p.lower() == "p":
                s = (FILES[fr % 8] + "x" if capture else "") + sqname(to) + ("=" + promo.upper() if promo else "")
            else:
                rivals = [o for o, t, _ in self.legal() if t == to and o != fr and self.b[o] == p]
                dis = ""
                if rivals:
                    if all(o % 8 != fr % 8 for o in rivals):
                        dis = FILES[fr % 8]
                    elif all(o // 8 != fr // 8 for o in rivals):
                        dis = str(fr // 8 + 1)
                    else:
                        dis = sqname(fr)
                s = p.upper() + dis + ("x" if capture else "") + sqname(to)
        n = self.push(m)
        if n.in_check(n.turn_white):
            s += "#" if not n.legal() else "+"
        return s

    def push_san(self, san):
        want = san.rstrip("+#!?")
        if want in ("O-O", "O-O-O"):
            cands = [m for m in self.legal() if self.b[m[0]].lower() == "k" and abs(m[1] - m[0]) == 2 and (m[1] > m[0]) == (want == "O-O")]
        else:
            g = re.fullmatch(r"([NBRQK])?([a-h])?([1-8])?x?([a-h][1-8])(?:=?([QRBN]))?", want)
            if not g:
                raise ValueError(f"unreadable SAN {san!r}")
            piece, df, dr, to, promo = g.groups()
            cands = [m for m in self.legal() if m[1] == sq(to) and self.b[m[0]].upper() == (piece or "P")
                     and m[2] == (promo.lower() if promo else None)
                     and (not df or FILES[m[0] % 8] == df) and (not dr or str(m[0] // 8 + 1) == dr)]
        if len(cands) != 1:
            raise ValueError(f"SAN {san!r} matches {len(cands)} legal moves")
        return self.push(cands[0])

    def push_uci(self, uci):
        m = (sq(uci[:2]), sq(uci[2:4]), uci[4:] or None)
        if m not in self.legal():
            raise ValueError(f"illegal UCI {uci!r}")
        return self.push(m)

    def fen(self):
        rows = []
        for r in range(7, -1, -1):
            row, gap = "", 0
            for f in range(8):
                p = self.b[r * 8 + f]
                if p:
                    row, gap = row + (str(gap) if gap else "") + p, 0
                else:
                    gap += 1
            rows.append(row + (str(gap) if gap else ""))
        ep = "-"   # like lichess / python-chess: only when an en passant capture is actually legal
        if self.ep is not None and any(m[1] == self.ep and self.b[m[0]].lower() == "p" for m in self.legal()):
            ep = sqname(self.ep)
        castle = "".join(c for c in "KQkq" if c in self.castling) or "-"
        return f"{'/'.join(rows)} {'w' if self.turn_white else 'b'} {castle} {ep} {self.half} {self.full}"

# ---- the task ----
open_lichess(DAILY)
init = page_init("/training/daily")["data"]
pz, game = init["puzzle"], init["game"]
moves = game["pgn"].split()
if len(moves) != pz["initialPly"] + 1:
    raise RuntimeError(f"pgn has {len(moves)} plies, initialPly {pz['initialPly']}: puzzle format changed")

board = Board()
for san in moves:
    board = board.push_san(san)
fen = board.fen()

# Check the replay against the board lichess actually drew (chessground keeps each piece's square in el.cgKey).
drawn = js("""[...document.querySelectorAll('cg-board piece:not(.ghost)')].map(p => [p.cgKey, p.className])""")
mine = {sqname(i): ("white " if white(p) else "black ") + {"p": "pawn", "n": "knight", "b": "bishop", "r": "rook", "q": "queen", "k": "king"}[p.lower()]
        for i, p in enumerate(board.b) if p}
if {k: c for k, c in drawn} != mine:
    raise RuntimeError(f"replayed position differs from the drawn board: {sorted(set(mine.items()) ^ set(map(tuple, drawn)))}")

line, b = [], board
for u in pz["solution"]:
    m = (sq(u[:2]), sq(u[2:4]), u[4:] or None)
    line.append(b.san(m))
    b = b.push_uci(u)  # raises on an illegal move, so bad page data never prints a made-up line

to_move = "white" if board.turn_white else "black"
print(f"daily puzzle {pz['id']}  https://lichess.org/training/{pz['id']}  (read {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())})")
print(f"rating {pz['rating']} | plays {pz['plays']} | themes {pz['themes']} | isDaily {init['isDaily']}")
print(f"{to_move} to move after {moves[-1]} (ply {pz['initialPly'] + 1}); FEN {fen}")
feedback = js("(document.querySelector('.puzzle__feedback') || {}).innerText") or ""
print("page says:", " / ".join(feedback.split("\n")[:2]))   # the rest is the hint / solution buttons; never click them
print(f"solution UCI {pz['solution']}  SAN {' '.join(line)}  -> final FEN {b.fen()}")
w, bl = game["players"]
print(f"from game {game['id']} ({'rated ' if game['rated'] else ''}{game['perf']['name']} {game['clock']}): "
      f"{w['name']} ({w['rating']}) vs {bl['name']} ({bl['rating']})")
print("game moves before the puzzle:", " ".join(f"{i // 2 + 1}.{m}" if i % 2 == 0 else m for i, m in enumerate(moves)))
```

Output (from a run in a fresh cloud browser on 2026-11-08):

```text
daily puzzle pnNfB  https://lichess.org/training/pnNfB  (read 2026-11-08 23:49 UTC)
rating 2144 | plays 25768 | themes ['mateIn2', 'middlegame', 'short', 'sacrifice', 'deflection', 'bodenMate'] | isDaily True
white to move after h5 (ply 36); FEN r1bqk2r/1p1n1pb1/4p1p1/1P1pP2p/pB1P1PQP/3B1N2/1P4P1/3K3R w kq - 0 19
page says: Your turn / Find the best move for white.
solution UCI ['g4e6', 'f7e6', 'd3g6']  SAN Qxe6+ fxe6 Bxg6#  -> final FEN r1bqk2r/1p1n2b1/4p1B1/1P1pP2p/pB1P1P1P/5N2/1P4P1/3K3R b kq - 0 20
from game F3H4Ogo2 (rated Blitz 3+2): mando_emiliano (1712) vs taufikBRA (1747)
game moves before the puzzle: 1.e4 e6 2.d4 d5 3.Nd2 Nf6 4.e5 Nfd7 5.Qg4 c5 6.c3 Nc6 7.Nb3 cxd4 8.cxd4 Nb4 9.Bd2 Nc2+ 10.Kd1 Nxa1 11.Bd3 Nxb3 12.axb3 g6 13.f4 Bg7 14.Nf3 Qb6 15.b4 a5 16.b5 a4 17.Bb4 Qd8 18.h4 h5
```

## Fields

| Field | Where | Notes |
|---|---|---|
| `puzzle.id`, `.rating`, `.plays` | daily page-init-data | `https://lichess.org/training/<id>` is the puzzle's own page; the og:title says "Chess tactic #<id> - White to play" |
| `puzzle.solution[]` | daily page-init-data | UCI, solver's moves and replies alternating; the solver moves first |
| `puzzle.themes[]` | daily page-init-data | theme keys (`mateIn2`, `sacrifice`, `bodenMate`, ...); not shown on the page until the puzzle is solved |
| `puzzle.initialPly` | daily page-init-data | index of the last game move before the puzzle; `pgn` has `initialPly + 1` moves |
| `game.id`, `.perf`, `.clock`, `.rated`, `.players[]` | daily page-init-data | the finished game the puzzle came from; players carry `name`, `id`, `color`, `rating` |
| `isDaily`, `angle` | daily page-init-data | `isDaily: true` on `/training/daily` |

## Gotchas

- **Puzzle rating and plays move during the day.** Reads of the same daily puzzle on 2026-11-08: 2008 / 24,453 plays, then 2085 / 24,646 at 23:26 UTC, 2052 / 24,828 at 23:30, 1971 / 24,921 at 23:32, 1958 / 25,025 at 23:33, 1985 / 25,681 at 23:47, 2144 / 25,768 at 23:49. Print the read time with the numbers.
- **`page-init-data` is gone from the live DOM** after the puzzle app boots (`document.scripts` has no such block), which is why the block re-reads the HTML. It is the page's own URL, not an API.
- **The tab title gets a horse marker** from the harness (`🐴 Just a moment...`): match with `includes`, not `startsWith`.

## What does not work

- **Player pages `/@/<user>`:** a fresh logged-out cloud browser got a Cloudflare "Just a moment..." challenge on the first load (2 of 2 fresh browsers on 2026-11-08; `cf_clearance` cookie set only after it); `curl` gets a Cloudflare HTTP 403. `/training/daily` set no such cookie. Not worked around: no player ratings or game counts here.
- **`/api/` (daily puzzle, user, games export) and `/@/<user>/download`:** disallowed by robots.txt for every user agent. Not used.
- **Not tested:** solving the puzzle on the page (hint / solution buttons were never clicked), logged-in views, puzzle pages other than the daily one.
