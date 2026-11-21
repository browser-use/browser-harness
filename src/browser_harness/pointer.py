"""Pointer motion and look: how the mouse travels to a click point, and the arrow drawn there.

Ported from macOS Harness (macos_harness/pointer.py): a short move is a straight spring "hop";
a long one "glides" along the best of 20 cubic candidate paths, timed by a damped spring (fast
start, soft landing). The drawn arrow stretches and tilts on a hop, turns into its path and thins
on a glide, and pulses on a press. Pure functions: no clock, no I/O. Units are CSS pixels, origin
top left, y down; angles are degrees, clockwise positive.
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
STRETCH, SQUASH, TILT_MAX, THIN_MAX, THIN_SPEED = 0.38, 0.18, 76.0, 1.5, 3000.0
FRAME = 1 / 60  # the window over which speed is measured
# Look. The arrow is a quad: tip, wing, notch, tail around the click point (macOS Harness rounds its
# corners and adds a fog; a CDP overlay quad has neither). Drawn as macOS Harness paints its inside:
# a black TINT under a white FILL, with a white RIM.
OUTLINE = ((-4.95, -5.0), (11.55, 0.7), (3.95, 4.35), (0.5, 12.3))
FILL, RIM, TINT = 0.16, 0.8, 0.37
_ALPHA = TINT + FILL * (1 - TINT)  # white FILL over black TINT, as one colour
COLOR = {"r": round(255 * FILL / _ALPHA), "g": round(255 * FILL / _ALPHA), "b": round(255 * FILL / _ALPHA), "a": round(_ALPHA, 3)}
RIM_COLOR = {"r": 255, "g": 255, "b": 255, "a": RIM}
IDLE = 30.0  # seconds without a move until the drawn arrow is hidden, as in macOS Harness
SIZE = 1.4  # CSS pixels per macOS point: the live view shows the page scaled down
PIVOT, PRESS_ANCHOR = (1.4, 2.0), (-2.7, -2.7)  # centre of turn and stretch; centre of the press
REST = (0.0, 1.0, 1.0, 0.0)  # (a, sx, sy, b): draw as rotate(a) scale(sx, sy) rotate(b) about PIVOT
# Press pulse: the scale by seconds since the press.
PRESS = ((0.0, 1.0), (0.025, 0.971), (0.05, 0.913), (0.075, 0.881), (0.1, 0.887), (0.15, 0.933),
         (0.2, 0.972), (0.25, 0.992), (0.3, 1.0))
U_ANGLE = math.degrees(math.atan2(U[1], U[0]))
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


def tangent(curve: Curve, t: float) -> Point:
    p0, c1, c2, p3 = curve
    a = 1 - t
    return tuple(  # type: ignore[return-value]
        3 * a * a * (c1[i] - p0[i]) + 6 * a * t * (c2[i] - c1[i]) + 3 * t * t * (p3[i] - c2[i])
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


def pose(move: dict, t: float) -> tuple[float, float, float, float]:
    """The arrow's shape (a, sx, sy, b) at time t. A hop stretches along its travel and tilts.
    A glide turns into its path and thins at speed. At rest: REST."""
    if t >= move["duration"] or move["mode"] == "still":
        return REST
    if move["mode"] == "hop":
        dx, dy = toward(move["start"], move["end"])
        p = clamp(spring(t, move["response"], move["damping"]))
        e = min(1, p / 0.22) * (1 - p) ** 0.62  # rises fast, falls to 0 on arrival
        axis = math.degrees(math.atan2(dy, dx))
        axis = axis - 180 if axis > 90 else axis + 180 if axis < -90 else axis
        tilt = clamp(0.75 * dx - 0.62 * dy, -1, 1) * TILT_MAX * e
        return (axis, 1 + STRETCH * e, 1 - SQUASH * e, tilt - axis)
    q = clamp(spring(t, move["response"], move["damping"])) * len(move["path"])
    i = min(int(q), len(move["path"]) - 1)
    heading, turn = tangent(move["path"][i], q - i), 0.0
    if math.hypot(*heading) >= 0.001:  # a handle pulled back to nothing has no direction
        turn = (math.degrees(math.atan2(heading[1], heading[0])) - U_ANGLE + 180) % 360 - 180
    t0, t1 = max(t - FRAME / 2, 0), t + FRAME / 2
    speed = math.dist(position(move, t0), position(move, t1)) / (t1 - t0)
    return (turn + U_ANGLE, 1.0, 1 / (1 + THIN_MAX * clamp(speed / THIN_SPEED)), -U_ANGLE)


def press_scale(t: float) -> float:
    """The arrow's scale t seconds after a press: linear between the PRESS rows."""
    for (k0, v0), (k1, v1) in zip(PRESS, PRESS[1:]):
        if t < k1:
            return v0 + (v1 - v0) * clamp((t - k0) / (k1 - k0))
    return PRESS[-1][1]


def arrow(x: float, y: float, shape: tuple = REST, press: float = 1.0, dpr: float = 1.0) -> list[float]:
    """The arrow's quad for Overlay.highlightQuad, [x1, y1, ... x4, y4], with its click point at CSS
    (x, y): each corner pressed about PRESS_ANCHOR, then posed about PIVOT, then scaled by SIZE.
    Divided by the devicePixelRatio: Chrome draws a quad unit as dpr CSS pixels (measured on cloud
    browsers at dpr 2 and 1.25)."""
    a, sx, sy, b = shape

    def turn(p: Point, deg: float) -> Point:
        c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
        return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)

    quad = []
    for corner in OUTLINE:
        p = add(PRESS_ANCHOR, add(corner, PRESS_ANCHOR, -1), press)
        p = turn(add(p, PIVOT, -1), b)
        p = add(PIVOT, turn((p[0] * sx, p[1] * sy), a))
        quad += [round((x + SIZE * p[0]) / dpr, 2), round((y + SIZE * p[1]) / dpr, 2)]
    return quad


def moves(start: Point, end: Point, bounds: Bounds, rng: random.Random | None = None) -> list[tuple[float, float, float]]:
    """The mouseMoved events of one move as (seconds from the start, x, y)."""
    return [(t, x, y) for t, x, y, _ in samples(start, end, bounds, rng)]


def samples(start: Point, end: Point, bounds: Bounds, rng: random.Random | None = None) -> list[tuple]:
    """The mouseMoved events of one move as (seconds from the start, x, y, arrow shape): 25-45 points sampled
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
        out.append((f * travel, clamp(x, bounds[0], bounds[2]), clamp(y, bounds[1], bounds[3]), pose(move, f * move["arrive"])))
    out[-1] = (travel, end[0], end[1], REST)
    return out
