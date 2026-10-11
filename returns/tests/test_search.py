import datetime as dt
import pytest
import swisseph as swe
import returns as rt

NATAL_JD = 2448058.1666667  # 1990-06-15 16:00 UT


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
