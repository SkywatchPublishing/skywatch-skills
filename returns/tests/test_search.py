import datetime as dt
import json
from pathlib import Path

import pytest
import swisseph as swe
import returns as rt

NATAL_JD = 2448058.1666667  # 1990-06-15 16:00 UT
ROOT = Path(__file__).resolve().parents[2]
NATAL_SCRIPT = ROOT / "natal-chart" / "scripts" / "natal_chart.py"
EXAMPLE = ROOT / "natal-chart" / "examples" / "chart.json"


def test_body_table():
    assert rt.BODIES["sun"] == ("Sun", swe.SUN)
    assert set(rt.BODIES) == {"sun", "moon", "mars", "jupiter", "saturn", "uranus", "chiron"}


def test_wrapped_difference():
    assert rt.wrapped(10.0, 350.0) == pytest.approx(20.0)
    assert rt.wrapped(350.0, 10.0) == pytest.approx(-20.0)


def test_solar_return_2027_matches_reference():
    natal_sun = swe.calc_ut(NATAL_JD, swe.SUN, swe.FLG_SWIEPH)[0][0]
    hits = rt.find_returns(swe.SUN, natal_sun, dt.date(2027, 1, 1), dt.date(2027, 12, 31))
    assert len(hits) == 1
    jd = hits[0]
    y, m, d, h = swe.revjul(jd)
    assert (y, m, d) == (2027, 6, 15) and h == pytest.approx(14.56034, abs=1e-4)
    assert abs(rt.wrapped(swe.calc_ut(jd, swe.SUN, swe.FLG_SWIEPH)[0][0], natal_sun)) < 0.001


def test_lunar_returns_in_a_year():
    natal_moon = swe.calc_ut(NATAL_JD, swe.MOON, swe.FLG_SWIEPH)[0][0]
    hits = rt.find_returns(swe.MOON, natal_moon, dt.date(2027, 1, 1), dt.date(2027, 12, 31))
    assert len(hits) in (13, 14)
    gaps = [b - a for a, b in zip(hits, hits[1:])]
    assert all(26.5 < g < 28.5 for g in gaps)


def test_mars_retrograde_year_gives_three_crossings():
    # Pick a natal Mars longitude inside Mars's 2027 retrograde loop so the loop crosses it three times.
    # Find the loop first: Mars is retrograde when its daily speed is negative.
    jd0 = swe.julday(2026, 9, 1, 0)
    speeds = [(jd0 + i, swe.calc_ut(jd0 + i, swe.MARS, swe.FLG_SWIEPH | swe.FLG_SPEED)[0]) for i in range(0, 300)]
    retro = [j for j, p in speeds if p[3] < 0]
    assert retro, "expected a Mars retrograde in the window"
    mid = retro[len(retro) // 2]
    target = swe.calc_ut(mid, swe.MARS, swe.FLG_SWIEPH)[0][0]
    hits = rt.find_returns(swe.MARS, target, dt.date(2026, 9, 1), dt.date(2027, 6, 30))
    assert len(hits) == 3


def test_precession_shift_grows_with_age():
    shift = rt.precession_shift(NATAL_JD, swe.julday(2027, 6, 15, 14.0))
    assert 0.50 < shift < 0.53  # ~37 years × ~50.3"/yr ≈ 0.517°


def test_boundary_exact_hit_at_start_recorded_once():
    start = dt.date(2027, 3, 1)
    target = swe.calc_ut(swe.julday(2027, 3, 1, 0.0), swe.SUN, swe.FLG_SWIEPH)[0][0]
    hits = rt.find_returns(swe.SUN, target, start, dt.date(2027, 3, 10))
    assert len(hits) == 1
    assert hits[0] == pytest.approx(swe.julday(2027, 3, 1, 0.0), abs=1e-6)


def test_boundary_exact_hit_at_end_recorded_once():
    end = dt.date(2027, 3, 10)
    target = swe.calc_ut(swe.julday(2027, 3, 10, 24.0), swe.SUN, swe.FLG_SWIEPH)[0][0]
    hits = rt.find_returns(swe.SUN, target, dt.date(2027, 3, 1), end)
    assert len(hits) == 1
    assert hits[0] == pytest.approx(swe.julday(2027, 3, 10, 24.0), abs=1e-6)


def test_start_equal_end_searches_that_one_day():
    day = dt.date(2027, 3, 5)
    target = swe.calc_ut(swe.julday(2027, 3, 5, 12.0), swe.MOON, swe.FLG_SWIEPH)[0][0]
    hits = rt.find_returns(swe.MOON, target, day, day)
    assert len(hits) == 1
    assert hits[0] == pytest.approx(swe.julday(2027, 3, 5, 12.0), abs=1e-6)


def test_sidereal_search_of_sidereal_natal_sun():
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    natal_sun = swe.calc_ut(NATAL_JD, swe.SUN, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)[0][0]
    hits = rt.find_returns(swe.SUN, natal_sun, dt.date(2027, 1, 1), dt.date(2027, 12, 31), sidereal=True)
    assert len(hits) == 1
    at_hit = swe.calc_ut(hits[0], swe.SUN, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)[0][0]
    assert abs(rt.wrapped(at_hit, natal_sun)) < 0.001
    tropical = rt.find_returns(swe.SUN, swe.calc_ut(NATAL_JD, swe.SUN, swe.FLG_SWIEPH)[0][0],
                               dt.date(2027, 1, 1), dt.date(2027, 12, 31))[0]
    assert 0.4 < hits[0] - tropical < 0.7  # the sidereal return lags by the ~0.5° ayanamsa drift


def test_shift_fn_moves_hit_later_by_about_13_hours():
    natal_sun = swe.calc_ut(NATAL_JD, swe.SUN, swe.FLG_SWIEPH)[0][0]
    window = (dt.date(2027, 1, 1), dt.date(2027, 12, 31))
    plain = rt.find_returns(swe.SUN, natal_sun, *window)[0]
    shifted = rt.find_returns(swe.SUN, natal_sun, *window, shift_fn=lambda jd: rt.precession_shift(NATAL_JD, jd))[0]
    assert 12.0 < (shifted - plain) * 24 < 14.0


def test_cast_return_keeps_second_occurrence_of_fall_back_hour(tmp_path):
    # 2027-11-07 06:30Z is 01:30 EST in New York, the second 01:30 of that night.
    jd = swe.julday(2027, 11, 7, 6.5)
    chart = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    out = tmp_path / "sun_return_2027-11-07.json"
    result = rt.cast_return(NATAL_SCRIPT, chart, jd, ["--geonameid", "5128581"], "America/New_York", out, "sun", [])
    meta = result["meta"]
    assert meta["datetime_local"] == "2027-11-07T01:30:00"
    assert meta["utc_offset"] == "-05:00"
    assert meta["datetime_utc"] == "2027-11-07T06:30:00Z" == meta["return_utc"]
    assert abs(meta["julian_day_ut"] - jd) * 86400 < 2


def test_consecutive_solar_returns_are_a_tropical_year_apart():
    natal_sun = swe.calc_ut(NATAL_JD, swe.SUN, swe.FLG_SWIEPH)[0][0]
    hits = rt.find_returns(swe.SUN, natal_sun, dt.date(2027, 1, 1), dt.date(2029, 12, 31))
    assert len(hits) == 3
    for a, b in zip(hits, hits[1:]):
        assert b - a == pytest.approx(365.24, abs=0.02)
