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
