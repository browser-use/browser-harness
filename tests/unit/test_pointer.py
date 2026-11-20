import math
import random

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
