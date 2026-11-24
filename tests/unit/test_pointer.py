import math
import random

import pytest

from browser_harness import pointer

VIEW = (0.0, 0.0, 1280.0, 720.0)


def test_a_short_move_hops_and_a_long_one_glides():
    assert pointer.plan((100, 100), (100 + pointer.HOP_MAX, 100), VIEW)["mode"] == "hop"
    assert pointer.plan((100, 100), (101 + pointer.HOP_MAX, 100), VIEW)["mode"] == "glide"
    assert pointer.plan((100, 100), (100.2, 100), VIEW)["mode"] == "still"


def test_moves_start_at_the_pointer_and_end_exactly_on_the_target():
    rng = random.Random(7)
    for start, end in [((100, 100), (160, 140)), ((50, 600), (1200, 80)), ((1250, 700), (30, 30))]:
        path = pointer.moves(start, end, VIEW, rng)
        assert pointer.MOVES[0] <= len(path) <= pointer.MOVES[1]
        assert path[-1][1:] == end
        # the first event lies on the way out of start: closer to it than to the target
        assert math.dist(path[0][1:], start) < math.dist(path[0][1:], end)
        assert all(VIEW[0] <= x <= VIEW[2] and VIEW[1] <= y <= VIEW[3] for _, x, y in path)


def test_moves_take_the_springs_natural_travel_time_in_rising_steps():
    for end in [(200, 150), (1100, 650)]:
        move = pointer.plan((100, 100), end, VIEW)
        path = pointer.moves((100, 100), end, VIEW, random.Random(1))
        times = [t for t, _, _ in path]
        assert times == sorted(times) and all(b > a for a, b in zip(times, times[1:]))
        assert times[-1] == max(move["arrive"], len(path) * pointer.MIN_GAP)
        assert 0.1 < move["arrive"] < 1.0  # a hop ~0.17 s, a long glide ~0.6 s
        assert times[-1] < 0.8


def test_a_hop_keeps_its_moves_apart_and_its_shape():
    path = pointer.moves((100, 100), (250, 160), VIEW, random.Random(2))
    assert len(path) == pointer.MOVES[0] and path[-1][0] == pointer.MOVES[0] * pointer.MIN_GAP
    # a straight hop stays on the line from start to end
    assert all(abs((x - 100) * 60 - (y - 100) * 150) / math.dist((100, 100), (250, 160)) < 1e-6 for _, x, y in path)


def test_a_glide_follows_its_curve_not_the_straight_line():
    path = pointer.moves((100, 600), (1100, 100), VIEW, random.Random(3))
    (x0, y0), (x1, y1) = (100, 600), (1100, 100)
    off = max(abs((y1 - y0) * x - (x1 - x0) * y + x1 * y0 - y1 * x0) / math.dist((x0, y0), (x1, y1)) for _, x, y in path)
    assert off > 20


def test_no_moves_when_already_there():
    assert pointer.moves((10, 10), (10, 10), VIEW) == []


def test_the_arrow_at_rest_is_the_macos_outline_around_the_click_point():
    quad = pointer.arrow(100, 50)
    want = [c for x, y in pointer.OUTLINE for c in (100 + pointer.SIZE * x, 50 + pointer.SIZE * y)]
    assert quad == pytest.approx(want, abs=0.01)
    # Chrome draws a quad unit as devicePixelRatio CSS pixels
    assert pointer.arrow(100, 50, dpr=2) == pytest.approx([c / 2 for c in quad], abs=0.01)


def test_a_press_pulses_the_arrow_smaller_and_back():
    assert pointer.press_scale(0) == 1 and pointer.press_scale(0.3) == 1 and pointer.press_scale(5) == 1
    assert pointer.press_scale(0.075) == pytest.approx(0.881) == min(pointer.press_scale(k / 200) for k in range(61))

    def area(q):
        return abs(sum(q[i] * q[(i + 3) % 8] - q[(i + 2) % 8] * q[i + 1] for i in range(0, 8, 2))) / 2
    assert area(pointer.arrow(0, 0, press=0.881)) == pytest.approx(0.881 ** 2 * area(pointer.arrow(0, 0)), rel=1e-3)


def test_the_drawn_arrow_stretches_on_a_hop_turns_on_a_glide_and_lands_at_rest():
    hop = pointer.samples((100, 100), (250, 160), VIEW, random.Random(4))
    glide = pointer.samples((100, 600), (1100, 100), VIEW, random.Random(4))
    assert hop[-1][3] == glide[-1][3] == pointer.REST
    assert max(s[3][1] for s in hop) > 1.1  # stretched along its travel
    assert any(abs(s[3][0] - pointer.U_ANGLE) > 20 for s in glide)  # turned into its path
    assert min(s[3][2] for s in glide) < 0.8  # thinned at speed
    assert [s[:3] for s in glide] == pointer.moves((100, 600), (1100, 100), VIEW, random.Random(4))
