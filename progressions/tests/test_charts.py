import datetime as dt
import json
from pathlib import Path

from zoneinfo import ZoneInfo

import pytest
import swisseph as swe
import progressions as pg

EXAMPLE = Path(__file__).resolve().parents[2] / "natal-chart" / "examples" / "chart.json"
NY = ("--geonameid", "5128581")


@pytest.fixture
def natal():
    return json.loads(EXAMPLE.read_text())


def at(natal, y, m, d):
    return pg.target_jd(dt.date(y, m, d), natal["meta"]["timezone"])


@pytest.mark.needs_ephemeris
def test_progressed_chart_example(natal):
    p = pg.progressed_chart(natal, at(natal, 2027, 6, 15))
    assert p["schema_version"] == 1
    assert p["meta"]["chart_type"] == "secondary_progressed"
    assert p["meta"]["derived_from"] == ["Example"]
    prog = p["meta"]["progression"]
    assert prog["target_date"] == "2027-06-15" and prog["angles_method"] == "solar-arc"
    assert prog["age_years"] == pytest.approx(37.0001, abs=1e-4)
    assert prog["solar_arc"] == pytest.approx(35.2991, abs=1e-3)
    assert p["bodies"]["Sun"]["formatted"] == "29°35' Cancer"
    assert p["bodies"]["Moon"]["formatted"] == "6°48' Leo"
    assert p["meta"]["datetime_local"] == natal["meta"]["datetime_local"]
    for b in p["bodies"].values():
        assert b["house"] == pg.house_of(b["longitude"], p["houses"]["cusps"])


def test_directed_chart_moves_everything_by_the_arc(natal):
    d = pg.directed_chart(natal, at(natal, 2027, 6, 15))
    arc = d["meta"]["progression"]["solar_arc"]
    assert d["meta"]["chart_type"] == "solar_arc_directed"
    assert d["meta"]["progression"]["angles_method"] is None
    for n, b in natal["bodies"].items():
        assert abs(pg.wrapped(d["bodies"][n]["longitude"] - (b["longitude"] + arc))) < 1e-3
        assert d["bodies"][n]["house"] == b["house"]
    for k in ("ascendant", "mc"):
        assert abs(pg.wrapped(d["angles"][k] - (natal["angles"][k] + arc))) < 1e-3
    assert all(a["applying"] is None for a in d["aspects"])
    # A directed position has no daily motion (CONTRACT.md: speed is null on directed charts).
    assert all(b["speed"] is None and b["retrograde"] is False for b in d["bodies"].values())


def test_directed_whole_sign_cusps_stay_on_sign_boundaries(cast):
    w = cast("--date", "1990-06-15", "--time", "12:00", *NY, "--houses", "whole_sign")
    d = pg.directed_chart(w, at(w, 2027, 6, 15))
    start = d["angles"]["ascendant"] // 30 * 30
    assert d["houses"]["system"] == "whole_sign"
    assert d["houses"]["cusps"] == [(start + 30 * i) % 360 for i in range(12)]
    for b in d["bodies"].values():
        assert b["house"] == pg.house_of(b["longitude"], d["houses"]["cusps"])


def test_solar_arc_angles_make_progressed_mc_equal_directed_mc(natal):
    t = at(natal, 2027, 6, 15)
    assert pg.progressed_chart(natal, t)["angles"]["mc"] == pytest.approx(pg.directed_chart(natal, t)["angles"]["mc"], abs=1e-3)


@pytest.mark.needs_ephemeris          # the example's natal Chiron has no progressed counterpart without the files
def test_identity_at_birth(natal):
    bj = natal["meta"]["julian_day_ut"]
    p, d = pg.progressed_chart(natal, bj), pg.directed_chart(natal, bj)
    for n, b in natal["bodies"].items():
        assert abs(pg.wrapped(p["bodies"][n]["longitude"] - b["longitude"])) < 1e-3
        assert abs(pg.wrapped(d["bodies"][n]["longitude"] - b["longitude"])) < 1e-3
    assert d["meta"]["progression"]["solar_arc"] == pytest.approx(0.0, abs=1e-6)


def test_untimed_natal(natal):
    natal["angles"] = None; natal["houses"] = None; natal["meta"]["time_unknown"] = True
    # natal-chart's moon_range for this birth cast without a time (at noon, the example's moment).
    natal["meta"]["moon_range"] = {"start": 340.9237, "end": 354.3375}
    t = at(natal, 2027, 6, 15)
    p, d = pg.progressed_chart(natal, t), pg.directed_chart(natal, t)
    for chart in (p, d):
        assert chart["angles"] is None and chart["houses"] is None
        assert chart["meta"]["progression"]["angles_method"] is None
        assert all(b["house"] is None for b in chart["bodies"].values())
    # The range moves with the chart: recomputed for a progressed chart, the natal range plus the arc directed.
    assert p["meta"]["moon_range"]["start"] == pytest.approx(edge_moon(natal, 0, 0, t), abs=1e-4)
    assert p["meta"]["moon_range"]["end"] == pytest.approx(edge_moon(natal, 23, 59, t), abs=1e-4)
    arc = d["meta"]["progression"]["solar_arc"]
    for k in ("start", "end"):
        assert abs(pg.wrapped(p["meta"]["moon_range"][k] - natal["meta"]["moon_range"][k])) > 1
        assert abs(pg.wrapped(d["meta"]["moon_range"][k] - (natal["meta"]["moon_range"][k] + arc))) < 1e-3


def edge_moon(natal, hour, minute, tjd):
    """The progressed Moon for a birth at hour:minute local on the natal birth date."""
    meta = natal["meta"]
    local = dt.datetime.combine(dt.date.fromisoformat(meta["datetime_local"][:10]), dt.time(hour, minute),
                                tzinfo=ZoneInfo(meta["timezone"]))
    u = local.astimezone(dt.timezone.utc)
    e = swe.julday(u.year, u.month, u.day, u.hour + u.minute / 60)
    return swe.calc_ut(e + (tjd - e) / pg.YEAR, swe.MOON, swe.FLG_SWIEPH)[0][0]


def test_untimed_moon_range_moves_with_the_chart(cast):
    u = cast("--date", "1990-06-15", *NY)
    t = at(u, 2027, 6, 15)
    natal_range = u["meta"]["moon_range"]
    p = pg.progressed_chart(u, t)["meta"]["moon_range"]
    assert p["start"] == pytest.approx(edge_moon(u, 0, 0, t), abs=1e-4)
    assert p["end"] == pytest.approx(edge_moon(u, 23, 59, t), abs=1e-4)
    d = pg.directed_chart(u, t)
    arc = d["meta"]["progression"]["solar_arc"]
    for k in ("start", "end"):
        assert abs(pg.wrapped(d["meta"]["moon_range"][k] - (natal_range[k] + arc))) < 1e-3
    assert pg.progressed_chart(u, u["meta"]["julian_day_ut"])["meta"]["moon_range"]["start"] == \
        pytest.approx(natal_range["start"], abs=0.05)


def test_untimed_moon_range_on_the_birth_date(cast):
    # At local noon on the birth date a birth at 00:00 is twelve hours old, while one at 23:59 has not happened
    # yet: that edge is age 0, the natal 23:59 Moon, not a Moon progressed backwards.
    u = cast("--date", "1990-06-15", *NY)
    t = at(u, 1990, 6, 15)
    p = pg.progressed_chart(u, t)["meta"]["moon_range"]
    assert p["start"] == pytest.approx(edge_moon(u, 0, 0, t), abs=1e-4)
    assert p["end"] == pytest.approx(u["meta"]["moon_range"]["end"], abs=2e-4)


def test_timed_charts_keep_a_null_moon_range(natal):
    t = at(natal, 2027, 6, 15)
    assert pg.progressed_chart(natal, t)["meta"]["moon_range"] is None
    assert pg.directed_chart(natal, t)["meta"]["moon_range"] is None


def test_target_before_the_birth_moment_is_the_birth_moment(cast):
    late = cast("--date", "1990-06-15", "--time", "18:30", *NY)
    t = at(late, 1990, 6, 15)                     # local noon, six and a half hours before birth
    assert t < late["meta"]["julian_day_ut"]
    for chart in (pg.progressed_chart(late, t), pg.directed_chart(late, t)):
        prog = chart["meta"]["progression"]
        assert prog["age_years"] == 0.0 and prog["solar_arc"] == 0.0 and prog["target_date"] == "1990-06-15"
        for n, b in late["bodies"].items():
            assert abs(pg.wrapped(chart["bodies"][n]["longitude"] - b["longitude"])) < 1e-3
        assert abs(pg.wrapped(chart["angles"]["ascendant"] - late["angles"]["ascendant"])) < 1e-3


def test_house_system_requested_is_carried_through(natal):
    natal["meta"]["house_system_requested"] = "koch"
    t = at(natal, 2027, 6, 15)
    for chart in (pg.progressed_chart(natal, t), pg.directed_chart(natal, t)):
        assert chart["meta"]["house_system_requested"] == "koch"
        assert chart["meta"]["house_system"] == chart["houses"]["system"] == "placidus"


def test_missing_chiron_stays_missing(natal):
    del natal["bodies"]["Chiron"]
    assert "Chiron" not in pg.progressed_chart(natal, at(natal, 2027, 6, 15))["bodies"]


def test_charts_record_the_pyswisseph_that_computed_them(natal):
    natal["meta"]["source"]["version"] = "2.08.00"          # as if cast with an older pyswisseph
    t = at(natal, 2027, 6, 15)
    for chart in (pg.progressed_chart(natal, t), pg.directed_chart(natal, t)):
        assert chart["meta"]["source"]["version"] == swe.version
        assert chart["meta"]["source"]["library"] == "pyswisseph"


@pytest.mark.needs_ephemeris
def test_charts_record_the_ephemeris_used(natal):
    t = at(natal, 2027, 6, 15)
    for chart in (pg.progressed_chart(natal, t), pg.directed_chart(natal, t)):
        assert chart["meta"]["source"]["ephemeris_files"] is True
        assert "chiron_unavailable" not in chart["meta"]["flags"] and "Chiron" in chart["bodies"]


def test_missing_ephemeris_files_flag_chiron_like_natal_chart(natal, no_ephemeris):
    t = at(natal, 2027, 6, 15)
    p, d = pg.progressed_chart(natal, t), pg.directed_chart(natal, t)
    assert "Chiron" not in p["bodies"] and "chiron_unavailable" in p["meta"]["flags"]
    # A directed Chiron is natal Chiron plus the arc: no ephemeris file needed.
    assert "Chiron" in d["bodies"] and "chiron_unavailable" not in d["meta"]["flags"]
    for chart in (p, d):
        assert chart["meta"]["source"] == {"library": "pyswisseph", "version": swe.version, "ephemeris_files": False}
    assert natal["meta"]["source"]["ephemeris_files"] is True
