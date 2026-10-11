import math
import pytest
import wheel_geometry as g


def test_ascendant_sits_at_left():
    x, y = g.point(asc=100.0, lon=100.0, cx=0, cy=0, r=10)
    assert (x, y) == (pytest.approx(-10), pytest.approx(0))


def test_descendant_sits_at_right_and_mc_above_when_square():
    x, y = g.point(asc=100.0, lon=280.0, cx=0, cy=0, r=10)
    assert (x, y) == (pytest.approx(10), pytest.approx(0))
    x, y = g.point(asc=100.0, lon=10.0, cx=0, cy=0, r=10)   # 90 degrees before the ascendant: top of the wheel
    assert (x, y) == (pytest.approx(0), pytest.approx(-10))


def test_spread_labels_pushes_apart_close_longitudes():
    out = g.spread([10.0, 10.5, 11.0, 200.0], min_gap=4.0)
    assert out[3] == pytest.approx(200.0)
    gaps = [out[i + 1] - out[i] for i in range(2)]
    assert all(gap >= 4.0 - 1e-9 for gap in gaps)
    assert out[1] == pytest.approx(10.5)   # middle one stays, outer two move


def _circular_gaps(out: list[float]) -> list[float]:
    """Gaps between circular neighbours, walking the circle in increasing longitude."""
    vals = sorted(out)
    return [(vals[(i + 1) % len(vals)] - vals[i]) % 360.0 or 360.0 for i in range(len(vals))]


def _circular_order(values: list[float]) -> list[int]:
    """Original indices in the order they appear walking the circle, started at the smallest."""
    return sorted(range(len(values)), key=lambda i: values[i])


def _same_cyclic_order(a: list[int], b: list[int]) -> bool:
    if len(a) != len(b):
        return False
    if not a:
        return True
    k = b.index(a[0])
    return b[k:] + b[:k] == a


@pytest.mark.parametrize("lons", [[358.0, 1.0, 3.0], [359.0, 0.5], [0.0, 0.0, 0.0]])
def test_spread_respects_the_zero_aries_seam(lons):
    out = g.spread(lons, min_gap=4.0)
    assert len(out) == len(lons)
    assert all(0.0 <= v < 360.0 for v in out)
    assert all(gap >= 4.0 - 1e-9 for gap in _circular_gaps(out))
    # original order is preserved around the circle (ties may stay in input order)
    assert _same_cyclic_order(_circular_order(lons), _circular_order(out))


def test_spread_empty_and_single():
    assert g.spread([], min_gap=4.0) == []
    assert g.spread([359.5], min_gap=4.0) == [pytest.approx(359.5)]


def test_spread_degenerate_fills_the_circle_evenly():
    out = g.spread([10.0, 10.0, 10.0, 10.0], min_gap=100.0)   # 4 * 100 >= 360
    assert all(gap == pytest.approx(90.0) for gap in _circular_gaps(out))
