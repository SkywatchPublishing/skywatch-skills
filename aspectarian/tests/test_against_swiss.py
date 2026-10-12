"""Optional cross-check against the Swiss Ephemeris.

The skill never imports swisseph; this test does, as an independent oracle, and is skipped
when pyswisseph is not installed. With the Swiss data files that natal-chart fetches
(natal-chart/ephe/) the two agree to hundredths of an arcsecond; without them pyswisseph
falls back to its Moshier ephemeris, good to about two arcseconds for the Moon, and the
tolerances widen to match.
"""
from pathlib import Path

import numpy as np
import pytest

import aspectarian as A

swe = pytest.importorskip("swisseph")

SWISS_FILES = Path(__file__).resolve().parents[2] / "natal-chart" / "ephe"
HAVE_FILES = (SWISS_FILES / "sepl_18.se1").exists() and (SWISS_FILES / "semo_18.se1").exists()
FLAG = swe.FLG_SWIEPH if HAVE_FILES else swe.FLG_MOSEPH
MAX_ARCSEC = 0.05 if HAVE_FILES else 3.0
MAX_SECONDS = 1.0 if HAVE_FILES else 10.0
IDS = {"Moon": swe.MOON, "Sun": swe.SUN, "Mercury": swe.MERCURY, "Venus": swe.VENUS, "Mars": swe.MARS,
       "Jupiter": swe.JUPITER, "Saturn": swe.SATURN, "Uranus": swe.URANUS, "Neptune": swe.NEPTUNE,
       "Pluto": swe.PLUTO}


class SwissSky(A.Sky):
    """Same search, Swiss Ephemeris positions. swe.calc takes Terrestrial Time, like Sky."""

    def __init__(self, ts):
        self.ts = ts

    def longitudes(self, jd_tt, names):
        jds = np.atleast_1d(jd_tt)
        out = {n: np.array([swe.calc(j, IDS[n], FLAG)[0][0] for j in jds]) for n in names}
        return out if np.ndim(jd_tt) else {n: float(v[0]) for n, v in out.items()}


@pytest.fixture(scope="module")
def swiss(sky):
    if HAVE_FILES:
        swe.set_ephe_path(str(SWISS_FILES))
    return SwissSky(sky.ts)


def test_positions_agree_through_2026(sky, swiss):
    jds = np.arange(sky.ts.utc(2026, 1, 1).tt, sky.ts.utc(2027, 1, 1).tt, 7 / 24)
    names = list(A.BODIES)
    a, b = sky.longitudes(jds, names), swiss.longitudes(jds, names)
    for n in names:
        assert np.max(np.abs(A.wrap180(a[n] - b[n]))) * 3600 < MAX_ARCSEC, n


def test_april_2026_events_agree(sky, swiss):
    start, end = sky.ts.utc(2026, 3, 27).tt, sky.ts.utc(2026, 5, 5).tt
    names = list(A.BODIES)
    ours, ours_in = A.search(sky, start, end, names)
    theirs, theirs_in = A.search(swiss, start, end, names)
    assert [e[1:] for e in ours] == [e[1:] for e in theirs]
    # The Moon moves fast enough that a position difference is a few seconds at most.
    moon = [(x, y) for x, y in zip(ours, theirs) if x.body1 == "Moon"]
    assert max(abs(x.jd - y.jd) for x, y in moon) * 86400 < MAX_SECONDS
    # Two slow bodies can take minutes to close an arcsecond, so judge those by angle: at the
    # Swiss moment of exactness our separation is exact to within the position tolerance.
    for y in theirs:
        pos = sky.longitudes(y.jd, [y.body1, y.body2])
        sep = pos[y.body1] - pos[y.body2]
        residual = min(abs(A.wrap180(sep - t)) for t in A.targets(A.ASPECTS[y.aspect]))
        assert residual * 3600 < MAX_ARCSEC, y
    assert [i.sign for i in ours_in] == [i.sign for i in theirs_in]
    assert max(abs(x.jd - y.jd) for x, y in zip(ours_in, theirs_in)) * 86400 < MAX_SECONDS
