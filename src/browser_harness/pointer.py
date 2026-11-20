"""Pointer motion: how the mouse travels to a click point.

Ported from macOS Harness (macos_harness/pointer.py, the drawn pointer's motion), trimmed to
the motion functions: a short move is a straight spring "hop"; a long one "glides" along the
best of 20 cubic candidate paths, timed by a damped spring (fast start, soft landing).
Pure functions: no clock, no I/O. Units are CSS pixels, origin top left, y down.
"""

from __future__ import annotations

import math
import random

Point = tuple[float, float]
Bounds = tuple[float, float, float, float]  # left, top, right, bottom
Curve = tuple[Point, Point, Point, Point]  # a cubic: start, two handles, end

HEADING = math.radians(-44.0)  # rest heading of an arrow pointer, from straight up
U = (math.sin(HEADING), -math.cos(HEADING))  # paths leave and land along U
STILL = 0.5  # closer than this: no move
HOP_MAX = 196.0  # up to this far: a straight hop; beyond: a glide along a curve
HOP = (0.24, 0.84)  # spring (response seconds, damping fraction) of a hop
GLIDE_DAMPING, SCALER, RESPONSE_MIN, RESPONSE_MAX = 0.9, 0.7, 0.12, 2.2
START_HANDLE, END_HANDLE = 0.41960295031576633, 0.15
ARC_SIZE, ARC_FLOW = 0.2765523188064277, 0.5783555327868779
ARC_SCALES, FLOW_SCALES = (0.55, 0.8, 1.05), (0.65, 1.0, 1.35)
MARGIN, SAMPLES = 20.0, 24
ARRIVED = (0.995, 3.157)  # spring progress and distance that count as arrived
TAIL_TIME = 1.4  # animation length in responses; the spring is within 0.1% by then
# Browser sampling: about one mouseMoved per frame, 25-45 of them. Akamai counts them: one click's
# path on homedepot.com validated _abck in 0/6 cloud sessions with 12 or 15 moves, 5/6 with 20, 6/6 with 30,
# at any travel time from 0.25 s to 1.5 s. A short hop is slowed so its moves stay MIN_GAP apart.
MOVE_EVERY, MIN_GAP, MOVES = 1 / 60, 0.012, (25, 45)


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def add(p: Point, v: Point, k: float = 1.0) -> Point:
    return (p[0] + v[0] * k, p[1] + v[1] * k)


def toward(p: Point, q: Point) -> Point:
    """The unit vector from p to q."""
    d = math.dist(p, q)
    return ((q[0] - p[0]) / d, (q[1] - p[1]) / d)


def spring(t: float, response: float, damping: float) -> float:
    """Step response of a damped spring released at rest: 0 at t = 0, settles at 1."""
    w = 2 * math.pi / response
    wd = w * math.sqrt(1 - damping * damping)
    swing = math.cos(wd * t) + damping * w / wd * math.sin(wd * t)
    return 1 - math.exp(-damping * w * t) * swing


def cubic(curve: Curve, t: float) -> Point:
    p0, c1, c2, p3 = curve
    a = 1 - t
    return tuple(  # type: ignore[return-value]
        p0[i] * a**3 + 3 * c1[i] * a * a * t + 3 * c2[i] * a * t * t + p3[i] * t**3
        for i in (0, 1)
    )


def reach(bounds: Bounds, p: Point, v: Point, length: float) -> Point:
    """The point `length` from p along v, pulled back so it stays inside the bounds."""
    for i in (0, 1):
        if v[i]:
            length = min(length, (bounds[i if v[i] < 0 else i + 2] - p[i]) / v[i])
    return add(p, v, max(0.0, length))


def candidates(start: Point, end: Point, bounds: Bounds) -> list[list[Curve]]:
    """20 paths, each one or two cubics. All leave start along U and reach end
    along U; no handle leaves the bounds."""
    d, along = math.dist(start, end), toward(start, end)
    hs = max(48, min(640, d * START_HANDLE, d * 0.9))
    he = max(48, min(640, d * END_HANDLE, d * 0.9))
    back = (-U[0], -U[1])

    def handles(k: float) -> tuple[Point, Point]:
        return reach(bounds, start, U, hs * k), reach(bounds, end, back, he * k)

    # One curve: with the full handles, then with shorter ones.
    paths = [[(start, *handles(k), end)] for k in (1, 0.65)]
    # Two curves through a point bowed to one side; they keep the full handles.
    leave, land = handles(1)
    normal = (-along[1], along[0])
    middle = add(((start[0] + end[0]) / 2, (start[1] + end[1]) / 2), U, hs * 0.16)
    bow, flow = clamp(d * ARC_SIZE, 50, 520), clamp(d * ARC_FLOW, 38, 440)
    for s in ARC_SCALES:
        for f in FLOW_SCALES:
            for side in (1, -1):
                arc = add(middle, normal, side * bow * s)
                into, out = add(arc, along, -flow * f), add(arc, along, flow * f)
                paths.append([(start, leave, into, arc), (arc, out, land, end)])
    return paths


def measure(path: list[Curve], bounds: Bounds) -> tuple[float, float, float, float, bool]:
    """Length, sum of turn squared, sharpest turn, sum of turns, and whether the
    path stays MARGIN inside the bounds."""
    length = energy = sharpest = turn = 0.0
    inside, prev, last = True, path[0][0], None
    for curve in path:
        for k in range(SAMPLES + 1):  # k = 0 is the start point: it counts too
            q = cubic(curve, k / SAMPLES)
            step = math.dist(prev, q)
            length += step
            inside = inside and all(
                bounds[i] + MARGIN <= q[i] <= bounds[i + 2] - MARGIN for i in (0, 1)
            )
            if step > 0.01:
                angle = math.atan2(q[1] - prev[1], q[0] - prev[0])
                if last is not None:
                    change = abs((angle - last + math.pi) % (2 * math.pi) - math.pi)
                    energy += change * change
                    sharpest = max(sharpest, change)
                    turn += change
                last = angle
            prev = q
    return length, energy, sharpest, turn, inside


def glide(start: Point, end: Point, bounds: Bounds) -> tuple[list[Curve], float]:
    """The best of the candidate paths, and its spring response."""
    d = math.dist(start, end)
    along_u = ((end[0] - start[0]) * U[0] + (end[1] - start[1]) * U[1]) / d
    against = clamp((-0.08 - along_u) / 0.92)  # how far the target is behind the arrow
    best: tuple = ((True, math.inf), [], 0.0)
    for path in candidates(start, end, bounds):
        length, energy, sharpest, turn, inside = measure(path, bounds)
        excess, arc = max(length / d - 1, 0), len(path) == 2
        bends = 140 * energy + 180 * sharpest + 18 * turn
        score = length + 320 * excess + bends + 90 * against + 45 * arc
        shape = clamp(
            0.42 * clamp(excess / 0.55)
            + 0.38 * clamp(turn / (1.4 * math.pi))
            + 0.2 * clamp(energy / 1.25)
        )
        far = clamp((length - 180) / 760)
        total = 0.42 + 0.22 * far + 0.12 * shape + 0.28 * against + 0.04 * arc
        response = SCALER * total * (0.9 if arc else 1)
        # A path that stays inside the bounds beats any that does not.
        if (not inside, score) < best[0]:
            best = ((not inside, score), path, response)
    return best[1], clamp(best[2], RESPONSE_MIN, RESPONSE_MAX)


def plan(start: Point, end: Point, bounds: Bounds) -> dict:
    """Everything a move needs, decided once: mode, path, spring, duration, and
    the time it arrives."""
    move: dict = {"mode": "still", "start": end, "end": end, "duration": 0.0, "arrive": 0.0}
    d = math.dist(start, end)
    if d < STILL:
        return move
    move.update(mode="hop", start=start, response=HOP[0], damping=HOP[1])
    if d > HOP_MAX:
        path, response = glide(start, end, bounds)
        move.update(mode="glide", path=path, response=response, damping=GLIDE_DAMPING)
    move["duration"] = TAIL_TIME * move["response"]
    t = 0.0
    while t < move["duration"] and not (
        spring(t, move["response"], move["damping"]) >= ARRIVED[0]
        and math.dist(position(move, t), end) <= ARRIVED[1]
    ):
        t += 0.001
    move["arrive"] = t
    return move


def position(move: dict, t: float) -> Point:
    """Where the pointer is at time t."""
    if t >= move["duration"]:
        return move["end"]
    p = spring(t, move["response"], move["damping"])
    if move["mode"] == "hop":
        return add(move["start"], add(move["end"], move["start"], -1), p)
    q = clamp(p) * len(move["path"])
    i = min(int(q), len(move["path"]) - 1)
    return cubic(move["path"][i], q - i)


def moves(start: Point, end: Point, bounds: Bounds, rng: random.Random | None = None) -> list[tuple[float, float, float]]:
    """The mouseMoved events of one move as (seconds from the start, x, y): 25-45 points sampled
    from the spring, intervals jittered +-25%, over its natural travel time (a hop too short for
    its points at MIN_GAP apart is slowed, keeping its shape), clamped to the bounds, the last one
    exactly on `end`. Empty when already there."""
    rng = rng or random
    move = plan(start, end, bounds)
    if move["mode"] == "still":
        return []
    n = max(MOVES[0], min(MOVES[1], round(move["arrive"] / MOVE_EVERY)))
    travel = max(move["arrive"], n * MIN_GAP)
    gaps = [rng.uniform(0.75, 1.25) for _ in range(n)]
    total, out, f = sum(gaps), [], 0.0
    for i, g in enumerate(gaps):
        f += g / total
        x, y = end if i == n - 1 else position(move, f * move["arrive"])
        out.append((f * travel, clamp(x, bounds[0], bounds[2]), clamp(y, bounds[1], bounds[3])))
    out[-1] = (travel, end[0], end[1])
    return out
