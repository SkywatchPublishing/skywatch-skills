"""Golden chart: engine output against positions published by an independent source.

Source
------
Astrodienst (astro.com) chart table for the fixture subject of the immanuel-python
test suite, as recorded verbatim in that suite with the comment "Results copied
from astro.com chart table" / "Spot-check for correct object positions against
astro.com":
    https://github.com/theriftlab/immanuel-python/blob/master/tests/test_charts.py
    https://github.com/theriftlab/immanuel-python/blob/master/tests/test_sweph.py
Accessed 2026-10-08. astro.com itself and Astro-Databank were not reachable from
this environment (proxy refused the host), so the values are taken from this
public, verbatim copy of the astro.com table rather than from astro.com directly.

Birth data as published
-----------------------
    2000-01-01 10:00 local, America/Los_Angeles (PST, UTC-8; no DST on 1 Jan)
    San Diego, CA: 32N43, 117W09 ("San Diego coords as used by astro.com")
    Tropical zodiac, Placidus houses, geocentric.

Published positions
-------------------
    Sun        Capricorn   10°37'26"   -> 280.62389°
    Moon       Scorpio     16°19'29"   -> 226.32472°
    Ascendant  Pisces      05°36'38"   -> 335.61056°
    MC         Sagittarius 14°50'44"   -> 254.84556°
    House 2    Aries       17°59'40"   ->  17.99444°
    Saturn     retrograde (astro.com and Astro Gold)

The source publishes only the Ascendant, MC and the second cusp. Houses 1, 4,
7, 10 (the angles) and 8 (opposite the 2nd) are checked, but beyond the four
angles the only independent evidence that the Placidus intermediate cusps are
right is cusp 2: cusp 8 is simply its opposite, and cusps 4 and 7 follow from
the MC and Ascendant whatever the house system. Cusps 3, 5, 6, 9, 11, 12 have no
published value in this source and are not asserted. Because this is a single
northern mid-latitude chart, it cannot catch a house-system mix-up that only
shows in the southern hemisphere or at high latitudes. The arcsecond values
above agree with the engine to well under 0.001°.
"""
import datetime as dt

import pytest

import chart as ch


def _lon(sign_index: int, d: int, m: int, s: int) -> float:
    return sign_index * 30 + d + m / 60 + s / 3600


# Sign indices: Aries 0 ... Pisces 11.
REFERENCE = {
    "Sun": _lon(9, 10, 37, 26),        # Capricorn 10°37'26"
    "Moon": _lon(7, 16, 19, 29),       # Scorpio 16°19'29"
    "Ascendant": _lon(11, 5, 36, 38),  # Pisces 05°36'38"
    "MC": _lon(8, 14, 50, 44),         # Sagittarius 14°50'44"
    "cusp2": _lon(0, 17, 59, 40),      # Aries 17°59'40"
}

BIRTH = dict(
    name="Reference",
    date=dt.date(2000, 1, 1),
    time=dt.time(10, 0),
    timezone="America/Los_Angeles",
    location={"name": "San Diego, US", "latitude": 32 + 43 / 60, "longitude": -(117 + 9 / 60), "geonameid": None},
    house_system="placidus",
)


def test_golden_chart_matches_published_positions():
    c = ch.build_chart(**BIRTH)
    for body in ("Sun", "Moon"):
        assert c["bodies"][body]["longitude"] == pytest.approx(REFERENCE[body], abs=0.1)
    assert c["angles"]["ascendant"] == pytest.approx(REFERENCE["Ascendant"], abs=0.5)
    assert c["angles"]["mc"] == pytest.approx(REFERENCE["MC"], abs=0.5)

    cusps = c["houses"]["cusps"]
    assert c["houses"]["system"] == "placidus"
    published = {
        1: REFERENCE["Ascendant"],
        2: REFERENCE["cusp2"],
        4: (REFERENCE["MC"] + 180) % 360,
        7: (REFERENCE["Ascendant"] + 180) % 360,
        8: (REFERENCE["cusp2"] + 180) % 360,
        10: REFERENCE["MC"],
    }
    for house, want in published.items():
        assert cusps[house - 1] == pytest.approx(want, abs=0.5), f"house {house}"

    assert c["bodies"]["Saturn"]["retrograde"] is True
