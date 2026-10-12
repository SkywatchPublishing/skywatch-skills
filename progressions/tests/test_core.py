import datetime as dt
import json
from pathlib import Path

from zoneinfo import ZoneInfo

import pytest
import swisseph as swe
import progressions as pg

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "natal-chart" / "examples" / "chart.json"
BIRTH = ("--date", "1990-06-15", "--time", "12:00", "--geonameid", "5128581")


@pytest.fixture
def natal():
    return json.loads(EXAMPLE.read_text())


def tjd(natal, y, m, d):
    return pg.target_jd(dt.date(y, m, d), natal["meta"]["timezone"])


def test_wrapped():
    assert pg.wrapped(190.0) == pytest.approx(-170.0)
    assert pg.wrapped(-190.0) == pytest.approx(170.0)
    assert pg.wrapped(180.0) == -180.0 and pg.wrapped(-180.0) == -180.0


@pytest.mark.parametrize("day", [dt.date(2000, 4, 8), dt.date(2000, 4, 15), dt.date(2027, 6, 15)])
def test_exact_local_midnight_keeps_its_date(day):
    tz = "America/New_York"
    u = dt.datetime.combine(day, dt.time(0), tzinfo=ZoneInfo(tz)).astimezone(dt.timezone.utc)
    assert pg.jd_to_local_date(swe.julday(u.year, u.month, u.day, u.hour + u.minute / 60), tz) == day


def test_target_date_round_trip(natal):
    tz = natal["meta"]["timezone"]
    assert pg.jd_to_local_date(pg.target_jd(dt.date(2027, 6, 15), tz), tz) == dt.date(2027, 6, 15)


def test_age_and_solar_arc(natal):
    bj, t = natal["meta"]["julian_day_ut"], tjd(natal, 2027, 6, 15)
    assert (t - bj) / pg.YEAR == pytest.approx(37.0001, abs=1e-4)
    assert pg.solar_arc(bj, t) == pytest.approx(35.2991, abs=1e-3)
    sun = swe.calc_ut(pg.progressed_jd(bj, t), swe.SUN, swe.FLG_SWIEPH)[0][0]
    assert pg.body_positions(pg.progressed_jd(bj, t))["Sun"]["longitude"] == pytest.approx(sun, abs=1e-9)


def test_solar_arc_and_naibod_angles(natal):
    bj, t = natal["meta"]["julian_day_ut"], tjd(natal, 2027, 6, 15)
    sa = pg.moved_houses(natal, t, "solar-arc")
    nb = pg.moved_houses(natal, t, "naibod")
    assert sa["angles"]["mc"] == pytest.approx((natal["angles"]["mc"] + pg.solar_arc(bj, t)) % 360, abs=1e-3)
    assert pg.wrapped(nb["angles"]["mc"] - sa["angles"]["mc"]) == pytest.approx(-1.656, abs=0.01)


@pytest.mark.parametrize("method", ["solar-arc", "naibod"])
def test_identity_at_birth(natal, method):
    h = pg.moved_houses(natal, natal["meta"]["julian_day_ut"], method)
    assert abs(pg.wrapped(h["angles"]["ascendant"] - natal["angles"]["ascendant"])) < 1e-3
    assert abs(pg.wrapped(h["cusps"][1] - natal["houses"]["cusps"][1])) < 1e-3


@pytest.mark.parametrize("method", ["solar-arc", "naibod"])
def test_sidereal_identity(cast, method):
    s = cast(*BIRTH, "--zodiac", "sidereal")
    h = pg.moved_houses(s, s["meta"]["julian_day_ut"], method)
    for k in ("ascendant", "mc"):
        assert abs(pg.wrapped(h["angles"][k] - s["angles"][k])) < 2e-4
    for a, b in zip(h["cusps"], s["houses"]["cusps"]):
        assert abs(pg.wrapped(a - b)) < 2e-4


def lahiri(jd):
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    return swe.get_ayanamsa_ex_ut(jd, swe.FLG_SWIEPH)[1]


@pytest.mark.parametrize("method", ["solar-arc", "naibod"])
def test_sidereal_houses_are_tropical_less_the_ayanamsa_at_the_progressed_instant(cast, method):
    trop, sid = cast(*BIRTH), cast(*BIRTH, "--zodiac", "sidereal")
    t = tjd(trop, 2070, 6, 15)
    a, b = pg.moved_houses(trop, t, method), pg.moved_houses(sid, t, method)
    aya = lahiri(pg.progressed_jd(trop["meta"]["julian_day_ut"], t))
    for k in a["angles"]:
        assert abs(pg.wrapped(b["angles"][k] - (a["angles"][k] - aya))) < 2e-4
    for x, y in zip(b["cusps"], a["cusps"]):
        assert abs(pg.wrapped(x - (y - aya))) < 2e-4


def test_sidereal_solar_arc_mc_is_natal_mc_plus_the_sidereal_arc(cast):
    sid = cast(*BIRTH, "--zodiac", "sidereal")
    bj, t = sid["meta"]["julian_day_ut"], tjd(sid, 2070, 6, 15)
    h = pg.moved_houses(sid, t, "solar-arc")
    assert abs(pg.wrapped(h["angles"]["mc"] - sid["angles"]["mc"] - pg.solar_arc(bj, t, "sidereal_lahiri"))) < 1e-4


def whole_signs(asc):
    return [(asc // 30 * 30 + 30 * i) % 360 for i in range(12)]


@pytest.mark.parametrize("birth", [
    BIRTH + ("--houses", "whole_sign"),                                               # requested
    ("--date", "1990-06-15", "--time", "12:00", "--lat", "69.65", "--lon", "18.96"),  # natal-chart's polar fallback
])
def test_sidereal_whole_sign_cusps_start_at_the_sidereal_ascendant_sign(cast, birth):
    s = cast(*birth, "--zodiac", "sidereal")
    assert s["houses"]["system"] == "whole_sign"
    bj = s["meta"]["julian_day_ut"]
    for method in ("solar-arc", "naibod"):
        assert pg.moved_houses(s, bj, method)["cusps"] == s["houses"]["cusps"]
        for t in (tjd(s, 2027, 6, 15), tjd(s, 2051, 2, 1)):
            h = pg.moved_houses(s, t, method)
            assert h["system"] == "whole_sign"
            assert h["cusps"] == whole_signs(h["angles"]["ascendant"])


def test_polar_fallback_rebuilds_whole_sign_cusps_after_the_shift():
    h = pg.houses_from_armc(100.0, 70.0, 23.44, "placidus", 24.0)
    trop_asc = swe.houses_armc(100.0, 70.0, 23.44, b"W")[1][0]
    assert h["system"] == "whole_sign" and h["flags"] == ["polar_fallback_whole_sign"]
    assert h["angles"]["ascendant"] == pytest.approx((trop_asc - 24.0) % 360)
    assert h["cusps"] == whole_signs(h["angles"]["ascendant"])
